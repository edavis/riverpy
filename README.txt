riverpy -- a River of News aggregator for the modern web

riverpy is a River of News style feed aggregator that takes an OPML
reading list, parses any linked RSS/Atom feeds, generates a river.js
file and uploads that file and a web-based viewer to Amazon S3.

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
  - http://river.davising.com/sample/ -- an example of a river
  - http://goo.gl/xVZeWl -- the OPML used to generate the above river
  - http://riverjs.org/ -- the river.js specification
  - http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  - http://fargo.io/ -- web-based OPML editor
