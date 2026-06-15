"""
cms.py — talks to the public CMS Provider Data Catalog API.
Given a CCN, fetch the facility's row and return the core report fields.
"""

import requests

PDC_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"
PROVIDER_INFO_DATASET = "4pq5-n9py"
REQUEST_TIMEOUT = 10


class FacilityNotFound(Exception):
    """Raised when no facility matches the given CCN."""
    pass


class CMSUnavailable(Exception):
    """Raised when the CMS API can't be reached or returns an error."""
    pass


def _query_dataset(dataset_id: str, ccn: str) -> list[dict]:
    """Filter one CMS dataset by CCN; return the list of matching rows."""
    url = f"{PDC_BASE}/{dataset_id}/0"
    params = {
        "conditions[0][property]": "cms_certification_number_ccn",
        "conditions[0][value]": ccn,
        "conditions[0][operator]": "=",
    }
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json().get("results", [])
    except requests.RequestException as exc:
        raise CMSUnavailable(str(exc)) from exc


def get_facility_core(ccn: str) -> dict:
    """Fetch the core report fields for one facility, by CCN.

    Raises FacilityNotFound if the CCN matches nothing,
    or CMSUnavailable if CMS can't be reached.
    """
    rows = _query_dataset(PROVIDER_INFO_DATASET, ccn)
    if not rows:
        raise FacilityNotFound(f"No facility found for CCN {ccn}")

    row = rows[0]
    return {
        "ccn": row.get("cms_certification_number_ccn", ccn),
        "provider_name": row.get("provider_name", ""),
        "location": _format_location(row),
        "state": row.get("state", ""),
        "certified_beds": row.get("number_of_certified_beds", ""),
        "ratings": {
            "overall": row.get("overall_rating", ""),
            "health_inspection": row.get("health_inspection_rating", ""),
            "staffing": row.get("staffing_rating", ""),
            "quality_of_care": row.get("qm_rating", ""),
        },
        "processing_date": row.get("processing_date", ""),
        "care_compare_url":
            f"https://www.medicare.gov/care-compare/details/nursing-home/{ccn}",
    }


def _format_location(row: dict) -> str:
    """Build a readable address like '5280 SW 157 AVE, MIAMI, FL'."""
    parts = [
        row.get("provider_address", ""),
        row.get("citytown", ""),
        row.get("state", ""),
    ]
    return ", ".join(p for p in parts if p)



# ---------------------------------------------------------------------------
# Phase 4b: claims-based hospitalization / ED metrics
# ---------------------------------------------------------------------------

CLAIMS_DATASET = "ijh5-nb2v"
AVERAGES_DATASET = "xcdc-v8bm"

# Our 4 measures: measure_code -> (clean key, label, unit)
#   unit "%"    = short-stay percentage
#   unit "rate" = long-stay count per 1,000 resident-days
CLAIMS_MEASURES = {
    "521": ("str_hospitalization", "Short-Stay Rehospitalization", "%"),
    "522": ("str_ed_visit",        "Short-Stay ED Visit",          "%"),
    "551": ("lt_hospitalization",  "Long-Stay Hospitalization",    "rate"),
    "552": ("lt_ed_visit",         "Long-Stay ED Visit",           "rate"),
}

# State/US Averages column name for each measure. These were read from the LIVE
# schema — CMS truncates + hashes long column names, so they can't be guessed.
AVERAGES_FIELDS = {
    "str_hospitalization": "percentage_of_short_stay_residents_who_were_rehospitalized__1d02",
    "str_ed_visit":        "percentage_of_short_stay_residents_who_had_an_outpatient_em_d911",
    "lt_hospitalization":  "number_of_hospitalizations_per_1000_longstay_resident_days",
    "lt_ed_visit":         "number_of_outpatient_emergency_department_visits_per_1000_l_de9d",
}


def _to_float(value):
    """Parse a CMS string into a float, or None if missing/blank."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_facility_metrics(ccn: str) -> dict:
    """This facility's 4 claims-based metrics, keyed by our clean keys."""
    rows = _query_dataset(CLAIMS_DATASET, ccn)   # may raise CMSUnavailable
    by_code = {r.get("measure_code"): r for r in rows}

    result = {}
    for code, (key, label, unit) in CLAIMS_MEASURES.items():
        row = by_code.get(code)
        if row is None:
            result[key] = {"value": None, "label": label, "unit": unit}
            continue
        # Care Compare shows the risk-adjusted score; fall back to observed.
        raw = row.get("adjusted_score") or row.get("observed_score")
        result[key] = {"value": _to_float(raw), "label": label, "unit": unit}
    return result


def _averages_row(state_or_nation: str) -> dict:
    """Fetch one row (NATION or a state) from the State/US Averages dataset."""
    url = f"{PDC_BASE}/{AVERAGES_DATASET}/0"
    params = {
        "conditions[0][property]": "state_or_nation",
        "conditions[0][value]": state_or_nation,
        "conditions[0][operator]": "=",
    }
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        results = response.json().get("results", [])
    except requests.RequestException as exc:
        raise CMSUnavailable(str(exc)) from exc
    return results[0] if results else {}


def get_metrics_comparison(ccn: str, state: str) -> list[dict]:
    """Combine facility values with national + state averages: 4 comparison rows."""
    facility = get_facility_metrics(ccn)
    national_row = _averages_row("NATION")
    state_row = _averages_row(state) if state else {}

    rows = []
    for code, (key, label, unit) in CLAIMS_MEASURES.items():
        field = AVERAGES_FIELDS[key]
        rows.append({
            "key": key,
            "label": label,
            "unit": unit,
            "facility": facility.get(key, {}).get("value"),
            "national": _to_float(national_row.get(field)),
            "state": _to_float(state_row.get(field)),
        })
    return rows


def format_metric(value, unit) -> str:
    """Display a metric, or 'Not available' if missing."""
    if value is None:
        return "Not available"
    return f"{value:.1f}%" if unit == "%" else f"{value:.2f}"