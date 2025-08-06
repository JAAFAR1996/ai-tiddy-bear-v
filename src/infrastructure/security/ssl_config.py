"""
SSL/TLS Configuration - Production Security
==========================================
Enterprise-grade SSL/TLS configuration with:
- Modern TLS protocols and cipher suites
- HSTS and certificate pinning
- OCSP stapling and CT monitoring
- Certificate management and rotation
- Security headers integration
- Performance optimization
"""

import os
import ssl
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import requests


class TLSVersion(Enum):
    """Supported TLS versions."""
    TLSv1_2 = ssl.PROTOCOL_TLSv1_2
    TLSv1_3 = ssl.PROTOCOL_TLS


class SecurityLevel(Enum):
    """Security configuration levels."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    PARANOID = "paranoid"


@dataclass
class CertificateInfo:
    """Certificate information."""
    common_name: str
    alternative_names: List[str] = field(default_factory=list)
    issuer: str = ""
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    fingerprint_sha256: str = ""
    public_key_pin: str = ""
    is_self_signed: bool = False
    is_ca: bool = False
    
    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        if not self.valid_from or not self.valid_until:
            return False
        
        now = datetime.utcnow()
        return self.valid_from <= now <= self.valid_until
    
    def expires_soon(self, days: int = 30) -> bool:
        """Check if certificate expires within specified days."""
        if not self.valid_until:
            return True
        
        return self.valid_until <= datetime.utcnow() + timedelta(days=days)


@dataclass
class TLSConfig:
    """TLS configuration settings."""
    # Protocol versions
    min_version: TLSVersion = TLSVersion.TLSv1_2
    max_version: TLSVersion = TLSv1_3
    
    # Cipher suites (in preference order)
    cipher_suites: List[str] = field(default_factory=lambda: [
        # TLS 1.3 cipher suites
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_AES_128_GCM_SHA256",
        
        # TLS 1.2 cipher suites (ECDHE for Perfect Forward Secrecy)
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-RSA-CHACHA20-POLY1305",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES256-SHA384",
        "ECDHE-RSA-AES128-SHA256"
    ])
    
    # Certificate paths
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    
    # HSTS settings
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    
    # OCSP settings
    ocsp_stapling: bool = True
    ocsp_must_staple: bool = False
    
    # Certificate Transparency
    ct_monitoring: bool = True
    ct_logs: List[str] = field(default_factory=lambda: [
        "https://ct.googleapis.com/logs/argon2024/",
        "https://ct.cloudflare.com/logs/nimbus2024/",
        "https://ct1.digicert-ct.com/log/"
    ])
    
    # Security features
    verify_mode: int = ssl.CERT_REQUIRED
    check_hostname: bool = True
    disable_compression: bool = True  # Prevent CRIME attacks
    
    # Performance settings
    session_cache_size: int = 1000
    session_timeout: int = 7200  # 2 hours
    
    # Certificate pinning
    pin_certificates: bool = True
    backup_pins: List[str] = field(default_factory=list)
    
    # Custom options
    custom_options: Dict[str, Any] = field(default_factory=dict)


class SSLConfigManager:
    """
    SSL/TLS configuration manager for production environments.
    
    Features:
    - Modern TLS protocol and cipher configuration
    - Certificate validation and monitoring
    - HSTS and security headers management
    - Certificate pinning and rotation
    - OCSP stapling configuration
    - Performance optimization
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.PRODUCTION):
        self.security_level = security_level
        self.logger = None  # Will be injected
        
        # Initialize configurations
        self.configs = self._initialize_configurations()
        
        # Certificate cache
        self._cert_cache: Dict[str, CertificateInfo] = {}
        
        # Pin cache
        self._pin_cache: Dict[str, str] = {}
    
    def _initialize_configurations(self) -> Dict[SecurityLevel, TLSConfig]:
        """Initialize security level specific configurations."""
        configs = {}
        
        # Development - Flexible for testing
        configs[SecurityLevel.DEVELOPMENT] = TLSConfig(
            min_version=TLSVersion.TLSv1_2,
            cipher_suites=[
                "ECDHE-RSA-AES256-GCM-SHA384",
                "ECDHE-RSA-AES128-GCM-SHA256",
                "DHE-RSA-AES256-GCM-SHA384",
                "DHE-RSA-AES128-GCM-SHA256"
            ],
            hsts_max_age=86400,  # 1 day
            hsts_preload=False,
            verify_mode=ssl.CERT_NONE,  # Allow self-signed
            check_hostname=False,
            pin_certificates=False,
            ocsp_stapling=False
        )
        
        # Staging - Production-like but with monitoring
        configs[SecurityLevel.STAGING] = TLSConfig(
            min_version=TLSVersion.TLSv1_2,
            cipher_suites=[
                "TLS_AES_256_GCM_SHA384",
                "TLS_AES_128_GCM_SHA256",
                "ECDHE-RSA-AES256-GCM-SHA384",
                "ECDHE-RSA-AES128-GCM-SHA256"
            ],
            hsts_max_age=2592000,  # 30 days
            hsts_preload=False,
            verify_mode=ssl.CERT_REQUIRED,
            check_hostname=True,
            pin_certificates=True,
            ocsp_stapling=True
        )
        
        # Production - Secure and optimized
        configs[SecurityLevel.PRODUCTION] = TLSConfig(
            min_version=TLSVersion.TLSv1_2,
            max_version=TLSVersion.TLSv1_3,
            cipher_suites=[
                # Prefer TLS 1.3
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_AES_128_GCM_SHA256",
                
                # TLS 1.2 fallback with PFS
                "ECDHE-RSA-AES256-GCM-SHA384",
                "ECDHE-RSA-CHACHA20-POLY1305",
                "ECDHE-RSA-AES128-GCM-SHA256"
            ],
            hsts_max_age=31536000,  # 1 year
            hsts_include_subdomains=True,
            hsts_preload=True,
            verify_mode=ssl.CERT_REQUIRED,
            check_hostname=True,
            pin_certificates=True,
            ocsp_stapling=True,
            ocsp_must_staple=True,
            ct_monitoring=True,
            session_cache_size=5000,
            disable_compression=True
        )
        
        # Paranoid - Maximum security
        configs[SecurityLevel.PARANOID] = TLSConfig(
            min_version=TLSVersion.TLSv1_3,  # TLS 1.3 only
            max_version=TLSVersion.TLSv1_3,
            cipher_suites=[
                "TLS_AES_256_GCM_SHA384",  # Only strongest cipher
            ],
            hsts_max_age=63072000,  # 2 years
            hsts_include_subdomains=True,
            hsts_preload=True,
            verify_mode=ssl.CERT_REQUIRED,
            check_hostname=True,
            pin_certificates=True,
            ocsp_stapling=True,
            ocsp_must_staple=True,
            ct_monitoring=True,
            session_timeout=3600,  # 1 hour
            disable_compression=True
        )
        
        return configs
    
    def get_ssl_context(
        self,
        server_side: bool = True,
        custom_config: Optional[TLSConfig] = None
    ) -> ssl.SSLContext:
        """
        Create SSL context with security configuration.
        
        Args:
            server_side: Whether this is for server or client
            custom_config: Custom TLS configuration
            
        Returns:
            Configured SSLContext
        """
        config = custom_config or self.configs[self.security_level]
        
        # Create context
        if hasattr(ssl, 'PROTOCOL_TLS_SERVER') and server_side:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        elif hasattr(ssl, 'PROTOCOL_TLS_CLIENT') and not server_side:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        
        # Set TLS version range
        if hasattr(context, 'minimum_version'):
            if config.min_version == TLSVersion.TLSv1_2:
                context.minimum_version = ssl.TLSVersion.TLSv1_2
            elif config.min_version == TLSVersion.TLSv1_3:
                context.minimum_version = ssl.TLSVersion.TLSv1_3
        
        if hasattr(context, 'maximum_version'):
            if config.max_version == TLSVersion.TLSv1_2:
                context.maximum_version = ssl.TLSVersion.TLSv1_2
            elif config.max_version == TLSVersion.TLSv1_3:
                context.maximum_version = ssl.TLSVersion.TLSv1_3
        
        # Set cipher suites
        if config.cipher_suites:
            context.set_ciphers(':'.join(config.cipher_suites))
        
        # Security options
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        
        # Disable compression to prevent CRIME attacks
        if config.disable_compression:
            context.options |= ssl.OP_NO_COMPRESSION
        
        # Cipher order preference
        context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE
        
        # Single DH use for Perfect Forward Secrecy
        context.options |= ssl.OP_SINGLE_DH_USE
        context.options |= ssl.OP_SINGLE_ECDH_USE
        
        # Verification settings
        context.verify_mode = config.verify_mode
        context.check_hostname = config.check_hostname
        
        # Load certificates
        if config.cert_file and config.key_file:
            context.load_cert_chain(config.cert_file, config.key_file)
        
        if config.ca_file:
            context.load_verify_locations(config.ca_file)
        
        # Session settings
        if hasattr(context, 'session_stats'):
            context.set_default_verify_paths()
        
        return context
    
    def load_certificate_info(self, cert_path: str) -> CertificateInfo:
        """Load and parse certificate information."""
        if cert_path in self._cert_cache:
            return self._cert_cache[cert_path]
        
        # Validate and sanitize the certificate path to prevent path traversal
        cert_path = self._validate_certificate_path(cert_path)
        
        try:
            with open(cert_path, 'rb') as cert_file:
                cert_data = cert_file.read()
            
            # Try PEM format first
            try:
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except ValueError:
                # Try DER format
                cert = x509.load_der_x509_certificate(cert_data, default_backend())
            
            # Extract certificate information
            cert_info = CertificateInfo(
                common_name=self._get_common_name(cert),
                alternative_names=self._get_subject_alt_names(cert),
                issuer=cert.issuer.rfc4514_string(),
                valid_from=cert.not_valid_before,
                valid_until=cert.not_valid_after,
                fingerprint_sha256=self._get_fingerprint(cert),
                public_key_pin=self._get_public_key_pin(cert),
                is_self_signed=self._is_self_signed(cert),
                is_ca=self._is_ca_certificate(cert)
            )
            
            # Cache the result
            self._cert_cache[cert_path] = cert_info
            
            return cert_info
            
        except (FileNotFoundError, PermissionError) as e:
            if self.logger:
                self.logger.error(f"Certificate file access error {cert_path}: {str(e)}")
            raise
        except ValueError as e:
            if self.logger:
                self.logger.error(f"Certificate format error {cert_path}: {str(e)}")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Unexpected error loading certificate {cert_path}: {str(e)}")
            raise
    
    def _get_common_name(self, cert: x509.Certificate) -> str:
        """Extract common name from certificate."""
        try:
            for attribute in cert.subject:
                if attribute.oid == x509.NameOID.COMMON_NAME:
                    return attribute.value
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to extract common name from certificate: {str(e)}")
        return ""
    
    def _get_subject_alt_names(self, cert: x509.Certificate) -> List[str]:
        """Extract Subject Alternative Names from certificate."""
        try:
            san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            return [name.value for name in san_ext.value]
        except x509.ExtensionNotFound:
            return []
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to extract SAN from certificate: {str(e)}")
            return []
    
    def _get_fingerprint(self, cert: x509.Certificate) -> str:
        """Get SHA-256 fingerprint of certificate."""
        fingerprint = cert.fingerprint(hashes.SHA256())
        return fingerprint.hex().upper()
    
    def _get_public_key_pin(self, cert: x509.Certificate) -> str:
        """Get HPKP pin for certificate."""
        public_key = cert.public_key()
        
        # Serialize public key in DER format
        der_key = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Calculate SHA-256 hash
        pin_hash = hashlib.sha256(der_key).digest()
        
        # Base64 encode
        return base64.b64encode(pin_hash).decode()
    
    def _is_self_signed(self, cert: x509.Certificate) -> bool:
        """Check if certificate is self-signed."""
        return cert.issuer == cert.subject
    
    def _is_ca_certificate(self, cert: x509.Certificate) -> bool:
        """Check if certificate is a CA certificate."""
        try:
            basic_constraints = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.BASIC_CONSTRAINTS
            )
            return basic_constraints.value.ca
        except x509.ExtensionNotFound:
            return False
    
    def get_hsts_header(self, config: Optional[TLSConfig] = None) -> str:
        """Get HSTS header value."""
        config = config or self.configs[self.security_level]
        
        hsts_parts = [f"max-age={config.hsts_max_age}"]
        
        if config.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")
        
        if config.hsts_preload:
            hsts_parts.append("preload")
        
        return "; ".join(hsts_parts)
    
    def get_security_headers(self, config: Optional[TLSConfig] = None) -> Dict[str, str]:
        """Get TLS-related security headers."""
        config = config or self.configs[self.security_level]
        headers = {}
        
        # HSTS header
        headers["Strict-Transport-Security"] = self.get_hsts_header(config)
        
        # Expect-CT header for Certificate Transparency
        if config.ct_monitoring:
            ct_header = f"max-age=86400, enforce"
            if config.ct_logs:
                # Add reporting URI if configured
                report_uri = os.getenv("CT_REPORT_URI")
                if report_uri:
                    ct_header += f', report-uri="{report_uri}"'
            headers["Expect-CT"] = ct_header
        
        # HPKP header (if certificate pinning enabled)
        if config.pin_certificates:
            hpkp_header = self._get_hpkp_header(config)
            if hpkp_header:
                headers["Public-Key-Pins"] = hpkp_header
        
        return headers
    
    def _get_hpkp_header(self, config: TLSConfig) -> Optional[str]:
        """Generate HPKP header with certificate pins."""
        pins = []
        
        # Add current certificate pin
        if config.cert_file:
            try:
                cert_info = self.load_certificate_info(config.cert_file)
                if cert_info.public_key_pin:
                    pins.append(f'pin-sha256="{cert_info.public_key_pin}"')
            except Exception:
                pass
        
        # Add backup pins
        for backup_pin in config.backup_pins:
            pins.append(f'pin-sha256="{backup_pin}"')
        
        if len(pins) < 2:
            # HPKP requires at least 2 pins
            return None
        
        hpkp_parts = pins + [
            "max-age=2592000",  # 30 days
            "includeSubDomains"
        ]
        
        # Add report URI if configured
        report_uri = os.getenv("HPKP_REPORT_URI")
        if report_uri:
            hpkp_parts.append(f'report-uri="{report_uri}"')
        
        return "; ".join(hpkp_parts)
    
    def validate_certificate_chain(self, cert_path: str, ca_path: Optional[str] = None) -> bool:
        """Validate certificate chain."""
        try:
            cert_info = self.load_certificate_info(cert_path)
            
            # Check if certificate is valid
            if not cert_info.is_valid():
                if self.logger:
                    self.logger.error(f"Certificate {cert_path} is not valid or expired")
                return False
            
            # Check if certificate expires soon
            if cert_info.expires_soon():
                if self.logger:
                    self.logger.warning(f"Certificate {cert_path} expires soon: {cert_info.valid_until}")
            
            # Additional validation could include OCSP checking
            # This would require implementing OCSP client
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Certificate validation failed: {str(e)}")
            return False
    
    def monitor_certificate_transparency(self, domain: str) -> Dict[str, Any]:
        """Monitor Certificate Transparency logs for domain."""
        config = self.configs[self.security_level]
        results = {}
        
        if not config.ct_monitoring:
            return results
        
        for ct_log_url in config.ct_logs:
            try:
                # Query CT log for domain certificates
                # This is a simplified implementation
                response = requests.get(
                    f"{ct_log_url}ct/v1/get-entries",
                    params={"domain": domain},
                    timeout=10
                )
                
                if response.status_code == 200:
                    results[ct_log_url] = {
                        "status": "success",
                        "certificates": response.json().get("entries", [])
                    }
                else:
                    results[ct_log_url] = {
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
                    
            except Exception as e:
                results[ct_log_url] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def get_cipher_strength_info(self) -> Dict[str, Any]:
        """Get information about configured cipher strength."""
        config = self.configs[self.security_level]
        
        cipher_info = {
            "tls_versions": {
                "minimum": config.min_version.name,
                "maximum": config.max_version.name
            },
            "cipher_suites": config.cipher_suites,
            "features": {
                "perfect_forward_secrecy": any(
                    "ECDHE" in cipher or "DHE" in cipher 
                    for cipher in config.cipher_suites
                ),
                "aead_ciphers": any(
                    "GCM" in cipher or "POLY1305" in cipher
                    for cipher in config.cipher_suites
                ),
                "compression_disabled": config.disable_compression,
                "session_resumption": config.session_cache_size > 0
            },
            "security_level": self.security_level.value
        }
        
        return cipher_info
    
    def _validate_certificate_path(self, cert_path: str) -> str:
        """Validate and sanitize certificate path to prevent path traversal."""
        import os.path
        
        # Remove any path traversal attempts
        cert_path = cert_path.replace('..', '').replace('//', '/').replace('\\\\', '\\')
        
        # Ensure path is absolute and normalized
        cert_path = os.path.abspath(cert_path)
        
        # Define allowed certificate directories
        allowed_dirs = [
            '/etc/ssl/certs',
            '/etc/pki/tls/certs',
            '/usr/local/share/ca-certificates',
            os.path.expanduser('~/.ssl/certs'),
            os.getcwd() + '/certs',  # Current working directory certs folder
        ]
        
        # Check if the path is within allowed directories
        path_allowed = False
        for allowed_dir in allowed_dirs:
            try:
                # Normalize the allowed directory path
                normalized_allowed = os.path.abspath(allowed_dir)
                # Check if cert_path starts with allowed directory
                if cert_path.startswith(normalized_allowed):
                    path_allowed = True
                    break
            except (OSError, ValueError):
                continue
        
        if not path_allowed:
            raise ValueError(f"Certificate path not in allowed directories: {cert_path}")
        
        # Ensure the file exists and is readable
        if not os.path.isfile(cert_path):
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        
        if not os.access(cert_path, os.R_OK):
            raise PermissionError(f"Certificate file not readable: {cert_path}")
        
        return cert_path
    
    def set_logger(self, logger):
        """Set logger for audit logging."""
        self.logger = logger


# Global instance
ssl_config_manager = SSLConfigManager()