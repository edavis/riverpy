#!/usr/bin/env python

import os
import json
import time
import Queue
import random
import hashlib
import cPickle
import argparse
from lxml import etree
from datetime import datetime
from cStringIO import StringIO

import arrow
import redis
import requests

from download import ParseFeed
import constants


redis_client = redis.Redis()


def write_river(fname, obj, callback='onGetRiverStream'):
    s = StringIO()
    if callback:
        s.write('%s(' % callback)
    json.dump(obj, s, sort_keys=True)
    if callback:
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

    # Don't create more threads than there are URLs
    feed_count = len(feed_urls)
    thread_count = min(feed_count, constants.THREADS)

    print('parsing %d feeds with %d threads' % (feed_count, thread_count))

    inbox = Queue.Queue()

    if os.path.exists(args.opml):
        opml_location = os.path.abspath(args.opml)
    else:
        opml_location = args.opml

    for _ in range(thread_count):
        p = ParseFeed(opml_location, inbox)
        p.daemon = True
        p.start()

    random.shuffle(feed_urls)
    for url in feed_urls:
        inbox.put(url)
    inbox.join()

    river_prefix = 'riverpy:%s' % hashlib.sha1(opml_location).hexdigest()
    river_entries = ':'.join([river_prefix, 'entries'])
    pickled_objs = redis_client.lrange(river_entries, 0, constants.OUTPUT_LIMIT + 1)
    entries = [cPickle.loads(obj) for obj in pickled_objs]

    current = arrow.utcnow()
    elapsed = str(round(time.time() - start, 3))
    river_obj = {
        'updatedFeeds': {
            'updatedFeed': entries,
        },
        'metadata': {
            'docs': 'http://riverjs.org/',
            'whenGMT': current.format(constants.RFC2822_FORMAT),
            'whenLocal': current.to('local').format(constants.RFC2822_FORMAT),
            'secs': elapsed,
            'version': '3',
        },
    }
    if args.opml.startswith(('http://', 'https://')):
        river_obj['metadata']['source'] = args.opml

    write_river(args.output, river_obj)
    print('took %s seconds' % elapsed)
