# """
# main.py — the FastAPI web app.

# Phase 1 scope: one endpoint that takes a CCN and returns the core
# facility data as JSON, to prove the data layer works before any UI.
# """

# from fastapi import FastAPI, HTTPException

# from app.cms import get_facility_core, FacilityNotFound

# app = FastAPI(title="Medelite Facility Assessment Snapshot")


# @app.get("/api/facility/{ccn}")
# def facility(ccn: str):
#     """Return the core report data for a given CCN."""
#     try:
#         return get_facility_core(ccn)
#     except FacilityNotFound:
#         raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")


# """
# main.py — the FastAPI web app.

# Phase 2 scope: a form page (GET /) and a report page (POST /report)
# that merges live CMS data with the user's manual inputs.
# """

# from fastapi import FastAPI, HTTPException, Request, Form
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates

# from app.cms import get_facility_core, FacilityNotFound

# app = FastAPI(title="Medelite Facility Assessment Snapshot")
# templates = Jinja2Templates(directory="app/templates")


# @app.get("/", response_class=HTMLResponse)
# def index(request: Request):
#     """Show the input form."""
#     return templates.TemplateResponse(request, "index.html")


# @app.post("/report", response_class=HTMLResponse)
# def report(
#     request: Request,
#     ccn: str = Form(...),
#     name_override: str = Form(""),
#     emr: str = Form(""),
#     current_census: str = Form(""),
#     patient_type: str = Form(""),
#     previous_coverage: str = Form(""),
#     previous_performance: str = Form(""),
#     medical_coverage: str = Form(""),
# ):
#     """Fetch CMS data, merge with manual inputs, render the report."""
#     try:
#         core = get_facility_core(ccn)
#     except FacilityNotFound:
#         raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")

#     # Name rule: user override wins; otherwise the official CMS name.
#     name = name_override.strip() or core["provider_name"]

#     # Combine CMS data + manual inputs into one object for the template.
#     data = {
#         **core,
#         "name": name,
#         "emr": emr,
#         "current_census": current_census,
#         "patient_type": patient_type,
#         "previous_coverage": previous_coverage,
#         "previous_performance": previous_performance,
#         "medical_coverage": medical_coverage,
#     }
#     return templates.TemplateResponse(request, "report.html", {"data": data})


# # Phase 1 JSON endpoint kept for debugging.
# @app.get("/api/facility/{ccn}")
# def facility(ccn: str):
#     try:
#         return get_facility_core(ccn)
#     except FacilityNotFound:
#         raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")



"""
main.py — the FastAPI web app.
Form (GET /), report (POST /report), PDF download (POST /report/pdf).
"""

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.cms import get_facility_core, FacilityNotFound

app = FastAPI(title="Medelite Facility Assessment Snapshot")
templates = Jinja2Templates(directory="app/templates")


def build_report_data(
    ccn, name_override, emr, current_census, patient_type,
    previous_coverage, previous_performance, medical_coverage,
):
    """Fetch CMS data and merge it with the manual inputs into one dict."""
    core = get_facility_core(ccn)  # may raise FacilityNotFound
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
    try:
        data = build_report_data(
            ccn, name_override, emr, current_census, patient_type,
            previous_coverage, previous_performance, medical_coverage,
        )
    except FacilityNotFound:
        raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")
    return templates.TemplateResponse(request, "report.html", {"data": data})


@app.post("/report/pdf")
def report_pdf(
    ccn: str = Form(...),
    name_override: str = Form(""),
    emr: str = Form(""),
    current_census: str = Form(""),
    patient_type: str = Form(""),
    previous_coverage: str = Form(""),
    previous_performance: str = Form(""),
    medical_coverage: str = Form(""),
):
    try:
        data = build_report_data(
            ccn, name_override, emr, current_census, patient_type,
            previous_coverage, previous_performance, medical_coverage,
        )
    except FacilityNotFound:
        raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")

    html_string = templates.env.get_template("pdf.html").render(data=data)
    pdf_bytes = HTML(string=html_string).write_pdf()

    filename = f"facility_snapshot_{data['ccn']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/facility/{ccn}")
def facility(ccn: str):
    try:
        return get_facility_core(ccn)
    except FacilityNotFound:
        raise HTTPException(status_code=404, detail=f"No facility found for CCN {ccn}")