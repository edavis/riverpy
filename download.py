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

import constants


redis_client = redis.Redis()


def entry_timestamp(entry):
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


def entry_fingerprint(url, entry):
    s = ''.join([url,
                 entry.get('title', ''),
                 entry.get('link', ''),
                 entry.get('guid', '')])
    s = s.encode('utf-8', 'ignore')
    return hashlib.sha1(s).hexdigest()


def clean_text(text, limit=280, suffix=' ...'):
    cleaned = bleach.clean(text, tags=[], strip=True).strip()
    if len(cleaned) > limit:
        return ''.join(cleaned[:limit]) + suffix
    else:
        return cleaned


class ParseFeed(threading.Thread):
    def __init__(self, opml, inbox):
        threading.Thread.__init__(self)
        self.inbox = inbox

        river_prefix = 'riverpy:%s' % hashlib.sha1(opml).hexdigest()
        self.river_fingerprints = ':'.join([river_prefix, 'fingerprints'])
        self.river_entries = ':'.join([river_prefix, 'entries'])
        self.river_counter = ':'.join([river_prefix, 'counter'])
        self.river_urls = ':'.join([river_prefix, 'urls'])

    def run(self):
        while True:
            url = self.inbox.get()
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as ex:
                sys.stderr.write('[% -8s] *** skipping %s: %s\n' % (self.getName(), url, str(ex)))
                sys.stderr.flush()
            else:
                doc = feedparser.parse(response.content)
                sys.stdout.write('[% -8s] %s (%d entries)\n' % (self.getName(), url, len(doc.entries)))
                items = []
                for entry in doc.entries:
                    fingerprint = entry_fingerprint(url, entry)
                    if redis_client.sismember(self.river_fingerprints, fingerprint):
                        continue
                    redis_client.sadd(self.river_fingerprints, fingerprint)

                    entry_title = entry.get('title', '')
                    entry_description = entry.get('description', '')
                    entry_link = entry.get('link', '')

                    obj = {
                        'link': entry_link,
                        'permaLink': '',
                        'pubDate': entry_timestamp(entry).format(constants.RFC2822_FORMAT),
                        'title': clean_text(entry_title or entry_description),
                        'id': str(redis_client.incr(self.river_counter)),
                    }

                    # entry.title gets first crack at being item.title
                    # in the river.
                    #
                    # But if entry.title doesn't exist, we're already
                    # using entry.description as the item.title so
                    # don't duplicate in item.body.
                    obj['body'] = clean_text(entry_description) if entry_title else ''

                    entry_comments = entry.get('comments')
                    if entry_comments:
                        obj['comments'] = entry_comments

                    # TODO add enclosure/thumbnail

                    items.append(obj)

                # First time we've seen this URL in this OPML file.
                # Only keep the first INITIAL_ITEM_LIMIT items.
                if not redis_client.sismember(self.river_urls, url):
                    items = items[:constants.INITIAL_ITEM_LIMIT]
                    redis_client.sadd(self.river_urls, url)

                if items:
                    obj = {
                        'feedDescription': doc.feed.get('description', ''),
                        'feedTitle': doc.feed.get('title', ''),
                        'feedUrl': url,
                        'item': items,
                        'websiteUrl': doc.feed.get('link', ''),
                        'whenLastUpdate': arrow.utcnow().format(constants.RFC2822_FORMAT),
                    }
                    redis_client.lpush(self.river_entries, cPickle.dumps(obj))
                    redis_client.ltrim(self.river_entries, 0, constants.ENTRIES_LIMIT + 1)
            finally:
                self.inbox.task_done()
