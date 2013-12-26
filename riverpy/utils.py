import re


def format_timestamp(timestamp, fmt=None):
    if fmt is None:
        fmt = 'ddd, DD MMM YYYY HH:mm:ss Z'
    return timestamp.format(fmt)


def slugify(s):
    s = re.sub('[^a-zA-Z0-9.]', '-', s)
    s = re.sub('--+', '-', s)
    return s.lower()
