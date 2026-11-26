"""Regenerate docs/wide/ and docs/pinnacle/ {index,plays}.html from the 9-book
pages. Run after any change to docs/index.html or docs/plays.html."""
import os
ROOT = os.path.join(os.path.dirname(__file__), "..", "docs")
SUB = {
    "wide": ("Wide", "Trial version: 9 books plus sharper books and exchanges. Where a sharp book prices a rung, the true probability comes from the sharp books alone."),
    "pinnacle": ("Pinnacle", "Pinnacle version (NFL and NBA): Pinnacle's vig-free line sets the true probability, and the market's ladder is shifted to match it at every rung."),
}
for folder, (label, sub) in SUB.items():
    for f in ("index.html", "plays.html"):
        s = open(os.path.join(ROOT, f)).read()
        w = s.replace('href="style.css"', 'href="../style.css"').replace('src="common.js"', 'src="../common.js"')
        tag = f' <span class="tag dark" style="font-size:14px;vertical-align:middle">{label}</span>'
        if f == "index.html":
            w = w.replace("<title>Prop Ladder</title>", f"<title>Prop Ladder · {label}</title>").replace("<h1>Prop Ladder</h1>", "<h1>Prop Ladder" + tag + "</h1>")
            w = w.replace('<p class="sub">True probability for every rung, from the whole market with the vig removed, against DraftKings, FanDuel and Kalshi.</p>', f'<p class="sub">{sub}</p>')
        else:
            w = w.replace("<title>All +EV plays · Prop Ladder</title>", f"<title>All +EV plays · {label}</title>").replace("<h1>All +EV plays</h1>", "<h1>All +EV plays" + tag + "</h1>")
        os.makedirs(os.path.join(ROOT, folder), exist_ok=True)
        open(os.path.join(ROOT, folder, f), "w").write(w)
print("wide and pinnacle pages written")
