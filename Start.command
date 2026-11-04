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
  print '서버를 실행하지 못했습니다. server.log를 확인하세요.'
  exit 1
fi
open http://127.0.0.1:8791
