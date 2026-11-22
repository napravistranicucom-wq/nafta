"""Check whether company websites embed Housecall Pro, using Common Crawl's archive.

For each domain we look up its archived pages (home, /book, /contact, /schedule...)
in a Common Crawl index, fetch those HTML records from data.commoncrawl.org and
search for the fingerprints in fingerprints.json. The HCP token found on a site
is the same company_id as in hcp-booking-companies.csv, so matches can be joined.

Usage: python3 leads/scan.py domains.txt OUT.csv [--crawl CC-MAIN-2026-43]
domains.txt: one domain per line (example.com).
"""
import bisect, csv, gzip, io, json, os, re, sys, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor

BASE = "https://data.commoncrawl.org"
HERE = os.path.dirname(os.path.abspath(__file__))
FP = json.load(open(os.path.join(HERE, "fingerprints.json")))
TOKEN_RE = re.compile(FP["token_regex"], re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"tel:\+?1?[\s.-]?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})")
BAD_EMAIL = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname", ".png", ".jpg", ".webp", ".gif", "godaddy", "wordpress")


FREE_MAIL = ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com", "live.com", "msn.com", "comcast.net", "att.net", "sbcglobal.net", "verizon.net", "bellsouth.net", "me.com", "proton.me", "protonmail.com")


def contacts(html, domain=""):
    emails = {re.sub(r"^(u00[0-9a-f]{2})+", "", e.lower().strip(".")) for e in EMAIL_RE.findall(html)}
    site = domain.lower().removeprefix("www.")
    emails = sorted(e for e in emails if not any(b in e for b in BAD_EMAIL)
                    and (e.split("@")[1].removeprefix("www.") == site or e.split("@")[1] in FREE_MAIL))
    phones = sorted({"%s-%s-%s" % m for m in PHONE_RE.findall(html)})
    return emails, phones
PATHS = ("", "book", "booking", "schedule", "contact", "contact-us", "services")
CACHE = os.environ.get("CC_CACHE", os.path.join(HERE, ".cc-cache"))


def get(url, rng=None):
    req = urllib.request.Request(url, headers={"User-Agent": "hcp-research/1.0"})
    if rng:
        req.add_header("Range", "bytes=%d-%d" % rng)
    return urllib.request.urlopen(req, timeout=120).read()


def surt(domain):
    d = domain.lower().strip().removeprefix("http://").removeprefix("https://").split("/")[0]
    d = d.removeprefix("www.")
    return ",".join(reversed(d.split("."))) + ")/"


class Index:
    def __init__(self, crawl):
        self.crawl = crawl
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, crawl + ".cluster.idx")
        if not os.path.exists(path):
            open(path, "wb").write(get("%s/cc-index/collections/%s/indexes/cluster.idx" % (BASE, crawl)))
        self.keys, self.loc = [], []
        for line in open(path, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                self.keys.append(p[0].split(" ")[0])
                self.loc.append((p[1], int(p[2]), int(p[3])))
        self.block_cache = {}

    def lookup(self, prefix):
        i = max(0, bisect.bisect_left(self.keys, prefix) - 1)
        out = []
        while i < len(self.keys) and self.keys[i] <= prefix + "￿":
            f, off, ln = self.loc[i]
            if (f, off) not in self.block_cache:
                url = "%s/cc-index/collections/%s/indexes/%s" % (BASE, self.crawl, f)
                self.block_cache[(f, off)] = zlib.decompress(get(url, (off, off + ln - 1)), 16 + zlib.MAX_WBITS).decode("utf-8", "replace")
            for row in self.block_cache[(f, off)].splitlines():
                if row.startswith(prefix):
                    out.append(json.loads(row.split(" ", 2)[2]))
            i += 1
        return out


def fetch_html(rec):
    off, ln = int(rec["offset"]), int(rec["length"])
    raw = gzip.GzipFile(fileobj=io.BytesIO(get(BASE + "/" + rec["filename"], (off, off + ln - 1)))).read()
    return raw.split(b"\r\n\r\n", 2)[-1].decode("utf-8", "replace")


def check(index, domain):
    key = surt(domain)
    recs = [r for r in index.lookup(key) if r.get("status") == "200" and "html" in r.get("mime", "")]
    wanted = [r for r in recs if r["url"].split("?")[0].rstrip("/").split("/", 3)[-1].lower() in PATHS
              or r["url"].rstrip("/").count("/") <= 2]
    res = {"domain": domain, "archived_pages": len(recs), "checked": 0, "uses_hcp": "unknown",
           "evidence": "", "hcp_company_id": "", "checked_url": "", "emails": "", "phones": ""}
    emails, phones = set(), set()
    # home page first, then contact/booking pages
    wanted.sort(key=lambda r: (r["url"].rstrip("/").count("/") > 2, "contact" not in r["url"].lower()))
    for r in wanted[:4]:
        try:
            html = fetch_html(r)
        except Exception:
            continue
        res["checked"] += 1
        e, p = contacts(html, domain); emails.update(e); phones.update(p)
        low = html.lower()
        strong = [f for f in FP["strong"] if f.lower() in low]
        weak = [f for f in FP["weak"] if f.lower() in low]
        if (strong or weak) and res["uses_hcp"] != "yes":
            m = TOKEN_RE.search(html)
            res.update(uses_hcp="yes" if strong else "maybe", evidence="; ".join(strong or weak),
                       hcp_company_id=next((g for g in (m.groups() if m else ()) if g), ""),
                       checked_url=r["url"])
        if res["uses_hcp"] == "yes" and emails:
            break
    if res["checked"] and res["uses_hcp"] == "unknown":
        res["uses_hcp"] = "no"
    res["emails"] = ";".join(sorted(emails)[:5]); res["phones"] = ";".join(sorted(phones)[:3])
    return res


def main():
    src, out = sys.argv[1], sys.argv[2]
    crawl = sys.argv[sys.argv.index("--crawl") + 1] if "--crawl" in sys.argv else "CC-MAIN-2026-43"
    domains = [l.strip() for l in open(src) if l.strip() and not l.startswith("#")]
    index = Index(crawl)
    with ThreadPoolExecutor(4) as ex, open(out, "w", newline="") as fh:
        w = None
        for res in ex.map(lambda d: check(index, d), domains):
            if w is None:
                w = csv.DictWriter(fh, fieldnames=list(res)); w.writeheader()
            w.writerow(res); fh.flush()
            print(res["domain"], res["uses_hcp"], res["evidence"], file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
