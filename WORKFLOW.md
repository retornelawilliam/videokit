# Arbetsflöde – från uppladdad video till färdig redigering

William ska kunna följa varje steg. Skapa en uppgiftslista med de sju stegen nedan och bocka av dem. Visa resultatet vid varje 👁-punkt.

## 0. Starta kitet (en gång per chatt)
```bash
[ -f /home/claude/videokit/setup.sh ] || git clone https://github.com/retornelawilliam/videokit.git /home/claude/videokit
bash /home/claude/videokit/setup.sh     # ska sluta med "VIDEOKIT REDO"
```
Om klonen nekas: kör verktyget `add_repo` (owner `retornelawilliam`, repo `videokit`) och klona igen med kommandot verktyget ger.

## 1. Förbered
```bash
/home/claude/scripts/prep.sh /mnt/user-data/uploads/IMG_XXXX.mov sv
```
Steget ger:
- jobbmappen `/home/claude/jobs/IMG_XXXX/`
- transkribering med tider
- `energy.txt` (ljudnivå per 50 ms)
- `stills.jpg` (var personen sitter, spegelvänt)

Titta på `stills.jpg` med Read för att bestämma bildutsnitt (x/y för huvudet).

## 2. Hitta exakta ord och klipp-punkter
- Normaliserat ljud ger bäst resultat för tysta talare:
  ```bash
  python3 /home/claude/scripts/tr_range.py JOB/IMG_XXXX_norm.wav /home/claude/models/sherpa-onnx-whisper-turbo 0.5:2.4 0.5:3.1 …
  ```
- **Ordtider:** transkribera prefix (start:slut med växande slut). Då syns var varje ord landar.
- **Felsägningar:** klipp bort en omtagning (t.ex. "som chat– … som ChatGPT"). Bekräfta klippet genom att klippa ihop ljudet med numpy och transkribera det.
- **Rättning:** Whisper hör fel på namn och mejladresser. Rätta efter sammanhang och fråga William om något är osäkert.

👁 **Skicka till William** (SendUserMessage):
- texten som den blir
- vad som klipps bort (tystnad och omtagningar)
- planen: hook-titel, nyckelord, accenter, kort och var de dyker upp

Kör vidare utan att vänta, om han inte har bett om att få godkänna först.

## 3. Grafik
- **Återanvänd** kort från `icons/seq/` om de passar (se BRANDS.md).
- **Nytt kort:** lägg en funktion i `scripts/seqs.py` som returnerar `(html, längd_s)`, registrera den i UI-listan och kör:
  ```bash
  python3 /home/claude/scripts/seqs.py mitt_kort
  ```
  Synka händelser i kortet med ordens tider. Räkna sekunder från kortets start, som är gruppens start minus 0,03 s.
- **Namnbrickor med logga:** lägg loggan i `icons/logos/<namn>.png` (vit bakgrund, kvadrat), lägg till namnet i `pills.py` och kör den.
- **Kontrollera** sista bildrutan av varje kort (komponera på grå bakgrund och titta med Read). Typsnitten ska vara Montserrat och Instrument Serif.

## 4. Config
Kopiera `configs/exempel/retornela_ai_IMG_7330.json` till jobbmappen och ändra. Nycklar:

| Nyckel | Betydelse |
|---|---|
| `src`, `out`, `work`, `wav16k` | sökvägar (work = `JOB/w`) |
| `mirror` | `true` |
| `framings` | `{"Z1": [zoom, cx, cy], "Z2": [...]}`. cx/cy = utsnittets mitt (0–1) i den spegelvända källan. Tumregel: Z1 = [1.3, huvud_x, huvud_y+0.154], Z2 = [1.6, huvud_x, huvud_y+0.125] |
| `anchor` | zoomcentrum i bild, oftast `[0.5, 0.34]` |
| `cap_y`, `cap_size` | undertexternas höjd (1250) och storlek (84) |
| `title` | `{"lines": [["light","…"],["serif","…"]], "y": 290, "size": 86, "end": sek}` |
| `segs[]` | `a`/`b` (källtid in/ut), `frame` (Z1/Z2), `caps` ("grupp \| grupp", `*accent*`, `~serif`), `starts` (källtid per grupp), `sp` (talstart/slut), `cut` (`whip` standard, `hard`, `rewind`), `cap_y`, `bw`, `drama` |
| `behinds[]` | `{"seg": i, "text": "AI", "until_seg": j, "w": 640, "overlap": 0.4}` |
| `leaks`, `flash`, `risers` | listor med segmentindex |
| `overlays[]` | `{"seg", "group" (text utan * ~), "kind": "seq"\|"chip"\|(tomt = bild/sticker), "dir"/"img", "size", "x", "y", "to_seg_end"\|"t1_seg"\|"until_group", "delay", "ticks": [a,b], "pops": [...]}` |
| `voice_fx` | rensningskedjan för ljudet (kopiera från exemplet) |
| `clean`, `cap_style: "tiktok"`, `no_zoom`, `cutout` | alternativa lägen |

## 5. Storyboard före slutrendering
```bash
cd JOB
python3 /home/claude/scripts/iman5.py cfg.json --stage ass
python3 /home/claude/scripts/iman5.py cfg.json --stage audio
python3 /home/claude/scripts/iman5.py cfg.json --stage video --preview 0.5,2.9,4.3,5.3,6.6,8.4,10.7,13.0,14.4
python3 /home/claude/scripts/storyboard.py frames w w/storyboard.jpg "0.5s hook,2.9s accent,…"
```
- `ass`-steget skriver ut whip-tider, kortens tider, accenter och "behind".
- Förhandsbilderna saknar undertexter.

Kolla:
- att ansiktet syns
- att inget kort krockar med undertext, titel eller bricka
- att inget hamnar i säkra zoner

👁 **Skicka** `storyboard.jpg` till William med en mening om vad den visar.

## 6. Slutrendering (i bakgrunden – förgrundskommandon har 10 minuters gräns)
```bash
cat > JOB/q.sh <<'EOF'
cd JOB && python3 /home/claude/scripts/iman5.py cfg.json --stage video > w/video.log 2>&1; echo DONE >> q.log
EOF
nohup bash JOB/q.sh >/dev/null 2>&1 &
# vänta: for i in $(seq 1 57); do [ -f JOB/q.log ] && break; sleep 10; done
```
15 s video ≈ 4 min. Text-bakom tar längre tid.

## 7. Kontroll och leverans
```bash
/home/claude/scripts/check.sh JOB/IMG_XXXX_iman.mp4          # −14 LUFS, längd
python3 /home/claude/scripts/storyboard.py video JOB/IMG_XXXX_iman.mp4 JOB/final_sheet.jpg 0.5,2.9,4.3,…
```
- Titta på `final_sheet.jpg` (nu med undertexter). Rätta det som är fel och rendera om.
- 👁 **Skicka videon** med SendUserFile och en kort sammanfattning: vad som klipptes, effekter, grafik och eventuella risker.

## Kända fallgropar
- Typsnitt i Chrome-grafik måste vara inbäddade. `font-family:Serif` utan citattecken blir systemets serif, så `seqs.py` byter automatiskt.
- Kortets höjd får inte ändras under animationen (sätt fast `height`), annars hoppar det.
- Text bakom personen kräver att huvudet syns och att `overlap` är 0.3–0.45.
- Stoppas miljön mitt i en rendering: kolla att mp4-filen går att läsa (moov atom) och rendera om.
- Hugging Face är blockerat. Allt laddas från GitHub.
