#!/usr/bin/env bash
# Rebuild everything from the raw data in data/. Run from the repo root.
set -euo pipefail

python build_sci_colonial.py                  # step 1: SCI x CEPII x UN migrant stock -> out/pairs.csv
python analyze_sci_colonial.py                # step 2: COLDAT coding, regressions, hub-and-spoke
python analyze_sci_colonial.py --mean-dates   # robustness: COLDAT mean dates -> out/mean_dates/
python make_sibling_figure.py                 # static figure -> out/sibling_gap.png / .svg
python make_maps.py                           # interactive maps and scatter -> out/maps/
