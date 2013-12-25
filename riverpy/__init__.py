import os
import json
import path
import time
import Queue
import random
import jinja2
import cPickle
import argparse
import pkg_resources
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


def s3_bucket(bucket_name):
    """
    Return an S3 bucket, ensuring it exists first.
    """
    conn = boto.connect_s3()
    bucket = conn.lookup(bucket_name)
    assert bucket is not None, "bucket '%s' doesn't exist" % bucket_name
    return bucket


def s3_save(bucket_name, key_name, value, content_type=None, policy='public-read'):
    bucket = s3_bucket(bucket_name)
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


def serialize_riverjs(obj):
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


def outline_commented(outline):
    return outline.get('isComment') == 'true'


def outline_rss(outline):
    return all([
        outline.get('type') == 'rss',
        outline.get('xmlUrl'),
        not outline_commented(outline)])


def load_rivers(location):
    head, body = load_opml(location)
    rivers = {}
    for summit in body:
        if outline_commented(summit):
            continue
        river_name = summit.get('name') or summit.get('text')
        outline_type = summit.get('type')
        feeds = []
        if outline_type is None:
            feeds = [el.get('xmlUrl') for el in summit.iterdescendants() if outline_rss(el)]
        elif outline_type == 'include':
            url = summit.get('url')
            head, body = load_opml(url)
            feeds = [el.get('xmlUrl') for el in body.iterdescendants() if outline_rss(el)]
        if feeds:
            rivers[river_name] = feeds
    return rivers


def start_downloads(thread_count, args, river, urls):
    inbox = Queue.Queue()
    for _ in range(thread_count):
        p = ParseFeed(river, args, inbox)
        p.daemon = True
        p.start()
    random.shuffle(urls)
    for url in urls:
        inbox.put(url)
    return inbox.join()


def extract_entries(river):
    key = utils.river_key(river, 'entries')
    objs = redis_client.lrange(key, 0, -1)
    return [cPickle.loads(obj) for obj in objs]


def prepare_riverjs(started, entries):
    current = arrow.utcnow()
    elapsed = str(round(time.time() - started, 3))
    return {
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


def river_init():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True)
    args = parser.parse_args()

    bucket = s3_bucket(args.bucket)
    assets_root = path.path(pkg_resources.resource_filename('riverpy', 'assets'))
    for fname in assets_root.walkfiles():
        key_name = fname.replace(assets_root + '/', '')
        key = Key(bucket, key_name)
        print('uploading %s' % key_name)
        key.set_contents_from_filename(fname, policy='public-read')


def upload_template(bucket_name, river):
    bucket = s3_bucket(bucket_name)
    template = '%s/index.html' % river
    if bucket.lookup(template) is None:
        environment = jinja2.Environment(loader=jinja2.PackageLoader('riverpy', 'templates'))
        index_template = environment.get_template('index.html')
        key = Key(bucket, template)
        key.set_metadata('Content-Type', 'text/html')
        key.set_contents_from_string(index_template.render(river=river), policy='public-read')


def main():
    start = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True, help='Destination S3 bucket. Required.')
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates [default: %(default)s]')
    parser.add_argument('-r', '--river', help='Only operate on this river')
    parser.add_argument('-c', '--clear', help='Clear previously seen rivers', action='store_true')
    parser.add_argument('opml', help='Path or URL of OPML reading list')
    args = parser.parse_args()

    # Clear just the provided river if --river provided
    if args.clear and args.river:
        forget_river(args.river)

    rivers = load_rivers(args.opml)
    for river, urls in rivers.iteritems():
        if args.river and river != args.river:
            continue

        # Clear everything if no --river provided
        if args.clear and not args.river:
            forget_river(river)

        print("generating '%s' river" % river)

        feed_count = len(urls)
        thread_count = min(feed_count, args.threads)
        print('parsing %d feeds with %d threads' % (feed_count, thread_count))

        start_downloads(thread_count, args, river, urls)

        entries = extract_entries(river)
        item_count = sum([len(entry['item']) for entry in entries])
        print('%d feed updates with %d items' % (len(entries), item_count))

        upload_template(args.bucket, river)

        river_obj = prepare_riverjs(start, entries)
        riverjs = serialize_riverjs(river_obj)
        s3_save(args.bucket, 'rivers/%s.js' % river, riverjs, 'application/json')

        secs = river_obj['metadata']['secs']
        print('took %s seconds' % secs)
