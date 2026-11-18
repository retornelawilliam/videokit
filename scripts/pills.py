import re, base64
from playwright.sync_api import sync_playwright

SPLIT = "with sync_playwright() as " + "p:"
src = open('/home/claude/scripts/assets.py').read().split(SPLIT)[0]
ns = {}; exec(src, ns); BASE_CSS = ns['BASE_CSS']

def _embed(css):
    def r(m):
        return "url('data:font/ttf;base64," + base64.b64encode(open(m.group(1), "rb").read()).decode() + "')"
    return re.sub(r"url\('file://([^']+\.ttf)'\)", r, css)
BASE_CSS = _embed(BASE_CSS)

def logo(n):
    return base64.b64encode(open(f"/home/claude/icons/logos/{n.lower()}.png", "rb").read()).decode()

SIZE = {"ChatGPT": 40, "Gemini": 40, "Claude": 44}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=("/usr/bin/google-chrome" if __import__("os").path.exists("/usr/bin/google-chrome") else None), args=["--no-sandbox"])
    pg = b.new_page(device_scale_factor=2, viewport={"width": 600, "height": 300})
    for n in ["ChatGPT", "Gemini", "Claude"]:
        html = f"""<div style="padding:24px"><div style="width:300px;height:92px;box-sizing:border-box;display:flex;align-items:center;gap:16px;padding:0 22px 0 13px;
          background:var(--ivory);border-radius:46px;box-shadow:0 14px 30px rgba(0,0,0,.35)">
          <div style="width:66px;height:66px;border-radius:50%;background:#fff;border:1.5px solid #E6DED4;box-sizing:border-box;display:flex;align-items:center;justify-content:center;overflow:hidden">
            <img src="data:image/png;base64,{logo(n)}" style="width:{SIZE[n]}px;height:{SIZE[n]}px"></div>
          <div style="font-size:36px;font-weight:800;color:var(--ink);letter-spacing:-.5px">{n}</div></div></div>"""
        pg.set_content(f"<html><head><style>{BASE_CSS}</style></head><body style='margin:0'><div id='r' style='display:inline-block'>{html}</div></body></html>")
        pg.wait_for_timeout(250)
        pg.evaluate("document.fonts.ready.then(()=>1)")
        pg.locator("#r").screenshot(path=f"/home/claude/icons/pills/{n.lower()}.png", omit_background=True)
    b.close()
print("ok")
