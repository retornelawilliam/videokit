# Videokit – Williams Iman Gadzhi-redigering

| Fil | Vad |
|---|---|
| `PROJECT_PROMPT.md` | Instruktionerna att klistra in i Claude-projektet |
| `STIL.md` | Husstilen: typsnitt, effekter, layout, regler |
| `BRANDS.md` | Fakta om Retornela, Impetus, MONARCH och Excet för text och grafik |
| `WORKFLOW.md` | Steg för steg med kommandon, configreferens och fallgropar |
| `setup.sh` | Installerar allt i en ny session (modeller laddas från GitHub) |
| `scripts/` | `prep.sh` (allt grovjobb), `align.py` (ordtider), `draft.py` (config + plan), `rattning.json` (hörfel → rätt stavning), `iman5.py` (motorn), `check.py` (kontroll), `seqs.py` (rörliga HTML-kort), `pills.py` (namnbrickor), `storyboard.py`, `transcribe.py`, `tr_range.py` |
| `fonts/` | Montserrat och Instrument Serif |
| `icons/` | `seq/` färdiga rörliga kort, `logos/`, `pills/`, `lucide/` linjeikoner, `gen/` statiska kort, emoji-PNG |
| `configs/exempel/` | Configs från tidigare videor att utgå från |

Snabbstart: `bash setup.sh`, sedan `scripts/prep.sh <video>` (ger `plan.txt` + `cfg.json`-utkast), sedan WORKFLOW.md.
