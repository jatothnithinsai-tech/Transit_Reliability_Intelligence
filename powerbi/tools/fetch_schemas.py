"""Cache Microsoft's public PBIR schemas, including transitive references."""
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "validation" / "schemas"
PREFIX = "https://developer.microsoft.com/json-schemas/"


def refs(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for item in value.values():
            yield from refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from refs(item)


def main():
    seeds = [
        json.loads(p.read_text(encoding="utf-8-sig"))["$schema"]
        for p in (ROOT / "Transit_Reliability_Intelligence.Report" / "definition").rglob("*.json")
        if "$schema" in json.loads(p.read_text(encoding="utf-8-sig"))
    ]
    seeds += [PREFIX + "fabric/item/report/definition/visualContainer/2.9.0/schema.json"]
    seen = {}
    while seeds:
        url = urldefrag(seeds.pop())[0]
        if not url.startswith(PREFIX) or url in seen:
            continue
        target = CACHE / urlparse(url).path.removeprefix("/json-schemas/")
        if target.exists():
            data = json.loads(target.read_text(encoding="utf-8-sig"))
        else:
            data = json.loads(urlopen(url, timeout=40).read())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        seen[url] = str(target.relative_to(ROOT)).replace("\\", "/")
        seeds.extend(urljoin(url, ref) for ref in refs(data) if not ref.startswith("#"))
    (CACHE / "index.json").write_text(json.dumps(seen, indent=2) + "\n", encoding="utf-8")
    print(f"Cached {len(seen)} Microsoft PBIR schemas.")


if __name__ == "__main__":
    main()
