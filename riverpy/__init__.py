import time
import path
import Queue
import random
import argparse
import pkg_resources

from river import River
from bucket import Bucket, MissingBucket
from download import ParseFeed
from subscription_list import SubscriptionList


def river_cleanup():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True, help='Destination S3 bucket. Required.')
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('opml', help='Path or URL of OPML reading list')
    args = parser.parse_args()

    bucket = Bucket(args.bucket)
    bucket_rivers = bucket.rivers()
    opml_rivers = SubscriptionList(args.opml).rivers()
    stale_rivers = bucket_rivers - opml_rivers

    keys = []
    for river_name in stale_rivers:
        keys.extend([
            '%s/index.html' % river_name,
            'rivers/%s.js' % river_name,
        ])
        if not args.dry_run:
            River.flush(river_name)

    if not args.dry_run and keys:
        print('deleting: %r' % keys)
        bucket.bucket.delete_keys(keys)
    elif args.dry_run and keys:
        print('would delete: %r' % keys)


def river_init():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True)
    args = parser.parse_args()

    try:
        bucket = Bucket(args.bucket)
    except MissingBucket:
        bucket = Bucket.create(args.bucket)

    assets_root = path.path(pkg_resources.resource_filename('riverpy', 'assets'))
    for filename in assets_root.walkfiles():
        key_name = filename.replace(assets_root + '/', '')
        print('uploading %s' % key_name)
        bucket.write_file(key_name, filename)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True, help='Destination S3 bucket. Required.')
    parser.add_argument('-n', '--no-download', help='Do everything but download the feeds', action='store_true')
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates [default: %(default)s]')
    parser.add_argument('-r', '--river', help='Only operate on this river')
    parser.add_argument('-c', '--clear', help='Clear previously seen rivers', action='store_true')
    parser.add_argument('opml', help='Path or URL of OPML reading list')
    args = parser.parse_args()

    start_time = time.time()
    inbox = Queue.Queue()
    feed_cache = {}
    total_feeds = 0

    bucket = Bucket(args.bucket)
    rivers = SubscriptionList(args.opml)

    for t in xrange(args.threads):
        p = ParseFeed(inbox, feed_cache, args.initial, args.entries)
        p.daemon = True
        p.start()

    for river in rivers:
        if args.river and river.name != args.river: continue

        if args.clear and (river.name == args.river or not args.river):
            # If --clear was passed, 1) clear only the given --river
            # or 2) all rivers if no --river was passed
            river.clear()

        total_feeds += len(river)
        print('%s: checking %d feeds' % (river.name, len(river)))

        if args.no_download: continue

        feeds = river.info['feeds']
        random.shuffle(feeds)
        for feed in feeds:
            inbox.put((river, feed))

    print('%d total feeds to be checked' % total_feeds)

    # Wait for all the feeds to finish updating
    inbox.join()

    for river in rivers:
        if args.river and river.name != args.river: continue
        river.upload_template(bucket)
        elapsed = river.upload_riverjs(bucket, start_time)
        print('%s: %d feed updates, %d items (took %s seconds)' % (
            river.name, len(river.entries), river.item_count, elapsed))
