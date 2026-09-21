"""
analyze_sci_colonial.py   (step 2 — run after build_sci_colonial.py)

1. Recodes colonial links with COLDAT (replaces the CEPII hegemon coding)
2. Runs the regression table
3. Builds the hub-and-spoke comparison for post-1945 British vs French colonies

Needs:
    out/pairs.csv                       (from step 1)
    data/coldat/COLDAT_dyads.csv

    pip install pyfixest matplotlib
    python analyze_sci_colonial.py                 # main run
    python analyze_sci_colonial.py --mean-dates    # robustness: COLDAT mean dates -> out/mean_dates/

Outputs (in ./out):
    coldat_name_matches.csv   every colonized COLDAT name and the ISO3 it matched -> CHECK
    regressions.csv           the table
    hub_spoke.csv             one row per post-1945 colony
    hub_spoke.png             the figure
    analysis_log.txt          everything printed
"""

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pycountry
import pyfixest as pf

from style import setup_matplotlib

setup_matplotlib()

# --mean-dates runs the robustness check with COLDAT's mean dates; its outputs go
# to out/mean_dates/ so they do not overwrite the main run.
MEAN_DATES = "--mean-dates" in sys.argv
PAIRS_FILE = Path("out") / "pairs.csv"
COLDAT_FILE = Path("data") / "coldat" / "COLDAT_dyads.csv"
OUT = Path("out") / "mean_dates" if MEAN_DATES else Path("out")
OUT.mkdir(parents=True, exist_ok=True)

DATE = "mean" if MEAN_DATES else "max"
SNAPSHOT_YEAR = 2026

SETTLER = {"USA", "CAN", "AUS", "NZL"}
SETTLER_INCLUDE_ZAF = False          # decision: South Africa. State it in the post.
if SETTLER_INCLUDE_ZAF:
    SETTLER = SETTLER | {"ZAF"}

# Not independent states: dropped from the whole sample
NON_SOVEREIGN = {
    "PRI", "GUM", "VIR", "ASM", "MNP", "REU", "GLP", "MTQ", "GUF", "MYT", "NCL", "PYF",
    "BMU", "CYM", "TCA", "VGB", "AIA", "MSR", "GIB", "FRO", "GRL", "ABW", "CUW", "SXM",
    "BES", "GGY", "JEY", "IMN", "ESH", "HKG", "MAC", "SPM", "WLF", "FLK", "SHN", "NIU",
    "COK", "TKL", "NFK", "CXR", "CCK", "IOT", "PCN",
}

EMPIRE_ISO = {
    "belgium": "BEL", "britain": "GBR", "france": "FRA", "germany": "DEU",
    "italy": "ITA", "netherlands": "NLD", "portugal": "PRT", "spain": "ESP",
}
MAIN = ["GBR", "FRA", "ESP"]

CTRL = "log_dist + contig + comlang_off + comlang_ethno + comrelig"
MIG = "log1p_mig + mig_zero"

log_lines = []


def say(*a):
    m = " ".join(str(x) for x in a)
    print(m)
    log_lines.append(m)


def section(t):
    say("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


# ================================================================== 1. COLDAT names -> ISO3
section("1. COLDAT name matching")

MANUAL = {
    "Congo, Democratic Republic of": "COD", "Democratic Republic of the Congo": "COD",
    "Congo, Dem. Rep.": "COD", "Congo (Kinshasa)": "COD", "DR Congo": "COD", "Zaire": "COD",
    "Congo, Democratic Republic of the": "COD", "Congo, Dem. Rep. of the": "COD",
    "Congo": "COG", "Republic of the Congo": "COG", "Congo, Republic of": "COG",
    "Congo, Rep.": "COG", "Congo (Brazzaville)": "COG", "Congo, Republic of the": "COG",
    "Ivory Coast": "CIV", "Cote d'Ivoire": "CIV", "Côte d'Ivoire": "CIV",
    "Cape Verde": "CPV", "Cabo Verde": "CPV", "Swaziland": "SWZ", "Eswatini": "SWZ",
    "Burma": "MMR", "Myanmar": "MMR", "East Timor": "TLS", "Timor-Leste": "TLS",
    "Gambia": "GMB", "The Gambia": "GMB", "Gambia, The": "GMB",
    "Bahamas": "BHS", "The Bahamas": "BHS", "Bahamas, The": "BHS",
    "Micronesia": "FSM", "Micronesia, Federated States of": "FSM",
    "Laos": "LAO", "Vietnam": "VNM", "Viet Nam": "VNM", "Syria": "SYR", "Tanzania": "TZA",
    "Russia": "RUS", "South Korea": "KOR", "North Korea": "PRK",
    "Korea, South": "KOR", "Korea, North": "PRK", "Bolivia": "BOL", "Venezuela": "VEN",
    "Iran": "IRN", "Moldova": "MDA", "Macedonia": "MKD", "North Macedonia": "MKD",
    "Brunei": "BRN", "Palestine": "PSE", "Kosovo": "XKX", "Taiwan": "TWN",
    "Czech Republic": "CZE", "Sao Tome and Principe": "STP", "São Tomé and Príncipe": "STP",
    "Saint Kitts and Nevis": "KNA", "St. Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA", "St. Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT", "St. Vincent and the Grenadines": "VCT",
    "Western Sahara": "ESH", "Hong Kong": "HKG", "Macau": "MAC", "Macao": "MAC",
    "Turkey": "TUR", "United States": "USA", "United States of America": "USA",
    "United Kingdom": "GBR", "Libya": "LBY", "Egypt": "EGY",
    # COLDAT's own spellings (from coldat_name_matches.csv)
    "Antigua & Barbuda": "ATG",
    "Congo - Brazzaville": "COG",
    "Congo - Kinshasa": "COD",
    "Côte d\u2019Ivoire": "CIV",          # curly apostrophe
    "Micronesia (Federated States of)": "FSM",
    "Myanmar (Burma)": "MMR",
    "St. Kitts & Nevis": "KNA",
    "St. Vincent & Grenadines": "VCT",
    "São Tomé & Príncipe": "STP",
    "Trinidad & Tobago": "TTO",
}


def name_to_iso3(name):
    if name in MANUAL:
        return MANUAL[name], "manual"
    try:
        return pycountry.countries.lookup(name).alpha_3, "exact"
    except LookupError:
        pass
    try:
        hit = pycountry.countries.search_fuzzy(name)[0]
        return hit.alpha_3, f"FUZZY -> {hit.name}"
    except LookupError:
        return None, "NO MATCH"


dy = pd.read_csv(COLDAT_FILE)
dy = dy[dy.col == 1].copy()

names = sorted(dy.country.unique())
match = pd.DataFrame([(n, *name_to_iso3(n)) for n in names], columns=["coldat_name", "iso3", "method"])
match.to_csv(OUT / "coldat_name_matches.csv", index=False)

say(f"Colonized countries in COLDAT: {len(names)}")
say("Match methods:", match.method.str.split(" ").str[0].value_counts().to_dict())
risky = match[match.method.str.startswith(("FUZZY", "NO"))]
if len(risky):
    say("\nCHECK THESE (fuzzy or unmatched):")
    say(risky.to_string(index=False))

dy = dy.merge(match[["coldat_name", "iso3"]], left_on="country", right_on="coldat_name")
dy = dy.dropna(subset=["iso3"])
dy["colony_iso"] = dy.iso3
dy["empire"] = dy.colonizer.map(EMPIRE_ISO)
dy["end"] = dy[f"colend_{DATE}"]
say(f"\nColonial links with no end year (still dependent or missing): {dy.end.isna().sum()}")

# ---- primary empire = European colonizer with the latest end year
prim = dy.assign(end_f=dy.end.fillna(9999)).sort_values("end_f").groupby("colony_iso").tail(1)
pm = prim.set_index("colony_iso").empire.copy()
pe = prim.set_index("colony_iso").end.copy()

# The "latest end year" rule picks a minor colonizer in a few cases
# (Spanish Sahara/Ifni for Morocco, British Southern Cameroons, the 1941-51
# British administration of Eritrea). Override with the main colonizer.
PRIMARY_OVERRIDE = {"MAR": "FRA", "CMR": "FRA", "ERI": "ITA", "LBY": "ITA"}
# Anglo-French condominium: no single primary empire, so no sibling status
NO_PRIMARY = {"VUT"}
for c, E in PRIMARY_OVERRIDE.items():
    row = dy[(dy.colony_iso == c) & (dy.empire == E)]
    if len(row):
        pm[c], pe[c] = E, row.end.iloc[0]
    else:
        say(f"  override {c}->{E} skipped: no such COLDAT link")

for c in NO_PRIMARY:
    pm = pm.drop(c, errors="ignore")
    pe = pe.drop(c, errors="ignore")

multi = (dy.groupby("colony_iso")
           .apply(lambda g: ", ".join(f"{e} {int(x)}" for e, x in zip(g.empire, g.end)))
           .loc[lambda s: dy.groupby("colony_iso").size().loc[s.index] > 1])
say(f"\nColonies with more than one European colonizer: {len(multi)}")
for c, txt in multi.items():
    say(f"  {c}: {txt}   -> primary {pm.get(c, 'none')}{' (override)' if c in PRIMARY_OVERRIDE else ''}")

say("\nKey cases (these were missing or wrong in CEPII):")
for c in ["NGA", "IDN", "COD", "EGY", "MAR", "MDG", "MYS", "USA", "LBR", "SDN", "NAM", "ERI", "IND", "LKA"]:
    say(f"  {c}: {pm.get(c, '— not a COLDAT colony')}  end={pe.get(c, '')}")


# ================================================================== 2. recode pairs
section("2. Recode pairs")

pairs = pd.read_csv(PAIRS_FILE, keep_default_na=False, na_values=[""])
present_ns = sorted((set(pairs.iso3_a) | set(pairs.iso3_b)) & NON_SOVEREIGN)
say("Non-sovereign territories found in SCI and dropped:", present_ns or "none")
pairs = pairs[~pairs.iso3_a.isin(NON_SOVEREIGN) & ~pairs.iso3_b.isin(NON_SOVEREIGN)].copy()

# pair-level colonial links (every colonizer, not only the primary one)
links = dy[["colony_iso", "empire", "end"]].copy()
links["iso3_a"] = np.where(links.colony_iso < links.empire, links.colony_iso, links.empire)
links["iso3_b"] = np.where(links.colony_iso < links.empire, links.empire, links.colony_iso)
links = links.drop_duplicates(["iso3_a", "iso3_b"])
pairs = pairs.merge(
    links[["iso3_a", "iso3_b", "empire", "end", "colony_iso"]].rename(
        columns={"empire": "link_empire", "end": "link_end", "colony_iso": "link_colony"}
    ),
    on=["iso3_a", "iso3_b"], how="left",
)

is_link = pairs.link_empire.notna()
is_settler = pairs.link_colony.isin(SETTLER)
pairs["settler_link"] = (is_link & is_settler).astype(int)
pairs["overseas_colonial"] = (is_link & ~is_settler).astype(int)
pairs["other_dependency"] = ((pairs.colonial_pair == 1) & ~is_link).astype(int)

for e in MAIN:
    pairs[f"col_{e}"] = ((pairs.overseas_colonial == 1) & (pairs.link_empire == e)).astype(int)
pairs["col_OTHEREUR"] = (
    (pairs.overseas_colonial == 1) & ~pairs.link_empire.isin(MAIN)
).astype(int)

# years since the link ended, in decades, centered within colonial pairs
yrs = SNAPSHOT_YEAR - pairs.link_end
mu = yrs[pairs.overseas_colonial == 1].mean()
pairs["col_x_decades"] = np.where(pairs.overseas_colonial == 1, (yrs - mu) / 10, 0.0)
say(f"Mean years since end, overseas colonial links: {mu:.0f}")

# siblings: same primary empire, neither is a settler colony
ea, eb = pairs.iso3_a.map(pm), pairs.iso3_b.map(pm)
ya, yb = pairs.iso3_a.map(pe), pairs.iso3_b.map(pe)
sib = ea.notna() & (ea == eb) & ~pairs.iso3_a.isin(SETTLER) & ~pairs.iso3_b.isin(SETTLER)
post45 = (ya >= 1945) & (yb >= 1945)
pairs["sibling45"] = (sib & post45).astype(int)
pairs["sibling_pre45"] = (sib & ~post45).astype(int)
pairs["sib45_GBR"] = (sib & post45 & (ea == "GBR")).astype(int)
pairs["sib45_FRA"] = (sib & post45 & (ea == "FRA")).astype(int)
pairs["sib45_OTHER"] = (sib & post45 & ~ea.isin(["GBR", "FRA"])).astype(int)

say("\nCounts in sample:")
for v in ["overseas_colonial", "settler_link", "other_dependency", "col_GBR", "col_FRA",
          "col_ESP", "col_OTHEREUR", "sibling45", "sib45_GBR", "sib45_FRA", "sib45_OTHER",
          "sibling_pre45"]:
    say(f"  {v:<18} {pairs[v].sum():>5}")


# ================================================================== 3. regressions
section("3. Regressions (directed, origin + destination FE, clustered by pair)")

AFRICA = {
    "DZA","AGO","BEN","BWA","BFA","BDI","CPV","CMR","CAF","TCD","COM","COD","COG","CIV","DJI",
    "EGY","GNQ","ERI","SWZ","ETH","GAB","GMB","GHA","GIN","GNB","KEN","LSO","LBR","LBY","MDG",
    "MWI","MLI","MRT","MUS","MAR","MOZ","NAM","NER","NGA","RWA","STP","SEN","SYC","SLE","SOM",
    "ZAF","SSD","SDN","TZA","TGO","TUN","UGA","ZMB","ZWE",
}
CFA = {"BEN","BFA","CIV","GNB","MLI","NER","SEN","TGO","CMR","CAF","TCD","COG","GNQ","GAB"}
pairs["africa_pair"] = (pairs.iso3_a.isin(AFRICA) & pairs.iso3_b.isin(AFRICA)).astype(int)
pairs["cfa_pair"] = (pairs.iso3_a.isin(CFA) & pairs.iso3_b.isin(CFA)).astype(int)

pairs["pair_id"] = pairs.iso3_a + "_" + pairs.iso3_b
dd = pd.concat([
    pairs.assign(o=pairs.iso3_a, d=pairs.iso3_b),
    pairs.assign(o=pairs.iso3_b, d=pairs.iso3_a),
], ignore_index=True)

LINK = "settler_link + other_dependency + sibling_pre45"
specs = {
    "(1) baseline":   f"log_sci ~ overseas_colonial + sibling45 + {LINK} + {CTRL} | o + d",
    "(2) +migration": f"log_sci ~ overseas_colonial + sibling45 + {LINK} + {CTRL} + {MIG} | o + d",
    "(3) x empire":   f"log_sci ~ col_GBR + col_FRA + col_ESP + col_OTHEREUR + sib45_GBR + sib45_FRA + sib45_OTHER + {LINK} + {CTRL} + {MIG} | o + d",
    "(4) x time":     f"log_sci ~ overseas_colonial + col_x_decades + sibling45 + {LINK} + {CTRL} + {MIG} | o + d",
}
p5 = pairs.scaled_sci.quantile(0.05)
samples = {k: dd for k in specs}
specs["(5) (3) drop bottom 5%"] = specs["(3) x empire"]
samples["(5) (3) drop bottom 5%"] = dd[dd.scaled_sci > p5]
EMP = "col_GBR + col_FRA + col_ESP + col_OTHEREUR"
SIB = "sib45_GBR + sib45_FRA + sib45_OTHER"
specs["(6) (3) + CFA zone"] = f"log_sci ~ {EMP} + {SIB} + cfa_pair + {LINK} + {CTRL} + {MIG} | o + d"
samples["(6) (3) + CFA zone"] = dd
specs["(7) (3) Africa only"] = f"log_sci ~ {SIB} + cfa_pair + {LINK} + {CTRL} + {MIG} | o + d"
samples["(7) (3) Africa only"] = dd[dd.africa_pair == 1]
specs["(8) time within empire"] = f"log_sci ~ {EMP} + col_x_decades + sibling45 + {LINK} + {CTRL} + {MIG} | o + d"
samples["(8) time within empire"] = dd

KEEP = ["overseas_colonial", "col_GBR", "col_FRA", "col_ESP", "col_OTHEREUR", "col_x_decades",
        "sibling45", "sib45_GBR", "sib45_FRA", "sib45_OTHER", "cfa_pair", "settler_link", "other_dependency",
        "sibling_pre45", "log_dist", "contig", "comlang_off", "log1p_mig"]


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


cols, fits = {}, {}
for name, f in specs.items():
    fit = pf.feols(f, data=samples[name], vcov={"CRV1": "pair_id"})
    t = fit.tidy()
    cell = {v: f"{t.loc[v, 'Estimate']:.3f}{stars(t.loc[v, 'Pr(>|t|)'])} ({t.loc[v, 'Std. Error']:.3f})"
            for v in KEEP if v in t.index}
    cell["N (directed)"] = f"{getattr(fit, '_N', len(samples[name])):,}"
    cols[name] = cell
    fits[name] = fit

table = pd.DataFrame(cols).reindex(KEEP + ["N (directed)"]).fillna("")
table.to_csv(OUT / "regressions.csv")
say(table.to_string())
say("\nOutcome: log scaled SCI. SE clustered by unordered pair. * p<.1 ** p<.05 *** p<.01")
say("Read coefficients as log points: exp(b) - 1 = % difference in friendship probability.")

section("3b. Is Britain different from France? (difference of coefficients)")


def diff_test(fit, a, b):
    t = fit.tidy()
    if a not in t.index or b not in t.index:
        return None
    d = t.loc[a, "Estimate"] - t.loc[b, "Estimate"]
    try:
        names = list(fit._coefnames)
        V = np.asarray(fit._vcov)
        i, j = names.index(a), names.index(b)
        se = np.sqrt(V[i, i] + V[j, j] - 2 * V[i, j])
        note = ""
    except Exception:
        se = np.hypot(t.loc[a, "Std. Error"], t.loc[b, "Std. Error"])
        note = "  (covariance unavailable: SE ignores it)"
    z = d / se
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / np.sqrt(2))))
    return f"{a} - {b} = {d:.3f} (SE {se:.3f}), p = {p:.3f}{note}"


for name in ["(3) x empire", "(6) (3) + CFA zone", "(7) (3) Africa only"]:
    for a, b in [("col_FRA", "col_GBR"), ("sib45_FRA", "sib45_GBR")]:
        r = diff_test(fits[name], a, b)
        if r:
            say(f"  {name:<22} {r}")


# ================================================================== 4. hub and spoke
section("4. Hub and spoke: post-1945 British vs French colonies")

base = dd.dropna(subset=["log_sci", "log_dist", "contig", "comlang_off", "comlang_ethno", "comrelig"]).copy()
gfit = pf.feols(f"log_sci ~ {CTRL} | o + d", data=base)
res = np.asarray(gfit.resid())
if len(res) != len(base):
    raise SystemExit("Residual length mismatch: pyfixest dropped rows. Send this message.")
base["resid"] = res
R = dict(zip(zip(base.o, base.d), base.resid))

# saved for make_maps.py
base[["o", "d", "resid", "log_sci"]].to_csv(OUT / "gravity_residuals.csv", index=False)
pd.DataFrame({
    "iso3": pm.index,
    "empire": pm.values,
    "end": pe.reindex(pm.index).values,
    "settler": pm.index.isin(list(SETTLER)),
}).to_csv(OUT / "primary_empire.csv", index=False)

sample_c = set(pairs.iso3_a) | set(pairs.iso3_b)
c45 = [c for c in pm.index
       if pm[c] in ("GBR", "FRA") and pe[c] >= 1945 and c not in SETTLER and c in sample_c]

rows = []
for c in c45:
    E = pm[c]
    sibs = [R[(c, s)] for s in c45 if pm[s] == E and s != c and (c, s) in R]
    cross = [R[(c, s)] for s in c45 if pm[s] != E and (c, s) in R]
    rows.append({
        "colony": c, "empire": E, "indep": int(pe[c]),
        "metropole_resid": R.get((c, E), np.nan),
        "sibling_resid": np.mean(sibs) if sibs else np.nan,
        "cross_empire_resid": np.mean(cross) if cross else np.nan,
        "n_sibs": len(sibs),
    })
hs = pd.DataFrame(rows)
hs["hub_gap"] = hs.metropole_resid - hs.sibling_resid          # >0: ties run through the capital
hs["sibling_premium"] = hs.sibling_resid - hs.cross_empire_resid  # >0: colonies of one empire cluster
hs.to_csv(OUT / "hub_spoke.csv", index=False)

say(f"Colonies: {hs.empire.value_counts().to_dict()}")
say("\nMeans by empire (residual log SCI, after geography, language, religion, country FE):")
say(hs.groupby("empire")[["metropole_resid", "sibling_resid", "cross_empire_resid",
                          "hub_gap", "sibling_premium"]].mean().round(2).to_string())

fig, ax = plt.subplots(figsize=(8, 7))
for E, colr in [("GBR", "#1f4e79"), ("FRA", "#b03a2e")]:
    s = hs[hs.empire == E]
    ax.scatter(s.sibling_resid, s.metropole_resid, c=colr, label=E, alpha=0.8)
    for _, r in s.iterrows():
        ax.annotate(r.colony, (r.sibling_resid, r.metropole_resid), fontsize=7,
                    xytext=(3, 3), textcoords="offset points", color=colr)
lim = [np.nanmin(hs[["sibling_resid", "metropole_resid"]].values) - 0.5,
       np.nanmax(hs[["sibling_resid", "metropole_resid"]].values) + 0.5]
ax.plot(lim, lim, ls="--", c="grey", lw=1)
ax.set_xlabel("Connectedness to sibling colonies (residual log SCI)")
ax.set_ylabel("Connectedness to the metropole (residual log SCI)")
ax.set_title("Above the line: ties run through the capital")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "hub_spoke.png", dpi=200)

(OUT / "analysis_log.txt").write_text("\n".join(log_lines))
say("\nSaved regressions.csv, hub_spoke.csv, hub_spoke.png, analysis_log.txt in out/")
