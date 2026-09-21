# Empire and Friendships

Code for the blog post **[[post title]]** ([[post link]]).

Using Facebook's Social Connectedness Index, this project asks how European empires shaped friendship ties between countries today. The main result: former French colonies are about **1.7 times** as connected to each other as former British colonies are, after controlling for distance, borders, shared language, shared religion and migration. The gap survives a control for the CFA franc zone and gets larger when the comparison is restricted to Africa. Ties between each former colony and its old capital are large for both empires, but too noisy to rank.

## Method in one paragraph

The outcome is the log of the SCI for each pair of countries (177 countries, 15,576 pairs). A gravity regression with a fixed effect for each country predicts connectedness from log distance, a shared border, shared official and spoken languages and shared religion; migration is added as a control in the main estimates. Colonial links come from COLDAT: each former colony is assigned to its last European colonizer. "Siblings" are two former colonies of the same empire that both became independent after 1945. Standard errors are clustered by country pair.

## Reproduce

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# download the raw data into data/ (see data/README.md)
./run_all.sh
```

Figures use [IBM Plex Sans](https://github.com/IBM/plex). The interactive maps load it from Google Fonts. The static figure needs it installed locally (macOS: `brew install --cask font-ibm-plex-sans`, or place the `.ttf` files in `fonts/`); without it, a fallback font is used.

## Scripts

| Script | What it does | Main outputs |
|---|---|---|
| `build_sci_colonial.py` | Merges SCI, CEPII Gravity and UN migrant stocks into one row per country pair | `out/pairs.csv`, `out/checkpoint.txt` |
| `analyze_sci_colonial.py` | Codes colonial links with COLDAT, runs the regressions and the hub-and-spoke comparison. `--mean-dates` runs the robustness check | `out/regressions.csv`, `out/regression_table.md`, `out/analysis_log.txt`, `out/hub_spoke.csv` |
| `make_sibling_figure.py` | Static figure of the French and British sibling estimates | `out/sibling_gap.png`, `out/sibling_gap.svg` |
| `make_maps.py` | Interactive Plotly maps and the hub-and-spoke scatter | `out/maps/*.html` |
| `style.py` | Shared font and colours | — |

## Coding decisions

- Each former colony is assigned to its **last European colonizer** in COLDAT, with four overrides where that rule picks a brief or partial administration: Morocco and Cameroon to France, Eritrea and Libya to Italy.
- **Vanuatu** (Anglo-French condominium) has no single colonizer and is left out of the sibling comparison.
- The **United States, Canada, Australia and New Zealand** are treated as settler colonies and estimated separately. South Africa is treated as a regular colony.
- **Non-sovereign territories** (for example Puerto Rico and Hong Kong) are dropped. **Kosovo** is dropped because it is not in CEPII.
- **Migrant stocks** of zero or missing are logged as zero with an indicator, so the migration control is a lower bound on the diaspora.

## Robustness

Results are unchanged to two decimal places with COLDAT mean dates instead of latest dates (`out/mean_dates/`) and when the weakest 5% of connections are dropped (column 5 of `out/regressions.csv`).

## Sources

- Johnston, D., Kuchler, T., Kulkarni, N. and Stroebel, J. (2026). The Social Connectedness Index: A large-scale dataset of social ties across geographic locations. *Data in Brief* 67, 112905.
- Bailey, M., Cao, R., Kuchler, T., Stroebel, J. and Wong, A. (2018). Social Connectedness: Measurement, Determinants, and Effects. *Journal of Economic Perspectives* 32(3): 259–280.
- Conte, M., Cotterlaz, P. and Mayer, T. (2022). The CEPII Gravity database. CEPII Working Paper 2022-05.
- United Nations, Department of Economic and Social Affairs, Population Division (2024). International Migrant Stock 2024.
- Becker, B. (2019). Introducing COLDAT: The Colonial Dates Dataset. Harvard Dataverse, doi:10.7910/DVN/T9SDEW.
- Head, K., Mayer, T. and Ries, J. (2010). The erosion of colonial trade linkages after independence. *Journal of International Economics* 81(1): 1–14.

## License

Code: MIT (see `LICENSE`). Data belongs to its original providers and is not redistributed here.
