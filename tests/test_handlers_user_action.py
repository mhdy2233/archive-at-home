"""
Unit tests for user action handlers.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from handlers.user_action import start, handle_checkin

@pytest.mark.asyncio
async def test_start_new_user():
    # Mock update and context
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_message.from_user.id = 12345
    update.effective_message.from_user.full_name = "Test User"
    # reply_text is awaited
    update.effective_message.reply_text = AsyncMock()
    
    context = MagicMock()
    context.args = []
    
    # Mock DB
    mock_user = MagicMock()
    mock_user.id = 12345
    mock_user.name = "Test User"
    
    with patch('handlers.user_action.User.get_or_create', new_callable=AsyncMock) as mock_db:
        mock_db.return_value = (mock_user, True) # created = True
        
        await start(update, context)
        
        mock_db.assert_called_once()
        update.effective_message.reply_text.assert_called_with("🎉 欢迎加入，您已成功注册！")

@pytest.mark.asyncio
async def test_start_existing_user():
    # Mock update and context
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_message.from_user.id = 12345
    update.effective_message.reply_text = AsyncMock()
    
    context = MagicMock()
    context.args = []
    
    with patch('handlers.user_action.User.get_or_create', new_callable=AsyncMock) as mock_db:
        mock_db.return_value = (MagicMock(), False) # created = False
        
        await start(update, context)
        
        update.effective_message.reply_text.assert_called_with("✅ 您已经注册过了~")

@pytest.mark.asyncio
async def test_handle_checkin_success():
    update = MagicMock()
    update.effective_message.from_user.id = 12345
    update.effective_message.reply_text = AsyncMock()
    
    mock_user = MagicMock()
    
    # Mock chained DB call: User.get_or_none().prefetch_related()
    with patch('handlers.user_action.User.get_or_none') as mock_get:
        # User.get_or_none(...) -> QuerySet -> prefetch_related -> await -> user
        mock_qs = MagicMock()
        mock_get.return_value = mock_qs
        mock_qs.prefetch_related = AsyncMock(return_value=mock_user)
        
        # Mock checkin logic
        with patch('handlers.user_action.checkin', new_callable=AsyncMock) as mock_checkin:
            mock_checkin.return_value = (100, 1100) # amount, balance
            
            await handle_checkin(update, MagicMock())
            
            # Verify reply contains success message
            args, _ = update.effective_message.reply_text.call_args
            assert "签到成功！获得 100 GP" in args[0]
            assert "当前余额：1100 GP" in args[0]
