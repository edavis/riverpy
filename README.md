# riverpy

riverpy is a River of News aggregator written in Python that generates
[river.js][] files.

[river.js]: <http://riverjs.org/>

## Overview

A River of News aggregator is a certain type of RSS reader.

As Dave Winer [puts it][]: "It's an application that reads feeds
you've subscribed to and presents only the new items, newest first. As
you scroll down you go back in time, to older items."

Click [here][riverpy-demo] to see a demo of riverpy in action.

[puts it]: <http://river2.newsriver.org/#whatIsARiverOfNewsStyleAggregator>
[riverpy-demo]: <http://riverpy-demo.s3.amazonaws.com/index.html>

## Installation

Make sure [redis][] is installed. On a Mac, you can install it via
[Homebrew][]. On Linux, your package manager should have it.

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

Once everything is installed, generate the river.js files with `river`:

```bash
$ river -o ~/riverpy/ http://git.io/demo-list.txt
```

This'll generate separate river.js files for the "News" and "Tech
News" categories (defined [here][demo-list.txt]) and place them in
`~/riverpy/rivers/`.

From here, you can begin creating your own subscription lists. See the
next section for the subscription list format.

[demo-list.txt]: <http://git.io/demo-list.txt>

## Options

TODO: explain available command-line arguments.

## Subscription lists

Subscription lists are plain text files that contain URLs of RSS feeds
grouped into categories.

Here's an example: http://git.io/demo-list.txt

It contains two categories ("News" and "Tech News") and a handful of
RSS feeds.

Subscription lists can be edited by any text editor (e.g., Notepad,
TextEdit, etc.)

The format itself is pretty simple. Each category has a name followed
by a colon. Then each feed belonging to that category follows this
format:

- two spaces
- a dash
- another space
- the URL of the RSS feed

You can have as many (or as few) categories as you want. Though there
must be at least one defined category.

There's no limit to the number of feeds a category can contain.

## Web frontend

TODO: explain how to view the river.js files

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
