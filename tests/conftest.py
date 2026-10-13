"""Pytest fixtures and configuration for Bruviti Analytics test suite.
"""

import sys
from pathlib import Path
from datetime import date
import pytest
import pandas as pd
from fastapi.testclient import TestClient

# Ensure root bruviti-assignment directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import app, data_loader
from app.data_loader import DataLoader, DatasetContainer
from app.metrics import MetricsEngine


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_dataframes():
    """Returns a dictionary of raw synthetic DataFrames for deterministic testing."""
    org_units_df = pd.DataFrame([
        {"org_id": "CORP", "name": "Corporate Root", "parent_id": None},
        {"org_id": "ENG", "name": "Engineering", "parent_id": "CORP"},
        {"org_id": "DEV", "name": "Development", "parent_id": "ENG"},
        {"org_id": "SALES", "name": "Sales", "parent_id": "CORP"},
    ])

    people_df = pd.DataFrame([
        {"person_id": "P1", "name": "Alice", "org_id": "DEV"},
        {"person_id": "P2", "name": "Bob", "org_id": "DEV"},
        {"person_id": "P3", "name": "Charlie", "org_id": "ENG"},
        {"person_id": "P4", "name": "Diana", "org_id": "SALES"},
    ])

    price_list_df = pd.DataFrame([
        {"tool": "Tool A", "monthly_price": 60.0},   # $2/day
        {"tool": "Tool B", "monthly_price": 150.0},  # $5/day
        {"tool": "Tool C", "monthly_price": 90.0},   # $3/day
        {"tool": "Tool D", "monthly_price": 300.0},  # $10/day
        {"tool": "Tool E", "monthly_price": 120.0},  # $4/day
    ])

    seats_df = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool B", "granted_on": "2024-01-01", "revoked_on": "2024-01-16"},
    ])

    activity_events_df = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"},
    ])

    return {
        "org_units": org_units_df,
        "people": people_df,
        "price_list": price_list_df,
        "seats": seats_df,
        "activity_events": activity_events_df,
    }


@pytest.fixture
def create_engine(sample_dataframes):
    """Factory fixture to create a MetricsEngine with custom dataframes."""
    def _builder(
        org_units=None,
        people=None,
        price_list=None,
        seats=None,
        activity_events=None
    ) -> MetricsEngine:
        loader = DataLoader()
        container = loader.load_from_dataframes(
            raw_org_units=org_units if org_units is not None else sample_dataframes["org_units"],
            raw_people=people if people is not None else sample_dataframes["people"],
            raw_price_list=price_list if price_list is not None else sample_dataframes["price_list"],
            raw_seats=seats if seats is not None else sample_dataframes["seats"],
            raw_activity_events=activity_events if activity_events is not None else sample_dataframes["activity_events"]
        )
        return MetricsEngine(container)

    return _builder
