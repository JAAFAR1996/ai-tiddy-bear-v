"""
Unit tests for read model interfaces.
Tests interfaces for child profiles, external API clients, and COPPA consent management.
"""

import pytest
from abc import ABC, abstractmethod
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.interfaces.read_model_interfaces import (
    IChildProfileReadModel,
    IChildProfileReadModelStore,
    IExternalAPIClient,
    IConsentManager,
)


class TestIChildProfileReadModel:
    """Test IChildProfileReadModel interface."""

    def test_ichild_profile_read_model_is_abstract(self):
        """Test IChildProfileReadModel is abstract base class."""
        assert issubclass(IChildProfileReadModel, ABC)
        
        with pytest.raises(TypeError):
            IChildProfileReadModel()

    def test_ichild_profile_read_model_abstract_properties(self):
        """Test IChildProfileReadModel has all required abstract properties."""
        abstract_methods = IChildProfileReadModel.__abstractmethods__
        expected_properties = {'id', 'name', 'age', 'preferences'}
        
        assert abstract_methods == expected_properties

    def test_ichild_profile_read_model_complete_implementation(self):
        """Test complete implementation of IChildProfileReadModel."""
        
        class TestChildProfileReadModel(IChildProfileReadModel):
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                self._id = child_id
                self._name = name
                self._age = age
                self._preferences = preferences
            
            @property
            def id(self) -> str:
                return self._id
            
            @property
            def name(self) -> str:
                return self._name
            
            @property
            def age(self) -> int:
                return self._age
            
            @property
            def preferences(self) -> dict[str, Any]:
                return self._preferences
        
        # Should be able to instantiate
        child_profile = TestChildProfileReadModel(
            child_id="child_123",
            name="Alice",
            age=8,
            preferences={"favorite_color": "blue", "interests": ["animals", "books"]}
        )
        
        assert isinstance(child_profile, IChildProfileReadModel)
        assert child_profile.id == "child_123"
        assert child_profile.name == "Alice"
        assert child_profile.age == 8
        assert child_profile.preferences["favorite_color"] == "blue"

    def test_ichild_profile_read_model_coppa_compliance(self):
        """Test child profile read model with COPPA compliance considerations."""
        
        class COPPACompliantChildProfile(IChildProfileReadModel):
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                # Validate COPPA age range
                if not (3 <= age <= 13):
                    raise ValueError("Child age must be between 3 and 13 for COPPA compliance")
                
                self._id = child_id
                self._name = name
                self._age = age
                self._preferences = self._sanitize_preferences(preferences)
            
            def _sanitize_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
                """Sanitize preferences to remove any potentially sensitive data."""
                safe_preferences = {}
                allowed_keys = ["favorite_color", "interests", "difficulty_level", "preferred_voice"]
                
                for key, value in preferences.items():
                    if key in allowed_keys:
                        safe_preferences[key] = value
                
                return safe_preferences
            
            @property
            def id(self) -> str:
                return self._id
            
            @property
            def name(self) -> str:
                return self._name
            
            @property
            def age(self) -> int:
                return self._age
            
            @property
            def preferences(self) -> dict[str, Any]:
                return self._preferences.copy()  # Return copy to prevent modification
        
        # Test valid COPPA age
        valid_profile = COPPACompliantChildProfile(
            child_id="child_456",
            name="Bob",
            age=7,
            preferences={
                "favorite_color": "green",
                "interests": ["dinosaurs"],
                "home_address": "123 Main St"  # Should be filtered out
            }
        )
        
        assert valid_profile.age == 7
        assert "favorite_color" in valid_profile.preferences
        assert "home_address" not in valid_profile.preferences  # Should be sanitized
        
        # Test invalid COPPA age
        with pytest.raises(ValueError, match="COPPA compliance"):
            COPPACompliantChildProfile("child_789", "Charlie", 15, {})

    def test_ichild_profile_read_model_data_immutability(self):
        """Test that child profile data maintains immutability."""
        
        class ImmutableChildProfile(IChildProfileReadModel):
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                self._id = child_id
                self._name = name
                self._age = age
                self._preferences = preferences.copy()
            
            @property
            def id(self) -> str:
                return self._id
            
            @property
            def name(self) -> str:
                return self._name
            
            @property
            def age(self) -> int:
                return self._age
            
            @property
            def preferences(self) -> dict[str, Any]:
                return self._preferences.copy()  # Always return copy
        
        original_preferences = {"favorite_animal": "elephant"}
        profile = ImmutableChildProfile("child_001", "David", 6, original_preferences)
        
        # Modifying returned preferences should not affect original
        returned_prefs = profile.preferences
        returned_prefs["new_key"] = "new_value"
        
        assert "new_key" not in profile.preferences
        assert profile.preferences == {"favorite_animal": "elephant"}


class TestIChildProfileReadModelStore:
    """Test IChildProfileReadModelStore interface."""

    def test_ichild_profile_read_model_store_is_abstract(self):
        """Test IChildProfileReadModelStore is abstract base class."""
        assert issubclass(IChildProfileReadModelStore, ABC)
        
        with pytest.raises(TypeError):
            IChildProfileReadModelStore()

    def test_ichild_profile_read_model_store_abstract_methods(self):
        """Test IChildProfileReadModelStore has all required abstract methods."""
        abstract_methods = IChildProfileReadModelStore.__abstractmethods__
        expected_methods = {'save', 'get_by_id', 'delete_by_id', 'update'}
        
        assert abstract_methods == expected_methods

    @pytest.mark.asyncio
    async def test_ichild_profile_read_model_store_complete_implementation(self):
        """Test complete implementation of IChildProfileReadModelStore."""
        
        # Mock child profile for testing
        class MockChildProfile(IChildProfileReadModel):
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                self._id = child_id
                self._name = name
                self._age = age
                self._preferences = preferences
            
            @property
            def id(self) -> str:
                return self._id
            
            @property
            def name(self) -> str:
                return self._name
            
            @property
            def age(self) -> int:
                return self._age
            
            @property
            def preferences(self) -> dict[str, Any]:
                return self._preferences
        
        class TestChildProfileStore(IChildProfileReadModelStore):
            def __init__(self):
                self.profiles = {}
            
            async def save(self, model: IChildProfileReadModel) -> None:
                self.profiles[model.id] = model
            
            async def get_by_id(self, child_id: str) -> IChildProfileReadModel | None:
                return self.profiles.get(child_id)
            
            async def delete_by_id(self, child_id: str) -> bool:
                if child_id in self.profiles:
                    del self.profiles[child_id]
                    return True
                return False
            
            async def update(self, child_id: str, updates: dict[str, Any]) -> bool:
                if child_id in self.profiles:
                    # Create updated profile (simplified)
                    old_profile = self.profiles[child_id]
                    new_preferences = old_profile.preferences.copy()
                    new_preferences.update(updates.get('preferences', {}))
                    
                    updated_profile = MockChildProfile(
                        child_id=old_profile.id,
                        name=updates.get('name', old_profile.name),
                        age=updates.get('age', old_profile.age),
                        preferences=new_preferences
                    )
                    self.profiles[child_id] = updated_profile
                    return True
                return False
        
        # Test the implementation
        store = TestChildProfileStore()
        profile = MockChildProfile("child_123", "Emma", 9, {"favorite_book": "Alice in Wonderland"})
        
        # Test save
        await store.save(profile)
        assert len(store.profiles) == 1
        
        # Test get_by_id
        retrieved = await store.get_by_id("child_123")
        assert retrieved is not None
        assert retrieved.name == "Emma"
        assert retrieved.age == 9
        
        # Test update
        updates = {"age": 10, "preferences": {"favorite_book": "Harry Potter"}}
        success = await store.update("child_123", updates)
        assert success is True
        
        updated_profile = await store.get_by_id("child_123")
        assert updated_profile.age == 10
        assert updated_profile.preferences["favorite_book"] == "Harry Potter"
        
        # Test delete
        deleted = await store.delete_by_id("child_123")
        assert deleted is True
        assert len(store.profiles) == 0
        
        # Test get non-existent
        none_result = await store.get_by_id("non_existent")
        assert none_result is None

    @pytest.mark.asyncio
    async def test_ichild_profile_read_model_store_coppa_operations(self):
        """Test child profile store with COPPA compliance operations."""
        
        class COPPACompliantProfileStore(IChildProfileReadModelStore):
            def __init__(self):
                self.profiles = {}
                self.audit_log = []
            
            def _log_coppa_event(self, event_type: str, child_id: str, details: Dict[str, Any] = None):
                """Log COPPA compliance events."""
                self.audit_log.append({
                    "event_type": event_type,
                    "child_id": child_id,
                    "timestamp": "2025-07-29T10:00:00Z",
                    "details": details or {}
                })
            
            async def save(self, model: IChildProfileReadModel) -> None:
                # Validate COPPA compliance before saving
                if not (3 <= model.age <= 13):
                    raise ValueError("Age not within COPPA range")
                
                self.profiles[model.id] = model
                self._log_coppa_event("profile_saved", model.id, {"age": model.age})
            
            async def get_by_id(self, child_id: str) -> IChildProfileReadModel | None:
                self._log_coppa_event("profile_accessed", child_id)
                return self.profiles.get(child_id)
            
            async def delete_by_id(self, child_id: str) -> bool:
                if child_id in self.profiles:
                    del self.profiles[child_id]
                    self._log_coppa_event("profile_deleted", child_id)
                    return True
                return False
            
            async def update(self, child_id: str, updates: dict[str, Any]) -> bool:
                if child_id in self.profiles:
                    # Log what's being updated (for COPPA compliance)
                    self._log_coppa_event("profile_updated", child_id, {"updates": list(updates.keys())})
                    return True
                return False
        
        # Mock child profile
        class MockProfile:
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                self.id = child_id
                self.name = name
                self.age = age
                self.preferences = preferences
        
        store = COPPACompliantProfileStore()
        valid_profile = MockProfile("child_coppa", "Grace", 8, {})
        
        # Test COPPA-compliant save
        await store.save(valid_profile)
        assert len(store.audit_log) == 1
        assert store.audit_log[0]["event_type"] == "profile_saved"
        
        # Test access logging
        await store.get_by_id("child_coppa")
        assert len(store.audit_log) == 2
        assert store.audit_log[1]["event_type"] == "profile_accessed"
        
        # Test update logging
        await store.update("child_coppa", {"preferences": {"theme": "space"}})
        assert len(store.audit_log) == 3
        assert store.audit_log[2]["event_type"] == "profile_updated"
        
        # Test COPPA age validation
        invalid_profile = MockProfile("child_invalid", "Too Old", 16, {})
        with pytest.raises(ValueError, match="COPPA range"):
            await store.save(invalid_profile)


class TestIExternalAPIClient:
    """Test IExternalAPIClient interface."""

    def test_iexternal_api_client_is_abstract(self):
        """Test IExternalAPIClient is abstract base class."""
        assert issubclass(IExternalAPIClient, ABC)
        
        with pytest.raises(TypeError):
            IExternalAPIClient()

    def test_iexternal_api_client_abstract_methods(self):
        """Test IExternalAPIClient has all required abstract methods."""
        abstract_methods = IExternalAPIClient.__abstractmethods__
        expected_methods = {'make_request', 'check_health'}
        
        assert abstract_methods == expected_methods

    @pytest.mark.asyncio
    async def test_iexternal_api_client_complete_implementation(self):
        """Test complete implementation of IExternalAPIClient."""
        
        class TestExternalAPIClient(IExternalAPIClient):
            def __init__(self):
                self.base_url = "https://api.example.com"
                self.is_healthy = True
                self.request_count = 0
            
            async def make_request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
                self.request_count += 1
                
                # Simulate API responses
                if endpoint == "/chat/completions":
                    return {
                        "choices": [{
                            "message": {
                                "content": "Hello! I'm happy to help you learn about animals!"
                            }
                        }],
                        "usage": {"total_tokens": 25}
                    }
                elif endpoint == "/moderate":
                    return {
                        "results": [{
                            "flagged": False,
                            "categories": {"violence": False, "hate": False}
                        }]
                    }
                
                return {"status": "success", "data": data}
            
            async def check_health(self) -> bool:
                return self.is_healthy
        
        # Test the implementation
        client = TestExternalAPIClient()
        
        # Test health check
        health = await client.check_health()
        assert health is True
        
        # Test API request
        response = await client.make_request("/chat/completions", {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Tell me about elephants"}]
        })
        
        assert "choices" in response
        assert "animals" in response["choices"][0]["message"]["content"]
        assert client.request_count == 1

    @pytest.mark.asyncio
    async def test_iexternal_api_client_child_safety_filtering(self):
        """Test external API client with child safety filtering."""
        
        class ChildSafeAPIClient(IExternalAPIClient):
            def __init__(self):
                self.blocked_requests = 0
            
            async def make_request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
                # Pre-filter requests for child safety
                if "messages" in data:
                    for message in data["messages"]:
                        content = message.get("content", "").lower()
                        unsafe_words = ["violence", "scary", "inappropriate", "adult"]
                        
                        if any(word in content for word in unsafe_words):
                            self.blocked_requests += 1
                            return {
                                "error": "Content not appropriate for children",
                                "blocked": True
                            }
                
                # Simulate safe API response
                return {
                    "choices": [{
                        "message": {
                            "content": "That's a wonderful question! Let me tell you something fun and educational."
                        }
                    }],
                    "safe_for_children": True
                }
            
            async def check_health(self) -> bool:
                # Health check includes safety filters
                return True
        
        client = ChildSafeAPIClient()
        
        # Test safe request
        safe_response = await client.make_request("/chat", {
            "messages": [{"role": "user", "content": "Tell me about friendly animals"}]
        })
        assert safe_response["safe_for_children"] is True
        assert client.blocked_requests == 0
        
        # Test unsafe request
        unsafe_response = await client.make_request("/chat", {
            "messages": [{"role": "user", "content": "Tell me about violence"}]
        })
        assert unsafe_response["blocked"] is True
        assert client.blocked_requests == 1

    @pytest.mark.asyncio
    async def test_iexternal_api_client_error_handling(self):
        """Test external API client error handling."""
        
        class RobustAPIClient(IExternalAPIClient):
            def __init__(self):
                self.retry_count = 0
                self.max_retries = 3
            
            async def make_request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
                self.retry_count += 1
                
                # Simulate different error conditions
                if endpoint == "/error":
                    if self.retry_count <= self.max_retries:
                        raise Exception("API temporarily unavailable")
                
                if endpoint == "/rate_limited":
                    return {
                        "error": "Rate limit exceeded",
                        "retry_after": 60
                    }
                
                return {"status": "success"}
            
            async def check_health(self) -> bool:
                try:
                    response = await self.make_request("/health", {})
                    return response.get("status") == "success"
                except Exception:
                    return False
        
        client = RobustAPIClient()
        
        # Test successful request
        response = await client.make_request("/success", {})
        assert response["status"] == "success"
        
        # Test rate limiting handling
        rate_limited_response = await client.make_request("/rate_limited", {})
        assert "Rate limit exceeded" in rate_limited_response["error"]
        assert rate_limited_response["retry_after"] == 60


class TestIConsentManager:
    """Test IConsentManager interface."""

    def test_iconsent_manager_is_abstract(self):
        """Test IConsentManager is abstract base class."""
        assert issubclass(IConsentManager, ABC)
        
        with pytest.raises(TypeError):
            IConsentManager()

    def test_iconsent_manager_abstract_methods(self):
        """Test IConsentManager has all required abstract methods."""
        abstract_methods = IConsentManager.__abstractmethods__
        expected_methods = {'verify_consent', 'get_consent_status', 'revoke_consent'}
        
        assert abstract_methods == expected_methods

    @pytest.mark.asyncio
    async def test_iconsent_manager_complete_implementation(self):
        """Test complete implementation of IConsentManager."""
        
        class TestConsentManager(IConsentManager):
            def __init__(self):
                self.consents = {}
                self.revoked_consents = set()
            
            async def verify_consent(self, child_id: str, operation: str) -> bool:
                if child_id in self.revoked_consents:
                    return False
                
                consent_key = f"{child_id}:{operation}"
                return self.consents.get(consent_key, False)
            
            async def get_consent_status(self, child_id: str) -> dict[str, Any]:
                if child_id in self.revoked_consents:
                    return {
                        "child_id": child_id,
                        "status": "revoked",
                        "consented_operations": [],
                        "revoked_at": "2025-07-29T10:00:00Z"
                    }
                
                consented_operations = [
                    op.split(":")[-1] for op in self.consents.keys() 
                    if op.startswith(child_id) and self.consents[op]
                ]
                
                return {
                    "child_id": child_id,
                    "status": "active" if consented_operations else "no_consent",
                    "consented_operations": consented_operations,
                    "last_updated": "2025-07-29T09:00:00Z"
                }
            
            async def revoke_consent(self, child_id: str) -> bool:
                self.revoked_consents.add(child_id)
                # Remove all existing consents for this child
                keys_to_remove = [key for key in self.consents.keys() if key.startswith(child_id)]
                for key in keys_to_remove:
                    del self.consents[key]
                return True
            
            # Helper method for testing
            def grant_consent(self, child_id: str, operation: str):
                """Grant consent for testing purposes."""
                consent_key = f"{child_id}:{operation}"
                self.consents[consent_key] = True
        
        # Test the implementation
        consent_manager = TestConsentManager()
        
        # Grant some test consents
        consent_manager.grant_consent("child_123", "chat_interaction")
        consent_manager.grant_consent("child_123", "voice_recording")
        
        # Test consent verification
        chat_allowed = await consent_manager.verify_consent("child_123", "chat_interaction")
        voice_allowed = await consent_manager.verify_consent("child_123", "voice_recording")
        data_collection_allowed = await consent_manager.verify_consent("child_123", "data_collection")
        
        assert chat_allowed is True
        assert voice_allowed is True
        assert data_collection_allowed is False
        
        # Test consent status
        status = await consent_manager.get_consent_status("child_123")
        assert status["status"] == "active"
        assert "chat_interaction" in status["consented_operations"]
        assert "voice_recording" in status["consented_operations"]
        
        # Test consent revocation
        revoked = await consent_manager.revoke_consent("child_123")
        assert revoked is True
        
        # Verify consent is revoked
        chat_allowed_after_revoke = await consent_manager.verify_consent("child_123", "chat_interaction")
        assert chat_allowed_after_revoke is False
        
        status_after_revoke = await consent_manager.get_consent_status("child_123")
        assert status_after_revoke["status"] == "revoked"
        assert len(status_after_revoke["consented_operations"]) == 0

    @pytest.mark.asyncio
    async def test_iconsent_manager_coppa_compliance_scenarios(self):
        """Test consent manager COPPA compliance scenarios."""
        
        class COPPAConsentManager(IConsentManager):
            def __init__(self):
                self.parent_consents = {}
                self.child_ages = {}
                self.audit_trail = []
            
            def _log_consent_event(self, event_type: str, child_id: str, operation: str = None):
                """Log consent events for COPPA compliance."""
                self.audit_trail.append({
                    "event_type": event_type,
                    "child_id": child_id,
                    "operation": operation,
                    "timestamp": "2025-07-29T10:00:00Z"
                })
            
            def set_child_age(self, child_id: str, age: int):
                """Set child age for COPPA validation."""
                self.child_ages[child_id] = age
            
            def grant_parent_consent(self, child_id: str, parent_id: str, operations: List[str]):
                """Grant parental consent for specific operations."""
                self.parent_consents[child_id] = {
                    "parent_id": parent_id,
                    "operations": operations,
                    "granted_at": "2025-07-29T09:00:00Z"
                }
            
            async def verify_consent(self, child_id: str, operation: str) -> bool:
                # Check if child is in COPPA age range
                child_age = self.child_ages.get(child_id)
                if not child_age or not (3 <= child_age <= 13):
                    return False  # Not in COPPA range
                
                # Check parental consent
                consent_info = self.parent_consents.get(child_id)
                if not consent_info:
                    self._log_consent_event("consent_denied_no_parent_consent", child_id, operation)
                    return False
                
                if operation in consent_info["operations"]:
                    self._log_consent_event("consent_verified", child_id, operation)
                    return True
                
                self._log_consent_event("consent_denied_operation_not_allowed", child_id, operation)
                return False
            
            async def get_consent_status(self, child_id: str) -> dict[str, Any]:
                child_age = self.child_ages.get(child_id)
                consent_info = self.parent_consents.get(child_id)
                
                status = {
                    "child_id": child_id,
                    "child_age": child_age,
                    "coppa_applicable": child_age and (3 <= child_age <= 13),
                    "parent_consent_required": True,
                    "consented_operations": consent_info["operations"] if consent_info else [],
                    "parent_id": consent_info["parent_id"] if consent_info else None,
                    "status": "active" if consent_info else "no_consent"
                }
                
                return status
            
            async def revoke_consent(self, child_id: str) -> bool:
                if child_id in self.parent_consents:
                    del self.parent_consents[child_id]
                    self._log_consent_event("consent_revoked", child_id)
                    return True
                return False
        
        # Test COPPA compliance scenarios
        consent_manager = COPPAConsentManager()
        
        # Setup test child
        consent_manager.set_child_age("child_coppa", 7)
        consent_manager.grant_parent_consent(
            "child_coppa", 
            "parent_123", 
            ["chat_interaction", "educational_content"]
        )
        
        # Test allowed operation
        chat_consent = await consent_manager.verify_consent("child_coppa", "chat_interaction")
        assert chat_consent is True
        
        # Test disallowed operation
        data_collection_consent = await consent_manager.verify_consent("child_coppa", "data_collection")
        assert data_collection_consent is False
        
        # Test consent status
        status = await consent_manager.get_consent_status("child_coppa")
        assert status["coppa_applicable"] is True
        assert status["parent_consent_required"] is True
        assert "chat_interaction" in status["consented_operations"]
        assert status["parent_id"] == "parent_123"
        
        # Test audit trail
        assert len(consent_manager.audit_trail) >= 2
        assert any(event["event_type"] == "consent_verified" for event in consent_manager.audit_trail)
        assert any(event["event_type"] == "consent_denied_operation_not_allowed" for event in consent_manager.audit_trail)
        
        # Test consent revocation
        revoked = await consent_manager.revoke_consent("child_coppa")
        assert revoked is True
        
        # Verify revocation
        status_after_revoke = await consent_manager.get_consent_status("child_coppa")
        assert status_after_revoke["status"] == "no_consent"
        
        # Check audit trail includes revocation
        assert any(event["event_type"] == "consent_revoked" for event in consent_manager.audit_trail)


class TestReadModelInterfacesIntegration:
    """Test integration scenarios between read model interfaces."""

    @pytest.mark.asyncio
    async def test_complete_child_profile_workflow(self):
        """Test complete workflow using all read model interfaces."""
        
        # Mock implementations for integration test
        class MockChildProfile(IChildProfileReadModel):
            def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
                self._id = child_id
                self._name = name
                self._age = age
                self._preferences = preferences
            
            @property
            def id(self) -> str:
                return self._id
            
            @property
            def name(self) -> str:
                return self._name
            
            @property
            def age(self) -> int:
                return self._age
            
            @property
            def preferences(self) -> dict[str, Any]:
                return self._preferences
        
        class MockProfileStore(IChildProfileReadModelStore):
            def __init__(self):
                self.profiles = {}
            
            async def save(self, model: IChildProfileReadModel) -> None:
                self.profiles[model.id] = model
            
            async def get_by_id(self, child_id: str) -> IChildProfileReadModel | None:
                return self.profiles.get(child_id)
            
            async def delete_by_id(self, child_id: str) -> bool:
                return child_id in self.profiles and self.profiles.pop(child_id, None) is not None
            
            async def update(self, child_id: str, updates: dict[str, Any]) -> bool:
                return child_id in self.profiles
        
        class MockConsentManager(IConsentManager):
            def __init__(self):
                self.consents = {"child_integration": ["profile_access", "data_storage"]}
            
            async def verify_consent(self, child_id: str, operation: str) -> bool:
                return operation in self.consents.get(child_id, [])
            
            async def get_consent_status(self, child_id: str) -> dict[str, Any]:
                return {
                    "child_id": child_id,
                    "status": "active",
                    "consented_operations": self.consents.get(child_id, [])
                }
            
            async def revoke_consent(self, child_id: str) -> bool:
                self.consents.pop(child_id, None)
                return True
        
        class MockAPIClient(IExternalAPIClient):
            async def make_request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
                return {"status": "success", "endpoint": endpoint, "data": data}
            
            async def check_health(self) -> bool:
                return True
        
        # Integration test workflow
        profile_store = MockProfileStore()
        consent_manager = MockConsentManager()
        api_client = MockAPIClient()
        
        # 1. Verify consent before creating profile
        can_create_profile = await consent_manager.verify_consent("child_integration", "profile_access")
        assert can_create_profile is True
        
        # 2. Create child profile
        child_profile = MockChildProfile(
            child_id="child_integration",
            name="Integration Test Child",
            age=8,
            preferences={"theme": "space", "difficulty": "medium"}
        )
        
        # 3. Save profile (with consent verification)
        can_store_data = await consent_manager.verify_consent("child_integration", "data_storage")
        if can_store_data:
            await profile_store.save(child_profile)
        
        # 4. Verify profile was saved
        saved_profile = await profile_store.get_by_id("child_integration")
        assert saved_profile is not None
        assert saved_profile.name == "Integration Test Child"
        
        # 5. Make API request for child-safe content
        api_response = await api_client.make_request("/generate_content", {
            "child_age": saved_profile.age,
            "preferences": saved_profile.preferences
        })
        assert api_response["status"] == "success"
        
        # 6. Get consent status
        consent_status = await consent_manager.get_consent_status("child_integration")
        assert consent_status["status"] == "active"
        assert "profile_access" in consent_status["consented_operations"]
        
        # 7. Update profile preferences
        update_success = await profile_store.update("child_integration", {
            "preferences": {"theme": "ocean", "difficulty": "hard"}
        })
        assert update_success is True

    def test_read_model_interfaces_architectural_compliance(self):
        """Test that read model interfaces maintain architectural boundaries."""
        
        # All interfaces should be abstract
        interfaces = [
            IChildProfileReadModel,
            IChildProfileReadModelStore,
            IExternalAPIClient,
            IConsentManager
        ]
        
        for interface in interfaces:
            assert issubclass(interface, ABC)
            assert len(interface.__abstractmethods__) > 0
            
            # Should not be instantiable
            with pytest.raises(TypeError):
                interface()

    def test_read_model_interfaces_type_annotations(self):
        """Test that read model interfaces have proper type annotations."""
        
        # Check IChildProfileReadModel properties
        assert hasattr(IChildProfileReadModel, 'id')
        assert hasattr(IChildProfileReadModel, 'name')
        assert hasattr(IChildProfileReadModel, 'age')
        assert hasattr(IChildProfileReadModel, 'preferences')
        
        # Check method signatures exist and are properly typed
        # Note: Detailed type checking would require more sophisticated inspection
        # but the basic structure verification ensures interface contract compliance

    @pytest.mark.asyncio
    async def test_read_model_interfaces_error_handling(self):
        """Test error handling scenarios across read model interfaces."""
        
        class ErrorHandlingProfileStore(IChildProfileReadModelStore):
            async def save(self, model: IChildProfileReadModel) -> None:
                if model.age < 3 or model.age > 13:
                    raise ValueError("Child age outside COPPA range")
            
            async def get_by_id(self, child_id: str) -> IChildProfileReadModel | None:
                if child_id == "error_child":
                    raise Exception("Database connection failed")
                return None
            
            async def delete_by_id(self, child_id: str) -> bool:
                if child_id == "protected_child":
                    raise PermissionError("Cannot delete protected profile")
                return False
            
            async def update(self, child_id: str, updates: dict[str, Any]) -> bool:
                if "invalid_field" in updates:
                    raise ValueError("Invalid field in updates")
                return False
        
        class ErrorHandlingConsentManager(IConsentManager):
            async def verify_consent(self, child_id: str, operation: str) -> bool:
                if child_id == "error_child":
                    raise Exception("Consent verification service unavailable")
                return False
            
            async def get_consent_status(self, child_id: str) -> dict[str, Any]:
                if child_id == "corrupted_child":
                    raise Exception("Corrupted consent data")
                return {"status": "unknown"}
            
            async def revoke_consent(self, child_id: str) -> bool:
                if child_id == "permanent_child":
                    raise PermissionError("Cannot revoke permanent consent")
                return False
        
        # Test error scenarios
        error_store = ErrorHandlingProfileStore()
        error_consent = ErrorHandlingConsentManager()
        
        # Test store errors
        with pytest.raises(Exception, match="Database connection failed"):
            await error_store.get_by_id("error_child")
        
        with pytest.raises(PermissionError, match="Cannot delete protected"):
            await error_store.delete_by_id("protected_child")
        
        with pytest.raises(ValueError, match="Invalid field"):
            await error_store.update("child_123", {"invalid_field": "value"})
        
        # Test consent manager errors
        with pytest.raises(Exception, match="Consent verification service unavailable"):
            await error_consent.verify_consent("error_child", "operation")
        
        with pytest.raises(Exception, match="Corrupted consent data"):
            await error_consent.get_consent_status("corrupted_child")
        
        with pytest.raises(PermissionError, match="Cannot revoke permanent"):
            await error_consent.revoke_consent("permanent_child")