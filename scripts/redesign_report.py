"""Apply the portfolio presentation to the existing report; data models and queries stay intact."""

from pathlib import Path
import json

BG = "#F6F8FC"
INK = "#263445"
MUTED = "#56687A"
WHITE = "#FFFFFF"
LINE = "#DEE5EE"
BLUE = "#2563A6"
TEAL = "#087F75"
CORAL = "#C9513E"
AMBER = "#A56C16"
PURPLE = "#7664BF"


def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def write(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lit(v):
    s = (
        str(v).lower()
        if isinstance(v, bool)
        else str(v) + "D"
        if isinstance(v, (float, int))
        else "'" + str(v).replace("'", "''") + "'"
    )
    return {"expr": {"Literal": {"Value": s}}}


def color(v):
    return {"solid": {"color": lit(v)}}


def obj(d, k, props):
    d.setdefault(k, [{"properties": {}}])[0].setdefault("properties", {}).update(props)


def rect(v, x, y, w, h):
    v["position"].update(x=x, y=y, width=w, height=h)


def title(v, text):
    obj(v["visual"].setdefault("visualContainerObjects", {}), "title", {"text": lit(text)})


def text(v, content, size=18, c=INK, bold=False):
    obj(
        v["visual"].setdefault("objects", {}),
        "general",
        {
            "paragraphs": [
                {
                    "textRuns": [
                        {
                            "value": content,
                            "textStyle": {
                                "fontFamily": "Segoe UI",
                                "fontSize": f"{size}px",
                                "color": c,
                                "fontWeight": "bold" if bold else "normal",
                            },
                        }
                    ]
                }
            ]
        },
    )


def props(v):
    return v["visual"].setdefault("objects", {})


def style(v, accent=BLUE, tint=None):
    cfg = v["visual"]
    typ = cfg["visualType"]
    vc = cfg.setdefault("visualContainerObjects", {})
    o = cfg.setdefault("objects", {})
    obj(
        vc,
        "title",
        {"fontColor": color(INK), "fontSize": lit(14), "fontFamily": lit("Segoe UI Semibold"), "bold": lit(True)},
    )
    obj(vc, "subTitle", {"fontColor": color(MUTED), "fontSize": lit(10)}) if "subTitle" in vc else None
    obj(vc, "background", {"show": lit(typ != "textbox"), "color": color(tint or WHITE), "transparency": lit(0)})
    obj(vc, "border", {"show": lit(typ != "textbox"), "color": color(LINE), "radius": lit(10)})

    # Replace previous dark-mode literal colours throughout visual formatting, without touching query bindings.
    def walk(x):
        if isinstance(x, dict):
            for k, val in x.items():
                if k == "Value" and isinstance(val, str):
                    swap = {
                        "'#F1F6FC'": f"'{INK}'",
                        "'#AFC0D5'": f"'{MUTED}'",
                        "'#112239'": f"'{WHITE}'",
                        "'#263D57'": f"'{LINE}'",
                    }
                    if val in swap:
                        x[k] = swap[val]
                elif isinstance(val, (dict, list)):
                    walk(val)
        elif isinstance(x, list):
            for val in x:
                walk(val)

    walk(o)
    if typ == "card":
        obj(
            o,
            "labels",
            {
                "color": color(accent),
                "fontSize": lit(30),
                "fontFamily": lit("Segoe UI Semibold"),
                "labelDisplayUnits": lit(1),
            },
        )
        obj(o, "categoryLabels", {"show": lit(False)})
    elif typ == "slicer":
        obj(o, "data", {"mode": lit("Dropdown")})
        obj(o, "items", {"fontColor": color(INK), "background": color(WHITE), "textSize": lit(12)})
        obj(o, "header", {"show": lit(False)})
    elif typ in ["lineChart", "barChart", "clusteredBarChart", "clusteredColumnChart"]:
        obj(o, "dataPoint", {"defaultColor": color(accent)})
        if len(cfg.get("query", {}).get("queryState", {}).get("Y", {}).get("projections", [])) > 1:
            o["dataPoint"][0]["properties"].pop("defaultColor", None)
        obj(o, "categoryAxis", {"labelColor": color(MUTED), "fontSize": lit(11), "showAxisTitle": lit(False)})
        obj(
            o,
            "valueAxis",
            {
                "labelColor": color(MUTED),
                "fontSize": lit(10),
                "showAxisTitle": lit(False),
                "gridlineColor": color(LINE),
                "gridlineTransparency": lit(30),
            },
        )
        obj(o, "legend", {"labelColor": color(MUTED), "fontSize": lit(11)})
        if "labels" in o:
            obj(o, "labels", {"color": color(INK), "fontSize": lit(11)})
    elif typ in ["tableEx", "pivotTable"]:
        obj(
            o,
            "columnHeaders",
            {
                "fontColor": color(WHITE),
                "backColor": color(accent),
                "fontSize": lit(11),
                "bold": lit(True),
                "autoSizeColumnWidth": lit(True),
                "columnAdjustment": lit("growToFit"),
            },
        )
        obj(
            o,
            "values",
            {
                "fontColorPrimary": color(INK),
                "backColorPrimary": color(WHITE),
                "fontColorSecondary": color(INK),
                "backColorSecondary": color("#F0F4FA"),
                "fontSize": lit(12),
            },
        )
        obj(
            o,
            "grid",
            {
                "gridVertical": lit(False),
                "gridHorizontal": lit(True),
                "gridHorizontalColor": color(LINE),
                "rowPadding": lit(5),
            },
        )


def theme(report, name, palette):
    f = report / "definition/report.json"
    d = read(f)
    d["$schema"] = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
    d.setdefault("settings", {})["locale"] = "en-GB"
    d.setdefault("themeCollection", {})["customTheme"] = {
        "name": name,
        "type": "RegisteredResources",
        "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.0.0"},
    }
    pkgs = d.setdefault("resourcePackages", [])
    pkg = next((p for p in pkgs if p["name"] == "RegisteredResources"), None)
    if pkg is None:
        pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        pkgs.append(pkg)
    pkg["items"] = [i for i in pkg["items"] if i.get("type") != "CustomTheme"] + [
        {"name": name, "path": name + ".json", "type": "CustomTheme"}
    ]
    write(
        report / "StaticResources/RegisteredResources" / f"{name}.json",
        {
            "name": name,
            "dataColors": palette,
            "background": BG,
            "foreground": INK,
            "tableAccent": palette[0],
            "good": TEAL,
            "neutral": "#C48B25",
            "bad": CORAL,
            "textClasses": {
                "title": {"fontFace": "Segoe UI Semibold", "color": INK},
                "label": {"fontFace": "Segoe UI", "color": MUTED},
                "callout": {"fontFace": "Segoe UI Semibold", "color": INK},
            },
        },
    )
    write(f, d)


def report_pages(report):
    return sorted((report / "definition/pages").glob("*/page.json"))


def load_page(f):
    pg = read(f)
    vs = {x.parent.name: read(x) for x in sorted((f.parent / "visuals").glob("*/visual.json"))}
    return pg, vs


def save_page(f, pg, vs):
    write(f, pg)
    for k, v in vs.items():
        write(f.parent / "visuals" / k / "visual.json", v)


def page_bg(pg, w, h):
    pg.update(width=w, height=h, displayOption="FitToPage")
    obj(pg.setdefault("objects", {}), "background", {"color": color(BG), "transparency": lit(0)})


def textbox(ref, name, content, box, size=18, c=MUTED, bold=False):
    v = {
        "$schema": ref,
        "name": name,
        "position": dict(zip(["x", "y", "width", "height"], box)) | {"z": 90, "tabOrder": 90},
        "visual": {
            "visualType": "textbox",
            "visualContainerObjects": {"title": [{"properties": {"show": lit(False)}}]},
        },
    }
    style(v)
    text(v, content, size, c, bold)
    return v


def redesign(base):
    target = Path(base)
    report = next(target.glob("*.Report"))
    f = report_pages(report)[0]
    pg, vs = load_page(f)
    page_bg(pg, 1920, 1080)
    accents = {
        "kpi_lines": BLUE,
        "kpi_snapshots": PURPLE,
        "kpi_good": TEAL,
        "kpi_disruption": CORAL,
        "line_good_service": BLUE,
        "daily_disruption": CORAL,
        "status_distribution": TEAL,
        "major_disruptions": CORAL,
    }
    for k, v in vs.items():
        style(v, accents.get(k, BLUE))
    text(vs["report_title"], "Transit reliability intelligence", 40, INK, True)
    rect(vs["report_title"], 40, 26, 1430, 60)
    text(vs["report_subtitle"], "LONDON UNDERGROUND  /  SAMPLED SERVICE OBSERVATIONS", 18, BLUE, True)
    rect(vs["report_subtitle"], 40, 94, 1430, 34)
    text(
        vs["scope_note"],
        "Network KPIs, trend and status mix stay global. Use the line filter to focus the two line comparisons.",
        18,
        MUTED,
    )
    rect(vs["scope_note"], 40, 139, 1840, 34)
    rect(vs["tube_line_filter"], 1510, 32, 370, 98)
    for i, (k, t, c, bg) in enumerate(
        [
            ("kpi_lines", "Tube lines observed", BLUE, "#EDF3FC"),
            ("kpi_snapshots", "Collection timestamps", PURPLE, "#F2F0FA"),
            ("kpi_good", "Observed good service", TEAL, "#EAF6F2"),
            ("kpi_disruption", "Observed disruption", CORAL, "#FCF0EB"),
        ]
    ):
        rect(vs[k], 40 + i * 466, 194, 442, 132)
        style(vs[k], c, bg)
        title(vs[k], t)
        obj(props(vs[k]), "labels", {"fontSize": lit(28)})
    rect(vs["line_good_service"], 40, 354, 718, 620)
    title(vs["line_good_service"], "Good service by Tube line")
    rect(vs["daily_disruption"], 782, 354, 1098, 222)
    title(vs["daily_disruption"], "Observed disruption across sampled days")
    obj(props(vs["daily_disruption"]), "lineStyles", {"markerColor": color(CORAL)})
    rect(vs["status_distribution"], 782, 600, 526, 374)
    title(vs["status_distribution"], "Service status records")
    # Native literal category colours replace a previous presentation-only DAX colour binding.
    points = props(vs["status_distribution"])["dataPoint"]
    props(vs["status_distribution"])["dataPoint"] = points[:1]
    rect(vs["major_disruptions"], 1332, 600, 548, 374)
    title(vs["major_disruptions"], "Major-status observations by line")
    # Fit all 11 categories instead of the original scrolling investigation chart.
    obj(props(vs["major_disruptions"]), "categoryAxis", {"innerPadding": lit(10), "fontSize": lit(11)})
    for k in ["line_good_service", "major_disruptions"]:
        obj(props(vs[k]), "labels", {"color": color(INK), "labelPosition": lit("OutsideEnd")})
    rect(vs["observation_context"], 40, 992, 1840, 34)
    obj(props(vs["observation_context"]), "labels", {"fontSize": lit(13), "color": color(MUTED)})
    obj(vs["observation_context"]["visual"]["visualContainerObjects"], "background", {"show": lit(False)})
    obj(vs["observation_context"]["visual"]["visualContainerObjects"], "border", {"show": lit(False)})
    rect(vs["disclaimer"], 40, 1032, 1840, 34)
    text(
        vs["disclaimer"],
        "Sampled TfL API statuses; percentages describe observations. They do not measure service uptime, punctuality or passenger delay.",
        17,
        MUTED,
    )
    save_page(f, pg, vs)
    theme(report, "Transit_Operations_Light", [BLUE, TEAL, "#C48B25", CORAL, PURPLE])
    return target


if __name__ == "__main__":
    redesign(Path(__file__).resolve().parents[1] / "powerbi")
