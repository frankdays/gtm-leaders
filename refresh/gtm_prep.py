"""Who needs GTM leaders? page refresh, step 1 of 2.

Usage: python3 gtm_prep.py <funding_search.xlsx> <data.json> <work.json>

Reads the LinkedIn_Announcements and Fundedcontacts tabs of "Funding Search: VC/PE V2",
compares them with the page's data.json, and writes work.json: one entry per company that
is not on the page yet, with every field filled except the category and, for companies
without usable Fundedcontacts rows, the leader lookup (done in Clay by the agent).
"""
import datetime
import json
import re
import sys

import openpyxl

START_ISO = "2026-07-01"  # the page covers deals announced on or after this date

EXCLUDE_STAGE = re.compile(r"acqui|merger|\bipo\b|pre-ipo|post-ipo|mature|\bdebt\b|bridge|loan|grant", re.I)
EXCLUDE_NAME = re.compile(r"\(acquir|acquired|acquisition|\s/\s", re.I)

SRC = {"linkedin.com": "LinkedIn", "techcrunch.com": "TechCrunch", "news.crunchbase.com": "Crunchbase News",
       "crunchbase.com": "Crunchbase News", "news.google.com": "Google News", "prnewswire.com": "PR Newswire"}

STAGES = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E+", "Growth", "Strategic", "Not specified"]

def norm_stage(raw):
    s = (raw or "").strip().lower()
    if not s or s.startswith("not specified") or s in ("-", "unknown", "undisclosed"):
        return "Not specified"
    if "strategic" in s or "corporate" in s:
        return "Strategic"
    if "growth" in s or "later" in s or "late stage" in s or "secondary" in s or "private equity" in s:
        return "Growth"
    letters = re.findall(r"series\s+([a-z])(?![a-z])", s) + re.findall(r"series\s+[a-z]\s*/\s*([a-z])(?![a-z])", s)
    if letters:
        top = max(letters)
        if s.startswith("pre-series") or s.startswith("pre series"):
            top = chr(ord(top) - 1)
            if top < "a":
                return "Seed"
        return "Series E+" if top >= "e" else "Series " + top.upper()
    if "pre-seed" in s or "pre seed" in s or "angel" in s:
        return "Pre-seed"
    if "seed" in s:
        return "Seed"
    return "Not specified"


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def ckey(name):
    """Loose company key; same rules as companyKey_ in FundingSheetSync.gs."""
    s = norm(name)
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    suf = re.compile(r"\s+(ai|inc|llc|ltd|limited|co|corp|corporation|technologies|technology|tech|labs|hq|holdings|group|gmbh|sa|sas)$")
    while True:
        prev = s
        s = suf.sub("", s)
        if s == prev or " " not in s:
            break
    return s.replace(" ", "")


def to_iso(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(str(v).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def pretty(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def clean(v):
    return "" if v is None else str(v).strip()


def tab(wb, name):
    rows = list(wb[name].iter_rows(values_only=True))
    hdr = [clean(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {h: r[i] for i, h in enumerate(hdr) if h and i < len(r)}
        if any(clean(v) for v in d.values()):
            out.append(d)
    return out


def main(xlsx, data_path, out_path):
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    deals = tab(wb, "LinkedIn_Announcements")
    contacts = tab(wb, "Fundedcontacts")

    data = json.load(open(data_path))
    rows = data["rows"] if isinstance(data, dict) else data
    have = {ckey(r["c"]) for r in rows}

    fc = {}
    for c in contacts:
        fc.setdefault(ckey(c.get("Company")), []).append(c)

    work, seen, skipped = [], set(), {"excluded": 0, "already": 0, "old_or_undated": 0}
    deals.sort(key=lambda d: to_iso(d.get("date")) or "")
    for d in deals:
        name = clean(d.get("company"))
        iso = to_iso(d.get("date"))
        if not name:
            continue
        if not iso or iso < START_ISO:
            skipped["old_or_undated"] += 1
            continue
        k = ckey(name)
        if not k or k in have or k in seen:
            skipped["already"] += 1
            continue
        stage = clean(d.get("stage")) or "Not specified"
        if EXCLUDE_STAGE.search(stage) or EXCLUDE_NAME.search(name):
            skipped["excluded"] += 1
            continue
        seen.add(k)
        url = clean(d.get("url"))
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
        fit_reason = clean(d.get("fit"))
        loc = clean(d.get("location"))
        row = {
            "fit": "high" if fit_reason and fit_reason != "-" else "low",
            "c": name, "u": "", "s": norm_stage(stage), "a": clean(d.get("amount")) or "Not disclosed",
            "d": pretty(iso), "iso": iso, "b": clean(d.get("business")),
            "st": "nc", "sst": "nc", "ml": [], "sl": [], "lead": None,
            "dl": url, "cat": "", "src": SRC.get(host, "Link"),
            "hq": "" if not loc or loc.lower().startswith("not specified") else loc,
        }
        people = fc.get(k, [])
        seat = clean(people[0].get("Marketing Seat")) if people else ""
        usable = people and seat and seat.lower() != "unknown" and any(clean(p.get("Contact Name")) for p in people)
        entry = {"row": row, "needs_clay": not usable}
        if usable:
            row["u"] = next((clean(p.get("Company LinkedIn")) for p in people if clean(p.get("Company LinkedIn"))), "")
            entry["fundedcontacts"] = [{
                "n": clean(p.get("Contact Name")), "t": clean(p.get("Title")), "u": clean(p.get("LinkedIn URL")),
                "role": clean(p.get("Role")), "seat": clean(p.get("Marketing Seat")),
            } for p in people if clean(p.get("Contact Name"))]
        work.append(entry)

    json.dump(work, open(out_path, "w"), indent=1, ensure_ascii=False)
    n_clay = sum(1 for w in work if w["needs_clay"])
    print(f"new companies: {len(work)} ({n_clay} need a Clay lookup, {len(work) - n_clay} from Fundedcontacts); skipped: {skipped}")
    for w in work:
        r = w["row"]
        print(f"  {r['iso']} | {r['fit']} | {r['c']} | {r['s']} | {r['b']} | clay={'yes' if w['needs_clay'] else 'no'}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
