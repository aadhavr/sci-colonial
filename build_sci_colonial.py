"""
build_sci_colonial.py

Builds one row per unordered country pair:
    SCI (Jan 2026 release)  x  CEPII Gravity V202211  x  UN DESA Migrant Stock 2024

Run from the repo root. Expects (see data/README.md):
    data/country.csv
    data/Gravity_csv_V202211/
    data/undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx

    pip install pandas numpy openpyxl pycountry
    python build_sci_colonial.py

Outputs (in ./out):
    pairs.csv                  analysis dataset
    metropole_assignment.csv   each ex-colony and the empire it is assigned to
    checkpoint.txt             everything printed below, saved
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry

# ------------------------------------------------------------------ paths
DATA = Path("data")
SCI_FILE = DATA / "country.csv"
GRAV_FILE = DATA / "Gravity_csv_V202211" / "Gravity_V202211.csv"
UN_FILE = DATA / "undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx"
OUT = Path("out")
OUT.mkdir(exist_ok=True)

GRAV_YEAR = 2020  # colonial/geographic vars are time-invariant; 2020 has full coverage
MIG_YEAR = 2024   # nearest UN year to the Jan 2026 SCI snapshot

# countries worth checking by name before any analysis
PRESENCE_CHECK = ["ER", "SS", "XK", "TL", "ME", "PT", "BE", "AO", "MZ", "CD", "NA"]

MAIN_EMPIRES = {"GBR", "FRA", "ESP"}
SMALL_EUROPEAN = {"PRT", "BEL", "NLD", "ITA", "DEU"}  # pooled: too few colonies each

log_lines = []


def say(*args):
    msg = " ".join(str(a) for a in args)
    print(msg)
    log_lines.append(msg)


def section(title):
    say("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


# ------------------------------------------------------------------ ISO helpers
MANUAL_ISO2_TO_ISO3 = {"XK": "XKX"}  # Kosovo is not in ISO 3166


def iso2_to_iso3(code):
    if code in MANUAL_ISO2_TO_ISO3:
        return MANUAL_ISO2_TO_ISO3[code]
    try:
        rec = pycountry.countries.get(alpha_2=code)
    except (KeyError, LookupError):
        rec = None
    return rec.alpha_3 if rec else None


def m49_to_iso3(num):
    try:
        rec = pycountry.countries.get(numeric=f"{int(num):03d}")
    except (KeyError, LookupError, ValueError):
        rec = None
    return rec.alpha_3 if rec else None  # regional aggregates return None


def order_pair(df, x, y):
    """Add iso3_a < iso3_b columns so every pair has one canonical order."""
    df["iso3_a"] = np.where(df[x] < df[y], df[x], df[y])
    df["iso3_b"] = np.where(df[x] < df[y], df[y], df[x])
    return df


# ================================================================== 1. SCI
section("1. SCI")

# keep_default_na=False: Namibia's ISO2 code is "NA", which pandas reads as missing
sci = pd.read_csv(SCI_FILE, dtype=str, keep_default_na=False)
say("Columns:", list(sci.columns))

need = {"user_country", "friend_country", "scaled_sci"}
if not need.issubset(sci.columns):
    sys.exit(f"Expected columns {need}. Check the file.")

sci = sci[["user_country", "friend_country", "scaled_sci"]].copy()
sci["scaled_sci"] = pd.to_numeric(sci["scaled_sci"])
say(f"Rows loaded: {len(sci):,}")

sci = sci[sci.user_country != sci.friend_country]  # drop self-pairs

iso2_codes = sorted(set(sci.user_country) | set(sci.friend_country))
say(f"Countries in SCI: {len(iso2_codes)}")

say("\nPresence check:")
for c in PRESENCE_CHECK:
    say(f"  {c}: {'present' if c in iso2_codes else 'ABSENT'}")

iso_map = {c: iso2_to_iso3(c) for c in iso2_codes}
unmapped = [c for c, v in iso_map.items() if v is None]
say("\nSCI ISO2 codes with no ISO3 (dropped):", unmapped or "none")

sci["iso3_u"] = sci.user_country.map(iso_map)
sci["iso3_f"] = sci.friend_country.map(iso_map)
sci = sci.dropna(subset=["iso3_u", "iso3_f"])
sci = order_pair(sci, "iso3_u", "iso3_f")

# The file is exactly symmetric: keep one row per unordered pair
sci = sci.drop_duplicates(subset=["iso3_a", "iso3_b"])[["iso3_a", "iso3_b", "scaled_sci"]]
sci["log_sci"] = np.log(sci.scaled_sci)
say(f"Unordered pairs: {len(sci):,}")

say("\nscaled_sci quantiles (watch the bottom; min-max scaling + DP noise):")
qs = sci.scaled_sci.quantile([0, 0.01, 0.05, 0.10, 0.25, 0.5, 0.75, 0.99, 1])
for q, v in qs.items():
    say(f"  p{int(q*100):>3}: {v:,.0f}")
say(f"  pairs with scaled_sci <= 10: {(sci.scaled_sci <= 10).sum():,}")


# ================================================================== 2. CEPII Gravity
section("2. CEPII Gravity")

WANT = [
    "year", "iso3_o", "iso3_d", "country_exists_o", "country_exists_d",
    "dist", "distw_harmonic", "contig",
    "comlang_off", "comlang_ethno", "comrelig",
    "col_dep_ever", "col_dep_end_year", "heg_o", "heg_d",
    "sibling_ever", "col45", "comcol", "colony", "smctry",
]
header = pd.read_csv(GRAV_FILE, nrows=0).columns
use = [c for c in WANT if c in header]
missing = [c for c in WANT if c not in header]
say("Columns not in this version (fine unless it is col_dep_ever/heg_o/heg_d):", missing or "none")

for critical in ["iso3_o", "iso3_d", "col_dep_ever", "heg_o", "heg_d", "dist"]:
    if critical not in use:
        sys.exit(f"Critical column {critical} missing. Send the header to fix the script.")

# The file is large: read in chunks and keep one year only
parts = []
for chunk in pd.read_csv(GRAV_FILE, usecols=use, chunksize=1_000_000, low_memory=False):
    parts.append(chunk[chunk.year == GRAV_YEAR])
grav = pd.concat(parts, ignore_index=True)

if "country_exists_o" in grav.columns:
    grav = grav[(grav.country_exists_o == 1) & (grav.country_exists_d == 1)]
grav = grav[grav.iso3_o != grav.iso3_d]

dups = grav.duplicated(subset=["iso3_o", "iso3_d"]).sum()
say(f"Directed rows for {GRAV_YEAR}: {len(grav):,}   duplicate pairs: {dups}")
grav = grav.drop_duplicates(subset=["iso3_o", "iso3_d"])

# One direction per pair is enough: symmetric vars are identical both ways,
# and heg_o / heg_d together say which side (if either) is the hegemon.
fwd = grav[grav.iso3_o < grav.iso3_d].rename(columns={"iso3_o": "iso3_a", "iso3_d": "iso3_b"})
fwd["metropole_in_pair"] = np.select(
    [fwd.heg_o == 1, fwd.heg_d == 1], [fwd.iso3_a, fwd.iso3_b], default=None
)
fwd["colonial_pair"] = (fwd.col_dep_ever == 1).astype(int)

# ---- primary metropole for each ex-colony
cp = fwd[(fwd.colonial_pair == 1) & fwd.metropole_in_pair.notna()].copy()
cp["colony_iso"] = np.where(cp.metropole_in_pair == cp.iso3_a, cp.iso3_b, cp.iso3_a)

n_heg = cp.groupby("colony_iso").metropole_in_pair.nunique()
say(f"\nEx-colonies/dependencies identified: {len(n_heg)}")
say(f"  with more than one hegemon: {(n_heg > 1).sum()}  (rule: keep the LAST one by end year)")

primary = (
    cp.sort_values("col_dep_end_year")
    .groupby("colony_iso")
    .tail(1)[["colony_iso", "metropole_in_pair", "col_dep_end_year"]]
    .rename(columns={"metropole_in_pair": "primary_metropole", "col_dep_end_year": "indep_year"})
)
primary.to_csv(OUT / "metropole_assignment.csv", index=False)
say("  Saved out/metropole_assignment.csv  -> CHECK 10-15 of these by eye")
say("  (e.g. Namibia may be assigned to South Africa, Cameroon to France or UK)")

pm = primary.set_index("colony_iso").primary_metropole

# ---- pair-level empire variables
fwd["colonial_empire"] = np.where(fwd.colonial_pair == 1, fwd.metropole_in_pair, None)

ma, mb = fwd.iso3_a.map(pm), fwd.iso3_b.map(pm)
fwd["sibling_pair"] = (ma.notna() & (ma == mb)).astype(int)
fwd["sibling_empire"] = np.where(fwd.sibling_pair == 1, ma, None)

if "sibling_ever" in fwd.columns:
    agree = (fwd.sibling_pair == (fwd.sibling_ever == 1)).mean()
    say(f"\nAgreement between own sibling_pair and CEPII sibling_ever: {agree:.1%}")


def empire_group(code):
    if code is None or (isinstance(code, float) and np.isnan(code)):
        return None
    if code in MAIN_EMPIRES:
        return code
    if code in SMALL_EUROPEAN:
        return "OTHER_EUR"
    return "OTHER"


fwd["colonial_group"] = fwd.colonial_empire.map(empire_group)
fwd["sibling_group"] = fwd.sibling_empire.map(empire_group)


# ================================================================== 3. UN migrant stock
section("3. UN DESA migrant stock")

xl = pd.ExcelFile(UN_FILE)
say("Sheets:", xl.sheet_names)
sheet = next((s for s in xl.sheet_names if s.strip().lower() == "table 1"), xl.sheet_names[0])
raw = pd.read_excel(UN_FILE, sheet_name=sheet, header=None)


def find_row(df, text):
    hits = df.index[df.apply(lambda r: r.astype(str).str.contains(text, case=False).any(), axis=1)]
    return hits[0] if len(hits) else None


hdr = find_row(raw, "Location code of destination")
if hdr is None:
    sys.exit("Could not find the header row. Open the xlsx and send the first 12 rows.")

labels = raw.iloc[hdr].astype(str).tolist()
dest_col = next(i for i, v in enumerate(labels) if "code of destination" in v.lower())
orig_col = next(i for i, v in enumerate(labels) if "code of origin" in v.lower())

# Year labels sit on the header row or next to it. The first MIG_YEAR column is both sexes.
year_col = None
for r in range(max(0, hdr - 2), hdr + 3):
    row = raw.iloc[r].tolist()
    hits = [i for i, v in enumerate(row) if str(v).split(".")[0].strip() == str(MIG_YEAR)]
    if hits:
        year_col = hits[0]
        say(f"Year {MIG_YEAR} found on row {r}, column {year_col} (both sexes block)")
        break
if year_col is None:
    sys.exit(f"Could not find year {MIG_YEAR}. Send the header rows.")

mig = raw.iloc[hdr + 1:, [dest_col, orig_col, year_col]].copy()
mig.columns = ["m49_d", "m49_o", "stock"]
mig = mig.apply(pd.to_numeric, errors="coerce").dropna(subset=["m49_d", "m49_o"])

mig["iso_d"] = mig.m49_d.map(m49_to_iso3)   # regions and aggregates map to None
mig["iso_o"] = mig.m49_o.map(m49_to_iso3)
mig = mig.dropna(subset=["iso_d", "iso_o"])
mig = mig[mig.iso_d != mig.iso_o]
mig["stock"] = mig.stock.fillna(0)
say(f"Country-to-country corridors with data: {len(mig):,}")

mig = order_pair(mig, "iso_d", "iso_o")
mig = mig.groupby(["iso3_a", "iso3_b"], as_index=False).stock.sum()  # both directions
mig = mig.rename(columns={"stock": "mig_stock"})


# ================================================================== 4. merge
section("4. Merge")

keep = [c for c in [
    "iso3_a", "iso3_b", "dist", "distw_harmonic", "contig", "comlang_off", "comlang_ethno",
    "comrelig", "smctry", "colonial_pair", "colonial_empire", "colonial_group",
    "col_dep_end_year", "sibling_pair", "sibling_empire", "sibling_group", "sibling_ever",
] if c in fwd.columns]

pairs = sci.merge(fwd[keep], on=["iso3_a", "iso3_b"], how="left", indicator="_grav")
no_grav = pairs[pairs._grav == "left_only"]
say(f"SCI pairs with no CEPII match: {len(no_grav):,} of {len(pairs):,}")
miss_c = sorted(set(no_grav.iso3_a) | set(no_grav.iso3_b))
cepii_c = set(fwd.iso3_a) | set(fwd.iso3_b)
say("  SCI countries never found in CEPII:", [c for c in miss_c if c not in cepii_c] or "none")
pairs = pairs[pairs._grav == "both"].drop(columns="_grav")

pairs = pairs.merge(mig, on=["iso3_a", "iso3_b"], how="left")
pairs["mig_zero"] = (pairs.mig_stock.isna() | (pairs.mig_stock == 0)).astype(int)
pairs["mig_stock"] = pairs.mig_stock.fillna(0)
pairs["log1p_mig"] = np.log1p(pairs.mig_stock)
pairs["log_dist"] = np.log(pairs.dist)

pairs["years_since_indep"] = np.where(
    pairs.colonial_pair == 1, 2026 - pairs.col_dep_end_year, np.nan
)

say(f"Final pairs: {len(pairs):,}")
say(f"Countries: {len(set(pairs.iso3_a) | set(pairs.iso3_b))}")
say(f"Pairs with zero/missing migrant stock: {pairs.mig_zero.mean():.1%}")


# ================================================================== 5. checkpoint
section("5. CHECKPOINT: colonial pairs that survive, by empire")

col = pairs[pairs.colonial_pair == 1]
say(f"Colonial pairs in final sample: {len(col)}\n")
say("By metropole (raw):")
say(col.colonial_empire.value_counts().to_string())
say("\nBy analysis group:")
say(col.colonial_group.value_counts().to_string())

section("5b. Sibling pairs (colony-to-colony, same empire)")
sib = pairs[pairs.sibling_pair == 1]
say(f"Sibling pairs: {len(sib)}\n")
say(sib.sibling_empire.value_counts().head(12).to_string())

section("5c. Sanity: 15 most connected colonial pairs")
top = col.sort_values("scaled_sci", ascending=False).head(15)
say(top[["iso3_a", "iso3_b", "colonial_empire", "scaled_sci", "mig_stock"]].to_string(index=False))

section("5d. Sanity: 10 least connected colonial pairs")
bot = col.sort_values("scaled_sci").head(10)
say(bot[["iso3_a", "iso3_b", "colonial_empire", "scaled_sci", "mig_stock"]].to_string(index=False))


# ================================================================== save
pairs.to_csv(OUT / "pairs.csv", index=False)
(OUT / "checkpoint.txt").write_text("\n".join(log_lines))
say("\nSaved out/pairs.csv and out/checkpoint.txt")
