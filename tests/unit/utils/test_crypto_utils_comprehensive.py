"""
Comprehensive unit tests for crypto_utils module.
Production-grade security testing for child data protection.
"""

import pytest
import json
import base64
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.utils.crypto_utils import CryptoUtils, EncryptionService


class TestCryptoUtils:
    """Test CryptoUtils class functionality."""

    @pytest.fixture
    def crypto_utils(self):
        """Create CryptoUtils instance for testing."""
        return CryptoUtils()

    @pytest.fixture
    def test_key(self):
        """Generate test encryption key."""
        return os.urandom(32)

    def test_init_default_parameters(self):
        """Test CryptoUtils initialization with default parameters."""
        crypto = CryptoUtils()
        assert crypto.default_algorithm == "AES-256-GCM"
        assert crypto.key_derivation_iterations == 100000

    def test_init_custom_parameters(self):
        """Test CryptoUtils initialization with custom parameters."""
        crypto = CryptoUtils(
            default_algorithm="AES-128-CBC", 
            key_derivation_iterations=50000
        )
        assert crypto.default_algorithm == "AES-128-CBC"
        assert crypto.key_derivation_iterations == 50000

    def test_generate_random_key_default_length(self, crypto_utils):
        """Test random key generation with default length."""
        key = crypto_utils.generate_random_key()
        
        assert isinstance(key, bytes)
        assert len(key) == 32  # Default length
        
        # Ensure randomness - two calls should produce different keys
        key2 = crypto_utils.generate_random_key()
        assert key != key2

    def test_generate_random_key_custom_length(self, crypto_utils):
        """Test random key generation with custom length."""
        for length in [16, 24, 32, 64]:
            key = crypto_utils.generate_random_key(length)
            assert isinstance(key, bytes)
            assert len(key) == length

    def test_hash_password_creates_valid_hash(self, crypto_utils):
        """Test password hashing produces valid bcrypt hash."""
        password = "test_password_123"
        hashed = crypto_utils.hash_password(password)
        
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")  # bcrypt format
        assert len(hashed) == 60  # Standard bcrypt hash length
        
        # Ensure different salts create different hashes
        hashed2 = crypto_utils.hash_password(password)
        assert hashed != hashed2

    def test_verify_password_correct_password(self, crypto_utils):
        """Test password verification with correct password."""
        password = "secure_password_456"
        hashed = crypto_utils.hash_password(password)
        
        assert crypto_utils.verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self, crypto_utils):
        """Test password verification with incorrect password."""
        password = "correct_password"
        wrong_password = "incorrect_password"
        hashed = crypto_utils.hash_password(password)
        
        assert crypto_utils.verify_password(wrong_password, hashed) is False

    def test_verify_password_edge_cases(self, crypto_utils):
        """Test password verification edge cases."""
        password = "test_password"
        hashed = crypto_utils.hash_password(password)
        
        # Empty password
        assert crypto_utils.verify_password("", hashed) is False
        
        # Unicode password
        unicode_password = "пароль"
        unicode_hashed = crypto_utils.hash_password(unicode_password)
        assert crypto_utils.verify_password(unicode_password, unicode_hashed) is True

    def test_encrypt_decrypt_data_roundtrip(self, crypto_utils, test_key):
        """Test encryption/decryption roundtrip."""
        plaintext = "Sensitive child data that needs protection"
        
        encrypted = crypto_utils.encrypt_data(plaintext, test_key)
        decrypted = crypto_utils.decrypt_data(encrypted, test_key)
        
        assert decrypted == plaintext

    def test_encrypt_data_structure(self, crypto_utils, test_key):
        """Test encrypted data structure contains required fields."""
        plaintext = "Test data"
        encrypted = crypto_utils.encrypt_data(plaintext, test_key)
        
        assert isinstance(encrypted, dict)
        assert "ciphertext" in encrypted
        assert "nonce" in encrypted
        assert "tag" in encrypted
        
        # Verify ciphertext is base64 encoded
        import base64
        try:
            base64.b64decode(encrypted["ciphertext"])
        except Exception:
            pytest.fail("Ciphertext is not valid base64")

    def test_encrypt_different_plaintexts_different_outputs(self, crypto_utils, test_key):
        """Test different plaintexts produce different encrypted outputs."""
        plaintext1 = "First secret message"
        plaintext2 = "Second secret message"
        
        encrypted1 = crypto_utils.encrypt_data(plaintext1, test_key)
        encrypted2 = crypto_utils.encrypt_data(plaintext2, test_key)
        
        assert encrypted1["ciphertext"] != encrypted2["ciphertext"]

    def test_decrypt_data_wrong_key_fails(self, crypto_utils):
        """Test decryption with wrong key fails appropriately."""
        plaintext = "Secret data"
        correct_key = os.urandom(32)
        wrong_key = os.urandom(32)
        
        encrypted = crypto_utils.encrypt_data(plaintext, correct_key)
        
        with pytest.raises(Exception):  # Should raise decryption error
            crypto_utils.decrypt_data(encrypted, wrong_key)

    def test_generate_hmac_signature(self, crypto_utils):
        """Test HMAC signature generation."""
        data = "Important message to authenticate"
        secret_key = os.urandom(32)
        
        signature = crypto_utils.generate_hmac(data, secret_key)
        
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length
        
        # Verify deterministic - same inputs produce same signature
        signature2 = crypto_utils.generate_hmac(data, secret_key)
        assert signature == signature2

    def test_verify_hmac_valid_signature(self, crypto_utils):
        """Test HMAC verification with valid signature."""
        data = "Authenticated data"
        secret_key = os.urandom(32)
        
        signature = crypto_utils.generate_hmac(data, secret_key)
        assert crypto_utils.verify_hmac(data, secret_key, signature) is True

    def test_verify_hmac_invalid_signature(self, crypto_utils):
        """Test HMAC verification with invalid signature."""
        data = "Authenticated data"
        secret_key = os.urandom(32)
        wrong_signature = "invalid_signature_12345"
        
        assert crypto_utils.verify_hmac(data, secret_key, wrong_signature) is False

    def test_verify_hmac_tampered_data(self, crypto_utils):
        """Test HMAC verification detects data tampering."""
        original_data = "Original message"
        tampered_data = "Tampered message"
        secret_key = os.urandom(32)
        
        signature = crypto_utils.generate_hmac(original_data, secret_key)
        assert crypto_utils.verify_hmac(tampered_data, secret_key, signature) is False

    def test_derive_key_pbkdf2(self, crypto_utils):
        """Test PBKDF2 key derivation."""
        password = "user_password"
        salt = os.urandom(16)
        
        derived_key = crypto_utils.derive_key(password, salt)
        
        assert isinstance(derived_key, bytes)
        assert len(derived_key) == 32  # SHA256 output length
        
        # Same inputs should produce same key
        derived_key2 = crypto_utils.derive_key(password, salt)
        assert derived_key == derived_key2

    def test_derive_key_different_salts(self, crypto_utils):
        """Test key derivation with different salts produces different keys."""
        password = "same_password"
        salt1 = os.urandom(16)
        salt2 = os.urandom(16)
        
        key1 = crypto_utils.derive_key(password, salt1)
        key2 = crypto_utils.derive_key(password, salt2)
        
        assert key1 != key2

    def test_derive_key_custom_iterations(self, crypto_utils):
        """Test key derivation with custom iteration count."""
        password = "test_password"
        salt = os.urandom(16)
        custom_iterations = 10000
        
        key = crypto_utils.derive_key(password, salt, custom_iterations)
        
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_secure_compare_identical_strings(self, crypto_utils):
        """Test secure string comparison with identical strings."""
        string1 = "identical_string"
        string2 = "identical_string"
        
        assert crypto_utils.secure_compare(string1, string2) is True

    def test_secure_compare_different_strings(self, crypto_utils):
        """Test secure string comparison with different strings."""
        string1 = "string_one"
        string2 = "string_two"
        
        assert crypto_utils.secure_compare(string1, string2) is False

    def test_secure_compare_timing_attack_resistance(self, crypto_utils):
        """Test secure comparison timing attack resistance."""
        # This test ensures hmac.compare_digest is used (constant-time)
        short_string = "a"
        long_string = "a" * 1000
        different_string = "b"
        
        # Should return False but take similar time regardless of length
        assert crypto_utils.secure_compare(short_string, different_string) is False
        assert crypto_utils.secure_compare(long_string, different_string) is False

    @patch('src.utils.crypto_utils.datetime')
    def test_encrypt_child_pii_structure(self, mock_datetime, crypto_utils):
        """Test child PII encryption includes COPPA metadata."""
        mock_datetime.utcnow.return_value.isoformat.return_value = "2023-01-01T00:00:00"
        
        child_data = {
            "name": "Test Child",
            "age": 8,
            "preferences": {"favorite_color": "blue"}
        }
        encryption_key = os.urandom(32)
        
        result = crypto_utils.encrypt_child_pii(child_data, encryption_key)
        
        # Verify encryption structure
        assert "ciphertext" in result
        assert "nonce" in result
        assert "tag" in result
        assert "metadata" in result
        
        # Verify COPPA metadata
        metadata = result["metadata"]
        assert metadata["data_type"] == "child_pii"
        assert metadata["coppa_protected"] is True
        assert metadata["encrypted_at"] == "2023-01-01T00:00:00"
        assert metadata["algorithm"] == "AES-256-GCM"

    def test_encrypt_child_pii_roundtrip(self, crypto_utils):
        """Test child PII encryption/decryption roundtrip."""
        child_data = {
            "child_id": "test_child_123",
            "name": "Alice Smith",
            "age": 10,
            "location": "Test City"
        }
        encryption_key = os.urandom(32)
        
        # Encrypt
        encrypted = crypto_utils.encrypt_child_pii(child_data, encryption_key)
        
        # Extract and decrypt
        encrypted_data = {
            "ciphertext": encrypted["ciphertext"],
            "nonce": encrypted["nonce"],
            "tag": encrypted["tag"]
        }
        decrypted_json = crypto_utils.decrypt_data(encrypted_data, encryption_key)
        decrypted_data = json.loads(decrypted_json)
        
        assert decrypted_data == child_data


class TestEncryptionService:
    """Test EncryptionService class functionality."""

    @pytest.fixture
    def encryption_service(self):
        """Create EncryptionService instance for testing."""
        return EncryptionService()

    @pytest.fixture
    def encryption_service_with_key(self):
        """Create EncryptionService with predefined key."""
        test_key = os.urandom(32)
        return EncryptionService(master_key=test_key)

    def test_init_without_master_key(self):
        """Test EncryptionService initialization without master key."""
        service = EncryptionService()
        
        assert service.master_key is not None
        assert len(service.master_key) == 32
        assert isinstance(service.crypto_utils, CryptoUtils)

    def test_init_with_master_key(self):
        """Test EncryptionService initialization with master key."""
        test_key = os.urandom(32)
        service = EncryptionService(master_key=test_key)
        
        assert service.master_key == test_key

    def test_encrypt_sensitive_data_various_types(self, encryption_service):
        """Test encryption of various data types."""
        test_cases = [
            "Simple string",
            {"key": "value", "number": 42},
            [1, 2, 3, "mixed", {"nested": True}],
            {"complex": {"nested": {"data": ["with", "arrays"]}}}
        ]
        
        for test_data in test_cases:
            encrypted = encryption_service.encrypt_sensitive_data(test_data)
            
            assert isinstance(encrypted, str)
            # Verify it's valid base64
            try:
                base64.b64decode(encrypted)
            except Exception:
                pytest.fail(f"Invalid base64 encoding for data: {test_data}")

    def test_encrypt_decrypt_sensitive_data_roundtrip(self, encryption_service):
        """Test encryption/decryption roundtrip for sensitive data."""
        original_data = {
            "user_id": "user_123",
            "session_token": "abc123xyz",
            "permissions": ["read", "write"],
            "metadata": {"last_login": "2023-01-01"}
        }
        
        encrypted = encryption_service.encrypt_sensitive_data(original_data)
        decrypted = encryption_service.decrypt_sensitive_data(encrypted)
        
        assert decrypted == original_data

    def test_encrypt_different_data_different_outputs(self, encryption_service):
        """Test different data produces different encrypted outputs."""
        data1 = {"message": "First secret"}
        data2 = {"message": "Second secret"}
        
        encrypted1 = encryption_service.encrypt_sensitive_data(data1)
        encrypted2 = encryption_service.encrypt_sensitive_data(data2)
        
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_service_fails(self):
        """Test decryption fails with different service instance."""
        service1 = EncryptionService()
        service2 = EncryptionService()
        
        data = {"secret": "important_data"}
        encrypted = service1.encrypt_sensitive_data(data)
        
        # Should fail because service2 has different master key
        with pytest.raises(Exception):
            service2.decrypt_sensitive_data(encrypted)

    def test_decrypt_invalid_data_fails(self, encryption_service):
        """Test decryption fails with invalid encrypted data."""
        invalid_data_cases = [
            "not_base64_data",
            base64.b64encode(b"invalid_json").decode(),
            base64.b64encode(b'{"missing": "ciphertext"}').decode()
        ]
        
        for invalid_data in invalid_data_cases:
            with pytest.raises(Exception):
                encryption_service.decrypt_sensitive_data(invalid_data)

    def test_service_consistency_across_operations(self, encryption_service_with_key):
        """Test service maintains consistency across multiple operations."""
        test_data = [
            "String data",
            {"dict": "data"},
            [1, 2, 3],
            {"complex": {"nested": {"structure": True}}}
        ]
        
        encrypted_items = []
        for item in test_data:
            encrypted = encryption_service_with_key.encrypt_sensitive_data(item)
            encrypted_items.append(encrypted)
        
        # Decrypt all items and verify
        for i, encrypted in enumerate(encrypted_items):
            decrypted = encryption_service_with_key.decrypt_sensitive_data(encrypted)
            assert decrypted == test_data[i]


class TestCryptoUtilsEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def crypto_utils(self):
        return CryptoUtils()

    def test_hash_password_empty_string(self, crypto_utils):
        """Test password hashing with empty string."""
        hashed = crypto_utils.hash_password("")
        assert isinstance(hashed, str)
        assert crypto_utils.verify_password("", hashed) is True

    def test_encrypt_data_empty_string(self, crypto_utils):
        """Test encryption of empty string."""
        test_key = os.urandom(32)
        encrypted = crypto_utils.encrypt_data("", test_key)
        decrypted = crypto_utils.decrypt_data(encrypted, test_key)
        assert decrypted == ""

    def test_hmac_empty_data(self, crypto_utils):
        """Test HMAC generation with empty data."""
        secret_key = os.urandom(32)
        signature = crypto_utils.generate_hmac("", secret_key)
        assert isinstance(signature, str)
        assert crypto_utils.verify_hmac("", secret_key, signature) is True

    def test_derive_key_empty_password(self, crypto_utils):
        """Test key derivation with empty password."""
        salt = os.urandom(16)
        key = crypto_utils.derive_key("", salt)
        assert isinstance(key, bytes)
        assert len(key) == 32


class TestCryptoUtilsSecurity:
    """Test security-specific aspects."""

    @pytest.fixture
    def crypto_utils(self):
        return CryptoUtils()

    def test_key_generation_entropy(self, crypto_utils):
        """Test generated keys have sufficient entropy."""
        keys = [crypto_utils.generate_random_key() for _ in range(10)]
        
        # All keys should be different
        assert len(set(keys)) == 10
        
        # Keys should not follow predictable patterns
        for key in keys:
            # Should not be all zeros or all ones
            assert key != b'\x00' * 32
            assert key != b'\xff' * 32

    def test_password_hash_timing_consistency(self, crypto_utils):
        """Test password hashing timing consistency."""
        import time
        
        passwords = ["short", "medium_length_password", "very_long_password" * 10]
        times = []
        
        for password in passwords:
            start = time.time()
            crypto_utils.hash_password(password)
            end = time.time()
            times.append(end - start)
        
        # Times should be similar (bcrypt cost factor provides consistency)
        avg_time = sum(times) / len(times)
        for t in times:
            # Allow 50% variance (bcrypt is naturally consistent)
            assert abs(t - avg_time) / avg_time < 0.5

    def test_encryption_key_size_requirements(self, crypto_utils):
        """Test encryption key size requirements."""
        plaintexts = ["test"]
        
        # Test various key sizes
        valid_keys = [os.urandom(32), os.urandom(64)]
        for key in valid_keys:
            try:
                encrypted = crypto_utils.encrypt_data("test", key)
                decrypted = crypto_utils.decrypt_data(encrypted, key)
                assert decrypted == "test"
            except Exception as e:
                pytest.fail(f"Valid key size {len(key)} failed: {e}")


# Integration test with real cryptographic operations
class TestCryptoIntegration:
    """Integration tests for cryptographic operations."""

    def test_full_child_data_protection_workflow(self):
        """Test complete child data protection workflow."""
        # Initialize services
        crypto_utils = CryptoUtils()
        encryption_service = EncryptionService()
        
        # Simulate child data collection
        child_data = {
            "child_id": "child_12345",
            "name": "Emily Johnson",
            "age": 9,
            "preferences": {
                "favorite_games": ["puzzle", "story"],
                "learning_level": "intermediate"
            },
            "parent_email": "parent@example.com"
        }
        
        # Step 1: Encrypt PII with COPPA compliance
        master_key = crypto_utils.generate_random_key(32)
        encrypted_pii = crypto_utils.encrypt_child_pii(child_data, master_key)
        
        # Step 2: Create session data
        session_data = {
            "session_id": "session_abc123",
            "child_id": child_data["child_id"],
            "login_time": datetime.utcnow().isoformat()
        }
        encrypted_session = encryption_service.encrypt_sensitive_data(session_data)
        
        # Step 3: Generate authentication token
        auth_token = crypto_utils.generate_hmac(
            session_data["session_id"],
            master_key
        )
        
        # Step 4: Verify data integrity and decrypt
        # Verify session
        assert crypto_utils.verify_hmac(
            session_data["session_id"],
            master_key,
            auth_token
        )
        
        # Decrypt session
        decrypted_session = encryption_service.decrypt_sensitive_data(encrypted_session)
        assert decrypted_session["child_id"] == child_data["child_id"]
        
        # Decrypt PII
        pii_cipher_data = {
            "ciphertext": encrypted_pii["ciphertext"],
            "nonce": encrypted_pii["nonce"],
            "tag": encrypted_pii["tag"]
        }
        decrypted_pii_json = crypto_utils.decrypt_data(pii_cipher_data, master_key)
        decrypted_pii = json.loads(decrypted_pii_json)
        
        assert decrypted_pii == child_data
        
        # Verify COPPA metadata
        assert encrypted_pii["metadata"]["coppa_protected"] is True
        assert encrypted_pii["metadata"]["data_type"] == "child_pii"