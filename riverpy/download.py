import sys
import redis
import arrow
import bleach
import logging
import cPickle
import hashlib
import requests
import threading
import feedparser
from datetime import datetime
from utils import format_timestamp

logger = logging.getLogger(__name__)

class ParseFeed(threading.Thread):
    def __init__(self, inbox, args):
        threading.Thread.__init__(self)
        self.inbox = inbox
        self.cli_args = args
        self.redis_client = redis.Redis()

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
        s = ''.join([
            entry.get('title', ''),
            entry.get('link', ''),
            entry.get('guid', ''),
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
            obj['title'] = entry.get('title')
            obj['body'] = ''

        if entry.get('link'):
            obj['link'] = entry.get('link')

        if entry.get('comments'):
            obj['comments'] = entry.get('comments')

        return obj

    def run(self):
        while True:
            river_name, feed_url = self.inbox.get()
            logger.info('Checking %s' % feed_url)
            try:
                response = requests.get(feed_url, timeout=15, verify=False)
                response.raise_for_status()
            except requests.exceptions.RequestException as ex:
                logger.exception('Failed to load %s' % feed_url)
            else:
                try:
                    feed_parsed = feedparser.parse(response.content)
                except ValueError as ex:
                    logger.exception('Failed to parse %s' % feed_url)
                    break

                feed_key = '%s:%s' % (river_name, feed_url)
                new_feed = (self.redis_client.llen(feed_key) == 0)

                feed_updates = []
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
                    river_key = 'rivers:%s' % river_name
                    self.redis_client.lpush(river_key, cPickle.dumps(river_update))
                    self.redis_client.ltrim(river_key, 0, self.cli_args.entries - 1)

            finally:
                self.inbox.task_done()
