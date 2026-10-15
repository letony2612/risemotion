#!/bin/sh
# The renderer mixes the music about 2.7 dB under the file. This puts assets/music.wav back on the rendered
# picture at its own level (as loud as the file itself), the picture copied as is.
# Usage: sh tools/master.sh renders/RISE_mots_v6.mp4
set -e
in="$1"
tmp="${in%.mp4}.master.mp4"
ffmpeg -v error -y -i "$in" -i assets/music.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 256k -ar 48000 -movflags +faststart "$tmp"
mv "$tmp" "$in"
