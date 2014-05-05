# riverpy

riverpy is a River of News aggregator written in Python that generates
[river.js][] files.

[river.js]: <http://riverjs.org/>

## Overview

A River of News aggregator is a certain type of RSS reader.

As Dave Winer [puts it][quote]: "It's an application that reads feeds
you've subscribed to and presents only the new items, newest first. As
you scroll down you go back in time, to older items."

I find it a more pleasant and natural way of reading the
news. Newspapers don't have unread counts. Why should RSS readers?

Click [here][riverpy-demo] to see a demo of riverpy in action.

[quote]: <http://river2.newsriver.org/#whatIsARiverOfNewsStyleAggregator>
[riverpy-demo]: <http://riverpy-demo.s3.amazonaws.com/index.html>

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

This'll create manifest.json and separate river.js formatted files for
each category defined in http://git.io/demo-list.txt and place them in
`~/riverpy/`.

## Options

TODO: explain available command-line arguments.

## Generated files

TODO: explain manifest.json and js/json files.

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

You can have as many (or as few) categories you'd like. Though there
must be at least one category.

There's no limit to the number of feeds a category can contain.

## Web frontend

TODO: explain how to view the river.js files, CORS, and optionally
setting up S3 as a standard website host.

## Refreshing feeds automatically

TODO: explain crontab

## Amazon S3

riverpy can write its files to local disk or to Amazon S3. If you
won't be using S3 you can skip this section.

You'll need an Amazon AWS account to use S3. Creating an account is
beyond the scope of this guide.

Once an account has been created, you'll need to configure your
credentials so riverpy can use them.

TODO: needed permissions?

## OPML subscription lists

riverpy also accepts subscription lists in the OPML file format.

TODO: explain format

## License

TODO: pick license
