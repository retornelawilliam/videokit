#!/bin/bash
# Installerar videokitet i en ny session (ca 2–4 min första gången, ~1 GB modeller från GitHub).
# Kör: bash /home/claude/videokit/setup.sh
set -e
K="$(cd "$(dirname "$0")" && pwd)"
H=/home/claude
mkdir -p $H/models/rnnoise $H/jobs

# 1) Motor, typsnitt och grafik på de sökvägar skripten väntar sig
for d in scripts fonts icons; do
  [ -L $H/$d ] && rm $H/$d
  [ -d $H/$d ] && [ ! -L $H/$d ] && mv $H/$d $H/${d}_old_$(date +%s)
  ln -sfn $K/$d $H/$d
done
cp -n $K/models/*.rnnn $H/models/rnnoise/ 2>/dev/null || true
chmod +x $K/scripts/*.sh

# 2) Python-paket (bara det som saknas)
python3 - <<'EOF' || pip install --quiet --break-system-packages sherpa-onnx onnxruntime opencv-python-headless soundfile scipy pillow playwright numpy num2words
import sherpa_onnx, onnxruntime, cv2, soundfile, scipy, PIL, playwright, numpy, num2words
EOF

# 3) Modeller från GitHub (Hugging Face är blockerat här)
if [ ! -f $H/models/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx ]; then
  echo "Laddar Whisper turbo (~560 MB)…"
  curl -sSL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-turbo.tar.bz2 | tar -xj -C $H/models
fi
OMNI=sherpa-onnx-omnilingual-asr-1600-languages-300M-ctc-int8-2025-11-12
if [ ! -f $H/models/$OMNI/model.int8.onnx ]; then
  echo "Laddar ordtids-modell (~290 MB)…"
  curl -sSL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$OMNI.tar.bz2 | tar -xj -C $H/models
fi
if [ ! -f $H/models/u2net_human_seg.onnx ]; then
  echo "Laddar personmask-modell (~170 MB)…"
  curl -sSL -o $H/models/u2net_human_seg.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
fi

# 4) Typsnitt synliga för libass/fontconfig (undertexter)
mkdir -p ~/.fonts && cp -n $K/fonts/*.ttf ~/.fonts/ 2>/dev/null; fc-cache -f >/dev/null 2>&1 || true

# 5) Chrome för grafiken (HTML -> PNG)
if [ ! -x /usr/bin/google-chrome ]; then
  echo "Chrome saknas – installerar Playwrights Chromium"; python3 -m playwright install chromium >/dev/null 2>&1 || true
fi

# 6) Kontroll
python3 - <<'EOF'
import os
need = ["/home/claude/models/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx", "/home/claude/models/u2net_human_seg.onnx",
        "/home/claude/models/sherpa-onnx-omnilingual-asr-1600-languages-300M-ctc-int8-2025-11-12/model.int8.onnx",
        "/home/claude/videokit/models/haarcascade_frontalface_default.xml", "/home/claude/scripts/align.py", "/home/claude/scripts/draft.py",
        "/home/claude/models/rnnoise/cb.rnnn", "/home/claude/fonts/Montserrat-Light.ttf", "/home/claude/fonts/InstrumentSerif-Italic.ttf",
        "/home/claude/scripts/iman5.py", "/home/claude/scripts/seqs.py"]
miss = [p for p in need if not os.path.exists(p)]
print("VIDEOKIT REDO" if not miss else "SAKNAS: " + ", ".join(miss))
EOF
