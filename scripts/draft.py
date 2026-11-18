"""Första utkast av config + plan, direkt från ordtiderna (align.py).

usage: python3 draft.py JOB [--pause 0.25] [--lang sv] [--drop 1.2-3.5,26.2-27] [--force]

Gör automatiskt:
  - rättstavar kända namn (rattning.json)
  - tar bort utfyllnad (eh, öh, ehm …) och omtagningar (behåller sista tagningen)
  - klipper all tystnad längre än --pause, tajt (0,04 s före / 0,05 s efter ord)
  - delar upp i segment (Z1/Z2 växelvis, whip vid meningsslut, hard mitt i mening)
  - undertextgrupper om 2–4 ord med exakta ordtider ("wt") → motorn tänder orden när de sägs
  - hittar ansiktet i stills och räknar ut Z1/Z2-utsnitten
  - hook-titel (utkast), ljusläckor och riser mot slutet
Skriver JOB/cfg.json (eller cfg_draft.json om cfg.json redan finns, utan --force) och JOB/plan.txt.
Kvar för Claude: hook-titel, ~serif- och *accent*-ord, "bakom"-ordet, grafik (overlays), rättstavning.
"""
import glob, json, os, re, sys
import numpy as np

J = sys.argv[1].rstrip("/")
arg = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
PAUSE = arg("--pause", 0.25)
LANG = arg("--lang", "sv")
S = "/home/claude/scripts"
NAME = os.path.basename(glob.glob(f"{J}/*_16k.wav")[0])[:-8]
SRC = next(p for p in glob.glob(f"{J}/{NAME}.*") if not p.endswith((".wav", ".json", ".txt", ".jpg")))
W = json.load(open(f"{J}/words.json"))
GAPS = json.load(open(f"{J}/gaps.json")) if os.path.exists(f"{J}/gaps.json") else []

# ---------- rättstavning ----------
def norm(w): return re.sub(r"[^\w@.+%&-]", "", w.lower()).strip(".-")
rules = [(alt.split(" "), rep) for k, rep in json.load(open(f"{S}/rattning.json")).items() if not k.startswith("_") for alt in k.split("|")]
i, out_ = 0, []
while i < len(W):
    hit = None
    for toks, rep in sorted(rules, key=lambda r: -len(r[0])):
        n = len(toks)
        if i + n <= len(W) and all(re.fullmatch(t, norm(W[i + k]["w"]), re.I) for k, t in enumerate(toks)):
            hit = (n, rep); break
    if hit:
        n, rep = hit
        tail = re.search(r"[,.?!:]+$", W[i + n - 1]["w"])
        out_.append(dict(W[i], w=rep + (tail.group(0) if tail else ""), e=W[i + n - 1]["e"], fixed=" ".join(x["w"] for x in W[i:i + n])))
        i += n
    else:
        out_.append(dict(W[i])); i += 1
W = out_
for k, w in enumerate(W): w["i"] = k; w["drop"] = None

# ---------- utfyllnad och omtagningar ----------
FILL = {"eh", "ehm", "öh", "öhm", "äh", "ähm", "eeh", "uh", "um", "uhm", "hmm", "mm", "mmm", "erm"}
for w in W:
    if norm(w["w"]) in FILL: w["drop"] = "utfyllnad"
# --drop 1.2-3.5,26.2-27.0 : ta bort ord som börjar inom intervallen (falska starter, sidospår)
DROPS = [tuple(map(float, r.split("-"))) for r in arg("--drop", "").split(",") if "-" in r]
for w in W:
    if any(a_ <= w["s"] <= b_ for a_, b_ in DROPS): w["drop"] = "bortvalt"

def pause_before(j): return W[j]["s"] - W[j - 1]["e"] if j > 0 else 9
def restart_signal(j):
    return (pause_before(j) >= 0.18 or W[j]["seg"] != W[j - 1]["seg"] or W[j - 1]["w"].endswith(("-", "–", "…"))
            or W[j - 1]["c"] < 0.3 or any(W[j - 1]["e"] - 0.05 <= g["s"] <= W[j]["s"] + 0.05 for g in GAPS))
def same(a, b): return a == b or (len(a) >= 2 and b.startswith(a))      # "chat–" ~ "chatgpt"

RETAKES = []
def retake_len(i, j):
    """Är W[i:j] en tidigare tagning av det som börjar på j? Kräver omstart + att orden upprepas."""
    m = j - i
    if j + m - 1 >= len(W) + 1 or not restart_signal(j): return False
    a = [norm(W[i + k]["w"]) for k in range(m)]
    b = [norm(W[j + k]["w"]) if j + k < len(W) else "" for k in range(m)]
    if a[0] != b[0]: return False
    if m >= 2 and not same(a[1], b[1]): return False
    hits = sum(same(x, y) for x, y in zip(a, b))
    return hits >= max(m - 1, int(np.ceil(0.7 * m))) if m >= 3 else hits == m

i = 0
while i < len(W) - 1:
    found = None
    if W[i]["drop"] is None and (i == 0 or pause_before(i) >= 0.15 or W[i - 1]["w"][-1] in ",.?!" or W[i]["seg"] != W[i - 1]["seg"]):
        for j in range(i + 1, min(len(W), i + 14)):
            if W[j]["s"] - W[i]["s"] > 9: break
            if retake_len(i, j): found = j          # längsta matchning vinner: sista tagningen behålls
    if found:
        for k in range(i, found): W[k]["drop"] = W[k]["drop"] or "omtagning"
        RETAKES.append((W[i]["s"], W[found]["s"] - 0.01, " ".join(x["w"] for x in W[i:found])))
        i = found
    else:
        i += 1

KEEP = [w for w in W if not w["drop"]]
assert KEEP, "inga ord kvar"

# ---------- segment ----------
segs, cur = [], [KEEP[0]]
for p, w in zip(KEEP, KEEP[1:]):
    dropped_between = w["i"] != p["i"] + 1
    if w["s"] - p["e"] > PAUSE or dropped_between: segs.append(cur); cur = [w]
    else: cur.append(w)
segs.append(cur)

def bounds(ws):
    f, l = ws[0], ws[-1]
    prev_e = W[f["i"] - 1]["e"] if f["i"] > 0 else 0.0
    next_s = W[l["i"] + 1]["s"] if l["i"] + 1 < len(W) else l["e"] + 0.5
    a = max(f["s"] - 0.04, prev_e + 0.005, 0.0)
    b = min(l["e"] + 0.05, next_s - 0.005)
    return round(a, 3), round(b, 3)

# slå ihop för korta segment (< 0,35 s) med närmaste granne om pausen är kort och inget är bortklippt emellan
def gap(l, r): return segs[r][0]["s"] - segs[l][-1]["e"] if segs[r][0]["i"] == segs[l][-1]["i"] + 1 else 9
k = 0
while k < len(segs):
    a, b = bounds(segs[k])
    if b - a < 0.35 and len(segs) > 1:
        gl = gap(k - 1, k) if k > 0 else 9
        gr = gap(k, k + 1) if k + 1 < len(segs) else 9
        if min(gl, gr) < 0.8:
            if gl <= gr: segs[k - 1] += segs.pop(k); k -= 1
            else: segs[k] += segs.pop(k + 1)
            continue
    k += 1

def cap_word(w):
    t = w["w"].lower()
    t = re.sub(r"\.+$", "", t)          # punkt i slutet bort, punkt i adresser (retornela.com) blir kvar
    return t.replace('"', "")

def groups(ws):
    """Fraser (bryts vid skiljetecken och pauser > 0,15 s) delas i jämna grupper om 2–4 ord (~8–18 tecken)."""
    phrases, ph = [], []
    for k, w in enumerate(ws):
        ph.append(w)
        nxt = ws[k + 1] if k + 1 < len(ws) else None
        if nxt is None or w["w"][-1] in ",.?!:" or nxt["s"] - w["e"] > 0.15: phrases.append(ph); ph = []
    def cost(g):
        ch = sum(len(cap_word(x)) for x in g) + len(g) - 1
        c = (ch - 13) ** 2 / 10
        if len(g) == 1 and len(cap_word(g[0])) < 7: c += 25
        if ch > 20: c += (ch - 20) * 6
        return c
    out_ = []
    for ph in phrases:
        n = len(ph); best = [0.0] + [1e9] * n; prv = [0] * (n + 1)
        for e in range(1, n + 1):
            for s_ in range(max(0, e - 4), e):
                c = best[s_] + cost(ph[s_:e])
                if c < best[e]: best[e], prv[e] = c, s_
        cut, e = [], n
        while e > 0: cut.append((prv[e], e)); e = prv[e]
        out_ += [ph[a_:b_] for a_, b_ in reversed(cut)]
    # ensam kort grupp efter en kort fras: slå ihop med föregående om det blir högst 4 ord
    k = 1
    while k < len(out_):
        if len(out_[k]) == 1 and len(cap_word(out_[k][0])) < 7 and len(out_[k - 1]) <= 3 and out_[k][0]["s"] - out_[k - 1][-1]["e"] < 0.4:
            out_[k - 1] += out_.pop(k)
        else: k += 1
    return out_

OUT_SEGS, PLAN_SEGS, o = [], [], 0.0
for k, ws in enumerate(segs):
    a, b = bounds(ws)
    gs = groups(ws)
    caps = " | ".join(" ".join(cap_word(w) for w in g) for g in gs)
    prev_end_sentence = k > 0 and segs[k - 1][-1]["w"][-1] in ".?!"
    retake_before = k > 0 and ws[0]["i"] != segs[k - 1][-1]["i"] + 1
    seg = {"a": a, "b": b, "frame": "Z1" if k % 2 == 0 else "Z2"}
    if k > 0 and not (prev_end_sentence or retake_before or ws[0]["s"] - segs[k - 1][-1]["e"] > 0.6):
        seg["cut"] = "hard"
    seg.update({"caps": caps, "sp": [round(ws[0]["s"], 3), round(ws[-1]["e"], 3)], "wt": [round(w["s"], 3) for w in ws]})
    OUT_SEGS.append(seg)
    PLAN_SEGS.append((k, a, b, o, seg["frame"], seg.get("cut", "whip" if k else "-"), caps))
    o += b - a
TOTAL = o

# ---------- ansikte -> utsnitt ----------
import cv2
hx, hy, face_ok = 0.5, 0.40, False
casc = cv2.CascadeClassifier("/home/claude/videokit/models/haarcascade_frontalface_default.xml")
pts = []
for p in sorted(glob.glob(f"{J}/w/still_*.jpg")):
    im = cv2.imread(p); g = cv2.cvtColor(cv2.resize(im, None, fx=2, fy=2), cv2.COLOR_BGR2GRAY)
    f = casc.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
    if len(f):
        x, y, w_, h_ = max(f, key=lambda r: r[2] * r[3])
        pts.append(((x + w_ / 2) / g.shape[1], (y + h_ / 2) / g.shape[0]))
if pts:
    hx, hy = float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts])); face_ok = True
FR = {"Z1": [1.3, round(hx, 3), round(min(0.8, hy + 0.154), 3)], "Z2": [1.6, round(hx, 3), round(min(0.8, hy + 0.125), 3)]}

# ---------- titel, effekter ----------
first = [cap_word(w) for w in segs[0]][:7]
cut1 = max(1, min(len(first) - 1, (len(first) + 1) // 2)) if len(first) > 1 else 1
title = {"lines": [["light", " ".join(first[:cut1])], ["serif", " ".join(first[cut1:]) or "…"]], "y": 290, "size": 86,
         "end": round(min(2.9, max(1.8, (OUT_SEGS[0]["b"] - OUT_SEGS[0]["a"]) - 0.3)), 2)}
n = len(OUT_SEGS)
ex = json.load(open("/home/claude/videokit/configs/exempel/retornela_ai_IMG_7330.json"))
cfg = {"_utkast": "draft.py: sätt hook-titel, ~serif (2–4), *accent* (2–3), behinds, overlays. 'wt' = ordens starttider (källtid), rör inte.",
       "src": SRC, "out": f"{J}/{NAME}_iman.mp4", "work": f"{J}/w", "wav16k": f"{J}/{NAME}_16k.wav",
       "mirror": True, "framings": FR, "cap_y": 1250, "cap_size": 84, "anchor": [0.5, 0.34], "title": title,
       "behinds": [], "leaks": sorted({max(0, n - 2), n - 1}) if n > 1 else [], "flash": [], "risers": [n - 1] if n > 2 else [],
       "overlays": [], "segs": OUT_SEGS, "voice_fx": ex["voice_fx"]}
dst = f"{J}/cfg.json" if (not os.path.exists(f"{J}/cfg.json") or "--force" in sys.argv) else f"{J}/cfg_draft.json"
with open(dst, "w") as f:
    f.write("{\n" + ",\n".join(
        f'  "{k}": ' + (("[\n" + ",\n".join("    " + json.dumps(s_, ensure_ascii=False) for s_ in v) + "\n  ]") if k == "segs" else json.dumps(v, ensure_ascii=False))
        for k, v in cfg.items()) + "\n}\n")

# ---------- plan ----------
src_len = W[-1]["e"] - W[0]["s"]
pauses = [(p["e"], w["s"]) for p, w in zip(KEEP, KEEP[1:]) if w["s"] - p["e"] > PAUSE and w["i"] == p["i"] + 1]
L = [f"PLAN {NAME}   {src_len:.1f} s tal -> {TOTAL:.1f} s klippt ({len(OUT_SEGS)} segment)", "",
     "TEXT", "  " + " ".join(w["w"] for w in KEEP), "", "KLIPPS BORT"]
L += [f"  omtagning {a:.2f}-{b:.2f}: \"{t}\"" for a, b, t in RETAKES]
L += [f"  utfyllnad {w['s']:.2f}: \"{w['w']}\"" for w in W if w["drop"] == "utfyllnad"]
L += [f"  bortvalt {a_:.2f}-{b_:.2f}: \"{' '.join(w['w'] for w in W if a_ <= w['s'] <= b_)}\"" for a_, b_ in DROPS]
L += [f"  tal utan text {g['s']:.2f}-{g['e']:.2f}: \"{g['ctc']}\" (Whisper skrev inte ut det – kolla att det ska bort)" for g in GAPS]
L += [f"  pauser > {PAUSE:.2f} s: {len(pauses)} st, totalt {sum(b - a for a, b in pauses):.1f} s"]
L += ["", "SEGMENT (källa a–b | start i klippet | utsnitt | övergång | undertexter)"]
L += [f"  {k:2d}  {a:6.2f}-{b:6.2f} | {o_:5.2f} | {fr} | {c:5s} | {caps}" for k, a, b, o_, fr, c, caps in PLAN_SEGS]
fixed = [w for w in W if w.get("fixed")]
unsure = [w for w in KEEP if w["c"] < 0.35]
flags = ([f"  rättat: \"{w['fixed']}\" -> {w['w']}" for w in fixed]
         + [f"  osäkert ord {w['s']:.2f}: \"{w['w']}\"" for w in unsure]
         + [f"  siffra/adress att dubbelkolla: \"{w['w']}\"" for w in KEEP if re.search(r"\d|@|\.\w", w["w"])]
         + ([] if face_ok else ["  hittade inget ansikte i stills – sätt framings för hand"]))
L += ["", "FLAGGOR"] + (flags or ["  inga"])
L += ["", f"UTSNITT  huvud x={hx:.2f} y={hy:.2f}  Z1={FR['Z1']}  Z2={FR['Z2']}",
      "KVAR ATT GÖRA  hook-titel (3 förslag), ~serif 2–4, *accent* 2–3, bakom-ord, grafik, rättstavning"]
open(f"{J}/plan.txt", "w").write("\n".join(L) + "\n")
print("\n".join(L)); print(f"\n-> {dst}")
