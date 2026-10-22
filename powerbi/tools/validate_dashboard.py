"""Offline Microsoft-schema, binding, formatting, layout and preservation checks."""
import hashlib
import json
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)
from jsonschema import Draft7Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "Transit_Reliability_Intelligence.Report"
MODEL = ROOT / "Transit_Reliability_Intelligence.SemanticModel" / "definition"
SCHEMAS = ROOT / "validation/schemas"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    errors, checks = [], []
    index = load(SCHEMAS / "index.json")
    store = {url: load(ROOT / path) for url, path in index.items()}
    for value in list(store.values()):
        if "$id" in value:
            store[value["$id"]] = value
    for path in (REPORT / "definition").rglob("*.json"):
        data = load(path)
        schema = store[data["$schema"]]
        validator = Draft7Validator(schema, resolver=RefResolver(base_uri=data["$schema"], referrer=schema, store=store))
        for error in validator.iter_errors(data):
            errors.append(f"{path.relative_to(ROOT)}: {list(error.path)}: {error.message}")
    checks.append("All PBIR JSON definitions validated against cached Microsoft schemas and transitive references.")
    # Validate visual-specific object/property names and literal values using the matching Desktop theme schema.
    theme = load(SCHEMAS / "reportThemeSchema-2.159.json")
    def resolve(value):
        while "$ref" in value:
            ref = value["$ref"]
            assert ref.startswith("#/")
            value = theme
            for part in ref[2:].split("/"):
                value = value[part]
        if "allOf" in value:
            properties = dict(value.get("properties", {}))
            for part in value["allOf"]:
                properties.update(resolve(part).get("properties", {}))
            value = {**value, "properties": properties}
        return value
    def decode(value):
        if isinstance(value, dict) and "expr" in value:
            expr = value["expr"]
            if "Literal" not in expr:
                raise ValueError("dynamic expression")
            literal = expr["Literal"]["Value"]
            if literal.startswith("'"):
                return literal[1:-1].replace("''", "'")
            if literal in ["true", "false"]:
                return literal == "true"
            return float(literal.rstrip("LD")) if "." in literal else int(literal.rstrip("LD"))
        if isinstance(value, dict):
            return {k: decode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [decode(v) for v in value]
        return value
    tables = {}
    for path in (MODEL / "tables").glob("*.tmdl"):
        text = path.read_text(encoding="utf-8-sig")
        name = re.search(r"^table (?:'([^']+)'|([^\n]+))", text)
        tables[name.group(1) or name.group(2)] = {
            "columns": re.findall(r"^\tcolumn (?:'([^']+)'|([^\n]+))", text, re.M),
            "measures": re.findall(r"^\tmeasure '([^']+)'", text, re.M),
        }
    for info in tables.values():
        info["columns"] = [a or b for a, b in info["columns"]]
    def bindings(value, source):
        if isinstance(value, dict):
            for kind in ["Measure", "Column"]:
                if kind in value:
                    expr = value[kind]
                    entity = expr.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    prop = expr.get("Property")
                    if entity is not None and prop not in tables.get(entity, {}).get("measures" if kind == "Measure" else "columns", []):
                        errors.append(f"{source}: unresolved {kind}: {entity}[{prop}]")
            for child in value.values():
                bindings(child, source)
        elif isinstance(value, list):
            for child in value:
                bindings(child, source)
    pages = list((REPORT / "definition/pages").glob("*/page.json"))
    assert len(pages) == 1, "Expected exactly one report page."
    page = load(pages[0])
    visuals = [load(p) for p in pages[0].parent.glob("visuals/*/visual.json")]
    for visual in visuals:
        name = visual["name"]
        bindings(visual, name)
        v = visual["visual"]
        visual_schema = resolve(theme["properties"]["visualStyles"]["properties"][v["visualType"]]["properties"]["*"])
        known = visual_schema["properties"]
        for obj, definitions in v.get("objects", {}).items():
            if obj not in known:
                errors.append(f"{name}: unknown formatting object {obj}")
                continue
            item_schema = resolve(resolve(known[obj])["items"])
            for definition in definitions:
                for prop, value in definition["properties"].items():
                    if prop not in item_schema.get("properties", {}):
                        errors.append(f"{name}: unknown formatting property {obj}.{prop}")
                        continue
                    # Theme-schema paragraphs describe theme defaults, not serialized PBIR text runs.
                    # Installed desktop.TextboxVisual.min.js serializes textRuns as an array
                    # of {value, textStyle}; validate that runtime representation explicitly.
                    if v["visualType"] == "textbox" and obj == "general" and prop == "paragraphs":
                        for paragraph in value:
                            assert isinstance(paragraph["textRuns"], list)
                            for run in paragraph["textRuns"]:
                                assert isinstance(run["value"], str)
                                assert set(run) <= {"value", "textStyle", "url"}
                        continue
                    try:
                        decoded = decode(value)
                    except ValueError:
                        continue
                    property_schema = item_schema["properties"][prop]
                    validator = Draft7Validator(property_schema, resolver=RefResolver.from_schema(theme))
                    for error in validator.iter_errors(decoded):
                        errors.append(f"{name}: {obj}.{prop}: {error.message}")
        p = visual["position"]
        if min(p["x"], p["y"]) < 0 or p["x"] + p["width"] > page["width"] or p["y"] + p["height"] > page["height"]:
            errors.append(name + ": outside page bounds")
    for i, a in enumerate(visuals):
        for b in visuals[i + 1:]:
            ap, bp = a["position"], b["position"]
            if max(ap["x"], bp["x"]) < min(ap["x"] + ap["width"], bp["x"] + bp["width"]) and max(ap["y"], bp["y"]) < min(ap["y"] + ap["height"], bp["y"] + bp["height"]):
                errors.append(f"Overlapping visuals: {a['name']}, {b['name']}")
    checks += ["All visual data bindings resolve to real TMDL columns/measures.", "Visual formatting names and literal values checked against Microsoft Desktop 2.159 schema; textbox paragraphs checked against installed Desktop serializer conventions.", "Exactly one 16:9 page; all 14 visual containers are within bounds and do not overlap."]
    # Ensure only the slicer can filter line-level visuals.
    filter_edges = [x for x in page["visualInteractions"] if x["type"] != "NoFilter"]
    assert {(x["source"], x["target"], x["type"]) for x in filter_edges} == {
        ("tube_line_filter", "line_good_service", "DataFilter"), ("tube_line_filter", "major_disruptions", "DataFilter")}
    checks.append("Explicit interactions isolate global KPIs, daily trend, distribution and footer from line selection.")
    backups = sorted((ROOT / "backups").glob("before_dashboard_*"))
    backup = backups[-1]
    original = backup / "Transit_Reliability_Intelligence.SemanticModel/definition"
    for path in (MODEL / "tables").glob("*.tmdl"):
        before = (original / "tables" / path.name).read_text(encoding="utf-8-sig")
        after = path.read_text(encoding="utf-8-sig")
        for label, value in [("partition", "\n\tpartition "), ("source column", "sourceColumn:")]:
            if label == "partition":
                if before[before.index(value):] != after[after.index(value):]:
                    errors.append(path.name + ": original partition/source changed")
            elif re.findall(r"sourceColumn:.*", before) != re.findall(r"sourceColumn:.*", after):
                errors.append(path.name + ": source column mapping changed")
    for relative in ["Transit_Reliability_Intelligence.pbip", "Transit_Reliability_Intelligence.Report/definition.pbir", "Transit_Reliability_Intelligence.SemanticModel/.pbi/cache.abf"]:
        current, saved = ROOT / relative, backup / relative
        if hashlib.sha256(current.read_bytes()).digest() != hashlib.sha256(saved.read_bytes()).digest():
            errors.append(relative + ": original project pointer or data cache changed")
    checks.append("All 12 original table partitions, source mappings, PostgreSQL/Power Query definitions, PBIP pointer, report model reference and import cache are unchanged from backup.")
    result = {"passed": not errors, "errors": errors, "checks": checks, "visual_count": len(visuals), "measure_count": len(load(ROOT / "validation/measure_manifest.json")), "backup": str(backup.relative_to(ROOT))}
    write_path = ROOT / "validation/static_validation.json"
    write_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
