riverpy is a River of News style aggregator that takes an OPML reading
list, parses any linked RSS/Atom feeds, generates a river.js file and
uploads that file and a web-based viewer to Amazon S3.

Installation:
  1) sudo aptitude install redis
  2) pip install riverpy
  3) river-init -b <S3-BUCKET>
  3) river -b <S3-BUCKET> <OPML-URL>

Links:
  - http://riverjs.org/ -- the river.js specification
  - http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  - http://fargo.io/ -- web-based OPML editor
