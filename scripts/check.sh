#!/bin/bash
# Snabbkoll av färdig video. Fullständig kontroll: python3 check.py JOB/cfg.json
V="$1"
CFG="$(dirname "$V")/cfg.json"
if [ -f "$CFG" ]; then exec python3 /home/claude/scripts/check.py "$CFG" "$V"; fi
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration,size -of default=nw=1 "$V"
ffmpeg -hide_banner -i "$V" -af ebur128 -f null - 2>&1 | grep -A1 "Integrated" | tail -1
