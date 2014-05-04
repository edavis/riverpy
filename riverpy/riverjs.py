import json
import logging

logger = logging.getLogger(__name__)

def prepare_riverjs(river_obj, callback='onGetRiverStream'):
    """
    Take a fully unpickled river object and serialize it into a JSON
    string.

    If callback is provided, make it JSONP.
    """
    serialized = json.dumps(river_obj, sort_keys=True)
    if callback:
        return '%s(%s)' % (callback, serialized)
    else:
        return serialized

def write_riverjs(bucket, river_name, river_obj):
    """
    Write the riverjs JSON to Amazon S3.
    """
    river_types = [
        ('rivers/%s.js' % river_name, 'onGetRiverStream'),
        ('rivers/%s.json' % river_name, None),
    ]
    for (key, callback) in river_types:
        riverjs = prepare_riverjs(river_obj, callback=callback)
        logger.info('Writing %s (%d bytes)' % (key, len(riverjs)))
        bucket.write_string(key, riverjs, 'application/json')

def generate_manifest(bucket, rivers, bucket_name):
    manifest = []
    for river in rivers:
        manifest.append({
            'url': 'rivers/%s.json' % river['name'],
            'title': river['title'],
        })
    manifest_obj = json.dumps(manifest)
    logger.info('Writing manifest.json (%d bytes)' % len(manifest_obj))
    bucket.write_string('manifest.json', manifest_obj, 'application/json')
