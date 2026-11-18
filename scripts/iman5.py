"""Iman Gadzhi-style editor v2: hook title, cold-open rewind, text-behind-person,
B&W accent flashes, mid-line punch-ins, B&W drama segments, richer SFX.
usage: python3 iman5.py config.json [--stage all|ass|audio|video] [--preview t1,t2,...]
"""
import json, math, re, subprocess, sys
import numpy as np, soundfile as sf, cv2
from scipy import signal
from PIL import Image, ImageDraw, ImageFont

CFG = json.load(open(sys.argv[1]))
STAGE = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
PREVIEW = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")] if "--preview" in sys.argv else None
FPS = CFG.get("fps", 30)
SRC, OUT, WD = CFG["src"], CFG["out"], CFG["work"].rstrip("/") + "/"
FONTS = "/home/claude/fonts"
SPOKEN = {"5": "fem", "50": "femtio"}

def snap(t): return round(t * FPS) / FPS

# ---------------- timeline ----------------
SEGS = []
o = 0.0
for s in CFG["segs"]:
    a, b = snap(s["a"]), snap(s["b"])
    fr = s["frame"]; fr = CFG["framings"][fr] if isinstance(fr, str) else fr
    SEGS.append(dict(a=a, d=b - a, o=o, z=fr[0], cx=fr[1], cy=fr[2], sp=s.get("sp", [s["a"] + 0.06, s["b"] - 0.07]),
                     caps=s["caps"], cut=s.get("cut", "whip"), yc=s.get("cap_y"), bw=s.get("bw", False),
                     drama=s.get("drama", False), starts=s.get("starts")))
    o += b - a
TOTAL = o
NF = int(round(TOTAL * FPS))
WHIP_CUTS = [S["o"] for S in SEGS[1:] if S["cut"] == "whip"]
REWINDS = [S["o"] for S in SEGS[1:] if S["cut"] == "rewind"]
LEAKS = [0.0] + [SEGS[i]["o"] for i in CFG.get("leaks", [])] + REWINDS
FLASHES = [SEGS[i]["o"] for i in CFG.get("flash", [])]
RISERS = [SEGS[i]["o"] for i in CFG.get("risers", [])]
DRAMAS = [S["o"] for S in SEGS if S["drama"]]

# ---------------- caption groups ----------------
a16, sr16 = sf.read(CFG["wav16k"], dtype="float32")
hop = int(0.01 * sr16)
env = np.array([np.sqrt(np.mean(a16[i*hop:i*hop+2*hop]**2) + 1e-12) for i in range((len(a16)-2*hop)//hop)])
env = 20*np.log10(np.convolve(env, np.ones(5)/5, mode="same"))

def snap_boundary(t, lo, hi):
    i0, i1 = int(max(lo, t-0.15)*100), int(min(hi, t+0.15)*100)
    if i1 <= i0: return t
    j = i0 + int(np.argmin(env[i0:i1]))
    return j/100 if env[j] < env[int(t*100)] - 4 else t

def wweight(w):
    w = re.sub(r"[,.?!*:~]", "", w)
    return len(SPOKEN.get(w, w)) + 1.5

GROUPS = []
for si, S in enumerate(SEGS):
    gs = [g.strip() for g in S["caps"].split("|")]
    ws = [sum(wweight(w) for w in g.split()) for g in gs]
    sp0, sp1 = S["sp"]
    starts = [sp0]; acc = sp0
    for w in ws[:-1]:
        acc += (sp1 - sp0) * w / sum(ws)
        starts.append(snap_boundary(acc, sp0 + 0.1, sp1 - 0.1))
    if S["starts"]: starts = S["starts"]
    for i, g in enumerate(gs):
        st = S["o"] + starts[i] - S["a"]
        p1 = S["o"] + ((starts[i+1] if i + 1 < len(gs) else sp1) - S["a"])
        en = S["o"] + ((starts[i+1] - S["a"]) if i + 1 < len(gs) else S["d"])
        GROUPS.append(dict(st=max(st - 0.03, S["o"]), en=en - 0.02, sp0=st, sp1=p1, raw=g, seg=si, idx=i, n=len(gs)))

ACCENTS = [g["sp0"] for g in GROUPS if "*" in g["raw"]]

# behind-text window
BEHINDS = []
for B in ([CFG["behind"]] if CFG.get("behind") else []) + CFG.get("behinds", []):
    S = SEGS[B["seg"]]
    st = S["o"]
    if B.get("group"):
        st = next(g["st"] for g in GROUPS if g["seg"] == B["seg"] and g["raw"].replace("*", "").replace("~", "") == B["group"])
    en = SEGS[B["until_seg"]]["o"] + SEGS[B["until_seg"]]["d"] if "until_seg" in B else S["o"] + S["d"]
    BEHINDS.append(dict(text=B["text"], st=st, en=en, w=B.get("w", 1000), overlap=B.get("overlap", 0.33)))
BEHIND = BEHINDS[0] if BEHINDS else None
def behind_at(t):
    for b_ in BEHINDS:
        if b_["st"] <= t < b_["en"]: return b_
    return None

# mid-line punch-ins (cut-in without a cut) in long segments
MICRO = []
for si, S in enumerate(SEGS):
    if S["d"] < 2.4 or S["drama"]: continue
    gs = [g for g in GROUPS if g["seg"] == si]
    if len(gs) < 2: continue
    t = gs[len(gs) // 2]["sp0"]
    if any(abs(t - a) < 0.6 for a in ACCENTS):
        t = gs[max(1, len(gs) // 2 - 1)]["sp0"]
        if any(abs(t - a) < 0.6 for a in ACCENTS): continue
    if any(b_["st"] - 0.2 <= t <= b_["en"] for b_ in BEHINDS): continue
    MICRO.append(t)
SNAPS = []   # tiktok-style snap zoom toggles at every caption group
if CFG.get("snap_zoom"):
    MICRO = []
    for g in GROUPS:
        if g["idx"] > 0: SNAPS.append((g["sp0"], g["seg"], g["idx"] % 2))

TITLE = CFG.get("title")
if TITLE:
    TITLE["en"] = SEGS[TITLE["until_seg"]]["o"] if "until_seg" in TITLE else TITLE["end"]

OVERLAYS = []
for ovc in CFG.get("overlays", []):
    S = SEGS[ovc["seg"]]
    g = next(g for g in GROUPS if g["seg"] == ovc["seg"] and g["raw"].replace("*", "").replace("~", "") == ovc["group"])
    t0 = g["st"] + ovc.get("delay", 0.0); t1 = (S["o"] + S["d"]) if ovc.get("to_seg_end") else g["en"]
    t1 = min(max(t1, t0 + ovc.get("min_dur", 0.9)), S["o"] + S["d"])
    if "t1_seg" in ovc: t1 = SEGS[ovc["t1_seg"]]["o"] + SEGS[ovc["t1_seg"]]["d"]
    if "until_group" in ovc:
        t1 = next(g2["en"] for g2 in GROUPS if g2["seg"] == ovc["seg"] and g2["raw"].replace("*", "").replace("~", "") == ovc["until_group"])
    OVERLAYS.append(dict(ovc, t0=t0, t1=t1))

# ---------------- ASS ----------------
def ts(t):
    t = max(0, t); return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"

def build_ass():
    X, Y, FSZ = 540, CFG.get("cap_y", 1150), CFG.get("cap_size", 84)
    LIGHT, BOLD = r"{\fnMontserrat Light\b0}", r"{\fnMontserrat\b1}"
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat,{FSZ},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,60,60,0,1
Style: Shd,Montserrat,{FSZ},&H30000000,&H30000000,&H30000000,&H00000000,0,0,0,0,100,100,0,0,1,8,0,5,60,60,0,1
Style: TT,Montserrat ExtraBold,{CFG.get("tt_size", 94)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,8,4,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    L = []
    def line(layer, st, en, style, tags, body):
        L.append(f"Dialogue: {layer},{ts(st)},{ts(en)},{style},,0,0,0,,{{{tags}}}{body}")
    TTS = CFG.get("cap_style") == "tiktok"
    for g in GROUPS:
        txt = g["raw"].replace("*", "")
        yy = SEGS[g["seg"]]["yc"] or Y
        words = txt.split()
        if TTS:
            W_ = [w_.upper() for w_ in words]
            wt = [wweight(x) for x in words]
            cm = np.concatenate([[0], np.cumsum(wt)]) / sum(wt)
            tk = [g["sp0"] + (g["sp1"] - g["sp0"]) * c for c in cm[:-1]]; tk[0] = g["st"]
            for k in range(len(W_)):
                a0 = tk[k]; a1 = tk[k+1] if k + 1 < len(W_) else g["en"]
                if a1 - a0 < 0.02: continue
                parts = []
                for j, w_ in enumerate(W_):
                    if j == k: parts.append(r"{\c&H4DE1FF&\fscx108\fscy108}" + w_ + r"{\c&HFFFFFF&\fscx100\fscy100}")
                    else: parts.append(w_)
                anim = r"\fscx70\fscy70\t(0,90,\fscx104\fscy104)\t(90,150,\fscx100\fscy100)" if k == 0 else ""
                line(1, a0, a1, "TT", f"\\pos({X},{yy}){anim}", " ".join(parts))
            continue
        w = [wweight(x) for x in words]
        cum = np.concatenate([[0], np.cumsum(w)]) / sum(w)
        tk = [g["sp0"] + (g["sp1"] - g["sp0"]) * c for c in cum[:-1]]
        tk[0] = g["st"]
        for k in range(len(words)):
            a0 = tk[k]; a1 = tk[k+1] if k + 1 < len(words) else g["en"]
            if a1 - a0 < 0.02: continue
            SER = r"{\fnInstrument Serif\i1\b0\fs%d}" % int(FSZ * 1.32)
            toks = []
            for j, w_ in enumerate(words):
                if "~" in w_: toks.append(SER + w_.replace("~", "") + r"{\i0\fs%d}" % FSZ)
                else: toks.append((BOLD if j <= k else LIGHT) + w_)
            body = " ".join(toks)
            anim = r"\fad(80,0)\fscx94\fscy94\t(0,120,\fscx100\fscy100)" if k == 0 else ""
            line(0, a0, a1, "Shd", f"\\pos({X},{yy+4})\\blur10{anim}", body)
            line(1, a0, a1, "Cap", f"\\pos({X},{yy}){anim}", body)
    if TITLE:
        y0 = TITLE.get("y", 300); fs = TITLE.get("size", 70); lh = int(fs * 1.25)
        for i, (wt, txt) in enumerate(TITLE["lines"]):
            if TITLE.get("style") == "tiktok":
                col = r"\c&H4DE1FF&" if wt == "yellow" else ""
                d = 110 * i
                anim = rf"\alpha&HFF&\t({d},{d+60},\alpha&H00&)\fscx60\fscy60\t({d},{d+120},\fscx106\fscy106)\t({d+120},{d+190},\fscx100\fscy100)"
                line(5, 0.0, TITLE["en"], "TT", rf"\pos(540,{y0 + i*lh})\fs{fs}{col}" + anim, txt.upper())
                continue
            fn = {"light": r"{\fnMontserrat Light\b0}", "serif": r"{\fnInstrument Serif\i1\b0\fs%d}" % int(fs * 1.3)}.get(wt, r"{\fnMontserrat ExtraBold\b0}")
            d = 90 * i
            anim = rf"\fad(0,180)\alpha&HFF&\t({d},{d+160},\alpha&H00&)\fscx92\fscy92\t({d},{d+200},\fscx100\fscy100)"
            line(4, 0.0, TITLE["en"], "Shd", rf"\pos(540,{y0 + i*lh + 4})\blur12\fs{fs}" + anim, fn + txt)
            line(5, 0.0, TITLE["en"], "Cap", rf"\pos(540,{y0 + i*lh})\fs{fs}" + anim, fn + txt)
    open(WD + "captions.ass", "w").write(hdr + "\n".join(L) + "\n")

# ---------------- audio ----------------
SR = 48000
rng_a = np.random.default_rng(7)
def dbg(x): return 10 ** (x / 20)

def whoosh(dur=0.42, f0=250, f1=5000, peak=0.62):
    n = int(dur * SR)
    noise = rng_a.standard_normal(n + 2048).astype(np.float32)
    f, t, Z = signal.stft(noise, SR, nperseg=1024, noverlap=768)
    tt = np.clip(t / dur, 0, 1)
    prog = np.where(tt < peak, tt / peak, 1 - (tt - peak) / (1 - peak) * 0.5)
    fc = np.exp(np.log(f0) + (np.log(f1) - np.log(f0)) * prog)
    mask = np.exp(-0.5 * ((np.log(f[:, None] + 1) - np.log(fc[None, :])) / 0.9) ** 2) / np.sqrt(f[:, None] / 300 + 1)
    _, y = signal.istft(Z * mask, SR, nperseg=1024, noverlap=768)
    y = y[:n]; x = np.linspace(0, 1, n)
    y = y * np.where(x < peak, (x / peak) ** 2.2, np.exp(-(x - peak) / (1 - peak) * 4))
    y /= np.max(np.abs(y)) + 1e-9
    pan = np.linspace(-0.6, 0.6, n)
    return np.stack([y * np.sqrt(0.5 * (1 - pan)), y * np.sqrt(0.5 * (1 + pan))], 1)

def boom(dur=1.8, f_end=42):
    n = int(dur * SR); t = np.arange(n) / SR
    freq = f_end + 95 * np.exp(-t / 0.05)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.42)
    body = np.tanh(2.2 * body) / np.tanh(2.2)
    click = rng_a.standard_normal(n) * np.exp(-t / 0.006)
    b, a = signal.butter(2, 2500 / (SR / 2)); click = signal.lfilter(b, a, click)
    y = body + 0.35 * click / (np.max(np.abs(click)) + 1e-9) + 0.25 * np.sin(2 * np.pi * 170 * t) * np.exp(-t / 0.04)
    y /= np.max(np.abs(y)); y[-int(0.3*SR):] *= np.linspace(1, 0, int(0.3*SR)) ** 2
    return np.stack([y, y], 1)

def pop(dur=0.06):
    n = int(dur * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(1500 - 800 * (t / dur)) / SR) * np.exp(-t / 0.014)
    return np.stack([y, y], 1)

def shutter():
    n = int(0.09 * SR); t = np.arange(n) / SR
    nz = rng_a.standard_normal(n)
    b, a = signal.butter(2, [1800 / (SR / 2), 9000 / (SR / 2)], btype="band"); nz = signal.lfilter(b, a, nz)
    env_ = np.exp(-t / 0.008) + 0.6 * np.exp(-np.clip(t - 0.045, 0, None) / 0.01) * (t > 0.045)
    y = nz * env_; y /= np.max(np.abs(y))
    return np.stack([y, y], 1)

def rewind_sfx(dur=0.55):
    # descending reverse whoosh + chirp for a 'tape rewind' feel
    w = whoosh(dur, 6000, 400, 0.85)[::-1].copy()
    n = len(w); t = np.arange(n) / SR
    f = 300 + 2200 * (t / dur) ** 2
    ch = 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 2
    return w + np.stack([ch, ch], 1)

def build_audio():
    inputs, fc, cat = [], [], []
    for i, S in enumerate(SEGS):
        inputs += ["-ss", f"{S['a']:.4f}", "-t", f"{S['d'] + 0.2:.4f}", "-i", SRC]
        d = S["d"]
        join_in = i > 0 and abs(SEGS[i-1]["a"] + SEGS[i-1]["d"] - S["a"]) < 1e-3
        join_out = i + 1 < len(SEGS) and abs(S["a"] + d - SEGS[i+1]["a"]) < 1e-3
        fades = ("" if join_in else "afade=t=in:d=0.012,") + ("" if join_out else f"afade=t=out:st={d-0.018:.4f}:d=0.018,")
        fc.append(f"[{i}:a]atrim=duration={d:.4f},asetpts=PTS-STARTPTS,{fades}apad=whole_dur={d:.4f}[a{i}]")
        cat.append(f"[a{i}]")
    fc.append("".join(cat) + f"concat=n={len(SEGS)}:v=0:a=1,highpass=f=80,"
              + CFG.get("voice_fx", "acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=2") + ",aresample=48000[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fc),
                    "-map", "[out]", "-ac", "2", "-t", f"{TOTAL:.4f}", WD + "voice.wav"], check=True)
    voice, _ = sf.read(WD + "voice.wav", dtype="float32"); N = len(voice)
    sfx = np.zeros((N + SR * 2, 2), np.float32)
    def place(clip, t, g):
        i = int(round(t * SR))
        if i < 0: clip, i = clip[-i:], 0
        sfx[i:i + len(clip)] += clip[:len(sfx) - i] * dbg(g)
    lv = CFG.get("sfx_db", 0)
    if CFG.get("clean"):
        def tick():
            n = int(0.012 * SR); t_ = np.arange(n) / SR
            y = np.sin(2 * np.pi * 2400 * t_) * np.exp(-t_ / 0.003)
            return np.stack([y, y], 1)
        place(whoosh(0.4, 500, 5000, 0.3), 0.0, -27 + lv)
        for r in RISERS: place(whoosh(0.7, 300, 6000, 0.92), r - 0.7 * 0.92, -26 + lv)
        for a in ACCENTS:
            if CFG.get("cutout"):
                place(whoosh(0.25, 900, 7000, 0.6), a - 0.15, -24 + lv); place(pop(0.07), a + 0.01, -21 + lv)
            else:
                place(boom(1.4), a + 0.02, -27 + lv)
        for b_ in BEHINDS:
            place(whoosh(0.32, 500, 6000, 0.7), b_["st"] - 0.32 * 0.7, -25 + lv); place(boom(), b_["st"], -22 + lv)
        for sp_ in SNAPS: place(pop(0.04), sp_[0], -34 + lv)
        for ov_ in OVERLAYS:
            k_ = ov_.get("kind")
            if k_ == "seq":
                place(whoosh(0.35, 400, 5500, 0.6), ov_["t0"] - 0.35 * 0.6, -25 + lv); place(tick(), ov_["t0"] + 0.05, -28 + lv)
                if ov_.get("ticks"):
                    a_, b2 = ov_["ticks"]; tt = ov_["t0"] + a_
                    while tt < ov_["t0"] + b2: place(tick(), tt, -36 + lv); tt += 0.05
            elif k_ == "scatter":
                for i_ in range(len(ov_["imgs"])): place(tick(), ov_["t0"] + i_ * ov_.get("stagger", 0.22) + 0.03, -29 + lv)
                place(whoosh(0.3, 5000, 500, 0.8), ov_["t1"] - 0.3, -25 + lv)
            else:
                place(tick(), ov_["t0"] + 0.03, -27 + lv); place(pop(0.05), ov_["t0"] + 0.05, -33 + lv)
        sfx = sfx[:N]
        sf.write(WD + "mix_raw.wav", voice + sfx, SR, subtype="FLOAT")
        return finish_mix()
    place(whoosh(0.35, 400, 6000, 0.25), 0.0, -19 + lv); place(boom(), 0.0, -14 + lv)
    for c in WHIP_CUTS: place(whoosh(0.42), c - 0.42 * 0.62, -19 + lv)
    for c in REWINDS:
        place(rewind_sfx(), c - 0.45, -15 + lv); place(boom(), c, -15 + lv)
    for r in RISERS: place(whoosh(0.7, 300, 7000, 0.92), r - 0.7 * 0.92, -20 + lv)
    for a in ACCENTS:
        place(boom(), a + 0.02, -17 + lv); place(pop(), a + 0.02, -27 + lv); place(shutter(), a + 0.01, -26 + lv)
    for m in MICRO: place(whoosh(0.22, 800, 6000, 0.7), m - 0.22 * 0.7, -26 + lv)
    for d in DRAMAS: place(boom(2.2, 34), d + 0.02, -15 + lv)
    for b_ in BEHINDS:
        place(whoosh(0.32, 500, 7000, 0.7), b_["st"] - 0.32 * 0.7, -21 + lv); place(boom(), b_["st"], -16 + lv)
    for sp_ in SNAPS: place(pop(0.04), sp_[0], -31 + lv)
    for ov_ in OVERLAYS:
        k_ = ov_.get("kind")
        if k_ in ("card", "phone", "top"):
            place(whoosh(0.35, 400, 6500, 0.6), ov_["t0"] - 0.35 * 0.6, -19 + lv); place(pop(0.08), ov_["t0"] + 0.2, -22 + lv)
        elif k_ == "scatter":
            for i_ in range(len(ov_["imgs"])): place(pop(0.06), ov_["t0"] + i_ * ov_.get("stagger", 0.22) + 0.03, -21 + lv)
            place(whoosh(0.3, 6000, 500, 0.8), ov_["t1"] - 0.3, -19 + lv)
        elif k_ == "seq":
            place(whoosh(0.38, 400, 6500, 0.6), ov_["t0"] - 0.38 * 0.6, -20 + lv); place(pop(0.07), ov_["t0"] + 0.06, -25 + lv)
            if ov_.get("ticks"):
                n_ = int(0.012 * SR); t_ = np.arange(n_) / SR; tk_ = np.sin(2 * np.pi * 2400 * t_) * np.exp(-t_ / 0.003); tk_ = np.stack([tk_, tk_], 1)
                a_, b2 = ov_["ticks"]; tt = ov_["t0"] + a_
                while tt < ov_["t0"] + b2: place(tk_, tt, -31 + lv); tt += 0.055
            for pt in ov_.get("pops", []): place(pop(0.06), ov_["t0"] + pt, -24 + lv)
        else:
            place(pop(0.07), ov_["t0"] + 0.03, -19 + lv)
    sfx = sfx[:N]
    sf.write(WD + "mix_raw.wav", voice + sfx, SR, subtype="FLOAT")
    finish_mix()

def finish_mix():
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", WD + "mix_raw.wav", "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", WD + "mix_raw.wav", "-af", af, "-c:a", "pcm_s16le", WD + "mix.wav"], check=True)

# ---------------- video ----------------
WW, WH, OW, OH = 1440, 2560, 1080, 1920
def _src_transfer():
    try:
        return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                               "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""
_TRC = _src_transfer()
if _TRC in ("arib-std-b67", "smpte2084"):   # iPhone HDR (HLG) or PQ -> tonemap to SDR
    TONEMAP = (f"zscale=tin={_TRC}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100,format=gbrpf32le,"
               "zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
else:                                         # vanlig SDR-video
    TONEMAP = "format=yuv420p,"
GRADE = (TONEMAP
         + CFG.get("grade", "eq=contrast=1.14:brightness=0.02:saturation=0.86:gamma=1.12,"
                   "curves=m='0/0.03 0.22/0.17 0.5/0.5 0.78/0.82 1/0.965',"
                   "colorbalance=rs=-0.03:bs=0.04:rh=0.03:bh=-0.025") + ","
         "scale=in_color_matrix=bt709:in_range=tv:out_range=full,format=rgb24")

def ease_out(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def ease_io(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)

def text_layer(text, width):
    """Render big text to a float alpha map sized to fit `width` px."""
    path = f"{FONTS}/Montserrat-ExtraBold.ttf"
    size = 400
    font = ImageFont.truetype(path, size)
    bb = font.getbbox(text)
    size = int(size * width / (bb[2] - bb[0]))
    font = ImageFont.truetype(path, size)
    bb = font.getbbox(text)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    im = Image.new("L", (w + 80, h + 80), 0)
    ImageDraw.Draw(im).text((40 - bb[0], 40 - bb[1]), text, font=font, fill=255)
    return np.asarray(im, np.float32) / 255

def build_video():
    seg_sess = None
    if BEHINDS or CFG.get("cutout"):
        import onnxruntime as ort
        seg_sess = ort.InferenceSession("/home/claude/models/u2net_human_seg.onnx", providers=["CPUExecutionProvider"])
        for b_ in BEHINDS: b_["txt"] = text_layer(b_["text"], b_["w"])
    MEAN = np.array([0.485, 0.456, 0.406], np.float32); STD = np.array([0.229, 0.224, 0.225], np.float32)
    def person_mask(rgb):
        x = cv2.resize(rgb, (320, 320), interpolation=cv2.INTER_AREA).astype(np.float32)
        x = ((x / max(x.max(), 1e-6) - MEAN) / STD).transpose(2, 0, 1)[None]
        y = seg_sess.run(None, {"input.1": x})[0][0, 0]
        y = (y - y.min()) / (y.max() - y.min() + 1e-6)
        y = cv2.resize(y, (OW, OH), interpolation=cv2.INTER_LINEAR)
        return np.clip((y - 0.25) / 0.5, 0, 1)

    def frame_source():
        """Decode one segment at a time (keeps memory flat)."""
        fs_ = WW * WH * 3
        for S in SEGS:
            n = int(round(S["d"] * FPS))
            z, cx, cy = S["z"], S["cx"], S["cy"]
            # 9:16-utsnitt oavsett om källan är stående eller liggande
            crop = (f"crop=w='trunc(min(iw,ih*9/16)/{z}/2)*2':h='trunc(min(ih,iw*16/9)/{z}/2)*2':"
                    f"x='max(0,min(iw-ow,{cx}*iw-ow/2))':y='max(0,min(ih-oh,{cy}*ih-oh/2))'")
            mir = "hflip," if CFG.get("mirror") else ""
            shp = "unsharp=5:5:0.7:5:5:0.0," if z > 1.1 else ""
            vf = f"fps={FPS},{mir}{crop},scale={WW}:{WH}:flags=lanczos,{shp}setsar=1," + GRADE
            p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{S['a']:.4f}", "-i", SRC, "-vf", vf,
                                  "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                                 stdout=subprocess.PIPE, bufsize=10**8)
            last = None
            for k in range(n):
                b = p.stdout.read(fs_)
                if len(b) < fs_:
                    if last is None: raise RuntimeError("decode failed")
                    b = last
                last = b
                yield b
            p.stdout.close(); p.wait()

    enc = None
    if PREVIEW is None:
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                                "-r", str(FPS), "-i", "pipe:0", "-i", WD + "mix.wav",
                                "-vf", f"ass={WD}captions.ass:fontsdir={FONTS},scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                                "-af", f"afade=t=out:st={TOTAL-0.15:.3f}:d=0.15",
                                "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "16M", "-bufsize", "32M",
                                "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    rng = np.random.default_rng(3)
    shake = rng.standard_normal((NF + 10, 2))
    AX, AY = CFG.get("anchor", [0.5, 0.40])
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    r = np.sqrt(((xx - OW / 2) / (OW / 2)) ** 2 + ((yy - OH * 0.45) / (OH / 2)) ** 2)
    VIG = (1 - 0.30 * np.clip(r - 0.45, 0, None) ** 1.6)[..., None].astype(np.float32)
    TOPGRAD = (1 - 0.55 * np.clip(1 - yy / (OH * 0.32), 0, 1) ** 1.5)[..., None].astype(np.float32)
    def leak(cx, cy, rad, col):
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * rad ** 2)))
        return (g[..., None] * np.array(col, np.float32)[None, None, :] / 255).astype(np.float32)
    LA = leak(OW * 1.05, OH * 0.25, 520, (255, 120, 40)) + leak(OW * 0.9, OH * 0.05, 300, (255, 190, 110))
    LB = leak(-OW * 0.05, OH * 0.55, 560, (255, 105, 45)) + leak(OW * 0.1, OH * 0.35, 260, (255, 200, 140))
    GR = []
    for _ in range(10):
        g = cv2.resize(rng.standard_normal((OH // 2, OW // 2)).astype(np.float32), (OW, OH))
        GR.append((g * 4.2)[..., None])

    def seg_at(t):
        for i in range(len(SEGS) - 1, -1, -1):
            if t >= SEGS[i]["o"] - 1e-6: return i
        return 0

    ALL_CUTS = [S_["o"] for S_ in SEGS[1:]]
    def params_clean(t, fi):
        if CFG.get("no_zoom"): return 1.0, 0.0, 0.0, 0.0, 0.0
        S = SEGS[seg_at(t)]; p = (t - S["o"]) / S["d"]
        zoom = 1 + 0.035 * ease_io(p)
        for ac in ACCENTS + MICRO:
            if S["o"] <= ac < S["o"] + S["d"] and t >= ac:
                zoom *= 1 + 0.06 * ease_io((t - ac) / 0.4)
        cur = None
        for st_, si_, par in SNAPS:
            if S["o"] <= st_ < S["o"] + S["d"] and t >= st_: cur = (st_, par)
        if cur:
            k_ = ease_io((t - cur[0]) / 0.16)
            zoom *= (1 + 0.09 * k_) if cur[1] == 1 else (1.09 - 0.09 * k_)
        for c in ALL_CUTS:
            if c <= t < c + 0.3: zoom *= 1 + 0.025 * (1 - ease_out((t - c) / 0.3))
        if t < 0.45: zoom *= 1 + 0.05 * (1 - ease_out(t / 0.45))
        return zoom, 0.0, 0.0, 0.0, 0.0

    def params(t, fi):
        if CFG.get("clean"): return params_clean(t, fi)
        S = SEGS[seg_at(t)]; p = (t - S["o"]) / S["d"]
        zoom = 1 + (0.16 * ease_io(p) if S["drama"] else 0.045 * ease_io(p))
        blur = ca = sx = sy = 0.0
        for ac in ACCENTS:
            if S["o"] <= ac < S["o"] + S["d"] and t >= ac:
                zoom *= 1 + 0.09 * ease_out((t - ac) / 0.12)
                k = math.exp(-(t - ac) / 0.09)
                sx += 20 * k * shake[fi][0]; sy += 20 * k * shake[fi][1]; ca += 6 * k
        for m in MICRO:
            if S["o"] <= m < S["o"] + S["d"] and t >= m:
                zoom *= 1 + 0.10 * ease_out((t - m) / 0.07)
        cur = None
        for st_, si_, par in SNAPS:
            if S["o"] <= st_ < S["o"] + S["d"] and t >= st_: cur = (st_, par)
        if cur:
            k_ = ease_out((t - cur[0]) / 0.06)
            zoom *= (1 + 0.11 * k_) if cur[1] == 1 else (1.11 - 0.11 * k_)
            if t - cur[0] < 0.12:
                q_ = 1 - (t - cur[0]) / 0.12; sx += 9 * q_ * shake[fi][0]; sy += 9 * q_ * shake[fi][1]
        for c in WHIP_CUTS:
            if c <= t < c + 0.17:
                q = 1 - (t - c) / 0.17
                zoom *= 1 + 0.07 * q * q; blur = max(blur, 0.11 * q * q); ca = max(ca, 9 * q)
                sx += 7 * q * q * shake[fi][0]; sy += 7 * q * q * shake[fi][1]
            if c - 0.07 <= t < c:
                q = (t - (c - 0.07)) / 0.07; blur = max(blur, 0.06 * q); zoom *= 1 + 0.03 * q
        for c in REWINDS:
            if c - 0.2 <= t < c:
                q = (t - (c - 0.2)) / 0.2; blur = max(blur, 0.22 * q * q); zoom *= 1 + 0.12 * q * q; ca = max(ca, 14 * q)
            if c <= t < c + 0.3:
                q = 1 - (t - c) / 0.3; blur = max(blur, 0.2 * q * q); zoom *= 1 + 0.15 * q ** 2; ca = max(ca, 12 * q)
        if t < 0.32:
            q = 1 - t / 0.32; zoom *= 1 + 0.22 * q ** 3; blur = max(blur, 0.16 * q * q); ca = max(ca, 10 * q)
        return zoom, blur, ca, sx, sy

    def view(src, zoom, sx, sy):
        s = zoom * OW / WW
        hw, hh = OW / (2 * s), OH / (2 * s)
        cx = min(max(AX * WW, hw), WW - hw); cy = min(max(AY * WH, hh), WH - hh)
        M = np.float32([[s, 0, OW / 2 - s * cx + sx], [0, s, OH / 2 - s * cy + sy]])
        return cv2.warpAffine(src, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def zblur(img, st, n=7):
        if st <= 0.004: return img
        acc = img.astype(np.float32)
        for k in range(1, n):
            M = cv2.getRotationMatrix2D((OW * 0.5, OH * 0.42), 0, 1 + st * k / (n - 1))
            acc += cv2.warpAffine(img, M, (OW, OH), borderMode=cv2.BORDER_REFLECT)
        return (acc / n).astype(np.uint8)

    def chroma(img, d):
        if d < 0.6: return img
        out = img.copy()
        for ch, sg in ((0, 1), (2, -1)):
            M = cv2.getRotationMatrix2D((OW / 2, OH / 2), 0, 1 + sg * d / 900)
            out[:, :, ch] = cv2.warpAffine(img[:, :, ch], M, (OW, OH), borderMode=cv2.BORDER_REFLECT)
        return out

    def to_bw(f, contrast=1.25):
        g = (f[..., 0] * 0.3 + f[..., 1] * 0.59 + f[..., 2] * 0.11)
        g = np.clip((g - 0.5) * contrast + 0.5, 0, 1)
        return np.repeat(g[..., None], 3, 2)

    st_b = {"mask": None, "ty": None, "cur": None}
    def behind(img, t):
        BEHIND = behind_at(t)
        if BEHIND is None: return img
        if st_b["cur"] is not BEHIND:
            st_b.update(mask=None, ty=None, cur=BEHIND)
        TXT = BEHIND["txt"]
        m = person_mask(img)
        if st_b["mask"] is not None: m = 0.55 * m + 0.45 * st_b["mask"]
        st_b["mask"] = m
        th, tw = TXT.shape
        if t < BEHIND["st"] + 0.35:                  # place text so the head overlaps its lower part; lock after 0.35 s
            cols = m[:, OW // 5: 4 * OW // 5] > 0.5
            rows = np.where(cols.sum(axis=1) > 0.12 * cols.shape[1])[0]   # a real head row, not speckle
            head = rows[0] if len(rows) else int(OH * 0.35)
            ty = float(np.clip(head - th * (1 - BEHIND["overlap"]), 160, OH * 0.55))
            st_b["ty"] = ty if st_b["ty"] is None else 0.6 * st_b["ty"] + 0.4 * ty
        k = ease_out((t - BEHIND["st"]) / 0.18)
        kout = min(1, (BEHIND["en"] - t) / 0.1)
        sc = 1.12 - 0.12 * k
        drift = -18 * (t - BEHIND["st"])
        A = np.zeros((OH, OW), np.float32)
        M = np.float32([[sc, 0, OW / 2 - sc * tw / 2], [0, sc, st_b["ty"] + drift + th / 2 - sc * th / 2]])
        A = cv2.warpAffine(TXT, M, (OW, OH), flags=cv2.INTER_LINEAR)
        A *= 0.96 * k * kout
        shd = cv2.GaussianBlur(A, (0, 0), 14) * 0.45
        bgk = 1 - m
        f = img.astype(np.float32) / 255
        f = f * (1 - 0.22 * k * bgk[..., None])                    # dim background a touch
        f = f * (1 - (shd * bgk)[..., None])
        a = (A * bgk)[..., None]
        f = f * (1 - a) + a
        return (f * 255).astype(np.uint8)

    VIG_C = (1 - 0.20 * np.clip(r - 0.5, 0, None) ** 1.6)[..., None].astype(np.float32)
    def finish_clean(img, t, fi):
        f = img.astype(np.float32) / 255
        if SEGS[seg_at(t)]["bw"]: f = to_bw(f, 1.25)
        if TITLE and t < TITLE["en"] + 0.2:
            k = min(1, t / 0.2, max(0, (TITLE["en"] + 0.2 - t) / 0.25))
            f = f * (1 - (1 - TOPGRAD) * k * 0.8)
        return np.clip(f * VIG_C * 255 + GR[fi % len(GR)] * 0.6, 0, 255).astype(np.uint8)

    CUT_FX = [(a, a + CFG.get("cutout_dur", 0.55)) for a in ACCENTS] if CFG.get("cutout") else []
    BGY = None
    KER = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))
    def cutout(img, t):
        nonlocal BGY
        for a, b in CUT_FX:
            if a <= t < b:
                if BGY is None:
                    rr = np.sqrt(((xx - OW / 2) / OW) ** 2 + ((yy - OH * 0.42) / OH) ** 2)
                    base = np.array([255, 225, 77], np.float32) / 255
                    BGY = base[None, None, :] * (1.06 - 0.35 * np.clip(rr * 1.4, 0, 1))[..., None]
                m = person_mask(img)
                ycut = CFG.get("cutout_ycut", 1110)
                m = m * np.clip((ycut - np.arange(OH, dtype=np.float32)) / 6, 0, 1)[:, None]
                mb = (m > 0.5).astype(np.uint8)
                nl, lab, st, _ = cv2.connectedComponentsWithStats(mb)
                if nl > 1:
                    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
                    keep = (lab == big).astype(np.float32)
                    m = m * cv2.GaussianBlur(cv2.dilate(keep, KER), (0, 0), 2)
                m = cv2.GaussianBlur(m, (0, 0), 1.2)
                mb = (m > 0.5).astype(np.uint8)
                dil = cv2.GaussianBlur(cv2.dilate(mb, KER).astype(np.float32), (0, 0), 1.5)
                outline = np.clip(dil - m, 0, 1)[..., None]
                sh = cv2.GaussianBlur(np.roll(dil, 16, axis=0), (0, 0), 14)[..., None] * 0.35
                f = img.astype(np.float32) / 255
                out = BGY * (1 - sh)
                out = out * (1 - outline) + 1.0 * outline
                mm = m[..., None]
                out = out * (1 - mm) + f * mm
                k = min(1.0, (t - a) / 0.05, (b - t) / 0.07)
                return (np.clip(f * (1 - k) + out * k, 0, 1) * 255).astype(np.uint8)
        return img

    def finish(img, t, fi):
        if CFG.get("clean"): return finish_clean(img, t, fi)
        f = img.astype(np.float32) / 255
        S = SEGS[seg_at(t)]
        bw = S["bw"]
        for ac in ACCENTS:
            if ac <= t < ac + 0.1: bw = True
        for c in REWINDS:
            if c - 0.07 <= t < c + 0.1: bw = True
        if bw: f = to_bw(f, 1.35 if S["bw"] else 1.25)
        for j, lt in enumerate(LEAKS):
            if lt - 0.05 <= t < lt + 0.75 and not S["bw"]:
                e = math.sin(math.pi * min(max((t - lt + 0.05) / 0.8, 0), 1)) ** 1.5
                f = 1 - (1 - f) * (1 - (LA if j % 2 == 0 else LB) * (0.75 * e))
        for ft in FLASHES + REWINDS:
            if ft <= t < ft + 0.13:
                a = 0.6 * (1 - (t - ft) / 0.13) ** 2; f = f * (1 - a) + a
        for ac in ACCENTS:
            if ac <= t < ac + 0.1:
                a = 0.28 * (1 - (t - ac) / 0.1); f = f * (1 - a) + a
        if TITLE and t < TITLE["en"] + 0.2:
            k = min(1, t / 0.15, max(0, (TITLE["en"] + 0.2 - t) / 0.2))
            f = f * (1 - (1 - TOPGRAD) * k)
        return np.clip(f * VIG * 255 + GR[fi % len(GR)], 0, 255).astype(np.uint8)

    def load_rgba(path, size):
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        im = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255
        sc_ = size / im.shape[1]
        return cv2.resize(im, (int(im.shape[1] * sc_), int(im.shape[0] * sc_)), interpolation=cv2.INTER_AREA)
    import glob as _glob
    SEQ = {}
    def seq_frames(d):
        if d not in SEQ: SEQ[d] = sorted(_glob.glob(d.rstrip("/") + "/*.png"))
        return SEQ[d]
    _cache = {}
    def seq_img(d, idx, size=None):
        fr = seq_frames(d); idx = max(0, min(idx, len(fr) - 1)); key = (d, idx, size)
        if key not in _cache:
            im = cv2.cvtColor(cv2.imread(fr[idx], cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255
            if size: im = cv2.resize(im, (size, size), interpolation=cv2.INTER_AREA)
            if len(_cache) > 400: _cache.clear()
            _cache[key] = im
        return _cache[key]
    ICON_DIR = "/home/claude/icons/seq/icon_"
    def glass_chip(f, cx, cy, D, icon_name, dt_icon, alpha, sc):
        r = D * sc / 2
        if r < 4 or alpha <= 0.01: return f
        x0, x1 = max(0, int(cx - r - 34)), min(OW, int(cx + r + 34)); y0, y1 = max(0, int(cy - r - 30)), min(OH, int(cy + r + 46))
        if x1 <= x0 or y1 <= y0: return f
        roi = f[y0:y1, x0:x1]
        yy_, xx_ = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = np.sqrt((xx_ - cx) ** 2 + (yy_ - cy) ** 2)
        m = np.clip(r - d + 0.5, 0, 1)[..., None]
        ring = np.clip(1 - np.abs(d - (r - 1.0)) / 1.1, 0, 1)[..., None]
        sd = np.sqrt((xx_ - cx) ** 2 + (yy_ - cy - 12) ** 2)
        sh = (np.clip((r + 10 - sd) / 22, 0, 1) ** 1.5)[..., None] * 0.30
        blurred = cv2.GaussianBlur(roi, (0, 0), 14)
        glass = blurred * 0.30 + np.array([0.05, 0.05, 0.06], np.float32) * 0.70
        hl = np.clip(1 - (yy_ - (cy - r)) / (r * 1.1), 0, 1)[..., None] * 0.10      # soft top highlight
        out = roi * (1 - sh * alpha * (1 - m))
        out = out * (1 - m * alpha) + (glass + hl) * m * alpha
        out = out * (1 - ring * 0.30 * alpha) + ring * 0.30 * alpha
        isz = max(8, int(D * 0.80 * sc))
        ic = seq_img(ICON_DIR + icon_name, int(dt_icon * FPS * 1.6), isz)
        ix0, iy0 = int(cx - isz / 2) - x0, int(cy - isz / 2) - y0
        h_, w_ = ic.shape[:2]
        if 0 <= ix0 and 0 <= iy0 and ix0 + w_ <= out.shape[1] and iy0 + h_ <= out.shape[0]:
            a_ = ic[..., 3:4] * alpha
            sub = out[iy0:iy0 + h_, ix0:ix0 + w_]
            out[iy0:iy0 + h_, ix0:ix0 + w_] = sub * (1 - a_) + ic[..., :3] * a_
        f[y0:y1, x0:x1] = out
        return f
    OVIMG = {}
    for ov_ in OVERLAYS:
        if ov_.get("kind") in ("seq", "chip") or (ov_.get("kind") == "scatter" and CFG.get("clean")):
            continue
        if ov_.get("kind") == "scatter":
            OVIMG[id(ov_)] = [load_rgba(pth, ov_.get("size", 200)) for pth in ov_["imgs"]]
        else:
            OVIMG[id(ov_)] = load_rgba(ov_["img"], ov_["size"])
    SCAT_POS = [(200, 330), (880, 300), (130, 700), (950, 690), (300, 1080), (820, 1060), (540, 200), (560, 1560), (90, 1000), (990, 980)]

    def ease_back(x, k=1.9):
        x = min(max(x, 0), 1); return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2

    def overlays(img, t):
        live = [o_ for o_ in OVERLAYS if o_["t0"] <= t < o_["t1"]]
        if not live: return img
        f = img.astype(np.float32) / 255
        def put(f, im, cx, cy, sc, ang, alpha):
            h, w = im.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
            M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
            L = cv2.warpAffine(im, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            a = L[..., 3:4] * alpha
            sh = cv2.GaussianBlur(np.roll(L[..., 3], 14, axis=0), (0, 0), 18)[..., None] * 0.45 * alpha
            f = f * (1 - sh)
            return f * (1 - a) + L[..., :3] * a
        for o_ in live:
            dt, rem = t - o_["t0"], o_["t1"] - t
            if o_.get("kind") == "seq":
                im = seq_img(o_["dir"], int(dt * FPS))
                k = ease_out(dt / 0.35); ko = min(1, rem / 0.22)
                if o_.get("from") == "right":
                    cx = o_["x"] + 90 * (1 - k) + 40 * (1 - ko); cy = o_["y"]
                else:
                    cx = o_["x"]; cy = o_["y"] + 34 * (1 - k) + 18 * (1 - ko)
                h_, w_ = im.shape[:2]
                M = np.float32([[1, 0, cx - w_ / 2], [0, 1, cy - h_ / 2]])
                L = cv2.warpAffine(im, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                a = L[..., 3:4] * min(1, dt / 0.25) * ko
                f = f * (1 - a) + L[..., :3] * a
                continue
            if o_.get("kind") == "chip":
                k = ease_out(dt / 0.3); ko = min(1, rem / 0.18)
                f = glass_chip(f, o_["x"], o_["y"] - 6 * math.sin(2 * math.pi * 0.5 * dt), o_.get("d", 170), o_["icon"], dt - 0.08,
                               min(1, dt / 0.2) * ko, 0.86 + 0.14 * k)
                continue
            if o_.get("kind") == "scatter" and CFG.get("clean"):
                gap = o_.get("stagger", 0.22); fly = max(0.0, 1 - rem / 0.35)
                for i_, nm in enumerate(o_["imgs"]):
                    d_ = dt - i_ * gap
                    if d_ <= 0: continue
                    px, py = SCAT_POS[i_ % len(SCAT_POS)]
                    px += 8 * math.sin(2 * math.pi * (0.35 + 0.05 * i_) * dt + i_)
                    py += 8 * math.cos(2 * math.pi * (0.3 + 0.04 * i_) * dt + 2 * i_)
                    e_ = ease_io(fly)
                    px = px + (540 - px) * e_; py = py + (1300 - py) * e_
                    f = glass_chip(f, px, py, o_.get("d", 150), nm, d_ - 0.05, min(1, d_ / 0.2) * (1 - e_ ** 3),
                                   (0.86 + 0.14 * ease_out(d_ / 0.3)) * (1 - 0.6 * e_))
                continue
            if o_.get("kind") == "scatter":
                ims = OVIMG[id(o_)]; n = len(ims); gap = o_.get("stagger", 0.22)
                fly = max(0.0, 1 - rem / 0.3)                     # last 0.3 s: everything collapses to centre
                for i_, im in enumerate(ims):
                    d_ = dt - i_ * gap
                    if d_ <= 0: continue
                    px, py = SCAT_POS[i_ % len(SCAT_POS)]
                    px += 14 * math.sin(2 * math.pi * (0.7 + 0.13 * i_) * dt + i_)
                    py += 14 * math.cos(2 * math.pi * (0.6 + 0.11 * i_) * dt + 2 * i_)
                    e_ = ease_in = fly ** 2
                    px = px + (540 - px) * e_; py = py + (900 - py) * e_
                    sc = ease_back(d_ / 0.24) * (1 - 0.85 * e_)
                    ang = 12 * math.sin(2 * math.pi * 1.3 * dt + i_) * (1 - e_)
                    if sc > 0.02: f = put(f, im, px, py, sc, ang, min(1, d_ / 0.05))
                continue
            im = OVIMG[id(o_)]; h, w = im.shape[:2]
            if o_.get("kind") == "phone":
                k = ease_out(dt / 0.32); ko = min(1, rem / 0.18)
                cx = o_["x"] + 520 * (1 - k) + 420 * (1 - ko); cy = o_["y"] + 30 * (1 - k)
                f = put(f, im, cx, cy, 1.0, -4 * k * ko + 6 * (1 - k), min(1, dt / 0.08) * ko)
                continue
            if o_.get("kind") == "top":                           # notification drops in from the top
                k = ease_back(dt / 0.35, 1.2); ko = min(1, rem / 0.18)
                f = put(f, im, o_["x"], o_["y"] - 380 * (1 - min(1, k)) - 300 * (1 - ko), 1.0, 0, min(1, dt / 0.08) * ko)
                continue
            if o_.get("kind") == "card":
                k = ease_out(dt / 0.28); ko = min(1, rem / 0.15)
                sc = 0.94 + 0.06 * k; ang = 0.0
                cx, cy = o_["x"], o_["y"] + 130 * (1 - k) + 60 * (1 - ko)
                alpha = k * ko
            else:
                sc = ease_back(dt / 0.26) * (1 if rem > 0.12 else max(0, rem / 0.12))
                ang = 9 * math.sin(2 * math.pi * 2.0 * dt) * math.exp(-dt / 0.5)
                cx, cy = o_["x"], o_["y"] - 10 * math.sin(2 * math.pi * 0.9 * dt)
                alpha = min(1, dt / 0.06)
            if sc <= 0.02 or alpha <= 0.01: continue
            M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
            M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
            L = cv2.warpAffine(im, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            a = L[..., 3:4] * alpha
            sh = cv2.GaussianBlur(np.roll(L[..., 3], 14, axis=0), (0, 0), 18)[..., None] * 0.45 * alpha
            f = f * (1 - sh)
            f = f * (1 - a) + L[..., :3] * a
        return (np.clip(f, 0, 1) * 255).astype(np.uint8)

    fs = WW * WH * 3
    want = None if PREVIEW is None else {int(round(x * FPS)) for x in PREVIEW}
    last = max(want) if want else NF
    img = None
    for fi, buf in enumerate(frame_source()):
        if fi >= NF: break
        t = fi / FPS
        in_b = behind_at(t) is not None
        if want is not None and fi not in want and not in_b:
            if fi > last: break
            continue
        src = np.frombuffer(buf, np.uint8).reshape(WH, WW, 3)
        zoom, blur, ca, sx, sy = params(t, fi)
        img = chroma(zblur(view(src, zoom, sx, sy), blur), ca)
        img = behind(img, t)
        img = cutout(img, t)
        img = finish(img, t, fi)
        img = overlays(img, t)
        if enc: enc.stdin.write(img.tobytes())
        elif fi in want: cv2.imwrite(f"{WD}prev_{t:05.2f}.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        if fi % 90 == 0: print("frame", fi, "/", NF, flush=True)
    if enc: enc.stdin.close(); enc.wait()

print(f"total {TOTAL:.2f}s, {len(SEGS)} segs | whip {[round(c,2) for c in WHIP_CUTS]} | rewind {[round(c,2) for c in REWINDS]}")
print(f"overlays {[(round(o_['t0'],2), round(o_['t1'],2), (o_.get('img') or o_.get('dir') or o_.get('icon') or 'scatter').rstrip('/').split('/')[-1]) for o_ in OVERLAYS]}")
print(f"accents {[round(a,2) for a in ACCENTS]} | micro {[round(m,2) for m in MICRO]} | behind {BEHIND and (round(BEHIND['st'],2), round(BEHIND['en'],2))} | title {TITLE and TITLE['en']}")
if STAGE in ("all", "ass"): build_ass()
if STAGE in ("all", "audio"): build_audio()
if STAGE in ("all", "video"): build_video()
print("done")
