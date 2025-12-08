"""
Extended unit tests for API endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from utils.api import app

class TestResolveEndpointExtended:
    """Extended tests for /resolve endpoint."""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    @pytest.mark.asyncio
    async def test_resolve_success_with_quality(self):
        """Test resolve success with image_quality parameter."""
        
        # Mock data
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.group = "普通用户"
        
        mock_cost = {'org': 1000, 'res': 500, 'pre': 1300}
        
        with patch('utils.api.verify_user', new_callable=AsyncMock) as mock_verify, \
             patch('utils.api.get_GP_cost', new_callable=AsyncMock) as mock_get_cost, \
             patch('utils.api.get_current_GP', return_value=2000), \
             patch('utils.api.get_gallery_info', new_callable=AsyncMock) as mock_info, \
             patch('utils.api.get_download_url', new_callable=AsyncMock) as mock_get_url, \
             patch('utils.api.deduct_GP', new_callable=AsyncMock) as mock_deduct:
            
            mock_verify.return_value = mock_user
            mock_get_cost.return_value = mock_cost
            mock_info.return_value = ("Info", False, "thumb", mock_cost, 0)
            mock_get_url.return_value = "http://download"
            
            # Test resolve with 'res' quality
            response = self.client.post("/resolve", json={
                "apikey": "test_key",
                "gid": 123,
                "token": "abc",
                "image_quality": "res"
            })
            
            data = response.json()
            assert data["code"] == 0
            assert "解析成功" in data["msg"]
            assert "http://download1?start=1" in data["data"]["archive_url"]
            
            mock_get_url.assert_called_with(mock_user, 123, "abc", "res", 500, 0)
            mock_deduct.assert_called_with(mock_user, 500)

    @pytest.mark.asyncio
    async def test_resolve_invalid_quality(self):
        """Test resolve with invalid image_quality."""
        
        mock_user = MagicMock()
        
        with patch('utils.api.verify_user', new_callable=AsyncMock) as mock_verify, \
             patch('utils.api.get_GP_cost', new_callable=AsyncMock) as mock_get_cost:
            
            mock_verify.return_value = mock_user
            mock_get_cost.return_value = {'org': 1000, 'res': 500}
            
            response = self.client.post("/resolve", json={
                "apikey": "test_key",
                "gid": 123,
                "token": "abc",
                "image_quality": "invalid"
            })
            
            data = response.json()
            assert data["code"] == 9
            assert "参数 image_quality 非法" in data["msg"]

    @pytest.mark.asyncio
    async def test_resolve_insufficient_gp(self):
        """Test resolve with insufficient GP."""
        
        mock_user = MagicMock()
        mock_cost = {'org': 1000, 'res': 500}
        
        with patch('utils.api.verify_user', new_callable=AsyncMock) as mock_verify, \
             patch('utils.api.get_GP_cost', new_callable=AsyncMock) as mock_get_cost, \
             patch('utils.api.get_current_GP', return_value=100):
            
            mock_verify.return_value = mock_user
            mock_get_cost.return_value = mock_cost
            
            response = self.client.post("/resolve", json={
                "apikey": "test_key",
                "gid": 123,
                "token": "abc",
                "image_quality": "res"
            })
            
            data = response.json()
            assert data["code"] == 5
            assert "GP 不足" in data["msg"]
