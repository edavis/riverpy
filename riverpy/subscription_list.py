import requests
from lxml import etree

import utils
from river import River


class SubscriptionList(object):
    def __init__(self, opml_url):
        (self.head, self.body) = self.parse(opml)
        self.opml_url = opml_url

    def rivers(self):
        return set(self.body.xpath("./outline[@name]/@name"))

    def parse(self, url):
        response = requests.get(url)
        response.raise_for_status()
        return etree.fromstring(response.content)

    def outline_is_comment(self, outline):
        return outline.get('isComment') == 'true'

    def outline_is_rss(self, outline):
        return all([
            outline.get('type') == 'rss',
            outline.get('xmlUrl'),
            not self.outline_is_comment(outline)])

    def load_rivers(self):
        rivers = []
        for summit in self.body:
            if self.outline_is_comment(summit):
                continue
            river_name = summit.get('name')
            if not river_name:
                river_name = utils.slugify(summit.get('text', ''))
            assert river_name, 'all summits need either a name or text attribute'
            summit_type = summit.get('type')
            if summit_type is None:
                parent = summit
            elif summit_type == 'include':
                url = summit.get('url')
                head, parent = self.parse(url)
            feeds = [el.get('xmlUrl') for el in parent.iterdescendants() if self.outline_is_rss(el)]
            if feeds:
                rivers.append({
                    'name': river_name,
                    'title': summit.get('text', ''),
                    'description': summit.get('description', ''),
                    'feeds': feeds,
                })
        return rivers

    def __iter__(self):
        return iter([River(info, self.opml_url) for info in self.load_rivers()])
