import re
import redis
import jinja2
import cPickle


def format_timestamp(timestamp, fmt=None):
    if fmt is None:
        fmt = 'ddd, DD MMM YYYY HH:mm:ss Z'
    return timestamp.format(fmt)


def slugify(s):
    s = re.sub('[^a-zA-Z0-9.]', '-', s)
    s = re.sub('--+', '-', s)
    return s.lower()


def upload_log(bucket):
    redis_client = redis.Redis()
    entries = [cPickle.loads(entry) for entry in redis_client.lrange('riverpy:log', 0, -1)]
    environment = jinja2.Environment(loader=jinja2.PackageLoader('riverpy', 'templates'))
    environment.filters['format_timestamp'] = format_timestamp
    template = environment.get_template('log.html')
    rendered = template.render(entries=entries)
    bucket.write_string('log.html', rendered, 'text/html')


def upload_index(bucket, rivers):
    environment = jinja2.Environment(loader=jinja2.PackageLoader('riverpy', 'templates'))
    template = environment.get_template('index.html')
    rendered = template.render(rivers=rivers)
    bucket.write_string('index.html', rendered, 'text/html')
