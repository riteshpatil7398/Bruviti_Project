"""Tests for data cleaning, anomaly detection, deduplication, and invalid record handling.
"""

from datetime import date
import pandas as pd
import pytest

from app.data_cleaner import DataCleaner


def test_17_duplicate_people_and_events():
    """Test 17: Duplicate records are cleaned deterministically based on business keys."""
    cleaner = DataCleaner()

    # Duplicate people
    raw_people = pd.DataFrame([
        {"person_id": "P1", "name": "Alice Johnson", "org_id": "ORG_DEV"},
        {"person_id": "P1", "name": "Alice Duplicate", "org_id": "ORG_DEV"},  # Duplicate
        {"person_id": "P2", "name": "Bob Smith", "org_id": "ORG_DEV"},
    ])
    clean_people = cleaner.clean_people(raw_people)
    assert len(clean_people) == 2
    assert clean_people.iloc[0]["name"] == "Alice Johnson"
    assert any(i.rule == "RULE-PPL-3" for i in cleaner.issues)

    # Duplicate events
    raw_events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"},
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"},  # Duplicate
        {"event_id": "E2", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-06 11:00:00", "activity_type": "query"},
    ])
    clean_events = cleaner.clean_activity_events(raw_events)
    assert len(clean_events) == 2
    assert any(i.rule == "RULE-EVT-4" for i in cleaner.issues)


def test_27_invalid_or_inconsistent_csv_data():
    """Test 27: Cleaning drops malformed rows and normalizes whitespace."""
    cleaner = DataCleaner()

    # 1. Negative and invalid prices
    raw_prices = pd.DataFrame([
        {"tool": "Tool A", "monthly_price": 60.0},
        {"tool": "Tool B", "monthly_price": -50.0},  # Negative
        {"tool": "Tool C", "monthly_price": "invalid"},  # Non-numeric
    ])
    clean_prices = cleaner.clean_price_list(raw_prices)
    assert len(clean_prices) == 1
    assert clean_prices.iloc[0]["tool"] == "Tool A"
    assert any(i.rule == "RULE-PRC-4" for i in cleaner.issues)

    # 2. Inconsistent seat date ranges (revoked_on < granted_on) and whitespace
    raw_seats = pd.DataFrame([
        # Valid with whitespace
        {"seat_id": " S1 ", "person_id": " P1 ", "tool": " Tool A ", "granted_on": " 2024-01-01 ", "revoked_on": None},
        # Invalid revoked_on < granted_on
        {"seat_id": "S2", "person_id": "P1", "tool": "Tool B", "granted_on": "2024-01-15", "revoked_on": "2024-01-10"},
        # Malformed date string
        {"seat_id": "S3", "person_id": "P2", "tool": "Tool C", "granted_on": "invalid-date", "revoked_on": None},
        # Missing required person_id
        {"seat_id": "S4", "person_id": "", "tool": "Tool D", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    clean_seats = cleaner.clean_seats(raw_seats)
    assert len(clean_seats) == 1
    assert clean_seats.iloc[0]["seat_id"] == "S1"
    assert clean_seats.iloc[0]["person_id"] == "P1"
    assert clean_seats.iloc[0]["tool"] == "Tool A"
    assert clean_seats.iloc[0]["granted_on"] == date(2024, 1, 1)

    # 3. Activity events with invalid timestamp
    raw_events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "not-a-timestamp", "activity_type": "login"},
        {"event_id": "E2", "person_id": "", "tool": "Tool A", "timestamp": "2024-01-05", "activity_type": "login"},
        {"event_id": "E3", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 14:00:00", "activity_type": "login"},
    ])
    clean_events = cleaner.clean_activity_events(raw_events)
    assert len(clean_events) == 1
    assert clean_events.iloc[0]["event_id"] == "E3"
    assert clean_events.iloc[0]["event_date"] == date(2024, 1, 5)
