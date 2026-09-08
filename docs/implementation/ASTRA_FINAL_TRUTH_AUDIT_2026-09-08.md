# Astra Final Truth Audit
Date: 2026-09-08
Task ID: tsk_eva_f2b760b734e4
Project ID: prj_repair

## Scope of Review
The objective of this review is to ensure that all test scripts conform to the formatting standards enforced by `ruff format`. We have successfully reformatted the following test scripts:
- `testscript/test_healing_daemon.py`
- `testscript/test_healing_daemon_e2e.py`
- `testscript/test_healing_synthesizer.py`
- `testscript/test_portal_api.py`
- `testscript/test_render_adapter.py`
- `testscript/test_supabase_adapter.py`

## Git Diff Evidence
```diff
diff --git a/testscript/test_healing_daemon.py b/testscript/test_healing_daemon.py
index 480a50b..5a1fe8a 100644
--- a/testscript/test_healing_daemon.py
+++ b/testscript/test_healing_daemon.py
@@ -43,8 +43,12 @@ def test_daemon_handles_completed_task(mock_queue):
         assert calls[1][1].get("timeout") == 300
         assert "task_1" in daemon.processed_tasks
 
-        mock_queue.list_tasks.assert_any_call(status=TriageStatus.COMPLETED, limit=100, project_id=daemon.project_id)
-        mock_queue.list_tasks.assert_any_call(status=TriageStatus.FAILED, limit=100, project_id=daemon.project_id)
+        mock_queue.list_tasks.assert_any_call(
+            status=TriageStatus.COMPLETED, limit=100, project_id=daemon.project_id
+        )
+        mock_queue.list_tasks.assert_any_call(
+            status=TriageStatus.FAILED, limit=100, project_id=daemon.project_id
+        )
 
 
 def test_daemon_handles_completed_task_not_approved(mock_queue):
diff --git a/testscript/test_healing_daemon_e2e.py b/testscript/test_healing_daemon_e2e.py
index 748e73c..ea14287 100644
--- a/testscript/test_healing_daemon_e2e.py
+++ b/testscript/test_healing_daemon_e2e.py
@@ -20,7 +20,6 @@ def test_healing_daemon_e2e_lifecycle(temp_env):
     queue, tmp_path = temp_env
     daemon = CIHealingDaemon(queue, project_id="prj_repair")
 
-
     worktree = tmp_path / "worktree_e2e"
     worktree.mkdir()
     evidence_dir = worktree / "evidence"
@@ -66,7 +65,7 @@ def test_healing_daemon_e2e_lifecycle(temp_env):
 
     envelope_0 = json.loads(repair_task_0["envelope_json"])
     assert "tests/test_dummy.py" in envelope_0["allowed_paths"]
-    assert any(p in ('src', 'src/') for p in envelope_0["allowed_paths"])
+    assert any(p in ("src", "src/") for p in envelope_0["allowed_paths"])
 
     with sqlite3.connect(queue.db_path) as conn:
         conn.execute(
diff --git a/testscript/test_healing_synthesizer.py b/testscript/test_healing_synthesizer.py
index 13c3f73..e40ec01 100644
--- a/testscript/test_healing_synthesizer.py
+++ b/testscript/test_healing_synthesizer.py
@@ -9,21 +9,21 @@ def test_synthesizer_bounds_allowed_paths():
     assert "alpha_core/healing" in bounded
     assert "test_file.py" in bounded
 
+
 def test_synthesizer_rejects_unsafe_paths():
     synth = RepairEnvelopeSynthesizer("tsk_123", 1)
     bounded = synth.bound_allowed_paths(
-        ["alpha_core/healing/"],
-        ["../../etc/passwd", "/etc/shadow", "alpha_core/malicious.py"]
+        ["alpha_core/healing/"], ["../../etc/passwd", "/etc/shadow", "alpha_core/malicious.py"]
     )
     assert "../../etc/passwd" not in bounded
     assert "/etc/shadow" not in bounded
     assert "alpha_core/malicious.py" not in bounded
 
+
 def test_synthesizer_normalizes_paths():
     synth = RepairEnvelopeSynthesizer("tsk_123", 1)
     bounded = synth.bound_allowed_paths(
-        ["alpha_core//healing/../healing"],
-        ["alpha_core/healing/./test.py"]
+        ["alpha_core//healing/../healing"], ["alpha_core/healing/./test.py"]
     )
     assert "alpha_core/healing/test.py" in bounded
 
@@ -41,7 +41,9 @@ def test_synthesizer_formats_actionable_prompt():
         "ruff_violations": [{"file": "other.py"}],
         "signature": "abc123hash",
     }
-    result = synth.synthesize(["alpha_core/", "test_file.py", "other.py"], failures, "prj_1", "/worktree")
+    result = synth.synthesize(
+        ["alpha_core/", "test_file.py", "other.py"], failures, "prj_1", "/worktree"
+    )
 
     assert result["parent_task_id"] == "tsk_123"
     assert result["repair_epoch"] == 1
diff --git a/testscript/test_portal_api.py b/testscript/test_portal_api.py
index 5054fc2..50c0682 100644
--- a/testscript/test_portal_api.py
+++ b/testscript/test_portal_api.py
@@ -109,7 +109,9 @@ async def test_portal_stream(mock_queue):
 
     with patch("alpha_core.api.app.portal_stream_generator", side_effect=mock_generator):
         async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
-            async with ac.stream("GET", f"/api/portal/projects/prj_test/stream?token={token}") as response:
+            async with ac.stream(
+                "GET", f"/api/portal/projects/prj_test/stream?token={token}"
+            ) as response:
                 assert response.status_code == 200
                 lines = []
                 async for line in response.aiter_lines():
diff --git a/testscript/test_render_adapter.py b/testscript/test_render_adapter.py
index 0b83c64..5a54bd5 100644
--- a/testscript/test_render_adapter.py
+++ b/testscript/test_render_adapter.py
@@ -162,6 +162,7 @@ async def test_check_health_exception(adapter):
         health_ok = await adapter.check_health("https://test-app.onrender.com")
         assert health_ok is False
 
+
 @pytest.mark.asyncio
 async def test_deploy_preview_with_commit_id(adapter):
     def mock_make_request(method, endpoint, data=None):
@@ -169,6 +170,7 @@ async def test_deploy_preview_with_commit_id(adapter):
             return {"service": {"env": "preview"}}
         if method == "POST" and endpoint == "/services/srv_123/deploys":
             import json
+
             if data:
                 parsed = json.loads(data)
                 assert parsed.get("commitId") == "abc1234"
@@ -187,6 +189,7 @@ async def test_deploy_preview_with_commit_id(adapter):
                     assert result.url == "https://test-app.onrender.com"
                     assert result.status == "LIVE"
 
+
 @pytest.mark.asyncio
 async def test_deploy_preview_rejects_production(adapter):
     def mock_make_request(method, endpoint, data=None):
@@ -195,5 +198,7 @@ async def test_deploy_preview_rejects_production(adapter):
         return {}
 
     with patch.object(adapter, "_make_request", side_effect=mock_make_request):
-        with pytest.raises(RuntimeError, match="Cannot deploy to production targets in preview mode"):
+        with pytest.raises(
+            RuntimeError, match="Cannot deploy to production targets in preview mode"
+        ):
             await adapter.deploy_preview()
diff --git a/testscript/test_supabase_adapter.py b/testscript/test_supabase_adapter.py
index e91f14e..594aeac 100644
--- a/testscript/test_supabase_adapter.py
+++ b/testscript/test_supabase_adapter.py
@@ -159,6 +159,7 @@ async def test_get_migration_status_error(mock_make_request, adapter):
     with pytest.raises(RuntimeError, match=r"Failed to inspect migration status: failed \*\*\*"):
         await adapter.get_migration_status()
 
+
 @pytest.mark.asyncio
 async def test_plan_migration_success(adapter):
     plan = await adapter.plan_migration("CREATE TABLE new_table (id int);")
@@ -166,11 +167,13 @@ async def test_plan_migration_success(adapter):
     assert plan["requires_approval"] is True
     assert plan["sql"] == "CREATE TABLE new_table (id int);"
 
+
 @pytest.mark.asyncio
 async def test_plan_migration_destructive(adapter):
     with pytest.raises(DestructiveDDLError):
         await adapter.plan_migration("DROP TABLE users;")
 
+
 @pytest.mark.asyncio
 async def test_rollback_migration(adapter):
     result = await adapter.rollback_migration("20230101")
```

## Conclusion
All test assertions are complete and verified. `ruff format` successfully applied and no remaining structural changes are required.
