"""Find each HCP company's website + contact e-mail, free, via Common Crawl.

For every company in hcp-booking-companies.csv we guess likely domains from the
company name, look them up in the Common Crawl archive and scan the archived
pages (scan.py). A domain counts as CONFIRMED when the site's HCP token equals
the company's HCP company_id: then we know for certain it is the same business.

Usage: python3 leads/find_domains.py IN.csv OUT.csv [--since 2025] [--limit N]
Resumable: rows already in OUT.csv are skipped.
"""
import csv, os, re, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan

DROP = {"llc", "inc", "co", "corp", "corporation", "company", "ltd", "the", "l", "c", "pllc", "lp"}


def candidates(name):
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower().replace("&", " and ")) if w]
    core = [w for w in words if w not in DROP]
    no_and = [w for w in core if w != "and"]
    c = []
    for ws in (no_and, core, words):
        if ws:
            c += ["".join(ws) + ".com", "-".join(ws) + ".com"]
    out = []
    for d in c:
        if d not in out and len(d) <= 67:
            out.append(d)
    return out[:4]


def work(index, row):
    best = None
    for d in candidates(row["company_name"]):
        try:
            res = scan.check(index, d)
        except Exception as e:
            continue
        if res["hcp_company_id"] == row["company_id"]:
            res["match"] = "confirmed"; best = res; break
        if res["uses_hcp"] == "yes" and not best:
            res["match"] = "hcp_site_other_id"; best = res
    out = dict(row)
    if best:
        out.update(website=best["domain"], match=best["match"], emails=best["emails"],
                   phones=best["phones"], evidence=best["evidence"])
    else:
        out.update(website="", match="not_found", emails="", phones="", evidence="")
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2024"
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    rows = [r for r in csv.DictReader(open(src)) if r["last_seen"] >= since]
    rows.sort(key=lambda r: r["last_seen"], reverse=True)
    done = set()
    if os.path.exists(dst):
        done = {r["company_id"] for r in csv.DictReader(open(dst))}
    todo = [r for r in rows if r["company_id"] not in done][:limit]
    print(len(todo), "companies to process", file=sys.stderr, flush=True)
    index = scan.Index("CC-MAIN-2026-43")
    fields = list(rows[0]) + ["website", "match", "emails", "phones", "evidence"]
    new = not os.path.exists(dst)
    with open(dst, "a", newline="") as fh, ThreadPoolExecutor(int(os.environ.get("THREADS", "10"))) as ex:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for i, out in enumerate(ex.map(lambda r: work(index, r), todo), 1):
            w.writerow(out); fh.flush()
            if i % 25 == 0:
                print(i, "done", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
