riverpy -- Generate river.js files with Python

riverpy is a River of News aggregator that takes an OPML reading list,
parses any included RSS/Atom feeds, generates a river.js file and
uploads that file to Amazon S3.

Most RSS clients treat the news like email. There are unread counts,
stars or favorites, tagging, and a folder structure to keep things
organized.

While those clients have their place, they focus more on the
read/unread state of articles rather than the chronology of when the
articles arrived. And for news, this chronology is vitally important.

An alternative to email-style RSS clients are River of News aggregators.

River of News aggregators display the newest items up top and older
items are displayed as you scroll down. If you've ever used Twitter,
you've used a River of News aggregator.

With riverpy, I've tried to build a River of News aggregator that is
easy for people to set up and start using. It is written in Python and
uses redis as its datastore.

Installation:
  1) install/configure redis
  2) pip install -r requirements.txt # may need to install libxml2 header files
  3) cp sample.cfg config.cfg # edit as necessary
  4) ./river.py </path/to/config.cfg>

TODO:
  - Subscribe to OPML subscription lists just like RSS feeds
  - Write an installation guide
  - Package and upload to PyPI

Links:
  - http://goo.gl/g11EUE -- an example of a river
  - http://goo.gl/xVZeWl -- the OPML used to generate the above river
  - http://riverjs.org/ -- the river.js specification
  - http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  - http://fargo.io/ -- web-based OPML editor
