#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/.venv/bin/python3" "$DIR/main.py" "$@" &
disown
