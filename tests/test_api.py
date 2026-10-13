"""API endpoint tests for Bruviti Software License Analytics.
"""

from fastapi.testclient import TestClient


def test_01_health_endpoint_returns_ok(client: TestClient):
    """Test 1: Health endpoint returns HTTP 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_02_missing_required_date_parameters(client: TestClient):
    """Test 2: Missing required date parameters returns HTTP 400."""
    # Missing both
    res1 = client.get("/api/summary")
    assert res1.status_code == 400
    assert "Missing required query parameter" in res1.json()["detail"]

    # Missing 'to'
    res2 = client.get("/api/summary?from=2024-01-01")
    assert res2.status_code == 400
    assert "to" in res2.json()["detail"]

    # Missing 'from' on /api/tools
    res3 = client.get("/api/tools?to=2024-01-31")
    assert res3.status_code == 400
    assert "from" in res3.json()["detail"]


def test_03_invalid_date_format(client: TestClient):
    """Test 3: Malformed date string returns HTTP 400."""
    res1 = client.get("/api/summary?from=invalid-date&to=2024-01-31")
    assert res1.status_code == 400
    assert "Invalid date format for 'from'" in res1.json()["detail"]

    res2 = client.get("/api/tools?from=2024-01-01&to=2024-13-45")
    assert res2.status_code == 400
    assert "Invalid date format for 'to'" in res2.json()["detail"]


def test_04_from_date_later_than_to_date(client: TestClient):
    """Test 4: 'from' date later than 'to' date returns HTTP 400."""
    res = client.get("/api/summary?from=2024-02-01&to=2024-01-01")
    assert res.status_code == 400
    assert "must be less than or equal to" in res.json()["detail"]


def test_16_unknown_organization_handling(client: TestClient):
    """Test 16: Unknown organization ID returns HTTP 404."""
    res = client.get("/api/summary?from=2024-01-01&to=2024-01-31&org=NON_EXISTENT_ORG_XYZ")
    assert res.status_code == 404
    assert "Organization unit 'NON_EXISTENT_ORG_XYZ' not found" in res.json()["detail"]


def test_25_exactly_five_tool_records_in_order(client: TestClient):
    """Test 25: Exactly five tool records in canonical order (Tool A -> Tool E)."""
    res = client.get("/api/tools?from=2024-01-01&to=2024-01-31")
    assert res.status_code == 200
    data = res.json()

    assert len(data) == 5
    expected_order = ["Tool A", "Tool B", "Tool C", "Tool D", "Tool E"]
    actual_order = [item["tool"] for item in data]
    assert actual_order == expected_order


def test_26_response_schema_and_json_types(client: TestClient):
    """Test 26: Validate JSON structure and field types for summary and tools."""
    # Summary response
    res_summary = client.get("/api/summary?from=2024-01-01&to=2024-01-31")
    assert res_summary.status_code == 200
    s_data = res_summary.json()

    assert isinstance(s_data["licensed_users"], int)
    assert isinstance(s_data["active_users"], int)
    assert isinstance(s_data["engagement_pct"], (float, int))
    assert isinstance(s_data["spend"], (float, int))
    assert isinstance(s_data["idle_spend"], (float, int))

    # Tools response
    res_tools = client.get("/api/tools?from=2024-01-01&to=2024-01-31")
    assert res_tools.status_code == 200
    t_data = res_tools.json()

    for item in t_data:
        assert isinstance(item["tool"], str)
        assert isinstance(item["licensed_users"], int)
        assert isinstance(item["active_users"], int)
        assert isinstance(item["engagement_pct"], (float, int))
        assert isinstance(item["spend"], (float, int))
        assert isinstance(item["idle_spend"], (float, int))
        assert item["cost_per_active"] is None or isinstance(item["cost_per_active"], (float, int))


def test_28_all_endpoints_work_with_default_data(client: TestClient):
    """Test 28: End-to-end sanity check that all endpoints function with default dataset."""
    # Root dashboard
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")

    # Company-wide summary
    res_sum = client.get("/api/summary?from=2026-05-01&to=2026-05-31")
    assert res_sum.status_code == 200
    s_json = res_sum.json()
    assert s_json["licensed_users"] > 0
    assert s_json["spend"] > 0

    # Org-filtered summary
    res_org = client.get("/api/summary?from=2026-05-01&to=2026-05-31&org=ORG01")
    assert res_org.status_code == 200
    org_json = res_org.json()
    assert org_json["licensed_users"] <= s_json["licensed_users"]

    # Tools endpoint
    res_tools = client.get("/api/tools?from=2026-05-01&to=2026-05-31&org=ORG01")
    assert res_tools.status_code == 200
    assert len(res_tools.json()) == 5
