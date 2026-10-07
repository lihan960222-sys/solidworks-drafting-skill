"""Offline validation. No CAD mutations, third-party packages or model inference."""
import json
import math
import os
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def validate(plan, allow_existing=False):
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def num(x):
        return type(x) in (float, int) and math.isfinite(x)

    def positive(x, name):
        require(num(x) and x > 0, name + " must be positive and finite")

    def vector(v, size, name):
        require(isinstance(v, list) and len(v) == size and all(num(x) for x in v), name + " invalid")

    require(plan.get("version") == 2, "Unsupported plan version")
    allowed = {"version", "facts", "output_drawing", "output_pdf", "template", "sheet", "views", "dimensions", "diameters", "sections", "labels", "tables", "notes", "unresolved", "output_dwg", "coverage", "dimension_ids", "model_dimensions", "import_pmi", "auto_arrange", "linear", "radial", "details", "export", "style", "dimension_scheme"}
    require(not set(plan) - allowed, "Unknown root fields: " + str(set(plan) - allowed))
    for key in ("facts", "output_drawing", "template"):
        require(isinstance(plan.get(key), str) and os.path.isabs(plan[key]), key + " must be absolute")
    require(Path(plan["facts"]).is_file(), "Facts file missing")
    require(Path(plan["template"]).is_file() and plan["template"].lower().endswith(".drwdot"), "Drawing template missing")
    require(plan["output_drawing"].lower().endswith(".slddrw"), "Native output must be .SLDDRW")
    for key in ("output_drawing", "output_pdf"):
        if key in plan:
            require(isinstance(plan[key], str) and os.path.isabs(plan[key]), key + " must be absolute")
            require(allow_existing or not Path(plan[key]).exists(), "Refusing existing output: " + plan[key])
    if "output_pdf" in plan:
        require(plan["output_pdf"].lower().endswith(".pdf"), "PDF output must be .pdf")
    facts = load(plan["facts"])
    require(facts.get("schema_version") == 2 and facts.get("document_type") == "part", "Expected part facts v1")
    require(len(facts.get("sha256", "")) == 64, "Facts lack source hash")
    sheet = plan["sheet"]
    for k in ("width_mm", "height_mm"):
        positive(sheet[k], k)
    require(type(sheet.get("first_angle")) is bool, "Projection convention must be explicit")

    def position(v, name):
        vector(v, 2, name)
        require(0 < v[0] < sheet["width_mm"] and 0 < v[1] < sheet["height_mm"], name + " outside sheet")

    def text(s, name):
        require(isinstance(s, str) and bool(s.strip()), name + " must be nonempty text")

    for k in ("views", "dimensions", "sections", "labels", "tables", "notes", "unresolved"):
        require(isinstance(plan.get(k), list), k + " must be an array")
    require(bool(plan["views"]), "Need at least one model view")
    ids = set()
    for view in plan["views"]:
        text(view["id"], "View ID")
        require(view["id"] not in ids, "Duplicate view ID")
        ids.add(view["id"])
        require(view["model_view"] in facts["model_views"], "Unknown model orientation")
        position(view["position_mm"], "View position")
        positive(view["scale"], "View scale")
        text(view["reason"], "View reason")
    for sec in plan["sections"]:
        require(sec["parent"] in ids, "Section parent unavailable")
        require(sec["id"] not in ids, "Duplicate section ID")
        text(sec["id"], "Section ID")
        text(sec["label"], "Section label")
        require(isinstance(sec["line_model_mm"], list) and len(sec["line_model_mm"]) == 2, "Section endpoints required")
        for endpoint in sec["line_model_mm"]:
            vector(endpoint, 3, "Section endpoint")
        require(sum((a-b)**2 for a, b in zip(*sec["line_model_mm"])) > 1e-6, "Degenerate cutting line")
        position(sec["position_mm"], "Section position")
        positive(sec["scale"], "Section scale")
        text(sec["reason"], "Section reason")
        ids.add(sec["id"])
    for dim in plan["dimensions"]:
        require(dim["view"] in ids, "Unknown dimension view")
        require(dim["direction"] in ("horizontal", "vertical"), "Unsupported dimension")
        positive(dim["expected_mm"], "Expected dimension")
        position(dim["position_mm"], "Dimension position")
        text(dim["evidence"], "Dimension evidence")
    edges = {e["id"]: e for e in facts["edges"]}
    require(isinstance(plan.get("diameters", []), list), "diameters must be an array")
    for dim in plan.get("diameters", []):
        require(dim["view"] in ids, "Unknown diameter view")
        require(type(dim["edge_id"]) is int and dim["edge_id"] in edges, "Unknown diameter edge")
        edge = edges[dim["edge_id"]]
        require(edge["type"] == "circle" and edge.get("persist_ref"), "Diameter needs persistent circle")
        positive(dim["expected_mm"], "Expected diameter")
        require(abs(edge["parameters_si"][6]*2000-dim["expected_mm"]) < 1e-5, "Diameter disagrees with source radius")
        position(dim["position_mm"], "Diameter position")
        text(dim["evidence"], "Diameter evidence")
    for tag in plan["labels"]:
        require(tag["view"] in ids, "Unknown label view")
        require(type(tag["edge_id"]) is int and tag["edge_id"] in edges, "Unknown edge ID")
        require(edges[tag["edge_id"]]["type"] == "circle" and edges[tag["edge_id"]].get("persist_ref"), "Need persistent circular edge")
        text(tag["text"], "Label text")
        vector(tag["offset_mm"], 2, "Label offset")
    for table in plan["tables"]:
        position(table["position_mm"], "Table position")
        positive(table["row_height_mm"], "Table row height")
        require(table["role"] in ("nominal_hole_schedule", "nominal_feature_schedule"), "Unsupported table role")
        text(table["evidence"], "Table evidence")
        widths = table["column_widths_mm"]
        require(isinstance(widths, list) and bool(widths), "Need table widths")
        for width in widths:
            positive(width, "Column width")
        rows = table["rows"]
        require(isinstance(rows, list) and bool(rows), "Need table rows")
        for row in rows:
            require(isinstance(row, list) and len(row) == len(widths) and all(isinstance(c, str) for c in row), "Unequal/non-text table cells")
        require(table["position_mm"][0] + sum(widths) < sheet["width_mm"], "Table right edge outside sheet")
        require(table["position_mm"][1] - len(rows)*table["row_height_mm"] > 0, "Table bottom outside sheet")
    for note in plan["notes"]:
        position(note["position_mm"], "Note position")
        require("font_mm" not in note, "Note font overrides unsupported; use selected template")
        text(note["text"], "Note text")
    for item in plan["unresolved"]:
        text(item, "Unresolved requirement")
    return {"status": "VALID", "views": len(ids), "dimensions": len(plan["dimensions"])+len(plan.get("diameters", [])), "labels": len(plan["labels"]), "tables": len(plan["tables"])}


if __name__ == "__main__":
    try:
        print(json.dumps(validate(load(sys.argv[1])), ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, IndexError) as exc:
        print("INVALID: " + str(exc), file=sys.stderr)
        sys.exit(1)
