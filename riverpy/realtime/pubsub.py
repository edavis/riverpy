import argparse
import base64
import logging
import redis
import requests
import uuid

from wsgiref.simple_server import make_server
from .pubsub_app import app

logger = logging.getLogger(__name__)

def subscribe_feed(topic_url, hub_url):
    return update_feed(topic_url, hub_url, 'subscribe')

def unsubscribe_feed(topic_url, hub_url):
    return update_feed(topic_url, hub_url, 'unsubscribe')

def update_feed(topic_url, hub_url, action):
    callback_base = '68.108.66.228:5917'
    callback_url = 'http://%s/%s' % (
        callback_base,
        base64.urlsafe_b64encode(topic_url),
    )
    params = {
        'hub.callback': callback_url,
        'hub.mode': action,
        'hub.topic': topic_url,
        'hub.verify': 'sync', # needed for v0.3, ignored in v0.4
    }
    return requests.post(hub_url, data=params)

def pubsub_server():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=5917, type=int, help="Port to listen on. [default: %(default)s]")
    parser.add_argument('--redis-host', default='127.0.0.1', help='Redis host to use. [default: %(default)s]')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port to use. [default: %(default)s]')
    parser.add_argument('--redis-db', default=0, type=int, help='Redis DB to use. [default: %(default)s]')
    args = parser.parse_args()

    redis_client = redis.Redis(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
    )

    httpd = make_server('', args.port, app)
    logger.info('Started HTTP server: http://0.0.0.0:%d/' % args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info('Stopping HTTP server')
