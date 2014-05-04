import json
import logging
import operator
from path import path
from bucket import Bucket

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

def write_riverjs(dest, river_name, river_obj):
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
        if isinstance(dest, Bucket):
            dest.write_string(key, riverjs, 'application/json')
        elif isinstance(dest, path):
            fname = dest.joinpath(key)
            fname.parent.makedirs_p()
            with fname.open('w') as fp:
                fp.write(riverjs)

def generate_manifest(dest, rivers):
    manifest = []
    for river in rivers:
        manifest.append({
            'url': 'rivers/%s.json' % river['name'],
            'title': river['title'],
        })
    manifest = sorted(manifest, key=operator.itemgetter('title'))
    manifest_obj = json.dumps(manifest)
    logger.info('Writing manifest.json (%d bytes)' % len(manifest_obj))
    if isinstance(dest, Bucket):
        dest.write_string('manifest.json', manifest_obj, 'application/json')
    elif isinstance(dest, path):
        fname = dest.joinpath('manifest.json')
        with fname.open('w') as fp:
            fp.write(manifest_obj)
