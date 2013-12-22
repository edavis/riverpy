def format_timestamp(timestamp, fmt=None):
    if fmt is None:
        fmt = 'ddd, DD MMM YYYY HH:mm:ss Z'
    return timestamp.format(fmt)
