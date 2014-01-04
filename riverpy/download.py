import sys
import hashlib
import threading
import cPickle
from datetime import datetime

import redis
import arrow
import bleach
import requests
import feedparser

import utils


class ParseFeed(threading.Thread):
    def __init__(self, inbox, feed_cache, initial_limit, entries_limit):
        threading.Thread.__init__(self)
        self.inbox = inbox
        self.feed_cache = feed_cache
        self.initial_limit = initial_limit
        self.entries_limit = entries_limit
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

    def entry_fingerprint(self, entry):
        s = ''.join([entry.get('title', ''),
                     entry.get('link', ''),
                     entry.get('guid', '')])
        s = s.encode('utf-8', 'ignore')
        return hashlib.sha1(s).hexdigest()


    def clean_text(self, text, limit=280, suffix=' ...'):
        cleaned = bleach.clean(text, tags=[], strip=True).strip()
        if len(cleaned) > limit:
            return ''.join(cleaned[:limit]) + suffix
        else:
            return cleaned

    def run(self):
        while True:
            river, url = self.inbox.get()
            river_fingerprints = river.key('fingerprints')
            river_entries = river.key('entries')
            river_counter = river.key('counter')
            river_urls = river.key('urls')

            try:
                feed_content = self.feed_cache.get(url)
                if feed_content is None:
                    response = requests.get(url, timeout=10, verify=False)
                    response.raise_for_status()
                    feed_content = response.content
                    self.feed_cache[url] = feed_content
            except requests.exceptions.RequestException as ex:
                sys.stderr.write('[% -8s] *** skipping %s: %s\n' % (self.name, url, str(ex)))
            else:
                try:
                    doc = feedparser.parse(feed_content)
                except ValueError as ex:
                    sys.stderr.write('[% -8s] *** failed parsing %s: %s\n' % (self.name, url, str(ex)))
                    break
                items = []
                for entry in doc.entries:
                    fingerprint = self.entry_fingerprint(entry)
                    if self.redis_client.sismember(river_fingerprints, fingerprint):
                        continue
                    self.redis_client.sadd(river_fingerprints, fingerprint)

                    entry_title = entry.get('title', '')
                    entry_description = entry.get('description', '')
                    entry_link = entry.get('link', '')

                    obj = {
                        'link': entry_link,
                        'permaLink': '',
                        'pubDate': utils.format_timestamp(self.entry_timestamp(entry)),
                        'title': self.clean_text(entry_title or entry_description),
                        'id': str(self.redis_client.incr(river_counter)),
                    }

                    # entry.title gets first crack at being item.title
                    # in the river.
                    #
                    # But if entry.title doesn't exist, we're already
                    # using entry.description as the item.title so
                    # don't duplicate in item.body.
                    obj['body'] = self.clean_text(entry_description) if entry_title else ''

                    # If entry.title == entry.description, remove
                    # item.body and just leave item.title
                    if (entry_title and entry_description) and self.clean_text(entry_title) == self.clean_text(entry_description):
                        obj['body'] = ''

                    entry_comments = entry.get('comments')
                    if entry_comments:
                        obj['comments'] = entry_comments

                    # TODO add enclosure/thumbnail

                    items.append(obj)

                # First time we've seen this URL in this OPML file.
                # Only keep the first INITIAL_ITEM_LIMIT items.
                if not self.redis_client.sismember(river_urls, url):
                    items = items[:self.initial_limit]
                    self.redis_client.sadd(river_urls, url)

                if items:
                    sys.stdout.write('[% -8s] %s (%d new)\n' % (self.name, url, len(items)))
                    obj = {
                        'feedDescription': doc.feed.get('description', ''),
                        'feedTitle': doc.feed.get('title', ''),
                        'feedUrl': url,
                        'item': items,
                        'websiteUrl': doc.feed.get('link', ''),
                        'whenLastUpdate': utils.format_timestamp(arrow.utcnow()),
                    }
                    self.redis_client.lpush(river_entries, cPickle.dumps(obj))
                    self.redis_client.ltrim(river_entries, 0, self.entries_limit - 1)
            finally:
                self.inbox.task_done()
