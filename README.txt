riverpy is a River of News aggregator. It takes an OPML file
containing an unlimited number of topics and associated RSS/Atom feeds
and generates a river.js file representing the flow of information
from those feeds. Everything is then uploaded to Amazon S3 for the
world to see.

A demo river can be found here: http://river.davising.com/nyt/

It is generated from an OPML file [1] made up of all the RSS
feeds offered by the New York Times [2]. It updates hourly.

[1] http://files.davising.com/opml/nytFeeds.opml
[2] http://www.nytimes.com/services/xml/rss/index.html

Installation:
  1) install/configure/start redis (default settings should work)
  2) $ pip install -e git+https://github.com/edavis/riverpy.git#egg=riverpy-git
  3) $ river-init -b <S3-BUCKET> # only necessary once
  4) $ river -b <S3-BUCKET> <OPML-URL> # generate and upload river.js files

I'll upload the package to PyPI once I'm confident other people are
able to get up and running with it.

Links:
  - http://riverjs.org/ -- the river.js specification
  - http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  - http://fargo.io/ -- web-based OPML editor
