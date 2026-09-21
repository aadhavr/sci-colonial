"""
make_maps.py  (run after analyze_sci_colonial.py)

Builds four interactive maps as standalone HTML files in out/maps/:

  1_friend_picker.html    click any country: who it is friends with, beyond what
                          distance, borders, language and religion predict
  2_empires.html          which European empire ruled where, and until when
  3_sibling_network.html  links between former colonies of the same empire that beat
                          the gravity prediction; French vs British; ties to the capital
  4_hub_spoke.html        each post-1945 colony: tie to the capital, tie to siblings,
                          sibling premium
  hub_spoke_scatter.html  the same three numbers as an interactive scatter

All text is set in IBM Plex Sans (loaded from Google Fonts inside each file).

Run from the repo root. Needs (from step 2): out/gravity_residuals.csv, out/primary_empire.csv, out/hub_spoke.csv

    pip install plotly geopandas
    python make_maps.py

geopandas downloads Natural Earth country shapes once (about 2 MB) to place lines
and markers. Without it, maps 1, 2 and 4 are still built, but map 3 is skipped and
small island states get no markers.
"""

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pycountry

from style import (DIV, EMP_COL, EMP_NAME, FONT_READY_JS, MUTED, GRID, TEXT,
                   hoverlabel, inject_font, plotly_font, title_font)

OUT = Path("out")
MAPS = OUT / "maps"
NE_URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
NE_LOCAL = Path("data") / "ne_50m_admin_0_countries.zip"

DEFAULT_COUNTRY = "SEN"
SMALL_AREA = 1.5  # square degrees: below this a country gets a marker, not only a fill

CAPITALS = {"FRA": (48.86, 2.35), "GBR": (51.51, -0.13)}  # hub lines end at the capital

CLIP = 2.5
TICKV = [-2, -1, 0, 1, 2]
TICKT = [f"{np.exp(v):.2g}×" for v in TICKV]

GEO = dict(
    projection_type="natural earth", showframe=False, showcoastlines=False,
    showcountries=True, countrycolor="white", countrywidth=0.4,
    showland=True, landcolor="#e6e6e6", showocean=False,
    resolution=50, bgcolor="rgba(0,0,0,0)",
)
LAYOUT = dict(
    autosize=True, margin=dict(l=0, r=0, t=44, b=0), paper_bgcolor="white",
    font=plotly_font(13),
    hoverlabel=hoverlabel(),
)


def title_(text):
    return dict(text=text, x=0.01, xanchor="left", y=0.985, yanchor="top", font=title_font())
CONFIG = {"displaylogo": False, "responsive": True,
          "modeBarButtonsToRemove": ["select2d", "lasso2d"]}
ZOOM = dict(  # second menu on the network and hub maps
    type="buttons", direction="right", x=0.99, xanchor="right", y=1.0, yanchor="top",
    bgcolor="white",
    buttons=[
        dict(label="World", method="relayout",
             args=[{"geo.center.lat": 15, "geo.center.lon": 10, "geo.projection.scale": 1}]),
        dict(label="Africa", method="relayout",
             args=[{"geo.center.lat": 3, "geo.center.lon": 15, "geo.projection.scale": 2.6}]),
        dict(label="Caribbean", method="relayout",
             args=[{"geo.center.lat": 15, "geo.center.lon": -70, "geo.projection.scale": 4}]),
    ],
)


# ------------------------------------------------------------------ helpers
def cname(iso3):
    c = pycountry.countries.get(alpha_3=iso3)
    if c is None:
        return iso3
    return getattr(c, "common_name", None) or c.name


def save(fig, name, post_script=None):
    MAPS.mkdir(parents=True, exist_ok=True)
    path = MAPS / name
    scripts = [FONT_READY_JS] + ([post_script] if post_script else [])
    fig.write_html(path, include_plotlyjs="cdn", full_html=True, config=CONFIG,
                   post_script=scripts, default_width="100%", default_height="100%")
    inject_font(path)
    print("saved", path)


def load_anchors():
    """ISO3 -> (lat, lon, area). Point inside the largest polygon; capitals for FRA/GBR."""
    try:
        import geopandas as gpd
    except ImportError:
        print("geopandas not installed: map 3 skipped, no small-state markers")
        return None
    try:
        if not NE_LOCAL.exists():
            print("downloading Natural Earth country shapes ...")
            urllib.request.urlretrieve(NE_URL, NE_LOCAL)
        world = gpd.read_file(NE_LOCAL)
    except Exception as e:
        print(f"Could not load Natural Earth ({e}): map 3 skipped, no small-state markers")
        return None

    cols = {c.upper(): c for c in world.columns}
    keys = [cols[k] for k in ["ISO_A3_EH", "ISO_A3", "ADM0_A3"] if k in cols]
    out = {}
    for _, row in world.iterrows():
        iso = next((str(row[k]) for k in keys if str(row[k]) not in ("-99", "None", "nan")), None)
        g = row.geometry
        if iso is None or g is None or iso in out:
            continue
        area = g.area
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda p: p.area)
        pt = g.representative_point()
        out[iso] = (pt.y, pt.x, area)
    for k, (la, lo) in CAPITALS.items():
        if k in out:
            out[k] = (la, lo, out[k][2])
    print(f"anchors for {len(out)} countries")
    return out


def post45(prim, empires=("FRA", "GBR")):
    p = prim[(prim.end >= 1945) & ~prim.settler & prim.empire.isin(empires)]
    return dict(zip(p.iso3, p.empire)), dict(zip(p.iso3, p.end))


# ------------------------------------------------------------------ map 1
def map_friend_picker(res):
    countries = sorted(set(res.o), key=cname)
    by_o = {c: g for c, g in res.groupby("o")}

    def view(sel):
        g = by_o[sel]
        z = g.resid.clip(-CLIP, CLIP).round(3).tolist()
        text = [f"<b>{cname(d)}</b><br>{np.exp(r):.2f}× predicted" for d, r in zip(g.d, g.resid)]
        return z, g.d.tolist(), text

    def title(sel):
        return f"{cname(sel)}: friendship ties vs. prediction"

    z0, l0, t0 = view(DEFAULT_COUNTRY)
    sel_text = lambda c: [f"<b>{cname(c)}</b><br>(selected)"]

    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        locations=l0, z=z0, text=t0, locationmode="ISO-3",
        hovertemplate="%{text}<extra></extra>",
        colorscale=DIV, zmid=0, zmin=-CLIP, zmax=CLIP,
        marker_line_width=0.3, marker_line_color="white",
        colorbar=dict(title="vs. prediction", tickvals=TICKV, ticktext=TICKT,
                      len=0.55, thickness=12, x=0.99),
    ))
    fig.add_trace(go.Choropleth(
        locations=[DEFAULT_COUNTRY], z=[1], text=sel_text(DEFAULT_COUNTRY),
        locationmode="ISO-3", hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, "#222222"], [1, "#222222"]], showscale=False, marker_line_width=0,
    ))

    buttons = []
    for c in countries:
        z, locs, text = view(c)
        buttons.append(dict(
            label=cname(c), name=c, method="update",
            args=[{"z": [z, [1]], "locations": [locs, [c]], "text": [text, sel_text(c)]},
                  {"title.text": title(c)}],
        ))

    fig.update_layout(**LAYOUT, geo=GEO, title=title_(title(DEFAULT_COUNTRY)),
                      updatemenus=[dict(buttons=buttons, direction="down",
                                        active=countries.index(DEFAULT_COUNTRY),
                                        x=0.01, xanchor="left", y=0.93, yanchor="top",
                                        bgcolor="white", showactive=True)])

    # click a country on the map to select it (reuses the menu's button data)
    js = """
var gd = document.getElementById('{plot_id}');
gd.on('plotly_click', function(ev) {
  if (!ev.points || !ev.points.length) return;
  var iso = ev.points[0].location;
  var btns = gd.layout.updatemenus[0].buttons;
  for (var i = 0; i < btns.length; i++) {
    if (btns[i].name === iso) {
      Plotly.update(gd, btns[i].args[0], btns[i].args[1]);
      Plotly.relayout(gd, {'updatemenus[0].active': i});
      break;
    }
  }
});
"""
    save(fig, "1_friend_picker.html", post_script=js)


# ------------------------------------------------------------------ map 2
def map_empires(prim, anchors):
    fig = go.Figure()
    for e in EMP_NAME:
        p = prim[prim.empire == e]
        if p.empty:
            continue
        text = [f"<b>{cname(i)}</b><br>{EMP_NAME[e]} until {int(y)}"
                + (" (settler colony)" if s else "")
                for i, y, s in zip(p.iso3, p.end, p.settler)]
        fig.add_trace(go.Choropleth(
            locations=p.iso3, z=[1] * len(p), text=text, locationmode="ISO-3",
            hovertemplate="%{text}<extra></extra>",
            colorscale=[[0, EMP_COL[e]], [1, EMP_COL[e]]], showscale=False,
            marker_line_width=0.3, marker_line_color="white",
            name=EMP_NAME[e], showlegend=True, legendgroup=e,
        ))
        if anchors:
            small = [i for i in p.iso3 if i in anchors and anchors[i][2] < SMALL_AREA]
            if small:
                fig.add_trace(go.Scattergeo(
                    lat=[anchors[i][0] for i in small], lon=[anchors[i][1] for i in small],
                    text=[t for i, t in zip(p.iso3, text) if i in small],
                    hovertemplate="%{text}<extra></extra>", mode="markers",
                    marker=dict(size=6, color=EMP_COL[e], line=dict(width=0.5, color="white")),
                    showlegend=False, legendgroup=e,
                ))
    metro = [e for e in EMP_NAME if e in set(prim.empire)]
    fig.add_trace(go.Choropleth(
        locations=metro, z=[1] * len(metro), locationmode="ISO-3",
        text=[f"<b>{cname(e)}</b><br>colonial power" for e in metro],
        hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, "#111111"], [1, "#111111"]], showscale=False,
        name="Colonial power", showlegend=True,
    ))
    fig.update_layout(
        **LAYOUT, geo=GEO,
        title=title_("Last European colonizer"),
        legend=dict(x=0.01, y=0.05, bgcolor="rgba(255,255,255,0.8)"),
    )
    save(fig, "2_empires.html")


# ------------------------------------------------------------------ map 3
def map_network(res, prim, hs, anchors):
    if not anchors:
        print("map 3 skipped (no coordinates)")
        return
    emp, indep = post45(prim)
    prem = dict(zip(hs.colony, hs.sibling_premium))
    metro_r = dict(zip(hs.colony, hs.metropole_resid))

    BINS = [(0.0, 0.5, 0.6, 0.25), (0.5, 1.0, 1.3, 0.45), (1.0, np.inf, 2.4, 0.75)]

    def segs(pairs):
        lat, lon = [], []
        for a, b in pairs:
            lat += [anchors[a][0], anchors[b][0], None]
            lon += [anchors[a][1], anchors[b][1], None]
        return lat, lon

    s = res[(res.o < res.d) & res.o.isin(emp) & res.d.isin(emp) & (res.resid > 0)]
    s = s[s.o.map(emp) == s.d.map(emp)]
    s = s[s.o.isin(anchors) & s.d.isin(anchors)]

    traces, tags = [], []
    for e in ["FRA", "GBR"]:
        se = s[s.o.map(emp) == e]
        for lo, hi, w, op in BINS:
            b = se[(se.resid > lo) & (se.resid <= hi)]
            lat, lon = segs(zip(b.o, b.d))
            traces.append(go.Scattergeo(lat=lat, lon=lon, mode="lines", hoverinfo="skip",
                                        line=dict(width=w, color=EMP_COL[e]), opacity=op,
                                        showlegend=False))
            tags.append(("sib", e))
        # ties to the capital
        cols = [c for c in emp if emp[c] == e and c in anchors and e in anchors]
        for lo, hi, w, op in [(-np.inf, 0.5, 0.6, 0.3)] + BINS[1:]:
            pick = [c for c in cols if lo < metro_r.get(c, -np.inf) <= hi]
            lat, lon = segs((c, e) for c in pick)
            traces.append(go.Scattergeo(lat=lat, lon=lon, mode="lines", hoverinfo="skip",
                                        line=dict(width=w, color=EMP_COL[e]), opacity=op,
                                        showlegend=False))
            tags.append(("hub", e))
        # nodes
        nodes = [c for c in emp if emp[c] == e and c in anchors]
        traces.append(go.Scattergeo(
            lat=[anchors[c][0] for c in nodes], lon=[anchors[c][1] for c in nodes],
            mode="markers", name=f"Former {EMP_NAME[e]} colony",
            marker=dict(size=6, color=EMP_COL[e], line=dict(width=0.6, color="white")),
            text=[f"<b>{cname(c)}</b><br>Former {EMP_NAME[e]} colony, independent {int(indep[c])}"
                  + (f"<br>Sibling premium: {np.exp(prem[c]):.2f}×" if c in prem and pd.notna(prem[c]) else "")
                  + (f"<br>Tie to {cname(e)}: {np.exp(metro_r[c]):.2f}× predicted"
                     if c in metro_r and pd.notna(metro_r[c]) else "")
                  for c in nodes],
            hovertemplate="%{text}<extra></extra>",
        ))
        tags.append(("node", e))
        # capital marker
        traces.append(go.Scattergeo(
            lat=[anchors[e][0]], lon=[anchors[e][1]], mode="markers+text",
            text=[EMP_NAME[e]], textposition="top center", hoverinfo="skip",
            marker=dict(size=10, color=EMP_COL[e], symbol="star"), showlegend=False,
        ))
        tags.append(("cap", e))

    def vis(view):
        out = []
        for kind, e in tags:
            if view == "FRA":
                out.append(e == "FRA" and kind in ("sib", "node"))
            elif view == "GBR":
                out.append(e == "GBR" and kind in ("sib", "node"))
            elif view == "both":
                out.append(kind in ("sib", "node"))
            else:  # hub
                out.append(kind in ("hub", "node", "cap"))
        return out

    T = {
        "both": "Links between former colonies, above prediction",
        "FRA": "Former French colonies",
        "GBR": "Former British colonies",
        "hub": "Ties to Paris and London",
    }
    SUB = ""

    fig = go.Figure(traces)
    for tr, v in zip(fig.data, vis("both")):
        tr.visible = v
    views = [("Both empires", "both"), ("French", "FRA"), ("British", "GBR"),
             ("Ties to the capital", "hub")]
    fig.update_layout(
        **LAYOUT,
        geo={**GEO, "center": dict(lat=3, lon=15), "projection_scale": 2.6},
        title=title_(T["both"] + SUB),
        legend=dict(x=0.01, y=0.05, bgcolor="rgba(255,255,255,0.8)"),
        updatemenus=[
            dict(type="buttons", direction="right", x=0.01, xanchor="left", y=0.93,
                 yanchor="top", bgcolor="white",
                 buttons=[dict(label=l, method="update",
                               args=[{"visible": vis(v)}, {"title.text": T[v] + SUB}])
                          for l, v in views]),
            {**ZOOM, "y": 0.93},
        ],
    )
    n_f = int((s.o.map(emp) == "FRA").sum())
    n_g = int((s.o.map(emp) == "GBR").sum())
    print(f"map 3: {n_f} French and {n_g} British sibling links above prediction")
    save(fig, "3_sibling_network.html")


# ------------------------------------------------------------------ map 4
def map_hub_spoke(hs, anchors):
    METRICS = [
        ("sibling_premium", "Sibling premium",
         "How much more connected each colony is to its siblings than to the other empire's colonies"),
        ("sibling_resid", "Tie to siblings",
         "Each colony's tie to other colonies of the same empire, vs. prediction"),
        ("metropole_resid", "Tie to the capital",
         "Each colony's tie to Paris or London, vs. prediction"),
    ]
    traces, owner = [], []
    for k, (col, label, _) in enumerate(METRICS):
        d = hs.dropna(subset=[col])
        text = [f"<b>{cname(c)}</b><br>Former {EMP_NAME[e]} colony<br>{label}: {np.exp(v):.2f}×"
                for c, e, v in zip(d.colony, d.empire, d[col])]
        z = d[col].clip(-CLIP, CLIP)
        traces.append(go.Choropleth(
            locations=d.colony, z=z, text=text, locationmode="ISO-3",
            hovertemplate="%{text}<extra></extra>",
            colorscale=DIV, zmid=0, zmin=-CLIP, zmax=CLIP,
            marker_line_width=0.3, marker_line_color="white", visible=(k == 0),
            colorbar=dict(title="multiple", tickvals=TICKV, ticktext=TICKT,
                          len=0.55, thickness=12, x=0.99),
        ))
        owner.append(k)
        if anchors:
            m = [(c, t, zz) for c, t, zz in zip(d.colony, text, z)
                 if c in anchors and anchors[c][2] < SMALL_AREA]
            if m:
                traces.append(go.Scattergeo(
                    lat=[anchors[c][0] for c, _, _ in m], lon=[anchors[c][1] for c, _, _ in m],
                    text=[t for _, t, _ in m], hovertemplate="%{text}<extra></extra>",
                    mode="markers", visible=(k == 0), showlegend=False,
                    marker=dict(size=7, color=[zz for _, _, zz in m], colorscale=DIV,
                                cmid=0, cmin=-CLIP, cmax=CLIP,
                                line=dict(width=0.6, color="#333")),
                ))
                owner.append(k)

    def title(k):
        return METRICS[k][1]

    fig = go.Figure(traces)
    fig.update_layout(
        **LAYOUT,
        geo={**GEO, "center": dict(lat=3, lon=15), "projection_scale": 2.6},
        title=title_(title(0)),
        updatemenus=[
            dict(type="buttons", direction="right", x=0.01, xanchor="left", y=0.93,
                 yanchor="top", bgcolor="white",
                 buttons=[dict(label=METRICS[k][1], method="update",
                               args=[{"visible": [o == k for o in owner]},
                                     {"title.text": title(k)}])
                          for k in range(len(METRICS))]),
            {**ZOOM, "y": 0.93},
        ],
    )
    save(fig, "4_hub_spoke.html")


# ------------------------------------------------------------------ hub-and-spoke scatter
def figure_hub_scatter(hs):
    """Interactive hub-and-spoke scatter: one dot per post-1945 French or British colony."""
    d = hs.dropna(subset=["metropole_resid", "sibling_resid"]).copy()
    for c in ["metropole", "sibling", "cross_empire"]:
        d[c + "_x"] = np.exp(d[c + "_resid"])
    lo = min(d.sibling_x.min(), d.metropole_x.min()) * 0.8
    hi = max(d.sibling_x.max(), d.metropole_x.max()) * 1.25

    fig = go.Figure()
    ref = dict(mode="lines", hoverinfo="skip", showlegend=False)
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], line=dict(color="#9a9a9a", width=1, dash="dash"), **ref))
    fig.add_trace(go.Scatter(x=[1, 1], y=[lo, hi], line=dict(color=GRID, width=1), **ref))
    fig.add_trace(go.Scatter(x=[lo, hi], y=[1, 1], line=dict(color=GRID, width=1), **ref))

    for e in ["FRA", "GBR"]:
        s = d[d.empire == e]
        if s.empty:
            continue
        custom = [[cname(c), int(y), m, sb, cr] for c, y, m, sb, cr in
                  zip(s.colony, s.indep, s.metropole_x, s.sibling_x, s.cross_empire_x)]
        fig.add_trace(go.Scatter(
            x=s.sibling_x, y=s.metropole_x, mode="markers",
            name=f"Former {EMP_NAME[e]} colonies", legendgroup=e,
            marker=dict(size=10, color=EMP_COL[e], opacity=0.85, line=dict(width=0.8, color="white")),
            customdata=custom,
            hovertemplate=("<b>%{customdata[0]}</b><br>"
                           f"Former {EMP_NAME[e]} colony, independent " "%{customdata[1]}<br>"
                           f"Tie to {cname(e)}: " "%{customdata[2]:.2f}× predicted<br>"
                           "Tie to sibling colonies: %{customdata[3]:.2f}×<br>"
                           "Tie to the other empire's colonies: %{customdata[4]:.2f}×<extra></extra>"),
        ))
        mx, my = float(np.exp(s.sibling_resid.mean())), float(np.exp(s.metropole_resid.mean()))
        fig.add_trace(go.Scatter(
            x=[mx], y=[my], mode="markers+text", legendgroup=e, showlegend=False,
            text=[f"{EMP_NAME[e]} average"], textposition="top center",
            textfont=dict(color=EMP_COL[e], size=12),
            marker=dict(size=17, symbol="diamond", color=EMP_COL[e], line=dict(width=2, color="white")),
            hovertemplate=(f"<b>Average former {EMP_NAME[e]} colony</b><br>"
                           f"Tie to {cname(e)}: {my:.2f}×<br>Tie to sibling colonies: {mx:.2f}×<extra></extra>"),
        ))

    ticks = [v for v in [0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32] if lo <= v <= hi]
    axis = dict(type="log", range=[np.log10(lo), np.log10(hi)], tickvals=ticks,
                ticktext=[f"{v:g}×" for v in ticks], gridcolor=GRID, zeroline=False,
                linecolor="#bbbbbb", ticks="outside", tickcolor="#bbbbbb")
    fig.update_layout(
        autosize=True, margin=dict(l=70, r=20, t=80, b=60),
        paper_bgcolor="white", plot_bgcolor="white",
        font=plotly_font(13), hoverlabel=hoverlabel(),
        title=title_("Closer to the capital, or to each other?"),
        xaxis=dict(title="Tie to sibling colonies (× predicted)", **axis),
        yaxis=dict(title="Tie to the old capital (× predicted)", **axis),
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", bgcolor="rgba(0,0,0,0)"),
        annotations=[dict(xref="paper", yref="paper", x=0.02, y=0.98, xanchor="left", yanchor="top",
                          showarrow=False, align="left",
                          text="Above the line: closer to the capital",
                          font=dict(color=MUTED, size=11))],
    )
    save(fig, "hub_spoke_scatter.html")


# ------------------------------------------------------------------ main
def main():
    res = pd.read_csv(OUT / "gravity_residuals.csv", dtype={"o": str, "d": str})
    prim = pd.read_csv(OUT / "primary_empire.csv", dtype={"iso3": str, "empire": str})
    prim["settler"] = prim.settler.astype(str).str.lower().eq("true")
    hs = pd.read_csv(OUT / "hub_spoke.csv", dtype={"colony": str, "empire": str})

    anchors = load_anchors()
    map_friend_picker(res)
    map_empires(prim, anchors)
    map_network(res, prim, hs, anchors)
    map_hub_spoke(hs, anchors)
    figure_hub_scatter(hs)
    print("\nEmbed in a Quarto post with, for example:")
    print('<iframe src="maps/1_friend_picker.html" width="100%" height="600" '
          'style="border:none;"></iframe>')


if __name__ == "__main__":
    main()
