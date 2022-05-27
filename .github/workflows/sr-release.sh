#!/usr/bin/env bash

set -eE
set -v
echo pypy user=${PYPI_USERNAME}
poetry publish --build --username ${PYPI_USERNAME} --password ${PYPI_TOKEN}
