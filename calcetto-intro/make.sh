#!/usr/bin/env bash
# Builds calcetto-intro.mp4: timeline cues -> synthesised audio -> frame-by-frame render -> H.264 + AAC.
#   ./make.sh              (60 fps)      FPS=30 ./make.sh   (30 fps)
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
mkdir -p build
node render.mjs --cues build/cues.json
python3 audio.py build/cues.json build/audio.wav
node render.mjs --video calcetto-intro.mp4 --audio build/audio.wav
