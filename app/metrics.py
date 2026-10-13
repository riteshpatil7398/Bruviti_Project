"""Core business rules and metrics calculation engine.
"""

from datetime import date, timedelta
from typing import Optional, List, Dict, Set, Tuple, Union, Any
import pandas as pd

from app.schemas import SummaryResponse, ToolMetricsResponse
from app.data_loader import DatasetContainer


REQUIRED_TOOLS_ORDER = ["Tool A", "Tool B", "Tool C", "Tool D", "Tool E"]


class MetricsEngine:
    """Calculates license usage, active users, engagement, spend, and idle spend."""

    def __init__(self, container: DatasetContainer):
        self.container = container
        self._price_map: Dict[Any, float] = self._build_price_map()

    def _build_price_map(self) -> Dict[Any, float]:
        """Map tool names and (tool, tier) combinations to monthly prices from cleaned price_list."""
        df = self.container.price_list_df
        price_map: Dict[Any, float] = {}
        if not df.empty and "tool" in df.columns and "monthly_price" in df.columns:
            for _, row in df.iterrows():
                tool = str(row["tool"]).strip()
                val = row["monthly_price"]
                tier_val = row.get("tier")
                if pd.notna(val):
                    try:
                        price_float = float(val)
                        if pd.notna(tier_val) and tier_val:
                            clean_tier = str(tier_val).strip().lower()
                            price_map[(tool, clean_tier)] = price_float
                        # Default tool fallback price
                        if tool not in price_map:
                            price_map[tool] = price_float
                    except (ValueError, TypeError):
                        pass
        return price_map

    def get_monthly_price(self, tool: str, tier: Optional[str] = None) -> Optional[float]:
        """Look up monthly price for tool and optional tier."""
        if tier:
            clean_tier = str(tier).strip().lower()
            val = self._price_map.get((tool, clean_tier))
            if val is not None:
                return val
        return self._price_map.get(tool)

    @staticmethod
    def calculate_seat_window_intersection(
        granted_on: date,
        revoked_on: Optional[date],
        query_from: date,
        query_to: date
    ) -> Tuple[int, Optional[date], Optional[date]]:
        """Calculate eligible holding days and interval within requested query window.

        Rules:
        - Window is inclusive: [query_from, query_to].
        - Seat holding starts on granted_on (inclusive).
        - Seat holding ends on the day BEFORE revoked_on (revoked_on is first day without seat).
        - If revoked_on is None, seat is held through query_to (open-ended).
        - Returns (eligible_days, overlap_start, overlap_end).
        """
        seat_start = granted_on
        if revoked_on is not None:
            seat_end = revoked_on - timedelta(days=1)
        else:
            seat_end = date.max

        overlap_start = max(seat_start, query_from)
        overlap_end = min(seat_end, query_to)

        if overlap_start <= overlap_end:
            eligible_days = (overlap_end - overlap_start).days + 1
            return eligible_days, overlap_start, overlap_end
        return 0, None, None

    def calculate_metrics(
        self,
        from_date: date,
        to_date: date,
        org: Optional[str] = None
    ) -> Tuple[SummaryResponse, List[ToolMetricsResponse]]:
        """Calculate both summary metrics and tool-level metrics for the query.

        Args:
            from_date: Inclusive start date.
            to_date: Inclusive end date.
            org: Optional organization unit ID.

        Returns:
            Tuple of (SummaryResponse, List[ToolMetricsResponse]).
        """
        # Step 1: Resolve scoped person IDs
        scoped_people = self.container.hierarchy.get_scoped_person_ids(
            org,
            self.container.people_df
        )

        seats_df = self.container.seats_df
        events_df = self.container.activity_events_df

        # Step 2: Identify eligible seats in the window for scoped people
        eligible_seats = []
        if not seats_df.empty:
            for _, row in seats_df.iterrows():
                person_id = str(row["person_id"]).strip()
                if person_id not in scoped_people:
                    continue

                tool = str(row["tool"]).strip()
                tier = row.get("tier")
                granted_on = row["granted_on"]
                revoked_on = row.get("revoked_on")
                if pd.isna(revoked_on):
                    revoked_on = None

                eligible_days, overlap_start, overlap_end = self.calculate_seat_window_intersection(
                    granted_on=granted_on,
                    revoked_on=revoked_on,
                    query_from=from_date,
                    query_to=to_date
                )

                if eligible_days > 0:
                    monthly_price = self.get_monthly_price(tool, tier)
                    if monthly_price is not None:
                        # Monthly price covers 30 days
                        seat_spend = (monthly_price / 30.0) * eligible_days
                    else:
                        seat_spend = 0.0

                    eligible_seats.append({
                        "seat_id": str(row["seat_id"]),
                        "person_id": person_id,
                        "tool": tool,
                        "tier": tier,
                        "eligible_days": eligible_days,
                        "overlap_start": overlap_start,
                        "overlap_end": overlap_end,
                        "spend": seat_spend,
                        "has_activity": False
                    })

        # Step 3: Match valid activity events against eligible seats
        active_users_by_tool: Dict[str, Set[str]] = {t: set() for t in REQUIRED_TOOLS_ORDER}
        all_active_users: Set[str] = set()

        if eligible_seats and not events_df.empty:
            # Pre-filter events to scoped people and query date window
            events_in_scope = events_df[
                events_df["person_id"].isin(scoped_people) &
                (events_df["event_date"] >= from_date) &
                (events_df["event_date"] <= to_date)
            ]

            # Index events by (person_id, tool) -> list of event_date
            events_by_person_tool: Dict[Tuple[str, str], List[date]] = {}
            for _, evt in events_in_scope.iterrows():
                key = (str(evt["person_id"]).strip(), str(evt["tool"]).strip())
                events_by_person_tool.setdefault(key, []).append(evt["event_date"])

            # Check each eligible seat for counted usage
            for seat in eligible_seats:
                key = (seat["person_id"], seat["tool"])
                dates = events_by_person_tool.get(key, [])
                overlap_start = seat["overlap_start"]
                overlap_end = seat["overlap_end"]

                # If any event date falls within this seat's eligible overlap
                for evt_date in dates:
                    if overlap_start <= evt_date <= overlap_end:
                        seat["has_activity"] = True
                        active_users_by_tool.setdefault(seat["tool"], set()).add(seat["person_id"])
                        all_active_users.add(seat["person_id"])
                        break

        # Step 4: Compute per-tool metrics for all 5 required tools in order
        tool_metrics_list: List[ToolMetricsResponse] = []

        # Group eligible seats by tool
        tool_seats_map: Dict[str, List[dict]] = {t: [] for t in REQUIRED_TOOLS_ORDER}
        for seat in eligible_seats:
            tool_seats_map.setdefault(seat["tool"], []).append(seat)

        for tool_name in REQUIRED_TOOLS_ORDER:
            t_seats = tool_seats_map.get(tool_name, [])
            t_licensed_users = len({s["person_id"] for s in t_seats})
            t_active_users = len(active_users_by_tool.get(tool_name, set()))

            t_engagement_pct = (
                round((t_active_users / t_licensed_users) * 100.0, 1)
                if t_licensed_users > 0
                else 0.0
            )

            t_spend_raw = sum(s["spend"] for s in t_seats)
            t_idle_spend_raw = sum(s["spend"] for s in t_seats if not s["has_activity"])

            t_spend = round(t_spend_raw, 2)
            t_idle_spend = round(t_idle_spend_raw, 2)

            t_cost_per_active = (
                round(t_spend_raw / t_active_users, 2)
                if t_active_users > 0
                else None
            )

            tool_metrics_list.append(
                ToolMetricsResponse(
                    tool=tool_name,
                    licensed_users=t_licensed_users,
                    active_users=t_active_users,
                    engagement_pct=t_engagement_pct,
                    spend=t_spend,
                    idle_spend=t_idle_spend,
                    cost_per_active=t_cost_per_active
                )
            )

        # Step 5: Compute overall summary metrics
        summary_licensed_users = len({s["person_id"] for s in eligible_seats})
        summary_active_users = len(all_active_users)

        summary_engagement_pct = (
            round((summary_active_users / summary_licensed_users) * 100.0, 1)
            if summary_licensed_users > 0
            else 0.0
        )

        total_spend_raw = sum(s["spend"] for s in eligible_seats)
        total_idle_spend_raw = sum(s["spend"] for s in eligible_seats if not s["has_activity"])

        summary = SummaryResponse(
            licensed_users=summary_licensed_users,
            active_users=summary_active_users,
            engagement_pct=summary_engagement_pct,
            spend=round(total_spend_raw, 2),
            idle_spend=round(total_idle_spend_raw, 2)
        )

        return summary, tool_metrics_list
