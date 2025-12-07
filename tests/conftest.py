"""
Shared pytest fixtures for all tests.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

# Mock config before importing modules
from config.config import cfg

cfg.update({
    'download_folder': '/tmp/download',
    'temp_folder': '/tmp/temp',
    'rclone_upload_remote': 'remote:bucket',
    'preview_url': 'http://example.com/gallery/',
    'preview_download_thread': 4,
    'ph_token': None,
    'storage_mode': 'r2',
    'AD': None,
    'eh_cookie': 'test_cookie',
    'BOT_TOKEN': 'test_token',
})


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = 123
    user.name = "TestUser"
    user.apikey = "test-api-key-uuid"
    user.group = "普通用户"
    user.GP_records = []
    return user


@pytest.fixture
def mock_message():
    """Create a mock Telegram message object."""
    return AsyncMock()


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response."""
    response = AsyncMock()
    response.status_code = 200
    response.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    return response


@pytest.fixture
def sample_gallery_html():
    """Sample E-Hentai gallery page HTML."""
    return '''
    <html>
    <head><title>Test Gallery</title></head>
    <body>
        <h1 id="gn">Test Gallery Title</h1>
        <h1 id="gj">テストギャラリー</h1>
    </body>
    </html>
    '''


@pytest.fixture
def mock_db_user():
    """Create a mock database user with related records."""
    from datetime import datetime, timedelta, timezone
    
    user = MagicMock()
    user.id = 123
    user.name = "TestUser"
    user.apikey = "test-api-key"
    user.group = "普通用户"
    
    # Mock GP records
    gp_record = MagicMock()
    gp_record.amount = 1000
    gp_record.expire_time = datetime.now(tz=timezone.utc) + timedelta(days=7)
    user.GP_records = [gp_record]
    
    return user
