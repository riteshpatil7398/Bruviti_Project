"""Tests for organization hierarchy traversal, cycles, scoping, and tree resolution.
"""

from datetime import date
import pandas as pd
import pytest

from app.organization import OrganizationHierarchy, UnknownOrganizationError


def test_14_usage_by_person_outside_selected_org_subtree(create_engine):
    """Test 14: People outside the requested organization subtree are excluded."""
    # DEV is child of ENG, SALES is sibling of ENG
    # P1 is in DEV, P4 is in SALES
    seats = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P4", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    events = pd.DataFrame([
        {"event_id": "E1", "person_id": "P1", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"},
        {"event_id": "E2", "person_id": "P4", "tool": "Tool A", "timestamp": "2024-01-05 10:00:00", "activity_type": "login"},
    ])
    engine = create_engine(seats=seats, activity_events=events)

    # Scoped only to DEV: only P1 is included
    summary_dev, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31), org="DEV")
    assert summary_dev.licensed_users == 1
    assert summary_dev.active_users == 1

    # Scoped to SALES: only P4 is included
    summary_sales, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31), org="SALES")
    assert summary_sales.licensed_users == 1
    assert summary_sales.active_users == 1


def test_15_parent_organization_queries_include_all_descendants(create_engine):
    """Test 15: Querying parent org (ENG) includes children (DEV)."""
    # P1 and P2 in DEV, P3 in ENG, P4 in SALES
    seats = pd.DataFrame([
        {"seat_id": "S1", "person_id": "P1", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S2", "person_id": "P2", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S3", "person_id": "P3", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
        {"seat_id": "S4", "person_id": "P4", "tool": "Tool A", "granted_on": "2024-01-01", "revoked_on": None},
    ])
    engine = create_engine(seats=seats)

    # ENG includes DEV (P1, P2) and ENG (P3) = 3 people
    summary_eng, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31), org="ENG")
    assert summary_eng.licensed_users == 3

    # Root CORP includes all (P1, P2, P3, P4) = 4 people
    summary_corp, _ = engine.calculate_metrics(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31), org="CORP")
    assert summary_corp.licensed_users == 4


def test_hierarchy_cycle_detection():
    """Test that circular parent references do not cause infinite loops in tree traversal."""
    # A -> B -> C -> A
    cyclic_orgs = pd.DataFrame([
        {"org_id": "A", "name": "Org A", "parent_id": "C"},
        {"org_id": "B", "name": "Org B", "parent_id": "A"},
        {"org_id": "C", "name": "Org C", "parent_id": "B"},
    ])
    hierarchy = OrganizationHierarchy(cyclic_orgs)
    descendants = hierarchy.get_descendants("A")
    assert descendants == {"A", "B", "C"}


def test_self_referencing_parent():
    """Test org where parent_id is itself."""
    self_ref_df = pd.DataFrame([
        {"org_id": "ROOT", "name": "Root", "parent_id": "ROOT"},
        {"org_id": "CHILD", "name": "Child", "parent_id": "ROOT"}
    ])
    hierarchy = OrganizationHierarchy(self_ref_df)
    descendants = hierarchy.get_descendants("ROOT")
    assert descendants == {"ROOT", "CHILD"}


def test_unknown_organization_raises():
    """Test that non-existent org_id raises UnknownOrganizationError."""
    df = pd.DataFrame([{"org_id": "CORP", "name": "Corp", "parent_id": None}])
    hierarchy = OrganizationHierarchy(df)
    with pytest.raises(UnknownOrganizationError):
        hierarchy.get_descendants("GHOST_ORG")
