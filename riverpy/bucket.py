import boto
import time
from boto.s3.bucket import Bucket
from boto.s3.key import Key

class MissingBucket(Exception): pass

class Bucket(object):
    def __init__(self, bucket_name):
        conn = boto.connect_s3()
        self.bucket = conn.lookup(bucket_name)
        if self.bucket is None:
            raise MissingBucket("bucket '%s' doesn't exist" % bucket_name)

    @classmethod
    def create(cls, bucket_name):
        conn = boto.connect_s3()
        bucket = conn.create_bucket(bucket_name)
        time.sleep(5) # make sure the bucket has been created
        bucket.configure_website('index.html')
        time.sleep(5) # make sure the website settings take effect
        return cls(bucket_name)

    def rivers(self):
        _rivers = set()
        whitelist = ('css', 'images', 'js', 'favicon.ico',
                     'apple-touch-icon-precomposed.png', 'rivers')
        for obj in self.bucket.list(delimiter='/'):
            if obj.name.startswith(whitelist): continue
            _rivers.add(obj.name[:-1]) # remove trailing slash
        return _rivers

    def write_string(self, path, string, content_type=None):
        key = Key(self.bucket, path)
        if content_type is not None:
            key.set_metadata('Content-Type', content_type)
        key.set_contents_from_string(string, policy='public-read')

    def write_file(self, key_name, filename):
        key = Key(self.bucket, key_name)
        key.set_contents_from_filename(filename, policy='public-read')
