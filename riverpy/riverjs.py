import json

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
    key = 'rivers/%s.js' % river_name
    riverjs = prepare_riverjs(river_obj)
    bucket.write_string(key, riverjs, 'application/json')

    # Also write raw JSON, in addition to JSONP
    key = 'rivers/%s.json' % river_name
    riverjs = prepare_riverjs(river_obj, callback=None)
    bucket.write_string(key, riverjs, 'application/json')

def generate_manifest(bucket, rivers, bucket_name):
    manifest = []
    for river in rivers:
        manifest.append({
            'url': 'rivers/%s.json' % river['name'],
            'title': river['title'],
        })
    bucket.write_string('manifest.json', json.dumps(manifest), 'application/json')
