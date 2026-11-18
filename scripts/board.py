"""Quiet Signal — style board: icon chips, a frame study of a live dashboard, palette."""
import subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

W, H = 2400, 1500
F = "/home/claude/fonts/"
SEQ = "/home/claude/icons/seq/"

# backdrop: a frame from the footage, mirrored, blurred and pressed down to near-black
p = subprocess.run(["ffmpeg", "-v", "error", "-ss", "30", "-i", "/home/claude/vid4/IMG_2814.mov", "-frames:v", "1", "-vf",
                    f"hflip,scale={W}:-1,crop={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
bg = np.frombuffer(p.stdout, np.uint8).reshape(H, W, 3).astype(np.float32) / 255
bg = cv2.GaussianBlur(bg, (0, 0), 40) * 0.16 + np.array([0.035, 0.035, 0.04], np.float32)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
bg *= (1 - 0.35 * np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 1.6 - 0.2, 0, 1))[..., None]
canvas = Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
d = ImageDraw.Draw(canvas)

def font(name, size): return ImageFont.truetype(F + name, size)
thin, light, serif_i = "Montserrat-Light.ttf", "Montserrat-Regular.ttf", "InstrumentSerif-Italic.ttf"
IV = (236, 230, 222, 255); MUT = (150, 144, 136, 255); GOLD = (181, 142, 87, 255)

def tracked(x, y, text, f, fill, tr):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + tr
    return x

M = 120
tracked(M, M, "QUIET SIGNAL", font(thin, 30), IV, 12)
d.text((M, M + 52), "rörelse som information", font=font(serif_i, 40), fill=MUT)
d.text((W - M, M + 8), "01 / 01", font=font(thin, 20), fill=MUT, anchor="ra")

# ---- row 1: the icon chips ----
icons = ["cap", "sparkles", "lightbulb", "gift", "martini", "shopping-bag", "flame", "trending-down", "globe", "timer", "message-circle", "folder"]
D, gap = 128, 0
n = len(icons); span = W - 2 * M; step = span / n
cy = 420
for i, nm in enumerate(icons):
    cx = M + step * (i + 0.5)
    chip = Image.new("RGBA", (D + 40, D + 40), (0, 0, 0, 0)); cd = ImageDraw.Draw(chip)
    cd.ellipse([20, 20, 20 + D, 20 + D], fill=(14, 14, 16, 215), outline=(255, 255, 255, 80), width=2)
    ic = Image.open(f"{SEQ}icon_{nm}/0024.png").convert("RGBA")
    isz = int(D * 0.56); ic = ic.resize((isz, isz), Image.LANCZOS)
    chip.alpha_composite(ic, (20 + (D - isz) // 2, 20 + (D - isz) // 2))
    canvas.alpha_composite(chip, (int(cx - D / 2 - 20), int(cy - D / 2 - 20)))
    d.text((cx, cy + D / 2 + 26), nm.replace("-", " "), font=font(thin, 17), fill=MUT, anchor="ma")
d.line([(M, cy + D / 2 + 78), (W - M, cy + D / 2 + 78)], fill=(255, 255, 255, 28), width=1)

# ---- row 2: frame study of the live dashboard ----
frames = [(6, "0,20 s"), (20, "0,67 s"), (40, "1,33 s"), (72, "2,40 s")]
fw = int((span - 3 * 40) / 4)
top = 700
for i, (idx, lbl) in enumerate(frames):
    im = Image.open(f"{SEQ}ret_dash_sv/{idx:04d}.png").convert("RGBA")
    im = im.resize((fw, int(im.height * fw / im.width)), Image.LANCZOS)
    x = M + i * (fw + 40)
    canvas.alpha_composite(im, (x, top))
    ty = top + im.height + 34
    d.ellipse([x + fw / 2 - 5, ty - 5, x + fw / 2 + 5, ty + 5], fill=GOLD)
    d.text((x + fw / 2, ty + 22), lbl, font=font(thin, 20), fill=IV, anchor="ma")
fh = top + int(Image.open(f"{SEQ}ret_dash_sv/0072.png").height * fw / Image.open(f"{SEQ}ret_dash_sv/0072.png").width) + 34
d.line([(M + fw / 2, fh), (W - M - fw / 2, fh)], fill=(181, 142, 87, 110), width=1)
d.text((M, top - 54), "fig. 1 — en siffra räknar, en linje ritas, inget studsar", font=font(thin, 20), fill=MUT)

# ---- palette ----
pal = [((247, 242, 236), "#F7F2EC"), ((31, 27, 24), "#1F1B18"), ((181, 142, 87), "#B58E57"), ((249, 115, 22), "#F97316"), ((255, 225, 77), "#FFE14D")]
px = W - M - len(pal) * 150 + 40
py = H - M - 40
for i, (c, hx) in enumerate(pal):
    x = px + i * 150
    d.ellipse([x, py - 50, x + 44, py - 6], fill=c + (255,), outline=(255, 255, 255, 60), width=1)
    d.text((x + 22, py + 8), hx, font=font(thin, 16), fill=MUT, anchor="ma")
d.text((M, H - M - 20), "0,30 s in · 0,15 s mellan · samma kurva varje gång", font=font(thin, 20), fill=MUT)

canvas.convert("RGB").save("/home/claude/vid4/design/quiet-signal-board.png", optimize=True)
print("saved")
