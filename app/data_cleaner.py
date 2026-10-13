"""Reusable, rule-based data cleaning and validation module.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Set, Tuple
import pandas as pd


def canonicalize_tool_name(tool_val: Optional[str]) -> str:
    """Canonicalize tool names to 'Tool A' ... 'Tool E' format.

    Handles single letters ('A' -> 'Tool A') as well as full names ('Tool A' -> 'Tool A').
    """
    if tool_val is None:
        return ""
    s = str(tool_val).strip()
    if not s:
        return ""
    upper_s = s.upper()
    if upper_s in {"A", "B", "C", "D", "E"}:
        return f"Tool {upper_s}"
    if s.lower().startswith("tool "):
        sub = s[5:].strip().upper()
        if sub in {"A", "B", "C", "D", "E"}:
            return f"Tool {sub}"
    return s


@dataclass
class ValidationIssue:
    """Represents a data quality finding or anomaly."""
    dataset: str
    severity: str  # "ERROR" (record dropped/rejected) or "WARNING" (record normalized)
    rule: str
    description: str
    record_identifier: Optional[str] = None


class DataCleaner:
    """Applies rule-based validation and normalization without mutating raw sources."""

    def __init__(self):
        self.issues: List[ValidationIssue] = []

    def log_issue(
        self,
        dataset: str,
        severity: str,
        rule: str,
        description: str,
        record_identifier: Optional[str] = None
    ) -> None:
        """Record a validation anomaly in the audit log."""
        self.issues.append(
            ValidationIssue(
                dataset=dataset,
                severity=severity,
                rule=rule,
                description=description,
                record_identifier=record_identifier
            )
        )

    def clean_org_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rule-based cleaning for organization units.

        Supports aliases: org_unit_id / org_id / id; parent_id / parent_org_id.
        """
        if df.empty:
            return pd.DataFrame(columns=["org_id", "name", "parent_id"])

        cleaned = df.copy()
        cleaned.columns = [c.strip().lower() for c in cleaned.columns]

        id_col = None
        for col_cand in ["org_id", "org_unit_id", "id"]:
            if col_cand in cleaned.columns:
                id_col = col_cand
                break

        if not id_col:
            self.log_issue("org_units", "ERROR", "RULE-ORG-SCHEMA", "Missing org_id / org_unit_id column")
            return pd.DataFrame(columns=["org_id", "name", "parent_id"])

        cleaned = cleaned.rename(columns={id_col: "org_id"})
        if "name" not in cleaned.columns:
            cleaned["name"] = cleaned["org_id"]
        if "parent_id" not in cleaned.columns:
            parent_col = "parent_org_id" if "parent_org_id" in cleaned.columns else None
            cleaned["parent_id"] = cleaned[parent_col] if parent_col else None

        # RULE-ORG-1: Strip whitespace
        for col in ["org_id", "name", "parent_id"]:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": None, "None": None, "": None})

        # RULE-ORG-2: Drop missing org_id
        valid_mask = cleaned["org_id"].notna() & (cleaned["org_id"] != "")
        dropped_count = (~valid_mask).sum()
        if dropped_count > 0:
            self.log_issue("org_units", "ERROR", "RULE-ORG-2", f"Dropped {dropped_count} rows with missing org_id")
        cleaned = cleaned[valid_mask].copy()

        # RULE-ORG-3: Deduplicate by business key org_id
        dup_mask = cleaned.duplicated(subset=["org_id"], keep="first")
        if dup_mask.any():
            dup_keys = cleaned.loc[dup_mask, "org_id"].tolist()
            self.log_issue("org_units", "WARNING", "RULE-ORG-3", f"Deduplicated {len(dup_keys)} org_ids: {dup_keys}")
            cleaned = cleaned[~dup_mask].copy()

        # RULE-ORG-4: Self-referencing check
        self_ref = cleaned["org_id"] == cleaned["parent_id"]
        if self_ref.any():
            self_ref_ids = cleaned.loc[self_ref, "org_id"].tolist()
            self.log_issue("org_units", "WARNING", "RULE-ORG-4", f"Broken self-referencing parents on orgs: {self_ref_ids}")
            cleaned.loc[self_ref, "parent_id"] = None

        return cleaned[["org_id", "name", "parent_id"]].reset_index(drop=True)

    def clean_people(self, df: pd.DataFrame, valid_org_ids: Optional[Set[str]] = None) -> pd.DataFrame:
        """Rule-based cleaning for people / users.

        Supports aliases: person_id / user_id / id; org_id / org_unit_id.
        """
        if df.empty:
            return pd.DataFrame(columns=["person_id", "name", "org_id"])

        cleaned = df.copy()
        cleaned.columns = [c.strip().lower() for c in cleaned.columns]

        id_col = None
        for col_cand in ["person_id", "user_id", "id"]:
            if col_cand in cleaned.columns:
                id_col = col_cand
                break

        org_col = None
        for col_cand in ["org_id", "org_unit_id"]:
            if col_cand in cleaned.columns:
                org_col = col_cand
                break

        if not id_col:
            self.log_issue("people", "ERROR", "RULE-PPL-SCHEMA", "Missing person_id / user_id column")
            return pd.DataFrame(columns=["person_id", "name", "org_id"])

        cleaned = cleaned.rename(columns={id_col: "person_id"})
        if org_col and org_col != "org_id":
            cleaned = cleaned.rename(columns={org_col: "org_id"})
        elif "org_id" not in cleaned.columns:
            cleaned["org_id"] = None

        if "name" not in cleaned.columns:
            cleaned["name"] = cleaned["person_id"]

        # RULE-PPL-1: Strip whitespace
        for col in ["person_id", "name", "org_id"]:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": None, "None": None, "": None})

        # RULE-PPL-2: Required person_id
        valid_mask = cleaned["person_id"].notna() & (cleaned["person_id"] != "")
        dropped_count = (~valid_mask).sum()
        if dropped_count > 0:
            self.log_issue("people", "ERROR", "RULE-PPL-2", f"Dropped {dropped_count} rows with missing person_id")
        cleaned = cleaned[valid_mask].copy()

        # RULE-PPL-3: Deduplicate by person_id
        dup_mask = cleaned.duplicated(subset=["person_id"], keep="first")
        if dup_mask.any():
            dup_keys = cleaned.loc[dup_mask, "person_id"].tolist()
            self.log_issue("people", "WARNING", "RULE-PPL-3", f"Deduplicated {len(dup_keys)} duplicate person_ids: {dup_keys}")
            cleaned = cleaned[~dup_mask].copy()

        # RULE-PPL-4: Referential check
        if valid_org_ids is not None:
            invalid_orgs = cleaned[cleaned["org_id"].notna() & ~cleaned["org_id"].isin(valid_org_ids)]
            if not invalid_orgs.empty:
                bad_ids = invalid_orgs["person_id"].tolist()
                self.log_issue("people", "WARNING", "RULE-PPL-4", f"People referencing unknown orgs: {bad_ids}")

        return cleaned[["person_id", "name", "org_id"]].reset_index(drop=True)

    def clean_price_list(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rule-based cleaning for price list.

        Supports aliases: tool / tool_name; monthly_price / monthly_price_usd / price.
        Supports optional tier column for tier-based tool pricing.
        """
        if df.empty:
            return pd.DataFrame(columns=["tool", "tier", "monthly_price"])

        cleaned = df.copy()
        cleaned.columns = [c.strip().lower() for c in cleaned.columns]

        tool_col = "tool" if "tool" in cleaned.columns else ("tool_name" if "tool_name" in cleaned.columns else None)
        price_col = None
        for col_cand in ["monthly_price", "monthly_price_usd", "price"]:
            if col_cand in cleaned.columns:
                price_col = col_cand
                break

        if not tool_col or not price_col:
            self.log_issue("price_list", "ERROR", "RULE-PRC-SCHEMA", "Missing tool or monthly_price column")
            return pd.DataFrame(columns=["tool", "tier", "monthly_price"])

        cleaned = cleaned.rename(columns={tool_col: "tool", price_col: "monthly_price"})
        cleaned["tool"] = cleaned["tool"].apply(canonicalize_tool_name)

        # Handle optional tier column
        has_tier = "tier" in cleaned.columns
        if has_tier:
            cleaned["tier"] = cleaned["tier"].astype(str).str.strip().str.lower().replace({"nan": None, "none": None, "": None})
        else:
            cleaned["tier"] = None

        # Drop missing tool
        valid_tool = cleaned["tool"].notna() & (cleaned["tool"] != "")
        if (~valid_tool).any():
            self.log_issue("price_list", "ERROR", "RULE-PRC-2", f"Dropped {(~valid_tool).sum()} rows with empty tool name")
        cleaned = cleaned[valid_tool].copy()

        # Deduplicate by (tool, tier) if tier exists, else by tool
        dedup_subset = ["tool", "tier"] if has_tier else ["tool"]
        dup_mask = cleaned.duplicated(subset=dedup_subset, keep="first")
        if dup_mask.any():
            self.log_issue("price_list", "WARNING", "RULE-PRC-3", f"Deduplicated duplicate tool prices: {cleaned.loc[dup_mask, 'tool'].tolist()}")
            cleaned = cleaned[~dup_mask].copy()

        # Validate monthly_price (empty/null is allowed for unpriced tools like Tool E standard, but non-numeric strings are rejected)
        raw_price_str = cleaned["monthly_price"].astype(str).str.strip().str.lower()
        is_corrupted = cleaned["monthly_price"].notna() & ~raw_price_str.isin(["", "nan", "none"])
        
        parsed_price = pd.to_numeric(cleaned["monthly_price"], errors="coerce")
        bad_format = is_corrupted & parsed_price.isna()
        if bad_format.any():
            bad_tools = cleaned.loc[bad_format, "tool"].tolist()
            self.log_issue("price_list", "ERROR", "RULE-PRC-4", f"Rejected non-numeric prices for tools: {bad_tools}")
            cleaned = cleaned[~bad_format].copy()
            parsed_price = parsed_price[~bad_format]

        cleaned["monthly_price"] = parsed_price
        negative_price = cleaned["monthly_price"].notna() & (cleaned["monthly_price"] < 0)
        if negative_price.any():
            bad_tools = cleaned.loc[negative_price, "tool"].tolist()
            self.log_issue("price_list", "ERROR", "RULE-PRC-4", f"Rejected negative prices for tools: {bad_tools}")
            cleaned = cleaned[~negative_price].copy()

        return cleaned[["tool", "tier", "monthly_price"]].reset_index(drop=True)

    def clean_seats(self, df: pd.DataFrame, valid_person_ids: Optional[Set[str]] = None) -> pd.DataFrame:
        """Rule-based cleaning for seats.

        Supports aliases: person_id / user_id / id.
        Supports optional tier column.
        """
        if df.empty:
            return pd.DataFrame(columns=["seat_id", "person_id", "tool", "tier", "granted_on", "revoked_on"])

        cleaned = df.copy()
        cleaned.columns = [c.strip().lower() for c in cleaned.columns]

        id_col = "seat_id" if "seat_id" in cleaned.columns else ("id" if "id" in cleaned.columns else None)
        if id_col:
            cleaned = cleaned.rename(columns={id_col: "seat_id"})
        else:
            cleaned["seat_id"] = [f"SEAT_{i+1:05d}" for i in range(len(cleaned))]

        user_col = "person_id" if "person_id" in cleaned.columns else ("user_id" if "user_id" in cleaned.columns else None)
        if user_col and user_col != "person_id":
            cleaned = cleaned.rename(columns={user_col: "person_id"})

        has_tier = "tier" in cleaned.columns
        if has_tier:
            cleaned["tier"] = cleaned["tier"].astype(str).str.strip().str.lower().replace({"nan": None, "none": None, "": None})
        else:
            cleaned["tier"] = None

        # Strip whitespace and canonicalize tool
        for col in ["seat_id", "person_id", "granted_on", "revoked_on"]:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": None, "None": None, "": None})
            else:
                cleaned[col] = None

        if "tool" in cleaned.columns:
            cleaned["tool"] = cleaned["tool"].apply(canonicalize_tool_name)
        else:
            cleaned["tool"] = None

        # RULE-SEAT-2: Required fields
        req_mask = (
            cleaned["person_id"].notna() & (cleaned["person_id"] != "") &
            cleaned["tool"].notna() & (cleaned["tool"] != "") &
            cleaned["granted_on"].notna() & (cleaned["granted_on"] != "")
        )
        if (~req_mask).any():
            self.log_issue("seats", "ERROR", "RULE-SEAT-2", f"Dropped {(~req_mask).sum()} seat records missing required fields")
        cleaned = cleaned[req_mask].copy()

        # RULE-SEAT-3 & 4: Date parsing
        cleaned["granted_on_parsed"] = pd.to_datetime(cleaned["granted_on"], format="%Y-%m-%d", errors="coerce").dt.date
        cleaned["revoked_on_parsed"] = pd.to_datetime(cleaned["revoked_on"], format="%Y-%m-%d", errors="coerce").dt.date

        # Drop invalid granted_on
        bad_granted = cleaned["granted_on_parsed"].isna()
        if bad_granted.any():
            self.log_issue("seats", "ERROR", "RULE-SEAT-3", f"Dropped {bad_granted.sum()} seats with invalid granted_on dates")
            cleaned = cleaned[~bad_granted].copy()

        # Check revoked_on < granted_on
        has_revoked = cleaned["revoked_on_parsed"].notna()
        invalid_revoked_order = has_revoked & (cleaned["revoked_on_parsed"] < cleaned["granted_on_parsed"])
        if invalid_revoked_order.any():
            bad_seats = cleaned.loc[invalid_revoked_order, "seat_id"].tolist()
            self.log_issue("seats", "ERROR", "RULE-SEAT-5", f"Dropped seats where revoked_on < granted_on: {bad_seats}")
            cleaned = cleaned[~invalid_revoked_order].copy()

        # Update clean date columns
        cleaned["granted_on"] = cleaned["granted_on_parsed"]
        cleaned["revoked_on"] = cleaned["revoked_on_parsed"]

        # RULE-SEAT-6: Deduplicate by (person_id, tool, granted_on) or with tier
        dedup_subset = ["person_id", "tool", "tier", "granted_on"] if has_tier else ["person_id", "tool", "granted_on"]
        dup_mask = cleaned.duplicated(subset=dedup_subset, keep="first")
        if dup_mask.any():
            self.log_issue("seats", "WARNING", "RULE-SEAT-6", f"Deduplicated {dup_mask.sum()} duplicate seat grants")
            cleaned = cleaned[~dup_mask].copy()

        # RULE-SEAT-7: Referential check
        if valid_person_ids is not None:
            unknown_ppl = ~cleaned["person_id"].isin(valid_person_ids)
            if unknown_ppl.any():
                self.log_issue("seats", "WARNING", "RULE-SEAT-7", f"Seats assigned to unknown person_ids: {cleaned.loc[unknown_ppl, 'person_id'].tolist()}")

        return cleaned[["seat_id", "person_id", "tool", "tier", "granted_on", "revoked_on"]].reset_index(drop=True)

    def clean_activity_events(self, df: pd.DataFrame, valid_person_ids: Optional[Set[str]] = None) -> pd.DataFrame:
        """Rule-based cleaning for activity events.

        Supports aliases: person_id / user_id / id.
        """
        if df.empty:
            return pd.DataFrame(columns=["event_id", "person_id", "tool", "event_date", "activity_type"])

        cleaned = df.copy()
        cleaned.columns = [c.strip().lower() for c in cleaned.columns]

        id_col = "event_id" if "event_id" in cleaned.columns else ("id" if "id" in cleaned.columns else None)
        if id_col:
            cleaned = cleaned.rename(columns={id_col: "event_id"})
        else:
            cleaned["event_id"] = [f"EVT_{i+1:05d}" for i in range(len(cleaned))]

        user_col = "person_id" if "person_id" in cleaned.columns else ("user_id" if "user_id" in cleaned.columns else None)
        if user_col and user_col != "person_id":
            cleaned = cleaned.rename(columns={user_col: "person_id"})

        date_col = "timestamp" if "timestamp" in cleaned.columns else (
            "date" if "date" in cleaned.columns else (
                "event_date" if "event_date" in cleaned.columns else None
            )
        )

        for col in ["event_id", "person_id", "activity_type"]:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": None, "None": None, "": None})
            else:
                cleaned[col] = None

        if "tool" in cleaned.columns:
            cleaned["tool"] = cleaned["tool"].apply(canonicalize_tool_name)
        else:
            cleaned["tool"] = None

        if not date_col:
            self.log_issue("activity_events", "ERROR", "RULE-EVT-SCHEMA", "Missing timestamp/date column")
            return pd.DataFrame(columns=["event_id", "person_id", "tool", "event_date", "activity_type"])

        # RULE-EVT-2: Required fields
        req_mask = (
            cleaned["person_id"].notna() & (cleaned["person_id"] != "") &
            cleaned["tool"].notna() & (cleaned["tool"] != "") &
            cleaned[date_col].notna() & (cleaned[date_col] != "")
        )
        if (~req_mask).any():
            self.log_issue("activity_events", "ERROR", "RULE-EVT-2", f"Dropped {(~req_mask).sum()} events missing required fields")
        cleaned = cleaned[req_mask].copy()

        # RULE-EVT-3: Parse date
        parsed_dates = pd.to_datetime(cleaned[date_col], errors="coerce", format="mixed").dt.date
        bad_dates = parsed_dates.isna()
        if bad_dates.any():
            self.log_issue("activity_events", "ERROR", "RULE-EVT-3", f"Dropped {bad_dates.sum()} events with unparseable date/timestamp")
            cleaned = cleaned[~bad_dates].copy()
            parsed_dates = parsed_dates[~bad_dates]

        cleaned["event_date"] = parsed_dates

        # RULE-EVT-4: Deduplicate by event_id
        dup_mask = cleaned.duplicated(subset=["event_id"], keep="first")
        if dup_mask.any():
            self.log_issue("activity_events", "WARNING", "RULE-EVT-4", f"Deduplicated {dup_mask.sum()} duplicate event IDs")
            cleaned = cleaned[~dup_mask].copy()

        # RULE-EVT-5: Referential check
        if valid_person_ids is not None:
            unknown_ppl = ~cleaned["person_id"].isin(valid_person_ids)
            if unknown_ppl.any():
                self.log_issue("activity_events", "WARNING", "RULE-EVT-5", f"Events from unknown person_ids: {cleaned.loc[unknown_ppl, 'person_id'].tolist()}")

        return cleaned[["event_id", "person_id", "tool", "event_date", "activity_type"]].reset_index(drop=True)
