#!/usr/bin/env python3
"""
COPPA Compliance Validation Script for AI Teddy Bear
Validates COPPA compliance requirements throughout the deployment process
"""

import os
import sys
import json
import yaml
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess
import requests
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ComplianceResult:
    """Result of a compliance check"""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class COPPAComplianceChecker:
    """
    Comprehensive COPPA compliance checker for AI Teddy Bear deployment
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results: List[ComplianceResult] = []
        
        # COPPA compliance requirements
        self.coppa_requirements = {
            "data_retention_max_days": 90,
            "required_encryption": ["at_rest", "in_transit"],
            "required_audit_logging": True,
            "parental_consent_required": True,
            "content_filtering_strict": True,
            "data_minimization": True,
            "secure_data_transmission": True,
            "access_controls": True,
            "vulnerability_scanning": True
        }
        
        # Child safety requirements
        self.child_safety_requirements = {
            "content_filtering": True,
            "age_appropriate_responses": True,
            "harmful_content_blocking": True,
            "inappropriate_interaction_prevention": True,
            "safety_monitoring": True,
            "emergency_contact_system": True
        }
    
    def run_all_checks(self) -> bool:
        """Run all COPPA compliance checks"""
        logger.info("Starting COPPA compliance validation...")
        
        # Configuration checks
        self._check_environment_configuration()
        self._check_docker_configuration()
        self._check_kubernetes_configuration()
        self._check_database_configuration()
        
        # Security checks
        self._check_encryption_configuration()
        self._check_data_retention_policies()
        self._check_audit_logging()
        self._check_access_controls()
        
        # Child safety checks
        self._check_child_safety_features()
        self._check_content_filtering()
        self._check_age_verification()
        
        # Infrastructure checks
        self._check_network_security()
        self._check_storage_security()
        self._check_monitoring_configuration()
        
        # Code compliance checks
        self._check_code_compliance()
        self._check_dependency_compliance()
        
        # Generate final report
        return self._generate_compliance_report()
    
    def _check_environment_configuration(self) -> None:
        """Check environment configuration for COPPA compliance"""
        logger.info("Checking environment configuration...")
        
        # Check environment files
        env_files = [
            self.project_root / ".env.example",
            self.project_root / "config" / "production.yaml",
            self.project_root / "config" / "staging.yaml"
        ]
        
        for env_file in env_files:
            if env_file.exists():
                self._validate_env_file(env_file)
    
    def _validate_env_file(self, env_file: Path) -> None:
        """Validate individual environment file for COPPA compliance"""
        try:
            with open(env_file, 'r') as f:
                if env_file.suffix == '.yaml' or env_file.suffix == '.yml':
                    config = yaml.safe_load(f)
                else:
                    # Parse .env file
                    config = {}
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            config[key] = value
            
            # Check COPPA compliance settings
            coppa_checks = [
                ("COPPA_COMPLIANCE_MODE", "true"),
                ("CONTENT_FILTER_STRICT", "true"),
                ("DATA_RETENTION_DAYS", lambda x: int(x) <= 90 if x.isdigit() else False),
                ("CHILD_SAFETY_STRICT", "true"),
                ("AUDIT_LOGGING_ENABLED", "true")
            ]
            
            for check_key, expected_value in coppa_checks:
                if isinstance(expected_value, str):
                    if config.get(check_key, "").lower() != expected_value.lower():
                        self.results.append(ComplianceResult(
                            f"env_config_{check_key.lower()}",
                            False,
                            f"Environment variable {check_key} must be set to {expected_value} in {env_file.name}",
                            {"file": str(env_file), "current_value": config.get(check_key, "Not set")}
                        ))
                    else:
                        self.results.append(ComplianceResult(
                            f"env_config_{check_key.lower()}",
                            True,
                            f"Environment variable {check_key} correctly configured in {env_file.name}"
                        ))
                elif callable(expected_value):
                    value = config.get(check_key, "")
                    if not expected_value(value):
                        self.results.append(ComplianceResult(
                            f"env_config_{check_key.lower()}",
                            False,
                            f"Environment variable {check_key} value {value} does not meet COPPA requirements in {env_file.name}",
                            {"file": str(env_file), "current_value": value}
                        ))
                    else:
                        self.results.append(ComplianceResult(
                            f"env_config_{check_key.lower()}",
                            True,
                            f"Environment variable {check_key} meets COPPA requirements in {env_file.name}"
                        ))
            
        except Exception as e:
            self.results.append(ComplianceResult(
                f"env_file_parse_{env_file.name}",
                False,
                f"Failed to parse environment file {env_file.name}: {str(e)}"
            ))
    
    def _check_docker_configuration(self) -> None:
        """Check Docker configuration for COPPA compliance"""
        logger.info("Checking Docker configuration...")
        
        dockerfile_path = self.project_root / "Dockerfile"
        if dockerfile_path.exists():
            self._validate_dockerfile(dockerfile_path)
        
        compose_files = [
            self.project_root / "docker-compose.yml",
            self.project_root / "docker-compose.production.yml"
        ]
        
        for compose_file in compose_files:
            if compose_file.exists():
                self._validate_docker_compose(compose_file)
    
    def _validate_dockerfile(self, dockerfile_path: Path) -> None:
        """Validate Dockerfile for security and compliance"""
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()
            
            # Check for security best practices
            security_checks = [
                (r'USER\s+(?:root|\$\{.*\})', False, "Should not run as root user"),
                (r'LABEL.*coppa\.compliant.*true', True, "Should have COPPA compliance label"),
                (r'LABEL.*child\.safety\.validated.*true', True, "Should have child safety validation label"),
                (r'HEALTHCHECK', True, "Should include health check"),
                (r'--chown=', True, "Should use proper file ownership")
            ]
            
            for pattern, should_match, message in security_checks:
                matches = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                if should_match and not matches:
                    self.results.append(ComplianceResult(
                        f"dockerfile_{pattern.replace(r'\\', '_').replace('.*', '_').replace(r'\s+', '_')}",
                        False,
                        f"Dockerfile security issue: {message}",
                        {"file": str(dockerfile_path)}
                    ))
                elif not should_match and matches:
                    self.results.append(ComplianceResult(
                        f"dockerfile_{pattern.replace(r'\\', '_').replace('.*', '_').replace(r'\s+', '_')}",
                        False,
                        f"Dockerfile security issue: {message}",
                        {"file": str(dockerfile_path), "match": matches.group()}
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"dockerfile_{pattern.replace(r'\\', '_').replace('.*', '_').replace(r'\s+', '_')}",
                        True,
                        f"Dockerfile check passed: {message}"
                    ))
                    
        except Exception as e:
            self.results.append(ComplianceResult(
                "dockerfile_parse",
                False,
                f"Failed to parse Dockerfile: {str(e)}"
            ))
    
    def _validate_docker_compose(self, compose_file: Path) -> None:
        """Validate Docker Compose file for COPPA compliance"""
        try:
            with open(compose_file, 'r') as f:
                compose_config = yaml.safe_load(f)
            
            # Check for required environment variables
            services = compose_config.get('services', {})
            app_service = services.get('app', {})
            environment = app_service.get('environment', [])
            
            # Convert list format to dict if needed
            if isinstance(environment, list):
                env_dict = {}
                for env_var in environment:
                    if '=' in env_var:
                        key, value = env_var.split('=', 1)
                        env_dict[key] = value
                environment = env_dict
            
            required_env_vars = [
                "COPPA_COMPLIANCE_MODE",
                "CONTENT_FILTER_STRICT", 
                "CHILD_SAFETY_STRICT",
                "COPPA_ENCRYPTION_KEY"
            ]
            
            for env_var in required_env_vars:
                if env_var not in environment:
                    self.results.append(ComplianceResult(
                        f"compose_env_{env_var.lower()}",
                        False,
                        f"Required COPPA environment variable {env_var} not found in {compose_file.name}",
                        {"file": str(compose_file)}
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"compose_env_{env_var.lower()}",
                        True,
                        f"Required COPPA environment variable {env_var} found in {compose_file.name}"
                    ))
            
        except Exception as e:
            self.results.append(ComplianceResult(
                f"compose_parse_{compose_file.name}",
                False,
                f"Failed to parse Docker Compose file {compose_file.name}: {str(e)}"
            ))
    
    def _check_kubernetes_configuration(self) -> None:
        """Check Kubernetes configuration for COPPA compliance"""
        logger.info("Checking Kubernetes configuration...")
        
        k8s_dir = self.project_root / "deployment" / "kubernetes"
        if k8s_dir.exists():
            for yaml_file in k8s_dir.glob("*.yaml"):
                self._validate_kubernetes_manifest(yaml_file)
    
    def _validate_kubernetes_manifest(self, manifest_file: Path) -> None:
        """Validate individual Kubernetes manifest for COPPA compliance"""
        try:
            with open(manifest_file, 'r') as f:
                # Handle multiple YAML documents
                documents = list(yaml.safe_load_all(f))
            
            for doc in documents:
                if not doc:
                    continue
                
                kind = doc.get('kind', '')
                metadata = doc.get('metadata', {})
                labels = metadata.get('labels', {})
                annotations = metadata.get('annotations', {})
                
                # Check for COPPA compliance labels
                required_labels = [
                    "coppa.compliant",
                    "child.safety.validated"
                ]
                
                for label in required_labels:
                    if label not in labels or labels[label].lower() != "true":
                        self.results.append(ComplianceResult(
                            f"k8s_label_{kind.lower()}_{label.replace('.', '_')}",
                            False,
                            f"Kubernetes {kind} missing required label {label}=true in {manifest_file.name}",
                            {"file": str(manifest_file), "kind": kind}
                        ))
                    else:
                        self.results.append(ComplianceResult(
                            f"k8s_label_{kind.lower()}_{label.replace('.', '_')}",
                            True,
                            f"Kubernetes {kind} has required label {label}=true in {manifest_file.name}"
                        ))
                
                # Check for child safety annotations
                if kind in ['Deployment', 'StatefulSet', 'DaemonSet']:
                    spec = doc.get('spec', {})
                    template = spec.get('template', {})
                    template_metadata = template.get('metadata', {})
                    template_annotations = template_metadata.get('annotations', {})
                    
                    child_safety_annotations = [
                        "child-safety.compliance/coppa",
                        "child-safety.monitoring/enabled"
                    ]
                    
                    for annotation in child_safety_annotations:
                        if annotation not in template_annotations:
                            self.results.append(ComplianceResult(
                                f"k8s_annotation_{kind.lower()}_{annotation.replace('/', '_').replace('-', '_')}",
                                False,
                                f"Kubernetes {kind} missing child safety annotation {annotation} in {manifest_file.name}",
                                {"file": str(manifest_file), "kind": kind}
                            ))
                        else:
                            self.results.append(ComplianceResult(
                                f"k8s_annotation_{kind.lower()}_{annotation.replace('/', '_').replace('-', '_')}",
                                True,
                                f"Kubernetes {kind} has child safety annotation {annotation} in {manifest_file.name}"
                            ))
                
        except Exception as e:
            self.results.append(ComplianceResult(
                f"k8s_manifest_parse_{manifest_file.name}",
                False,
                f"Failed to parse Kubernetes manifest {manifest_file.name}: {str(e)}"
            ))
    
    def _check_database_configuration(self) -> None:
        """Check database configuration for COPPA compliance"""
        logger.info("Checking database configuration...")
        
        # Check Alembic configuration
        alembic_ini = self.project_root / "alembic.ini"
        if alembic_ini.exists():
            self._validate_alembic_config(alembic_ini)
        
        # Check database models for COPPA compliance
        self._check_database_models()
    
    def _validate_alembic_config(self, alembic_ini: Path) -> None:
        """Validate Alembic configuration for COPPA compliance"""
        try:
            with open(alembic_ini, 'r') as f:
                content = f.read()
            
            # Check for secure configuration
            if "sqlalchemy.url" in content and "password" in content.lower():
                # Should use environment variables for passwords
                if "${" not in content:
                    self.results.append(ComplianceResult(
                        "alembic_password_security",
                        False,
                        "Alembic configuration should use environment variables for database passwords",
                        {"file": str(alembic_ini)}
                    ))
                else:
                    self.results.append(ComplianceResult(
                        "alembic_password_security",
                        True,
                        "Alembic configuration uses environment variables for database passwords"
                    ))
            
        except Exception as e:
            self.results.append(ComplianceResult(
                "alembic_parse",
                False,
                f"Failed to parse Alembic configuration: {str(e)}"
            ))
    
    def _check_database_models(self) -> None:
        """Check database models for COPPA compliance"""
        models_dir = self.project_root / "src" / "core"
        if models_dir.exists():
            for py_file in models_dir.glob("*.py"):
                if "model" in py_file.name.lower():
                    self._validate_model_file(py_file)
    
    def _validate_model_file(self, model_file: Path) -> None:
        """Validate individual model file for COPPA compliance"""
        try:
            with open(model_file, 'r') as f:
                content = f.read()
            
            # Check for child data handling
            if "child" in content.lower() or "kid" in content.lower() or "minor" in content.lower():
                # Should have proper encryption and retention
                compliance_patterns = [
                    (r'created_at.*datetime', True, "Child data models should have timestamp fields"),
                    (r'encrypted.*True', True, "Child data should be encrypted"),
                    (r'retention.*days', True, "Child data should have retention policies")
                ]
                
                for pattern, should_match, message in compliance_patterns:
                    matches = re.search(pattern, content, re.IGNORECASE)
                    if should_match and not matches:
                        self.results.append(ComplianceResult(
                            f"model_child_data_{pattern.replace(r'\\', '_').replace('.*', '_')}",
                            False,
                            f"Child data model issue: {message} in {model_file.name}",
                            {"file": str(model_file)}
                        ))
            
        except Exception as e:
            self.results.append(ComplianceResult(
                f"model_parse_{model_file.name}",
                False,
                f"Failed to parse model file {model_file.name}: {str(e)}"
            ))
    
    def _check_encryption_configuration(self) -> None:
        """Check encryption configuration for COPPA compliance"""
        logger.info("Checking encryption configuration...")
        
        # Check for encryption keys in environment
        required_encryption_vars = [
            "COPPA_ENCRYPTION_KEY",
            "SECRET_KEY",
            "JWT_SECRET_KEY"
        ]
        
        for var in required_encryption_vars:
            # Check if variable is referenced in configuration files
            found = False
            for config_file in self.project_root.rglob("*.yaml"):
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                        if var in content:
                            found = True
                            break
                except:
                    continue
            
            if found:
                self.results.append(ComplianceResult(
                    f"encryption_key_{var.lower()}",
                    True,
                    f"Encryption variable {var} is configured"
                ))
            else:
                self.results.append(ComplianceResult(
                    f"encryption_key_{var.lower()}",
                    False,
                    f"Required encryption variable {var} not found in configuration",
                    {"variable": var}
                ))
    
    def _check_data_retention_policies(self) -> None:
        """Check data retention policies for COPPA compliance"""
        logger.info("Checking data retention policies...")
        
        # Check for data retention configuration
        retention_checks = [
            ("DATA_RETENTION_DAYS", 90),
            ("AUTO_DELETE_ENABLED", "true"),
            ("BACKUP_RETENTION_DAYS", 30)
        ]
        
        for var_name, max_value in retention_checks:
            found = False
            for config_file in self.project_root.rglob("*.yaml"):
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                        if var_name in content:
                            found = True
                            # Extract value if possible
                            match = re.search(f'{var_name}.*?(\d+)', content)
                            if match and isinstance(max_value, int):
                                value = int(match.group(1))
                                if value <= max_value:
                                    self.results.append(ComplianceResult(
                                        f"retention_{var_name.lower()}",
                                        True,
                                        f"Data retention {var_name} is compliant ({value} <= {max_value} days)"
                                    ))
                                else:
                                    self.results.append(ComplianceResult(
                                        f"retention_{var_name.lower()}",
                                        False,
                                        f"Data retention {var_name} exceeds COPPA limit ({value} > {max_value} days)",
                                        {"current_value": value, "max_allowed": max_value}
                                    ))
                            break
                except:
                    continue
            
            if not found:
                self.results.append(ComplianceResult(
                    f"retention_{var_name.lower()}",
                    False,
                    f"Data retention policy {var_name} not configured",
                    {"variable": var_name}
                ))
    
    def _check_audit_logging(self) -> None:
        """Check audit logging configuration for COPPA compliance"""
        logger.info("Checking audit logging configuration...")
        
        # Check logging configuration
        logging_config_files = [
            self.project_root / "config" / "logging.yaml",
            self.project_root / "deployment" / "kubernetes" / "configmap.yaml"
        ]
        
        for config_file in logging_config_files:
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                    
                    # Check for child safety and audit logging
                    audit_patterns = [
                        "child_safety",
                        "security",
                        "audit",
                        "compliance"
                    ]
                    
                    for pattern in audit_patterns:
                        if pattern in content.lower():
                            self.results.append(ComplianceResult(
                                f"audit_logging_{pattern}",
                                True,
                                f"Audit logging configured for {pattern} in {config_file.name}"
                            ))
                        else:
                            self.results.append(ComplianceResult(
                                f"audit_logging_{pattern}",
                                False,
                                f"Audit logging missing for {pattern} in {config_file.name}",
                                {"file": str(config_file), "pattern": pattern}
                            ))
                
                except Exception as e:
                    self.results.append(ComplianceResult(
                        f"audit_config_parse_{config_file.name}",
                        False,
                        f"Failed to parse logging configuration {config_file.name}: {str(e)}"
                    ))
    
    def _check_access_controls(self) -> None:
        """Check access controls for COPPA compliance"""
        logger.info("Checking access controls...")
        
        # Check for security configurations
        security_files = [
            self.project_root / "src" / "infrastructure" / "security",
            self.project_root / "deployment" / "kubernetes" / "rbac.yaml"
        ]
        
        for security_path in security_files:
            if security_path.exists():
                if security_path.is_dir():
                    for py_file in security_path.glob("*.py"):
                        self._validate_security_file(py_file)
                else:
                    self._validate_security_file(security_path)
    
    def _validate_security_file(self, security_file: Path) -> None:
        """Validate security configuration file"""
        try:
            with open(security_file, 'r') as f:
                content = f.read()
            
            security_patterns = [
                (r'authentication', True, "Should have authentication controls"),
                (r'authorization', True, "Should have authorization controls"), 
                (r'rate.?limit', True, "Should have rate limiting"),
                (r'cors', True, "Should have CORS configuration")
            ]
            
            for pattern, should_exist, message in security_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"security_{pattern.replace('?', '_')}",
                        True,
                        f"Security control found: {message} in {security_file.name}"
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"security_{pattern.replace('?', '_')}",
                        False,
                        f"Security control missing: {message} in {security_file.name}",
                        {"file": str(security_file)}
                    ))
                    
        except Exception as e:
            self.results.append(ComplianceResult(
                f"security_parse_{security_file.name}",
                False,
                f"Failed to parse security file {security_file.name}: {str(e)}"
            ))
    
    def _check_child_safety_features(self) -> None:
        """Check child safety features implementation"""
        logger.info("Checking child safety features...")
        
        # Check for child safety service implementation
        child_safety_files = [
            self.project_root / "src" / "application" / "services" / "child_safety_service.py",
            self.project_root / "src" / "core" / "security_service.py"
        ]
        
        for safety_file in child_safety_files:
            if safety_file.exists():
                self._validate_child_safety_service(safety_file)
    
    def _validate_child_safety_service(self, safety_file: Path) -> None:
        """Validate child safety service implementation"""
        try:
            with open(safety_file, 'r') as f:
                content = f.read()
            
            safety_features = [
                ("content.?filter", "Content filtering functionality"),
                ("age.?verification", "Age verification system"),
                ("parental.?consent", "Parental consent handling"),
                ("inappropriate.?content", "Inappropriate content detection"),
                ("safety.?score", "Safety scoring system"),
                ("block.?harmful", "Harmful content blocking")
            ]
            
            for pattern, description in safety_features:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"child_safety_{pattern.replace('?', '_')}",
                        True,
                        f"Child safety feature implemented: {description} in {safety_file.name}"
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"child_safety_{pattern.replace('?', '_')}",
                        False,
                        f"Child safety feature missing: {description} in {safety_file.name}",
                        {"file": str(safety_file), "feature": description}
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"child_safety_parse_{safety_file.name}",
                False,
                f"Failed to parse child safety file {safety_file.name}: {str(e)}"
            ))
    
    def _check_content_filtering(self) -> None:
        """Check content filtering implementation"""
        logger.info("Checking content filtering...")
        
        # Look for content filtering in application services
        content_filter_files = list(self.project_root.rglob("*content*filter*.py"))
        content_filter_files.extend(list(self.project_root.rglob("*filter*.py")))
        
        if not content_filter_files:
            self.results.append(ComplianceResult(
                "content_filtering_implementation",
                False,
                "No content filtering implementation found",
                {"expected_files": "content_filter.py or similar"}
            ))
        else:
            for filter_file in content_filter_files:
                self._validate_content_filter(filter_file)
    
    def _validate_content_filter(self, filter_file: Path) -> None:
        """Validate content filter implementation"""
        try:
            with open(filter_file, 'r') as f:
                content = f.read()
            
            filter_features = [
                ("profanity", "Profanity filtering"),
                ("harmful", "Harmful content detection"),
                ("inappropriate", "Inappropriate content blocking"),
                ("age.?appropriate", "Age-appropriate content validation"),
                ("safety.?check", "Safety checking mechanism")
            ]
            
            for pattern, description in filter_features:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"content_filter_{pattern.replace('?', '_')}",
                        True,
                        f"Content filter feature: {description} found in {filter_file.name}"
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"content_filter_{pattern.replace('?', '_')}",
                        False,
                        f"Content filter feature missing: {description} in {filter_file.name}",
                        {"file": str(filter_file), "feature": description}
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"content_filter_parse_{filter_file.name}",
                False,
                f"Failed to parse content filter file {filter_file.name}: {str(e)}"
            ))
    
    def _check_age_verification(self) -> None:
        """Check age verification system"""
        logger.info("Checking age verification system...")
        
        # Look for age verification implementation
        age_verification_patterns = [
            "age.*verification",
            "parental.*consent",
            "guardian.*approval",
            "child.*age.*validation"
        ]
        
        found_age_verification = False
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                for pattern in age_verification_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        found_age_verification = True
                        self.results.append(ComplianceResult(
                            f"age_verification_{pattern.replace('.*', '_')}",
                            True,
                            f"Age verification feature found: {pattern} in {py_file.name}"
                        ))
                        break
            except:
                continue
        
        if not found_age_verification:
            self.results.append(ComplianceResult(
                "age_verification_system",
                False,
                "Age verification system not found in codebase",
                {"required": "Age verification and parental consent system"}
            ))
    
    def _check_network_security(self) -> None:
        """Check network security configuration"""
        logger.info("Checking network security...")
        
        # Check for network policies and security groups
        network_files = [
            self.project_root / "deployment" / "kubernetes" / "network-policy.yaml",
            self.project_root / "terraform" / "modules" / "security" / "main.tf"
        ]
        
        for network_file in network_files:
            if network_file.exists():
                self._validate_network_security_file(network_file)
    
    def _validate_network_security_file(self, network_file: Path) -> None:
        """Validate network security configuration"""
        try:
            with open(network_file, 'r') as f:
                content = f.read()
            
            security_features = [
                ("NetworkPolicy", "Kubernetes network policies"),
                ("security.group", "Security group configuration"),
                ("ingress", "Ingress rules"),
                ("egress", "Egress rules"),
                ("deny.all", "Default deny policies")
            ]
            
            for pattern, description in security_features:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"network_security_{pattern.replace('.', '_')}",
                        True,
                        f"Network security feature: {description} found in {network_file.name}"
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"network_security_parse_{network_file.name}",
                False,
                f"Failed to parse network security file {network_file.name}: {str(e)}"
            ))
    
    def _check_storage_security(self) -> None:
        """Check storage security configuration"""
        logger.info("Checking storage security...")
        
        # Check for encrypted storage configuration
        storage_files = [
            self.project_root / "deployment" / "kubernetes" / "pvc.yaml",
            self.project_root / "terraform" / "modules" / "s3" / "main.tf",
            self.project_root / "terraform" / "modules" / "rds" / "main.tf"
        ]
        
        for storage_file in storage_files:
            if storage_file.exists():
                self._validate_storage_security(storage_file)
    
    def _validate_storage_security(self, storage_file: Path) -> None:
        """Validate storage security configuration"""
        try:
            with open(storage_file, 'r') as f:
                content = f.read()
            
            # Check for encryption configuration
            encryption_patterns = [
                ("encrypted.*true", "Encryption enabled"),
                ("kms.key", "KMS key configuration"),
                ("encryption.at.rest", "Encryption at rest"),
                ("storageClassName.*encrypted", "Encrypted storage class")
            ]
            
            for pattern, description in encryption_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"storage_security_{pattern.replace('.', '_').replace('.*', '_')}",
                        True,
                        f"Storage security feature: {description} found in {storage_file.name}"
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"storage_security_parse_{storage_file.name}",
                False,
                f"Failed to parse storage security file {storage_file.name}: {str(e)}"
            ))
    
    def _check_monitoring_configuration(self) -> None:
        """Check monitoring configuration for COPPA compliance"""
        logger.info("Checking monitoring configuration...")
        
        # Check for monitoring and alerting
        monitoring_files = [
            self.project_root / "deployment" / "kubernetes" / "monitoring.yaml",
            self.project_root / "terraform" / "modules" / "cloudwatch" / "main.tf"
        ]
        
        for monitoring_file in monitoring_files:
            if monitoring_file.exists():
                self._validate_monitoring_config(monitoring_file)
    
    def _validate_monitoring_config(self, monitoring_file: Path) -> None:
        """Validate monitoring configuration"""
        try:
            with open(monitoring_file, 'r') as f:
                content = f.read()
            
            monitoring_features = [
                ("child.safety.*alert", "Child safety alerts"),
                ("coppa.*compliance.*monitoring", "COPPA compliance monitoring"),
                ("security.*monitoring", "Security monitoring"),
                ("audit.*logging", "Audit logging"),
                ("data.*retention.*alert", "Data retention alerts")
            ]
            
            for pattern, description in monitoring_features:
                if re.search(pattern, content, re.IGNORECASE):
                    self.results.append(ComplianceResult(
                        f"monitoring_{pattern.replace('.*', '_').replace('.', '_')}",
                        True,
                        f"Monitoring feature: {description} found in {monitoring_file.name}"
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"monitoring_parse_{monitoring_file.name}",
                False,
                f"Failed to parse monitoring file {monitoring_file.name}: {str(e)}"
            ))
    
    def _check_code_compliance(self) -> None:
        """Check code compliance with COPPA requirements"""
        logger.info("Checking code compliance...")
        
        # Check for COPPA-related imports and usage
        for py_file in self.project_root.rglob("*.py"):
            if "test" not in str(py_file) and "__pycache__" not in str(py_file):
                self._validate_code_file(py_file)
    
    def _validate_code_file(self, code_file: Path) -> None:
        """Validate individual code file for COPPA compliance"""
        try:
            with open(code_file, 'r') as f:
                content = f.read()
            
            # Check for proper child data handling
            if "child" in content.lower() or "kid" in content.lower():
                compliance_patterns = [
                    ("encrypt", "Encryption usage"),
                    ("validate", "Data validation"),
                    ("sanitize", "Data sanitization"),
                    ("audit", "Audit logging")
                ]
                
                for pattern, description in compliance_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        self.results.append(ComplianceResult(
                            f"code_compliance_{pattern}_{code_file.stem}",
                            True,
                            f"Code compliance: {description} found in {code_file.name}"
                        ))
        
        except Exception as e:
            # Skip binary files or files that can't be read
            pass
    
    def _check_dependency_compliance(self) -> None:
        """Check dependency compliance and security"""
        logger.info("Checking dependency compliance...")
        
        requirements_files = [
            self.project_root / "requirements.txt",
            self.project_root / "requirements-prod.txt"
        ]
        
        for req_file in requirements_files:
            if req_file.exists():
                self._validate_requirements_file(req_file)
    
    def _validate_requirements_file(self, req_file: Path) -> None:
        """Validate requirements file for security and compliance"""
        try:
            with open(req_file, 'r') as f:
                requirements = f.readlines()
            
            # Check for security-related packages
            security_packages = [
                "cryptography",
                "bcrypt", 
                "pyjwt",
                "authlib"
            ]
            
            found_packages = []
            for line in requirements:
                package_name = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                if package_name.lower() in [p.lower() for p in security_packages]:
                    found_packages.append(package_name)
            
            for package in security_packages:
                if package.lower() in [p.lower() for p in found_packages]:
                    self.results.append(ComplianceResult(
                        f"dependency_{package}",
                        True,
                        f"Security package {package} found in {req_file.name}"
                    ))
                else:
                    self.results.append(ComplianceResult(
                        f"dependency_{package}",
                        False,
                        f"Security package {package} missing from {req_file.name}",
                        {"file": str(req_file), "package": package}
                    ))
        
        except Exception as e:
            self.results.append(ComplianceResult(
                f"requirements_parse_{req_file.name}",
                False,
                f"Failed to parse requirements file {req_file.name}: {str(e)}"
            ))
    
    def _generate_compliance_report(self) -> bool:
        """Generate final compliance report"""
        logger.info("Generating compliance report...")
        
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results if result.passed)
        failed_checks = total_checks - passed_checks
        
        compliance_percentage = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": failed_checks,
                "compliance_percentage": round(compliance_percentage, 2)
            },
            "coppa_compliant": compliance_percentage >= 95,  # Require 95% compliance
            "results": [
                {
                    "check_name": result.check_name,
                    "passed": result.passed,
                    "message": result.message,
                    "details": result.details
                }
                for result in self.results
            ]
        }
        
        # Save report
        report_file = self.project_root / "coppa_compliance_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*50}")
        print("COPPA COMPLIANCE REPORT")
        print(f"{'='*50}")
        print(f"Total Checks: {total_checks}")
        print(f"Passed: {passed_checks}")
        print(f"Failed: {failed_checks}")
        print(f"Compliance: {compliance_percentage:.1f}%")
        print(f"COPPA Compliant: {'✅ YES' if report['coppa_compliant'] else '❌ NO'}")
        
        if failed_checks > 0:
            print(f"\n{'='*30}")
            print("FAILED CHECKS:")
            print(f"{'='*30}")
            for result in self.results:
                if not result.passed:
                    print(f"❌ {result.check_name}: {result.message}")
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return report['coppa_compliant']

def main():
    """Main function to run COPPA compliance checks"""
    import argparse
    
    parser = argparse.ArgumentParser(description='COPPA Compliance Checker for AI Teddy Bear')
    parser.add_argument('--project-root', default='.', help='Project root directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    checker = COPPAComplianceChecker(args.project_root)
    is_compliant = checker.run_all_checks()
    
    sys.exit(0 if is_compliant else 1)

if __name__ == "__main__":
    main()