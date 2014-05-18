import sys
import redis
import arrow
import random
import bleach
import logging
import cPickle
import hashlib
import requests
import threading
import feedparser
from datetime import datetime, timedelta
from utils import format_timestamp

logger = logging.getLogger(__name__)

class ParseFeed(threading.Thread):
    def __init__(self, inbox, args):
        threading.Thread.__init__(self)
        self.inbox = inbox
        self.cli_args = args
        self.redis_client = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            db=args.redis_db,
        )

    def entry_timestamp(self, entry):
        """
        Return an entry's timestamp as best that can be figured.

        If no timestamp can be found, return the current time.
        """
        for key in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if key not in entry: continue
            if entry[key] is None: continue
            val = (entry[key])[:6]
            reported_timestamp = arrow.get(datetime(*val))
            if reported_timestamp < arrow.utcnow():
                return reported_timestamp
        return arrow.utcnow()

    def clean_text(self, text, limit=280, suffix='&nbsp;...'):
        cleaned = bleach.clean(text, tags=[], strip=True).strip()
        if len(cleaned) > limit:
            return ''.join(cleaned[:limit]) + suffix
        else:
            return cleaned

    def entry_fingerprint(self, entry):
        if entry.get('guid'):
            return entry.get('guid')
        else:
            s = ''.join([
                entry.get('title', ''),
                entry.get('link', ''),
            ])
            s = s.encode('utf-8', 'ignore')
            return hashlib.sha1(s).hexdigest()

    def new_entry(self, feed_key, entry):
        """
        Return True if this entry hasn't been seen before in this feed.
        """
        return (self.entry_fingerprint(entry) not in
                set(self.redis_client.lrange(feed_key, 0, -1)))

    def add_feed_entry(self, feed_key, entry, limit=1000):
        """
        Add the entry to the feed key, capping at `limit'.
        """
        entry_key = self.entry_fingerprint(entry)
        self.redis_client.lpush(feed_key, entry_key)
        self.redis_client.ltrim(feed_key, 0, limit - 1)

    def populate_feed_update(self, entry):
        obj = {
            'id': str(self.redis_client.incr('id-generator')),
            'pubDate': format_timestamp(self.entry_timestamp(entry)),
        }

        # If both <title> and <description> exist:
        #   title -> <title>
        #   body -> <description>
        if entry.get('title') and entry.get('description'):
            obj['title'] = self.clean_text(entry.get('title'))
            obj['body'] = self.clean_text(entry.get('description'))

            # Drop the body if it's just a duplicate of the title.
            if obj['title'] == obj['body']:
                obj['body'] == ''

        # If <description> exists but <title> doesn't:
        #   title -> <description>
        #   body -> ''
        #
        # See http://scripting.com/2014/04/07/howToDisplayTitlelessFeedItems.html
        # for an ad-hoc spec.
        elif not entry.get('title') and entry.get('description'):
            obj['title'] = self.clean_text(entry.get('description'))
            obj['body'] = ''

        # If neither of the above work but <title> exists:
        #   title -> <title>
        #   body -> ''
        #
        # A rare occurance -- just about everybody uses both <title>
        # and <description> and those with title-less feeds just use
        # <description> (in keeping with the RSS spec) -- but the
        # Nieman Journalism Lab's RSS feed [1] needs this conditional
        # so I assume it's not the only one out there.
        #
        # [1] http://www.niemanlab.org/feed/
        elif entry.get('title'):
            obj['title'] = self.clean_text(entry.get('title'))
            obj['body'] = ''

        if entry.get('link'):
            obj['link'] = entry.get('link')

        if entry.get('comments'):
            obj['comments'] = entry.get('comments')

        return obj

    def request_feed(self, feed_url):
        headers_key = 'http:headers:%s' % feed_url
        body_key = 'http:body:%s' % feed_url

        request_headers = {}
        (last_modified, etag) = self.redis_client.hmget(headers_key, 'last-modified', 'etag')
        if last_modified:
            request_headers['If-Modified-Since'] = last_modified
        if etag:
            request_headers['If-None-Match'] = etag

        response = requests.get(feed_url, headers=request_headers, timeout=15, verify=False)
        response.raise_for_status()

        logger.info('Checked %s (%d)' % (feed_url, response.status_code))

        self.redis_client.hmset(headers_key, response.headers)

        if response.status_code == 200:
            self.redis_client.set(body_key, response.text)
            return response.text
        elif response.status_code == 304:
            return self.redis_client.get(body_key)

    def average_update_interval(self, history_timestamps):
        it = iter(history_timestamps)
        first = arrow.get(next(it))
        delta = timedelta()
        for timestamp in it:
            delta += (first - arrow.get(timestamp))
            first = arrow.get(timestamp)
        return delta / len(history_timestamps)

    def run(self):
        while True:
            feed_url = self.inbox.get()
            try:
                feed_content = self.request_feed(feed_url)
            except requests.exceptions.RequestException as ex:
                logger.exception('Failed to check %s' % feed_url)
                future = arrow.utcnow() + timedelta(seconds=60*60)
                fmt = format_timestamp(future.to('local'))
                logger.info('Next check for %s: %s (%d seconds)' % (feed_url, fmt, 60*60))
                self.redis_client.zadd('next_check', feed_url, future.timestamp)
            else:
                try:
                    feed_parsed = feedparser.parse(feed_content)
                except ValueError as ex:
                    logger.exception('Failed to parse %s' % feed_url)
                    break

                feed_key = '%s:entries' % feed_url
                new_feed = (self.redis_client.llen(feed_key) == 0)

                feed_updates = []
                timestamps = []

                for entry in feed_parsed.entries:
                    # We must keep track of feed updates so they're only seen
                    # once. Here's how that happens:
                    #
                    # Redis stores a list at `feed_key` that contains
                    # the 1000 (by default) most recently seen feed
                    # update fingerprints. See self.entry_fingerprint
                    # for how the fingerprint is calculated.
                    #
                    # If the fingerprint hasn't been seen before, add it
                    # to `feed_key`.
                    #
                    # If it has, this feed update has already been seen
                    # so we can skip it.
                    if self.new_entry(feed_key, entry):
                        self.add_feed_entry(feed_key, entry)
                    else:
                        continue

                    update = self.populate_feed_update(entry)
                    feed_updates.append(update)
                    timestamps.append(self.entry_timestamp(entry))

                timestamp_key = '%s:timestamps' % feed_url

                # Add any new timestamps found during this check
                if timestamps:
                    logger.info('%d new entries for %s' % (len(timestamps), feed_url))
                    new_timestamps = [obj.timestamp for obj in timestamps]
                    self.redis_client.lpush(timestamp_key, *new_timestamps)
                    self.redis_client.sort(timestamp_key, desc=True, store=timestamp_key)
                    self.redis_client.ltrim(timestamp_key, 0, 99)
                else:
                    logger.info('No new entries for %s' % feed_url)

                history = self.redis_client.lrange(timestamp_key, 0, 9 if timestamps else 8)
                if not timestamps:
                    # See http://goo.gl/X6QhWN for why we do this
                    history.insert(0, arrow.utcnow().timestamp)

                delta = self.average_update_interval(history)

                # Don't check more than once a minute
                if delta.seconds < 60:
                    delta = timedelta(seconds=60)

                # Cap the next check at two hours.
                elif delta.seconds > (2*60*60):
                    logger.debug('Randomly scheduling %s' % feed_url)
                    delta = timedelta(seconds=random.uniform(60*60, 2*60*60))

                future_update = arrow.utcnow() + delta
                fmt = format_timestamp(future_update.to('local'))

                logger.info('Next check for %s: %s (%d seconds)' % (feed_url, fmt, delta.seconds))
                self.redis_client.zadd('next_check', feed_url, future_update.timestamp)

                # Keep --initial most recent updates if this is the
                # first time we've seen the feed
                if new_feed:
                    feed_updates = feed_updates[:self.cli_args.initial]

                if feed_updates:
                    river_update = {
                        'feedDescription': feed_parsed.feed.get('description', ''),
                        'feedTitle': feed_parsed.feed.get('title', ''),
                        'feedUrl': feed_url,
                        'item': feed_updates,
                        'websiteUrl': feed_parsed.feed.get('link', ''),
                        'whenLastUpdate': format_timestamp(arrow.utcnow()),
                    }

                    for river_name in self.redis_client.smembers('%s:rivers' % feed_url):
                        river_key = 'rivers:%s' % river_name
                        self.redis_client.lpush(river_key, cPickle.dumps(river_update))
                        self.redis_client.ltrim(river_key, 0, self.cli_args.entries - 1)
                        self.redis_client.sadd('updated_rivers', river_name)

                    firehose_key = 'rivers:firehose'
                    self.redis_client.lpush(firehose_key, cPickle.dumps(river_update))
                    self.redis_client.ltrim(firehose_key, 0, self.cli_args.entries - 1)
                    self.redis_client.sadd('updated_rivers', 'firehose')

            finally:
                self.inbox.task_done()
