#!/bin/bash

for i in $(ls plugins/tests/); do
  if [ "$i" = "__pycache__" ]; then
    continue
  fi
  if [ "$i" = "__init__" ]; then
    continue
  fi

  python3 -m plugins.tests.${i/.py/}
done
