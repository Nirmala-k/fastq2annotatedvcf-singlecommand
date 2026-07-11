#!/bin/sh
set -e

if [ "$#" -eq 0 ]; then
  exec python3 run_all.py
fi

if [ "$1" = "python3" ] || [ "$1" = "python" ] || [ "$1" = "/usr/bin/python3" ]; then
  exec "$@"
fi

exec python3 run_all.py "$@"
