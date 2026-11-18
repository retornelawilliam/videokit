"""Kontroll före leverans – allt som WORKFLOW kräver, med OK/FEL per punkt.

usage: python3 check.py JOB/cfg.json [video.mp4]      (video = cfg["out"] om den utelämnas)
       python3 check.py JOB/cfg.json --plan           (bara layout, före rendering – kräver --stage ass)

Kollar: 1080×1920, 30 fps, längd, −14 LUFS (±1), true peak ≤ −1 dBTP,
        säkra zoner (översta 150 / nedersta 250 px) för undertexter, titel och kort,
        krockar kort↔undertext, kort↔kort, kort↔titel, kort över ansiktet,
        och skriver ut all text i ordning för korrekturläsning.
"""
import glob, json, os, re, subprocess, sys
from PIL import Image, ImageFont

cfg_p = sys.argv[1]; CFG = json.load(open(cfg_p))
WD = CFG["work"].rstrip("/") + "/"
PLAN = "--plan" in sys.argv
V = next((a for a in sys.argv[2:] if a.endswith((".mp4", ".mov"))), CFG["out"])
TL = json.load(open(WD + "timeline.json"))
FONTS = "/home/claude/fonts"
TOP, BOT, W, H = 150, 1920 - 250, 1080, 1920
res = []
def ok(c, txt, warn=False): res.append(("OK " if c else ("VARN" if warn else "FEL")) + "  " + txt)

# ---------- teknik ----------
if not PLAN:
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
                                    "-of", "json", V], capture_output=True, text=True).stdout)
    vs = next(s for s in pr["streams"] if s["codec_type"] == "video")
    has_a = any(s["codec_type"] == "audio" for s in pr["streams"])
    dur = float(pr["format"]["duration"])
    ok(vs["width"] == 1080 and vs["height"] == 1920, f"upplösning {vs['width']}×{vs['height']}")
    ok(vs["r_frame_rate"] in ("30/1", "30000/1000"), f"bildfrekvens {vs['r_frame_rate']}")
    ok(abs(dur - TL["total"]) < 0.25, f"längd {dur:.2f} s (tidslinje {TL['total']:.2f} s)")
    ok(has_a, "ljudspår finns")
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", V, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    ok(abs(I + 14) <= 1.0, f"ljudnivå {I:.1f} LUFS (mål −14)")
    ok(TP <= -0.9, f"true peak {TP:.1f} dBTP (max −1)")

# ---------- rektanglar ----------
fb = ImageFont.truetype(f"{FONTS}/Montserrat-Bold.ttf", TL["cap_size"])
def cap_rect(txt, y, size=None):
    f = fb if not size else ImageFont.truetype(f"{FONTS}/Montserrat-Bold.ttf", size)
    t = re.sub(r"[*~]", "", txt)
    if TL.get("tiktok"): t = t.upper()
    w = f.getlength(t); h = (size or TL["cap_size"]) * 1.15
    return (540 - w / 2, y - h / 2, 540 + w / 2, y + h / 2)

def ov_rect(o):
    k = o.get("kind")
    if k == "seq":
        fr = sorted(glob.glob(o["dir"].rstrip("/") + "/*.png"))
        w, h = Image.open(fr[-1]).size if fr else (800, 400)
    elif k == "chip":
        w = h = o.get("d", 170)
    elif k == "scatter":
        return None
    else:
        p = o.get("img")
        if not p or not os.path.exists(p): return None
        iw, ih = Image.open(p).size; w = o.get("size", iw); h = ih * w / iw
    # kortet glider in ~34 px nedifrån: räkna med det
    return (o["x"] - w / 2, o["y"] - h / 2, o["x"] + w / 2, o["y"] + h / 2 + 20)

def inter(a, b, pad=8):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])
def name(o): return (o.get("img") or o.get("dir") or o.get("icon") or "scatter").rstrip("/").split("/")[-1]

G = [dict(g, r=cap_rect(g["raw"], g["y"])) for g in TL["groups"]]
O = [dict(o, r=ov_rect(o)) for o in TL["overlays"]]
T = TL.get("title")
TR = []
if T:
    fs = T.get("size", 70); lh = int(fs * 1.25)
    for i, (_, txt) in enumerate(T["lines"]):
        TR.append(cap_rect(txt, T.get("y", 300) + i * lh, fs))

# säkra zoner
bad = [g for g in G if g["r"][1] < TOP or g["r"][3] > BOT]
ok(not bad, "undertexter inom säkra zoner" + ("" if not bad else ": " + ", ".join(f"'{g['raw']}' y={g['y']}" for g in bad[:4])))
wide = [g for g in G if g["r"][2] - g["r"][0] > 980]
ok(not wide, "undertexter ryms i bredd" + ("" if not wide else ": " + ", ".join(f"'{g['raw']}'" for g in wide[:4])))
ok(all(r[1] >= TOP and r[3] <= BOT for r in TR), "titeln inom säkra zoner")
bo = [o for o in O if o["r"] and (o["r"][1] < TOP or o["r"][3] > BOT or o["r"][0] < 0 or o["r"][2] > W)]
ok(not bo, "kort inom säkra zoner" + ("" if not bo else ": " + ", ".join(f"{name(o)} {tuple(int(v) for v in o['r'])}" for o in bo)))

# krockar
cc = []
for o in O:
    if not o["r"]: continue
    for g in G:
        if g["st"] < o["t1"] and o["t0"] < g["en"] and inter(o["r"], g["r"]): cc.append(f"{name(o)} ↔ '{g['raw']}' ({max(o['t0'], g['st']):.1f} s)")
ok(not cc, "kort krockar inte med undertexter" + ("" if not cc else ": " + "; ".join(sorted(set(cc))[:5])))
oo = [f"{name(a)} ↔ {name(b)}" for i, a in enumerate(O) for b in O[i + 1:]
      if a["r"] and b["r"] and a["t0"] < b["t1"] and b["t0"] < a["t1"] and inter(a["r"], b["r"], 0)]
ok(not oo, "kort krockar inte med varandra" + ("" if not oo else ": " + "; ".join(oo)))
if T:
    ot = [name(o) for o in O if o["r"] and o["t0"] < T["en"] and any(inter(o["r"], r) for r in TR)]
    ok(not ot, "kort krockar inte med titeln" + ("" if not ot else ": " + ", ".join(ot)))
    gt = [g["raw"] for g in G if g["st"] < T["en"] and any(inter(g["r"], r) for r in TR)]
    ok(not gt, "undertext krockar inte med titeln" + ("" if not gt else ": " + ", ".join(gt)))
# ansiktet: huvudet hamnar kring ankaret (x 540, y ≈ anchor*1920)
ay = CFG.get("anchor", [0.5, 0.34])[1] * H
face = (540 - 170, ay - 240, 540 + 170, ay + 220)
fo = [name(o) for o in O if o["r"] and inter(o["r"], face, 0) and o.get("kind") != "chip"]
ok(not fo, "ansiktet syns (inga kort över huvudet)" + ("" if not fo else ": " + ", ".join(fo)), warn=True)
if TL.get("behinds"):
    ok(all(0.3 <= b.get("overlap", 0.33) <= 0.45 for b in TL["behinds"]), "bakom-text: overlap 0,3–0,45", warn=True)

# text för korrektur
txt = []
for si, S in enumerate(CFG["segs"]):
    txt.append(re.sub(r"\s*\|\s*", " ", S["caps"]).replace("*", "").replace("~", ""))
print("\n".join(res))
print("\nTEXT I VIDEON (korrläs namn, märken, adresser):")
if T: print("  titel: " + " / ".join(l[1] for l in T["lines"]))
print("  " + " ".join(txt))
print("\n" + ("ALLT OK" if not any(r.startswith("FEL") for r in res) else f"{sum(r.startswith('FEL') for r in res)} FEL att rätta"))
