"""Find businesses that use Housecall Pro online booking, via Common Crawl.

Common Crawl archives public web pages monthly. Every HCP customer with online
booking gets a page at book.housecallpro.com/book/<Company-Name>/<company_id>
(or /lead-form/...). We read Common Crawl's URL index directly from
data.commoncrawl.org (the cluster.idx + range requests that the index server
uses internally) and collect every such company.

Usage: python3 leads/cc_hcp.py OUT.csv [--from-year 2024]
"""
import csv, json, re, sys, urllib.parse, urllib.request, zlib
from collections import defaultdict

BASE = "https://data.commoncrawl.org"
PREFIXES = ["com,housecallpro,book)/", "com,housecallpro)/book"]
PATH_RE = re.compile(r"/(book|lead-form)/([^/?#]+)/([0-9a-f]{32})", re.I)


def get(url, rng=None, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": "hcp-research/1.0"})
    if rng:
        req.add_header("Range", "bytes=%d-%d" % rng)
    return urllib.request.urlopen(req, timeout=timeout)


def crawls(from_year):
    html = get(BASE + "/crawl-data/index.html").read().decode()
    ids = sorted(set(re.findall(r"CC-MAIN-(20\d\d)-(\d\d)", html)))
    return ["CC-MAIN-%s-%s" % i for i in ids if int(i[0]) >= from_year]


def blocks(crawl):
    """Yield (file, offset, length) of index blocks whose key range overlaps PREFIXES.

    Block i covers keys from first_key[i] up to first_key[i+1]."""
    url = "%s/cc-index/collections/%s/indexes/cluster.idx" % (BASE, crawl)
    ranges = [(p, p + "\uffff") for p in PREFIXES]
    prev = None
    for raw in get(url):
        parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        cur = (parts[0].split(" ")[0], parts[1], int(parts[2]), int(parts[3]))
        if prev and any(prev[0] <= hi and cur[0] >= lo for lo, hi in ranges):
            yield prev[1:]
        if prev and prev[0] > max(hi for _, hi in ranges):
            break
        prev = cur


def rows(crawl):
    seen = set()
    for f, off, ln in blocks(crawl):
        if (f, off) in seen:
            continue
        seen.add((f, off))
        url = "%s/cc-index/collections/%s/indexes/%s" % (BASE, crawl, f)
        data = zlib.decompress(get(url, (off, off + ln - 1)).read(), 16 + zlib.MAX_WBITS)
        for row in data.decode("utf-8", "replace").splitlines():
            if any(row.startswith(p) for p in PREFIXES):
                key, ts, js = row.split(" ", 2)
                yield ts, json.loads(js)


def name_from_slug(slug):
    s = urllib.parse.unquote(slug)
    s = s.replace("--", " & ").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def main():
    out = sys.argv[1]
    from_year = int(sys.argv[sys.argv.index("--from-year") + 1]) if "--from-year" in sys.argv else 2024
    comp = {}
    kinds = defaultdict(set)
    for crawl in crawls(from_year):
        n = 0
        try:
            for ts, rec in rows(crawl):
                m = PATH_RE.search(rec.get("url", ""))
                if not m:
                    continue
                kind, slug, cid = m.group(1).lower(), m.group(2), m.group(3).lower()
                kinds[cid].add(kind)
                c = comp.setdefault(cid, {"company_id": cid, "company_name": name_from_slug(slug),
                                          "slug": slug, "booking_url": rec["url"].split("?")[0],
                                          "first_seen": ts[:8], "last_seen": ts[:8], "crawls": set()})
                c["first_seen"] = min(c["first_seen"], ts[:8])
                if ts[:8] >= c["last_seen"]:
                    c.update(last_seen=ts[:8], company_name=name_from_slug(slug), slug=slug,
                             booking_url=rec["url"].split("?")[0])
                c["crawls"].add(crawl)
                n += 1
        except Exception as e:  # keep going if one crawl fails
            print(crawl, "ERROR", e, file=sys.stderr, flush=True)
        print(crawl, n, "rows, total companies", len(comp), file=sys.stderr, flush=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["company_id", "company_name", "slug", "booking_url", "page_types",
                    "first_seen", "last_seen", "crawls_seen"])
        for c in sorted(comp.values(), key=lambda c: c["company_name"].lower()):
            w.writerow([c["company_id"], c["company_name"], c["slug"], c["booking_url"],
                        "+".join(sorted(kinds[c["company_id"]])), c["first_seen"], c["last_seen"],
                        len(c["crawls"])])
    print("wrote", len(comp), "companies to", out, file=sys.stderr)


if __name__ == "__main__":
    main()
