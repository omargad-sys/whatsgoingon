"""Render the social share card from the real artifacts.

    python build_og.py

Writes public/og.png (1200x630).

Generated rather than drawn by hand so the preview can never claim something the
site does not. It reads the same JSON the app reads, prints the counts that are
actually in it, and stamps SYNTHETIC across the card when the build is fixture
data. A share image that looks authoritative while the underlying build is fake
would be the single most misleading artifact in the project.

Uses matplotlib, which is already a dependency. No basemap library: the event
points draw their own coastlines, because political violence happens on land.
"""

import datetime as dt

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patheffects import withStroke

from paths import (
    EVENTS_TOP,
    GENERATED_DIR,
    MANIFEST,
    SENSITIVITIES,
    WORLD_HEAT,
    ensure_dirs,
    read_json,
)

# Same tokens as app/globals.css.
PLANE = "#0d0d0d"
SURFACE = "#1a1a19"
INK = "#ffffff"
MUTED = "#898781"
SECONDARY = "#c3c2b7"
SEQ = ["#184f95", "#256abf", "#3987e5", "#86b6ef", "#cde2fb"]
WARNING = "#fab219"

W, H = 1200, 630
DPI = 100


def severity_color(fatalities):
    if fatalities >= 20:
        return "#d03b3b"
    if fatalities >= 5:
        return "#ec835a"
    if fatalities >= 1:
        return "#fab219"
    return MUTED


def main():
    ensure_dirs()
    heat = read_json(WORLD_HEAT)
    events = read_json(EVENTS_TOP)
    manifest = read_json(MANIFEST)
    sens = read_json(SENSITIVITIES)

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=PLANE)

    # Map occupies the full card; text sits on top of it.
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(PLANE)
    ax.set_xlim(-170, 180)
    ax.set_ylim(-58, 78)
    ax.axis("off")

    # Density first, as a dim underlay.
    if heat["cells"]:
        lons = [c[1] for c in heat["cells"]]
        lats = [c[2] for c in heat["cells"]]
        counts = [c[3] for c in heat["cells"]]
        top = sorted(counts)[int(len(counts) * 0.95)] or 1
        ax.scatter(
            lons,
            lats,
            s=[6 + 34 * min(c / top, 1) for c in counts],
            c=[SEQ[min(int(4 * min(c / top, 1)), 4)] for c in counts],
            alpha=0.30,
            linewidths=0,
            zorder=1,
        )

    # Individual events on top, coloured by severity.
    feats = events.get("features", [])
    if feats:
        ax.scatter(
            [f["geometry"]["coordinates"][0] for f in feats],
            [f["geometry"]["coordinates"][1] for f in feats],
            s=[3 + min(f["properties"]["f"], 30) * 0.9 for f in feats],
            c=[severity_color(f["properties"]["f"]) for f in feats],
            alpha=0.85,
            linewidths=0,
            zorder=2,
        )

    # Scrim so the type stays readable over whatever the data happens to draw.
    ax.add_patch(
        plt.Rectangle(
            (-170, -58), 350, 136, facecolor=PLANE, alpha=0.55, zorder=3, linewidth=0
        )
    )

    def text(x, y, s, size, color, weight="normal", alpha=1.0):
        fig.text(
            x, y, s, fontsize=size, color=color, weight=weight, alpha=alpha,
            ha="left", va="baseline", zorder=4,
            path_effects=[withStroke(linewidth=3, foreground=PLANE, alpha=0.6)],
        )

    text(0.055, 0.76, "What's Going On", 54, INK, "bold")
    text(0.055, 0.685, "Conflict risk, honestly measured", 22, SECONDARY)

    acled = manifest["acled"]
    stats = [
        (f"{acled['panel_countries']}", "countries tracked"),
        (f"{acled['detail_events']:,}", "events mapped"),
        (
            f"{sens['sample']['n_significant']}/{sens['sample']['n_pairs']}",
            "relationships identified",
        ),
    ]
    for i, (value, label) in enumerate(stats):
        x = 0.055 + i * 0.20
        text(x, 0.30, value, 38, INK, "bold")
        text(x, 0.245, label, 15, MUTED)

    text(
        0.055,
        0.135,
        "Escalation forecast x conflict shock x ETF sensitivity.",
        17,
        SECONDARY,
    )
    text(
        0.055,
        0.085,
        "Nothing is shown unless all three layers clear their significance gate.",
        17,
        MUTED,
    )

    if manifest.get("synthetic"):
        fig.text(
            0.5, 0.5, "SYNTHETIC DATA", fontsize=68, color=WARNING, weight="bold",
            ha="center", va="center", rotation=18, alpha=0.42, zorder=5,
        )

    out = GENERATED_DIR.parent / "og.png"
    fig.savefig(out, facecolor=PLANE, dpi=DPI)
    plt.close(fig)
    print(f"  wrote {out.relative_to(GENERATED_DIR.parent.parent)} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
