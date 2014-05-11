import base64
import logging

from flask import Flask, request

app = Flask(__name__)

logger = logging.getLogger(__name__)

@app.route('/<encoded_url>', methods=['GET', 'POST'])
def handle(encoded_url):
    url = base64.urlsafe_b64decode(encoded_url.encode('utf-8'))
    logger.debug('Received URL: %r' % url)
    logger.debug('  Method: %r' % request.method)

    # Hub is verifying subscription
    if request.method == 'GET':
        logger.debug('  GET: %r' % request.args)
        return request.args.get('hub.challenge', '')

    elif request.method == 'POST':
        return ''
