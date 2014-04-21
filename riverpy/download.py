import sys
import redis
import arrow
import bleach
import hashlib
import requests
import threading
import cPickle
import feedparser
from datetime import datetime
from utils import format_timestamp

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

    def clean_text(self, text, limit=280, suffix=' ...'):
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

    def new_entry(self, entry, feed_url, river_name):
        """
        Return True if this entry hasn't been seen before in this feed.
        """
        feed_key = '%s:%s' % (river_name, feed_url)
        return (self.entry_fingerprint(entry) not in
                set(self.redis_client.lrange(feed_key, 0, -1)))

    def add_feed_entry(self, entry, feed_url, river_name, limit=1000):
        """
        Add the entry to the feed key, capping at `limit'.
        """
        feed_key = '%s:%s' % (river_name, feed_url)
        entry_key = self.entry_fingerprint(entry)
        self.redis_client.lpush(feed_key, entry_key)
        self.redis_client.ltrim(feed_key, 0, limit - 1)

    def populate_feed_update(self, entry):
        obj = {
            'id': str(self.redis_client.incr('id-generator')),
            'pubDate': format_timestamp(self.entry_timestamp(entry)),
        }

        # http://scripting.com/2014/04/07/howToDisplayTitlelessFeedItems.html

        if entry.get('title') and entry.get('description'):
            obj['title'] = self.clean_text(entry.get('title'))
            obj['body'] = self.clean_text(entry.get('description'))

            # Some feeds duplicate the title and
            # description. If so, drop the body here.
            if obj['title'] == obj['body']:
                obj['body'] == ''

        elif not entry.get('title') and entry.get('description'):
            obj['title'] = self.clean_text(entry.get('description'))
            obj['body'] = ''

        if entry.get('link'):
            obj['link'] = entry.get('link')

        if entry.get('comments'):
            obj['comments'] = entry.get('comments')

        return obj

    def run(self):
        while True:
            river_name, feed_url = self.inbox.get()
            print('Parsing %s' % feed_url)
            try:
                response = requests.get(feed_url, timeout=15, verify=False)
                response.raise_for_status()
            except requests.exceptions.RequestException as ex:
                pass
            else:
                try:
                    feed_parsed = feedparser.parse(response.content)
                except ValueError as ex:
                    break

                new_feed = (self.redis_client.llen(feed_url) == 0)

                feed_updates = []
                for entry in feed_parsed.entries:
                    if self.new_entry(entry, feed_url, river_name):
                        self.add_feed_entry(entry, feed_url, river_name)
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
