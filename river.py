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
from ConfigParser import SafeConfigParser

import arrow
import redis
import requests

from download import ParseFeed
import utils


redis_client = redis.Redis()


def read_config(*filenames):
    config = SafeConfigParser()
    config.read(filenames)
    return config


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
    parser.add_argument('-o', '--output')
    parser.add_argument('config')
    args = parser.parse_args()

    start = time.time()

    config = read_config(args.config)
    opml = config.get('river', 'opml')

    feed_urls = list(parse_subscription_list(opml))

    # Don't create more threads than there are URLs
    feed_count = len(feed_urls)
    thread_count = min(feed_count, config.getint('limits', 'threads'))

    print('parsing %d feeds with %d threads' % (feed_count, thread_count))

    inbox = Queue.Queue()
    opml_location = os.path.abspath(opml) if os.path.exists(opml) else opml

    for _ in range(thread_count):
        p = ParseFeed(opml_location, config, inbox)
        p.daemon = True
        p.start()

    random.shuffle(feed_urls)
    for url in feed_urls:
        inbox.put(url)
    inbox.join()

    river_entries = utils.river_key(opml_location, 'entries')
    pickled_objs = redis_client.lrange(river_entries, 0, -1)
    entries = [cPickle.loads(obj) for obj in pickled_objs]
    count = sum([len(obj['item']) for obj in entries])
    print('%d feed updates with %d items' % (len(entries), count))

    current = arrow.utcnow()
    elapsed = str(round(time.time() - start, 3))
    river_obj = {
        'updatedFeeds': {
            'updatedFeed': entries,
        },
        'metadata': {
            'docs': 'http://riverjs.org/',
            'whenGMT': utils.format_timestamp(current),
            'whenLocal': utils.format_timestamp(current.to('local')),
            'secs': elapsed,
            'version': '3',
        },
    }
    if opml.startswith(('http://', 'https://')):
        river_obj['metadata']['source'] = opml

    write_river(args.output, river_obj)
    print('took %s seconds' % elapsed)
