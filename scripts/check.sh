#!/bin/bash
# Snabbkoll av färdig video: längd, upplösning, ljudnivå (mål -14 LUFS).
V="$1"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration,size -of default=nw=1 "$V"
ffmpeg -hide_banner -i "$V" -af ebur128 -f null - 2>&1 | grep -A1 "Integrated" | tail -1
