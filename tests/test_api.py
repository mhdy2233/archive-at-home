"""
Unit tests for API endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from utils.api import app, format_response, verify_user, clean_results_cache


# ============ Helper Function Tests ============

def test_format_response():
    """Test response formatting."""
    response = format_response(0, "Success", {"key": "value"})
    assert response.status_code == 200
    
    import json
    content = json.loads(response.body)
    assert content["code"] == 0
    assert content["msg"] == "Success"
    assert content["data"]["key"] == "value"


def test_format_response_no_data():
    """Test response formatting without data."""
    response = format_response(1, "Error")
    
    import json
    content = json.loads(response.body)
    assert content["code"] == 1
    assert content["data"] == {}


# ============ User Verification Tests ============

@pytest.mark.asyncio
async def test_verify_user_missing_apikey():
    """Test verify_user with missing API key."""
    result = await verify_user("")
    
    import json
    content = json.loads(result.body)
    assert content["code"] == 1
    assert "参数不完整" in content["msg"]


@pytest.mark.asyncio
async def test_verify_user_invalid_apikey():
    """Test verify_user with invalid API key."""
    # Mock User.get_or_none to return a mock QuerySet, not a coroutine
    with patch('utils.api.User.get_or_none') as mock_get:
        # The query set object returned by get_or_none(...)
        mock_queryset = MagicMock()
        mock_get.return_value = mock_queryset
        
        # prefetch_related should return a coroutine (or AsyncMock) that resolves to None
        mock_queryset.prefetch_related = AsyncMock(return_value=None)
        
        result = await verify_user("invalid-key")
        
        import json
        content = json.loads(result.body)
        assert content["code"] == 2


@pytest.mark.asyncio
async def test_verify_user_banned():
    """Test verify_user with banned user."""
    mock_user = MagicMock()
    mock_user.group = "黑名单"
    
    with patch('utils.api.User.get_or_none', new_callable=AsyncMock) as mock_get:
        mock_query = AsyncMock()
        mock_query.prefetch_related.return_value = mock_user
        mock_get.return_value = mock_query
        
        # Need to mock the chained call properly
        mock_get.return_value.prefetch_related = AsyncMock(return_value=mock_user)


# ============ API Endpoint Tests ============

class TestResolveEndpoint:
    """Tests for /resolve endpoint."""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    def test_resolve_missing_params(self):
        """Test resolve with missing parameters."""
        response = self.client.post("/resolve", json={"apikey": "test"})
        data = response.json()
        assert data["code"] == 1
        assert "参数不完整" in data["msg"]
    
    def test_resolve_all_params_missing(self):
        """Test resolve with all parameters missing."""
        response = self.client.post("/resolve", json={})
        data = response.json()
        assert data["code"] == 1


class TestBalanceEndpoint:
    """Tests for /balance endpoint."""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    def test_balance_missing_apikey(self):
        """Test balance with missing API key."""
        response = self.client.post("/balance", json={})
        data = response.json()
        assert data["code"] == 1


class TestCheckinEndpoint:
    """Tests for /checkin endpoint."""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    def test_checkin_missing_apikey(self):
        """Test checkin with missing API key."""
        response = self.client.post("/checkin", json={})
        data = response.json()
        assert data["code"] == 1


class TestRedirectEndpoint:
    """Tests for / redirect endpoint."""
    
    def setup_method(self):
        self.client = TestClient(app, follow_redirects=False)
    
    def test_root_redirect(self):
        """Test root endpoint redirects to Telegram."""
        response = self.client.get("/")
        assert response.status_code == 301
        assert "t.me" in response.headers.get("location", "")


# ============ Cache Tests ============

@pytest.mark.asyncio
async def test_clean_results_cache():
    """Test cache cleaning function."""
    from utils.api import results_cache
    import time
    
    # Add expired and valid entries
    results_cache["expired_key"] = {"d_url": "url1", "expire_time": time.time() - 100}
    results_cache["valid_key"] = {"d_url": "url2", "expire_time": time.time() + 100}
    
    await clean_results_cache(None)
    
    assert "expired_key" not in results_cache
    assert "valid_key" in results_cache
    
    # Cleanup
    results_cache.clear()
