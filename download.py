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
    def __init__(self, inbox):
        threading.Thread.__init__(self)
        self.inbox = inbox

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
                    if redis_client.sismember('riverpy:fingerprints', fingerprint):
                        continue
                    redis_client.sadd('riverpy:fingerprints', fingerprint)

                    entry_title = entry.get('title', '')
                    entry_description = entry.get('description', '')
                    entry_link = entry.get('link', '')

                    # Only use guid when it looks like a URL
                    #
                    # Note: I think in theory URIs can also start with
                    # http:// but I don't think I've ever seen that in
                    # the wild
                    guid = entry.get('guid', '')
                    if guid and guid.startswith(('http://', 'https://')):
                        entry_permalink = guid
                    else:
                        entry_permalink = ''

                    obj = {
                        'link': entry_link,
                        'permaLink': entry_permalink,
                        'pubDate': entry_timestamp(entry).format(constants.RFC2822_FORMAT),
                        'title': clean_text(entry_title or entry_description),
                        'id': str(redis_client.incr('riverpy:next:entry')),
                    }

                    # entry.title gets first crack at being item.title in the river.
                    #
                    # But if entry.title doesn't exist, we're already
                    # using entry.description as the item.title so
                    # don't duplicate in item.body.
                    if entry_title:
                        obj['body'] = clean_text(entry_description)
                    else:
                        obj['body'] = ''

                    entry_comments = entry.get('comments')
                    if entry_comments:
                        obj['comments'] = entry_comments

                    # TODO add enclosure/thumbnail

                    items.append(obj)

                if items:
                    obj = {
                        'feedDescription': doc.feed.get('description', ''),
                        'feedTitle': doc.feed.get('title', ''),
                        'feedUrl': url,
                        'item': items,
                        'websiteUrl': doc.feed.get('link', ''),
                        'whenLastUpdate': arrow.utcnow().format(constants.RFC2822_FORMAT),
                    }
                    redis_client.lpush('riverpy:entries', cPickle.dumps(obj))
                    redis_client.ltrim('riverpy:entries', 0, constants.OUTPUT_LIMIT + 1)
            finally:
                self.inbox.task_done()
