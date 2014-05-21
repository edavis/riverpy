# riverpy

riverpy is a River of News aggregator written in Python that generates
[river.js][] files.

Click [here][riverpy-demo] to see a demo of riverpy in action.

[river.js]: <http://riverjs.org/>

## Overview

A River of News aggregator is a certain type of RSS reader.

As Dave Winer [puts it][quote]: "It's an application that reads feeds
you've subscribed to and presents only the new items, newest first. As
you scroll down you go back in time, to older items."

[quote]: <http://river2.newsriver.org/#whatIsARiverOfNewsStyleAggregator>
[riverpy-demo]: <http://river-demo.ericdavis.org/>

## Installation

Before you begin, make sure [redis][] is installed and running. On a
Mac, you can install it via [Homebrew][]. On Linux, your package
manager should have it.

Once installed, install riverpy into a [virtualenv][]:

```bash
$ virtualenv ~/riverpy-env
$ source ~/riverpy-env/bin/activate
$ pip install git+https://github.com/edavis/riverpy#egg=riverpy
```

[redis]: <http://redis.io/>
[Homebrew]: <http://brew.sh/>
[virtualenv]: <http://www.virtualenv.org/en/latest/>

## Quick Start

Once everything is installed, generate the files with `river`:

```bash
$ river -o ~/riverpy/ http://git.io/demo-list.txt
```

The resulting files are placed in `~/riverpy/`. See "Generated files"
for more details.

## Options

Pass `-b/--bucket` and/or `-o/--output` to tell `river` where to store
the generated files. At least one of these options is required, but
providing both will write the files to both locations.

"Bucket" refers to a [S3 bucket][S3]. "Output" is a local
directory. If the destination doesn't already exist, it will be
created.

[S3]: <http://docs.aws.amazon.com/AmazonS3/latest/dev/UsingBucket.html>

`-t/--threads` specifies the number of threads used to download your
subscribed feeds. Increasing this will speed up feed downloads but
also use more system resources. The default is four.

`-e/--entries` sets the max number of objects in the
`updatedFeeds.updatedFeed` array. The default is 100.

`-i/--initial` sets the max number of objects in the
`updatedFeeds.updatedFeed[n].item` array for newly subscribed
feeds. This prevents newly subscribed feeds from overwhelming a
river. The default is five.

Feeds that have been seen at least once before aren't subject to this
limit.

Pass `--json` to have `river` produce raw JSON files rather than JSONP.

Use `--redis-host`, `--redis-port`, or `--redis-db` to change how
`river` connects to redis. By default it'll connect to host 127.0.0.1,
port 6379, database 0.

Finally, a subscription list is required. This specifies which feeds
to check. `river` accepts both URLs and filenames here. The format of
this file is explained in the next section. As this is a required
argument, there is no default.

## Subscription lists

Subscription lists are plain text files that contain URLs of RSS feeds
grouped into categories.

Here's an example: http://git.io/demo-list.txt

It contains two categories ("News" and "Tech News") and a handful of
RSS feeds belonging to each.

Subscription lists can be edited by any text editor (e.g., Notepad,
TextEdit, etc.)

The format itself is pretty simple. Each category has a name followed
by a colon. Each feed belonging to that category follows this format:

- two spaces
- a dash
- another space
- the URL of the RSS feed

You must define at least one category. Beyond that, you can have as
many categories as you'd like.

There's no limit to the number of feeds a category can contain.

## Generated files

At the top-level of the destination will be a `manifest.js` file. This
file is generated to allow third-party programs an "entry point" so
they can find and display all available rivers. It is an array of
objects, each containing two keys: `url` and `title`.

Next to `manifest.js` will be a `rivers` sub-folder. Inside this
folder there will be a `.js` file for each category in your
subscription list. The category names are lowercased and special
characters are removed.

These `.js` files are formatted according to the [river.js][]
specification.

[JSON]: <http://en.wikipedia.org/wiki/JSON>
[JSON]: <http://en.wikipedia.org/wiki/JSONP>

## Web frontend

TODO: explain how to view the river.js files, CORS, and optionally
setting up S3 as a standard website host.

## Checking multiple subscription lists

It's recommended to use a different redis database (via `--redis-db`) for
each unique subscription list that `river` checks.

If you use the same redis database for different subscription lists,
categories with the same name will begin overwriting each other and
it'll be a mess.

## Refreshing feeds automatically

TODO: explain crontab

## Amazon S3

TODO: explain boto and necessary credentials

## OPML subscription lists

riverpy also accepts subscription lists in the OPML file format.

TODO: explain format

## License

TODO: pick license
