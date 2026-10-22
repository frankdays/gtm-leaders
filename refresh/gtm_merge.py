"""Who needs GTM leaders? page refresh, step 2 of 2.

Usage: python3 gtm_merge.py <data.json> <work.json> <lookups.json> <cats.json> <out_data.json>

lookups.json: {"<company name exactly as in work.json>": {"u": "<company LinkedIn URL or ''>",
               "clay": "yes" | "nomatch", "people": [{"n": name, "t": title, "u": profile URL}, ...]}}
cats.json:    {"<company name>": "<one of CATEGORIES>"}

Classifies leader titles, fills st/sst/ml/sl/lead, appends the new rows to data.json's rows
(existing rows are never changed) and stamps "updated".
"""
import datetime
import json
import re
import sys

CATEGORIES = [
    "AI infrastructure and models", "Agriculture and food", "Consumer and retail", "Cybersecurity",
    "Defense and space", "Developer tools and data", "Education", "Energy and climate",
    "Enterprise AI and automation", "Fintech and insurance", "HR and recruiting", "Healthcare and biotech",
    "Industrial, construction and supply chain", "Legal and compliance", "Media, gaming and entertainment",
    "Mobility and transportation", "Real estate and proptech", "Robotics and autonomy",
    "Sales, marketing and CX", "Semiconductors and hardware", "Other",
]

NOT_A_LEADER = re.compile(r"assistant|chief of staff|\bintern\b|recruit|scientist|research|clinical|dmpk|trainer|student", re.I)
VP = r"(\bvp\b|\bsvp\b|\bevp\b|\bavp\b|vice[- ]president)"
MKT_YES = re.compile(r"\bcmo\b|chief marketing|" + VP + r"[^|]{0,30}marketing|marketing[^|]{0,6}" + VP, re.I)
MKT_ANY = re.compile(r"marketing|\bgrowth\b|\bbrand\b|\bcmo\b", re.I)
SALES_YES = re.compile(r"\bcro\b|chief revenue|chief commercial|\bcco\b|chief sales|chief business officer|"
                       + VP + r"[^|]{0,30}(sales|revenue|commercial)", re.I)
SALES_ANY = re.compile(r"sales|revenue|commercial|\bgtm\b|go-to-market|business development", re.I)


def classify(title):
    """Returns (marketing level, sales level); each is 'yes', 'head' or None."""
    t = title or ""
    if NOT_A_LEADER.search(t):
        return None, None
    m = "yes" if MKT_YES.search(t) else ("head" if MKT_ANY.search(t) else None)
    s = "yes" if SALES_YES.search(t) else ("head" if SALES_ANY.search(t) else None)
    # support functions are not the sales or marketing leader
    if re.search(r"operations|\bops\b|enablement|strategy|analytics", t, re.I):
        if s == "yes" and not re.search(r"\bcro\b|chief", t, re.I):
            s = "head"
        if m == "yes" and not re.search(r"\bcmo\b|chief", t, re.I):
            m = "head"
    if m == "head" and re.search(r"revenue marketing", t, re.I):
        s = s if s == "yes" else None
    return m, s


def person(p, lv):
    return {"n": p["n"], "t": (p.get("t") or "")[:90], "u": p.get("u") or "", "lv": lv}


def fill_leaders(row, people):
    ml, sl, seen = [], [], set()
    for p in people:
        key = (p.get("u") or p.get("n") or "").strip().lower()
        if not p.get("n") or key in seen:
            continue
        seen.add(key)
        m, s = classify(p.get("t"))
        if m:
            ml.append(person(p, m))
        if s:
            sl.append(person(p, s))
    order = {"yes": 0, "head": 1}
    ml.sort(key=lambda p: order[p["lv"]])
    sl.sort(key=lambda p: order[p["lv"]])
    row["ml"], row["sl"] = ml[:3], sl[:3]
    row["st"] = "yes" if any(p["lv"] == "yes" for p in ml) else "no"
    row["sst"] = "yes" if any(p["lv"] == "yes" for p in sl) else "no"


def from_fundedcontacts(row, contacts):
    """High-fit companies the daily Funding Search run already researched on LinkedIn."""
    ml, sl = [], []
    for c in contacts:
        role = c.get("role", "")
        if role == "Marketing Exec":
            ml.append(person(c, "yes"))
        elif role == "Head of Marketing":
            ml.append(person(c, "head"))
        elif role == "CRO":
            sl.append(person(c, "yes"))
        elif role == "Revenue Leader":
            sl.append(person(c, "yes" if SALES_YES.search(c.get("t") or "") else "head"))
    seat = (contacts[0].get("seat") or "").lower() if contacts else ""
    row["ml"], row["sl"] = ml[:3], sl[:3]
    row["st"] = "yes" if seat == "yes" or any(p["lv"] == "yes" for p in ml) else "no"
    row["sst"] = "yes" if any(p["lv"] == "yes" for p in sl) else "no"
    if row["st"] == "no":
        ceo = next((c for c in contacts if c.get("role", "").startswith("CEO")), None) or \
              next((c for c in contacts if c.get("role") == "Founder"), None)
        if ceo:
            row["lead"] = {"n": ceo["n"], "u": ceo.get("u", ""), "t": "CEO" if ceo["role"].startswith("CEO") else "Founder"}


def main(data_path, work_path, lookups_path, cats_path, out_path):
    data = json.load(open(data_path))
    rows = data["rows"] if isinstance(data, dict) else data
    work = json.load(open(work_path))
    lookups = json.load(open(lookups_path)) if lookups_path != "-" else {}
    cats = json.load(open(cats_path))
    today = datetime.date.today().isoformat()

    added, problems = [], []
    for w in work:
        row = dict(w["row"])
        name = row["c"]
        cat = cats.get(name, "")
        if cat not in CATEGORIES:
            problems.append(f"{name}: category '{cat}' is not in the list; set to Other")
            cat = "Other"
        row["cat"] = cat
        if not w["needs_clay"]:
            from_fundedcontacts(row, w.get("fundedcontacts", []))
        else:
            lk = lookups.get(name)
            if not lk or lk.get("clay") != "yes":
                row["clay"] = "nomatch"
                row["st"] = row["sst"] = "nc"
                if lk and lk.get("u"):
                    row["u"] = lk["u"]
            else:
                row["clay"] = "yes"
                row["u"] = lk.get("u") or row["u"]
                fill_leaders(row, lk.get("people", []))
        row["chk"] = today
        added.append(row)

    out = {"updated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"), "rows": rows + added}
    json.dump(out, open(out_path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"rows before: {len(rows)}, added: {len(added)}, after: {len(out['rows'])}")
    for r in added:
        print(f"  {r['c']} | {r['fit']} | mkt={r['st']} sales={r['sst']} | {r['cat']} | "
              + "; ".join(p['n'] + ' (' + p['t'][:40] + ')' for p in r['ml'] + r['sl']))
    for p in problems:
        print("PROBLEM:", p)


if __name__ == "__main__":
    main(*sys.argv[1:6])
