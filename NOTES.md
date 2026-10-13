# NOTES.md — Architectural Decisions & Trade-Offs

## Architecture Overview
The application is structured into four clean layers:
1. **Data Ingestion & Cleaning Layer (`app/data_loader.py`, `app/data_cleaner.py`)**: Loads CSVs, normalizes identifiers, enforces business-key deduplication, audits anomalies, and produces an immutable `DatasetContainer`.
2. **Domain Hierarchy Layer (`app/organization.py`)**: Implements cycle-defended tree traversal using an adjacency list and BFS with visited sets to compute organization subtrees.
3. **Analytics Engine (`app/metrics.py`)**: Vectorized and dictionary-indexed seat intersection and activity matching, ensuring sub-millisecond query evaluation without repetitive dataframe scans.
4. **Presentation & API Layer (`main.py`, `templates/`, `static/`)**: FastAPI endpoints with Pydantic type validation, comprehensive HTTP status mapping, and a vanilla JavaScript single-page dashboard.

## Key Trade-Offs

- **In-Memory Pandas Container vs. Relational Database (SQLite/PostgreSQL)**:
  - *Decision*: Kept datasets in-memory using Pandas and native Python structures.
  - *Rationale*: Eliminates external database dependencies, configuration overhead, and disk concurrency locks while delivering instant sub-millisecond query performance for standard enterprise seat catalogs (< 500,000 records).
- **Index-Based Event Matching vs. Repeated Cross-Joins**:
  - *Decision*: Pre-indexed events by `(person_id, tool)` into chronological lookup buckets.
  - *Rationale*: Replaces quadratic cartesian product scans with $O(S + E)$ lookups, ensuring high throughput even across long historical date ranges.
- **Strict Query Date Validation in FastAPI**:
  - *Decision*: Enforced standard ISO `YYYY-MM-DD` and strict calendar verification via Python `datetime.strptime`.
  - *Rationale*: Prevents invalid calendar inputs (such as February 30th) from corrupting downstream arithmetic before hitting business logic.

## Known Limitations & Intentional Omissions

- **Dynamic Org Unit Updates at Runtime**: The org tree is compiled upon startup/re-load. Hot-reloading CSVs on file change is not enabled by default to ensure thread safety.
- **Authentication & Multi-Tenant RBAC**: Kept out of scope to comply with local execution constraints and zero-credential deployment.
- **Seat Reassignment Tracking**: Seats are modeled via grant and revocation date pairs. Seat transfers across users are represented as separate revoked/granted records.

## Future Improvements

1. **Incremental Activity Streaming**: Support streaming ingestion of real-time activity events via WebSockets or append-only Parquet logs.
2. **License Optimization Recommendations**: Auto-generate prescriptive recommendations for administrators (e.g. "Revoke Tool D for User X to save $100/mo").
3. **Export Capabilities**: Add one-click CSV and PDF report export from the frontend dashboard.
