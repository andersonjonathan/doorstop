[![Unix Build Status](https://img.shields.io/travis/com/doorstop-dev/doorstop/develop.svg?label=unix)](https://travis-ci.com/doorstop-dev/doorstop)
[![Windows Build Status](https://img.shields.io/appveyor/ci/jacebrowning/doorstop/develop.svg?label=windows)](https://ci.appveyor.com/project/jacebrowning/doorstop)
<br>
[![Coverage Status](http://img.shields.io/coveralls/doorstop-dev/doorstop/develop.svg)](https://coveralls.io/r/doorstop-dev/doorstop)
[![Scrutinizer Code Quality](http://img.shields.io/scrutinizer/g/doorstop-dev/doorstop.svg)](https://scrutinizer-ci.com/g/doorstop-dev/doorstop/?branch=develop)
[![PyPI Version](http://img.shields.io/pypi/v/Doorstop.svg)](https://pypi.org/project/Doorstop)
<br>
[![Gitter](https://badges.gitter.im/doorstop-dev/community.svg)](https://gitter.im/doorstop-dev/community)
[![Google](https://img.shields.io/badge/forum-on_google-387eef)](https://groups.google.com/forum/#!forum/doorstop-dev)
[![Best Practices](https://bestpractices.coreinfrastructure.org/projects/754/badge)](https://bestpractices.coreinfrastructure.org/projects/754)

# Overview

Doorstop is a [requirements management](http://alternativeto.net/software/doorstop/) tool that facilitates the storage of textual requirements alongside source code in version control.

<img align="left" width="100" src="https://raw.githubusercontent.com/doorstop-dev/doorstop/develop/docs/images/logo-black-white.png"/>

When a project leverages this tool, each linkable item (requirement, test case, etc.) is stored as a YAML file in a designated directory. The items in each directory form a document. The relationship between documents forms a tree hierarchy. Doorstop provides mechanisms for modifying this tree, validating item traceability, and publishing documents in several formats.

Doorstop is under active development and we welcome contributions.
The project is licensed as [LGPLv3](https://github.com/doorstop-dev/doorstop/blob/develop/LICENSE.md).
To report a problem or a security vulnerability please [raise an issue](https://github.com/doorstop-dev/doorstop/issues).
Additional references:

- publication: [JSEA Paper](http://www.scirp.org/journal/PaperInformation.aspx?PaperID=44268#.UzYtfWRdXEZ)
- talks: [GRDevDay](https://speakerdeck.com/jacebrowning/doorstop-requirements-management-using-python-and-version-control), [BarCamp](https://speakerdeck.com/jacebrowning/strip-searched-a-rough-introduction-to-requirements-management)
- sample: [Generated HTML](http://doorstop-dev.github.io/doorstop/)


# Changes in this forked version of Doorstop

## Documents
Documents can have a `name` and a `level` that is used for order and display in the TOC.

## Items

* Items can have a `stakeholder` that links to another item, see `ROLE` below for context.
* Items can have a `prio` that is visible in the published report.
* Items can have a `implemented` state that is `true` or `false` and is visible as a checkmark or cross in the published report.
* Items can have links to JIRA by using the `jira` keyword as a list.
* The logic in fetching child items has changed to be able to have links to any item.
* The following prefixes has a special meaning
  * TEST - Used to define a test case, listed as tests in the published report.
  * USECASE - Used to define a use case, listed as use cases in the published report.
  * ROLE - Used to define a stakeholder, listed as stakeholders in the published report.

## CLI

* Added `--jira-url` to enable links to JIRA issues.
* Added `--result-file` to include test results in the traceability matrix
    The result file should be a YAML file with the test item as the key and look something like this:
  ```yaml
  TEST-0001:
  - function: test_get_all_news
    result_file: /results.xml
    status: passed
  - function: test_get_all_news
    result_file: /results_v2.xml
    status: failure
  TEST-0002:
  - function: test_create_news
    result_file: /results.xml
    status: error
  TEST-0003:
  - function: test_get_latest_news_for_user
    result_file: /results.xml
    status: skipped
  ```
* Added `--doc-title` and `--doc-version`, these strings are included in the published report.

## Published report
* Added bootstrap css on index page.
* Added title and version to index page.
* Removed old `Item traceability` matrix due to issues with the child logic and lack of understanding for the intended purpose.
* Added search to index page to easier find requirements.
* Added a traceability matrix that starts from a use case shows the associated requirements and the testcases for those requirements. If provided, the test results are also shown.

## Limitations:
Only the following links are supported in the traceability matrix.
* Use case -> Requirement
* Requirement -> Test

# Setup

## Requirements

* Python 3.5+
* A version control system for requirements storage

## Installation

Install Doorstop with pip:

```sh
$ pip install doorstop
```

or add it to your [Poetry](https://poetry.eustace.io/) project:

```sh
$ poetry add doorstop
```

After installation, Doorstop is available on the command-line:

```sh
$ doorstop --help
```

And the package is available under the name 'doorstop':

```sh
$ python
>>> import doorstop
>>> doorstop.__version__
```

# Usage

Switch to an existing version control working directory, or create one:

```sh
$ git init .
```

## Create documents

Create a new parent requirements document:

```sh
$ doorstop create SRD ./reqs/srd
```

Add a few items to that document:

```sh
$ doorstop add SRD
$ doorstop add SRD
$ doorstop add SRD
```

## Special item prefixes
The following prefixes has a special meaning
* TEST
* USECASE
* ROLE

### Test items
Items with the TEST prefix should map to a testcase.

### USECASE item
Items with the USECASE prefix work the same way as requirements but gets links grouped.

### ROLE item
Items with the ROLE prefix should describe stakeholders.
Other items may have the `stakeholder` attribute to show who is the stakeholder to a requirement.


## Link items

Create a child document to link to the parent:

```sh
$ doorstop create HLTC ./tests/hl --parent SRD
$ doorstop add HLTC
```

Link items between documents:

```sh
$ doorstop link HLTC001 SRD002
```

## Publish reports

Run integrity checks on the document tree:

```sh
$ doorstop
```

Publish the documents as HTML:

```sh
$ doorstop publish all ./public
```
