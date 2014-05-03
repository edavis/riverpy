riverpy
=======

riverpy is a [River of News aggregator][river-of-news].

[river-of-news]: <http://threads2.scripting.com/2013/april/anotherPitchForRiverOfNews>

Given an [OPML file][opml] containing a
[list of RSS feeds organized by topic][river-opml], riverpy generates
a [river.js][] file for each topic.

[opml]: <http://dev.opml.org/spec2.html>
[river-opml]: <http://opml.davising.com/rss.opml>
[river.js]: <http://riverjs.org/>

 the flow of information from its feeds.

Everything is then uploaded to Amazon S3 for the world to see.

Links
-----

  * http://riverjs.org/ -- the river.js specification
  * http://dev.opml.org/spec2.html -- the OPML 2.0 specification
  * http://fargo.io/ -- web-based OPML editor
