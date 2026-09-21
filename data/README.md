# Data

Raw data is not included in this repository. Download each source and place it here so the layout matches:

```
data/
├── country.csv                                              # SCI, country-to-country
├── Gravity_csv_V202211/
│   ├── Gravity_V202211.csv
│   └── Countries_V202211.csv
├── undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx
├── coldat/
│   └── COLDAT_dyads.csv
└── ne_50m_admin_0_countries.zip                             # downloaded automatically by make_maps.py
```

| File | Source | Where to get it |
|---|---|---|
| `country.csv` | Social Connectedness Index, January 2026 release, country-to-country file | [Humanitarian Data Exchange](https://data.humdata.org/dataset/social-connectedness-index) |
| `Gravity_csv_V202211/` | CEPII Gravity database, version 202211 (CSV) | [CEPII](https://www.cepii.fr/cepii/en/bdd_modele/bdd_modele_item.asp?id=8) |
| `undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx` | UN DESA International Migrant Stock 2024, destination and origin | [UN DESA](https://www.un.org/development/desa/pd/content/international-migrant-stock) |
| `coldat/COLDAT_dyads.csv` | Colonial Dates Dataset (COLDAT), Becker | [Harvard Dataverse](https://doi.org/10.7910/DVN/T9SDEW) |
| `ne_50m_admin_0_countries.zip` | Natural Earth 1:50m admin-0 countries | Downloaded by `make_maps.py` on first run |

Each source has its own terms of use and citation requirements. Cite them as listed in the main README.
