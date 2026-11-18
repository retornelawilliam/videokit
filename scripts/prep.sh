#!/bin/bash
# Förbereder en ny video: jobbmapp, ljud, transkribering, energiprofil och stillbilder.
# Användning: prep.sh /mnt/user-data/uploads/IMG_1234.mov [sv|en]
set -e
SRC="$1"; LNG="${2:-sv}"
[ -f "$SRC" ] || { echo "Hittar inte $SRC"; exit 1; }
NAME=$(basename "${SRC%.*}")
J=/home/claude/jobs/$NAME; mkdir -p "$J/w"
cp -n "$SRC" "$J/" 2>/dev/null || true
V="$J/$(basename "$SRC")"
MODEL=/home/claude/models/sherpa-onnx-whisper-turbo
S=/home/claude/scripts

echo "== Källa"
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,color_transfer:stream_side_data=rotation:format=duration -of default=nw=1 "$V" | tee "$J/probe.txt"

ffmpeg -v error -y -i "$V" -vn -ac 1 -ar 16000 "$J/${NAME}_16k.wav"
ffmpeg -v error -y -i "$V" -vn -af dynaudnorm=f=150:g=15,highpass=f=80 -ac 1 -ar 16000 "$J/${NAME}_norm.wav"

echo "== Transkribering ($LNG)"
python3 $S/transcribe.py "$J/${NAME}_16k.wav" $MODEL "$J/${NAME}_segs.json" "$LNG" 2>/dev/null

# energiprofil (50 ms, dB) för exakta klipp-punkter
python3 - "$J/${NAME}_16k.wav" "$J/energy.txt" <<'EOF'
import soundfile as sf, numpy as np, sys
a, sr = sf.read(sys.argv[1]); hop = int(.05 * sr)
db = [20 * np.log10(np.sqrt(np.mean(a[i:i + hop] ** 2)) + 1e-9) for i in range(0, len(a) - hop, hop)]
open(sys.argv[2], "w").write(" ".join(f"{i * 0.05:.2f}:{int(d)}" for i, d in enumerate(db)))
EOF

# 4 stillbilder (tonemappade, spegelvända) så man ser var personen sitter
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
TRC=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of csv=p=0 "$V")
if [ "$TRC" = "arib-std-b67" ] || [ "$TRC" = "smpte2084" ]; then
  TM="zscale=tin=$TRC:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
else TM=""; fi
i=0; for f in 0.1 0.35 0.6 0.85; do
  t=$(python3 -c "print(round($DUR*$f,2))")
  ffmpeg -v error -y -ss $t -i "$V" -frames:v 1 -vf "${TM}hflip,scale=270:-2" "$J/w/still_$i.jpg"; i=$((i+1))
done
ffmpeg -v error -y -i "$J/w/still_0.jpg" -i "$J/w/still_1.jpg" -i "$J/w/still_2.jpg" -i "$J/w/still_3.jpg" -filter_complex hstack=4 "$J/stills.jpg"
echo "== Klart: $J  (stills.jpg = spegelvända stillbilder, energy.txt = ljudnivå)"
