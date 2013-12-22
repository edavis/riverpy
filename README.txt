riverpy -- Generate river.js files with Python

river.py takes an OPML subscription list, parses its RSS/Atom
feeds, and outputs a river.js file.

Installation:
  1) install/configure redis
  2) pip install -r requirements.txt
  3) ./river.py -o </path/to/river.js> </path/to/config.cfg>

TODO:
  - Have river.py take care of "publishing" the resulting files (e.g.,
    copying to Amazon S3)
  - Subscribe to OPML subscription lists just like RSS feeds
  - Create a web frontend to render the river.js files
  - Package and upload to PyPI

Links:
  - http://riverjs.org/ for more information on river.js
  - http://nbariver.com/ for an example of a river of news feed.
