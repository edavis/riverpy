import path
import argparse
import pkg_resources

from river import River
from bucket import Bucket
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

    bucket = Bucket(args.bucket)

    if args.clear and args.river:
        River({'name': args.river}).clear()

    for river in SubscriptionList(args.opml):
        if args.river and river.name != args.river: continue
        if args.clear and not args.river: river.clear()

        print("generating '%s' river" % river.name)

        feed_count = len(river)
        thread_count = min(feed_count, args.threads)
        print('parsing %d feeds with %d threads' % (feed_count, thread_count))

        if not args.no_download:
            river.update(thread_count, args)

        print('%d feed updates with %d items' % (len(river.entries), river.item_count))

        river.upload_template(bucket)
        secs = river.upload_riverjs(bucket)
        print('took %s seconds' % secs)

        if not args.river:
            print('')
