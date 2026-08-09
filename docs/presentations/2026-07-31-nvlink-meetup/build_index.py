"""Skleja index.html: wlewa wykresy SVG i screenshot PNG inline do index_src.html.

Uruchomienie:

    uv run python docs/presentations/2026-07-31-nvlink-meetup/build_index.py

Kolejnosc: najpierw generate_charts.py (SVG w charts/), potem ten skrypt.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Przyciety kadr na potrzeby slajdu 3; oryginalny dowod (pelny zrzut) pozostaje
# nienaruszony w results/runs/2026-08-03_domkniecie_grafana/nvidia_smi_nop2p.png.
SCREENSHOT = HERE / "nvidia_smi_crop.png"


def inline_svg(name: str) -> str:
    text = (HERE / "charts" / f"{name}.svg").read_text(encoding="utf-8")
    svg = re.sub(r"^.*?<svg", "<svg", text, count=1, flags=re.DOTALL)
    return "\n".join(line.rstrip() for line in svg.splitlines())


def main() -> None:
    html = (HERE / "index_src.html").read_text(encoding="utf-8")
    html = re.sub(r"\{\{SVG:([a-z0-9_]+)\}\}", lambda m: inline_svg(m.group(1)), html)
    png_uri = "data:image/png;base64," + base64.b64encode(SCREENSHOT.read_bytes()).decode()
    html = html.replace("{{PNG:nvidia_smi}}", png_uri)
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html: {len(html) / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
