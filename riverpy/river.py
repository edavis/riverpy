import json
import time
import Queue
import random
import hashlib
import cPickle
from cStringIO import StringIO

import redis
import arrow
import jinja2

import utils
from download import ParseFeed


class River(object):
    prefix = 'riverpy:'
    keys = ['fingerprints', 'entries', 'counter', 'urls']

    def __init__(self, info):
        self.info = info
        self.name = info['name']
        self.redis_client = redis.Redis()
        self.environment = jinja2.Environment(loader=jinja2.PackageLoader('riverpy', 'templates'))
        self.start = time.time()

    def __len__(self):
        return len(self.info['feeds'])

    def clear(self):
        redis_keys = [self.key(key) for key in self.keys]
        self.redis_client.delete(*redis_keys)

    @property
    def entries(self):
        objs = self.redis_client.lrange(self.key('entries'), 0, -1)
        return [cPickle.loads(obj) for obj in objs]

    @property
    def item_count(self):
        return sum([len(entry['item']) for entry in self.entries])

    def key(self, key):
        prefix = self.prefix + hashlib.sha1(self.name).hexdigest()
        return ':'.join([prefix, key])

    def update(self, thread_count, args):
        inbox = Queue.Queue()
        for t in xrange(thread_count):
            p = ParseFeed(inbox, self, args)
            p.daemon = True
            p.start()
        random.shuffle(self.info['feeds'])
        for url in self.info['feeds']:
            inbox.put(url)
        inbox.join()

    def upload_template(self, bucket):
        template = self.environment.get_template('index.html')
        rendered = template.render(name = self.name,
                                   title = self.info['title'],
                                   description = self.info['description'])
        bucket.write_string('%s/index.html' % self.name, rendered, 'text/html')

    def upload_riverjs(self, bucket):
        now = arrow.utcnow()
        elapsed = str(round(time.time() - self.start, 3))
        river_obj = {
            'updatedFeeds': {
                'updatedFeed': self.entries,
            },
            'metadata': {
                'docs': 'http://riverjs.org/',
                'whenGMT': utils.format_timestamp(now),
                'whenLocal': utils.format_timestamp(now.to('local')),
                'secs': elapsed,
                'version': '3',
            },
        }
        s = StringIO()
        s.write('onGetRiverStream(')
        json.dump(river_obj, s, sort_keys=True)
        s.write(')')
        bucket.write_string('rivers/%s.js' % self.name, s.getvalue(), 'application/json')
        return elapsed
