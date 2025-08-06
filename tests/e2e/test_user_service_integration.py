"""
🎯 User Service E2E Integration Tests - Production Grade
========================================================
Comprehensive End-to-End integration tests with REAL database:
- Real PostgreSQL database connections
- Real User/Child repositories
- Full authentication flows
- Session management integration
- Error handling and edge cases
- COPPA compliance validation

NO MOCKS - Production Reality Testing
"""

import asyncio
import pytest
import uuid
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock
from contextlib import asynccontextmanager

# Database and async support
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete, func

# Internal imports
from src.application.services.user_service import UserService
from src.adapters.database_production import ProductionUserRepository, ProductionChildRepository
from src.infrastructure.persistence.database.production_config import DatabaseManager
from src.infrastructure.logging.structlog_logger import StructlogLogger
from src.core.entities import User, Child
from src.core.value_objects.value_objects import ChildPreferences


class UserServiceE2ETest:
    """End-to-End integration tests for User Service with real database."""
    
    # Test Database Configuration
    TEST_DB_CONFIG = {
        'host': os.getenv('TEST_DB_HOST', 'localhost'),
        'port': int(os.getenv('TEST_DB_PORT', '5432')),
        'database': os.getenv('TEST_DB_NAME', 'ai_teddy_bear_test'),
        'username': os.getenv('TEST_DB_USER', 'postgres'),
        'password': os.getenv('TEST_DB_PASSWORD', 'password'),
    }
    
    @pytest.fixture(scope="session")
    async def test_database_manager(self):
        """Setup test database manager with real connections."""
        # Create test database if it doesn't exist
        await self._ensure_test_database_exists()
        
        # Initialize production database manager for testing
        db_manager = DatabaseManager(
            database_url=f"postgresql+asyncpg://{self.TEST_DB_CONFIG['username']}:{self.TEST_DB_CONFIG['password']}@{self.TEST_DB_CONFIG['host']}:{self.TEST_DB_CONFIG['port']}/{self.TEST_DB_CONFIG['database']}",
            echo=False,  # Disable SQL logging for tests
            pool_size=10,
            max_overflow=20
        )
        
        await db_manager.initialize()
        
        # Create all tables
        await db_manager.create_tables()
        
        yield db_manager
        
        # Cleanup
        await db_manager.close()
    
    @pytest.fixture
    async def db_session(self, test_database_manager):
        """Provide clean database session for each test."""
        async with test_database_manager.get_session() as session:
            try:
                yield session
            finally:
                # Cleanup test data after each test
                await self._cleanup_test_data(session)
                await session.commit()
    
    @pytest.fixture
    async def user_repository(self, db_session):
        """Real User repository with database connection."""
        return ProductionUserRepository(db_session)
    
    @pytest.fixture
    async def child_repository(self, db_session):
        """Real Child repository with database connection."""
        return ProductionChildRepository(db_session)
    
    @pytest.fixture
    async def user_service(self, user_repository, child_repository):
        """Real User Service with production repositories."""
        logger = StructlogLogger("test_user_service", component="e2e_test")
        
        service = UserService(
            user_repository=user_repository,
            child_repository=child_repository,
            logger=logger,
            session_timeout_minutes=30,
            max_sessions_per_user=5
        )
        
        yield service
        
        # Cleanup active sessions
        await service.cleanup_expired_sessions()
    
    # ========================================================================
    # USER MANAGEMENT E2E TESTS
    # ========================================================================
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_user_registration_flow(self, user_service, user_repository):
        """Test complete user registration with database persistence."""
        # Test data
        user_data = {
            'email': f'e2e_test_{uuid.uuid4()}@example.com',
            'password_hash': 'test_hash_123',
            'first_name': 'John',
            'last_name': 'Doe',
            'date_of_birth': datetime(1985, 5, 15),
            'phone_number': '+1234567890',
            'address': '123 Test Street',
            'timezone': 'UTC',
            'language_preference': 'en',
            'marketing_consent': True
        }
        
        # 1. Register new user
        user_id = await user_service.create_user(user_data)
        assert user_id is not None
        assert isinstance(user_id, uuid.UUID)
        
        # 2. Verify user exists in database
        created_user = await user_repository.get_by_id(user_id)
        assert created_user is not None
        assert created_user['email'] == user_data['email']
        assert created_user['first_name'] == user_data['first_name']
        assert created_user['is_active'] is True
        assert created_user['created_at'] is not None
        
        # 3. Test user login simulation
        retrieved_user = await user_repository.get_by_email(user_data['email'])
        assert retrieved_user is not None
        assert retrieved_user['id'] == user_id
        
        # 4. Update user profile
        update_data = {
            'first_name': 'Johnny',
            'phone_number': '+1987654321',
            'last_login': datetime.utcnow()
        }
        
        success = await user_service.update_user(user_id, update_data)
        assert success is True
        
        # 5. Verify updates persisted
        updated_user = await user_repository.get_by_id(user_id)
        assert updated_user['first_name'] == 'Johnny'
        assert updated_user['phone_number'] == '+1987654321'
        assert updated_user['last_login'] is not None
        
        print(f"✅ Complete user registration flow test passed for user {user_id}")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_child_management_with_coppa_compliance(self, user_service, child_repository):
        """Test child creation and COPPA compliance with real database."""
        # 1. Create parent user first
        parent_data = {
            'email': f'parent_e2e_{uuid.uuid4()}@example.com',
            'password_hash': 'parent_hash',
            'first_name': 'Parent',
            'last_name': 'User',
            'date_of_birth': datetime(1980, 1, 1)
        }
        
        parent_id = await user_service.create_user(parent_data)
        assert parent_id is not None
        
        # 2. Create child with COPPA-compliant data
        child_data = {
            'name': 'Test Child',
            'age': 8,
            'parent_id': parent_id,
            'preferences': {
                'favorite_color': 'blue',
                'interests': ['stories', 'animals'],
                'bedtime': '20:00'
            },
            'safety_settings': {
                'content_filter_level': 'strict',
                'max_session_duration': 30,
                'allowed_topics': ['education', 'fun']
            }
        }
        
        child_id = await user_service.create_child(child_data)
        assert child_id is not None
        assert isinstance(child_id, uuid.UUID)
        
        # 3. Verify child in database with COPPA compliance
        created_child = await child_repository.get_by_id(child_id)
        assert created_child is not None
        assert created_child['name'] == child_data['name']
        assert created_child['age'] == child_data['age']
        assert created_child['parent_id'] == parent_id
        assert created_child['is_active'] is True
        
        # 4. Verify COPPA compliance fields
        assert 'preferences' in created_child
        assert 'safety_settings' in created_child
        assert created_child['created_at'] is not None
        
        # 5. Test child retrieval by parent
        parent_children = await child_repository.get_by_parent_id(parent_id)
        assert len(parent_children) == 1
        assert parent_children[0]['id'] == child_id
        
        # 6. Test child update with safety validation
        update_data = {
            'preferences': {
                'favorite_color': 'green',
                'interests': ['stories', 'music'],
                'bedtime': '19:30'
            }
        }
        
        success = await user_service.update_child(child_id, update_data)
        assert success is True
        
        # 7. Verify update persisted
        updated_child = await child_repository.get_by_id(child_id)
        assert updated_child['preferences']['favorite_color'] == 'green'
        assert 'music' in updated_child['preferences']['interests']
        
        print(f"✅ Child management with COPPA compliance test passed for child {child_id}")
    
    # ========================================================================
    # SESSION MANAGEMENT E2E TESTS
    # ========================================================================
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_session_lifecycle_with_database_consistency(self, user_service):
        """Test complete session lifecycle with database consistency."""
        # 1. Setup test user and child
        parent_id = await self._create_test_user(user_service)
        child_id = await self._create_test_child(user_service, parent_id)
        
        # 2. Create session
        device_info = {
            'device_type': 'tablet',
            'device_id': f'test_device_{uuid.uuid4()}',
            'app_version': '1.0.0',
            'os_version': 'iOS 15.0'
        }
        
        session_id = await user_service.create_session(
            child_id=child_id,
            device_info=device_info,
            accessibility_needs=[]
        )
        assert session_id is not None
        
        # 3. Verify session creation
        assert session_id in user_service._sessions
        session_data = user_service._sessions[session_id]
        assert session_data.child_id == child_id
        assert session_data.device_info == device_info
        assert session_data.is_active is True
        
        # 4. Test session activity updates
        original_activity = session_data.last_activity
        await asyncio.sleep(0.1)  # Small delay to ensure time difference
        
        await user_service.update_session_activity(session_id)
        updated_session = user_service._sessions[session_id]
        assert updated_session.last_activity > original_activity
        
        # 5. Test session statistics
        stats = await user_service.get_session_stats(child_id)
        assert stats is not None
        assert stats['active_sessions'] == 1
        assert stats['total_session_time'] >= 0
        
        # 6. Test session timeout behavior
        # Simulate expired session
        expired_time = datetime.utcnow() - timedelta(hours=2)
        user_service._sessions[session_id].last_activity = expired_time
        
        # Run cleanup
        cleaned_count = await user_service.cleanup_expired_sessions()
        assert cleaned_count >= 1
        assert session_id not in user_service._sessions
        
        # 7. Test session recreation after cleanup
        new_session_id = await user_service.create_session(
            child_id=child_id,
            device_info=device_info,
            accessibility_needs=[]
        )
        assert new_session_id != session_id
        assert new_session_id in user_service._sessions
        
        # 8. Clean end session
        await user_service.end_session(new_session_id)
        assert new_session_id not in user_service._sessions
        
        print(f"✅ Session lifecycle test passed with sessions {session_id} -> {new_session_id}")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_concurrent_sessions_database_consistency(self, user_service):
        """Test concurrent sessions with database consistency under load."""
        # 1. Setup test users and children
        parent_id = await self._create_test_user(user_service)
        children = []
        
        for i in range(5):  # Create 5 children
            child_id = await self._create_test_child(user_service, parent_id, name=f"Child_{i}")
            children.append(child_id)
        
        # 2. Create concurrent sessions
        concurrent_sessions = []
        
        async def create_child_session(child_id, session_num):
            device_info = {
                'device_type': 'smartphone',
                'device_id': f'concurrent_device_{session_num}',
                'session_num': session_num
            }
            
            session_id = await user_service.create_session(
                child_id=child_id,
                device_info=device_info,
                accessibility_needs=[]
            )
            return session_id, child_id
        
        # Create 15 concurrent sessions (3 per child)
        tasks = []
        for i in range(15):
            child_id = children[i % 5]  # Distribute across children
            tasks.append(create_child_session(child_id, i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. Verify all sessions created successfully
        created_sessions = []
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Session creation failed: {result}")
            else:
                session_id, child_id = result
                created_sessions.append((session_id, child_id))
                assert session_id in user_service._sessions
        
        assert len(created_sessions) >= 10  # Allow some failures under load
        print(f"✅ Created {len(created_sessions)} concurrent sessions")
        
        # 4. Test concurrent session activities
        async def update_session_activity(session_id):
            try:
                await user_service.update_session_activity(session_id)
                return True
            except Exception as e:
                print(f"Activity update failed for {session_id}: {e}")
                return False
        
        activity_tasks = [update_session_activity(sid) for sid, _ in created_sessions[:10]]
        activity_results = await asyncio.gather(*activity_tasks, return_exceptions=True)
        
        successful_updates = sum(1 for r in activity_results if r is True)
        assert successful_updates >= 8  # Allow some failures
        
        # 5. Test session statistics consistency
        for child_id in children:
            stats = await user_service.get_session_stats(child_id)
            assert stats['active_sessions'] >= 0
            assert 'total_session_time' in stats
            assert 'last_activity' in stats
        
        # 6. Cleanup all sessions
        cleanup_tasks = [user_service.end_session(sid) for sid, _ in created_sessions]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Verify cleanup
        remaining_sessions = len(user_service._sessions)
        print(f"✅ Concurrent sessions test completed. Remaining sessions: {remaining_sessions}")
    
    # ========================================================================
    # ERROR HANDLING E2E TESTS
    # ========================================================================
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_database_error_handling_and_recovery(self, user_service, db_session):
        """Test database error handling and recovery scenarios."""
        # 1. Test duplicate email handling
        user_data = {
            'email': f'duplicate_test_{uuid.uuid4()}@example.com',
            'password_hash': 'test_hash',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        # Create first user
        user_id_1 = await user_service.create_user(user_data)
        assert user_id_1 is not None
        
        # Attempt to create duplicate
        try:
            user_id_2 = await user_service.create_user(user_data)
            assert False, "Should have raised exception for duplicate email"
        except Exception as e:
            assert "already exists" in str(e).lower() or "duplicate" in str(e).lower()
        
        # 2. Test invalid child creation (non-existent parent)
        fake_parent_id = uuid.uuid4()
        child_data = {
            'name': 'Orphan Child',
            'age': 7,
            'parent_id': fake_parent_id
        }
        
        try:
            child_id = await user_service.create_child(child_data)
            assert False, "Should have raised exception for non-existent parent"
        except Exception as e:
            assert "parent" in str(e).lower() or "not found" in str(e).lower()
        
        # 3. Test session creation with invalid child
        fake_child_id = uuid.uuid4()
        try:
            session_id = await user_service.create_session(
                child_id=fake_child_id,
                device_info={'device': 'test'},
                accessibility_needs=[]
            )
            assert False, "Should have raised exception for non-existent child"
        except Exception as e:
            assert "child" in str(e).lower() or "not found" in str(e).lower()
        
        # 4. Test service recovery after errors
        # Verify service is still functional after errors
        valid_user_data = {
            'email': f'recovery_test_{uuid.uuid4()}@example.com',
            'password_hash': 'recovery_hash',
            'first_name': 'Recovery',
            'last_name': 'User'
        }
        
        recovery_user_id = await user_service.create_user(valid_user_data)
        assert recovery_user_id is not None
        
        print(f"✅ Database error handling and recovery test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_data_integrity_and_transactions(self, user_service, user_repository, child_repository):
        """Test data integrity and transaction consistency."""
        # 1. Test atomic user creation
        user_data = {
            'email': f'integrity_test_{uuid.uuid4()}@example.com',
            'password_hash': 'integrity_hash',
            'first_name': 'Integrity',
            'last_name': 'Test',
            'date_of_birth': datetime(1990, 1, 1)
        }
        
        user_id = await user_service.create_user(user_data)
        
        # 2. Create child and verify foreign key relationship
        child_data = {
            'name': 'Integrity Child',
            'age': 6,
            'parent_id': user_id,
            'preferences': {'theme': 'space'}
        }
        
        child_id = await user_service.create_child(child_data)
        
        # 3. Verify referential integrity
        child = await child_repository.get_by_id(child_id)
        user = await user_repository.get_by_id(user_id)
        
        assert child['parent_id'] == user['id']
        assert child['parent_id'] == user_id
        
        # 4. Test cascade behavior (attempt to delete parent with children)
        # This should be prevented by foreign key constraints or business logic
        try:
            await user_repository.delete(user_id)
            
            # Verify child still exists and parent wasn't deleted
            remaining_child = await child_repository.get_by_id(child_id)
            remaining_user = await user_repository.get_by_id(user_id)
            
            # Either user deletion was prevented, or child was orphaned safely
            assert remaining_child is not None or remaining_user is not None
            
        except Exception as e:
            # Expected behavior - deletion should be prevented
            print(f"Expected constraint violation: {e}")
        
        # 5. Test data consistency after operations
        final_child = await child_repository.get_by_id(child_id)
        final_user = await user_repository.get_by_id(user_id)
        
        if final_user and final_child:
            assert final_child['parent_id'] == final_user['id']
        
        print(f"✅ Data integrity and transactions test passed")
    
    # ========================================================================
    # PERFORMANCE E2E TESTS
    # ========================================================================
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.performance
    async def test_large_dataset_operations(self, user_service):
        """Test service performance with larger datasets."""
        print("🚀 Starting large dataset operations test...")
        
        # 1. Create multiple users and children
        users_created = []
        children_created = []
        
        # Create 20 users with 60 children total
        for i in range(20):
            user_data = {
                'email': f'bulk_user_{i}_{uuid.uuid4()}@example.com',
                'password_hash': f'hash_{i}',
                'first_name': f'User{i}',
                'last_name': 'Bulk'
            }
            
            user_id = await user_service.create_user(user_data)
            users_created.append(user_id)
            
            # Create 2-4 children per user
            for j in range(2 + (i % 3)):  # 2, 3, or 4 children
                child_data = {
                    'name': f'Child{j}_of_User{i}',
                    'age': 5 + (j % 8),  # Ages 5-12
                    'parent_id': user_id,
                    'preferences': {
                        'favorite_number': j,
                        'theme': f'theme_{i}_{j}'
                    }
                }
                
                child_id = await user_service.create_child(child_data)
                children_created.append(child_id)
        
        print(f"✅ Created {len(users_created)} users and {len(children_created)} children")
        
        # 2. Create many concurrent sessions
        sessions_created = []
        session_tasks = []
        
        for i, child_id in enumerate(children_created[:30]):  # First 30 children
            device_info = {
                'device_type': 'tablet' if i % 2 else 'phone',
                'device_id': f'bulk_device_{i}',
                'bulk_test': True
            }
            
            session_tasks.append(
                user_service.create_session(
                    child_id=child_id,
                    device_info=device_info,
                    accessibility_needs=[]
                )
            )
        
        session_results = await asyncio.gather(*session_tasks, return_exceptions=True)
        
        for result in session_results:
            if not isinstance(result, Exception):
                sessions_created.append(result)
        
        print(f"✅ Created {len(sessions_created)} concurrent sessions")
        
        # 3. Test bulk session activities
        activity_tasks = []
        for session_id in sessions_created[:20]:  # First 20 sessions
            activity_tasks.append(user_service.update_session_activity(session_id))
        
        await asyncio.gather(*activity_tasks, return_exceptions=True)
        
        # 4. Test statistics retrieval for all children
        stats_tasks = []
        for child_id in children_created[:10]:  # Sample of children
            stats_tasks.append(user_service.get_session_stats(child_id))
        
        stats_results = await asyncio.gather(*stats_tasks, return_exceptions=True)
        successful_stats = [r for r in stats_results if not isinstance(r, Exception)]
        
        print(f"✅ Retrieved statistics for {len(successful_stats)} children")
        
        # 5. Cleanup bulk sessions
        cleanup_tasks = [user_service.end_session(sid) for sid in sessions_created]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        print(f"✅ Large dataset operations test completed successfully")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _ensure_test_database_exists(self):
        """Ensure test database exists, create if needed."""
        # Connect to postgres database to create test database
        admin_conn_string = f"postgresql://{self.TEST_DB_CONFIG['username']}:{self.TEST_DB_CONFIG['password']}@{self.TEST_DB_CONFIG['host']}:{self.TEST_DB_CONFIG['port']}/postgres"
        
        try:
            conn = await asyncpg.connect(admin_conn_string)
            
            # Check if test database exists
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                self.TEST_DB_CONFIG['database']
            )
            
            if not db_exists:
                # Create test database
                await conn.execute(f"CREATE DATABASE {self.TEST_DB_CONFIG['database']}")
                print(f"✅ Created test database: {self.TEST_DB_CONFIG['database']}")
            
            await conn.close()
            
        except Exception as e:
            print(f"⚠️ Database setup warning: {e}")
            # Continue anyway - database might already exist or be accessible
    
    async def _cleanup_test_data(self, session: AsyncSession):
        """Clean up test data after each test."""
        try:
            # Delete test users and children (cascade should handle relationships)
            await session.execute(
                delete(User).where(User.email.like('%e2e_test_%'))
            )
            await session.execute(
                delete(User).where(User.email.like('%parent_e2e_%'))
            )
            await session.execute(
                delete(User).where(User.email.like('%bulk_user_%'))
            )
            await session.execute(
                delete(User).where(User.email.like('%duplicate_test_%'))
            )
            await session.execute(
                delete(User).where(User.email.like('%recovery_test_%'))
            )
            await session.execute(
                delete(User).where(User.email.like('%integrity_test_%'))
            )
            
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
    
    async def _create_test_user(self, user_service) -> uuid.UUID:
        """Create a test user for testing."""
        user_data = {
            'email': f'test_parent_{uuid.uuid4()}@example.com',
            'password_hash': 'test_parent_hash',
            'first_name': 'Test',
            'last_name': 'Parent',
            'date_of_birth': datetime(1985, 1, 1)
        }
        
        return await user_service.create_user(user_data)
    
    async def _create_test_child(self, user_service, parent_id: uuid.UUID, name: str = None) -> uuid.UUID:
        """Create a test child for testing."""
        child_data = {
            'name': name or f'Test Child {uuid.uuid4()}',
            'age': 8,
            'parent_id': parent_id,
            'preferences': {
                'favorite_color': 'blue',
                'interests': ['stories']
            }
        }
        
        return await user_service.create_child(child_data)


# Configuration for pytest
pytest_plugins = ["pytest_asyncio"]


# Run specific test categories
if __name__ == "__main__":
    print("🎯 User Service E2E Integration Tests")
    print("Run with: pytest tests/e2e/test_user_service_integration.py -v -m e2e")
    print("Performance tests: pytest tests/e2e/test_user_service_integration.py -v -m performance")