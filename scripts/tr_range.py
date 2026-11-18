import sys
import soundfile as sf
import sherpa_onnx

wav, model_dir = sys.argv[1], sys.argv[2]
ranges = [tuple(map(float, r.split(":"))) for r in sys.argv[3:]]
audio, sr = sf.read(wav, dtype="float32")
rec = sherpa_onnx.OfflineRecognizer.from_whisper(
    encoder=f"{model_dir}/turbo-encoder.int8.onnx",
    decoder=f"{model_dir}/turbo-decoder.int8.onnx",
    tokens=f"{model_dir}/turbo-tokens.txt",
    language="sv", task="transcribe", num_threads=2,
)
for a, b in ranges:
    st = rec.create_stream()
    st.accept_waveform(sr, audio[int(a * sr):int(b * sr)])
    rec.decode_stream(st)
    print(f"{a:6.2f}-{b:6.2f}  {st.result.text.strip()}", flush=True)
