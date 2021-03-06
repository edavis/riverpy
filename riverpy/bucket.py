import boto
import time
import logging
from boto.s3.key import Key

logger = logging.getLogger(__name__)

class Bucket(object):
    def __init__(self, bucket_name):
        conn = boto.connect_s3()
        self.bucket = conn.lookup(bucket_name)
        if self.bucket is None:
            logger.debug("%s doesn't exist, creating" % bucket_name)
            self.bucket = conn.create_bucket(bucket_name)

    def write_string(self, path, string, content_type=None):
        key = Key(self.bucket, path)
        headers = {}
        if content_type is not None:
            headers['Content-Type'] = content_type
        key.set_contents_from_string(string, headers=headers, policy='public-read')
