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

import boto
import arrow
import redis
import requests
import jinja2

from boto.s3.bucket import Bucket
from boto.s3.key import Key

from download import ParseFeed
import utils


redis_client = redis.Redis()


def read_config(*filenames):
    config = SafeConfigParser()
    config.read(filenames)
    return config


def write_to_s3(bucket_name, key_name, value):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucket_name) # TODO create if doesn't exist
    key = bucket.new_key(key_name)
    key.set_metadata('Content-Type', 'application/json')
    key.set_contents_from_string(value)
    key.set_acl('public-read')


def generate_riverjs(obj):
    s = StringIO()
    s.write('onGetRiverStream(')
    json.dump(obj, s, sort_keys=True)
    s.write(')')
    return s.getvalue()


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
    parser.add_argument('-u', '--url')
    parser.add_argument('-s', '--source')
    parser.add_argument('-c', '--clear', action='store_true')
    parser.add_argument('--no-download', action='store_true', help='Don\'t download feeds, only rebuild river.js file(s)')
    parser.add_argument('--clear-all', action='store_true')
    parser.add_argument('--init', action='store_true')
    parser.add_argument('config')
    args = parser.parse_args()

    start = time.time()
    config = read_config(args.config)

    if args.init:
        conn = boto.connect_s3()
        bucket = Bucket(conn, config.get('s3', 'bucket'))
        os.chdir('ui')
        for (dirpath, dirnames, filenames) in os.walk('.'):
            if 'index.html' in filenames:
                filenames.remove('index.html')
            for filename in filenames:
                joined = os.path.join(dirpath, filename)
                key = Key(bucket, joined.lstrip('./'))
                key.set_contents_from_filename(joined, policy='public-read')
        # Create a source if requested
        if args.source:
            environment = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
            index = environment.get_template('index.html')
            rendered = index.render(river='/rivers/%s.js' % args.source)
            key = Key(bucket, '%s/index.html' % args.source)
            key.set_metadata('Content-Type', 'text/html')
            key.set_contents_from_string(rendered, policy='public-read')
        raise SystemExit

    urls = []
    keys = ['fingerprints', 'entries', 'counter', 'urls']
    sources = config.get('river', 'sources').strip()
    for source in sources.splitlines():
        (opml_url, output_prefix) = source.split(' -> ', 1)
        # If we pass --source, only update that particular river
        if args.source and output_prefix != args.source:
            continue
        # If we pass --clear, forget everything we know about that
        # OPML file.
        if args.clear and args.source == output_prefix:
            print('clearing everything we know about %s' % output_prefix)
            redis_keys = [utils.river_key(opml_url, key) for key in keys]
            redis_client.delete(*redis_keys)
        urls.append((opml_url, output_prefix))

    if args.clear_all:
        for (opml, source) in urls:
            redis_keys = [utils.river_key(opml, key) for key in keys]
            redis_client.delete(*redis_keys)

    for opml_url, output_prefix in urls:
        print('generating river for %s' % output_prefix)

        if not args.no_download:
            if args.url:
                feed_urls = [args.url]
            else:
                feed_urls = list(parse_subscription_list(opml_url))

            # Don't create more threads than there are URLs
            feed_count = len(feed_urls)
            thread_count = min(feed_count, config.getint('limits', 'threads'))

            print('parsing %d feeds with %d threads' % (feed_count, thread_count))

            inbox = Queue.Queue()

            for _ in range(thread_count):
                p = ParseFeed(opml_url, config, inbox)
                p.daemon = True
                p.start()

            random.shuffle(feed_urls)
            for url in feed_urls:
                inbox.put(url)
            inbox.join()
        else:
            print('not downloading feeds')

        river_entries = utils.river_key(opml_url, 'entries')
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
                'source': opml_url,
            },
        }

        bucket = config.get('s3', 'bucket')
        key = 'rivers/%s.js' % output_prefix
        riverjs = generate_riverjs(river_obj)
        write_to_s3(bucket, key, riverjs)

        print('took %s seconds' % elapsed)

        # Print an empty line if we're hitting multiple feed lists
        if not args.source:
            print
