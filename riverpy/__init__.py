import json
import time
import redis
import arrow
import Queue
import random
import cPickle
import logging
import operator
import argparse
from path import path

from bucket import Bucket
from download import ParseFeed
from utils import format_timestamp, slugify
from riverjs import serialize_riverjs
from parser import parse_subscription_list

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fmt = logging.Formatter('[%(levelname)-5s] %(asctime)s - %(name)s - %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)

def generate_river_obj(redis_client, river_name):
    """
    Return a dict that matches the river.js spec.
    """
    river_key = 'rivers:%s' % river_name
    river_updates = [cPickle.loads(update) for update in redis_client.lrange(river_key, 0, -1)]
    return {
        'updatedFeeds': {
            'updatedFeed': river_updates,
        },
        'metadata': {
            'docs': 'http://riverjs.org/',
            'whenGMT': format_timestamp(arrow.utcnow()),
            'whenLocal': format_timestamp(arrow.utcnow().to('local')),
            'version': '3',
            'secs': '',
        },
    }

def outdated_feeds(redis_client):
    """
    Return all the feeds that need to be checked.
    """
    return redis_client.zrangebyscore('next_check', '-inf', arrow.utcnow().timestamp)

def upcoming_feeds(redis_client, num=5):
    """
    Return the feeds that are next to be checked.
    """
    return redis_client.zrange('next_check', 0, num - 1, withscores=True)

def write_to_bucket(bucket, key, data):
    if bucket is not None:
        bucket.write_string(key, data, 'application/json')

def write_to_file(directory, key, data):
    if directory is not None:
        fname = directory.joinpath(key)
        fname.parent.makedirs_p()
        with fname.open('w') as fp:
            fp.write(data)

def river_writer():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', help='Destination S3 bucket.')
    parser.add_argument('-o', '--output', help='Destination directory.')
    parser.add_argument('--json', action='store_true', help='Generate JSON instead of JSONP. [default: %(default)s]')
    parser.add_argument('--redis-host', default='127.0.0.1', help='Redis host to use. [default: %(default)s]')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port to use. [default: %(default)s]')
    parser.add_argument('--redis-db', default=0, type=int, help='Redis DB to use. [default: %(default)s]')
    args = parser.parse_args()

    if not args.bucket and not args.output:
        raise SystemExit('Need either a -b/--bucket or -o/--output directory. Exiting.')

    # Need two clients as redis_client can't do anything else once it
    # subscribes to the channel.
    redis_client = redis.Redis(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
    )

    river_client = redis.Redis(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
    )

    if args.bucket:
        s3_bucket = Bucket(args.bucket)
    else:
        s3_bucket = None

    if args.output:
        output_directory = path(args.output)
        output_directory.makedirs_p()
    else:
        output_directory = None

    pubsub = redis_client.pubsub()
    pubsub.subscribe('update:%d' % args.redis_db)

    manifest = []
    for item in pubsub.listen():
        if item['type'] != 'message': continue

        update_msg = cPickle.loads(item['data'])
        available_rivers = update_msg['available_rivers']
        updated_rivers = update_msg['updated_rivers']
        updated_manifest = False

        for river_name in updated_rivers:
            river_obj = generate_river_obj(river_client, river_name)
            riverjs = serialize_riverjs(river_obj, args.json)
            key = 'rivers/%s.js' % river_name
            logger.info('Writing %s.js (%d bytes)' % (river_name, len(riverjs)))

            write_to_bucket(s3_bucket, key, riverjs)
            write_to_file(output_directory, key, riverjs)

            for river_obj in available_rivers:
                if river_obj['name'] == river_name:
                    break

            manifest_obj = {
                'title': river_obj['title'],
                'url': 'rivers/%s.js' % river_obj['name'],
            }

            if manifest_obj not in manifest:
                updated_manifest = True
                manifest.append(manifest_obj)

            river_client.srem('updated_rivers', river_name)

        if updated_manifest:
            manifest = sorted(manifest, key=operator.itemgetter('title'))
            if args.json:
                manifest_js = json.dumps(manifest)
            else:
                manifest_js = 'onGetRiverManifest(%s)' % json.dumps(manifest)
            logger.info('Writing manifest.js (%d bytes)' % len(manifest_js))
            write_to_bucket(s3_bucket, 'manifest.js', manifest_js)
            write_to_file(output_directory, 'manifest.js', manifest_js)
            updated_manifest = False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds. [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates. [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items. [default: %(default)s]')
    parser.add_argument('--redis-host', default='127.0.0.1', help='Redis host to use. [default: %(default)s]')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port to use. [default: %(default)s]')
    parser.add_argument('--redis-db', default=0, type=int, help='Redis DB to use. [default: %(default)s]')
    parser.add_argument('feeds', help='Subscription list to use. Accepts URLs and filenames.')
    args = parser.parse_args()

    redis_client = redis.Redis(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
    )
    total_feeds = 0
    inbox = Queue.Queue()

    rivers = list(parse_subscription_list(args.feeds))
    for river in rivers:
        for feed_url in river['feeds']:
            redis_client.sadd('%s:rivers' % feed_url, river['name'])
            if redis_client.zrank('next_check', feed_url) is None:
                redis_client.zadd('next_check', feed_url, -1)
        total_feeds += len(river['feeds'])

    rivers.append({'title': 'Firehose', 'name': 'firehose'})
    logger.info('In total, found %d categories (%d feeds)' % (len(rivers), total_feeds))

    for t in xrange(args.threads):
        p = ParseFeed(inbox, args)
        p.daemon = True
        p.start()

    while True:
        for feed_url in outdated_feeds(redis_client):
            inbox.put(feed_url)
        inbox.join()

        update_msg = {
            'available_rivers': rivers,
            'updated_rivers': redis_client.smembers('updated_rivers'),
        }
        redis_client.publish('update:%d' % args.redis_db, cPickle.dumps(update_msg))

        for (feed_url, timestamp) in upcoming_feeds(redis_client):
            obj = arrow.get(timestamp).to('local')
            future = obj - arrow.utcnow()
            logger.debug((feed_url, obj, future.seconds))

        logger.debug('')
        time.sleep(15)
