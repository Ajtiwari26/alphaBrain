import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from alpha_worker.adapters.supabase_adapter import (
    DestructiveDDLError,
    MigrationStatus,
    SupabaseAdapter,
)


@pytest.fixture
def adapter():
    return SupabaseAdapter(api_url="https://api.example.com", api_key="secret-key")


def test_init_validation():
    with pytest.raises(ValueError, match="Supabase API URL cannot be empty"):
        SupabaseAdapter(api_url="", api_key="key")
    with pytest.raises(ValueError, match="Supabase API key cannot be empty"):
        SupabaseAdapter(api_url="url", api_key="")


def test_mask_secrets(adapter):
    assert adapter._mask_secrets("error with secret-key inside") == "error with *** inside"
    adapter.api_key = ""
    assert adapter._mask_secrets("error with secret-key inside") == "error with secret-key inside"


@patch("urllib.request.urlopen")
def test_make_request_success(mock_urlopen, adapter):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"status": "ok"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = adapter._make_request("GET", "/test")
    assert result == {"status": "ok"}


@patch("urllib.request.urlopen")
def test_make_request_http_error(mock_urlopen, adapter):
    mock_error = urllib.error.HTTPError(
        url="https://api.example.com/test",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )
    mock_error.read = MagicMock(return_value=b'{"error": "bad key secret-key"}')
    mock_urlopen.side_effect = mock_error

    with pytest.raises(
        RuntimeError, match=r"Supabase API error 403: {\"error\": \"bad key \*\*\*\"}"
    ):
        adapter._make_request("GET", "/test")


@patch("urllib.request.urlopen")
def test_make_request_general_exception(mock_urlopen, adapter):
    mock_urlopen.side_effect = Exception("connection failed with secret-key")
    with pytest.raises(
        RuntimeError, match=r"Supabase API request failed: connection failed with \*\*\*"
    ):
        adapter._make_request("GET", "/test")


@patch("urllib.request.urlopen")
def test_make_request_empty_response(mock_urlopen, adapter):
    mock_response = MagicMock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = adapter._make_request("GET", "/test")
    assert result == {}


@patch("urllib.request.urlopen")
def test_make_request_with_data(mock_urlopen, adapter):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"status": "ok"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = adapter._make_request("POST", "/test", data=b'{"key": "value"}')
    assert result == {"status": "ok"}

    # Verify Content-Type header was added
    call_args = mock_urlopen.call_args[0][0]
    assert call_args.get_header("Content-type") == "application/json"


@pytest.mark.asyncio
@patch("alpha_worker.adapters.supabase_adapter.SupabaseAdapter._make_request")
async def test_check_health_success(mock_make_request, adapter):
    mock_make_request.return_value = {"info": "all good"}
    assert await adapter.check_health() is True


@pytest.mark.asyncio
@patch("alpha_worker.adapters.supabase_adapter.SupabaseAdapter._make_request")
async def test_check_health_exception(mock_make_request, adapter):
    mock_make_request.side_effect = Exception("Network error")
    assert await adapter.check_health() is False


def test_validate_ddl_safe(adapter):
    adapter.validate_ddl("CREATE TABLE users (id serial primary key);")
    adapter.validate_ddl("ALTER TABLE users ADD COLUMN age int;")
    # Should not raise


def test_validate_ddl_destructive(adapter):
    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("DROP TABLE users;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("TRUNCATE TABLE logs;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("TRUNCATE logs;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("DROP SCHEMA public CASCADE;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("ALTER TABLE users DROP COLUMN age;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl('ALTER TABLE "users" DROP COLUMN age;')

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("ALTER TABLE users\nDROP COLUMN age;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("DROP INDEX my_idx;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("DROP FUNCTION my_func;")

    with pytest.raises(DestructiveDDLError, match="Destructive DDL detected"):
        adapter.validate_ddl("DROP TRIGGER my_trig;")


@pytest.mark.asyncio
@patch("alpha_worker.adapters.supabase_adapter.SupabaseAdapter._make_request")
async def test_get_migration_status_success(mock_make_request, adapter):
    mock_make_request.return_value = [{"version": "20230101"}, {"version": "20230102"}]
    status = await adapter.get_migration_status()
    assert isinstance(status, MigrationStatus)
    assert status.applied_count == 2
    assert status.pending_count is None
    assert status.is_healthy is True


@pytest.mark.asyncio
@patch("alpha_worker.adapters.supabase_adapter.SupabaseAdapter._make_request")
async def test_get_migration_status_error(mock_make_request, adapter):
    mock_make_request.side_effect = Exception("failed secret-key")
    with pytest.raises(RuntimeError, match=r"Failed to inspect migration status: failed \*\*\*"):
        await adapter.get_migration_status()
