#!/usr/bin/env python

import os
import json
import time
import Queue
import random
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


def entry_timestamp(entry):
    """
    Determine the timestamp for a feed entry.

    Return 'None' if no timestamp can be found or the timestamp found
    is in the future.
    """
    for key in ['published_parsed', 'updated_parsed', 'created_parsed']:
        if key not in entry: continue
        if entry[key] is None: continue
        val = (entry[key])[:6]
        reported_timestamp = arrow.get(datetime(*val))
        return reported_timestamp if reported_timestamp < arrow.utcnow() else None


def sort_entries(parsed_feeds):
    """
    Return all feed entries ordered by timestamp descending.
    """
    redis_client = redis.StrictRedis()
    entries = []
    for feed in parsed_feeds:
        for entry in feed.entries:
            entry_link = entry.get('link', '')
            timestamp_key = 'timestamp:' + hashlib.sha1(feed.feed_url + entry_link).hexdigest()
            if redis_client.exists(timestamp_key) and entry_link:
                timestamp = redis_client.get(timestamp_key)
                timestamp = arrow.get(timestamp)
            else:
                timestamp = entry_timestamp(entry) or arrow.utcnow()
                redis_client.set(timestamp_key, timestamp)
            obj = {'feed': feed.feed, 'entry': entry, 'url': feed.feed_url}
            entries.append((timestamp, obj))
    return sorted(entries, key=operator.itemgetter(0), reverse=True)


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

    # Sort all the entries by their respective timestamp
    entries = sort_entries(parsed_feeds)
    print('\nparsed %d entries from %d feeds' % (len(entries), len(feed_urls)))

    river_entries = []
    for (timestamp, obj) in entries[:OUTPUT_LIMIT]:
        entry = obj['entry']
        feed = obj['feed']
        entry_title = entry.get('title', '') or entry.get('description', '')
        river_entries.append({
            'title': clean_text(entry_title),
            'link': entry.get('link', '#'),
            'description': clean_text(entry.get('description', '')),
            'pubDate': timestamp.format(RFC2822_FORMAT),
            'pubDateGenerated': entry_timestamp(entry) is None,
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
    print('built in %s seconds' % str(time.time() - start))
