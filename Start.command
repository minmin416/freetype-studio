#!/bin/zsh
set -e
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  ./Setup.command
fi
if ! curl -fs http://127.0.0.1:8791/api/fonts >/dev/null; then
  nohup .venv/bin/python server.py > server.log 2>&1 &
  for i in {1..40}; do
    if curl -fs http://127.0.0.1:8791/api/fonts >/dev/null; then
      break
    fi
    sleep 0.25
  done
fi
if ! curl -fs http://127.0.0.1:8791/api/fonts >/dev/null; then
  print 'Could not start the server. See server.log for details.'
  exit 1
fi
open http://127.0.0.1:8791
