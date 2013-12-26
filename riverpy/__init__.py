import path
import Queue
import random
import argparse
import pkg_resources

from river import River
from bucket import Bucket
from download import ParseFeed
from subscription_list import SubscriptionList


def river_init():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True)
    args = parser.parse_args()

    bucket = Bucket(args.bucket)
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
    total_feeds = 0

    bucket = Bucket(args.bucket)
    rivers = SubscriptionList(args.opml)

    for t in xrange(args.threads):
        p = ParseFeed(inbox, args.initial, args.entries)
        p.daemon = True
        p.start()

    for river in rivers:
        if args.river and river.name != args.river: continue
        # Clear a river if:
        # 1) We're on the provided --river
        # 2) No --river was provided (i.e., clear everything)
        if args.clear and river.name == args.river: river.clear()
        elif args.clear and not args.river: river.clear()

        total_feeds += len(river)
        print('%-25s: updating %d feeds' % (river.name, len(river)))

        if args.no_download: continue

        feeds = river.info['feeds']
        random.shuffle(feeds)
        for feed in feeds:
            inbox.put((river, feed))

    print('%d feeds to be checked' % total_feeds)

    # Wait for all the feeds to finish updating
    inbox.join()

    for river in rivers:
        river.upload_template(bucket)
        elapsed = river.upload_riverjs(bucket, start_time)
        print('%-25s: %d feed updates, %d items (took %s seconds)' % (
            river.name, len(river.entries), river.item_count, elapsed))
