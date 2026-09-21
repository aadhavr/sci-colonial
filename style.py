"""
style.py — shared look for every figure and map.

Font: IBM Plex Sans.
  * Plotly maps load it from Google Fonts inside each HTML file (an iframe does not
    inherit the blog's fonts, so each file has to load its own).
  * matplotlib needs the font installed locally. setup_matplotlib() looks in ./fonts/
    and the usual system font folders, so a newly installed font is found without
    clearing matplotlib's cache.
    macOS:  brew install --cask font-ibm-plex-sans
    or put the .ttf files from https://github.com/IBM/plex in ./fonts/
"""

from pathlib import Path
import warnings

FONT_NAME = "IBM Plex Sans"
FONT_STACK = "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif"
FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600'
    '&display=swap" rel="stylesheet">'
)

EMP_NAME = {"FRA": "France", "GBR": "Britain", "ESP": "Spain", "PRT": "Portugal",
            "NLD": "Netherlands", "BEL": "Belgium", "ITA": "Italy", "DEU": "Germany"}
EMP_COL = {"FRA": "#b03a2e", "GBR": "#1f4e79", "ESP": "#c9a227", "PRT": "#2e8b57",
           "NLD": "#e67e22", "BEL": "#6c3483", "ITA": "#17a589", "DEU": "#666666"}

TEXT = "#222222"
MUTED = "#6b6b6b"
GRID = "#e5e5e5"

# brown-teal diverging scale for "above / below prediction"
DIV = [[0.0, "#8c510a"], [0.25, "#d8b365"], [0.5, "#f5f5f5"], [0.75, "#5ab4ac"], [1.0, "#01665e"]]


# ------------------------------------------------------------------ plotly
def plotly_font(size=13):
    return dict(family=FONT_STACK, size=size, color=TEXT)


# Light hover box with dark text (Plotly's default box is dark grey, which made
# dark text unreadable).
def hoverlabel():
    return dict(bgcolor="white", bordercolor="#cfcfcf", font=plotly_font(12), align="left")


def title_font():
    return dict(family=FONT_STACK, size=15, color=TEXT)


# Redraw once the web font has loaded, so labels are measured in Plex, not the fallback.
FONT_READY_JS = """
var gdf = document.getElementById('{plot_id}');
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(function () { Plotly.react(gdf, gdf.data, gdf.layout); });
}
"""


def inject_font(html_path):
    """Add the Google Fonts link to the <head> of a Plotly HTML file."""
    p = Path(html_path)
    s = p.read_text(encoding="utf-8")
    if FONT_LINK not in s:
        s = s.replace("<head>", "<head>" + FONT_LINK, 1)
        # the figure fills the iframe exactly, so the iframe height sets the figure height
        s = s.replace("<head>", "<head><style>html,body{height:100%;margin:0;}</style>", 1)
        s = s.replace("<body>", '<body style="margin:0;font-family:' + FONT_STACK.replace("'", "&#39;") + '">', 1)
        p.write_text(s, encoding="utf-8")


# ------------------------------------------------------------------ matplotlib
def setup_matplotlib():
    import matplotlib as mpl
    from matplotlib import font_manager as fm

    dirs = [Path("fonts"), Path.home() / "Library" / "Fonts", Path("/Library/Fonts"),
            Path("/System/Library/Fonts"), Path.home() / ".local" / "share" / "fonts",
            Path.home() / ".fonts", Path("/usr/share/fonts"), Path("C:/Windows/Fonts")]
    for d in dirs:
        if not d.exists():
            continue
        try:
            for f in d.rglob("IBMPlexSans*"):
                if f.suffix.lower() in (".ttf", ".otf"):
                    fm.fontManager.addfont(str(f))
        except (PermissionError, OSError):
            continue

    if FONT_NAME in {f.name for f in fm.fontManager.ttflist}:
        family = [FONT_NAME]
    else:
        warnings.warn("IBM Plex Sans not found: figures use the fallback font. "
                      "Install it (brew install --cask font-ibm-plex-sans) or put the .ttf "
                      "files in ./fonts/")
        family = ["Helvetica Neue", "Arial", "DejaVu Sans"]

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": family + ["DejaVu Sans"],
        "text.color": TEXT, "axes.labelcolor": TEXT,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": "#bbbbbb", "axes.titleweight": "semibold",
        "svg.fonttype": "path",   # SVG keeps the Plex shapes even where Plex is not installed
    })
