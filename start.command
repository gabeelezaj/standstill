#!/bin/zsh
# Fallback launcher: double-click this if the app bundle won't open.
cd "$(dirname "$0")/web" || exit 1
PORT=8777
curl -s -o /dev/null -m 1 "http://127.0.0.1:$PORT/" || \
  (/usr/bin/python3 -m http.server $PORT --bind 127.0.0.1 </dev/null >/dev/null 2>&1 &)
sleep 1
open -a "Google Chrome" "http://localhost:$PORT/" 2>/dev/null || open "http://localhost:$PORT/"
