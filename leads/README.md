# Leadovi: firme koje koriste Housecall Pro

Sve je besplatno i radi preko arhive interneta **Common Crawl** (`data.commoncrawl.org`). Ne treba ni Google ni plaćeni alat.

## Kako radi
1. **`cc_hcp.py`** pronalazi sve firme koje imaju Housecall Pro online booking.
   - Svaka HCP firma s bookingom ima stranicu `book.housecallpro.com/book/<Ime-Firme>/<company_id>`.
   - Skripta čita Common Crawlov indeks URL-ova za svaki mjesečni snimak od 2024. i skuplja svaku takvu stranicu.
   - Izlaz: `hcp-booking-companies.csv` (ID firme, ime, booking link, kada je viđena).
2. **`scan.py`** za zadanu web stranicu provjerava ima li ugrađen HCP kod.
   - Tragove traži u `fingerprints.json`, a oni su potvrđeni iz HCP-ove skripte `online-booking.housecallpro.com/script.js`.
   - Izvlači i e-mailove (samo na domeni firme ili Gmail/Yahoo itd.) i telefone.
3. **`find_domains.py`** za svaku firmu iz koraka 1 pogađa web adresu iz imena, a `scan.py` je provjerava.
   - **`confirmed`**: HCP token na stranici je isti kao ID firme. Znamo 100 % da je to ta firma.
   - **`hcp_site_other_id`**: stranica sigurno koristi HCP, ali pod drugim ID-om (npr. nova booking stranica).
   - **`not_found`**: domena nije pogođena. Ove firme treba obogatiti drugim alatom (Outscraper/Apollo, pretraga po imenu).
   - Izlaz: `hcp-users.csv`. Skripta se može prekinuti i nastaviti, jer preskače već obrađene firme.

## Pokretanje
```bash
python3 leads/cc_hcp.py leads/hcp-booking-companies.csv --from-year 2024
python3 leads/find_domains.py leads/hcp-booking-companies.csv leads/hcp-users.csv --since 2024
python3 leads/scan.py domains.txt rezultat.csv          # provjera vlastite liste domena
```
Mreža mora dopuštati `data.commoncrawl.org`.

## Za Instantly
Za kampanju uzmi redove gdje `emails` nije prazan. `confirmed` i `hcp_site_other_id` su sigurni korisnici HCP-a.
Prije slanja provjeri adrese u NeverBounce ili ZeroBounce.
