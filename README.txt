riverpy is a River of News style aggregator that takes an OPML reading
list, parses any linked RSS/Atom feeds, generates a river.js file and
uploads that file and a web-based viewer to Amazon S3.

Installation:
  1) install/configure redis
  2) pip install -r requirements.txt # may need to install libxml2 header files
  3) ./river.py -b <S3-BUCKET> <OPML-URL>

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
