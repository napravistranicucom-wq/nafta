# nafta

## Core lab param extraction (CSV/Excel)

Ako imaš PDF-ove/slike lab izvještaja (permeability, porosity, saturations, density…), možeš ih skinuti lokalno u folder i pokrenuti skriptu koja izvuče parametre i složi ih u tablicu.

### (Opcionalno) Skini dokumente sa core report URL-a

Ako imaš URL tipa `https://my.usgs.gov/crcwc/core/report/15887`:

```bash
python3 download_core_report.py --url https://my.usgs.gov/crcwc/core/report/15887 --out ./docs --same-host
```

Ako je iza logina, proslijedi cookie (iz browsera):

```bash
python3 download_core_report.py --url https://my.usgs.gov/crcwc/core/report/15887 --out ./docs --cookie "JSESSIONID=..." --same-host
```

### Instalacija

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# OCR (opcionalno ali često potrebno za skenirane PDF-ove)
sudo apt-get update && sudo apt-get install -y tesseract-ocr
```

### Pokretanje

Stavi dokumente u npr. `./docs/` pa:

```bash
python extract_core_params.py --input ./docs --out-long core_params_long.csv --out-wide core_params_wide.xlsx
```

- `core_params_long.csv`: “long” format (svaki pronađeni parametar je jedan red)
- `core_params_wide.xlsx`: “wide” format (1 red po fajlu + kolone za parametre) + dodatni sheet `long`

### Koje parametre trenutno traži

Trenutno hvata:
- Permeability (perm/k/air/gas perm)
- Porosity
- Grain density / Bulk density
- Sw / So / Sg
- Net confining pressure

Ako mi kažeš tačno kako su ti nazivi napisani u tim PDF-ovima (ili zalijepi 20–30 linija teksta iz izvještaja), mogu proširiti regexe da hvata i tvoje specifične kolone/parametre.
