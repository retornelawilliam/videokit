#!/bin/bash
cd /home/claude/vid4
E=/home/claude/scripts/iman4.py
for n in 2812 2813 2814 2815 2816 2817; do
  python3 $E c${n}_head.json --stage all > w/${n}h/all.log 2>&1
  echo "HEAD $n $(date +%T) $(ffprobe -v error -show_entries format=duration -of csv=p=0 w/${n}h/head.mp4)" >> queue6.log
done
for c in c2814_short c2815_short c2817_short; do
  python3 $E $c.json --stage all > w/${c}.log 2>&1
  echo "SHORT $c $(date +%T)" >> queue6.log
done
echo "ALLDONE" >> queue6.log
