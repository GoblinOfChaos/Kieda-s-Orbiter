"""Update check utility — used by the app to notify on startup when a
newer version is available on GitHub."""

import json
import urllib.request
from pathlib import Path


def _version_tuple(v):
    """Parse 'X.Y.Z'-style strings into a comparable int tuple. Falls back
    to (0,) for anything unparseable, so a malformed version never crashes
    the comparison - it just sorts as "oldest possible"."""
    parts = []
    for p in v.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def check_for_update(current_version_path="VERSION", repo="GoblinOfChaos/Kiedas-Orbiter", timeout=8):
    """Returns a dict {"current": str, "latest": str, "url": str} if a newer
    version is available on GitHub, or None if up to date / check failed.
    Never raises - any network/parse error just returns None."""
    try:
        p = Path(current_version_path)
        current = p.read_text().strip() if p.exists() else "unknown"

        base_url = f"https://github.com/{repo}/releases"
        latest = None

        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/latest",
                headers={"User-Agent": "kiedas-orbiter/1.0", "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            latest = data.get("tag_name", "").lstrip("v")
            base_url = data.get("html_url", base_url)
        except Exception:
            pass

        if not latest:
            req2 = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/tags",
                headers={"User-Agent": "kiedas-orbiter/1.0", "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req2, timeout=timeout) as r:
                tags = json.loads(r.read())
            if tags:
                latest = tags[0]["name"].lstrip("v")

        if latest and _version_tuple(latest) > _version_tuple(current):
            return {"current": current, "latest": latest, "url": base_url}
        return None
    except Exception:
        return None
