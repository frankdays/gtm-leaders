"""Build the public, companies-only copy of the Who needs GTM leaders? page.
Usage: python3 make_public.py <data.json> <index.html> <out_dir>
Drops leader names, titles, profile links and CEO/founder leads; keeps Yes/No/Needs lookup."""
import json, os, sys

# GoatCounter page-view analytics, added to the public GitHub Pages copy only.
GOATCOUNTER = ('<script data-goatcounter="https://frankdays.goatcounter.com/count"\n'
               '        async src="//gc.zgo.at/count.js"></script>\n')

def main(data_path, index_path, out_dir):
    d = json.load(open(data_path))
    rows = d["rows"] if isinstance(d, dict) else d
    keep = ("fit", "c", "u", "s", "a", "d", "iso", "b", "st", "sst", "dl", "cat", "src", "hq")
    pub = [dict({k: r.get(k) for k in keep}, ml=[], sl=[], lead=None) for r in rows]
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"updated": d.get("updated"), "rows": pub}, open(os.path.join(out_dir, "data.json"), "w"),
              ensure_ascii=False, separators=(",", ":"))
    html = open(index_path).read()
    html = html.replace("a Head of Marketing alone counts as No, with the name shown.", "a Head of Marketing alone counts as No.")
    html = html.replace("High-fit companies were checked on LinkedIn; most others were checked in Clay. ", "")
    html = html.replace("the daily Funding Deals and Funded Contacts sheets, and Clay people search (searches only, no enrichment)",
                        "and public company and people data")
    if "gc.zgo.at/count.js" not in html:
        html = html.replace("</body>", GOATCOUNTER + "</body>", 1)
    open(os.path.join(out_dir, "index.html"), "w").write(html)
    open(os.path.join(out_dir, ".nojekyll"), "w").write("")
    print(f"public rows: {len(pub)}; people fields removed")

if __name__ == "__main__":
    main(*sys.argv[1:4])
