"""Generate the RGS Young Geographer StoryMap content from the result files.

The Royal Geographical Society's KS5 category asks for an Esri StoryMap on the
theme "From Source to Sea", explicitly including conflict among the river
themes. This writes the section-by-section narrative and a self-contained HTML
preview, with every figure injected from the analysis rather than typed, so the
entry cannot drift from the paper it is based on.

Output:
  storymap.html  - readable preview, open in any browser
  storymap.md    - plain text to paste into ArcGIS StoryMaps section by section
"""
import json
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")


def load(p):
    return json.load(open(p, encoding="utf-8"))


facts = load("facts.json")
master = load("results_master.json")["controls"]
ncy = load("nicosia_ci.json")
cyp = load("results_cyprus.json")
loc = load("localised.json")
base = load("results.json")

none, nwr = master["none"], master["nowater_norail"]
cy_plac = np.array([r["ratio"] for r in cyp["runs"]
                    if r.get("ok") and r["kind"] == "placebo"])
cy_z = (ncy["true"] - cy_plac.mean()) / cy_plac.std(ddof=1)
ham = [r["ratio"] for r in base["runs"] if r.get("ok") and r.get("city") == "hamburg"]
bins = sorted(loc["bins"], key=lambda b: -b["ratio"])

V = {
    "cy_pct": f"{(ncy['true'] - 1) * 100:.1f}",
    "cy_z": f"{cy_z:+.2f}",
    "cy_n": len(cy_plac),
    "be_pct": f"{(none['true'] - 1) * 100:.1f}",
    "be_z": f"{none['z']:+.2f}",
    "be_n": none["n_placebo"],
    "nwr_pct": f"{(nwr['true'] - 1) * 100:.1f}",
    "nwr_z": f"{nwr['z']:+.2f}",
    "water_share": facts["water_share"],
    "water_same": facts["water_share_sameside"],
    "rail_share": facts["rail_share"],
    "both_share": facts["water_or_rail_share"],
    "ring_km": facts["ring_km"],
    "inner_km": facts["inner_km"],
    "area": facts["ring_area_km2"],
    "area_err": facts["area_error_pct"],
    "nodes": f"{facts['berlin_nodes']:,}",
    "top1": bins[0]["near"], "top1v": f"{bins[0]['ratio']:.3f}",
    "top2": bins[1]["near"], "top2v": f"{bins[1]['ratio']:.3f}",
    "bot1": bins[-1]["near"], "bot1v": f"{bins[-1]['ratio']:.3f}",
    "ham_max": f"{max(ham):.2f}",
    "ratio": f"{(ncy['true'] - 1) / (none['true'] - 1):.0f}",
}

SECTIONS = [
    ("The river that carried a border",
     f"""The Spree rises in the hills of Saxony and runs north-west through
Berlin before joining the Havel and, eventually, the North Sea. For twenty-eight
years, part of its course through the centre of Berlin was also the edge of a
country. The Berlin Wall did not cut across the city at random. Where it could,
it followed water: the Spree itself, the Landwehrkanal, the Britzer canal, and
the rail corridors that had already been laid beside them.

This is not a Berlin peculiarity. Borders follow rivers everywhere, and for an
obvious reason: a river is already difficult to cross, so it is cheap to defend
and easy to agree on. That habit leaves a question that is harder than it first
appears. When a border and a river lie on top of one another, and you measure
the mark the border left on a city, what have you actually measured?"""),

    ("What a road network remembers",
     f"""A city's road network keeps a record of what has been difficult to
cross. The measure is called circuity: the distance you must actually travel
between two points, divided by the straight-line distance between them. Travel
across open ground and the ratio sits near one. Travel across a river with few
bridges and it climbs, because you must go the long way round to reach a
crossing.

This study builds Berlin's drivable road network from open mapping data --
{V['nodes']} junctions -- and asks a simple question. If you pick two points
between 1 and 6 km apart on opposite sides of where the Wall stood, do you
travel further than two points the same distance apart, in the same
neighbourhood, on the same side?"""),

    ("The problem with an obvious answer",
     f"""You will find excess circuity across the Wall. But you will also find
it across an arbitrary line drawn anywhere awkward. Laying the same curve across
Hamburg, a city never divided, produces apparent severance of up to
{V['ham_max']} -- purely from the Elbe and the port. A river severs a road
network all by itself, with no politics involved at all.

So the test cannot be "is there extra circuity?" It has to be "is there more
extra circuity here than at comparable places?" This study answers that by
taking the Wall's exact shape -- all {V['ring_km']} km of it -- and rotating it
about its own centre to {V['be_n']} other positions in the same city. Each
rotated copy has identical shape, length and enclosed area. Only the history is
removed. The real position is then scored against those {V['be_n']} imposters."""),

    ("A boundary that is still shut",
     f"""Before trusting a result at a boundary that is gone, you need to know
the instrument works on one that is still there. In Nicosia, the United Nations
Buffer Zone has divided Cyprus since 1974 and remains closed, crossed by only a
handful of checkpoints.

Crossing it costs {V['cy_pct']}% additional travel distance. Not one of
{V['cy_n']} displaced comparison lines comes close: the true position sits
{V['cy_z']} standard deviations above them. The method detects a living
boundary without difficulty, which is what makes the Berlin number
interpretable."""),

    ("Berlin, thirty-seven years on",
     f"""Crossing the line where the Wall stood still costs about
{V['be_pct']}% more travel distance than moving the same distance alongside it
-- and no rotated copy of the Wall, anywhere else in Berlin, matches it.

The effect is small. Set against Nicosia's {V['cy_pct']}%, a boundary still
closed costs roughly {V['ratio']} times more than one taken down a generation
ago. Berlin has very largely healed. But not completely."""),

    ("The river's twist",
     f"""Here the rivers return, and not as expected. The obvious worry was
that the Berlin result was really the Spree in disguise -- and
{V['water_share']}% of trips crossing the former Wall do also cross water,
with {V['both_share']}% crossing water or railway.

But removing every water crossing did not shrink the effect. It grew, from
{V['be_pct']}% to {V['nwr_pct']}% once railways went too.

The reason is that Berlin is a watery city, so the comparison trips cross
rivers as well -- {V['water_same']}% of them. A river shared by both groups is
not a rival explanation for the difference between them. It is noise in both,
and it was hiding the boundary rather than creating it. Where a river must be
crossed anyway, the river dominates and the old border adds almost nothing.
Where no river intervenes, the border's own mark is clearest."""),

    ("Where the mark survives",
     f"""The residue is not spread evenly along the line. It is largest in the
south-east, where the Wall ran beside the Spree and the Britzer canal through
{V['top1']} ({V['top1v']}) and {V['top2']} ({V['top2v']}). It is smallest, and
actually negative, in the centre at {V['bot1']} ({V['bot1v']}).

That map is a map of reconstruction money. Potsdamer Platz, the government
quarter and the new central station were all built straight across the former
line in the 1990s. The south-eastern stretch through Treptow and Johannisthal
was not. Where Berlin rebuilt across the river, the border disappeared from the
road network. Where it did not, a trace remains."""),

    ("What follows the water",
     f"""Rivers give cities their shape, and then politics borrows that shape
and calls it a border. Long after the politics is dismantled, the river is still
there, and so is the pattern of bridges it dictated.

The instrument built here is not specific to Berlin. It needs only a line, a
road network, and a set of honest comparisons. It could be pointed at Belfast's
peace lines, at the Green Line through Nicosia's suburbs, or at any of the
rivers that became borders and are now merely rivers again. Two measurements
hint at how quickly a boundary fades. A dozen would begin to tell us what makes
some fade faster than others."""),
]

CAPTIONS = {
    2: ("fig1_map.png",
        f"The reconstructed Wall over Berlin's water network. Red marks the "
        f"{V['inner_km']} km that divided East from West; grey the outer ring. "
        f"Validation: the assembled loop encloses {V['area']} km2 against West "
        f"Berlin's actual 480 km2, an error of {V['area_err']}%."),
    5: ("fig2_nulls.png",
        "The true position of the Wall (red) against rotated copies of the same "
        "curve (grey). Removing water and rail crossings moves the red line "
        "further from the null, not closer."),
}

# ---------------- markdown, for pasting into ArcGIS ----------------
md = ["# From Source to Sea: the river that carried a border",
      "",
      "*RGS Young Geographer of the Year 2026 - Key Stage 5 - StoryMap content*",
      "",
      "Paste each section below into a corresponding ArcGIS StoryMaps block.",
      "Images referenced are in this repository.", ""]
for i, (title, body) in enumerate(SECTIONS):
    md.append(f"## {title}\n")
    md.append(body.strip() + "\n")
    if i in CAPTIONS:
        img, cap = CAPTIONS[i]
        md.append(f"![{cap}]({img})\n\n*{cap}*\n")
open("storymap.md", "w", encoding="utf-8").write("\n".join(md))

# ---------------- self-contained HTML preview ----------------
def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


body = []
for i, (title, text) in enumerate(SECTIONS):
    body.append(f"<section><h2>{esc(title)}</h2>")
    for para in text.strip().split("\n\n"):
        body.append(f"<p>{esc(' '.join(para.split()))}</p>")
    if i in CAPTIONS:
        img, cap = CAPTIONS[i]
        body.append(f'<figure><img src="{img}" alt="{esc(cap)}">'
                    f"<figcaption>{esc(cap)}</figcaption></figure>")
    body.append("</section>")

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>From Source to Sea: the river that carried a border</title>
<style>
:root {{ --ink:#15181d; --muted:#5d646e; --accent:#b3202c; --bg:#fbfaf8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:17px/1.62 Georgia,'Iowan Old Style',serif; }}
header {{ padding:5rem 1.5rem 3rem; text-align:center;
  border-bottom:1px solid #e4e0da; }}
h1 {{ font-size:clamp(2rem,5vw,3.1rem); line-height:1.12; margin:0 0 .6rem;
  letter-spacing:-.02em; }}
.sub {{ color:var(--muted); font-size:1rem; font-style:italic; }}
main {{ max-width:46rem; margin:0 auto; padding:0 1.5rem 6rem; }}
section {{ padding:2.6rem 0; border-bottom:1px solid #eceae6; }}
section:last-child {{ border-bottom:0; }}
h2 {{ font-size:1.5rem; margin:0 0 1rem; color:var(--accent);
  letter-spacing:-.01em; }}
p {{ margin:0 0 1.05rem; }}
figure {{ margin:2rem 0 0; }}
img {{ width:100%; height:auto; border:1px solid #e4e0da; border-radius:3px;
  background:#fff; }}
figcaption {{ font-size:.85rem; color:var(--muted); margin-top:.6rem;
  font-style:italic; }}
footer {{ text-align:center; color:var(--muted); font-size:.85rem;
  padding:0 1.5rem 4rem; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ink:#e9e6e1; --muted:#9aa1ab; --accent:#e8737d; --bg:#14161a; }}
  header, section {{ border-color:#282c33; }}
  img {{ border-color:#282c33; background:#f5f3f0; }}
}}
</style></head><body>
<header>
  <h1>From Source to Sea:<br>the river that carried a border</h1>
  <p class="sub">How the Spree shaped the Berlin Wall &mdash; and why that makes
  the Wall so hard to measure</p>
</header>
<main>
{chr(10).join(body)}
</main>
<footer>Analysis and figures generated from open OpenStreetMap data.
Full method, code and paper: github.com/Leo-Y-Zhang/boundary-severance</footer>
</body></html>"""

open("storymap.html", "w", encoding="utf-8").write(html)
print(f"wrote storymap.md ({len(SECTIONS)} sections) and storymap.html")
print(f"key figures: Nicosia {V['cy_pct']}% (z={V['cy_z']}), "
      f"Berlin {V['be_pct']}% -> {V['nwr_pct']}% controlled")
