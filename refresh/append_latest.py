"""Optional step 3b: bridge a stale sync.

Usage: python3 append_latest.py <fs.xlsx> <dated sheet .xlsx> [more dated sheets...]

Each dated sheet is either a "Funding Deals YYYY-MM-DD" sheet or a "Funded Contacts YYYY-MM-DD"
sheet; the script tells them apart by their header row.

- Funding Deals sheets are what FundingSheetSync.gs copies into the LinkedIn_Announcements tab.
  Rows are appended to that tab, skipping any row whose company and date are already there.
  Column mapping follows the sync: company, business, amount, stage, investors, location, date,
  fit (the Fit Reason, "-" when not high fit), url.
- Funded Contacts sheets are what the sync copies into the Fundedcontacts tab. Rows are appended
  by header name ("Marketing Exec" goes into "Marketing Seat"), skipping any row whose company and
  LinkedIn URL (or company and contact name when there is no URL) are already there. This lets
  gtm_prep.py reuse the Funding Search LinkedIn lookup instead of searching Clay again.

Everything is appended to the LOCAL working copy of fs.xlsx, never to the Drive spreadsheet.
"""
import datetime
import re
import sys

import openpyxl

TAB = "LinkedIn_Announcements"
CONTACTS_TAB = "Fundedcontacts"


def day(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    return datetime.datetime.strptime(str(v).strip(), "%b %d, %Y").date()


def key(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def clean(v):
    return "" if v is None else str(v).strip()


def url_key(u):
    return clean(u).lower().split("?")[0].rstrip("/")


def append_deals(ws, rows, seen):
    added = 0
    for r in rows:
        if not r[0]:
            continue
        d = day(r[6])
        if (key(r[0]), d) in seen:
            continue
        fit = r[8] if str(r[7]).strip().lower() == "yes" and r[8] else "-"
        ws.append([r[0], r[1], r[2], r[3], r[4], r[5], datetime.datetime.combine(d, datetime.time()), fit, r[9]])
        seen.add((key(r[0]), d))
        added += 1
        print(f"  appended deal {d} | {r[0]}")
    return added


def contact_key(company, url, name):
    return (key(company), url_key(url) or "name:" + clean(name).lower())


def append_contacts(ws, header, rows):
    tab_hdr = [clean(c.value) for c in ws[1]]
    col = {h: i for i, h in enumerate(tab_hdr) if h}
    seen = set()
    for r in ws.iter_rows(min_row=2, values_only=True):
        rec = {h: r[i] for h, i in col.items() if i < len(r)}
        if clean(rec.get("Company")):
            seen.add(contact_key(rec.get("Company"), rec.get("LinkedIn URL"), rec.get("Contact Name")))
    src = {("Marketing Seat" if h == "Marketing Exec" else h): i for i, h in enumerate(header) if h}
    added = 0
    for r in rows:
        rec = {h: r[i] for h, i in src.items() if i < len(r)}
        if not clean(rec.get("Company")):
            continue
        k = contact_key(rec.get("Company"), rec.get("LinkedIn URL"), rec.get("Contact Name"))
        if k in seen:
            continue
        ws.append([rec.get(h) if h else None for h in tab_hdr])
        seen.add(k)
        added += 1
        print(f"  appended contact {clean(rec.get('Company'))} | {clean(rec.get('Contact Name')) or '(no contact)'}")
    return added


def main(fs, sheets):
    wb = openpyxl.load_workbook(fs)
    ws = wb[TAB]
    seen = set()
    # openpyxl saves 1872.0 as 1872, which would make gtm_prep see a company named "1872.0" as new.
    for c in ws["A"]:
        if isinstance(c.value, float):
            c.value = str(c.value)
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] and isinstance(r[6], datetime.datetime):
            seen.add((key(r[0]), r[6].date()))
    deals = contacts = 0
    for path in sheets:
        src = list(openpyxl.load_workbook(path, read_only=True).worksheets[0].iter_rows(values_only=True))
        if not src:
            continue
        header = [clean(h) for h in src[0]]
        if "Contact Name" in header:
            contacts += append_contacts(wb[CONTACTS_TAB], header, src[1:])
        else:
            deals += append_deals(ws, src[1:], seen)
    wb.save(fs)
    print(f"appended {deals} deal rows and {contacts} contact rows to {fs}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
