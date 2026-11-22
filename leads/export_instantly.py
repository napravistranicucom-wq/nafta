"""Build instantly-import.csv from hcp-users.csv (one row per company with an e-mail)."""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
KW = [('hvac','HVAC'),('heating','HVAC'),('air','HVAC'),('cooling','HVAC'),('mechanical','HVAC'),('plumb','plumbing'),('drain','plumbing'),('rooter','plumbing'),('electric','electrical'),('clean','cleaning'),('carpet','cleaning'),('maid','cleaning'),('appliance','appliance repair'),('garage','garage door'),('door','garage door'),('junk','junk removal'),('roof','roofing'),('window','window cleaning'),('handyman','handyman'),('paint','painting'),('pest','pest control'),('lawn','lawn care'),('landscap','landscaping'),('pool','pool service'),('pressure','pressure washing'),('septic','septic'),('solar','solar'),('tree','tree service')]
GENERIC = ('info@','office@','contact@','hello@','service@','support@','sales@','admin@')

def industry(name):
    n = name.lower()
    return next((v for k, v in KW if k in n), 'home services')

def main():
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, 'hcp-users.csv'))) if r['emails']]
    seen = set(); out = []
    for r in sorted(rows, key=lambda r: r['last_seen'], reverse=True):
        em = [e for e in r['emails'].split(';') if e]
        dom = r['website']
        em.sort(key=lambda e: (not e.endswith('@' + dom), e.startswith(GENERIC)))
        e = next((x for x in em if x not in seen), None)
        if not e:
            continue
        seen.add(e)
        out.append([e, r['company_name'], dom, industry(r['company_name']), r['phones'].split(';')[0], r['match'], r['last_seen']])
    with open(os.path.join(HERE, 'instantly-import.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['email','company_name','website','industry','phone','hcp_match','last_seen_on_hcp'])
        w.writerows(out)
    print(len(out), 'rows in instantly-import.csv')

if __name__ == '__main__':
    main()
