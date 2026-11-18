# Williams videostil – Iman Gadzhi-stil (husstil)

Gäller varje video om William inte säger annat. Referens: `configs/exempel/retornela_ai_IMG_7330.json` (senaste och mest Iman-lika).

## Alltid
- **Format:** 1080×1920, 30 fps, H.264 crf 19, AAC 192k, ljud normaliserat till **−14 LUFS**.
- **Spegelvänd** (`"mirror": true`). William vill ha det så, även om en logga/text i bild blir bakvänd (påpeka det i så fall).
- **Ingen bakgrundsmusik.** Bara röst och ljudeffekter.
- **Klipp bort all tystnad och alla felsägningar.** Börjar han om en mening, behåll den sista tagningen. Klipp tätt (ca 0,03–0,05 s marginal) och verifiera klippet genom att transkribera ihopklippt ljud.
- **Rensat ljud:** `voice_fx` i exempel-configen (RNNoise + afftdn + EQ + deesser + kompressor).
- **iPhone-HDR (HLG)** tonemappas automatiskt; vanlig SDR och liggande video fungerar också (motorn skär ut 9:16).

## Typsnitt
- **Undertexter:** Montserrat, gemener, 2–4 ord per grupp. Orden går från tunn (Light) till fet (Bold) medan han pratar.
- **Nyckelord:** Instrument Serif *Italic* (sätt `~` före ordet i `caps`, t.ex. `~lösningen`). Använd 2–4 per video, på de viktigaste orden.
- **Hook-titel** (första 2–3 s): rad 1 Montserrat Light, rad 2 Instrument Serif Italic (`"serif"`). Gemener, en fråga eller ett löfte, max 3–4 ord per rad.
- **Text bakom personen:** Montserrat ExtraBold, ett stort ord (t.ex. "AI"), en gång per video på nyckelmomentet.
- **Grafik/kort:** Montserrat + Instrument Serif. Typsnitten bäddas in som data-URL i `seqs.py`; kontrollera att de faktiskt laddar (inte Arial/Times).

## Effekter (fullt Iman-läge = standard)
- **Klipp:** whip-klipp med rörelseoskärpa och kromatisk aberration mellan segmenten, hårda inzoomningar (Z1→Z2) som jump cuts och mikro-inzoomningar i långa segment. Långsam push-in hela tiden.
- **Accentord** (`*ord*` i `caps`, 2–3 per video): svartvit blixt + boom + skak.
- **Ljusläckor och blixt:** på CTA- och slutsegmentet (`leaks`, `flash`). Riser in mot CTA (`risers`).
- **Struktur:** filmkorn och vinjett. Titeln har mörk gradient upptill.
- **Ljud:** whoosh på klipp och kort, pop på brickor, boom på accenter, slutare på svartvitt, tick på skrivande text och uppräkning. Ingen musik.

### Andra lägen (bara när William ber om det)
- **Clean** (`"clean": true`): lugnare effekter, Lucide-linjeikoner i glas-brickor i stället för emoji, och levande dashboards.
- **TikTok** (`"cap_style": "tiktok"`): versaler med gult aktivt ord, snap-zoomar och cutout-sticker. Användes för Excet. Färre zoomar: `"no_zoom": true` + `"cutout": true`.

## Grafik
- **Rörliga HTML-kort** (`seqs.py`): renderas bildruta för bildruta med `render(t)`.
  - Byggstenar: `data-in`, `data-type`, `data-count`, `data-pop`, `data-swap`, `data-fill`, `data-draw`.
  - Synka händelser i kortet med exakt när han säger orden. Räkna ut tiden relativt kortets start.
- **Namnbrickor med logga** (`pills.py`): poppar upp bredvid huvudet när ett namn sägs. Loggor ligger i `icons/logos/`.
  - Tredjepartsloggor används bara om William själv har gett dem.
- **Retornela-palett:** ivory `#F7F2EC`, ink `#1F1B18`, guld `#B58E57`, rosé `#EAD8CF`, linje `#E6DED4`, dämpad `#8B8178`.
- **Sanning först:** visa bara funktioner, priser och siffror som bolaget faktiskt har. Exempeldata märks som demo (t.ex. "Din klinik").
  - Hitta aldrig på resultat som "6 h sparad/vecka".
  - Osäker? Fråga William eller håll kortet generellt.

## Layout (1080×1920)
- **Ansiktet ska alltid synas.** Kort hamnar i nedre halvan: centrum y≈1400–1500, bredd ≤ 990 px.
- **Undertexter:** y=1250 normalt. När ett kort syns: y≈1000–1060, över bröstet, inte över kortet. Aldrig på ljus bordsyta utan stark skugga.
- **Säkra zoner:** de nedersta ~250 px och översta ~150 px täcks av TikTok/IG-gränssnittet.
- **Namnbrickor:** höger kolumn x≈895, med 125 px mellanrum. Får inte krocka med "bakom"-texten eller huvudet.
- **Kontroll:** kolla alltid en storyboard innan slutrendering.

## Leveranser
- **Huvudversion:** `NAMN_iman.mp4`.
- **Bara på begäran:** kortversion (≤ 30 s), hook B (ny öppning), varianter.
- **Skicka filen** med en mening om vad som gjorts, och flagga risker (t.ex. bakvänd logga, ord som kan vara feltranskriberade, påståenden som bör dubbelkollas).
