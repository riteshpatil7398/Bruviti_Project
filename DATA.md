# DATA.md — Dataset Schemas, Quality Rules & Appendix P Assumptions

## 1. Dataset Availability & Inspection Findings

The official enterprise dataset files were provided directly for the project:
1. `org_units.csv` (37 organizational units spanning L3 to L6 hierarchy)
2. `people.csv` (400 enterprise users across all teams)
3. `price_list.csv` (Tiered pricing for tools A through E, including standard, pro, enterprise)
4. `seats.csv` (Hundreds of seat lifecycle records across 2026)
5. `activity_events.csv` (Missing from initial input paste; generated as a clearly separated 2026 development fixture to ensure immediate end-to-end operation, pending official file provision)

---

## 2. Dataset Schemas & Normalization

The ingestion layer (`app/data_cleaner.py`, `app/data_loader.py`) supports the canonical field aliases and structures:

### 2.1 `org_units.csv`
Represents the organizational hierarchy.
| Column | Type | Nullable | Description |
|---|---|---|---|
| `org_unit_id` (alias: `org_id`) | String | No | Unique business key (`ORG01` through `ORG37`). |
| `name` | String | No | Name of unit (e.g. `Engineering`, `Platform`, `Data`). |
| `parent_id` | String | Yes | Foreign key pointing to parent `org_unit_id`. Empty for root `ORG01`. |
| `level` | String | Yes | Organizational depth (`L3` root down to `L6` teams). |

### 2.2 `people.csv`
Represents enterprise employees.
| Column | Type | Nullable | Description |
|---|---|---|---|
| `user_id` (alias: `person_id`) | String | No | Unique business key (`U0001` through `U0400`). |
| `name` | String | No | Full name of the user. |
| `org_unit_id` (alias: `org_id`) | String | No | Foreign key linking user to their organizational unit. |
| `role` | String | Yes | Job role (e.g., `Senior Developer`, `Lead`). |
| `location` | String | Yes | Office location (e.g., `Bengaluru`, `Pune`, `Hyderabad`). |

### 2.3 `price_list.csv`
Catalog of monthly license prices with multi-tier support.
| Column | Type | Nullable | Description |
|---|---|---|---|
| `tool` | String | No | Tool identifier (`A`, `B`, `C`, `D`, `E` or `Tool A` ... `Tool E`). |
| `tier` | String | Yes | License tier (`standard`, `pro`, `enterprise`). |
| `monthly_price_usd` (alias: `monthly_price`) | Float | Yes | 30-day billing price. Empty for unpriced tools (e.g., `Tool E`). |

#### Official Pricing Matrix:
- **Tool A**: Standard = $19/mo, Pro = $39/mo
- **Tool B**: Standard = $25/mo
- **Tool C**: Standard = $30/mo, Enterprise = $60/mo
- **Tool D**: Standard = $20/mo
- **Tool E**: Standard = Unpriced / Free tier (spend = $0.00)

### 2.4 `seats.csv`
Seat grant and revocation lifecycle records.
| Column | Type | Nullable | Description |
|---|---|---|---|
| `user_id` (alias: `person_id`) | String | No | Identifier of the employee assigned the seat. |
| `tool` | String | No | Tool identifier (`A`–`E` / `Tool A`–`Tool E`). |
| `tier` | String | Yes | License tier allocated to this seat (`standard`, `pro`, `enterprise`). |
| `granted_on` | Date (YYYY-MM-DD) | No | Inclusive date on which the seat holding starts (Year 2026). |
| `revoked_on` | Date (YYYY-MM-DD) | Yes | First date without the seat. Null for open-ended seats. |

### 2.5 `activity_events.csv`
Usage activity events.
| Column | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | String | Yes | Unique event tracking identifier. |
| `person_id` (alias: `user_id`) | String | No | User executing the tool action. |
| `tool` | String | No | Tool on which the activity was performed (`Tool A`–`Tool E`). |
| `timestamp` / `date` | Timestamp/Date | No | Event timestamp (`YYYY-MM-DD HH:MM:SS`) or date (`YYYY-MM-DD`). |
| `activity_type` | String | Yes | Action type (e.g., `login`, `query`, `api_call`). |

---

## 3. Data Cleaning and Validation Rules

Data cleaning is applied strictly in-memory without altering source files:

| Rule ID | Dataset | Trigger Condition | Cleaning Action & Impact | Severity |
|---|---|---|---|---|
| `RULE-ORG-1` | `org_units` | Leading/trailing whitespace | Stripped from all string fields. | Normalization |
| `RULE-ORG-2` | `org_units` | Missing `org_id` or `name` | Row dropped. | ERROR |
| `RULE-ORG-3` | `org_units` | Duplicate `org_id` | First occurrence retained; duplicates dropped. | WARNING |
| `RULE-ORG-4` | `org_units` | `parent_id == org_id` | Cycle broken by setting `parent_id = None`. | WARNING |
| `RULE-PPL-1` | `people` | Leading/trailing whitespace | Stripped from all string fields. | Normalization |
| `RULE-PPL-2` | `people` | Missing `person_id` | Row dropped. | ERROR |
| `RULE-PPL-3` | `people` | Duplicate `person_id` | First occurrence retained; duplicates dropped. | WARNING |
| `RULE-PPL-4` | `people` | `org_id` not in `org_units` | Logged in audit trail; record retained as orphan. | WARNING |
| `RULE-PRC-1` | `price_list` | Tool name variant (`A` vs `Tool A`) | Canonicalized to `Tool A` ... `Tool E`. | Normalization |
| `RULE-PRC-2` | `price_list` | Missing `tool` name | Row dropped. | ERROR |
| `RULE-PRC-3` | `price_list` | Duplicate `(tool, tier)` entry | First occurrence retained; duplicates dropped. | WARNING |
| `RULE-PRC-4` | `price_list` | Negative monthly price | Row dropped. | ERROR |
| `RULE-SEAT-1` | `seats` | Tool name variant (`A` vs `Tool A`) | Canonicalized to `Tool A` ... `Tool E`. | Normalization |
| `RULE-SEAT-2` | `seats` | Missing `person_id`, `tool`, or `granted_on` | Row dropped. | ERROR |
| `RULE-SEAT-3` | `seats` | Unparseable `granted_on` | Row dropped. | ERROR |
| `RULE-SEAT-4` | `seats` | Unparseable `revoked_on` | Row dropped. | ERROR |
| `RULE-SEAT-5` | `seats` | `revoked_on < granted_on` | Chronologically invalid grant; row dropped. | ERROR |
| `RULE-SEAT-6` | `seats` | Duplicate `(person_id, tool, tier, granted_on)` | First grant retained; duplicate dropped. | WARNING |
| `RULE-EVT-1` | `activity_events` | Tool name variant | Canonicalized to `Tool A` ... `Tool E`. | Normalization |
| `RULE-EVT-2` | `activity_events` | Missing `person_id`, `tool`, or date | Row dropped. | ERROR |
| `RULE-EVT-3` | `activity_events` | Unparseable date/timestamp | Row dropped. | ERROR |
| `RULE-EVT-4` | `activity_events` | Duplicate `event_id` | First occurrence retained; duplicates dropped. | WARNING |

---

## 4. Date Window & Proration Math

1. **Inclusive Window**: For requested `from` and `to`, both boundary dates are included:
   $$\text{eligible\_window} = [from, to]$$
2. **Seat Holding Period**:
   - Starts on `granted_on` (inclusive).
   - Ends on `revoked_on - 1 day` (inclusive) because `revoked_on` is explicitly the first day *without* the seat.
   - If `revoked_on` is null, seat is active through the end of the query window.
3. **Tier-Specific Seat Spend**:
   - For a seat holding Tool $T$ at Tier $R$:
     $$\text{monthly\_price} = \text{lookup}(T, R) \quad \text{or} \quad \text{lookup}(T)$$
   - Prorated spend for $E$ eligible days:
     $$\text{seat\_spend} = \frac{\text{monthly\_price}}{30} \times E$$
4. **Unpriced Tool Handling**:
   - Tool E has no price specified. Its spend is calculated as `$0.00`, but its seat holders and activity are fully counted toward `licensed_users`, `active_users`, and `engagement_pct`.
5. **Idleness**:
   - A seat is idle if zero counted events occurred for `(person_id, tool)` in the seat's eligible overlap period.
   - Its prorated spend is added to `idle_spend`.
