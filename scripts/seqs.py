"""Render animated ("live") overlays as RGBA PNG frame sequences via headless Chrome.
Each page exposes render(t); data-attributes drive deterministic animation."""
import os, re, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/claude/scripts")
import importlib.util, types
src = open('/home/claude/scripts/assets.py').read().split('with sync_playwright() as p:')[0]
ns = {}
exec(src, ns)
BASE_CSS = ns['BASE_CSS']

import base64 as _b64
def _embed(css):
    def r(m):
        return "url('data:font/ttf;base64," + _b64.b64encode(open(m.group(1), "rb").read()).decode() + "')"
    return re.sub(r"url\('file://([^']+\.ttf)'\)", r, css)
BASE_CSS = _embed(BASE_CSS)

OUT = "/home/claude/icons/seq/"
LUC = "/home/claude/icons/lucide/"
FPS = 30
ONLY = sys.argv[1:]  # optional subset

RUNTIME = r"""
<script>
const E = x => { x = Math.min(Math.max(x,0),1); return 1 - Math.pow(1-x,3); };          // ease-out cubic
const EIO = x => { x = Math.min(Math.max(x,0),1); return x<.5 ? 4*x*x*x : 1-Math.pow(-2*x+2,3)/2; };
function fmt(v, el){ const d = +(el.dataset.dec||0); let s = d ? v.toFixed(d).replace('.',',') : Math.round(v).toLocaleString('sv-SE');
  return (el.dataset.pre||'') + s + (el.dataset.suf||''); }
function render(t){
  document.querySelectorAll('[data-in]').forEach(el=>{ const t0=+el.dataset.in, d=+(el.dataset.dur||0.35), k=E((t-t0)/d);
    const dy = +(el.dataset.dy ?? 16), dx = +(el.dataset.dx || 0);
    el.style.opacity=k; el.style.transform=`translate(${dx*(1-k)}px,${dy*(1-k)}px)`; });
  document.querySelectorAll('[data-pop]').forEach(el=>{ const t0=+el.dataset.pop, x=Math.min(Math.max((t-t0)/0.3,0),1);
    const s = x<=0?0.6: 1 + 0.12*Math.sin(Math.PI*x)*(1-x) ; el.style.opacity=E(x*1.6); el.style.transform=`scale(${0.6+0.4*E(x)+ (s-1)})`; });
  document.querySelectorAll('[data-count]').forEach(el=>{ const [t0,t1]=el.dataset.span.split(',').map(Number);
    el.textContent = fmt(+el.dataset.count * EIO((t-t0)/(t1-t0)), el); });
  document.querySelectorAll('[data-draw]').forEach(el=>{ const [t0,t1]=el.dataset.draw.split(',').map(Number);
    el.style.strokeDasharray=1; el.style.strokeDashoffset = 1-EIO((t-t0)/(t1-t0)); });
  document.querySelectorAll('[data-fill]').forEach(el=>{ const [t0,t1,p]=el.dataset.fill.split(',').map(Number);
    el.style.width = (p*EIO((t-t0)/(t1-t0)))+'%'; });
  document.querySelectorAll('[data-type]').forEach(el=>{ if(!el.dataset.full) el.dataset.full=el.textContent;
    const [t0,t1]=el.dataset.type.split(',').map(Number); const n=Math.round(el.dataset.full.length*Math.min(Math.max((t-t0)/(t1-t0),0),1));
    el.textContent = el.dataset.full.slice(0,n); el.style.opacity = n>0?1:0; });
  document.querySelectorAll('[data-wave]').forEach((el,i)=>{ const bars=el.children;
    for(let j=0;j<bars.length;j++){ const h = 0.25 + 0.75*Math.abs(Math.sin(t*6.3 + j*0.9) * Math.sin(t*2.1 + j*0.37));
      bars[j].style.transform=`scaleY(${h})`; } });
  document.querySelectorAll('[data-follow]').forEach(el=>{ const p=document.getElementById(el.dataset.follow);
    const [t0,t1]=el.dataset.span.split(',').map(Number); const k=EIO((t-t0)/(t1-t0)); const L=p.getTotalLength();
    const pt=p.getPointAtLength(L*k); el.setAttribute('cx',pt.x); el.setAttribute('cy',pt.y); el.style.opacity = k>0?1:0; });
  document.querySelectorAll('[data-swap]').forEach(el=>{ const t0=+el.dataset.swap; const a=el.children[0], b=el.children[1];
    const k=E((t-t0)/0.25); a.style.opacity=1-k; b.style.opacity=k; });
}
</script>"""

# ---------------- icons: line icons drawn on ----------------
CAP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M2.5 16.5c0-6 3.9-10 9-10s8.2 3.6 8.6 8.2"/><path d="M20.1 14.7c1.6.4 2.4 1.1 2.2 1.8H2.5"/><path d="M10.6 6.6c-1.5 2.8-2 6.2-1.6 9.9"/><circle cx="11.5" cy="5.6" r=".7"/></svg>"""

def icon_page(svg, px=104, sw=2.1, color="#ffffff"):
    svg = re.sub(r'width="24"', "", svg); svg = re.sub(r'height="24"', "", svg)
    svg = svg.replace('stroke-width="2"', f'stroke-width="{sw}"').replace("currentColor", color)
    # every drawable element gets pathLength=1 and a staggered draw window
    elems = re.findall(r"<(path|circle|rect|line|polyline|ellipse|polygon)\b", svg)
    n = max(1, len(elems)); i = [0]
    def tag(m):
        k = i[0]; i[0] += 1
        t0 = 0.05 + 0.32 * k / n
        return f'<{m.group(1)} pathLength="1" data-draw="{t0:.3f},{t0 + 0.32:.3f}"'
    svg = re.sub(r"<(path|circle|rect|line|polyline|ellipse|polygon)\b", tag, svg)
    svg = svg.replace("<svg", f'<svg width="{px}" height="{px}"', 1)
    return f'<div style="width:{px+8}px;height:{px+8}px;display:flex;align-items:center;justify-content:center">{svg}</div>', 0.8

# ---------------- UI pages ----------------
T = {
 "sv": dict(clinic="Lumière Clinic", hi="Hej Sara", pts_lbl="Dina poäng", pts="poäng", left="260 poäng kvar till gratis ansiktsbehandling",
            rewards="Belöningar", r1=("10 % rabatt", "500 poäng"), r2=("Gratis ansiktsbehandling", "1 500 poäng"), r3=("Hydrafacial", "2 500 poäng"),
            redeem="Lös in", locked="Låst", treat="Mina behandlingar", up="Kommande", h="Historik", conf="Bekräftad",
            u1=("Laserbehandling", "Fre 12 dec · 14:00"), u2=("Hydrafacial", "Tor 8 jan · 10:30"),
            h1=("Microneedling", "14 nov"), h2=("Konsultation", "2 okt"), offers="Dina erbjudanden",
            off=("15 % på nästa besök", "Gäller t.o.m. 31 dec"), tabs=("Hem", "Behandlingar", "Poäng", "Profil")),
 "en": dict(clinic="Lumière Clinic", hi="Hi Sara", pts_lbl="Your points", pts="points", left="260 points left to a free facial",
            rewards="Rewards", r1=("10% off", "500 points"), r2=("Free facial", "1,500 points"), r3=("Hydrafacial", "2,500 points"),
            redeem="Redeem", locked="Locked", treat="My treatments", up="Upcoming", h="History", conf="Confirmed",
            u1=("Laser treatment", "Fri 12 Dec · 2:00 PM"), u2=("Hydrafacial", "Thu 8 Jan · 10:30 AM"),
            h1=("Microneedling", "14 Nov"), h2=("Consultation", "2 Oct"), offers="Your offers",
            off=("15% off your next visit", "Valid until 31 Dec"), tabs=("Home", "Treatments", "Points", "Profile")),
}

def phone(inner, tabs_on, tabs):
    t = "".join(f'<div class="{"on" if i == tabs_on else ""}"><i></i>{x}</div>' for i, x in enumerate(tabs))
    return (f'<div class="phone"><div class="screen"><div class="island"></div><div class="status"><span>9:41</span><span>●●● ▮</span></div>'
            f'<div class="app">{inner}</div><div class="tabs">{t}</div></div></div>')

def points(l):
    t = T[l]
    row = lambda i, dot, a, b, btn, cls, t0: (f'<div class="row" data-in="{t0}" data-dx="40" data-dy="0"><div class="dot">{dot}</div>'
                                             f'<div class="rt"><b>{a}</b><span>{b}</span></div><div class="btn {cls}">{btn}</div></div>')
    inner = f"""<div class="clinic">{t['clinic']}</div><div class="h1">{t['hi']}</div>
    <div class="card-dark"><div class="small">{t['pts_lbl']}</div>
      <div style="display:flex;align-items:baseline;gap:10px"><div class="big" data-count="1240" data-span="0.1,1.15">0</div><div class="small">{t['pts']}</div></div>
      <div class="bar"><i data-fill="0.25,1.35,83" style="width:0"></i></div><div class="small" data-in="1.0">{t['left']}</div></div>
    <div class="sec" data-in="0.45">{t['rewards']}</div>
    {row(0,'%',*t['r1'],t['redeem'],'',0.55)}{row(1,'✦',*t['r2'],t['locked'],'ghost',0.7)}{row(2,'◇',*t['r3'],t['locked'],'ghost',0.85)}"""
    return phone(inner, 2, t["tabs"]), 1.6

def treatments(l):
    t = T[l]
    row = lambda dot, a, b, right, t0: (f'<div class="row" data-in="{t0}" data-dx="40" data-dy="0"><div class="dot">{dot}</div>'
                                       f'<div class="rt"><b>{a}</b><span>{b}</span></div>{right}</div>')
    chip = lambda t0: f'<div class="chip" data-pop="{t0}">{t["conf"]}</div>'
    pts = lambda v, t0: f'<span data-pop="{t0}" style="font-weight:700;color:var(--gold);font-size:13px">+{v} p</span>'
    inner = f"""<div class="clinic">{t['clinic']}</div><div class="h1">{t['treat']}</div>
    <div class="sec" data-in="0.05">{t['up']}</div>
    {row('12',*t['u1'],chip(0.45),0.15)}{row('8',*t['u2'],chip(0.6),0.3)}
    <div class="sec" data-in="0.45">{t['h']}</div>
    {row('✓',*t['h1'],pts(150,0.85),0.55)}{row('✓',*t['h2'],pts(50,0.95),0.7)}
    <div class="sec" data-in="0.9">{t['offers']}</div>
    <div class="offer" data-in="1.0"><b>{t['off'][0]}</b><span style="font-size:12px">{t['off'][1]}</span></div>"""
    return phone(inner, 1, t["tabs"]), 1.4

def notif():
    wave = "".join('<i style="display:inline-block;width:4px;height:26px;margin-right:3px;border-radius:2px;background:#B58E57;transform-origin:center"></i>' for _ in range(22))
    def n(title, body, extra, time, t0):
        return f"""<div data-in="{t0}" data-dy="-60" data-dur="0.45" style="width:620px;background:rgba(250,247,243,.97);border-radius:30px;padding:18px 20px;display:flex;gap:14px;
                 box-shadow:0 20px 40px rgba(0,0,0,.22);margin-bottom:14px">
          <div style="width:52px;height:52px;border-radius:13px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;
               align-items:center;justify-content:center;color:#f3dcae;font-family:Serif;font-size:32px;flex:none">R</div>
          <div style="flex:1"><div style="display:flex;justify-content:space-between;font-size:14px;color:#6d655d;font-weight:600">
            <span>RETORNELA</span><span>{time}</span></div>
            <div style="font-size:18px;font-weight:700;color:#1F1B18;margin-top:3px">{title}</div>
            <div style="font-size:16px;color:#3b352f;margin-top:2px;line-height:1.35">{body}</div>{extra}</div></div>"""
    voice = f"""<div style="display:flex;align-items:center;gap:12px;margin-top:10px">
        <div style="width:34px;height:34px;border-radius:17px;background:#1F1B18;color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px">▶</div>
        <div data-wave style="display:flex;align-items:center;height:30px">{wave}</div><span style="font-size:13px;color:#6d655d;font-weight:600">0:07</span></div>"""
    return (n("Lumière Clinic", "Röstmeddelande: Hej Sara! Dags för din nästa behandling.", voice, "nu", 0.0) +
            n("Påminnelse", "Din laserbehandling är imorgon kl 14:00", "", "5 min", 0.7)), 4.5

def referral():
    return """<div style="width:620px;background:var(--ivory);border-radius:34px;padding:34px;box-shadow:0 24px 50px rgba(0,0,0,.28)">
      <div class="clinic" data-in="0">Lumière Clinic</div>
      <div data-in="0.1" style="font-family:Serif;font-size:52px;color:var(--ink);line-height:1;margin-top:8px">Bjud in en vän</div>
      <div data-in="0.25" style="font-size:19px;color:#4a433c;margin-top:10px">Ni får båda <b>300 poäng</b> när din vän bokar sin första behandling.</div>
      <div style="display:flex;gap:12px;margin-top:22px;align-items:center">
        <div style="flex:1;border:2px dashed var(--gold);border-radius:18px;padding:14px 18px;font-weight:800;font-size:26px;letter-spacing:3px;color:var(--ink);height:62px">
          <span data-type="0.4,0.95">SARA300</span></div>
        <div class="btn" data-pop="1.0" style="font-size:18px;padding:16px 22px;border-radius:18px">Dela länk</div></div></div>""", 1.4

def dashboard():
    pts = [(0, 150), (60, 140), (120, 128), (180, 118), (240, 100), (300, 92), (360, 70), (420, 58), (480, 40), (540, 28)]
    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    kpi = lambda lbl, cnt, suf, sub, t0: f"""<div data-in="{t0}" style="flex:1;background:#fff;border-radius:20px;padding:18px 20px;border:1px solid var(--line)">
        <div style="font-size:13px;color:var(--muted);font-weight:600">{lbl}</div>
        <div style="font-family:Serif;font-size:46px;color:var(--ink);line-height:1.05;margin-top:6px"><span data-count="{cnt}" data-span="{t0+0.1},{t0+1.1}" data-suf="{suf}">0</span></div>
        <div data-in="{t0+1.0}" style="font-size:12px;color:#2f6b3a;font-weight:700;margin-top:2px">{sub}</div></div>"""
    return f"""<div style="width:900px;background:var(--ivory);border-radius:28px;overflow:hidden;box-shadow:0 30px 60px rgba(0,0,0,.3)">
      <div style="height:44px;background:#ece5dc;display:flex;align-items:center;gap:8px;padding:0 18px">
        <i style="width:12px;height:12px;border-radius:6px;background:#e0675d"></i><i style="width:12px;height:12px;border-radius:6px;background:#f0bd4f"></i>
        <i style="width:12px;height:12px;border-radius:6px;background:#62c454"></i>
        <span style="margin-left:14px;font-size:13px;color:#6d655d;font-weight:600">Retornela · Klinikpanel</span></div>
      <div style="padding:26px 30px 30px">
        <div style="display:flex;justify-content:space-between;align-items:flex-end">
          <div><div class="clinic">Lumière Clinic · demo</div><div style="font-family:Serif;font-size:44px;color:var(--ink)">Översikt</div></div>
          <div style="font-size:13px;color:var(--muted);font-weight:600">Senaste 6 mån</div></div>
        <div style="display:flex;gap:14px;margin-top:16px">
          {kpi('Återkommande kunder', 64, ' %', '▲ +18 p.e.', 0.05)}{kpi('Aktiva medlemmar', 312, '', '▲ +41 denna månad', 0.15)}{kpi('Genererat via appen', 48200, ' kr', '▲ från poäng & erbjudanden', 0.25)}</div>
        <div style="background:#fff;border-radius:20px;border:1px solid var(--line);margin-top:14px;padding:18px 20px">
          <div style="font-size:14px;font-weight:700;color:var(--ink)">Återbesök per månad</div>
          <svg width="840" height="180" viewBox="0 0 540 170" preserveAspectRatio="none" style="margin-top:8px;overflow:visible">
            <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#B58E57" stop-opacity=".30"/><stop offset="1" stop-color="#B58E57" stop-opacity="0"/></linearGradient></defs>
            <path d="{path} L540,170 L0,170 Z" fill="url(#g)" data-in="1.3" data-dy="0"/>
            <path id="ln" d="{path}" fill="none" stroke="#B58E57" stroke-width="3" pathLength="1" data-draw="0.35,1.6"/>
            <circle r="5" fill="#B58E57" data-follow="ln" data-span="0.35,1.6"/></svg>
          <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);font-weight:600;margin-top:4px">
            <span>jun</span><span>jul</span><span>aug</span><span>sep</span><span>okt</span><span>nov</span></div></div></div></div>""", 2.4

def logo(l):
    tag = "Lojalitetsappar för kliniker" if l == "sv" else "Loyalty apps for clinics"
    sub = "runt om i Europa" if l == "sv" else "across Europe"
    letters = "".join(f'<span data-in="{0.12 + 0.06*i:.2f}" data-dy="10" style="display:inline-block">{c}</span>' for i, c in enumerate("Retornela"))
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:56px 40px 48px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.3)">
      <div data-pop="0" style="width:84px;height:84px;margin:0 auto;border-radius:22px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;align-items:center;justify-content:center;
           color:#f3dcae;font-family:Serif;font-size:56px">R</div>
      <div style="font-family:Serif;font-size:118px;color:var(--ink);line-height:1;margin-top:18px;letter-spacing:1px">{letters}</div>
      <div style="height:2px;margin:22px auto;width:70px;background:var(--line);overflow:hidden"><i data-fill="0.65,1.0,100" style="display:block;height:2px;background:var(--gold);width:0"></i></div>
      <div data-in="0.85" style="font-size:26px;color:#3b352f;font-weight:600">{tag}</div>
      <div data-in="1.0" style="font-size:20px;color:var(--muted);font-weight:400;margin-top:6px">{sub}</div></div>""", 1.4

def cta(l):
    h = "Se hur din egen app kan se ut" if l == "sv" else "See what your own app could look like"
    dm = "Skriv till oss i DM" if l == "sv" else "Send us a DM"
    ic = lambda s, t0: f'<div data-pop="{t0}" style="width:54px;height:54px;border-radius:16px;background:var(--rose);display:flex;align-items:center;justify-content:center;font-size:26px;color:var(--ink);font-weight:700">{s}</div>'
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:40px;box-shadow:0 30px 60px rgba(0,0,0,.3)">
      <div class="clinic" data-in="0">Retornela</div>
      <div data-in="0.08" style="font-family:Serif;font-size:56px;color:var(--ink);line-height:1.05;margin-top:8px">{h}</div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:26px;height:54px">{ic('✉', 0.3)}<div style="font-size:30px;font-weight:700;color:var(--ink)" data-type="0.38,1.0">info@retornela.com</div></div>
      <div data-in="1.0" style="display:flex;align-items:center;gap:16px;margin-top:14px">{ic('↗', 1.0)}<div style="font-size:26px;font-weight:600;color:#4a433c">{dm}</div></div></div>""", 1.4

def impetus():
    side = ["Översikt", "Tidrapporter", "ÄTA", "Offerter", "Fakturor", "Inköp"]
    s = "".join(f'<div style="padding:12px 16px;border-radius:12px;margin-bottom:4px;font-size:15px;font-weight:{700 if x=="Offerter" else 500};'
                f'background:{"#F97316" if x=="Offerter" else "transparent"};color:{"#fff" if x=="Offerter" else "#cbd5e1"}">{x}</div>' for x in side)
    rows = [("Rivning & förberedelse", "12 h", 7800), ("Tätskikt & kakel", "26 m²", 23400), ("Material", "", 18650), ("Golvbrunn & rör", "4 h", 5200)]
    r = "".join(f'<div data-in="{0.3 + 0.2*i:.2f}" data-dx="30" data-dy="0" style="display:flex;padding:13px 0;border-bottom:1px solid #e2e8f0;font-size:16px;color:#0f172a">'
                f'<span style="flex:1;font-weight:600">{a}</span><span style="width:90px;color:#64748b">{b}</span>'
                f'<span style="width:120px;text-align:right;font-weight:700">{"−" if c < 0 else ""}{abs(c):,} kr</span></div>'.replace(",", " ")
                for i, (a, b, c) in enumerate(rows))
    kp = lambda a, cnt, suf, t0: (f'<div data-in="{t0}" style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:14px 16px;margin-bottom:12px">'
                                  f'<div style="font-size:13px;color:#64748b;font-weight:600">{a}</div><div style="font-size:30px;font-weight:800;color:#0f172a;margin-top:4px">'
                                  f'<span data-count="{cnt}" data-span="{t0+0.1},{t0+1.1}" data-suf="{suf}">0</span></div></div>')
    return f"""<div style="width:960px;height:600px;display:flex;border-radius:26px;overflow:hidden;box-shadow:0 30px 60px rgba(0,0,0,.3);background:#f8fafc">
      <div style="width:210px;background:#0f172a;padding:24px 14px;display:flex;flex-direction:column"><div style="color:#fff;font-weight:800;font-size:20px;margin:0 6px 22px">Allt på ett ställe</div>{s}<div data-in="1.3" style="margin-top:auto;display:flex;align-items:center;gap:8px;padding:11px 12px;border-radius:12px;background:#13213a;color:#e2e8f0;font-size:13px;font-weight:700"><span style="width:9px;height:9px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.18)"></span>Synkat med Fortnox</div></div>
      <div style="flex:1;padding:26px 26px;display:flex;gap:20px">
        <div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-radius:20px;padding:22px 24px">
          <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-size:13px;color:#64748b;font-weight:700">OFFERT #1042</div>
            <div data-swap="2.25" style="position:relative;width:86px;height:26px">
              <div style="position:absolute;right:0;font-size:12px;font-weight:700;padding:5px 10px;border-radius:10px;background:#ffedd5;color:#c2410c">Utkast</div>
              <div style="position:absolute;right:0;font-size:12px;font-weight:700;padding:5px 10px;border-radius:10px;background:#dcfce7;color:#15803d;opacity:0">Skickad</div></div></div>
          <div data-in="0.05" style="font-size:26px;font-weight:800;color:#0f172a;margin-top:6px">Badrumsrenovering</div>
          <div data-in="0.15" style="font-size:15px;color:#64748b;margin:2px 0 10px">Andersson · Kungsbacka</div>{r}
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px">
            <div data-in="1.05"><div style="font-size:13px;color:#64748b;font-weight:600">Totalt att betala</div><div style="font-size:32px;font-weight:800;color:#0f172a">
              <span data-count="55050" data-span="1.1,1.9" data-suf=" kr">0</span></div></div>
            <div data-swap="2.25" style="position:relative;width:170px;height:52px">
              <div style="position:absolute;inset:0;background:#F97316;color:#fff;font-weight:700;font-size:17px;border-radius:14px;display:flex;align-items:center;justify-content:center">Skicka offert</div>
              <div style="position:absolute;inset:0;background:#16a34a;color:#fff;font-weight:700;font-size:17px;border-radius:14px;display:flex;align-items:center;justify-content:center;opacity:0">Skickad ✓</div></div></div></div>
        <div style="width:220px">{kp('Öppna projekt',8,'',0.2)}{kp('Inrapporterad tid',1284,' h',0.32)}{kp('ÄTA att fakturera',3,' st',0.44)}{kp('Fakturerat i nov',312400,' kr',0.56)}</div></div></div>""", 2.8

def coupon():
    letters = "".join(f'<span data-in="{0.3 + 0.06*i:.2f}" data-dy="14" style="display:inline-block">{c}</span>' for i, c in enumerate("EARLY15"))
    return f"""<div style="width:760px;background:#0b0b0b;border-radius:34px;padding:40px 44px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.45);border:1px solid #2a2a2a">
      <div data-in="0" style="font-size:22px;letter-spacing:12px;color:#d6b46e;font-weight:700">BLACK FRIDAY</div>
      <div style="position:relative;margin:26px auto 0;border-radius:24px;padding:18px 10px">
        <svg style="position:absolute;inset:0;width:100%;height:100%;overflow:visible"><rect x="1.5" y="1.5" width="99%" height="97%" rx="24" fill="none" stroke="#d6b46e" stroke-width="3" pathLength="1" data-draw="0.1,0.7"/></svg>
        <div data-in="0.2" style="font-size:16px;letter-spacing:4px;color:#9b9b9b;font-weight:600">RABATTKOD</div>
        <div style="font-size:104px;font-weight:800;color:#fff;letter-spacing:4px;line-height:1.1">{letters}</div></div>
      <div data-in="0.85" style="font-size:30px;font-weight:700;color:#fff;margin-top:24px">15 % på allt</div>
      <div data-in="0.95" style="font-size:20px;color:#9b9b9b;margin-top:6px">monarcheu.com</div></div>""", 1.3

def excet():
    li = lambda s, t0: (f'<div style="display:flex;align-items:center;gap:16px;margin-top:14px"><div data-pop="{t0}" style="width:40px;height:40px;border-radius:20px;background:#FFE14D;color:#000;'
                        f'font-weight:900;font-size:26px;display:flex;align-items:center;justify-content:center;flex:none">✓</div>'
                        f'<div data-in="{t0+0.05}" data-dx="20" data-dy="0" style="font-size:30px;font-weight:800;color:#fff;text-align:left">{s}</div></div>')
    return f"""<div style="width:820px;background:#000;border-radius:34px;padding:36px 40px;box-shadow:0 30px 60px rgba(0,0,0,.5);border:3px solid #FFE14D">
      <div data-in="0" style="font-size:24px;font-weight:800;letter-spacing:6px;color:#FFE14D">GÄSTLISTA</div>
      <div data-in="0.08" style="font-size:64px;font-weight:900;color:#fff;line-height:1.05;margin-top:4px">5 DEC · EXCET</div>
      <div data-in="0.2" style="font-size:22px;font-weight:600;color:#bbb;margin:10px 0 6px">Goodiebag till de 50 första</div>
      {li('Chans på gratis MONARCH-keps',0.45)}{li('Jacquelle Beauty-läppglans',0.75)}{li('Första drinken bjuder vi på',1.05)}</div>""", 1.5

def _luc(name, size=26, color="#1F1B18", sw=2.2):
    svg = open(LUC + name + ".svg").read()
    svg = re.sub(r'width="\d+"', f'width="{size}"', svg, 1); svg = re.sub(r'height="\d+"', f'height="{size}"', svg, 1)
    return svg.replace('stroke="currentColor"', f'stroke="{color}"').replace('stroke-width="2"', f'stroke-width="{sw}"')

def aichat():
    # tabs light up exactly when each platform is named (seconds after the card appears)
    tabs = [("ChatGPT", 1.30), ("Gemini", 2.62), ("Claude", 3.28)]
    tb = "".join(f'<div data-swap="{t0}" style="position:relative;height:40px;width:{w}px">'
                 f'<div style="position:absolute;inset:0;border-radius:20px;border:1.5px solid var(--line);color:var(--muted);font-size:17px;font-weight:600;display:flex;align-items:center;justify-content:center">{n}</div>'
                 f'<div style="position:absolute;inset:0;border-radius:20px;background:var(--ink);color:#F7F2EC;font-size:17px;font-weight:700;display:flex;align-items:center;justify-content:center;opacity:0;box-shadow:0 6px 16px rgba(31,27,24,.25)">{n}</div></div>'
                 for (n, t0), w in zip(tabs, (128, 112, 106)))
    bar = lambda w_, t0: f'<div data-in="{t0}" data-dy="10" style="display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:18px;background:#fff;margin-top:10px;opacity:.55"><div style="width:30px;height:30px;border-radius:50%;background:var(--line)"></div><div style="height:12px;width:{w_}px;border-radius:6px;background:var(--line)"></div></div>'
    return f"""<div style="width:860px;height:500px;box-sizing:border-box;background:var(--ivory);border-radius:36px;padding:30px 32px 32px;box-shadow:0 30px 70px rgba(0,0,0,.35)">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div data-in="0" style="display:flex;align-items:center;gap:10px">{_luc("sparkles", 26, "#B58E57")}<span class="clinic" style="font-size:14px">AI-sök</span></div>
        <div style="display:flex;gap:8px">{tb}</div></div>
      <div style="display:flex;justify-content:flex-end;margin-top:22px;min-height:66px">
        <div data-in="0.1" style="max-width:560px;background:var(--ink);color:#F7F2EC;border-radius:24px 24px 6px 24px;padding:16px 22px;font-size:23px;font-weight:600;line-height:1.3">
          <span data-type="0.15,0.9">Bästa skönhetskliniken nära mig?</span></div></div>
      <div style="position:relative;margin-top:18px;min-height:300px">
        <div data-swap="1.25" style="position:relative;height:40px">
          <div style="position:absolute;left:0;top:0;display:flex;gap:8px;padding:12px 4px">
            <i data-pop="0.95" style="display:block;width:12px;height:12px;border-radius:50%;background:var(--gold)"></i><i data-pop="1.02" style="display:block;width:12px;height:12px;border-radius:50%;background:var(--gold);opacity:.7"></i><i data-pop="1.09" style="display:block;width:12px;height:12px;border-radius:50%;background:var(--gold);opacity:.45"></i></div>
          <div style="position:absolute;left:0;top:0;font-size:20px;color:#4a433c;font-weight:600;padding-top:8px;opacity:0">Kliniker som ofta rekommenderas:</div></div>
        <div data-in="1.45" data-dy="18" style="display:flex;align-items:center;gap:16px;padding:16px 18px;border-radius:20px;background:#fff;margin-top:12px;border:2px solid var(--gold);box-shadow:0 10px 26px rgba(181,142,87,.28)">
          <div style="width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;align-items:center;justify-content:center;color:#f3dcae;font-family:Serif;font-size:28px">1</div>
          <div style="flex:1"><div style="font-family:Serif;font-size:34px;color:var(--ink);line-height:1">Din klinik</div>
            <div style="font-size:15px;color:var(--muted);font-weight:600;margin-top:4px">Visas först i svaret</div></div>
          <div data-pop="1.95" style="display:flex;align-items:center;gap:6px;background:var(--rose);color:var(--ink);font-weight:700;font-size:15px;padding:9px 13px;border-radius:14px">{_luc("star", 16, "#B58E57", 2.4)}Rekommenderas</div></div>
        {bar(300, 1.62)}{bar(240, 1.76)}</div></div>""", 3.6

def cta_ai():
    ic = lambda n, t0: f'<div data-pop="{t0}" style="width:56px;height:56px;border-radius:16px;background:var(--rose);display:flex;align-items:center;justify-content:center">{_luc(n, 28)}</div>'
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:40px;box-shadow:0 30px 60px rgba(0,0,0,.3)">
      <div class="clinic" data-in="0">Retornela</div>
      <div data-in="0.08" style="font-family:Serif;font-size:56px;color:var(--ink);line-height:1.05;margin-top:8px;white-space:nowrap">Få din klinik att synas<br><i>i AI-svaren</i></div>
      <div data-in="1.15" style="display:flex;align-items:center;gap:16px;margin-top:26px">{ic("message-circle", 1.15)}<div style="font-size:28px;font-weight:600;color:#4a433c">Skriv till oss i DM</div></div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:14px;height:56px">{ic("mail", 2.55)}<div style="font-size:30px;font-weight:700;color:var(--ink)" data-type="2.62,3.45">info@retornela.com</div></div></div>""", 3.6

def logo_ai():
    letters = "".join(f'<span data-in="{0.12 + 0.06*i:.2f}" data-dy="10" style="display:inline-block">{c}</span>' for i, c in enumerate("Retornela"))
    return f"""<div style="width:760px;background:var(--ivory);border-radius:36px;padding:56px 40px 48px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.3)">
      <div data-pop="0" style="width:84px;height:84px;margin:0 auto;border-radius:22px;background:linear-gradient(135deg,#2a231e,#5a4634);display:flex;align-items:center;justify-content:center;
           color:#f3dcae;font-family:Serif;font-size:56px">R</div>
      <div style="font-family:Serif;font-size:118px;color:var(--ink);line-height:1;margin-top:18px;letter-spacing:1px">{letters}</div>
      <div style="height:2px;margin:22px auto;width:70px;background:var(--line);overflow:hidden"><i data-fill="0.65,1.0,100" style="display:block;height:2px;background:var(--gold);width:0"></i></div>
      <div data-in="0.8" style="font-size:26px;color:#3b352f;font-weight:600">Lojalitetsappar &amp; AI-synlighet</div>
      <div data-in="0.95" style="font-size:20px;color:var(--muted);font-weight:400;margin-top:6px">för kliniker runt om i Europa</div></div>""", 1.4

# name: (builder, output width px)
UI = {
    "ret_points_sv": (lambda: points("sv"), 440), "ret_points_en": (lambda: points("en"), 440),
    "ret_treat_sv": (lambda: treatments("sv"), 440), "ret_treat_en": (lambda: treatments("en"), 440),
    "ret_push_sv": (notif, 900), "ret_ref_sv": (referral, 820), "ret_dash_sv": (dashboard, 940),
    "ret_logo_sv": (lambda: logo("sv"), 720), "ret_logo_en": (lambda: logo("en"), 720),
    "ret_cta_sv": (lambda: cta("sv"), 780), "ret_cta_en": (lambda: cta("en"), 780),
    "imp_dash": (impetus, 980), "ret_aichat": (aichat, 990), "ret_cta_ai": (cta_ai, 880), "ret_logo_ai": (logo_ai, 720), "bf_coupon": (coupon, 860), "excet_card": (excet, 860),
}
ICONS = ["sparkles", "lightbulb", "gift", "martini", "shopping-bag", "flame", "globe", "trending-down", "timer", "message-circle",
         "folder", "mail", "file-text", "calendar", "receipt", "sheet", "smartphone", "message-square", "clipboard-list", "laptop", "cap"]

def render(pg, name, html, dur, width_px=None, css_w=None):
    html = html.replace("font-family:Serif", "font-family:'Serif'")
    d = OUT + name + "/"; os.makedirs(d, exist_ok=True)
    pg.set_content(f"<html><head><style>{BASE_CSS}</style></head><body><div id='root'>{html}</div>{RUNTIME}</body></html>")
    pg.wait_for_timeout(200)
    pg.evaluate("document.fonts.ready.then(()=>1)")
    root = pg.locator("#root")
    n = int(round(dur * FPS)) + 1
    for i in range(n):
        pg.evaluate(f"render({i / FPS})")
        root.screenshot(path=f"{d}{i:04d}.png", omit_background=True)
    return n

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=("/usr/bin/google-chrome" if __import__("os").path.exists("/usr/bin/google-chrome") else None), args=["--no-sandbox"])
    for name in ICONS:
        if ONLY and name not in ONLY and "icons" not in ONLY: continue
        svg = CAP_SVG if name == "cap" else open(LUC + name + ".svg").read()
        html, dur = icon_page(svg)
        pg = b.new_page(device_scale_factor=1, viewport={"width": 400, "height": 400})
        n = render(pg, "icon_" + name, html, dur); pg.close()
        print("icon", name, n)
    for name, (fn, wpx) in UI.items():
        if ONLY and name not in ONLY and "ui" not in ONLY: continue
        html, dur = fn(); html = html.replace("font-family:Serif", "font-family:'Serif'")
        m = b.new_page(device_scale_factor=1, viewport={"width": 1300, "height": 1100})
        m.set_content(f"<html><head><style>{BASE_CSS}</style></head><body><div id='root'>{html}</div></body></html>")
        css_w = m.locator("#root").bounding_box()["width"]; m.close()
        pg = b.new_page(device_scale_factor=wpx / css_w, viewport={"width": 1300, "height": 1100})
        n = render(pg, name, html, dur); pg.close()
        print("ui", name, n)
    b.close()
