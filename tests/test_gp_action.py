"""
Unit tests for GP action utility functions.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone
from utils.GP_action import get_current_GP, checkin, deduct_GP

def create_mock_record(amount, expire_days_from_now, source="签到"):
    record = MagicMock()
    record.amount = amount
    record.source = source
    # Use UTC to match logic
    record.expire_time = datetime.now(tz=timezone.utc) + timedelta(days=expire_days_from_now)
    # Async save mock
    record.save = AsyncMock()
    return record

def test_get_current_GP():
    user = MagicMock()
    # Mock records: 1 valid, 1 expired, 1 zero amount
    valid = create_mock_record(1000, 7)
    expired = create_mock_record(1000, -1)
    zero = create_mock_record(0, 7)
    
    user.GP_records = [valid, expired, zero]
    
    total = get_current_GP(user)
    assert total == 1000

@pytest.mark.asyncio
async def test_checkin_success():
    user = MagicMock()
    user.id = 123
    user.name = "Test User"
    user.GP_records = []
    
    with patch('utils.GP_action.GPRecord.create', new_callable=AsyncMock) as mock_create:
        amount, new_balance = await checkin(user)
        
        assert 10000 <= amount <= 20000
        assert new_balance == amount
        mock_create.assert_called_once()

@pytest.mark.asyncio
async def test_checkin_already_checked():
    user = MagicMock()
    # Mock a record that indicates checkin happened today (expires in 7 days)
    # Logic in checkin uses Asia/Shanghai time. 
    # To mock this robustly, we'd need to mock datetime or ensure the record matches.
    # We'll mock the record to have exactly 7 days from "today" (Shanghai).
    
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    
    record = MagicMock()
    record.source = "签到"
    # Create a datetime that converts to today+7 days in Shanghai
    target_date = today + timedelta(days=7)
    # We construct a mock expire_time whose .astimezone(...).date() returns target_date
    record.expire_time.astimezone.return_value.date.return_value = target_date
    record.amount = 1000
    
    user.GP_records = [record]
    
    # Also need get_current_GP to work
    # get_current_GP uses datetime.now(tz=timezone.utc)
    # We should ensure record.expire_time > now for it to count
    record.expire_time.__gt__ = lambda self, other: True 
    # Hacky, but assuming get_current_GP works or we mock it.
    
    with patch('utils.GP_action.get_current_GP', return_value=1000):
        with patch('utils.GP_action.GPRecord.create', new_callable=AsyncMock) as mock_create:
            amount, new_balance = await checkin(user)
            
            assert amount == 0
            assert new_balance == 1000
            mock_create.assert_not_called()

@pytest.mark.asyncio
async def test_deduct_GP_single_record():
    user = MagicMock()
    record = create_mock_record(2000, 7)
    
    # Mock chain: user.GP_records.filter().order_by().all()
    mock_query = AsyncMock()
    mock_query.return_value = [record] # .all() returns list
    
    mock_order = MagicMock()
    mock_order.all = mock_query
    
    mock_filter = MagicMock()
    mock_filter.order_by.return_value = mock_order
    
    user.GP_records.filter.return_value = mock_filter
    
    await deduct_GP(user, 500)
    
    assert record.amount == 1500
    record.save.assert_called_once()

@pytest.mark.asyncio
async def test_deduct_GP_multiple_records():
    user = MagicMock()
    # Need 2500 total.
    # Record 1: 1000
    # Record 2: 2000
    rec1 = create_mock_record(1000, 1)
    rec2 = create_mock_record(2000, 2)
    
    mock_query = AsyncMock()
    mock_query.return_value = [rec1, rec2]
    
    user.GP_records.filter.return_value.order_by.return_value.all = mock_query
    
    await deduct_GP(user, 2500)
    
    assert rec1.amount == 0
    assert rec2.amount == 500 # 2000 - (2500 - 1000) = 500
    
    rec1.save.assert_called_once()
    rec2.save.assert_called_once()
