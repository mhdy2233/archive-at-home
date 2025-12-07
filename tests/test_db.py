"""
Unit tests for database models.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock


# ============ Model Definition Tests ============

def test_user_model_fields():
    """Test User model has expected fields."""
    from db.db import User
    
    # Check field names exist
    field_names = [f.model_field_name for f in User._meta.fields_map.values() if hasattr(f, 'model_field_name')]
    
    assert 'id' in User._meta.fields_map
    assert 'name' in User._meta.fields_map
    assert 'apikey' in User._meta.fields_map
    assert 'group' in User._meta.fields_map


def test_gp_record_model_fields():
    """Test GPRecord model has expected fields."""
    from db.db import GPRecord
    
    assert 'amount' in GPRecord._meta.fields_map
    assert 'expire_time' in GPRecord._meta.fields_map
    assert 'source' in GPRecord._meta.fields_map


def test_client_model_fields():
    """Test Client model has expected fields."""
    from db.db import Client
    
    assert 'url' in Client._meta.fields_map
    assert 'enable_GP_cost' in Client._meta.fields_map
    assert 'status' in Client._meta.fields_map


def test_archive_history_model_fields():
    """Test ArchiveHistory model has expected fields."""
    from db.db import ArchiveHistory
    
    assert 'gid' in ArchiveHistory._meta.fields_map
    assert 'token' in ArchiveHistory._meta.fields_map
    assert 'GP_cost' in ArchiveHistory._meta.fields_map


def test_preview_model_fields():
    """Test Preview model has expected fields."""
    from db.db import Preview
    
    assert 'gid' in Preview._meta.fields_map
    assert 'token' in Preview._meta.fields_map
    assert 'ph_url' in Preview._meta.fields_map


# ============ Default Value Tests ============

def test_gp_record_default_expire_time():
    """Test GPRecord default expire_time is ~7 days from now."""
    from db.db import GPRecord
    
    # Get the default function
    expire_field = GPRecord._meta.fields_map['expire_time']
    default_func = expire_field.default
    
    if callable(default_func):
        default_time = default_func()
        now = datetime.now(tz=timezone.utc)
        
        # Should be approximately 7 days in the future
        diff = default_time - now
        # diff.days is 6 if 6 days 23 hours...
        assert 6 <= diff.days <= 7


def test_user_default_group():
    """Test User default group is '普通用户'."""
    from db.db import User
    
    group_field = User._meta.fields_map['group']
    assert group_field.default == "普通用户"


def test_gp_record_default_source():
    """Test GPRecord default source is '签到'."""
    from db.db import GPRecord
    
    source_field = GPRecord._meta.fields_map['source']
    assert source_field.default == "签到"


# ============ Relationship Tests ============

def test_user_has_gp_records_relation():
    """Test User has GP_records reverse relation."""
    from db.db import User
    
    # Check that the relation is defined
    assert hasattr(User, 'GP_records')


def test_user_has_clients_relation():
    """Test User has clients reverse relation."""
    from db.db import User
    
    assert hasattr(User, 'clients')


def test_user_has_archive_histories_relation():
    """Test User has archive_histories reverse relation."""
    from db.db import User
    
    assert hasattr(User, 'archive_histories')


def test_user_has_previews_relation():
    """Test User has previews reverse relation."""
    from db.db import User
    
    assert hasattr(User, 'previews')


# ============ Database Functions Tests ============

@pytest.mark.asyncio
async def test_checkpoint_db():
    """Test checkpoint_db function runs without error."""
    from db.db import checkpoint_db
    
    with patch('db.db.aiosqlite.connect') as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        
        await checkpoint_db()
        
        mock_db.execute.assert_called_once_with("PRAGMA wal_checkpoint(FULL);")
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_init_db():
    """Test init_db function."""
    from db.db import init_db
    
    with patch('db.db.Tortoise.init', new_callable=AsyncMock) as mock_init, \
         patch('db.db.Tortoise.generate_schemas', new_callable=AsyncMock) as mock_schemas:
        
        await init_db()
        
        mock_init.assert_called_once()
        mock_schemas.assert_called_once()
