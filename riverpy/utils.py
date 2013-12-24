import hashlib


def format_timestamp(timestamp, fmt=None):
    if fmt is None:
        fmt = 'ddd, DD MMM YYYY HH:mm:ss Z'
    return timestamp.format(fmt)


def river_key(opml, key):
    prefix = 'riverpy:' + hashlib.sha1(opml).hexdigest()
    return ':'.join([prefix, key])
