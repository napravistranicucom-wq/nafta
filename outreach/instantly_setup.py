"""Create the Crewly cold email campaign in Instantly (API v2) and add the leads.

The campaign is created PAUSED (Instantly's default for new campaigns). This
script never activates it: you start sending yourself in the Instantly app.

Usage:
  python3 outreach/instantly_setup.py --dry-run          # show what would be sent
  python3 outreach/instantly_setup.py                    # create campaign + add leads
  python3 outreach/instantly_setup.py --campaign ID      # only add leads to an existing campaign

The API key is read from INSTANTLY_API_KEY. In a Claude cloud session the
network proxy adds the key for api.instantly.ai, so a dummy value is enough there.
"""
import csv, json, os, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://api.instantly.ai/api/v2"
KEY = os.environ.get("INSTANTLY_API_KEY", "dummy-key-injected-by-proxy")
DAYS = {"sun": "0", "mon": "1", "tue": "2", "wed": "3", "thu": "4", "fri": "5", "sat": "6"}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit("%s %s -> HTTP %s: %s" % (method, path, e.code, e.read().decode()[:500]))


def html(text):
    return "".join("<div>%s</div>" % (line or "<br>") for line in text.split("\n"))


def campaign_body(seq, accounts):
    s = seq["schedule"]
    steps = []
    for st in seq["steps"]:
        steps.append({"type": "email", "delay": st["delay_days_after"],
                      "variants": [{"subject": v["subject"], "body": html(v["body"])} for v in st["variants"]]})
    return {
        "name": seq["campaign_name"],
        "campaign_schedule": {"schedules": [{
            "name": "Mornings Tue-Thu", "timezone": s["timezone"],
            "timing": {"from": s["from"], "to": s["to"]},
            "days": {DAYS[d]: True for d in s["days"]},
        }]},
        "sequences": [{"steps": steps}],
        "email_list": accounts,
        "daily_limit": seq["daily_limit"],
        "stop_on_reply": seq["stop_on_reply"],
        "text_only": True,
    }


def leads():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "leads", "instantly-import.csv"))))
    return [r for r in rows if not r["website"].endswith(".ca")]  # US only


def main():
    dry = "--dry-run" in sys.argv
    seq = json.load(open(os.path.join(HERE, "sequence.json")))
    if "POSTAL_ADDRESS" in json.dumps(seq) and not dry:
        raise SystemExit("Replace POSTAL_ADDRESS in outreach/sequence.json with a real postal address first (CAN-SPAM).")
    ls = leads()

    if "--campaign" in sys.argv:
        cid = sys.argv[sys.argv.index("--campaign") + 1]
    else:
        accounts = [] if dry else [a["email"] for a in call("GET", "/accounts?limit=100").get("items", [])]
        if not dry and not accounts:
            raise SystemExit("No sending accounts in Instantly yet. Add and warm up inboxes first.")
        body = campaign_body(seq, accounts or ["you@getcrewly.com"])
        if dry:
            print(json.dumps(body, indent=2)[:3000]); print("...", len(ls), "leads would be added"); return
        cid = call("POST", "/campaigns", body)["id"]
        print("created campaign", cid, "(paused) with", len(accounts), "sending accounts")

    ok = 0
    for r in ls:
        call("POST", "/leads", {
            "campaign": cid, "email": r["email"], "company_name": r["company_name"],
            "website": r["website"], "phone": r["phone"],
            "custom_variables": {"industry": r["industry"], "hcp_match": r["hcp_match"]},
            "skip_if_in_workspace": True,
        })
        ok += 1
        if ok % 50 == 0:
            print(ok, "leads added", flush=True)
        time.sleep(0.25)
    print("done:", ok, "leads in campaign", cid, "- review it in Instantly, then press Resume to start sending")


if __name__ == "__main__":
    main()
