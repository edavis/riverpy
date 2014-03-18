riverpy
=======

riverpy is a River of News aggregator. It takes an OPML file
containing any number of RSS/Atom feeds organized by topic and
generates a river.js file for each topic representing the flow of
information from its feeds. Everything is then uploaded to Amazon S3
for the world to see.

Demo
----

A demo river can be found here: http://river.davising.com/

It is updated every hour from my personal [OPML file][opml].

[opml]: https://dl.dropboxusercontent.com/s/fk2riel6m5lz7nz/rss.opml

Installation
------------

  1. install/configure/start redis (default settings should work)
  2. `$ pip install -e git+https://github.com/edavis/riverpy.git#egg=riverpy-git`
  3. `$ river-init -b <S3-BUCKET> # only necessary once`
  4. `$ river -b <S3-BUCKET> <OPML-URL> # generate and upload river.js files`

I'll upload the package to PyPI once I'm confident other people are
able to get up and running with it.

Links
-----

  * http://riverjs.org/ -- the river.js specification
  * http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  * http://fargo.io/ -- web-based OPML editor
