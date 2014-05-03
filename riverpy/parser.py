import re
import yaml
import requests
from lxml import etree

from utils import slugify

is_remote = lambda url: url.startswith(('http://', 'https://'))

def parse_subscription_list(location):
    if location.endswith('.opml'):
        return parse_opml(location)
    else:
        return parse_yaml(location)

def parse_yaml(location):
    if is_remote(location):
        resp = requests.get(location)
        resp.raise_for_status()
        doc = yaml.load(resp.text)
    else:
        doc = yaml.load(open(location))

    for river, feeds in doc.items():
        yield {
            'name': slugify(river),
            'title': river,
            'feeds': feeds,
        }

def parse_opml(location):
    def _parse(loc):
        if is_remote(loc):
            resp = requests.get(loc)
            resp.raise_for_status()
            return etree.fromstring(resp.text)
        else:
            return etree.parse(loc).getroot()

    def _is_rss(el):
        return (el.get('type') == 'rss' and
                el.get('xmlUrl') and
                not el.get('isComment') == 'true')

    head, body = _parse(location)

    for summit in body:
        if summit.get('name'):
            river_name = summit.get('name')
        elif summit.get('text'):
            river_name = slugify(summit.get('text', ''))
        else:
            raise ValueError, 'all summits need either a name or text attribute'

        if summit.get('type') == 'include':
            _, parent = _parse(summit.get('url'))
        else:
            parent = summit

        feeds = [el.get('xmlUrl') for el in parent.iterdescendants() if _is_rss(el)]
        if feeds:
            yield {
                'name': river_name,
                'title': summit.get('text', ''),
                'feeds': feeds,
            }
