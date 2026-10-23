#!/bin/sh
set -eu
python3 "$(dirname "$0")/adpathlens.py" "$@"
