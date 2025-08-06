"""
E2E Test Utilities - Helper Functions for Testing
=================================================
Utility functions for E2E testing:
- Test data generation
- Response validation
- Performance measurement
- Retry mechanisms
- Child safety validation
- API helpers
"""

import asyncio
import time
import random
import string
import hashlib
from typing import Dict, List, Any, Optional, Callable, TypeVar, Union
from datetime import datetime, timedelta
from functools import wraps
import json
import uuid

from httpx import Response
from faker import Faker

from src.infrastructure.logging import get_logger


logger = get_logger("e2e_test_utils")
fake = Faker()

T = TypeVar('T')


# Test data generation
def generate_test_username() -> str:
    """Generate unique test username."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


def generate_test_email() -> str:
    """Generate unique test email."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def generate_child_name() -> str:
    """Generate appropriate child name."""
    first_names = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Jamie"]
    return random.choice(first_names)


def generate_test_data(data_type: str, **kwargs) -> Dict[str, Any]:
    """Generate test data based on type."""
    if data_type == "user":
        return {
            "username": generate_test_username(),
            "email": generate_test_email(),
            "password": "TestPassword123!",
            "role": kwargs.get("role", "parent"),
            "display_name": fake.name(),
            "timezone": "UTC",
            "language": "en"
        }
    
    elif data_type == "child":
        age = kwargs.get("age", random.randint(5, 12))
        return {
            "name": generate_child_name(),
            "estimated_age": age,
            "parental_consent": kwargs.get("parental_consent", True),
            "favorite_topics": ["animals", "space", "dinosaurs"],
            "content_preferences": {
                "story_length": "medium",
                "complexity": "age_appropriate",
                "educational_focus": True
            }
        }
    
    elif data_type == "message":
        return {
            "content": kwargs.get("content", "Tell me a story about a brave rabbit"),
            "sender_type": kwargs.get("sender_type", "child"),
            "content_type": "conversation"
        }
    
    elif data_type == "conversation":
        return {
            "title": kwargs.get("title", f"Conversation {datetime.now().strftime('%Y-%m-%d')}"),
            "educational_content": kwargs.get("educational", True),
            "context_data": {
                "mood": "happy",
                "time_of_day": "evening",
                "previous_topics": []
            }
        }
    
    else:
        raise ValueError(f"Unknown data type: {data_type}")


def generate_bulk_test_data(data_type: str, count: int, **kwargs) -> List[Dict[str, Any]]:
    """Generate multiple test data items."""
    return [generate_test_data(data_type, **kwargs) for _ in range(count)]


# Response validation
def validate_response(
    response: Response,
    expected_status: int = 200,
    required_fields: Optional[List[str]] = None,
    schema: Optional[Dict[str, type]] = None
) -> Dict[str, Any]:
    """Validate API response comprehensively."""
    # Check status code
    assert response.status_code == expected_status, \
        f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
    
    # Parse JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        raise AssertionError(f"Invalid JSON response: {response.text}")
    
    # Check required fields
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        assert not missing_fields, f"Missing required fields: {missing_fields}"
    
    # Validate schema
    if schema:
        for field, expected_type in schema.items():
            if field in data:
                assert isinstance(data[field], expected_type), \
                    f"Field '{field}' should be {expected_type.__name__}, got {type(data[field]).__name__}"
    
    return data


def validate_error_response(response: Response, expected_status: int, error_code: Optional[str] = None) -> Dict[str, Any]:
    """Validate error response format."""
    data = validate_response(
        response,
        expected_status=expected_status,
        required_fields=["error", "message"],
        schema={"error": str, "message": str}
    )
    
    if error_code:
        assert data["error"] == error_code, f"Expected error code '{error_code}', got '{data['error']}'"
    
    return data


def validate_pagination_response(response: Response, max_items: Optional[int] = None) -> Dict[str, Any]:
    """Validate paginated response format."""
    data = validate_response(
        response,
        required_fields=["items", "total", "page", "page_size"],
        schema={
            "items": list,
            "total": int,
            "page": int,
            "page_size": int
        }
    )
    
    # Validate pagination logic
    assert data["page"] > 0, "Page number should be positive"
    assert data["page_size"] > 0, "Page size should be positive"
    assert len(data["items"]) <= data["page_size"], "Items count should not exceed page size"
    
    if max_items:
        assert len(data["items"]) <= max_items, f"Too many items returned: {len(data['items'])}"
    
    return data


# Child safety validation
def validate_child_safety(data: Dict[str, Any], safety_checks: List[str]) -> Dict[str, bool]:
    """Validate child safety compliance."""
    results = {}
    
    for check in safety_checks:
        if check == "parental_consent":
            results[check] = data.get("parental_consent", False) is True
        
        elif check == "age_appropriate":
            age = data.get("estimated_age", 0)
            results[check] = 3 <= age <= 18
        
        elif check == "content_filtering":
            results[check] = data.get("content_filtering_enabled", False) is True
        
        elif check == "data_retention":
            retention_days = data.get("data_retention_days", 0)
            results[check] = 0 < retention_days <= 90
        
        elif check == "no_pii":
            # Check for personally identifiable information
            pii_fields = ["social_security", "full_address", "phone_number", "exact_birthdate"]
            results[check] = not any(field in data for field in pii_fields)
        
        elif check == "encrypted_data":
            # Check if sensitive data is encrypted
            if "content_encrypted" in data:
                results[check] = data["content_encrypted"] is not None
            else:
                results[check] = True  # No sensitive data to encrypt
        
        else:
            logger.warning(f"Unknown safety check: {check}")
            results[check] = False
    
    return results


def assert_child_safety_compliance(data: Dict[str, Any], required_checks: List[str]):
    """Assert that all child safety checks pass."""
    results = validate_child_safety(data, required_checks)
    
    failed_checks = [check for check, passed in results.items() if not passed]
    assert not failed_checks, f"Child safety checks failed: {failed_checks}"


# Performance measurement
def measure_performance(func: Callable) -> Callable:
    """Decorator to measure function performance."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"{func.__name__} completed in {duration_ms:.2f}ms")
            return result, duration_ms
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"{func.__name__} failed after {duration_ms:.2f}ms: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"{func.__name__} completed in {duration_ms:.2f}ms")
            return result, duration_ms
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"{func.__name__} failed after {duration_ms:.2f}ms: {str(e)}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class PerformanceTimer:
    """Context manager for performance timing."""
    
    def __init__(self, operation_name: str, threshold_ms: Optional[float] = None):
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if self.threshold_ms and self.duration_ms > self.threshold_ms:
            logger.warning(
                f"{self.operation_name} exceeded threshold: {self.duration_ms:.2f}ms > {self.threshold_ms}ms"
            )
        else:
            logger.info(f"{self.operation_name} completed in {self.duration_ms:.2f}ms")
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if self.threshold_ms and self.duration_ms > self.threshold_ms:
            logger.warning(
                f"{self.operation_name} exceeded threshold: {self.duration_ms:.2f}ms > {self.threshold_ms}ms"
            )
        else:
            logger.info(f"{self.operation_name} completed in {self.duration_ms:.2f}ms")


# Retry mechanisms
async def retry_on_failure(
    func: Callable[..., T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """Retry async function on failure with exponential backoff."""
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(f"All {max_retries} attempts failed")
    
    raise last_exception


def retry_decorator(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for retrying functions."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_on_failure(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                delay=delay,
                backoff=backoff,
                exceptions=exceptions
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Wait conditions
async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 30.0,
    interval: float = 0.5,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """Wait for a condition to become true."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if await condition() if asyncio.iscoroutinefunction(condition) else condition():
            return True
        await asyncio.sleep(interval)
    
    raise TimeoutError(error_message)


async def wait_for_api_ready(base_url: str, health_endpoint: str = "/health", timeout: float = 60.0):
    """Wait for API to be ready."""
    import httpx
    
    async def check_health():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}{health_endpoint}")
                return response.status_code == 200
        except:
            return False
    
    await wait_for_condition(
        check_health,
        timeout=timeout,
        error_message=f"API at {base_url} not ready within {timeout}s"
    )


# Data cleanup helpers
async def cleanup_test_data(entity_ids: Dict[str, List[str]], repositories: Dict[str, Any]):
    """Clean up test data by entity type."""
    cleanup_order = ["messages", "conversations", "children", "users"]
    
    for entity_type in cleanup_order:
        if entity_type in entity_ids and entity_type in repositories:
            repo = repositories[entity_type]
            for entity_id in entity_ids[entity_type]:
                try:
                    await repo.delete(uuid.UUID(entity_id))
                    logger.debug(f"Deleted {entity_type} {entity_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete {entity_type} {entity_id}: {str(e)}")


# API request helpers
def build_api_url(base_url: str, path: str, version: str = "v1") -> str:
    """Build full API URL."""
    # Remove trailing slashes
    base_url = base_url.rstrip("/")
    path = path.lstrip("/")
    
    # Add API version if not already in path
    if not path.startswith(f"api/{version}"):
        path = f"api/{version}/{path}"
    
    return f"{base_url}/{path}"


def generate_auth_headers(token: str) -> Dict[str, str]:
    """Generate authorization headers."""
    return {"Authorization": f"Bearer {token}"}


def generate_child_safety_headers(
    child_id: Optional[str] = None,
    parental_consent: bool = True,
    age: Optional[int] = None
) -> Dict[str, str]:
    """Generate child safety headers for requests."""
    headers = {
        "X-Child-Safety-Enabled": "true",
        "X-Parental-Consent": "true" if parental_consent else "false"
    }
    
    if child_id:
        headers["X-Child-ID"] = child_id
    
    if age:
        headers["X-Child-Age"] = str(age)
    
    return headers


# Test scenario helpers
async def create_test_scenario(data_manager, scenario_type: str) -> Dict[str, Any]:
    """Create a complete test scenario."""
    if scenario_type == "basic_family":
        # Create parent with one child
        parent = await data_manager.create_test_user(role="parent")
        child = await data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            age=8,
            parental_consent=True
        )
        
        return {
            "parent": parent,
            "children": [child]
        }
    
    elif scenario_type == "multi_child_family":
        # Create parent with multiple children
        parent = await data_manager.create_test_user(role="parent")
        children = []
        
        for age in [5, 8, 12]:
            child = await data_manager.create_test_child(
                parent_id=uuid.UUID(parent["id"]),
                age=age,
                parental_consent=True
            )
            children.append(child)
        
        return {
            "parent": parent,
            "children": children
        }
    
    elif scenario_type == "restricted_child":
        # Create child without parental consent
        parent = await data_manager.create_test_user(role="parent")
        child = await data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            age=7,
            parental_consent=False
        )
        
        return {
            "parent": parent,
            "children": [child],
            "restricted": True
        }
    
    else:
        raise ValueError(f"Unknown scenario type: {scenario_type}")


# Security testing helpers
def generate_malicious_payloads() -> List[Dict[str, Any]]:
    """Generate common security test payloads."""
    return [
        # SQL Injection
        {"content": "'; DROP TABLE users; --"},
        {"username": "admin' OR '1'='1"},
        
        # XSS
        {"content": "<script>alert('XSS')</script>"},
        {"name": "<img src=x onerror=alert('XSS')>"},
        
        # Command Injection
        {"content": "; cat /etc/passwd"},
        {"filename": "test.txt; rm -rf /"},
        
        # Path Traversal
        {"file_path": "../../../../etc/passwd"},
        {"avatar_url": "file:///etc/passwd"},
        
        # LDAP Injection
        {"username": "admin)(|(password=*))"},
        
        # XXE
        {"content": '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'},
        
        # JSON Injection
        {"settings": '{"admin": true, "role": "admin"}'}
    ]


def generate_large_payload(size_mb: int = 10) -> str:
    """Generate large payload for testing size limits."""
    # Generate random string of specified size
    size_bytes = size_mb * 1024 * 1024
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size_bytes))


# Hash and encryption helpers
def hash_child_identifier(child_id: str, salt: str = "test_salt") -> str:
    """Hash child identifier for privacy."""
    return hashlib.sha256(f"{child_id}{salt}".encode()).hexdigest()


def generate_test_jwt(payload: Dict[str, Any], secret: str = "test_secret") -> str:
    """Generate test JWT token."""
    import jwt
    
    payload.update({
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    })
    
    return jwt.encode(payload, secret, algorithm="HS256")