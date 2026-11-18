import sys, json
import numpy as np
import soundfile as sf
import sherpa_onnx

wav, model_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
lang = sys.argv[4] if len(sys.argv) > 4 else ""

audio, sr = sf.read(wav, dtype="float32")
hop = int(0.01 * sr)
win = int(0.03 * sr)
n = (len(audio) - win) // hop
rms = np.array([np.sqrt(np.mean(audio[i*hop:i*hop+win]**2) + 1e-12) for i in range(n)])
db = 20 * np.log10(rms)
thr = -38.0
speech = db > thr

# group into chunks, merging gaps shorter than 0.25s, dropping chunks < 0.15s
segs = []
start = None
for i, s in enumerate(speech):
    t = i * 0.01
    if s and start is None:
        start = t
    if not s and start is not None:
        segs.append([start, t]); start = None
if start is not None:
    segs.append([start, n * 0.01])
merged = []
for s in segs:
    if merged and s[0] - merged[-1][1] < 0.25:
        merged[-1][1] = s[1]
    else:
        merged.append(s)
merged = [s for s in merged if s[1] - s[0] >= 0.15]

# Whisper ser bara 30 s åt gången: dela långa bitar i den tystaste punkten mellan 35 och 65 %
def split_long(a, b):
    if b - a <= 24: return [[a, b]]
    i0, i1 = int((a + 0.35 * (b - a)) / 0.01), int((a + 0.65 * (b - a)) / 0.01)
    c = (i0 + int(np.argmin(db[i0:i1]))) * 0.01
    return split_long(a, c) + split_long(c, b)
merged = [x for a, b in merged for x in split_long(a, b)]

rec = sherpa_onnx.OfflineRecognizer.from_whisper(
    encoder=f"{model_dir}/turbo-encoder.int8.onnx",
    decoder=f"{model_dir}/turbo-decoder.int8.onnx",
    tokens=f"{model_dir}/turbo-tokens.txt",
    language=lang, task="transcribe", num_threads=2,
)
res = []
for a, b in merged:
    pa, pb = max(0, a - 0.08), min(len(audio) / sr, b + 0.08)
    chunk = audio[int(pa * sr):int(pb * sr)]
    st = rec.create_stream()
    st.accept_waveform(sr, chunk)
    rec.decode_stream(st)
    txt = st.result.text.strip()
    res.append({"start": round(a, 2), "end": round(b, 2), "text": txt})
    print(f"{a:6.2f}-{b:6.2f}  {txt}", flush=True)
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
