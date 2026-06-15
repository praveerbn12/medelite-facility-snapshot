"""
main.py — the FastAPI web app.
Form (GET /), report (POST /report), PDF download (POST /report/pdf).
Phase 4a: validation + friendly error pages + CMS-outage handling.
Required fields: CCN (6 digits) and Current Census (whole number).
"""

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.cms import get_facility_core, FacilityNotFound, CMSUnavailable

app = FastAPI(title="Medelite Facility Assessment Snapshot")
templates = Jinja2Templates(directory="app/templates")


def validate_inputs(ccn: str, current_census: str):
    """Validate the required/numeric fields.

    Returns (clean_ccn, error_message); error_message is None if all good.
    CCN stays a STRING so leading zeros (e.g. 015010) are never lost.
    """
    ccn = ccn.strip()
    if not (len(ccn) == 6 and ccn.isdigit()):
        return ccn, "Please enter a valid 6-digit CCN (digits only) — for example, 686123."

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


def build_report_data(
    ccn, name_override, emr, current_census, patient_type,
    previous_coverage, previous_performance, medical_coverage,
):
    """Fetch CMS data and merge it with the manual inputs into one dict."""
    core = get_facility_core(ccn)  # may raise FacilityNotFound or CMSUnavailable
    name = name_override.strip() or core["provider_name"]
    return {
        **core,
        "name": name,
        "emr": emr,
        "current_census": current_census,
        "patient_type": patient_type,
        "previous_coverage": previous_coverage,
        "previous_performance": previous_performance,
        "medical_coverage": medical_coverage,
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