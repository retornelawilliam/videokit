"""Gör en storyboard/kontaktark så William ser vad som händer.

Två lägen:
  python3 storyboard.py frames <mapp-med-prev_*.jpg> <ut.jpg> [etiketter,komma,separerade]
  python3 storyboard.py video  <video.mp4> <ut.jpg> t1,t2,t3,...   (bildrutor ur färdig video, med text)
"""
import glob, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

FONT = "/home/claude/fonts/Montserrat-Bold.ttf"
TW, TH, COLS = 300, 533, 5

def tile(paths, labels, out):
    rows = (len(paths) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW + (COLS + 1) * 12, rows * (TH + 44) + 12), (18, 16, 14))
    f = ImageFont.truetype(FONT, 22)
    for i, (p, lab) in enumerate(zip(paths, labels)):
        im = Image.open(p).convert("RGB"); im.thumbnail((TW, TH))
        x = 12 + (i % COLS) * (TW + 12); y = 12 + (i // COLS) * (TH + 44)
        sheet.paste(im, (x, y))
        ImageDraw.Draw(sheet).text((x + 4, y + TH + 8), lab, font=f, fill=(240, 232, 220))
    sheet.save(out, quality=88)
    print(out, sheet.size)

mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == "frames":
    paths = sorted(glob.glob(os.path.join(src, "prev_*.jpg")))
    labels = sys.argv[4].split(",") if len(sys.argv) > 4 else [os.path.basename(p) for p in paths]
    tile(paths, labels, out)
else:
    ts = [float(t) for t in sys.argv[4].split(",")]
    d = tempfile.mkdtemp(); paths = []
    for i, t in enumerate(ts):
        p = f"{d}/f{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", src, "-frames:v", "1", "-vf", "scale=540:-2", p], check=True)
        paths.append(p)
    tile(paths, [f"{t:.1f} s" for t in ts], out)
