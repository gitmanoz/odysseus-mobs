"""Exercise built-in palette application and reset without changing runtime state."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _exercise():
    if not shutil.which("node"):
        pytest.skip("Node required for theme behavior regression")
    source = (ROOT / "static/js/theme.js").read_text(encoding="utf-8")
    source = source.split("// Per-route SVG shape registry")[0]
    source = "\n".join(line for line in source.splitlines() if not line.startswith("import "))
    source = source.replace("export ", "")
    hex_source = (ROOT / "static/js/color/hex.js").read_text(encoding="utf-8").replace("export ", "")
    script = """
    const values = {};
    const document = { documentElement: {dataset:{},style:{setProperty(k,v){values[k]=v}}},querySelector(){return null} };
    const _updateFavicon = () => {};
    """ + hex_source + source + """
    applyColors(THEMES.graphite);
    const graphite = { appearance:document.documentElement.dataset.themeAppearance, values:{...values} };
    applyColors(THEMES.studio);
    const studio = { appearance:document.documentElement.dataset.themeAppearance, values:{...values} };
    applyColors(THEMES.cyberpunk);
    console.log(JSON.stringify({graphite, studio, reset:document.documentElement.dataset.themeAppearance,
      legacy:values, names:Object.keys(THEMES), pattern:THEME_DEFAULT_PATTERN.graphite,
      defaultTheme:DEFAULT_THEME}));
    """
    result = subprocess.run(["node", "-e", script],cwd=ROOT,text=True,capture_output=True,check=True)
    return json.loads(result.stdout)


def test_graphite_applies_complete_palette_and_switch_resets_presentation():
    result = _exercise()
    palette = result["graphite"]["values"]
    assert result["graphite"]["appearance"] == "graphite"
    assert palette["--bg"] == "#101113"
    assert palette["--fg"] == "#e6e8eb"
    assert palette["--user-bubble-bg"] != palette["--ai-bubble-bg"]
    assert palette["--code-fg"] == palette["--fg"]
    assert result["pattern"] == "none"
    assert result["defaultTheme"] == "studio"
    assert result["studio"]["values"]["--red"] == '#c8b68a'
    assert result["reset"] == ""
    assert result["legacy"]["--fg"] == "#0ff0fc"
    assert result["legacy"]["--code-fg"] == "#0ff0fc"
    assert set(result["names"]) == {"studio", "graphite", "dark", "light", "midnight", "paper",
        "cyberpunk", "retrowave", "forest", "ocean", "ume", "copper", "terminal",
        "organs", "lavender", "gpt", "claude", "cute"}


def test_graphite_text_and_accent_have_readable_surface_contrast():
    palette = _exercise()["graphite"]["values"]
    def luminance(hex_value):
        channels = [int(hex_value[i:i+2],16)/255 for i in (1,3,5)]
        linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c,w in zip(linear,(.2126,.7152,.0722)))
    def contrast(fg,bg):
        hi,lo=sorted((luminance(fg),luminance(bg)),reverse=True)
        return (hi+.05)/(lo+.05)
    for surface in ("--bg","--panel","--input-bg","--user-bubble-bg","--code-bg"):
        assert contrast(palette["--fg"],palette[surface]) >= 7
        assert contrast(palette["--red"],palette[surface]) >= 4.5


def test_first_paint_matches_default_before_theme_module_loads():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    css = (ROOT / "static/style.css").read_text(encoding="utf-8")
    assert '<html lang="pt-BR" data-theme-appearance="graphite">' in html
    assert '<meta name="theme-color" content="#101113">' in html
    core = css.split(':root {', 1)[1].split('}', 1)[0]
    for token, color in _exercise()["studio"]["values"].items():
        if token in {"--bg", "--fg", "--panel", "--border", "--red"}:
            assert f'{token}: {color};' in core
