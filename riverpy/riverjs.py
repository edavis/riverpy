import json
import logging
import operator
from path import path
from bucket import Bucket

logger = logging.getLogger(__name__)

def serialize_riverjs(river_obj, create_json):
    """
    Take a fully unpickled river object and serialize it into a JSON
    string.

    If callback is provided, make it JSONP.
    """
    serialized = json.dumps(river_obj, sort_keys=True)
    if create_json:
        return serialized
    else:
        return 'onGetRiverStream(%s)' % serialized
