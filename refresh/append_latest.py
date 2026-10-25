"""Optional step 3b: bridge a stale sync.

Usage: python3 append_latest.py <fs.xlsx> <funding_deals_YYYY-MM-DD.xlsx> [more dated sheets...]

The dated "Funding Deals YYYY-MM-DD" sheets are what FundingSheetSync.gs copies into the
LinkedIn_Announcements tab. When the sync has not run yet, this appends the dated sheet's rows
to the LOCAL working copy of fs.xlsx (never to the Drive spreadsheet), skipping any row whose
company and date are already in the tab. Column mapping follows the sync: company, business,
amount, stage, investors, location, date, fit (the Fit Reason, "-" when not high fit), url.
"""
import datetime
import re
import sys

import openpyxl

TAB = "LinkedIn_Announcements"


def day(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    return datetime.datetime.strptime(str(v).strip(), "%b %d, %Y").date()


def key(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


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
    added = 0
    for path in sheets:
        src = openpyxl.load_workbook(path, read_only=True).worksheets[0]
        for r in list(src.iter_rows(values_only=True))[1:]:
            if not r[0]:
                continue
            d = day(r[6])
            if (key(r[0]), d) in seen:
                continue
            fit = r[8] if str(r[7]).strip().lower() == "yes" and r[8] else "-"
            ws.append([r[0], r[1], r[2], r[3], r[4], r[5], datetime.datetime.combine(d, datetime.time()), fit, r[9]])
            seen.add((key(r[0]), d))
            added += 1
            print(f"  appended {d} | {r[0]}")
    wb.save(fs)
    print(f"appended {added} rows to {fs}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
