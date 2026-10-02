"""Unit tests for Mobile Bridge Pagination and Caching (Worker 2 & 5).

Verifies:
1. list_triage_tasks_paginated returns items, total, limit, offset, has_more.
2. Parameter clamping (limit 1..50, offset >= 0).
3. get_git_worktrees_paginated returns correct pagination structure.
"""

from alpha_core.mobile_bridge.service import MobileBridgeService


def test_triage_pagination():
    svc = MobileBridgeService()
    # 1. Page 1 default
    res = svc.list_triage_tasks_paginated(limit=5, offset=0)
    assert "items" in res
    assert "total" in res
    assert "limit" in res
    assert "offset" in res
    assert "has_more" in res
    assert res["limit"] == 5
    assert res["offset"] == 0
    assert len(res["items"]) <= 5
    if res["total"] > 5:
        assert res["has_more"] is True

    # 2. Clamping
    res_clamped = svc.list_triage_tasks_paginated(limit=100, offset=-5)
    assert res_clamped["limit"] == 50
    assert res_clamped["offset"] == 0

    # 3. Beyond end
    res_beyond = svc.list_triage_tasks_paginated(limit=10, offset=99999)
    assert len(res_beyond["items"]) == 0
    assert res_beyond["has_more"] is False


def test_worktrees_pagination():
    svc = MobileBridgeService()
    res = svc.get_git_worktrees_paginated(limit=10, offset=0)
    assert "items" in res
    assert "total" in res
    assert "limit" in res
    assert "offset" in res
    assert "has_more" in res
    assert res["limit"] == 10
    assert res["offset"] == 0
    assert len(res["items"]) <= 10
