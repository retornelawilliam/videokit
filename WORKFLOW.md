# Arbetsflöde – från uppladdad video till färdig redigering

William ska kunna följa varje steg. Skapa en uppgiftslista med de sju stegen nedan och bocka av dem. Visa resultatet vid varje 👁-punkt.

## 0. Starta kitet (en gång per chatt)
Prompten för Claude-projektet ligger i `PROJECT_PROMPT.md`. Ändras arbetssättet ska både den och den här filen uppdateras.
```bash
[ -f /home/claude/videokit/setup.sh ] || git clone https://github.com/retornelawilliam/videokit.git /home/claude/videokit
bash /home/claude/videokit/setup.sh     # ska sluta med "VIDEOKIT REDO"
```
Om klonen nekas: kör verktyget `add_repo` (owner `retornelawilliam`, repo `videokit`) och klona igen med kommandot verktyget ger.

## 1. Förbered (ett kommando, ~1 min per minut video)
```bash
/home/claude/scripts/prep.sh /mnt/user-data/uploads/IMG_XXXX.mov sv
```
Steget gör allt grovjobb och lägger det i `/home/claude/jobs/IMG_XXXX/`:
| Fil | Vad |
|---|---|
| `plan.txt` | texten, vad som klipps bort (omtagningar, utfyllnad, pauser), segmenten, flaggor |
| `cfg.json` | färdigt config-utkast: klipp, Z1/Z2, undertextgrupper med exakta ordtider (`wt`) |
| `words.txt` | varje ord med start/slut, `?` = osäkert ord, `!!` = tal som Whisper inte skrev ut |
| `stills.jpg` | spegelvända stillbilder (kolla att utsnittet/ansiktet stämmer) |

Bakom kulisserna: Whisper transkriberar → `align.py` tvångsjusterar texten mot ljudet (Omnilingual CTC, 20 ms) → `draft.py` klipper, grupperar, rättstavar (`rattning.json`) och hittar ansiktet.

## 2. Text och klipp
- Läs `plan.txt`. Kontrollera **omtagningar** (sista tagningen behålls) och **tal utan text** (Whisper tvättar bort felsägningar – de klipps bort, men kolla att inget viktigt försvinner).
- **Rättstava** direkt i `caps` i `cfg.json`. Behåll samma antal ord per segment, annars stämmer inte `wt` (motorn varnar och gissar tider).
  - Slå ihop/dela ord → ändra `wt` också (ett starttal per ord, källtid; se `words.txt`).
- Nytt återkommande hörfel? Lägg in det i `scripts/rattning.json` (lärande).
- Felaktigt klipp? Ändra `a`/`b` (källtid) eller kör om med annan paus: `python3 scripts/draft.py JOB --pause 0.35 --force`.
- Falsk start eller sidospår som inte upprepas ordagrant (t.ex. "nummer tre" utan "två")? `--drop 1.0-3.5,26.2-27.0` tar bort orden i de tidsintervallen.
- Whisper fel på många ord? Rätta texten per chunk i `NAME_segs.json` (slå ihop chunkar som delar ett ord), kör `align.py` igen och sedan `draft.py --force`.
- Stickprov vid tvekan: `python3 scripts/tr_range.py JOB/IMG_XXXX_norm.wav /home/claude/models/sherpa-onnx-whisper-turbo 3.1:4.2`

👁 **Skicka till William** (SendUserMessage):
- texten som den blir
- vad som klipps bort (tystnad och omtagningar)
- planen: hook-titel (+ 2 alternativ), nyckelord, accenter, bakom-ordet, kort och var de dyker upp (tidsstämplar)

Kör vidare utan att vänta, om han inte har bett om att få godkänna först.

## 3. Grafik
- **Återanvänd** kort från `icons/seq/` om de passar (se BRANDS.md).
- **Nytt kort:** lägg en funktion i `scripts/seqs.py` som returnerar `(html, längd_s)`, registrera den i `UI` och kör:
  ```bash
  python3 /home/claude/scripts/seqs.py mitt_kort
  ```
  Synka händelser i kortet med ordens tider i `words.txt`. Räkna sekunder från kortets start (= gruppens första ord − 0,03 s).
  Skriptet varnar om typsnitten inte laddar ("VARNING … typsnitt").
- **Namnbrickor med logga:** lägg loggan i `icons/logos/<namn>.png` (vit bakgrund, kvadrat), lägg till namnet i `pills.py` och kör den.
- **Kontrollera** sista bildrutan av varje nytt kort (komponera på grå bakgrund och titta med Read).

## 4. Config – det som är kvar efter utkastet
| Nyckel | Gör så här |
|---|---|
| `title` | hook-titel: `{"lines": [["light","…"],["serif","…"]], "y": 290, "size": 86, "end": sek}` |
| `caps` | `~ord` = serif kursiv (2–4 per video), `*ord*` = accent med svartvit blixt (2–3). Grupper skiljs med `\|` – flytta gärna, `wt` följer orden |
| `behinds[]` | `{"seg": i, "text": "AI", "until_seg": j, "w": 640, "overlap": 0.4}` |
| `overlays[]` | `{"seg", "group" (gruppens text utan * ~), "kind": "seq"\|"chip"\|(tomt = bild/bricka), "dir"/"img", "size", "x", "y", "to_seg_end"\|"t1_seg"\|"until_group", "delay", "ticks": [a,b], "pops": [...]}` |
| `cap_y` per segment | 1000–1060 när ett kort syns i nedre halvan, annars 1250 (standard) |
| `leaks`, `flash`, `risers` | segmentindex; utkastet sätter ljusläckor + riser på slutet |
| `framings` | utkastet räknar från ansiktet: Z1 = [1.3, x, y+0.154], Z2 = [1.6, x, y+0.125]. Saknas ansikte → sätt för hand |
| `cut` | `whip` (standard), `hard` (mitt i mening, utkastet sätter), `rewind` |
| `clean`, `cap_style: "tiktok"`, `no_zoom`, `cutout` | alternativa lägen |

Övriga nycklar (`src`, `out`, `work`, `wav16k`, `sp`, `wt`, `voice_fx`) är redan ifyllda. `starts` behövs inte när `wt` finns.

## 5. Storyboard före slutrendering
```bash
cd JOB
python3 /home/claude/scripts/iman5.py cfg.json --stage ass
python3 /home/claude/scripts/check.py cfg.json --plan          # säkra zoner + krockar, innan något renderas
python3 /home/claude/scripts/iman5.py cfg.json --stage audio
python3 /home/claude/scripts/iman5.py cfg.json --stage video --preview auto   # -> w/storyboard.jpg
```
- `--preview auto` väljer nyckelmomenten själv (hook, accenter, varje kort, bakom-text, varje segment, slut), bränner in undertexterna och gör `w/storyboard.jpg` med etiketter.
- Egna tider går fortfarande: `--preview 0.5,2.9,4.3`.
- Bakom-text gör förhandsvisningen långsammare (varje bildruta i fönstret räknas).

Kolla att ansiktet syns, att inget krockar och att texten är rätt. Rätta och kör om.

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
python3 /home/claude/scripts/check.py JOB/cfg.json        # upplösning, fps, längd, −14 LUFS, true peak, zoner, krockar, all text
python3 /home/claude/scripts/storyboard.py video JOB/IMG_XXXX_iman.mp4 JOB/final_sheet.jpg 0.5,2.9,4.3,…
```
- `check.py` ska sluta med "ALLT OK". Läs texten den skriver ut (namn, märken, adresser).
- Titta på `final_sheet.jpg`. Rätta det som är fel och rendera om.
- 👁 **Skicka videon** med SendUserFile och en kort sammanfattning: vad som klipptes, effekter, grafik och eventuella risker.
- Lägg till ett förslag på posttext: 1–2 meningar på videons språk och 3–5 relevanta hashtags.

## Kända fallgropar
- Typsnitt i Chrome-grafik måste vara inbäddade (data-URL). `seqs.py` och `assets.py` gör det och varnar annars. Kort renderade före nov 2026 kunde ha fått Times/Arial – alla är omrenderade.
- Kortets höjd får inte ändras under animationen (sätt fast `height`), annars hoppar det.
- Text bakom personen kräver att huvudet syns och att `overlap` är 0.3–0.45.
- CTC-modellen blir instabil på väldigt korta ljudbitar – `align.py` kör därför hela klippet på en gång (upp till 38 s, längre i 30-sekundersfönster).
- Stoppas miljön mitt i en rendering: kolla att mp4-filen går att läsa (moov atom) och rendera om.
- Hugging Face är blockerat. Allt laddas från GitHub.
