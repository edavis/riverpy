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
from cStringIO import StringIO

import boto
import arrow
import redis
import requests

from boto.s3.key import Key

from download import ParseFeed
import utils


redis_client = redis.Redis()


def s3_save(bucket_name, key_name, value, content_type=None, policy='public-read'):
    conn = boto.connect_s3()
    bucket = conn.lookup(bucket_name)
    assert bucket is not None, "bucket '%s' must exist" % bucket_name
    key = Key(bucket, key_name)
    if content_type is not None:
        key.set_metadata('Content-Type', content_type)
    key.set_contents_from_string(value, policy=policy)


def forget_river(river):
    """
    Delete everything we know about a given river.
    """
    keys = ['fingerprints', 'entries', 'counter', 'urls']
    redis_keys = [utils.river_key(river, key) for key in keys]
    redis_client.delete(*redis_keys)


def generate_riverjs(obj):
    s = StringIO()
    s.write('onGetRiverStream(')
    json.dump(obj, s, sort_keys=True)
    s.write(')')
    return s.getvalue()


def load_opml(location):
    if os.path.exists(os.path.expanduser(location)):
        with open(os.path.expanduser(location)) as fp:
            doc = etree.parse(fp)
        opml = doc.getroot()
    else:
        response = requests.get(location)
        response.raise_for_status()
        opml = etree.fromstring(response.content)
    return opml


def load_rivers(location):
    head, body = load_opml(location)
    rivers = {}
    for summit in body:
        if summit.get('isComment') == 'true':
            continue
        river_name = summit.get('name') or summit.get('text')
        outline_type = summit.get('type')
        if outline_type is None:
            rivers[river_name] = [el.get('xmlUrl') for el in summit.iterdescendants() if el.get('type') == 'rss']
        elif outline_type == 'include':
            url = summit.get('url')
            head, body = load_opml(url)
            rivers[river_name] = [el.get('xmlUrl') for el in body.iterdescendants() if el.get('type') == 'rss']
    return rivers


if __name__ == '__main__':
    start = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True, help='Destination S3 bucket. Required.')
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates [default: %(default)s]')
    parser.add_argument('opml', help='Path or URL of OPML reading list')
    args = parser.parse_args()

    rivers = load_rivers(args.opml)
    for river, urls in rivers.iteritems():
        print("generating '%s' river" % river)

        feed_count = len(urls)
        thread_count = min(feed_count, args.threads)

        print('parsing %d feeds with %d threads' % (feed_count, thread_count))

        inbox = Queue.Queue()
        for _ in range(thread_count):
            p = ParseFeed(river, args, inbox)
            p.daemon = True
            p.start()

        random.shuffle(urls)
        for url in urls:
            inbox.put(url)
        inbox.join()

        river_entries = utils.river_key(river, 'entries')
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

        key = 'rivers/%s.js' % river
        riverjs = generate_riverjs(river_obj)
        s3_save(args.bucket, key, riverjs, 'application/json')

        print('took %s seconds' % elapsed)
