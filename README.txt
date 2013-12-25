riverpy is a River of News style aggregator that takes an OPML reading
list, parses any linked RSS/Atom feeds, generates a river.js file and
then hosts everything on Amazon S3.

To see one in action, http://river.davising.com/nyt/ is a river of
New York Times headlines that updates hourly.

Installation:
  1) install/configure/start redis (default settings should work)
  2) $ pip install -e git+https://github.com/edavis/riverpy.git#egg=riverpy-git
  3) $ river-init -b <S3-BUCKET> # one-time only
  4) $ river -b <S3-BUCKET> <OPML-URL> # generate and upload river.js files

I'll upload the package to PyPI once I'm confident other people are
able to get up and running with it.

Links:
  - http://goo.gl/aVIHeA -- OPML file used to generate the NYT river
  - http://riverjs.org/ -- the river.js specification
  - http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  - http://fargo.io/ -- web-based OPML editor
