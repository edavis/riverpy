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

    def write_string(self, path, string, content_type=None):
        key = Key(self.bucket, path)
        if content_type is not None:
            key.set_metadata('Content-Type', content_type)
        key.set_contents_from_string(string, policy='public-read')
