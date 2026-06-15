"""
main.py — the FastAPI web app.
Form (GET /), report (POST /report), PDF download (POST /report/pdf).
Phase 4a: validation + friendly error pages + CMS-outage handling.
Required fields: CCN (6 digits) and Current Census (whole number).
"""
import base64
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.cms import (
    get_facility_core, get_metrics_comparison, format_metric,
    FacilityNotFound, CMSUnavailable,
)

app = FastAPI(title="Medelite Facility Assessment Snapshot")
templates = Jinja2Templates(directory="app/templates")

# Load the corporate logo once and inline it as a base64 data URI, so it
# renders identically in the browser and in the WeasyPrint PDF — no dependency
# on static-file serving or file-path resolution. Falls back to the text
# banner if the file is missing.
_LOGO_PATH = Path(__file__).parent / "static" / "medelite-logo.png"
try:
    _logo_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    LOGO_DATA_URI = f"data:image/png;base64,{_logo_b64}"
except FileNotFoundError:
    LOGO_DATA_URI = ""

# Make it available to every template (web pages and the PDF).
templates.env.globals["logo_data_uri"] = LOGO_DATA_URI


def validate_inputs(ccn: str, current_census: str):
    """Validate the required/numeric fields.

    Returns (clean_ccn, error_message); error_message is None if all good.
    CCN stays a STRING so leading zeros (e.g. 015010) are never lost.
    """
    ccn = ccn.strip()
    if not (len(ccn) == 6 and ccn.isdigit()):
        return ccn, "Please enter a valid 6-digit CCN (digits only) — for example, 123456."

    census = current_census.strip()
    if not census:
        return ccn, "Current Census is required. Enter the facility's current resident count (for example, 112)."
    if not census.isdigit():
        return ccn, "Current Census must be a whole number (for example, 112)."

    return ccn, None


def render_error(request: Request, message: str, status_code: int = 400):
    """Render the friendly error page (keeps the INFINITE banner)."""
    return templates.TemplateResponse(
        request, "error.html", {"message": message}, status_code=status_code
    )


# def build_report_data(
#     ccn, name_override, emr, current_census, patient_type,
#     previous_coverage, previous_performance, medical_coverage,
# ):
#     """Fetch CMS data + metrics, merge with manual inputs into one dict."""
#     core = get_facility_core(ccn)
#     name = name_override.strip() or core["provider_name"]

#     metrics = get_metrics_comparison(ccn, core["state"])
#     by_key = {row["key"]: row for row in metrics}

#     def fmt(key, which):
#         m = by_key[key]
#         return format_metric(m[which], m["unit"])

#     def tone(key):
#         """Lower is better for all four measures: green if the facility is below
#         the national average, red if above, neutral if either value is missing."""
#         fac, nat = by_key[key]["facility"], by_key[key]["national"]
#         if fac is None or nat is None:
#             return "neutral"
#         if fac < nat:
#             return "good"
#         if fac > nat:
#             return "bad"
#         return "neutral"

#     # 12 rows in the template's order. Facility rows carry a tone; benchmarks stay neutral.
#     metrics_rows = [
#         ("Short Term Hospitalization",                  fmt("str_hospitalization", "facility"), tone("str_hospitalization")),
#         ("STR National Avg. for Hospitalization",       fmt("str_hospitalization", "national"), "neutral"),
#         ("STR State National Avg. for Hospitalization", fmt("str_hospitalization", "state"),    "neutral"),
#         ("STR ED Visit",                                fmt("str_ed_visit", "facility"),        tone("str_ed_visit")),
#         ("STR ED Visits National Avg.",                 fmt("str_ed_visit", "national"),        "neutral"),
#         ("STR ED Visits State Avg.",                    fmt("str_ed_visit", "state"),           "neutral"),
#         ("LT Hospitalization",                          fmt("lt_hospitalization", "facility"),  tone("lt_hospitalization")),
#         ("LT National Avg. for Hospitalization",        fmt("lt_hospitalization", "national"),  "neutral"),
#         ("LT State National Avg. for Hospitalization",  fmt("lt_hospitalization", "state"),     "neutral"),
#         ("ED Visit",                                    fmt("lt_ed_visit", "facility"),         tone("lt_ed_visit")),
#         ("LT ED Visits National Avg.",                  fmt("lt_ed_visit", "national"),         "neutral"),
#         ("LT ED Visits State Avg.",                     fmt("lt_ed_visit", "state"),            "neutral"),
#     ]

#     return {
#         **core,
#         "name": name,
#         "emr": emr,
#         "current_census": current_census,
#         "patient_type": patient_type,
#         "previous_coverage": previous_coverage,
#         "previous_performance": previous_performance,
#         "medical_coverage": medical_coverage,
#         "metrics_rows": metrics_rows,
#     }

def build_report_data(
    ccn, name_override, emr, current_census, patient_type,
    previous_coverage, previous_performance, medical_coverage,
):
    """Fetch CMS data + metrics, merge with manual inputs into one dict."""
    core = get_facility_core(ccn)
    name = name_override.strip() or core["provider_name"]

    metrics = get_metrics_comparison(ccn, core["state"])
    by_key = {row["key"]: row for row in metrics}

    def fmt(key, which):
        m = by_key[key]
        return format_metric(m[which], m["unit"])

    def tone(key):
        """Lower is better for all four measures: green if facility is below the
        national average, red if above, neutral if either value is missing."""
        fac, nat = by_key[key]["facility"], by_key[key]["national"]
        if fac is None or nat is None:
            return "neutral"
        if fac < nat:
            return "good"
        if fac > nat:
            return "bad"
        return "neutral"

    metrics_rows = [
        ("Short Term Hospitalization",                  fmt("str_hospitalization", "facility"), tone("str_hospitalization")),
        ("STR National Avg. for Hospitalization",       fmt("str_hospitalization", "national"), "neutral"),
        ("STR State National Avg. for Hospitalization", fmt("str_hospitalization", "state"),    "neutral"),
        ("STR ED Visit",                                fmt("str_ed_visit", "facility"),        tone("str_ed_visit")),
        ("STR ED Visits National Avg.",                 fmt("str_ed_visit", "national"),        "neutral"),
        ("STR ED Visits State Avg.",                    fmt("str_ed_visit", "state"),           "neutral"),
        ("LT Hospitalization",                          fmt("lt_hospitalization", "facility"),  tone("lt_hospitalization")),
        ("LT National Avg. for Hospitalization",        fmt("lt_hospitalization", "national"),  "neutral"),
        ("LT State National Avg. for Hospitalization",  fmt("lt_hospitalization", "state"),     "neutral"),
        ("ED Visit",                                    fmt("lt_ed_visit", "facility"),         tone("lt_ed_visit")),
        ("LT ED Visits National Avg.",                  fmt("lt_ed_visit", "national"),         "neutral"),
        ("LT ED Visits State Avg.",                     fmt("lt_ed_visit", "state"),            "neutral"),
    ]

    # Grouped comparison bars, normalized per measure (units differ across measures).
    chart_measures = [
        ("str_hospitalization", "Short-Term Hospitalization"),
        ("str_ed_visit",        "Short-Term ED Visit"),
        ("lt_hospitalization",  "Long-Term Hospitalization"),
        ("lt_ed_visit",         "Long-Term ED Visit"),
    ]
    metrics_chart = []
    for key, label in chart_measures:
        row = by_key[key]
        series = [
            ("Facility", row["facility"], True),
            ("National", row["national"], False),
            ("State",    row["state"],    False),
        ]
        present = [v for _, v, _ in series if v is not None]
        vmax = max(present) if present else 0
        bars = [
            {
                "name": nm,
                "value": format_metric(v, row["unit"]),
                "width": round(v / vmax * 100, 1) if (v is not None and vmax) else 0,
                "is_facility": is_fac,
            }
            for nm, v, is_fac in series
        ]
        metrics_chart.append({"label": label, "tone": tone(key), "bars": bars})

    return {
        **core,
        "name": name,
        "emr": emr,
        "current_census": current_census,
        "patient_type": patient_type,
        "previous_coverage": previous_coverage,
        "previous_performance": previous_performance,
        "medical_coverage": medical_coverage,
        "metrics_rows": metrics_rows,
        "metrics_chart": metrics_chart,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/report", response_class=HTMLResponse)
def report(
    request: Request,
    ccn: str = Form(...),
    name_override: str = Form(""),
    emr: str = Form(""),
    current_census: str = Form(""),
    patient_type: str = Form(""),
    previous_coverage: str = Form(""),
    previous_performance: str = Form(""),
    medical_coverage: str = Form(""),
):
    ccn, error = validate_inputs(ccn, current_census)
    if error:
        return render_error(request, error, status_code=400)

    try:
        data = build_report_data(
            ccn, name_override, emr, current_census, patient_type,
            previous_coverage, previous_performance, medical_coverage,
        )
    except FacilityNotFound:
        return render_error(
            request,
            f"We couldn't find a facility with CCN {ccn}. Double-check the number and try again.",
            status_code=404,
        )
    except CMSUnavailable:
        return render_error(
            request,
            "We couldn't reach the CMS data service right now. Please try again in a moment.",
            status_code=503,
        )

    return templates.TemplateResponse(request, "report.html", {"data": data})


@app.post("/report/pdf")
def report_pdf(
    request: Request,
    ccn: str = Form(...),
    name_override: str = Form(""),
    emr: str = Form(""),
    current_census: str = Form(""),
    patient_type: str = Form(""),
    previous_coverage: str = Form(""),
    previous_performance: str = Form(""),
    medical_coverage: str = Form(""),
):
    ccn, error = validate_inputs(ccn, current_census)
    if error:
        return render_error(request, error, status_code=400)

    try:
        data = build_report_data(
            ccn, name_override, emr, current_census, patient_type,
            previous_coverage, previous_performance, medical_coverage,
        )
    except FacilityNotFound:
        return render_error(
            request,
            f"We couldn't find a facility with CCN {ccn}. Double-check the number and try again.",
            status_code=404,
        )
    except CMSUnavailable:
        return render_error(
            request,
            "We couldn't reach the CMS data service right now. Please try again in a moment.",
            status_code=503,
        )

    html_string = templates.env.get_template("pdf.html").render(data=data)
    pdf_bytes = HTML(string=html_string).write_pdf()

    filename = f"facility_snapshot_{data['ccn']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Debug JSON endpoint — raw API, so JSON errors are fine here.
@app.get("/api/facility/{ccn}")
def facility(ccn: str):
    try:
        return get_facility_core(ccn)
    except FacilityNotFound:
        raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")
    except CMSUnavailable:
        raise HTTPException(status_code=503, detail="CMS data service unavailable")

# @app.get("/api/debug/metrics-check/{ccn}")
# def debug_metrics_check(ccn: str):
#     """TEMPORARY: verify all 12 numbers before we render them anywhere."""
#     from app.cms import get_facility_core, get_metrics_comparison, format_metric
#     core = get_facility_core(ccn)
#     rows = get_metrics_comparison(ccn, core["state"])
#     for r in rows:
#         r["facility_fmt"] = format_metric(r["facility"], r["unit"])
#         r["national_fmt"] = format_metric(r["national"], r["unit"])
#         r["state_fmt"] = format_metric(r["state"], r["unit"])
#     return {"state": core["state"], "metrics": rows}