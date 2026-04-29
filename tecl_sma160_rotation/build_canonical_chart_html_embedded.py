from __future__ import annotations

import re
from pathlib import Path

from canonical_chart_data import DASHBOARD_DIR, canonical_chart_json


HTML_PATH = DASHBOARD_DIR / "canonical-chart.html"
EMBED_RE = re.compile(
    r'(<script id="__canonicalEmbed" type="application/json">)(.*?)(</script>)',
    flags=re.DOTALL,
)


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    payload = canonical_chart_json()
    replaced, count = EMBED_RE.subn(rf"\1{payload}\3", html, count=1)
    if count != 1:
        raise RuntimeError(f"canonical embed script tag not found in {HTML_PATH}")
    HTML_PATH.write_text(replaced, encoding="utf-8")
    print(f"Embedded canonical chart data into {HTML_PATH}")


if __name__ == "__main__":
    main()
