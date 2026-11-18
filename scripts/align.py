"""Ordtider automatiskt: tvingad justering (CTC, Omnilingual ASR) av Whisper-texten mot ljudet.

usage: python3 align.py JOB/NAME_16k.wav JOB/NAME_segs.json JOB/words.json [sv|en]

Skriver:
  words.json  [{"w": ord som Whisper skrev, "s": start, "e": slut, "c": säkerhet 0–1, "seg": chunk}, ...]  (källtid, s)
  words.txt   läsbar lista: tid, ord, säkerhet (? = osäkert ord)
  gaps.json   partier med tal som inte matchar texten (Whisper tvättar ofta bort omtagningar) + CTC:s ordagranna text
Ersätter manuellt letande med tr_range.py. Rättad text kan justeras om: --text fix.txt (en rad per chunk i segs.json).
"""
import json, re, sys
import numpy as np, soundfile as sf, onnxruntime as ort

MD = "/home/claude/models/sherpa-onnx-omnilingual-asr-1600-languages-300M-ctc-int8-2025-11-12"
FR = 0.02          # 20 ms per CTC-ruta
BLANK, SPACE = 0, 4

wav, segs_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
LANG = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else "sv"
FIX = open(sys.argv[sys.argv.index("--text") + 1]).read().strip().split("\n") if "--text" in sys.argv else None

audio, sr = sf.read(wav, dtype="float32")
assert sr == 16000, "kräver 16 kHz mono (prep.sh skapar *_16k.wav)"
segs = json.load(open(segs_p))
if FIX:
    assert len(FIX) == len(segs), f"--text: {len(FIX)} rader men {len(segs)} chunkar"
    for s, t in zip(segs, FIX): s["text"] = t

tok2id, id2tok = {}, {}
for line in open(f"{MD}/tokens.txt", encoding="utf-8").read().split("\n"):
    if not line: continue
    t, i = line.rsplit(" ", 1)
    t = " " if t == "" else t
    tok2id.setdefault(t, int(i)); id2tok[int(i)] = t
sess = ort.InferenceSession(f"{MD}/model.int8.onnx", providers=["CPUExecutionProvider"])

# ---------- 10 ms energi (för att förfina ordens kanter) ----------
H = 160
env = np.array([np.sqrt(np.mean(audio[i:i + 2 * H] ** 2) + 1e-12) for i in range(0, len(audio) - 2 * H, H)])
env = 20 * np.log10(np.convolve(env, np.ones(3) / 3, mode="same"))
FLOOR = float(np.percentile(env, 10))

def logprobs(x):
    """CTC-logprob per 20 ms. Långa fönster körs i bitar om 30 s med överlapp."""
    def run(y):
        y = (y - y.mean()) / (y.std() + 1e-5)
        lg = sess.run(None, {"x": y[None].astype(np.float32)})[0][0]
        lg = lg - lg.max(-1, keepdims=True)
        return lg - np.log(np.exp(lg).sum(-1, keepdims=True))
    n = len(x) // 320
    if len(x) <= 38 * sr: return run(x)[:n]
    W, ST, out_ = 30 * sr, 26 * sr, []
    for a in range(0, len(x), ST):
        lp = run(x[a:a + W]); f0 = a // 320
        lo = 0 if a == 0 else 2 * sr // 320
        hi = len(lp) if a + W >= len(x) else len(lp) - 2 * sr // 320
        out_.append((f0 + lo, lp[lo:hi]))
        if a + W >= len(x): break
    full = np.full((n + 50, out_[0][1].shape[1]), -50.0, np.float32)
    for f0, lp in out_: full[f0:f0 + len(lp)] = lp[:max(0, len(full) - f0)]
    return full[:n]

# ---------- text -> CTC-tecken ----------
SAY = {"sv": {"@": " snabel a ", "&": " och ", "%": " procent", "+": " plus ", "/": " ", ".": " punkt "},
       "en": {"@": " at ", "&": " and ", "%": " percent", "+": " plus ", "/": " slash ", ".": " dot "}}[LANG if LANG in ("sv", "en") else "en"]

def spoken(word):
    w = word.lower()
    try:
        from num2words import num2words
        w = re.sub(r"\d+([.,]\d+)?", lambda m: " " + num2words(float(m.group(0).replace(",", ".")) if re.search("[.,]", m.group(0)) else int(m.group(0)), lang=LANG) + " ", w)
    except Exception:
        pass
    w = re.sub(r"(?<=\w)\.(?=\w)", SAY["."], w)                    # retornela.com -> retornela punkt com
    for k, v in SAY.items():
        if k != ".": w = w.replace(k, v)
    w = w.replace("-", " ")
    w = "".join(ch for ch in w if ch == " " or ch in tok2id)
    return re.sub(r"\s+", " ", w).strip()

def viterbi(lp, tgt):
    """CTC-tvångsjustering. Returnerar för varje mål-tecken (ruta_första, ruta_sista)."""
    T, L = len(lp), len(tgt)
    ext = np.full(2 * L + 1, BLANK); ext[1::2] = tgt
    S = len(ext)
    skip = np.zeros(S, bool)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    em = lp[:, ext]                                              # T x S
    NEG = -1e9
    dp = np.full(S, NEG); dp[0] = em[0, 0]
    if S > 1: dp[1] = em[0, 1]
    bp = np.zeros((T, S), np.int8)
    for t in range(1, T):
        c0 = dp
        c1 = np.concatenate([[NEG], dp[:-1]])
        c2 = np.where(skip, np.concatenate([[NEG, NEG], dp[:-2]]), NEG)
        st = np.stack([c0, c1, c2])
        k = st.argmax(0)
        dp = st[k, np.arange(S)] + em[t]
        bp[t] = k
    s = S - 1 if S == 1 or dp[S - 1] >= dp[S - 2] else S - 2
    path = np.zeros(T, int)
    for t in range(T - 1, -1, -1):
        path[t] = s; s -= int(bp[t, s])
    spans = [[None, None] for _ in range(L)]
    for t, s in enumerate(path):
        if s % 2 == 1:
            j = s // 2
            if spans[j][0] is None: spans[j][0] = t
            spans[j][1] = t
    return spans, path

def greedy(lp):
    ids = lp.argmax(-1); out_, prev = [], -1
    for i in ids:
        if i != prev and i != BLANK: out_.append(id2tok.get(int(i), ""))
        prev = i
    return re.sub(r"\s+", " ", "".join(out_)).strip()

LP = logprobs(audio)          # hela klippet på en gång: korta fönster ger instabil CTC
WORDS, GAPS = [], []
for ci, sg in enumerate(segs):
    disp = sg["text"].split()
    if not disp: continue
    nxt = segs[ci + 1]["start"] if ci + 1 < len(segs) else len(audio) / sr
    prv = segs[ci - 1]["end"] if ci > 0 else 0.0
    w0 = max(0.0, prv + 0.02, sg["start"] - 0.3)
    w1 = min(len(audio) / sr, nxt - 0.02, sg["end"] + 0.3)
    w0 = min(w0, sg["start"]); w1 = max(w1, sg["end"])
    if WORDS: w0 = max(w0, WORDS[-1]["e"] + 0.01)
    w0 = round(w0 / FR) * FR
    lp = LP[int(round(w0 / FR)):int(round(w1 / FR))]
    tgt, owner = [], []
    for k, w in enumerate(disp):
        sp = spoken(w)
        if not sp: continue
        if tgt: tgt.append(SPACE); owner.append(-1)
        for ch in sp:
            tgt.append(SPACE if ch == " " else tok2id[ch]); owner.append(k)
    if not tgt or len(lp) < len(tgt):
        print(f"! chunk {ci}: kunde inte justeras ({sg['text'][:40]}…)", file=sys.stderr)
        for k, w in enumerate(disp):
            a = sg["start"] + (sg["end"] - sg["start"]) * k / len(disp)
            WORDS.append(dict(w=w, s=round(a, 3), e=round(a + (sg["end"] - sg["start"]) / len(disp), 3), c=0.0, seg=ci))
        continue
    spans, path = viterbi(lp, np.array(tgt))
    tmp = []
    for k, w in enumerate(disp):
        fr = [spans[j] for j in range(len(tgt)) if owner[j] == k and spans[j][0] is not None]
        if not fr: tmp.append(None); continue
        f0, f1 = fr[0][0], fr[-1][1]
        conf = float(np.mean([np.exp(lp[a:b + 1, tgt[j]].max()) for j in range(len(tgt)) if owner[j] == k and spans[j][0] is not None for a, b in [spans[j]]]))
        tmp.append([w0 + f0 * FR + 0.01, w0 + (f1 + 1) * FR + 0.01, conf])
    # ord utan uttalbara tecken (t.ex. "–"): lägg mellan grannarna
    for k in range(len(tmp)):
        if tmp[k] is None:
            a = next((tmp[j][1] for j in range(k - 1, -1, -1) if tmp[j]), sg["start"])
            b = next((tmp[j][0] for j in range(k + 1, len(tmp)) if tmp[j]), sg["end"])
            tmp[k] = [a, max(a, b), 0.0]
    # förfina kanter med energin: förläng start bakåt / slut framåt så länge det låter (max 0.12 / 0.25 s)
    for k, (a, b, c) in enumerate(tmp):
        lo = tmp[k - 1][1] + 0.01 if k else w0
        hi = tmp[k + 1][0] - 0.01 if k + 1 < len(tmp) else w1
        i0, i1 = int(a * 100), int(b * 100)
        pk = env[i0:max(i0 + 1, i1)].max() if i1 > i0 else env[min(i0, len(env) - 1)]
        thr = max(FLOOR + 10, pk - 28)
        while i0 > 0 and env[i0 - 1] > thr and (i0 - 1) / 100 >= max(lo, a - 0.12): i0 -= 1
        while i1 < len(env) - 1 and env[i1] > thr and (i1 + 1) / 100 <= min(hi, b + 0.25): i1 += 1
        tmp[k] = [i0 / 100, max(i1 / 100, i0 / 100 + 0.04), c]
    for w, (a, b, c) in zip(disp, tmp):
        WORDS.append(dict(w=w, s=round(a, 3), e=round(b, 3), c=round(c, 2), seg=ci))
    # tal som inte hör till texten: rutor där CTC hör tecken men justeringen säger blank i > 0.25 s
    nb = 1 - np.exp(lp[:, BLANK])
    voiced = (path % 2 == 0) & (nb > 0.5)
    t = 0
    while t < len(voiced):
        if voiced[t]:
            u = t
            while u < len(voiced) and (voiced[u] or (u + 3 < len(voiced) and voiced[u + 1:u + 4].any())): u += 1
            if (u - t) * FR >= 0.25:
                txt = greedy(lp[max(0, t - 2):u + 2])
                if len(txt.replace(" ", "")) >= 2:
                    GAPS.append(dict(s=round(w0 + t * FR, 2), e=round(w0 + u * FR, 2), ctc=txt, seg=ci))
            t = u
        t += 1
    sg["ctc"] = greedy(lp)

json.dump(WORDS, open(out, "w"), ensure_ascii=False, indent=0)
base = out.rsplit("/", 1)[0] + "/" if "/" in out else ""
json.dump(GAPS, open(base + "gaps.json", "w"), ensure_ascii=False, indent=1)
json.dump(segs, open(segs_p, "w"), ensure_ascii=False, indent=1)     # + "ctc" (ordagrann) per chunk
with open(base + "words.txt", "w") as f:
    for ci, sg in enumerate(segs):
        f.write(f"# chunk {ci}  {sg['start']:.2f}-{sg['end']:.2f}\n#   whisper: {sg['text']}\n#   ordagrant: {sg.get('ctc', '')}\n")
        for w in WORDS:
            if w["seg"] == ci: f.write(f"{w['s']:7.2f} {w['e']:7.2f}  {w['w']}{'  ?' if w['c'] < 0.35 else ''}\n")
        for g in GAPS:
            if g["seg"] == ci: f.write(f"  !! {g['s']:.2f}-{g['e']:.2f} tal utan text (omtagning?): {g['ctc']}\n")
print(f"{len(WORDS)} ord, {sum(w['c'] < 0.35 for w in WORDS)} osäkra, {len(GAPS)} partier tal utan text -> {base}words.txt")
