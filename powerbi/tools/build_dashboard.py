"""Build the complete one-page report using the existing enhanced PBIR project.

Run only after taking a project backup. No connection, partition or ETL changes.
Formatting names are checked against Microsoft's Desktop 2.159 theme schema.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "Transit_Reliability_Intelligence.Report"
MODEL = ROOT / "Transit_Reliability_Intelligence.SemanticModel" / "definition"
PAGE_ID = "136ec41bb4e584b42f87"
PAGE = REPORT / "definition/pages" / PAGE_ID
HOST = "analytics vw_operational_kpi_summary"
S = "'analytics vw_operational_kpi_summary'"
F = "'analytics vw_line_snapshot_status'"
R = "'analytics vw_line_reliability'"
D = "'analytics vw_daily_disruption_trends'"
V = "'analytics vw_disruption_severity'"
M = "'analytics vw_major_disruptions_by_line'"
NAVY, PANEL, BORDER = "#081322", "#112239", "#263D57"
WHITE, MUTED, TEAL, ORANGE, RED = "#F1F6FC", "#AFC0D5", "#37D6BC", "#FFAA70", "#FF747C"
MEASURES = {}


def add(name, expression, fmt, description, folder="Report metrics"):
    MEASURES[name] = dict(expression=expression, formatString=fmt, description=description, folder=folder)


add("Total Tube Lines", f"CALCULATE ( MAX ( {S}[tube_lines_monitored] ), REMOVEFILTERS () )", "#,0", "Network-wide distinct monitored line IDs, as calculated by the SQL summary; ignores report filters.")
add("Total Historical Snapshots", f"CALCULATE ( DISTINCTCOUNT ( {F}[snapshot_time] ), REMOVEFILTERS () )", "#,0", "Network-wide distinct collection timestamps. A timestamp shared by 11 lines counts once.")
add("Observed Good Service %", f"100.0 * DIVIDE ( CALCULATE ( MAX ( {S}[good_service_observations] ), REMOVEFILTERS () ), CALCULATE ( MAX ( {S}[total_line_observations] ), REMOVEFILTERS () ) )", '0.00\\%', "Network-wide Good Service line/snapshot observations divided by all line/snapshot observations, on a 0-100 scale. Not uptime.")
add("Observed Disruption %", f"100.0 * DIVIDE ( CALCULATE ( MAX ( {S}[disrupted_observations] ), REMOVEFILTERS () ), CALCULATE ( MAX ( {S}[total_line_observations] ), REMOVEFILTERS () ) )", '0.00\\%', "Network-wide disrupted line/snapshot observations divided by all line/snapshot observations, on a 0-100 scale. Not incident counts.")
add("Line Observed Good Service %", f"100.0 * DIVIDE ( SUM ( {R}[good_service_snapshots] ), SUM ( {R}[total_snapshots] ) )", '0.00\\%', "Weighted ratio of counts for selected Tube lines; never sums stored percentage columns.")
add("Daily Observed Disruption %", f"100.0 * DIVIDE ( SUM ( {D}[disrupted_line_observations] ), SUM ( {D}[total_line_observations] ) )", '0.00\\%', "Daily network-wide ratio of disrupted to all line/snapshot observations. Dates come from the SQL Europe/London calendar.")
add("Status Record Count", f"SUM ( {V}[total_status_records] )", "#,0", "Raw service-status records grouped by description. Multiple statuses can occur at the same line/snapshot; this is not a snapshot or incident count.")
add("Major Disruption Snapshots", f"SUM ( {M}[major_status_snapshots] )", "#,0", "Distinct line/snapshot observations matching any SQL-defined major category: Severe Delays, Part Closure, Part Suspended or Planned Closure. A snapshot matching multiple categories counts once per line.")
add("Line Snapshots Observed", f"SUM ( {R}[total_snapshots] )", "#,0", "Line/snapshot observations for the selected lines. Totals across lines are not distinct collection timestamps.", "Report tooltips")
add("Daily Collection Times", f"SUM ( {D}[snapshots_collected] )", "#,0", "Distinct collection timestamps per observed local date, summed only across disjoint dates.", "Report tooltips")
add("Daily Line Observations", f"SUM ( {D}[total_line_observations] )", "#,0", "Number of observed line/snapshot pairs per local date.", "Report tooltips")
add("Status Record Share %", f"100.0 * DIVIDE ( [Status Record Count], CALCULATE ( [Status Record Count], REMOVEFILTERS ( {V} ) ) )", '0.00\\%', "Share of raw status records; denominator differs from the observation-based KPI denominator.", "Report tooltips")
for name, col, description in [
    ("Severe Delay Snapshots", "severe_delay_snapshots", "Observed snapshots with Severe Delays."),
    ("Closure or Suspension Snapshots", "closure_or_suspension_snapshots", "Observed snapshots with Part Closure or Part Suspended."),
    ("Planned Closure Snapshots", "planned_closure_snapshots", "Observed snapshots with Planned Closure; included in the SQL major-status union."),
]:
    add(name, f"SUM ( {M}[{col}] )", "#,0", description + " Category counts can overlap; do not add them to obtain the major total.", "Report tooltips")
add("Status Record Color", f'SWITCH ( SELECTEDVALUE ( {V}[status_description] ), "Good Service", "{TEAL}", "Severe Delays", "{RED}", "Part Suspended", "{RED}", "{ORANGE}" )', None, "Category-based colors, without treating severity codes as a numeric scale.", "Report presentation")
add("Observation Context", f'''VAR LatestObservation = CALCULATE ( MAX ( {S}[latest_snapshot_time] ), REMOVEFILTERS () )
RETURN
    IF ( ISBLANK ( LatestObservation ), "No imported observations", "Latest imported observation: " & FORMAT ( LatestObservation, "dd MMM yyyy HH:mm" ) & " (model time)" )
        & "  |  Import mode; refresh timestamp unavailable"''', None, "Latest imported observation timestamp, not the time of model refresh. No refresh timestamp exists in the supplied model.", "Report presentation")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lit(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = str(value) + ("L" if isinstance(value, int) else "D")
    return {"expr": {"Literal": {"Value": value}}}


def fill(color):
    return {"solid": {"color": lit(color)}}


def objects(**kwargs):
    return {key: [{"properties": value}] for key, value in kwargs.items()}


def field(entity, name, measure=False):
    return {"Measure" if measure else "Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}}


def projection(entity, name, measure=False, display=None):
    result = {"field": field(entity, name, measure), "queryRef": entity + "." + name, "nativeQueryRef": name}
    if display:
        result["displayName"] = display
    return result


def metric(name, display=None):
    return projection(HOST, name, True, display)


def query(roles, sort=None, direction="Descending", show_all=False):
    q = {"queryState": {role: {"projections": projections} for role, projections in roles.items()}}
    if show_all:
        q["queryState"]["Category"]["showAll"] = True
    if sort:
        q["sortDefinition"] = {"sort": [{"field": sort, "direction": direction}], "isDefaultSort": False}
    return q


def container(title=None, subtitle=None, panel=True, accent=None):
    o = objects(
        background={"show": lit(panel), "color": fill(PANEL), "transparency": lit(0)},
        border={"show": lit(panel), "color": fill(accent or BORDER), "radius": lit(12), "width": lit(1)},
        padding={k: lit(20 if panel else 0) for k in ["top", "bottom", "left", "right"]},
        visualHeader={"show": lit(False)},
        dropShadow={"show": lit(False)},
    )
    if title:
        o.update(objects(title={"show": lit(True), "text": lit(title), "fontColor": fill(WHITE), "fontSize": lit(16), "fontFamily": lit("Segoe UI Semibold"), "alignment": lit("left"), "titleWrap": lit(True)}))
    if subtitle:
        o.update(objects(subTitle={"show": lit(True), "text": lit(subtitle), "fontColor": fill(MUTED), "fontSize": lit(10), "fontFamily": lit("Segoe UI"), "titleWrap": lit(True)}))
    return o


VISUALS = []


def visual(name, typ, x, y, w, h, obj=None, q=None, vco=None, alt=None):
    v = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json",
         "name": name, "position": {"x": x, "y": y, "width": w, "height": h, "z": len(VISUALS), "tabOrder": len(VISUALS)},
         "visual": {"visualType": typ, "objects": obj or {}, "visualContainerObjects": vco or container(panel=False)},
         "howCreated": "Default"}
    if q:
        v["visual"]["query"] = q
    if alt:
        v["visual"]["visualContainerObjects"].update(objects(general={"altText": lit(alt)}))
    VISUALS.append(v)
    write(PAGE / "visuals" / name / "visual.json", v)
    return v


def textbox(name, text, x, y, w, h, size=14, color=MUTED, bold=False):
    p = [{"textRuns": [{"value": text, "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{size}px", "color": color, "fontWeight": "bold" if bold else "normal"}}]}]
    return visual(name, "textbox", x, y, w, h, objects(general={"paragraphs": p}), alt=text)


def axes(color, percentage=False, horizontal=False):
    obj = objects(
        categoryAxis={"show": lit(True), "showAxisTitle": lit(False), "labelColor": fill(MUTED), "fontSize": lit(11), "fontFamily": lit("Segoe UI"), "gridlineShow": lit(False)},
        valueAxis={"show": lit(True), "showAxisTitle": lit(False), "labelColor": fill(MUTED), "fontSize": lit(10), "fontFamily": lit("Segoe UI"), "start": lit(0), "labelDisplayUnits": lit(0), "labelPrecision": lit(0), "gridlineShow": lit(True), "gridlineColor": fill(BORDER), "gridlineTransparency": lit(30)},
        dataPoint={"defaultColor": fill(color)},
        legend={"show": lit(False)},
        labels={"show": lit(True), "color": fill(WHITE), "fontSize": lit(11), "fontFamily": lit("Segoe UI"), "labelDisplayUnits": lit(0), "labelPrecision": lit(1 if percentage else 0)},
        general={"responsive": lit(False)},
    )
    if percentage:
        obj["valueAxis"][0]["properties"]["end"] = lit(100)
    if horizontal:
        obj["categoryAxis"][0]["properties"].update({"innerPadding": lit(30), "maxMarginFactor": lit(32)})
    return obj


def update_model():
    host_path = MODEL / "tables" / (HOST + ".tmdl")
    text = host_path.read_text(encoding="utf-8-sig")
    text = re.sub(r"\n\t///? BEGIN GENERATED REPORT MEASURES.*?\n\t///? END GENERATED REPORT MEASURES\n", "\n", text, flags=re.S)
    existing = re.findall(r"^\tmeasure '([^']+)'", text, re.M)
    if existing:
        assert set(existing) <= set(MEASURES), "Existing unrelated measures require an explicit merge."
        start = text.index("\n\t/// ")
        end = text.index("\n\tcolumn ")
        text = text[:start] + text[end:]
    blocks = [""]
    for name, spec in MEASURES.items():
        blocks += ["\t/// " + spec["description"], f"\tmeasure '{name}' ="]
        blocks.extend("\t\t\t" + line for line in spec["expression"].splitlines())
        if spec["formatString"]:
            blocks.append("\t\tformatString: " + spec["formatString"])
        blocks.extend(["\t\tdisplayFolder: " + spec["folder"], ""])
    blocks.append("")
    insertion = text.index("\n\tcolumn ")
    text = text[:insertion] + "\n".join(blocks) + text[insertion:]
    host_path.write_text(text, encoding="utf-8")
    # Guard stored 0-100 percentage fields against accidental implicit SUM/percent scaling.
    for path in (MODEL / "tables").glob("analytics*.tmdl"):
        text = path.read_text(encoding="utf-8-sig")
        def safe_percent(match):
            block = match.group(0)
            block = block.replace("summarizeBy: sum", "summarizeBy: none")
            if "formatString:" not in block:
                block = block.replace("dataType: double", "dataType: double\n\t\tformatString: 0.00\\%")
            return block
        changed = re.sub(r"\tcolumn (?:observed_\w+_pct|percentage_of_records)\n.*?(?=\n\t(?:column|partition) |\Z)", safe_percent, text, flags=re.S)
        if changed != text:
            path.write_text(changed, encoding="utf-8")
    rel_path = MODEL / "relationships.tmdl"
    rel = rel_path.read_text(encoding="utf-8-sig")
    rel = re.sub(r"relationship AutoDetected_5a1ab0dd-e647-4ee4-842a-5aee3abef2dd\n.*?(?=\nrelationship|\Z)", "relationship AutoDetected_5a1ab0dd-e647-4ee4-842a-5aee3abef2dd\n\tfromCardinality: many\n\ttoCardinality: one\n\tcrossFilteringBehavior: oneDirection\n\tfromColumn: 'analytics vw_line_reliability'.line_id\n\ttoColumn: Dim_Tube_Lines.line_id\n", rel, flags=re.S)
    rel = re.sub(r"relationship AutoDetected_fa75046f-984c-4396-9355-d4dc015ae179\n.*?(?=\nrelationship|\Z)", "relationship AutoDetected_fa75046f-984c-4396-9355-d4dc015ae179\n\tfromCardinality: many\n\ttoCardinality: one\n\tcrossFilteringBehavior: oneDirection\n\tfromColumn: 'analytics vw_major_disruptions_by_line'.line_id\n\ttoColumn: Dim_Tube_Lines.line_id\n", rel, flags=re.S)
    rel_path.write_text(rel, encoding="utf-8")
    write(ROOT / "validation/measure_manifest.json", MEASURES)
    dax = "DEFINE\n" + "\n".join(f"    MEASURE {S}[{name}] = {spec['expression']}" for name, spec in MEASURES.items())
    (ROOT / "validation/measure_definitions.dax").write_text(dax + "\n", encoding="utf-8")


def build():
    update_model()
    textbox("report_title", "TfL | Transit Reliability Intelligence", 48, 28, 1424, 56, 38, WHITE, True)
    textbox("report_subtitle", "Tube Service Performance & Disruption Analytics", 48, 88, 1400, 35, 21, MUTED)
    textbox("scope_note", "NETWORK VIEW  /  KPIs, daily trend and status distribution cover all lines. The line filter applies to both bar charts.", 48, 137, 1824, 29, 15, MUTED)
    visual("tube_line_filter", "slicer", 1504, 28, 368, 100,
           objects(data={"mode": lit("Dropdown")}, selection={"singleSelect": lit(False), "selectAllCheckboxEnabled": lit(True)},
                   header={"show": lit(False)}, items={"fontColor": fill(WHITE), "background": fill(PANEL), "textSize": lit(12)},
                   general={"selfFilterEnabled": lit(True)}),
           query({"Values": [projection("Dim_Tube_Lines", "line_name", display="Tube line")]}, field("Dim_Tube_Lines", "line_name"), "Ascending"),
           container("Tube line", panel=True), "Select one or more Tube lines. Filters only the two line-level bar charts; clear selection to display all 11 lines.")
    cards = [
        ("kpi_lines", "Total Tube Lines", "GLOBAL  /  distinct monitored lines", WHITE),
        ("kpi_snapshots", "Total Historical Snapshots", "GLOBAL  /  distinct collection times", WHITE),
        ("kpi_good", "Observed Good Service %", "GLOBAL  /  line-snapshot observations", TEAL),
        ("kpi_disruption", "Observed Disruption %", "GLOBAL  /  line-snapshot observations", ORANGE),
    ]
    for i, (name, measure, subtitle, color) in enumerate(cards):
        visual(name, "card", 48 + i * 464, 184, 432, 148,
               objects(labels={"color": fill(color), "fontSize": lit(36), "fontFamily": lit("Segoe UI Semibold"), "labelDisplayUnits": lit(0), "labelPrecision": lit(2 if "%" in measure else 0)}, categoryLabels={"show": lit(False)}),
               query({"Values": [metric(measure)]}), container(measure, subtitle), MEASURES[measure]["description"])
    line_category = projection("Dim_Tube_Lines", "line_name", display="Tube line")
    visual("line_good_service", "clusteredBarChart", 48, 356, 696, 636,
           axes(TEAL, percentage=True, horizontal=True),
           query({"Category": [line_category], "Y": [metric("Line Observed Good Service %", "Observed Good Service %")], "Tooltips": [metric("Line Snapshots Observed")]}, field(HOST, "Line Observed Good Service %", True), show_all=True),
           container("Observed Good Service % by Tube Line", "LINE FILTER  /  all 11 lines when cleared; sorted by observed share"), MEASURES["Line Observed Good Service %"]["description"])
    trend = axes(ORANGE, percentage=True)
    trend["categoryAxis"][0]["properties"]["axisType"] = lit("Scalar")
    trend["lineStyles"] = [{"properties": {"strokeWidth": lit(3), "showMarker": lit(True), "markerSize": lit(7), "markerColor": fill(ORANGE), "lineChartType": lit("linear")}}]
    visual("daily_disruption", "lineChart", 768, 356, 1104, 302, trend,
           query({"Category": [projection("analytics vw_daily_disruption_trends", "observation_date", display="Observation date")], "Y": [metric("Daily Observed Disruption %")], "Tooltips": [metric("Daily Collection Times"), metric("Daily Line Observations")]}, field("analytics vw_daily_disruption_trends", "observation_date"), "Ascending"),
           container("Daily Observed Disruption %", "GLOBAL  /  Europe/London dates; markers represent sampled days; gaps are unobserved"), MEASURES["Daily Observed Disruption %"]["description"])
    status = axes(ORANGE)
    status["categoryAxis"][0]["properties"].update({"fontSize": lit(10), "maxMarginFactor": lit(35)})
    status["dataPoint"].append({"properties": {"fill": {"solid": {"color": {"expr": field(HOST, "Status Record Color", True)}}}}, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}})
    visual("status_distribution", "clusteredColumnChart", 768, 682, 540, 310, status,
           query({"Category": [projection("analytics vw_disruption_severity", "status_description", display="Status description")], "Y": [metric("Status Record Count")], "Tooltips": [metric("Status Record Share %")]}, field(HOST, "Status Record Count", True)),
           container("Status Record Distribution", "GLOBAL  /  raw records by status description; multiple statuses may coexist"), MEASURES["Status Record Count"]["description"])
    major = axes(RED, horizontal=True)
    major["categoryAxis"][0]["properties"].update({"fontSize": lit(10), "innerPadding": lit(18)})
    major["labels"][0]["properties"]["fontSize"] = lit(10)
    visual("major_disruptions", "clusteredBarChart", 1332, 682, 540, 310, major,
           query({"Category": [line_category], "Y": [metric("Major Disruption Snapshots")], "Tooltips": [metric("Severe Delay Snapshots"), metric("Closure or Suspension Snapshots"), metric("Planned Closure Snapshots")]}, field(HOST, "Major Disruption Snapshots", True), show_all=True),
           container("Major Disruption Snapshots by Tube Line", "LINE FILTER  /  SQL major categories; includes planned closures"), MEASURES["Major Disruption Snapshots"]["description"])
    # Text card keeps the context live against imported data; never substitutes current clock time.
    visual("observation_context", "card", 48, 1016, 1824, 27,
           objects(labels={"color": fill(MUTED), "fontSize": lit(10), "fontFamily": lit("Segoe UI")}, categoryLabels={"show": lit(False)}),
           query({"Values": [metric("Observation Context")]}), container(panel=False), MEASURES["Observation Context"]["description"])
    textbox("disclaimer", "Snapshot-based observations; not official TfL uptime.", 48, 1047, 1824, 26, 15, MUTED)
    page = json.loads((PAGE / "page.json").read_text(encoding="utf-8-sig"))
    page.update({"displayName": "Transit Reliability", "height": 1080, "width": 1920, "displayOption": "FitToPage",
                 "objects": objects(background={"color": fill(NAVY), "transparency": lit(0)}),
                 "visualInteractions": []})
    # Explicit isolation: all chart clicks are non-filtering; only the dimension slicer filters the line charts.
    data_visuals = [v["name"] for v in VISUALS if "query" in v["visual"]]
    for source in data_visuals:
        for target in data_visuals:
            if source != target:
                kind = "DataFilter" if source == "tube_line_filter" and target in ["line_good_service", "major_disruptions"] else "NoFilter"
                page["visualInteractions"].append({"source": source, "target": target, "type": kind})
    write(PAGE / "page.json", page)
    print(f"Built {len(VISUALS)} visuals and {len(MEASURES)} explicit measures on one 1920 x 1080 page.")


if __name__ == "__main__":
    build()
