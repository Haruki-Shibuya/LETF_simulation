from __future__ import annotations

import re

from position_dashboard_data import DASHBOARD_DIR, position_dashboard_json


HTML_PATH = DASHBOARD_DIR / "index.html"
EMBED_PATTERN = re.compile(
    r'(<script id="__positionEmbed" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    payload = position_dashboard_json()
    updated, count = EMBED_PATTERN.subn(rf"\1{payload}\3", html)
    if count != 1:
        raise RuntimeError(f"position embed script tag not found in {HTML_PATH}")
    HTML_PATH.write_text(updated, encoding="utf-8")
    print(f"Embedded position dashboard data into {HTML_PATH}")


if __name__ == "__main__":
    main()
