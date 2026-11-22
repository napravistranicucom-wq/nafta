"""Merge manually found domains (CSV: company_id,domain[,city_state]) into hcp-users.csv.

Each domain is checked with scan.py against the Common Crawl archive:
confirmed = HCP token on the site equals the company_id; hcp_site_other_id = other
HCP token; found_manual = found by search, no HCP trace in the archive.
Usage: python3 leads/merge_manual.py found0.csv [found1.csv ...]
"""
import csv, os, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scan, export_instantly

def main():
    found = {}
    for p in sys.argv[1:]:
        for r in csv.DictReader(open(p)):
            d = (r.get('domain') or '').strip().lower().removeprefix('https://').removeprefix('http://').removeprefix('www.').split('/')[0]
            if d and '.' in d:
                found[r['company_id']] = d
    path = os.path.join(HERE, 'hcp-users.csv')
    rows = list(csv.DictReader(open(path))); fields = list(rows[0])
    index = scan.Index('CC-MAIN-2026-43')
    def chk(item):
        cid, d = item
        try:
            return cid, d, scan.check(index, d)
        except Exception as e:
            return cid, d, None
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(chk, found.items()))
    by = {r['company_id']: r for r in rows}
    stats = {}
    for cid, d, rs in res:
        r = by.get(cid)
        if not r or r['match'] in ('confirmed', 'hcp_site_other_id'):
            continue
        m = 'found_manual'
        if rs and rs['hcp_company_id'] == cid: m = 'confirmed'
        elif rs and rs['uses_hcp'] == 'yes': m = 'hcp_site_other_id'
        r.update(website=d, match=m, emails=(rs or {}).get('emails', ''), phones=(rs or {}).get('phones', ''),
                 evidence=(rs or {}).get('evidence', ''))
        stats[m] = stats.get(m, 0) + 1
        stats['with_email'] = stats.get('with_email', 0) + bool(r['emails'])
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(len(found), 'domains;', stats)
    export_instantly.main()

if __name__ == '__main__':
    main()
