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