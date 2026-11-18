"""Render UI mockups (Retornela app/dashboard, Impetus platform, coupon, guest-list card) to transparent PNGs."""
import os
from playwright.sync_api import sync_playwright

OUT = "/home/claude/icons/gen/"
os.makedirs(OUT, exist_ok=True)
F = "file:///home/claude/fonts/"

BASE_CSS = f"""
@font-face {{ font-family: 'Mont'; src: url('{F}Montserrat-Light.ttf'); font-weight: 300; }}
@font-face {{ font-family: 'Mont'; src: url('{F}Montserrat-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Mont'; src: url('{F}Montserrat-SemiBold.ttf'); font-weight: 600; }}
@font-face {{ font-family: 'Mont'; src: url('{F}Montserrat-Bold.ttf'); font-weight: 700; }}
@font-face {{ font-family: 'Mont'; src: url('{F}Montserrat-ExtraBold.ttf'); font-weight: 800; }}
@font-face {{ font-family: 'Serif'; src: url('{F}InstrumentSerif-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Serif'; src: url('{F}InstrumentSerif-Italic.ttf'); font-style: italic; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: transparent; }}
body {{ font-family: 'Mont', sans-serif; -webkit-font-smoothing: antialiased; }}
#root {{ display: inline-block; padding: 30px; }}
:root {{ --ivory:#F7F2EC; --ink:#1F1B18; --gold:#B58E57; --rose:#EAD8CF; --muted:#8B8178; --line:#E6DED4; }}
.phone {{ width: 390px; height: 800px; background: #0c0c0c; border-radius: 58px; padding: 12px;
          box-shadow: 0 30px 60px rgba(0,0,0,.35), inset 0 0 0 2px #2a2a2a; }}
.screen {{ width: 100%; height: 100%; background: var(--ivory); border-radius: 46px; overflow: hidden; position: relative; }}
.island {{ position:absolute; top:12px; left:50%; transform:translateX(-50%); width:118px; height:34px; background:#000; border-radius:20px; z-index:5; }}
.status {{ height: 54px; display:flex; justify-content:space-between; align-items:flex-end; padding: 0 30px 6px; font-weight:600; font-size:15px; color:var(--ink); }}
.app {{ padding: 10px 22px; }}
.clinic {{ font-size: 11px; letter-spacing: 3px; color: var(--muted); text-transform: uppercase; font-weight:600; }}
.h1 {{ font-family:'Serif'; font-size: 38px; color: var(--ink); line-height: 1.05; margin-top: 4px; }}
.card-dark {{ margin-top: 16px; border-radius: 26px; padding: 22px; color: #fff;
              background: linear-gradient(135deg, #2a231e 0%, #4a3a2c 100%); }}
.big {{ font-family:'Serif'; font-size: 64px; line-height: 1; }}
.small {{ font-size: 12px; opacity: .8; }}
.bar {{ height: 8px; border-radius: 4px; background: rgba(255,255,255,.2); margin: 14px 0 8px; overflow:hidden; }}
.bar > i {{ display:block; height:100%; width:83%; background: linear-gradient(90deg, #d9b97f, #f3dcae); border-radius:4px; }}
.sec {{ font-size: 12px; font-weight:700; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); margin: 20px 0 10px; }}
.row {{ display:flex; align-items:center; gap: 12px; background:#fff; border-radius: 18px; padding: 13px 14px; margin-bottom: 9px; box-shadow: 0 1px 0 var(--line); }}
.dot {{ width: 40px; height: 40px; border-radius: 12px; background: var(--rose); display:flex; align-items:center; justify-content:center; color: var(--ink); font-weight:700; font-size: 15px; }}
.rt {{ flex:1; }} .rt b {{ display:block; font-size: 14px; color: var(--ink); font-weight:600; }} .rt span {{ font-size: 12px; color: var(--muted); }}
.btn {{ font-size: 12px; font-weight:700; padding: 8px 12px; border-radius: 12px; background: var(--ink); color:#fff; }}
.btn.ghost {{ background: transparent; color: var(--muted); border: 1px solid var(--line); }}
.chip {{ font-size: 11px; font-weight:700; padding: 5px 9px; border-radius: 10px; background:#e7f2e8; color:#2f6b3a; }}
.tabs {{ position:absolute; bottom:0; left:0; right:0; height: 78px; background:#fff; border-top:1px solid var(--line);
         display:flex; justify-content:space-around; align-items:center; padding-bottom: 14px; font-size: 11px; color: var(--muted); font-weight:600; }}
.tabs .on {{ color: var(--ink); }}
.tabs i {{ display:block; width: 22px; height: 22px; border-radius: 7px; margin: 0 auto 4px; background: var(--line); }}
.tabs .on i {{ background: var(--gold); }}
.offer {{ border-radius: 20px; padding: 16px; background: var(--rose); color: var(--ink); }}
.offer b {{ font-family:'Serif'; font-size: 26px; font-weight:400; display:block; }}
"""

def phone(inner, tabs_on=2, tabs=("Hem", "Behandlingar", "Poäng", "Profil")):
    t = "".join(f'<div class="{"on" if i == tabs_on else ""}"><i></i>{x}</div>' for i, x in enumerate(tabs))
    return f'<div class="phone"><div class="screen"><div class="island"></div><div class="status"><span>9:41</span><span>●●● ▮</span></div><div class="app">{inner}</div><div class="tabs">{t}</div></div></div>'

T = {
 "sv": dict(clinic="Lumière Clinic", hi="Hej Sara", pts_lbl="Dina poäng", pts="poäng", left="260 poäng kvar till gratis ansiktsbehandling",
            rewards="Belöningar", r1=("10 % rabatt", "500 poäng"), r2=("Gratis ansiktsbehandling", "1 500 poäng"), r3=("Hydrafacial", "2 500 poäng"),
            redeem="Lös in", locked="Låst", earn="Så tjänar du poäng", e1=("Varje besök", "+100 p"), e2=("Värva en vän", "+300 p"),
            treat="Mina behandlingar", up="Kommande", h="Historik", conf="Bekräftad",
            u1=("Laserbehandling", "Fre 12 dec · 14:00"), u2=("Hydrafacial", "Tor 8 jan · 10:30"),
            h1=("Microneedling", "14 nov"), h2=("Konsultation", "2 okt"), offers="Dina erbjudanden",
            off=("15 % på nästa besök", "Gäller t.o.m. 31 dec"),
            tabs=("Hem", "Behandlingar", "Poäng", "Profil")),
 "en": dict(clinic="Lumière Clinic", hi="Hi Sara", pts_lbl="Your points", pts="points", left="260 points left to a free facial",
            rewards="Rewards", r1=("10% off", "500 points"), r2=("Free facial", "1,500 points"), r3=("Hydrafacial", "2,500 points"),
            redeem="Redeem", locked="Locked", earn="How you earn points", e1=("Every visit", "+100 pts"), e2=("Refer a friend", "+300 pts"),
            treat="My treatments", up="Upcoming", h="History", conf="Confirmed",
            u1=("Laser treatment", "Fri 12 Dec · 2:00 PM"), u2=("Hydrafacial", "Thu 8 Jan · 10:30 AM"),
            h1=("Microneedling", "14 Nov"), h2=("Consultation", "2 Oct"), offers="Your offers",
            off=("15% off your next visit", "Valid until 31 Dec"),
            tabs=("Home", "Treatments", "Points", "Profile")),
}

def points(l):
    t = T[l]
    inner = f"""
    <div class="clinic">{t['clinic']}</div><div class="h1">{t['hi']}</div>
    <div class="card-dark"><div class="small">{t['pts_lbl']}</div>
      <div style="display:flex;align-items:baseline;gap:10px"><div class="big">1 240</div><div class="small">{t['pts']}</div></div>
      <div class="bar"><i></i></div><div class="small">{t['left']}</div></div>
    <div class="sec">{t['rewards']}</div>
    <div class="row"><div class="dot">%</div><div class="rt"><b>{t['r1'][0]}</b><span>{t['r1'][1]}</span></div><div class="btn">{t['redeem']}</div></div>
    <div class="row"><div class="dot">✦</div><div class="rt"><b>{t['r2'][0]}</b><span>{t['r2'][1]}</span></div><div class="btn ghost">{t['locked']}</div></div>
    <div class="row"><div class="dot">◇</div><div class="rt"><b>{t['r3'][0]}</b><span>{t['r3'][1]}</span></div><div class="btn ghost">{t['locked']}</div></div>"""
    return phone(inner, 2, t["tabs"])

def treatments(l):
    t = T[l]
    inner = f"""
    <div class="clinic">{t['clinic']}</div><div class="h1">{t['treat']}</div>
    <div class="sec">{t['up']}</div>
    <div class="row"><div class="dot">12</div><div class="rt"><b>{t['u1'][0]}</b><span>{t['u1'][1]}</span></div><div class="chip">{t['conf']}</div></div>
    <div class="row"><div class="dot">8</div><div class="rt"><b>{t['u2'][0]}</b><span>{t['u2'][1]}</span></div><div class="chip">{t['conf']}</div></div>
    <div class="sec">{t['h']}</div>
    <div class="row"><div class="dot">✓</div><div class="rt"><b>{t['h1'][0]}</b><span>{t['h1'][1]}</span></div><span style="font-weight:700;color:var(--gold);font-size:13px">+150 p</span></div>
    <div class="row"><div class="dot">✓</div><div class="rt"><b>{t['h2'][0]}</b><span>{t['h2'][1]}</span></div><span style="font-weight:700;color:var(--gold);font-size:13px">+50 p</span></div>
    <div class="sec">{t['offers']}</div>
    <div class="offer"><b>{t['off'][0]}</b><span style="font-size:12px">{t['off'][1]}</span></div>"""
    return phone(inner, 1, t["tabs"])

def notif():
    def n(title, body, time="nu"):
        return f"""<div style="width:620px;background:rgba(250,247,243,.96);border-radius:30px;padding:18px 20px;display:flex;gap:14px;
                 box-shadow:0 20px 40px rgba(0,0,0,.25);margin-bottom:14px;backdrop-filter:blur(10px)">
          <div style="width:52px;height:52px;border-radius:13px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;
               align-items:center;justify-content:center;color:#f3dcae;font-family:Serif;font-size:32px;flex:none">R</div>
          <div style="flex:1"><div style="display:flex;justify-content:space-between;font-size:14px;color:#6d655d;font-weight:600">
            <span>RETORNELA</span><span>{time}</span></div>
            <div style="font-size:18px;font-weight:700;color:#1F1B18;margin-top:3px">{title}</div>
            <div style="font-size:16px;color:#3b352f;margin-top:2px;line-height:1.35">{body}</div></div></div>"""
    return n("Lumière Clinic", "Röstmeddelande: Hej Sara! Det är dags för din nästa behandling. Boka i appen ✨") + \
           n("Påminnelse", "Din laserbehandling är imorgon kl 14:00", "5 min")

def referral():
    return """<div style="width:620px;background:var(--ivory);border-radius:34px;padding:34px;box-shadow:0 24px 50px rgba(0,0,0,.3)">
      <div class="clinic">Lumière Clinic</div>
      <div style="font-family:Serif;font-size:52px;color:var(--ink);line-height:1;margin-top:8px">Bjud in en vän</div>
      <div style="font-size:19px;color:#4a433c;margin-top:10px">Ni får båda <b>300 poäng</b> när din vän bokar sin första behandling.</div>
      <div style="display:flex;gap:12px;margin-top:22px;align-items:center">
        <div style="flex:1;border:2px dashed var(--gold);border-radius:18px;padding:14px 18px;font-weight:800;font-size:26px;letter-spacing:3px;color:var(--ink)">SARA300</div>
        <div class="btn" style="font-size:18px;padding:16px 22px;border-radius:18px">Dela länk</div></div></div>"""

def dashboard():
    pts = [(0, 150), (60, 140), (120, 128), (180, 118), (240, 100), (300, 92), (360, 70), (420, 58), (480, 40), (540, 28)]
    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    area = path + " L540,170 L0,170 Z"
    kpi = lambda lbl, val, sub: f"""<div style="flex:1;background:#fff;border-radius:20px;padding:18px 20px;border:1px solid var(--line)">
        <div style="font-size:13px;color:var(--muted);font-weight:600">{lbl}</div>
        <div style="font-family:Serif;font-size:46px;color:var(--ink);line-height:1.05;margin-top:6px">{val}</div>
        <div style="font-size:12px;color:#2f6b3a;font-weight:700;margin-top:2px">{sub}</div></div>"""
    return f"""<div style="width:900px;background:var(--ivory);border-radius:28px;overflow:hidden;box-shadow:0 30px 60px rgba(0,0,0,.35)">
      <div style="height:44px;background:#ece5dc;display:flex;align-items:center;gap:8px;padding:0 18px">
        <i style="width:12px;height:12px;border-radius:6px;background:#e0675d"></i><i style="width:12px;height:12px;border-radius:6px;background:#f0bd4f"></i>
        <i style="width:12px;height:12px;border-radius:6px;background:#62c454"></i>
        <span style="margin-left:14px;font-size:13px;color:#6d655d;font-weight:600">Retornela · Klinikpanel</span></div>
      <div style="padding:26px 30px 30px">
        <div style="display:flex;justify-content:space-between;align-items:flex-end">
          <div><div class="clinic">Lumière Clinic · demo</div><div style="font-family:Serif;font-size:44px;color:var(--ink)">Översikt</div></div>
          <div style="font-size:13px;color:var(--muted);font-weight:600">Senaste 6 mån</div></div>
        <div style="display:flex;gap:14px;margin-top:16px">
          {kpi('Återkommande kunder', '64 %', '▲ +18 p.e.')}{kpi('Aktiva medlemmar', '312', '▲ +41 denna månad')}{kpi('Genererat via appen', '48 200 kr', '▲ från poäng & erbjudanden')}</div>
        <div style="background:#fff;border-radius:20px;border:1px solid var(--line);margin-top:14px;padding:18px 20px">
          <div style="font-size:14px;font-weight:700;color:var(--ink)">Återbesök per månad</div>
          <svg width="840" height="180" viewBox="0 0 540 170" preserveAspectRatio="none" style="margin-top:8px">
            <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#B58E57" stop-opacity=".35"/><stop offset="1" stop-color="#B58E57" stop-opacity="0"/></linearGradient></defs>
            <path d="{area}" fill="url(#g)"/><path d="{path}" fill="none" stroke="#B58E57" stroke-width="3"/></svg>
          <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);font-weight:600;margin-top:4px">
            <span>jun</span><span>jul</span><span>aug</span><span>sep</span><span>okt</span><span>nov</span></div></div></div></div>"""

def logo(l):
    tag = "Lojalitetsappar för kliniker" if l == "sv" else "Loyalty apps for clinics"
    sub = "runt om i Europa" if l == "sv" else "across Europe"
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:56px 40px 48px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.35)">
      <div style="width:84px;height:84px;margin:0 auto;border-radius:22px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;align-items:center;justify-content:center;
           color:#f3dcae;font-family:Serif;font-size:56px">R</div>
      <div style="font-family:Serif;font-size:118px;color:var(--ink);line-height:1;margin-top:18px;letter-spacing:1px">Retornela</div>
      <div style="width:70px;height:2px;background:var(--gold);margin:22px auto"></div>
      <div style="font-size:26px;color:#3b352f;font-weight:600">{tag}</div>
      <div style="font-size:20px;color:var(--muted);font-weight:400;margin-top:6px">{sub}</div></div>"""

def cta(l):
    h = "Se hur din egen app kan se ut" if l == "sv" else "See what your own app could look like"
    dm = "Skriv till oss i DM" if l == "sv" else "Send us a DM"
    ic = lambda s: f'<div style="width:54px;height:54px;border-radius:16px;background:var(--rose);display:flex;align-items:center;justify-content:center;font-size:26px;color:var(--ink);font-weight:700">{s}</div>'
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:40px;box-shadow:0 30px 60px rgba(0,0,0,.35)">
      <div class="clinic">Retornela</div>
      <div style="font-family:Serif;font-size:56px;color:var(--ink);line-height:1.05;margin-top:8px">{h}</div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:26px">{ic('✉')}<div style="font-size:30px;font-weight:700;color:var(--ink)">info@retornela.com</div></div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:14px">{ic('↗')}<div style="font-size:26px;font-weight:600;color:#4a433c">{dm}</div></div></div>"""

def impetus():
    side = ["Översikt", "Offerter", "Projekt", "Tidrapporter", "Fakturor", "Kunder"]
    s = "".join(f'<div style="padding:12px 16px;border-radius:12px;margin-bottom:4px;font-size:15px;font-weight:{700 if x=="Offerter" else 500};'
                f'background:{"#F97316" if x=="Offerter" else "transparent"};color:{"#fff" if x=="Offerter" else "#cbd5e1"}">{x}</div>' for x in side)
    rows = [("Rivning & förberedelse", "12 h", "7 800 kr"), ("Tätskikt & kakel", "26 m²", "23 400 kr"), ("Material", "", "18 650 kr"), ("ROT-avdrag", "", "−9 360 kr")]
    r = "".join(f'<div style="display:flex;padding:13px 0;border-bottom:1px solid #e2e8f0;font-size:16px;color:#0f172a">'
                f'<span style="flex:1;font-weight:600">{a}</span><span style="width:90px;color:#64748b">{b}</span><span style="width:120px;text-align:right;font-weight:700">{c}</span></div>' for a, b, c in rows)
    kp = lambda a, b: f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:14px 16px;margin-bottom:12px"><div style="font-size:13px;color:#64748b;font-weight:600">{a}</div><div style="font-size:30px;font-weight:800;color:#0f172a;margin-top:4px">{b}</div></div>'
    return f"""<div style="width:960px;height:600px;display:flex;border-radius:26px;overflow:hidden;box-shadow:0 30px 60px rgba(0,0,0,.35);background:#f8fafc">
      <div style="width:210px;background:#0f172a;padding:24px 14px"><div style="color:#fff;font-weight:800;font-size:20px;margin:0 6px 22px">Allt på ett ställe</div>{s}</div>
      <div style="flex:1;padding:26px 26px;display:flex;gap:20px">
        <div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-radius:20px;padding:22px 24px">
          <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-size:13px;color:#64748b;font-weight:700">OFFERT #1042</div>
            <div style="font-size:12px;font-weight:700;padding:5px 10px;border-radius:10px;background:#ffedd5;color:#c2410c">Utkast</div></div>
          <div style="font-size:26px;font-weight:800;color:#0f172a;margin-top:6px">Badrumsrenovering</div>
          <div style="font-size:15px;color:#64748b;margin:2px 0 10px">Andersson · Kungsbacka</div>{r}
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px">
            <div><div style="font-size:13px;color:#64748b;font-weight:600">Totalt att betala</div><div style="font-size:32px;font-weight:800;color:#0f172a">40 490 kr</div></div>
            <div style="background:#F97316;color:#fff;font-weight:700;font-size:17px;padding:14px 22px;border-radius:14px">Skicka offert</div></div></div>
        <div style="width:220px">{kp('Öppna projekt','8')}{kp('Offerter i nov','14')}{kp('Fakturerat i nov','312 400 kr')}{kp('Tid sparad / vecka','6 h')}</div></div></div>"""

def coupon():
    return """<div style="width:760px;background:#0b0b0b;border-radius:34px;padding:40px 44px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.45);border:1px solid #2a2a2a">
      <div style="font-size:22px;letter-spacing:12px;color:#d6b46e;font-weight:700">BLACK FRIDAY</div>
      <div style="margin:26px auto 0;border:3px dashed #d6b46e;border-radius:24px;padding:18px 10px">
        <div style="font-size:16px;letter-spacing:4px;color:#9b9b9b;font-weight:600">RABATTKOD</div>
        <div style="font-size:104px;font-weight:800;color:#fff;letter-spacing:4px;line-height:1.1">EARLY15</div></div>
      <div style="font-size:30px;font-weight:700;color:#fff;margin-top:24px">15 % på allt</div>
      <div style="font-size:20px;color:#9b9b9b;margin-top:6px">monarcheu.com</div></div>"""

def excet():
    li = lambda s: f'<div style="display:flex;align-items:center;gap:16px;margin-top:14px"><div style="width:40px;height:40px;border-radius:20px;background:#FFE14D;color:#000;font-weight:900;font-size:26px;display:flex;align-items:center;justify-content:center;flex:none">✓</div><div style="font-size:30px;font-weight:800;color:#fff;text-align:left">{s}</div></div>'
    return f"""<div style="width:820px;background:#000;border-radius:34px;padding:36px 40px;box-shadow:0 30px 60px rgba(0,0,0,.5);border:3px solid #FFE14D">
      <div style="font-size:24px;font-weight:800;letter-spacing:6px;color:#FFE14D">GÄSTLISTA</div>
      <div style="font-size:64px;font-weight:900;color:#fff;line-height:1.05;margin-top:4px">5 DEC · EXCET</div>
      <div style="font-size:22px;font-weight:600;color:#bbb;margin:10px 0 6px">Goodiebag till de 50 första</div>
      {li('Chans på gratis MONARCH-keps')}{li('Jacquelle Beauty-läppglans')}{li('Första drinken bjuder vi på')}</div>"""

PAGES = {
    "ret_points_sv": points("sv"), "ret_points_en": points("en"),
    "ret_treat_sv": treatments("sv"), "ret_treat_en": treatments("en"),
    "ret_push_sv": notif(), "ret_ref_sv": referral(), "ret_dash_sv": dashboard(),
    "ret_logo_sv": logo("sv"), "ret_logo_en": logo("en"), "ret_cta_sv": cta("sv"), "ret_cta_en": cta("en"),
    "imp_dash": impetus(), "bf_coupon": coupon(), "excet_card": excet(),
}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=("/usr/bin/google-chrome" if __import__("os").path.exists("/usr/bin/google-chrome") else None), args=["--no-sandbox"])
    pg = b.new_page(device_scale_factor=2, viewport={"width": 1200, "height": 1000})
    for name, html in PAGES.items():
        pg.set_content(f"<html><head><style>{BASE_CSS}</style></head><body><div id='root'>{html}</div></body></html>")
        pg.wait_for_timeout(250)
        pg.locator("#root").screenshot(path=OUT + name + ".png", omit_background=True)
        print("ok", name)
    b.close()
