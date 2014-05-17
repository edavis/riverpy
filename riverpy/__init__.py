import time
import redis
import arrow
import Queue
import random
import cPickle
import logging
import argparse
from path import path

from bucket import Bucket
from download import ParseFeed
from utils import format_timestamp, slugify
from riverjs import serialize_riverjs, serialize_manifest
from parser import parse_subscription_list

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def init_logging(log_filename):
    fh = logging.FileHandler(log_filename)
    ch = logging.StreamHandler()
    fmt = logging.Formatter('[%(levelname)-5s] %(asctime)s - %(name)s - %(message)s')
    for handler in [fh, ch]:
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(fmt)
        logger.addHandler(handler)

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

def river_writer():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', help='Destination S3 bucket.')
    parser.add_argument('-o', '--output', help='Destination directory.')
    parser.add_argument('-l', '--log-filename', default='river.log', help='Location of log file. [default: %(default)s]')
    parser.add_argument('--json', action='store_true', help='Generate JSON instead of JSONP. [default: %(default)s]')
    parser.add_argument('--redis-host', default='127.0.0.1', help='Redis host to use. [default: %(default)s]')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port to use. [default: %(default)s]')
    parser.add_argument('--redis-db', default=0, type=int, help='Redis DB to use. [default: %(default)s]')
    args = parser.parse_args()

    init_logging(args.log_filename)

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
    pubsub.subscribe('update')

    for item in pubsub.listen():
        if item['type'] != 'message': continue
        river_name = item['data']
        river_obj = generate_river_obj(river_client, river_name)
        riverjs = serialize_riverjs(river_obj, args.json)
        key = 'rivers/%s.js' % river_name
        logger.info('Writing %s.js (%d bytes)' % (river_name, len(riverjs)))

        if s3_bucket:
            s3_bucket.write_string(key, riverjs, 'application/json')

        if output_directory:
            fname = output_directory.joinpath(key)
            fname.parent.makedirs_p()
            with fname.open('w') as fp:
                fp.write(riverjs)

        river_client.srem('updated_rivers', river_name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log-filename', default='river.log', help='Location of log file. [default: %(default)s]')
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds. [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates. [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items. [default: %(default)s]')
    parser.add_argument('--redis-host', default='127.0.0.1', help='Redis host to use. [default: %(default)s]')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port to use. [default: %(default)s]')
    parser.add_argument('--redis-db', default=0, type=int, help='Redis DB to use. [default: %(default)s]')
    parser.add_argument('feeds', help='Subscription list to use. Accepts URLs and filenames.')
    args = parser.parse_args()

    init_logging(args.log_filename)

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

    logger.info('In total, found %d categories (%d feeds)' % (len(rivers), total_feeds))

    for t in xrange(args.threads):
        p = ParseFeed(inbox, args)
        p.daemon = True
        p.start()

    while True:
        for feed_url in outdated_feeds(redis_client):
            inbox.put(feed_url)
        inbox.join()

        for updated_river in redis_client.smembers('updated_rivers'):
            redis_client.publish('update', updated_river)

        for (feed_url, timestamp) in upcoming_feeds(redis_client):
            obj = arrow.get(timestamp).to('local')
            future = obj - arrow.utcnow()
            logger.debug((feed_url, obj, future.seconds))

        logger.debug('')
        time.sleep(15)
