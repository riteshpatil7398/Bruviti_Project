# Bruviti — Software License Usage & Cost Analytics

A production-quality REST API and interactive analytics dashboard designed to monitor enterprise software seat licensing, prorated billing spend, user engagement, and idle license waste across organizational hierarchies.

Built for the **Bruviti AI Campus Hiring** engineering evaluation.

---

## 1. Project Overview

Enterprise SaaS licenses often go unused after being granted, leading to significant idle spend. This application calculates precise, prorated daily utilization and spend for enterprise tools based on:
- **Date Window Overlap**: Accurate daily proration based on a 30-day billing cycle.
- **Strict Seat Holding Intervals**: Seat starts on `granted_on` and ends on the day before `revoked_on`.
- **Recursive Organizational Scoping**: Scoping metrics to a department and all its nested sub-units.
- **Activity Attribution**: Matching validated user actions against tool licenses held on the exact date of activity.
- **Idle Spend Isolation**: Pinpointing spend allocated to seats with zero usage.

---

## 2. Prerequisites

- **Python 3.11+**
- **pip** package manager

No external databases, cloud services, or API credentials are required. Everything runs locally.

---

## 3. Repository Structure

```text
bruviti-assignment/
├── main.py                     # FastAPI entry point, routes, and exception handlers
├── requirements.txt           # Production and testing dependencies
├── README.md                  # Project overview and run guide
├── DATA.md                    # Data schemas, cleaning rules, and Appendix P notes
├── NOTES.md                   # Architecture trade-offs and design review
├── AI.md                      # AI tool usage and verification disclosures
├── .gitignore                 # Standard Python, testing, and IDE ignore rules
├── data/                      # CSV data sources (configurable via DATA_DIR)
│   ├── people.csv
│   ├── org_units.csv
│   ├── seats.csv
│   ├── price_list.csv
│   └── activity_events.csv
├── app/                       # Core application domain logic
│   ├── __init__.py
│   ├── data_loader.py         # Ingestion, validation, and container management
│   ├── data_cleaner.py        # Rule-based cleaning and anomaly auditing
│   ├── organization.py        # Tree traversal, cycle detection, and scoping
│   ├── metrics.py             # Math engine: daily proration, idleness, KPIs
│   └── schemas.py             # Pydantic schemas for requests and responses
├── static/                    # Dashboard frontend assets
│   ├── style.css              # Responsive modern CSS theme
│   └── app.js                 # Vanilla JS async API client and UI renderer
├── templates/
│   └── index.html             # Dashboard single-page template
└── tests/                     # Comprehensive automated pytest suite
    ├── __init__.py
    ├── conftest.py            # Test fixtures and synthetic data factory
    ├── test_api.py            # HTTP route validation, status codes, schemas
    ├── test_metrics.py        # Boundary math, proration, and engagement logic
    ├── test_organizations.py  # Hierarchy recursion, cycles, and scoping
    └── test_data_quality.py   # Cleaning rules, duplicates, invalid records
```

---

## 4. Setup and Installation

### Step 1: Create and Activate Virtual Environment
```bash
python -m venv venv

# On Windows (Command Prompt / PowerShell):
.\venv\Scripts\activate

# On Linux / macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 5. Running the Application

Start the local server on port **8000**:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Once running:
- **Interactive Web Dashboard**: Open [http://localhost:8000/](http://localhost:8000/) in your browser.
- **Interactive Swagger API Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs).
- **Health Check Endpoint**: Open [http://localhost:8000/health](http://localhost:8000/health).

---

## 6. Running Automated Tests

Run the complete automated test suite covering all 28 requirements:

```bash
pytest -v
```

To run with coverage reporting:
```bash
pytest -v --cov=app --cov=main
```

---

## 7. Data Placement and Startup Behavior

The service automatically reads and validates the five required CSV files from the `data/` directory upon startup:
- `org_units.csv`
- `people.csv`
- `price_list.csv`
- `seats.csv`
- `activity_events.csv`

To configure a different directory, set the `DATA_DIR` environment variable:
```bash
export DATA_DIR=/path/to/custom/data
# Windows PowerShell:
$env:DATA_DIR = "C:\path\to\custom\data"
```

If any required dataset is missing or unreadable on startup, the application logs the failure and `/health` returns `HTTP 503 Service Unavailable` until valid files are provided.

---

## 8. API Reference & Sample Payloads

### 8.1 Health Readiness Check
- **Endpoint**: `GET /health`
- **Description**: Returns 200 when all datasets are loaded, validated, and ready to serve queries.

#### Sample Response (HTTP 200 OK)
```json
{
  "status": "ok"
}
```

---

### 8.2 Company & Organization Summary
- **Endpoint**: `GET /api/summary`
- **Query Parameters**:
  - `from` *(required, string YYYY-MM-DD)*: Inclusive start date.
  - `to` *(required, string YYYY-MM-DD)*: Inclusive end date.
  - `org` *(optional, string)*: Organization unit ID filter.

#### Sample Request
```http
GET /api/summary?from=2026-05-01&to=2026-05-31&org=ORG01 HTTP/1.1
Host: localhost:8000
```

#### Sample Response (HTTP 200 OK)
*(Example payload)*
```json
{
  "licensed_users": 6,
  "active_users": 4,
  "engagement_pct": 66.7,
  "spend": 560.00,
  "idle_spend": 120.00
}
```

---

### 8.3 Tool-Wise Unit Economics
- **Endpoint**: `GET /api/tools`
- **Query Parameters**: Same as `/api/summary` (`from`, `to`, `org`).
- **Description**: Returns an array of exactly 5 tools in canonical order (`Tool A` through `Tool E`).

#### Sample Request
```http
GET /api/tools?from=2026-05-01&to=2026-05-31 HTTP/1.1
Host: localhost:8000
```

#### Sample Response (HTTP 200 OK)
*(Example payload)*
```json
[
  {
    "tool": "Tool A",
    "licensed_users": 3,
    "active_users": 2,
    "engagement_pct": 66.7,
    "spend": 154.00,
    "idle_spend": 62.00,
    "cost_per_active": 77.00
  },
  {
    "tool": "Tool B",
    "licensed_users": 3,
    "active_users": 2,
    "engagement_pct": 66.7,
    "spend": 465.00,
    "idle_spend": 155.00,
    "cost_per_active": 232.50
  },
  {
    "tool": "Tool C",
    "licensed_users": 3,
    "active_users": 2,
    "engagement_pct": 66.7,
    "spend": 213.00,
    "idle_spend": 93.00,
    "cost_per_active": 106.50
  },
  {
    "tool": "Tool D",
    "licensed_users": 2,
    "active_users": 2,
    "engagement_pct": 100.0,
    "spend": 370.00,
    "idle_spend": 0.00,
    "cost_per_active": 185.00
  },
  {
    "tool": "Tool E",
    "licensed_users": 2,
    "active_users": 1,
    "engagement_pct": 50.0,
    "spend": 192.00,
    "idle_spend": 68.00,
    "cost_per_active": 192.00
  }
]
```

---

## 9. Error Handling Standards

All endpoints enforce consistent JSON error contracts:
- `HTTP 400 Bad Request`: Returned when date parameters are missing, malformed, or when `from > to`.
  ```json
  {
    "detail": "The 'from' date (2024-02-01) must be less than or equal to the 'to' date (2024-01-01)."
  }
  ```
- `HTTP 404 Not Found`: Returned when an unknown organization ID is supplied.
  ```json
  {
    "detail": "Organization unit 'UNKNOWN_ORG' not found."
  }
  ```
- `HTTP 503 Service Unavailable`: Returned if datasets failed validation upon startup.
