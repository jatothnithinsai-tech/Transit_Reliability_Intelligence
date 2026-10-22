"""Print authoritative Desktop formatting property names for report authoring."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "validation/schemas/reportThemeSchema-2.159.json").read_text(encoding="utf-8"))


def resolve(value):
    while "$ref" in value:
        ref = value["$ref"]
        assert ref.startswith("#/")
        value = schema
        for part in ref[2:].split("/"):
            value = value[part]
    if "allOf" in value:
        properties = dict(value.get("properties", {}))
        for part in value["allOf"]:
            properties.update(resolve(part).get("properties", {}))
        value = {**value, "properties": properties}
    return value


print("ROOT", list(schema))
styles = resolve(schema["properties"]["visualStyles"])
print("VISUALS", list(styles.get("properties", {})))
for name in ["card", "multiRowCard", "cardVisual", "clusteredBarChart", "clusteredColumnChart", "lineChart", "slicer", "textbox"]:
    visual = resolve(styles.get("properties", {}).get(name, {}))
    print("\nVISUAL", name, list(visual))
    selectors = resolve(visual.get("properties", {}).get("*", {}))
    objects = selectors.get("properties", {})
    print("OBJECTS", list(objects))
    for obj in ["labels", "categoryLabels", "categoryAxis", "valueAxis", "dataPoint", "lineStyles", "markers", "selection", "data", "header", "items", "general", "paragraphs", "wordWrap", "card", "text"]:
        if obj in objects:
            props = resolve(resolve(objects[obj])["items"]).get("properties", {})
            print(obj, list(props))
