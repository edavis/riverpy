import json
import redis
import arrow
import Queue
import random
import cPickle
import argparse
import requests
from lxml import etree

from bucket import Bucket
from download import ParseFeed
from utils import format_timestamp, slugify
from riverjs import write_riverjs, generate_manifest

def parse_subscription_list(location):
    """
    Parse the source OPML that contains all the RSS feeds and their
    associated rivers/categories.

    :param location: URL or file path of OPML file
    """
    def _parse(loc):
        if loc.startswith(('http://', 'https://')):
            response = requests.get(loc)
            response.raise_for_status()
            return etree.fromstring(response.content)
        else:
            return etree.parse(loc).getroot()

    def _is_rss(el):
        return (el.get('type') == 'rss' and
                el.get('xmlUrl') and
                not el.get('isComment') == 'true')

    head, body = _parse(location)

    for summit in body:
        if summit.get('name'):
            river_name = summit.get('name')
        elif summit.get('text'):
            river_name = slugify(summit.get('text', ''))
        else:
            raise ValueError, 'all summits need either a name or text attribute'

        if summit.get('type') == 'include':
            _, parent = _parse(summit.get('url'))
        else:
            parent = summit

        feeds = [el.get('xmlUrl') for el in parent.iterdescendants() if _is_rss(el)]
        if feeds:
            yield {
                'name': river_name,
                'title': summit.get('text', ''),
                'feeds': feeds,
            }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', required=True, help='Destination S3 bucket. Required.')
    parser.add_argument('-t', '--threads', default=4, type=int, help='Number of threads to use for downloading feeds [default: %(default)s]')
    parser.add_argument('-e', '--entries', default=100, type=int, help='Display this many grouped feed updates [default: %(default)s]')
    parser.add_argument('-i', '--initial', default=5, type=int, help='Limit new feeds to this many new items [default: %(default)s]')
    parser.add_argument('opml', help='Path or URL of OPML reading list')
    args = parser.parse_args()

    total_feeds = 0
    redis_client = redis.Redis()
    s3_bucket = Bucket(args.bucket)

    inbox = Queue.Queue()
    for t in xrange(args.threads):
        p = ParseFeed(inbox, args)
        p.daemon = True
        p.start()

    rivers = list(parse_subscription_list(args.opml))
    for river in rivers:
        feeds = river['feeds']
        total_feeds += len(feeds)
        print('%s: checking %d feeds' % (river['name'], len(feeds)))
        random.shuffle(feeds)
        for feed in feeds:
            inbox.put((river['name'], feed))

    print('%d total feeds to be checked' % total_feeds)
    inbox.join()

    for river in rivers:
        river_key = 'rivers:%s' % river['name']
        river_updates = [cPickle.loads(update) for update in redis_client.lrange(river_key, 0, -1)]
        river_obj = {
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
        print('writing %s.js' % river['name'])
        write_riverjs(s3_bucket, river['name'], river_obj)

    print('generating manifest.json')
    generate_manifest(s3_bucket, rivers, args.bucket)
