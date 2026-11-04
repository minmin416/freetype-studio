#!/bin/zsh
set -e
cd -- "${0:A:h}"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
print '설치 완료. Start.command를 더블클릭하세요.'
