"""
Unit tests for resolve utility functions.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from collections import defaultdict
import utils.resolve as resolve_module
from utils.resolve import get_gallery_info, get_download_url

# Initialize tag_map for testing
resolve_module.tag_map = defaultdict(lambda: {"name": "", "data": {}})

@pytest.mark.asyncio
async def test_get_gallery_info_success():
    # Mock dependencies
    mock_cost = {'org': 1000, 'res': 500, 'pre': 1300}
    mock_gdata = {
        'title': 'Test Gallery',
        'title_jpn': '测试画廊',
        'rating': '4.5',
        'category': 'Doujinshi',
        'uploader': 'Tester',
        'posted': '1600000000',
        'filecount': '10',
        'tags': ['language:chinese', 'group:test'],
        'thumb': 'http://s.exhentai.org/t/1.jpg'
    }
    
    with patch('utils.resolve.get_GP_cost', new_callable=AsyncMock) as mock_get_cost, \
         patch('utils.resolve.get_gdata', new_callable=AsyncMock) as mock_get_gdata:
        
        mock_get_cost.return_value = mock_cost
        mock_get_gdata.return_value = mock_gdata
        
        text, is_h, thumb, cost, timeout = await get_gallery_info(123, 'abc')
        
        assert "主标题：Test Gallery" in text
        assert is_h is True
        assert thumb == 'http://ehgt.org/t/1.jpg'
        assert cost == mock_cost

@pytest.mark.asyncio
async def test_get_download_url_success():
    user = MagicMock()
    user.name = "TestUser"
    
    client = MagicMock()
    client.url = "http://node1"
    client.enable_GP_cost = 1
    client.save = AsyncMock()
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "msg": "Success",
        "d_url": "http://download/file.zip?start=1",
        "require_GP": 100,
        "status": {
            "msg": {"Free": 1, "EX": "OK", "GP": 1000, "Credits": 0},
            "enable_GP_cost": 1
        }
    }
    
    with patch('utils.resolve.get_available_clients', new_callable=AsyncMock) as mock_get_clients, \
         patch('utils.resolve.http.post', new_callable=AsyncMock) as mock_post, \
         patch('utils.resolve.ArchiveHistory.create', new_callable=AsyncMock) as mock_history:
        
        mock_get_clients.return_value = [client]
        mock_post.return_value = mock_resp
        
        url = await get_download_url(user, 123, 'abc', 'org', 1000, 0)
        
        assert url == "http://download/file.zip"
        mock_history.assert_called_once()
        client.save.assert_called() # status updated

@pytest.mark.asyncio
async def test_get_download_url_no_clients():
    with patch('utils.resolve.get_available_clients', new_callable=AsyncMock) as mock_get_clients:
        mock_get_clients.return_value = []
        
        url = await get_download_url(MagicMock(), 123, 'abc', 'org', 1000, 0)
        assert url is None

@pytest.mark.asyncio
async def test_get_download_url_client_fail():
    client = MagicMock()
    client.url = "http://node1"
    client.save = AsyncMock()
    
    with patch('utils.resolve.get_available_clients', new_callable=AsyncMock) as mock_get_clients, \
         patch('utils.resolve.http.post', new_callable=AsyncMock) as mock_post:
        
        mock_get_clients.return_value = [client]
        mock_post.side_effect = Exception("Network Error")
        
        url = await get_download_url(MagicMock(), 123, 'abc', 'org', 1000, 0)
        
        assert url is None
        assert client.status == "异常"
        client.save.assert_called()
