"""
Tests for database production adapter - real database operations
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.adapters.database_production import (
    ProductionDatabaseAdapter,
    ProductionUserRepository,
    ProductionChildRepository,
    ProductionConversationRepository,
    ProductionMessageRepository,
    ProductionEventRepository,
    ProductionConsentRepository,
    DatabaseConnectionManager,
    get_database_adapter,
    _validate_uuid,
    _validate_age,
    _validate_email
)
from src.interfaces.exceptions import DatabaseError, ValidationError


class TestValidationFunctions:
    def test_validate_uuid_valid(self):
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = _validate_uuid(valid_uuid, "test_id")
        assert isinstance(result, uuid.UUID)
        assert str(result) == valid_uuid

    def test_validate_uuid_invalid_format(self):
        with pytest.raises(ValidationError) as exc:
            _validate_uuid("invalid-uuid", "test_id")
        assert "Invalid UUID format" in str(exc.value)

    def test_validate_uuid_none(self):
        with pytest.raises(ValidationError) as exc:
            _validate_uuid(None, "test_id")
        assert "cannot be None" in str(exc.value)

    def test_validate_age_valid(self):
        assert _validate_age(5) == 5
        assert _validate_age(13) == 13

    def test_validate_age_too_young(self):
        with pytest.raises(ValidationError) as exc:
            _validate_age(2)
        assert "COPPA compliance" in str(exc.value)

    def test_validate_age_too_old(self):
        with pytest.raises(ValidationError) as exc:
            _validate_age(15)
        assert "COPPA compliance" in str(exc.value)

    def test_validate_email_valid(self):
        result = _validate_email("test@example.com")
        assert result == "test@example.com"

    def test_validate_email_invalid(self):
        with pytest.raises(ValidationError) as exc:
            _validate_email("invalid-email")
        assert "Invalid email format" in str(exc.value)


class TestDatabaseConnectionManager:
    @pytest.fixture
    def mock_config(self):
        config = Mock()
        config.DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test"
        config.DATABASE_POOL_SIZE = 5
        config.DATABASE_MAX_OVERFLOW = 10
        config.DATABASE_POOL_TIMEOUT = 30
        config.DEBUG = False
        return config

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_config):
        with patch('src.adapters.database_production.create_async_engine') as mock_async_engine:
            with patch('src.adapters.database_production.create_engine') as mock_sync_engine:
                with patch('src.adapters.database_production.async_sessionmaker') as mock_async_session:
                    with patch('src.adapters.database_production.sessionmaker') as mock_sync_session:
                        manager = DatabaseConnectionManager(mock_config)
                        
                        await manager.initialize()
                        
                        assert manager._initialized is True
                        mock_async_engine.assert_called_once()
                        mock_sync_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_config):
        manager = DatabaseConnectionManager(mock_config)
        
        with patch.object(manager, 'get_async_session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.execute.return_value.scalar.return_value = 1
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            result = await manager.health_check()
            
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_config):
        manager = DatabaseConnectionManager(mock_config)
        
        with patch.object(manager, 'get_async_session') as mock_session:
            mock_session.side_effect = Exception("Connection failed")
            
            result = await manager.health_check()
            
            assert result is False


class TestProductionUserRepository:
    @pytest.fixture
    def user_repo(self):
        return ProductionUserRepository()

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_repo, mock_session):
        with patch.object(user_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            # Mock existing user check
            mock_session.execute.return_value.scalar_one_or_none.return_value = None
            
            user = await user_repo.create_user(
                email="test@example.com",
                password_hash="hashed_password",
                role="parent"
            )
            
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, user_repo, mock_session):
        with patch.object(user_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            # Mock existing user
            existing_user = Mock()
            mock_session.execute.return_value.scalar_one_or_none.return_value = existing_user
            
            with pytest.raises(ValidationError) as exc:
                await user_repo.create_user(
                    email="existing@example.com",
                    password_hash="hashed_password"
                )
            
            assert "already exists" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self, user_repo, mock_session):
        with patch.object(user_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            mock_user = Mock()
            mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user
            
            result = await user_repo.get_user_by_email("test@example.com")
            
            assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, user_repo, mock_session):
        with patch.object(user_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            mock_session.execute.return_value.scalar_one_or_none.return_value = None
            
            result = await user_repo.get_user_by_email("notfound@example.com")
            
            assert result is None


class TestProductionChildRepository:
    @pytest.fixture
    def child_repo(self):
        return ProductionChildRepository()

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_child_success(self, child_repo, mock_session):
        with patch.object(child_repo.connection_manager, 'get_async_session') as mock_get_session:
            with patch.object(child_repo, '_validate_foreign_key') as mock_validate_fk:
                mock_get_session.return_value.__aenter__.return_value = mock_session
                mock_validate_fk.return_value = None
                
                child = await child_repo.create_child(
                    name="Ahmed",
                    age=8,
                    parent_id="550e8400-e29b-41d4-a716-446655440000"
                )
                
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_child_invalid_age(self, child_repo):
        with pytest.raises(ValidationError) as exc:
            await child_repo.create_child(
                name="Baby",
                age=2,  # Too young
                parent_id="550e8400-e29b-41d4-a716-446655440000"
            )
        
        assert "COPPA compliance" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_children_by_parent(self, child_repo, mock_session):
        with patch.object(child_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            mock_children = [Mock(), Mock()]
            mock_session.execute.return_value.scalars.return_value.all.return_value = mock_children
            
            result = await child_repo.get_children_by_parent("550e8400-e29b-41d4-a716-446655440000")
            
            assert len(result) == 2


class TestProductionConversationRepository:
    @pytest.fixture
    def conv_repo(self):
        return ProductionConversationRepository()

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, conv_repo):
        with patch.object(conv_repo.connection_manager, 'get_async_session') as mock_get_session:
            with patch.object(conv_repo, '_validate_foreign_key') as mock_validate_fk:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                mock_validate_fk.return_value = None
                
                conversation = await conv_repo.create_conversation(
                    child_id="550e8400-e29b-41d4-a716-446655440000",
                    title="Chat Session"
                )
                
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversations_by_child(self, conv_repo):
        with patch.object(conv_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            mock_conversations = [Mock(), Mock()]
            mock_session.execute.return_value.scalars.return_value.all.return_value = mock_conversations
            
            result = await conv_repo.get_conversations_by_child(
                "550e8400-e29b-41d4-a716-446655440000",
                limit=10
            )
            
            assert len(result) == 2


class TestProductionMessageRepository:
    @pytest.fixture
    def msg_repo(self):
        return ProductionMessageRepository()

    @pytest.mark.asyncio
    async def test_create_message_success(self, msg_repo):
        with patch.object(msg_repo.connection_manager, 'get_async_session') as mock_get_session:
            with patch.object(msg_repo, '_validate_foreign_key') as mock_validate_fk:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                mock_validate_fk.return_value = None
                
                message = await msg_repo.create_message(
                    conversation_id="550e8400-e29b-41d4-a716-446655440000",
                    child_id="550e8400-e29b-41d4-a716-446655440001",
                    content="Hello AI",
                    role="user",
                    safety_score=1.0
                )
                
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_message_invalid_safety_score(self, msg_repo):
        with pytest.raises(ValidationError) as exc:
            await msg_repo.create_message(
                conversation_id="550e8400-e29b-41d4-a716-446655440000",
                child_id="550e8400-e29b-41d4-a716-446655440001",
                content="Hello",
                role="user",
                safety_score=1.5  # Invalid score
            )
        
        assert "safety_score must be between 0.0 and 1.0" in str(exc.value)


class TestProductionEventRepository:
    @pytest.fixture
    def event_repo(self):
        return ProductionEventRepository()

    @pytest.mark.asyncio
    async def test_log_event_success(self, event_repo):
        with patch.object(event_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            event_data = {
                "event_type": "safety_violation",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "description": "Content filtered"
            }
            
            event = await event_repo.log_event(event_data)
            
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_event_missing_fields(self, event_repo):
        with pytest.raises(ValidationError) as exc:
            await event_repo.log_event({"event_type": "test"})  # Missing required fields
        
        assert "Missing required field" in str(exc.value)


class TestProductionConsentRepository:
    @pytest.fixture
    def consent_repo(self):
        return ProductionConsentRepository()

    @pytest.mark.asyncio
    async def test_create_consent_success(self, consent_repo):
        with patch.object(consent_repo.connection_manager, 'get_async_session') as mock_get_session:
            with patch.object(consent_repo, '_validate_foreign_key') as mock_validate_fk:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                mock_validate_fk.return_value = None
                
                consent = await consent_repo.create_consent(
                    parent_email="parent@example.com",
                    child_id="550e8400-e29b-41d4-a716-446655440000",
                    consent_timestamp=datetime.now(),
                    ip_address="192.168.1.1"
                )
                
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_consent_by_child(self, consent_repo):
        with patch.object(consent_repo.connection_manager, 'get_async_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            mock_consent = Mock()
            mock_session.execute.return_value.scalar_one_or_none.return_value = mock_consent
            
            result = await consent_repo.get_consent_by_child("550e8400-e29b-41d4-a716-446655440000")
            
            assert result == mock_consent


class TestProductionDatabaseAdapter:
    @pytest.fixture
    def db_adapter(self):
        return ProductionDatabaseAdapter()

    @pytest.mark.asyncio
    async def test_initialize_success(self, db_adapter):
        with patch.object(db_adapter.connection_manager, 'initialize') as mock_init:
            await db_adapter.initialize()
            
            mock_init.assert_called_once()
            assert db_adapter._initialized is True

    @pytest.mark.asyncio
    async def test_health_check(self, db_adapter):
        with patch.object(db_adapter.connection_manager, 'health_check') as mock_health:
            mock_health.return_value = True
            
            result = await db_adapter.health_check()
            
            assert result is True

    def test_get_repositories(self, db_adapter):
        assert isinstance(db_adapter.get_user_repository(), ProductionUserRepository)
        assert isinstance(db_adapter.get_child_repository(), ProductionChildRepository)
        assert isinstance(db_adapter.get_conversation_repository(), ProductionConversationRepository)
        assert isinstance(db_adapter.get_message_repository(), ProductionMessageRepository)
        assert isinstance(db_adapter.get_event_repository(), ProductionEventRepository)
        assert isinstance(db_adapter.get_consent_repository(), ProductionConsentRepository)


class TestDatabaseAdapterFactory:
    @pytest.mark.asyncio
    async def test_get_database_adapter_singleton(self):
        with patch('src.adapters.database_production.initialize_production_database') as mock_init:
            mock_adapter = Mock()
            mock_init.return_value = mock_adapter
            
            # First call
            adapter1 = await get_database_adapter()
            # Second call
            adapter2 = await get_database_adapter()
            
            # Should return same instance
            assert adapter1 == adapter2
            mock_init.assert_called_once()  # Should only initialize once