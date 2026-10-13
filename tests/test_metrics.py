"""Unit tests for license metrics, date window intersections, spend calculations, and activity counting.
"""

from datetime import date
import pandas as pd
import pytest

from app.metrics import MetricsEngine


def test_05_seat_granted_exactly_on_first_requested_day(create_engine):
    """Test 5: Seat granted on 2024-01-01, window 2024-01-01 to 2024-01-10 is exactly 10 days."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": None
    }])
    # Monthly price 60.0 -> $2/day * 10 days = $20.00
    engine = create_engine(seats=seats)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 10))

    assert summary.licensed_users == 1
    assert summary.spend == 20.00


def test_06_seat_revoked_on_first_or_last_requested_day(create_engine):
    """Test 6:
    - Revoked on first day (2024-01-01): 0 eligible days because 2024-01-01 is first day without seat.
    - Revoked on last day (2024-01-10): held Jan 1 through Jan 9 = 9 eligible days.
    """
    # Case A: Revoked on first day
    seats_first_day = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2023-12-01", "revoked_on": "2024-01-01"
    }])
    engine_a = create_engine(seats=seats_first_day)
    summary_a, _ = engine_a.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 10))
    assert summary_a.licensed_users == 0
    assert summary_a.spend == 0.00

    # Case B: Revoked on last day of window (2024-01-10)
    # Seat held 2024-01-01 to 2024-01-09 (9 days)
    # Tool A is $2/day -> $18.00
    seats_last_day = pd.DataFrame([{
        "seat_id": "S2", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": "2024-01-10"
    }])
    engine_b = create_engine(seats=seats_last_day)
    summary_b, _ = engine_b.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 10))
    assert summary_b.licensed_users == 1
    assert summary_b.spend == 18.00


def test_07_seat_granted_before_and_revoked_after_window(create_engine):
    """Test 7: Granted 2023-12-15 and revoked 2024-02-15 spans entire window Jan 1-31 (31 days)."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2023-12-15", "revoked_on": "2024-02-15"
    }])
    # Tool A: 60/30 = $2.00/day * 31 = $62.00
    engine = create_engine(seats=seats)
    summary, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))
    assert summary.licensed_users == 1
    assert summary.spend == 62.00


def test_08_open_ended_seats_no_revocation_date(create_engine):
    """Test 8: Open-ended seat continues through query window end."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": None
    }])
    # Jan 1 to Jan 15 = 15 days * $2.00 = $30.00
    engine = create_engine(seats=seats)
    summary, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 15))
    assert summary.licensed_users == 1
    assert summary.spend == 30.00


def test_09_seat_holding_outside_requested_window(create_engine):
    """Test 9: Seats granted after window or revoked before window have 0 eligible days."""
    seats = pd.DataFrame([
        # Granted after window
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-02-01", "revoked_on": None},
        # Revoked before window (revoked 2023-12-31, so seat ended 2023-12-30)
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool B", "granted_on": "2023-11-01", "revoked_on": "2023-12-31"}
    ])
    engine = create_engine(seats=seats)
    summary, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))
    assert summary.licensed_users == 0
    assert summary.spend == 0.00


def test_10_usage_before_seat_grant(create_engine):
    """Test 10: Activity before seat granted_on date is uncounted."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-10", "revoked_on": None
    }])
    events = pd.DataFrame([{
        "event_id": "E1", "person_id": "P1", "tool": "Tool A",
        "timestamp": "2024-01-05 10:00:00", "activity_type": "query"
    }])
    engine = create_engine(seats=seats, activity_events=events)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 1
    assert summary.active_users == 0  # Activity was before seat grant!
    assert summary.idle_spend == summary.spend


def test_11_usage_on_revocation_date(create_engine):
    """Test 11: Activity on revocation date itself is uncounted (revoked_on is first day without seat)."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": "2024-01-10"
    }])
    events = pd.DataFrame([{
        "event_id": "E1", "person_id": "P1", "tool": "Tool A",
        "timestamp": "2024-01-10 09:00:00", "activity_type": "login"
    }])
    engine = create_engine(seats=seats, activity_events=events)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 1
    assert summary.active_users == 0  # Event on Jan 10 cannot count!
    assert summary.idle_spend == summary.spend


def test_12_usage_outside_query_date_window(create_engine):
    """Test 12: Activity outside requested query date window does not make user active in window."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": None
    }])
    # Event happened Jan 5, but query window is Jan 10 to Jan 20
    events = pd.DataFrame([{
        "event_id": "E1", "person_id": "P1", "tool": "Tool A",
        "timestamp": "2024-01-05 12:00:00", "activity_type": "login"
    }])
    engine = create_engine(seats=seats, activity_events=events)
    summary, _ = engine.calculate_metrics(from_date=date(2024, 1, 10), to_date=date(2024, 1, 20))

    assert summary.licensed_users == 1
    assert summary.active_users == 0
    assert summary.engagement_pct == 0.0


def test_13_usage_for_wrong_tool(create_engine):
    """Test 13: Usage of Tool B does not validate activity for Tool A license."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": None
    }])
    events = pd.DataFrame([{
        "event_id": "E1", "person_id": "P1", "tool": "Tool B",  # Wrong tool!
        "timestamp": "2024-01-05 10:00:00", "activity_type": "login"
    }])
    engine = create_engine(seats=seats, activity_events=events)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 1
    assert summary.active_users == 0

    tool_a = next(t for t in tools if t.tool == "Tool A")
    assert tool_a.licensed_users == 1
    assert tool_a.active_users == 0


def test_18_missing_tool_prices(create_engine):
    """Test 18: Unpriced tools excluded from spend without excluding seats or users from licensing."""
    price_list = pd.DataFrame([
        {"tool": "Tool A", "monthly_price": 60.0},
        # Tool B is NOT in price_list!
    ])
    seats = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool B", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P2", "tool": "Tool B", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"}
    ])
    engine = create_engine(price_list=price_list, seats=seats, activity_events=events)
    # Window Jan 1-30 (30 days)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 30))

    # Both users licensed
    assert summary.licensed_users == 2
    assert summary.active_users == 1
    assert summary.engagement_pct == 50.0

    # Tool A spend: 60/30 * 30 = 60.00
    # Tool B spend: 0.00 (unpriced)
    assert summary.spend == 60.00

    tool_b = next(t for t in tools if t.tool == "Tool B")
    assert tool_b.licensed_users == 1
    assert tool_b.active_users == 1
    assert tool_b.spend == 0.00
    assert tool_b.cost_per_active == 0.00


def test_19_idle_seats_and_idle_spend(create_engine):
    """Test 19: Spend of seats with zero counted activity is correctly isolated to idle spend."""
    seats = pd.DataFrame([
        # P1 has Tool A ($2/day) - Active
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        # P2 has Tool B ($5/day) - Idle
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool B", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"}
    ])
    engine = create_engine(seats=seats, activity_events=events)
    # Window Jan 1 to Jan 10 (10 days)
    # Tool A spend = $2 * 10 = $20.00 (Active)
    # Tool B spend = $5 * 10 = $50.00 (Idle)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 10))

    assert summary.spend == 70.00
    assert summary.idle_spend == 50.00

    tool_b = next(t for t in tools if t.tool == "Tool B")
    assert tool_b.spend == 50.00
    assert tool_b.idle_spend == 50.00
    assert tool_b.cost_per_active is None


def test_20_multiple_seats_held_by_one_person(create_engine):
    """Test 20: Person holding multiple tool seats is counted once in summary, once per tool."""
    seats = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P1", "tool": "Tool B", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"}
    ])
    engine = create_engine(seats=seats, activity_events=events)
    # Jan 1 to Jan 30 (30 days)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 30))

    assert summary.licensed_users == 1  # Distinct person
    assert summary.active_users == 1
    assert summary.engagement_pct == 100.0

    tool_a = next(t for t in tools if t.tool == "Tool A")
    tool_b = next(t for t in tools if t.tool == "Tool B")

    assert tool_a.licensed_users == 1
    assert tool_a.active_users == 1
    assert tool_a.idle_spend == 0.00

    assert tool_b.licensed_users == 1
    assert tool_b.active_users == 0
    assert tool_b.idle_spend == 150.00  # P1's Tool B seat was idle!


def test_21_zero_licensed_users(create_engine):
    """Test 21: Zero licensed users in window returns 0.0 engagement and spend."""
    seats = pd.DataFrame(columns=["seat_id", "person_id", "tool", "granted_on", "revoked_on"])
    engine = create_engine(seats=seats)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 0
    assert summary.active_users == 0
    assert summary.engagement_pct == 0.0
    assert summary.spend == 0.0
    assert summary.idle_spend == 0.0

    for t in tools:
        assert t.licensed_users == 0
        assert t.cost_per_active is None


def test_22_zero_active_users(create_engine):
    """Test 22: Licensed users exist but active users is zero."""
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool A",
        "granted_on": "2024-01-01", "revoked_on": None
    }])
    events = pd.DataFrame(columns=["event_id", "person_id", "tool", "timestamp", "activity_type"])
    engine = create_engine(seats=seats, activity_events=events)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 1
    assert summary.active_users == 0
    assert summary.engagement_pct == 0.0

    tool_a = next(t for t in tools if t.tool == "Tool A")
    assert tool_a.cost_per_active is None


def test_23_engagement_percentage_rounding(create_engine):
    """Test 23: Engagement percentage is rounded to exactly one decimal place."""
    # 1 active out of 3 licensed = 33.333% -> 33.3%
    seats = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S3", "person_id": "P3", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"}
    ])
    engine = create_engine(seats=seats, activity_events=events)
    summary, tools = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    assert summary.licensed_users == 3
    assert summary.active_users == 1
    assert summary.engagement_pct == 33.3

    tool_a = next(t for t in tools if t.tool == "Tool A")
    assert tool_a.engagement_pct == 33.3


def test_24_prorated_daily_spend(create_engine):
    """Test 24: Monthly price / 30 * eligible_days."""
    # Tool B has monthly price 150.00 -> $5.00/day
    seats = pd.DataFrame([{
        "seat_id": "S1", "person_id": "P1", "tool": "Tool B",
        "granted_on": "2024-01-01", "revoked_on": "2024-01-16"  # 15 days
    }])
    engine = create_engine(seats=seats)
    summary, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))

    # 15 days * $5.00 = 75.00
    assert summary.spend == 75.00
