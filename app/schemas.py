"""Pydantic schemas and models for Bruviti Software License Usage & Cost Analytics.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="ok", description="Service readiness status")


class SummaryResponse(BaseModel):
    """Aggregate license usage and cost summary schema."""
    licensed_users: int = Field(..., description="Distinct people holding at least one eligible seat in window")
    active_users: int = Field(..., description="Distinct people with valid counted usage in window")
    engagement_pct: float = Field(..., description="Percentage of licensed users that are active (rounded to 1 decimal)")
    spend: float = Field(..., description="Total prorated spend for eligible seats in window (rounded to 2 decimals)")
    idle_spend: float = Field(..., description="Spend for seats with zero usage in window (rounded to 2 decimals)")


class ToolMetricsResponse(BaseModel):
    """Tool-level license usage and cost metrics schema."""
    tool: str = Field(..., description="Name of the tool (Tool A, Tool B, Tool C, Tool D, Tool E)")
    licensed_users: int = Field(..., description="Distinct people holding an eligible seat for this tool")
    active_users: int = Field(..., description="Distinct people with valid counted usage for this tool")
    engagement_pct: float = Field(..., description="Tool engagement percentage (rounded to 1 decimal)")
    spend: float = Field(..., description="Total prorated spend for this tool (rounded to 2 decimals)")
    idle_spend: float = Field(..., description="Prorated spend for idle seats of this tool (rounded to 2 decimals)")
    cost_per_active: Optional[float] = Field(
        None,
        description="Prorated spend divided by active users, or null if active_users is 0"
    )


class QueryParams(BaseModel):
    """Validated query parameters for analytics endpoints."""
    from_date: date = Field(..., alias="from", description="Inclusive start date (YYYY-MM-DD)")
    to_date: date = Field(..., alias="to", description="Inclusive end date (YYYY-MM-DD)")
    org: Optional[str] = Field(None, description="Optional organization unit ID filter")

    @field_validator("org", mode="before")
    @classmethod
    def clean_org(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        return v_str if v_str else None


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    detail: str = Field(..., description="Descriptive error explanation")
