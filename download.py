import sys
import threading
import requests
import feedparser


class ParseFeed(threading.Thread):
    def __init__(self, inbox, outbox):
        threading.Thread.__init__(self)
        self.inbox = inbox
        self.outbox = outbox

    def run(self):
        while True:
            url = self.inbox.get()
            response = None

            try:
                response = requests.get(url, timeout=5.0)
                response.raise_for_status()
            except requests.exceptions.RequestException as ex:
                sys.stderr.write('[% -8s] *** skipping %s: %s\n' % (self.getName(), url, str(ex)))
                sys.stderr.flush()
            else:
                parsed = feedparser.parse(response.content)
                parsed.update({'feed_url': url})
                sys.stdout.write('[% -8s] %s (%d entries)\n' % (self.getName(), url, len(parsed.entries)))
                sys.stdout.flush()
                self.outbox.put(parsed)
            finally:
                self.inbox.task_done()
