#!/bin/zsh
set -e
cd -- "${0:A:h}"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
print 'Setup complete. Double-click Start.command to launch.'
