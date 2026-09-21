"""
make_sibling_figure.py  (run after analyze_sci_colonial.py)

Reads out/regressions.csv and draws the central figure of the post:
French vs British post-1945 sibling coefficients in specs (3), (6), (7),
shown as friendship multiples, exp(b), with 95% intervals.

    python make_sibling_figure.py   ->  out/sibling_gap.png, out/sibling_gap.svg
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from style import EMP_COL, MUTED, setup_matplotlib

setup_matplotlib()

OUT = Path("out")
tab = pd.read_csv(OUT / "regressions.csv", index_col=0)

SPECS = {
    "(3) x empire": "All former colonies",
    "(6) (3) + CFA zone": "Controlling for\nthe CFA franc zone",
    "(7) (3) Africa only": "African pairs only",
}
EMPIRES = [("sib45_FRA", "Former French colonies", EMP_COL["FRA"]),
           ("sib45_GBR", "Former British colonies", EMP_COL["GBR"])]
PAT = re.compile(r"(-?\d+\.\d+)\**\s*\((\d+\.\d+)\)")


def parse(cell):
    m = PAT.search(str(cell))
    if not m:
        raise SystemExit(f"Could not parse table cell: {cell!r}")
    return float(m.group(1)), float(m.group(2))


fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(SPECS))
offset = {"sib45_FRA": -0.12, "sib45_GBR": 0.12}

for var, label, col in EMPIRES:
    b, se = zip(*(parse(tab.loc[var, s]) for s in SPECS))
    b, se = np.array(b), np.array(se)
    mult, lo, hi = np.exp(b), np.exp(b - 1.96 * se), np.exp(b + 1.96 * se)
    xs = x + offset[var]
    ax.errorbar(xs, mult, yerr=[mult - lo, hi - mult], fmt="o", color=col,
                capsize=4, ms=7, lw=1.5, label=label)
    for xi, m in zip(xs, mult):
        ax.annotate(f"{m:.2f}×", (xi, m), xytext=(8, -3), textcoords="offset points",
                    fontsize=9, color=col)

ax.axhline(1, color=MUTED, lw=1, ls="--")
ax.text(len(SPECS) - 0.5, 1.02, "no extra connection", fontsize=8, color=MUTED,
        ha="right", va="bottom")
ax.set_xticks(x)
ax.set_xticklabels(SPECS.values())
ax.set_xlim(-0.5, len(SPECS) - 0.5)
ax.set_ylabel("Friendship multiple between two former colonies\nof the same empire (95% CI)")
ax.set_title("Former French colonies stay connected to each other.\nFormer British colonies, much less.",
             loc="left", fontsize=12)
ax.legend(frameon=False, loc="upper right")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.text(0.01, 0.01,
         "Post-1945 independence. Log SCI on distance, contiguity, language, religion, migrant stock, "
         "country FE; SE clustered by pair.\nSources: Social Connectedness Index (Jan 2026), "
         "CEPII Gravity, UN DESA Migrant Stock 2024, COLDAT.",
         fontsize=7, color=MUTED, va="bottom")
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT / "sibling_gap.png", dpi=200)
fig.savefig(OUT / "sibling_gap.svg")
print("Saved out/sibling_gap.png and out/sibling_gap.svg")
