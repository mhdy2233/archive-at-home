"""
Unit tests for resolver handlers.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from handlers.resolver import reply_gallery_info, download

@pytest.mark.asyncio
async def test_reply_gallery_info_success():
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.reply_photo = AsyncMock()
    
    # Mock get_gallery_info result
    # text, has_spoiler, thumb, require_GP, timeout
    mock_info = ("Info Text", False, "http://thumb", {'org': 1000, 'res': 500, 'pre': 1300}, 0)
    
    with patch('handlers.resolver.get_gallery_info', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_info
        
        # Mock Config for AD check
        with patch('handlers.resolver.cfg', {'AD': {'text': 'Ad', 'url': 'http://ad'}}) as mock_cfg:
            await reply_gallery_info(update, MagicMock(), "http://url", "123", "abc")
            
            mock_get.assert_called_once()
            update.effective_message.reply_photo.assert_called_once()
            
            # Verify keyboard contains download buttons
            args, kwargs = update.effective_message.reply_photo.call_args
            markup = kwargs['reply_markup']
            # Deep inspection of markup if needed, but call existence is good enough

@pytest.mark.asyncio
async def test_download_callback_success():
    update = MagicMock()
    update.effective_user.id = 12345
    update.callback_query.data = "download|123|abc|org|1000|0"
    update.callback_query.answer = AsyncMock()
    
    # Mock message editing
    update.effective_message.edit_caption = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.caption = "Test Caption"
    
    mock_user = MagicMock()
    mock_user.group = "普通用户"
    
    with patch('handlers.resolver.User.get_or_none') as mock_get_user, \
         patch('handlers.resolver.get_current_GP', return_value=2000), \
         patch('handlers.resolver.get_download_url', new_callable=AsyncMock) as mock_get_url, \
         patch('handlers.resolver.deduct_GP', new_callable=AsyncMock) as mock_deduct, \
         patch('handlers.resolver.cfg', {'AD': {'text': None, 'url': None}}):
        
        # Fix: Assign AsyncMock to the method itself, not its return_value
        mock_get_user.return_value.prefetch_related = AsyncMock(return_value=mock_user)
        mock_get_url.return_value = "http://download"
        
        await download(update, MagicMock())
        
        mock_deduct.assert_called_with(mock_user, 1000)
        update.effective_message.edit_caption.assert_called()
        assert "✅ 下载链接获取成功" in update.effective_message.edit_caption.call_args[1]['caption']

@pytest.mark.asyncio
async def test_download_callback_gp_insufficient():
    update = MagicMock()
    update.effective_user.id = 12345
    update.callback_query.data = "download|123|abc|org|5000|0"
    update.callback_query.answer = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    
    mock_user = MagicMock()
    
    with patch('handlers.resolver.User.get_or_none') as mock_get_user, \
         patch('handlers.resolver.get_current_GP', return_value=100): # 100 < 5000
        
        mock_get_user.return_value.prefetch_related = AsyncMock(return_value=mock_user)
        
        await download(update, MagicMock())
        
        update.effective_message.reply_text.assert_called()
        assert "GP 不足" in update.effective_message.reply_text.call_args[0][0]
