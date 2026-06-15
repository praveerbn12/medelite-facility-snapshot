# Facility Assessment Snapshot

A lightweight web app for sizing up a skilled nursing facility before outreach. Enter a facility's **CCN (CMS Certification Number)**, and the app pulls live public data from CMS, merges it with manual operational inputs, and produces a polished one-page report — downloadable as a print-ready **PDF** or an editable **Word document**.

- **Live app:** https://medelite-facility-snapshot.onrender.com
- **Repository:** https://github.com/praveerbn12/medelite-facility-snapshot

Try CCN `686123` (Kendall Lakes Healthcare and Rehab Center, FL) or `335774` (Seton Health at Schuyler Ridge, NY).

---

## Quickstart

**Run locally**

```bash
git clone https://github.com/praveerbn12/medelite-facility-snapshot.git
cd medelite-facility-snapshot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000.

**Run with Docker**

```bash
docker build -t medelite-snapshot .
docker run -p 8000:8000 medelite-snapshot
```

No API key is required — CMS public data is free and open.

---

## Requirements coverage

**Required (MVP)**

- [x] Dynamic CCN lookup — enter any valid CCN to fetch that facility
- [x] CMS data engine — pulls location, star ratings, and metadata from the CMS Provider Data Catalog API
- [x] Facility name override — defaults to the official CMS legal name, overridable with a custom internal name
- [x] Manual operational inputs — EMR, Current Census, Patient Type, Medelite history, medical coverage
- [x] One-click PDF export — clean, print-ready download
- [x] Clickable Medicare Care Compare hyperlink in the PDF, built dynamically from the CCN
- [x] Corporate branding header ("INFINITE — Managed by MEDELITE") on both the web UI and the exports
- [x] Live deployment + public repository

**Optional bonus features — all four implemented**

- [x] All 12 short-stay (STR) and long-stay (LT) hospitalization/ED metrics, with state and national averages
- [x] Visual performance cards — color-coded rows and per-measure comparison bars (facility vs. national vs. state)
- [x] Advanced error handling — input validation and friendly handling of invalid CCNs and CMS outages
- [x] Editable Word (.docx) export

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Web framework | FastAPI + Jinja2 (server-rendered) |
| Styling (web) | Tailwind CSS (CDN) |
| PDF export | WeasyPrint |
| Word export | python-docx |
| CMS data | requests → CMS Provider Data Catalog API |
| Deployment | Docker on Render |

---

## Key engineering decisions

- **Server-rendered FastAPI over a single-page app.** This is a data-in, document-out tool with no rich client interactivity, so a server-rendered app is a single deployable artifact with no client/server split. An SPA's build tooling and separate API layer would have been overhead with no payoff here.

- **A dedicated, plain-CSS template drives the PDF.** WeasyPrint renders HTML/CSS but does not execute JavaScript, so the Tailwind-via-CDN web page can't be reused for the PDF. A separate print stylesheet gives precise, reliable page control — page one is the complete data table, page two is the benchmark charts.

- **CCN is handled as a string, never an integer.** CMS Certification Numbers are 6-character text values with meaningful leading zeros; coercing them to integers would silently corrupt the lookup.

- **Always live data, stamped with its source date.** CMS refreshes its datasets roughly monthly, so the app fetches current values on every request and stamps the report with "Data as of {processing date}." This is also why live numbers differ from the static sample in the brief (see *Data drift* below).

- **The "INFINITE" brand is hardcoded and never overwritten.** The branding banner is a fixed platform name, deliberately kept independent of the CMS/facility name. The facility name lives only inside the report body. The logo is embedded as a base64 data URI so the branding is self-contained in both the web page and the (JavaScript-free) PDF, with a text fallback if the asset is missing.

- **The Word export is data-focused by design.** The .docx reproduces the full data table with the same color-coded comparison cues (below/above the national average). The benchmark bars are intentionally web- and PDF-only: Word has no clean native bar primitive, and the editable document's purpose is data you can revise, not a fixed visualization.

---

## Data mapping notes

The 12 hospitalization/ED measures come from the CMS claims-based dataset. Per the brief's guidance, the report's **STR** shorthand maps to CMS **Short-Stay** resident metrics and **LT** maps to **Long-Stay** metrics. The verbose government field names are programmatically renamed to the report's clean labels.

---

## Assumptions

The brief invited reasonable engineering assumptions where the spec was ambiguous. The notable ones:

- **Current Census is treated as a required input.** It's central to the snapshot, so it's validated as a required numeric field. The remaining manual fields (EMR, Patient Type, Medelite history, medical coverage) are optional and fall back to "Not provided."

- **The 12 metric labels are reproduced verbatim from the Medelite template** — including its internal inconsistencies. For example, the long-stay ED facility row is labeled simply "ED Visit" while its averages read "LT ED Visits," and "Short Term Hospitalization" is spelled out while "LT Hospitalization" is abbreviated. These were preserved for fidelity to the provided template; the chart uses clean, consistent naming ("Short-Term / Long-Term").

- **Branding uses the INFINITE/MEDELITE logo image**, with a text banner as a fallback.

### Data drift

The sample outputs shown in the brief reflect an earlier CMS data refresh. Because the app always pulls live data, current values for the same facility will differ from the sample — this is expected, and the report stamps the actual source date for transparency.

---

## Project structure

```
.
├── app/
│   ├── main.py            # FastAPI routes: form, report, PDF, Word
│   ├── cms.py             # CMS API client + field mapping
│   ├── docx_report.py     # Word (.docx) generation
│   ├── static/            # Logo asset
│   └── templates/         # Jinja2: index, report, pdf, error
├── Dockerfile
└── requirements.txt
```

---

## Possible next steps

- Cache CMS responses to avoid refetching on repeated lookups of the same CCN.
- Swap `requests` for an async HTTP client to fetch the provider, claims, and averages datasets concurrently.
- Add a small automated test suite around the data-mapping and validation logic.
- Add retry/backoff handling for CMS rate limits.
