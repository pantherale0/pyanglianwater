<div align="center">

# pyanglianwater

A module to interact with Anglian Water and retrieve smart meter usage.

[![Build Status](https://github.com/pantherale0/pyanglianwater/workflows/build/badge.svg)](https://github.com/pantherale0/pyanglianwater/actions)
[![Coverage Status](https://coveralls.io/repos/github/pantherale0/pyanglianwater/badge.svg?branch=main)](https://coveralls.io/github/pantherale0/pyanglianwater?branch=main)
[![PyPi](https://img.shields.io/pypi/v/pyanglianwater)](https://pypi.org/project/pyanglianwater)
[![Licence](https://img.shields.io/github/license/pantherale0/pyanglianwater)](LICENSE)

<img src="https://raw.githubusercontent.com/justintime50/assets/main/src/python-template/showcase.png" alt="Showcase">

</div>

## Install

```bash
# Install tool
pip3 install pyanglianwater

# Install locally
just install
```

## Usage

TODO

### Unavailable hourly readings

`AnglianWater.get_usages()` can raise
`pyanglianwater.exceptions.HourlyReadingsUnavailableError` when the hourly usage
endpoint returns HTTP 500 with error code `"1"` and description
`"Failed to retrieve usage data"`. This suggests that hourly readings are
unavailable, but does not confirm that they are disabled on the account.

The exception exposes the original HTTP `status` and raw `response`, and chains
the original `UnknownEndpointError` as its cause. Other failures and usage
frequencies retain their existing error handling.

## Development

```bash
# Get a comprehensive list of development tools
just --list
```
