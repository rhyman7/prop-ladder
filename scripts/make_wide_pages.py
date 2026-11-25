"""Regenerate docs/wide/{index,plays}.html from the 9-book pages.
Run after any change to docs/index.html or docs/plays.html."""
import os
ROOT = os.path.join(os.path.dirname(__file__), "..", "docs")
for f in ("index.html", "plays.html"):
    s = open(os.path.join(ROOT, f)).read()
    w = s.replace('href="style.css"', 'href="../style.css"').replace('src="common.js"', 'src="../common.js"')
    tag = ' <span class="tag dark" style="font-size:14px;vertical-align:middle">Wide</span>'
    if f == "index.html":
        w = w.replace("<title>Prop Ladder</title>", "<title>Prop Ladder · Wide</title>").replace("<h1>Prop Ladder</h1>", "<h1>Prop Ladder" + tag + "</h1>")
        w = w.replace('<p class="sub">True probability for every rung, from the whole market with the vig removed, against DraftKings and FanDuel.</p>',
                      '<p class="sub">Trial version: 9 books plus sharper books and exchanges. Where a sharp book prices a rung, the true probability comes from the sharp books alone.</p>')
    else:
        w = w.replace("<title>All +EV plays · Prop Ladder</title>", "<title>All +EV plays · Wide</title>").replace("<h1>All +EV plays</h1>", "<h1>All +EV plays" + tag + "</h1>")
    os.makedirs(os.path.join(ROOT, "wide"), exist_ok=True)
    open(os.path.join(ROOT, "wide", f), "w").write(w)
print("wide pages written")
