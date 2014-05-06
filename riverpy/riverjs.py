import json
import logging
import operator
from path import path
from bucket import Bucket

logger = logging.getLogger(__name__)

def serialize_riverjs(river_obj, callback):
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

def serialize_manifest(rivers, callback):
    manifest = []
    for river in rivers:
        manifest.append({
            'url': 'rivers/%s.%s' % (river['name'], 'js' if callback else 'json'),
            'title': river['title'],
        })
    manifest = sorted(manifest, key=operator.itemgetter('title'))
    if callback:
        return 'onGetRiverManifest(%s)' % json.dumps(manifest)
    else:
        return json.dumps(manifest)
