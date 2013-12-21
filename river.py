#!/usr/bin/env python

import os
import json
import time
import Queue
import random
import cPickle
import hashlib
import operator
import argparse
from lxml import etree
from datetime import datetime
from cStringIO import StringIO

import redis
import arrow
import bleach
import requests
import feedparser

from download import ParseFeed


RFC2822_FORMAT = 'ddd, DD MMM YYYY HH:mm:ss Z'
THREADS = 8
OUTPUT_LIMIT = 250


def entry_fingerprint(feed, entry):
    s = ''.join([feed.feed_url,
                 entry.get('title', ''),
                 entry.get('link', ''),
                 entry.get('guid', '')])
    s = s.encode('utf-8', 'ignore')
    return hashlib.sha1(s).hexdigest()


def sort_entries(parsed_feeds):
    redis_client = redis.StrictRedis()
    for feed in parsed_feeds:
        for entry in feed.entries:
            fingerprint = entry_fingerprint(feed, entry)
            if redis_client.sismember('fingerprints', fingerprint):
                continue
            redis_client.sadd('fingerprints', fingerprint)
            obj = {'feed': feed.feed, 'entry': entry,
                   'url': feed.feed_url, 'timestamp': arrow.utcnow()}
            redis_client.lpush('entries', cPickle.dumps(obj))
            redis_client.ltrim('entries', 0, OUTPUT_LIMIT)
    return redis_client.lrange('entries', 0, OUTPUT_LIMIT)


def clean_text(text, limit=280, suffix=' ...'):
    cleaned = bleach.clean(text, tags=[], strip=True).strip()
    if len(cleaned) > limit:
        return ''.join(cleaned[:limit]) + suffix
    else:
        return cleaned


def write_river(fname, obj):
    s = StringIO()
    s.write('loadRiver(')
    json.dump(obj, s, sort_keys=True)
    s.write(')')
    with open(fname, 'w') as fp:
        fp.write(s.getvalue())


def parse_subscription_list(location):
    """
    Return an iterator of xmlUrls from an OPML file.

    'location' can be either local or remote.
    """
    if os.path.exists(location):
        with open(location) as fp:
            doc = etree.parse(fp)
        opml = doc.getroot()
    else:
        response = requests.get(location)
        opml = etree.fromstring(response.content)

    outlines = opml.xpath('//outline[@type="rss"]')
    for outline in outlines:
        xmlUrl = outline.get('xmlUrl')
        if xmlUrl:
            yield xmlUrl


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', default='river.js')
    parser.add_argument('opml')
    args = parser.parse_args()

    start = time.time()
    feed_urls = list(parse_subscription_list(args.opml))

    print('creating a river.js file for %d feeds' % len(feed_urls))

    # Download/parse the feeds, placing feedparser objects into outbox
    inbox = Queue.Queue()
    outbox = Queue.Queue()

    # Don't create more threads than there are URLs
    thread_count = min(len(feed_urls), THREADS)
    print('creating %d threads' % thread_count)

    for _ in range(thread_count):
        p = ParseFeed(inbox, outbox)
        p.daemon = True
        p.start()

    random.shuffle(feed_urls)
    for url in feed_urls:
        inbox.put(url)
    inbox.join()

    # Empty the outbox into parsed_feeds
    parsed_feeds = []
    while not outbox.empty():
        parsed_feeds.append(outbox.get_nowait())

    entries = sort_entries(parsed_feeds)
    river_entries = []
    for pickled_obj in entries:
        obj = cPickle.loads(pickled_obj)
        entry = obj['entry']
        feed = obj['feed']
        entry_title = entry.get('title', '') or entry.get('description', '')
        river_entries.append({
            'title': clean_text(entry_title),
            'link': entry.get('link', '#'),
            'description': clean_text(entry.get('description', '')),
            'pubDate': obj['timestamp'].format(RFC2822_FORMAT),
            'feed': {
                'title': feed.get('title', ''),
                'link': feed.get('link', ''),
                'url': obj['url'],
            },
        })


    river_obj = {
        'river': river_entries,
        'metadata': {
            'lastBuildDate': arrow.utcnow().format(RFC2822_FORMAT),
        },
    }

    write_river(args.output, river_obj)
    print('\nbuilt in %s seconds' % str(time.time() - start))
