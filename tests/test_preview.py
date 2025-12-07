"""
Unit tests for preview module.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from utils.preview import get_gallery_images, natural_sort_key, async_multithread_download
from config.config import cfg

def test_natural_sort_key():
    assert natural_sort_key("1.jpg") == ['', 1, '.jpg']
    assert natural_sort_key("10.jpg") == ['', 10, '.jpg']
    assert natural_sort_key("2.jpg") == ['', 2, '.jpg']
    
    files = ["1.jpg", "10.jpg", "2.jpg", "foo.jpg"]
    files.sort(key=natural_sort_key)
    assert files == ["1.jpg", "2.jpg", "10.jpg", "foo.jpg"]

@pytest.mark.asyncio
async def test_get_gallery_images_success():
    # Mock objects
    mock_mes = AsyncMock()
    mock_user = MagicMock()
    
    # Mock http client response
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    
    # We patch multiple dependencies
    with patch('utils.preview.http.get', return_value=mock_resp) as mock_http_get, \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download, \
         patch('utils.preview.zipfile.ZipFile'), \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.os.listdir', return_value=['1.jpg', '2.jpg']), \
         patch('utils.preview.os.path.isfile', return_value=True), \
         patch('utils.preview.os.remove'), \
         patch('utils.preview.shutil.rmtree'), \
         patch('utils.preview.subprocess.run') as mock_run, \
         patch('utils.preview.telepress.TelegraphPublisher') as mock_publisher_cls, \
         patch('utils.preview.Preview.create', new_callable=AsyncMock) as mock_db_create, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:

        # Configure mocks
        mock_download.return_value = True
        mock_publisher = MagicMock()
        mock_publisher_cls.return_value = mock_publisher
        mock_to_thread.return_value = "http://telegra.ph/test"

        # Execute
        result = await get_gallery_images(
            gid="123", 
            token="abc", 
            d_url="http://download", 
            mes=mock_mes, 
            user=mock_user
        )

        # Assertions
        assert result is True
        mock_mes.edit_text.assert_called()
        mock_run.assert_called() # rclone called
        mock_to_thread.assert_called() # telepress called
        mock_db_create.assert_called() # db created

@pytest.mark.asyncio
async def test_get_gallery_images_key_missing():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "Key missing, or incorrect key provided."
    
    with patch('utils.preview.http.get', return_value=mock_resp):
        result = await get_gallery_images("123", "abc", "http://d", AsyncMock(), MagicMock())
        assert result[0] is False
        assert result[1] == "请检查画廊是否正确"

@pytest.mark.asyncio
async def test_get_gallery_images_download_fail():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    
    # Mock download failing
    with patch('utils.preview.http.get', return_value=mock_resp), \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download:
        
        mock_download.return_value = (False, "Download Error")
        
        result = await get_gallery_images("123", "abc", "http://d", AsyncMock(), MagicMock())
        assert result[0] is False
        assert result[1] == "Download Error"

@pytest.mark.asyncio
async def test_get_gallery_images_telepress_fail():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    
    with patch('utils.preview.http.get', return_value=mock_resp), \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download, \
         patch('utils.preview.zipfile.ZipFile'), \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.os.listdir', return_value=['1.jpg']), \
         patch('utils.preview.os.path.isfile', return_value=True), \
         patch('utils.preview.os.remove'), \
         patch('utils.preview.shutil.rmtree'), \
         patch('utils.preview.subprocess.run'), \
         patch('utils.preview.telepress.TelegraphPublisher'), \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_download.return_value = True
        
        async def raise_error(*args, **kwargs):
            raise Exception("Telepress Error")
        mock_to_thread.side_effect = raise_error

        result = await get_gallery_images("123", "abc", "http://d", AsyncMock(), MagicMock())
        
        assert result[0] is False
        assert str(result[1]) == "Telepress Error"


# ============ Telegraph Mode Tests ============

@pytest.mark.asyncio
async def test_get_gallery_images_telegraph_mode():
    """Test Telegraph direct upload mode."""
    cfg['storage_mode'] = 'telegraph'
    
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    mock_mes = AsyncMock()
    mock_user = MagicMock()
    
    with patch('utils.preview.http.get', return_value=mock_resp), \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download, \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.os.path.exists', return_value=True), \
         patch('utils.preview.os.remove'), \
         patch('utils.preview.shutil.rmtree'), \
         patch('utils.preview.telepress.publish') as mock_publish, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread, \
         patch('utils.preview.Preview.create', new_callable=AsyncMock):
        
        mock_download.return_value = True
        mock_to_thread.return_value = "http://telegra.ph/test"
        
        result = await get_gallery_images("123", "abc", "http://d", mock_mes, mock_user)
        
        assert result is True
        # Verify telepress.publish was called (via asyncio.to_thread)
        mock_to_thread.assert_called()
    
    # Reset config
    cfg['storage_mode'] = 'r2'


@pytest.mark.asyncio  
async def test_get_gallery_images_r2_mode():
    """Test R2 storage mode (default)."""
    cfg['storage_mode'] = 'r2'
    
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><h1 id="gn">Test Gallery</h1></html>'
    mock_mes = AsyncMock()
    mock_user = MagicMock()
    
    with patch('utils.preview.http.get', return_value=mock_resp), \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download, \
         patch('utils.preview.zipfile.ZipFile'), \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.os.listdir', return_value=['1.jpg', '2.jpg']), \
         patch('utils.preview.os.path.isfile', return_value=True), \
         patch('utils.preview.os.path.exists', return_value=True), \
         patch('utils.preview.os.remove'), \
         patch('utils.preview.shutil.rmtree'), \
         patch('utils.preview.subprocess.run') as mock_rclone, \
         patch('utils.preview.telepress.TelegraphPublisher') as mock_publisher_cls, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread, \
         patch('utils.preview.Preview.create', new_callable=AsyncMock):
        
        mock_download.return_value = True
        mock_to_thread.return_value = "http://telegra.ph/test"
        
        result = await get_gallery_images("123", "abc", "http://d", mock_mes, mock_user)
        
        assert result is True
        # Verify rclone was called in R2 mode
        mock_rclone.assert_called()


# ============ Natural Sort Tests ============

def test_natural_sort_key_complex():
    """Test natural sort with complex filenames."""
    files = [
        "image_1.png",
        "image_10.png", 
        "image_2.png",
        "image_100.png",
        "image_20.png"
    ]
    files.sort(key=natural_sort_key)
    assert files == [
        "image_1.png",
        "image_2.png",
        "image_10.png",
        "image_20.png",
        "image_100.png"
    ]


def test_natural_sort_key_mixed():
    """Test natural sort with mixed content."""
    files = ["a1b2.jpg", "a1b10.jpg", "a2b1.jpg"]
    files.sort(key=natural_sort_key)
    assert files == ["a1b2.jpg", "a1b10.jpg", "a2b1.jpg"]


# ============ HTTP Error Tests ============

@pytest.mark.asyncio
async def test_get_gallery_images_http_error():
    """Test handling of HTTP errors."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 404
    
    with patch('utils.preview.http.get', return_value=mock_resp):
        result = await get_gallery_images("123", "abc", "http://d", AsyncMock(), MagicMock())
        assert result[0] is False
        assert "无法获取画廊信息" in result[1]


@pytest.mark.asyncio
async def test_get_gallery_images_no_title():
    """Test handling when title is not found."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><body>No title here</body></html>'
    mock_mes = AsyncMock()
    
    with patch('utils.preview.http.get', return_value=mock_resp), \
         patch('utils.preview.async_multithread_download', new_callable=AsyncMock) as mock_download, \
         patch('utils.preview.os.makedirs'), \
         patch('utils.preview.os.path.exists', return_value=True), \
         patch('utils.preview.os.remove'), \
         patch('utils.preview.shutil.rmtree'), \
         patch('utils.preview.telepress.publish'), \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread, \
         patch('utils.preview.Preview.create', new_callable=AsyncMock):
        
        cfg['storage_mode'] = 'telegraph'
        mock_download.return_value = True
        mock_to_thread.return_value = "http://telegra.ph/test"
        
        result = await get_gallery_images("123", "abc", "http://d", mock_mes, MagicMock())
        
        # Should use "Unknown Title" as fallback
        assert result is True
    
    cfg['storage_mode'] = 'r2'
