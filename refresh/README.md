# GTM Openings Before They're Posted: daily page refresh

Adds each day's new funding rounds to the "GTM Openings Before They're Posted" page (formerly "Who needs GTM leaders?")
(its URL is in the scheduled task's instructions), with whether each company has a
marketing leader (CMO, VP or SVP Marketing) and a sales leader (CRO, VP or SVP Sales or Revenue,
Chief Commercial Officer or similar). A companies-only public copy (no people) is pushed to
GitHub Pages at https://github.com/frankdays/gtm-leaders each time the page is published.

**Source of truth:** the LinkedIn_Announcements and Fundedcontacts tabs of "Funding Search: VC/PE V2"
(its fileId is in the scheduled task's instructions). The daily Funding Search VC/PE task writes the
dated sheets at about 9am ET and FundingSheetSync.gs copies them into those tabs at 11am ET, so this
refresh runs after noon ET.

**The page:** `index.html` holds the layout and code only; every row lives in the published file
`data.json` (`{"updated": "<ISO time>", "rows": [...]}`). The refresh only ever changes `data.json`.

## Rules

- Append only. Never change or delete an existing row in data.json, and never edit the spreadsheet.
- Rows cover deals announced on or after Jul 1, 2026. Acquisitions, mergers, IPOs, debt and bridge
  rounds are left out (gtm_prep.py applies this).
- No Clay, ConnectSafely, LinkedIn or web lookups of any kind. Leaders come only from the Fundedcontacts
  tab (the daily Funding Search task's LinkedIn lookup). Companies without that data are added as
  "Needs lookup".
- Companies are listed by name; people only by name, title and public LinkedIn URL from the
  Fundedcontacts tab. No emails or phone numbers.
- The GitHub copy never contains people: only the output of make_public.py is pushed.

## Steps

1. **Scripts.** Make a working folder OUTSIDE the repo checkout (for example `/tmp/gtm`) and copy
   `refresh/gtm_prep.py`, `refresh/gtm_merge.py` and `refresh/make_public.py` from this repo into it.
   Every file in steps 2 to 7 (fs.xlsx, work.json, cats.json and the rest) goes in that folder, never
   in the repo: they hold people data. `pip install openpyxl --break-system-packages` if the import fails.
2. **Current page data.** Artifact `read` with the page url
   (no path) first, so the later publish is allowed. Then Artifact `read` with the same url and
   `path` `data.json`, and `path` `index.html`; note where each file was saved.
3. **Spreadsheet.** Google Drive `download_file_content` on the fileId above with exportMimeType
   `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. The result is saved to a file;
   base64-decode its `content` field with Python into `fs.xlsx`. Never copy base64 by hand.
   Freshness check: the Drive export can return a stale copy. Use Google Drive `search_files` with
   `title contains 'Funding Deals' and modifiedTime > '<today>T00:00:00Z'` to find today's dated
   "Funding Deals YYYY-MM-DD" sheet. If it exists and has rows dated today, but fs.xlsx's
   LinkedIn_Announcements tab has no rows dated today, download the spreadsheet again (up to 2 more
   tries) before going on, and say in the report if it was still stale.
3b. **Bridge a stale sync.** If, after those tries, any "Funding Deals YYYY-MM-DD" sheet modified since the
   newest date in the LinkedIn_Announcements tab (check the last 3 days, not only today) has rows that the tab
   lacks, download each such sheet with `download_file_content` (same exportMimeType, base64-decode into
   `latest_<date>.xlsx` in the working folder). Also download the "Funded Contacts YYYY-MM-DD" sheet for each
   of those dates, if it exists, into `contacts_<date>.xlsx` (it holds the Funding Search LinkedIn lookup for
   those companies). Then run
   `python3 append_latest.py fs.xlsx latest_<date>.xlsx contacts_<date>.xlsx ...` (copy it to the working folder
   in step 1; use a Python that has openpyxl). It tells the two kinds of sheet apart by their headers, appends
   the missing rows to the LOCAL fs.xlsx only (LinkedIn_Announcements and Fundedcontacts tabs), skips rows
   already in the tabs, and never touches Drive. Then go on to step 4. Say in the report that the sync was
   bridged and how many deal and contact rows were appended. Companies whose contacts were bridged reuse the
   Funding Search lookup; the rest are added as "Needs lookup".
4. **New companies.** `python3 gtm_prep.py fs.xlsx <data.json path> work.json`. It prints each company
   not yet on the page and whether Funding Search leader data exists for it. If it finds none, stop: publish nothing and
   report "No new funded companies today."
5. **Categories.** For every company in work.json, pick exactly one category from this list, using the
   Business line: AI infrastructure and models; Agriculture and food; Consumer and retail; Cybersecurity;
   Defense and space; Developer tools and data; Education; Energy and climate; Enterprise AI and automation;
   Fintech and insurance; HR and recruiting; Healthcare and biotech; Industrial, construction and supply
   chain; Legal and compliance; Media, gaming and entertainment; Mobility and transportation; Real estate
   and proptech; Robotics and autonomy; Sales, marketing and CX; Semiconductors and hardware; Other.
   Write `cats.json` as `{"<company name exactly as in work.json>": "<category>"}`.
6. **No leader lookups.** Entries with `needs_lookup: false` take their leaders from the Fundedcontacts tab
   (gtm_merge.py does this, including companies where Funding Search searched and found no marketing or sales
   leader, which show as No). Entries with `needs_lookup: true` are added as "Needs lookup". Do not search for
   their leaders anywhere: no Clay, no ConnectSafely or LinkedIn, no web search.
7. **Merge.** `python3 gtm_merge.py <data.json path> work.json - cats.json data_out.json` (the `-` means there
   is no lookups file).
   Check its printout: row count before plus added equals after, and no PROBLEM lines left unexplained.
8. **Publish** only the data file: Artifact publish with `url` = the page url,
   `file_path` = the index.html saved in step 2 (unchanged), and `files` = `{"data.json": "<data_out.json path>"}`.
   Do not pass `icon`. If the publish is refused because the page changed, read the live version again,
   rerun steps 2 to 7 on it, and publish once more.
9. **GitHub copy** (only after step 8 published). Push the companies-only copy to GitHub Pages:
   ```
   cd <repo checkout> && git checkout main && git pull origin main
   python3 <working folder>/make_public.py <data_out.json path> <index.html path from step 2> .
   ```
   Before committing, confirm no person data is in the copy: every row has empty `ml` and `sl` and
   `lead` null, and `grep -c "linkedin.com/in/" data.json index.html` is 0 for data.json and at most 1 for index.html (the "Created by Frank Days" byline link, `linkedin.com/in/frank-days/`, is the only allowed one). If not, do not push.
   Then `git add index.html data.json .nojekyll` (never `git add -A`), commit as "Frank Days <frank.days@gmail.com>" with message
   "Refresh: <N> rows (<added> added <YYYY-MM-DD>)", and `git push origin main`. Never force-push and
   never push anything other than index.html, data.json and .nojekyll. If the push is refused, do not
   retry with other methods; give the exact error in the report (the claude.ai page is still updated).
10. **Report** in a few lines: companies added (high fit first), how many have no marketing leader, the
    high-fit ones with no marketing leader by name, how many companies were added as "Needs lookup" (name the high-fit ones), whether the GitHub copy
    was pushed, and any errors.
