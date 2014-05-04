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
from riverjs import write_riverjs, generate_manifest
from parser import parse_subscription_list

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)-5s] %(asctime)s - %(name)s - %(message)s',
)

logging.getLogger('requests').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', help='Destination S3 bucket.')
    parser.add_argument('-o', '--output', help='Destination directory.')

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

    s3_bucket = None
    output_directory = None

    if args.bucket:
        s3_bucket = Bucket(args.bucket)

    if args.output:
        output_directory = path(args.output)
        output_directory.makedirs_p()

    rivers = list(parse_subscription_list(args.feeds))
    for river in rivers:
        feeds = list(set(river['feeds']))
        total_feeds += len(feeds)
        logger.info("Found category '%s' (%d feeds)" % (river['title'], len(feeds)))
        random.shuffle(feeds)
        for feed in feeds:
            inbox.put((river['name'], feed))

    logger.info('In total, found %d categories (%d feeds)' % (len(rivers), total_feeds))

    for t in xrange(args.threads):
        p = ParseFeed(inbox, args)
        p.daemon = True
        p.start()

    inbox.join()

    logger.info('Done checking feeds')

    for river in rivers:
        river_key = 'rivers:%s' % river['name']
        river_updates = [cPickle.loads(update) for update in redis_client.lrange(river_key, 0, -1)]
        river_obj = {
            'updatedFeeds': {
                'updatedFeed': river_updates,
            },
            'metadata': {
                'docs': 'http://riverjs.org/',
                'subscriptionList': args.feeds,
                'whenGMT': format_timestamp(arrow.utcnow()),
                'whenLocal': format_timestamp(arrow.utcnow().to('local')),
                'version': '3',
                'secs': '',
            },
        }
        if s3_bucket:
            write_riverjs(s3_bucket, river['name'], river_obj)

        if output_directory:
            write_riverjs(output_directory, river['name'], river_obj)

    if s3_bucket:
        generate_manifest(s3_bucket, rivers)

    if output_directory:
        generate_manifest(output_directory, rivers)
