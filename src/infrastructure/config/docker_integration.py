"""
Docker Configuration Integration - Docker Secrets and Environment Integration
===========================================================================
Docker-specific configuration management for containerized deployments:
- Docker Secrets integration
- Docker Compose environment variables
- Kubernetes ConfigMap/Secret integration
- Container health checks and readiness probes
- Multi-stage configuration loading
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime

from .configuration_manager import ConfigurationManager, ConfigSource, ConfigItem, Environment
from ..logging import get_logger, audit_logger

@dataclass
class DockerSecretConfig:
    """Configuration for Docker Secrets."""
    secrets_path: str = "/run/secrets"
    enabled: bool = True
    prefix: str = ""
    suffix: str = ""


@dataclass 
class KubernetesConfig:
    """Configuration for Kubernetes integration."""
    config_map_path: str = "/etc/config"
    secrets_path: str = "/etc/secrets"
    service_account_path: str = "/var/run/secrets/kubernetes.io/serviceaccount"
    namespace_file: str = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


class DockerSecretsProvider:
    """Docker Secrets configuration provider."""
    
    def __init__(self, config: DockerSecretConfig):
        self.config = config
        self.logger = get_logger("docker_secrets")
        self.secrets_path = Path(config.secrets_path)
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get secret from Docker Secrets."""
        if not self.config.enabled or not self.secrets_path.exists():
            return None
        
        # Construct secret file name
        secret_name = f"{self.config.prefix}{key}{self.config.suffix}"
        secret_file = self.secrets_path / secret_name
        
        try:
            if secret_file.exists():
                secret_value = secret_file.read_text().strip()
                
                self.logger.debug(f"Docker secret '{secret_name}' loaded")
                return secret_value
                
        except Exception as e:
            self.logger.error(f"Failed to read Docker secret '{secret_name}': {str(e)}")
        
        return None
    
    def list_available_secrets(self) -> List[str]:
        """List all available Docker secrets."""
        if not self.secrets_path.exists():
            return []
        
        try:
            return [f.name for f in self.secrets_path.iterdir() if f.is_file()]
        except Exception as e:
            self.logger.error(f"Failed to list Docker secrets: {str(e)}")
            return []


class KubernetesProvider:
    """Kubernetes ConfigMap and Secret provider."""
    
    def __init__(self, config: KubernetesConfig):
        self.config = config
        self.logger = get_logger("kubernetes_provider")
        self.config_map_path = Path(config.config_map_path)
        self.secrets_path = Path(config.secrets_path)
        self.namespace = self._get_namespace()
    
    def _get_namespace(self) -> Optional[str]:
        """Get current Kubernetes namespace."""
        try:
            namespace_file = Path(self.config.namespace_file)
            if namespace_file.exists():
                return namespace_file.read_text().strip()
        except Exception as e:
            self.logger.warning(f"Could not determine Kubernetes namespace: {str(e)}")
        return None
    
    async def get_config_value(self, key: str) -> Optional[str]:
        """Get configuration value from ConfigMap."""
        if not self.config_map_path.exists():
            return None
        
        try:
            config_file = self.config_map_path / key
            if config_file.exists():
                value = config_file.read_text().strip()
                self.logger.debug(f"Kubernetes ConfigMap value '{key}' loaded")
                return value
                
        except Exception as e:
            self.logger.error(f"Failed to read Kubernetes ConfigMap '{key}': {str(e)}")
        
        return None
    
    async def get_secret_value(self, key: str) -> Optional[str]:
        """Get secret value from Kubernetes Secret."""
        if not self.secrets_path.exists():
            return None
        
        try:
            secret_file = self.secrets_path / key
            if secret_file.exists():
                value = secret_file.read_text().strip()
                self.logger.debug(f"Kubernetes Secret '{key}' loaded")
                return value
                
        except Exception as e:
            self.logger.error(f"Failed to read Kubernetes Secret '{key}': {str(e)}")
        
        return None
    
    def get_pod_info(self) -> Dict[str, Any]:
        """Get information about the current pod."""
        pod_info = {
            "namespace": self.namespace,
            "hostname": os.getenv("HOSTNAME"),
            "node_name": os.getenv("NODE_NAME"),
            "pod_ip": os.getenv("POD_IP"),
            "service_account": self._get_service_account()
        }
        return {k: v for k, v in pod_info.items() if v is not None}
    
    def _get_service_account(self) -> Optional[str]:
        """Get service account name."""
        try:
            token_file = Path(self.config.service_account_path) / "token"
            if token_file.exists():
                # Service account info can be extracted from JWT token
                # For now, just return that it exists
                return "default"
        except Exception:
            pass
        return None


class ContainerConfigurationManager(ConfigurationManager):
    """Extended configuration manager for containerized environments."""
    
    def __init__(self, environment: Optional[Environment] = None):
        super().__init__(environment)
        
        # Container-specific providers
        self.docker_secrets = DockerSecretsProvider(
            DockerSecretConfig(
                secrets_path=os.getenv("DOCKER_SECRETS_PATH", "/run/secrets"),
                enabled=os.getenv("ENABLE_DOCKER_SECRETS", "true").lower() == "true"
            )
        )
        
        self.kubernetes = KubernetesProvider(
            KubernetesConfig(
                config_map_path=os.getenv("K8S_CONFIG_MAP_PATH", "/etc/config"),
                secrets_path=os.getenv("K8S_SECRETS_PATH", "/etc/secrets")
            )
        )
        
        # Container metadata
        self.container_info = self._get_container_info()
        self.logger = get_logger("container_config_manager")
        
        self.logger.info(
            f"Container configuration manager initialized",
            metadata={
                "environment": self.environment.value,
                "container_runtime": self._detect_container_runtime(),
                "orchestrator": self._detect_orchestrator(),
                **self.container_info
            }
        )
    
    def _get_container_info(self) -> Dict[str, Any]:
        """Get container runtime information."""
        container_info = {}
        
        # Docker information
        if Path("/.dockerenv").exists():
            container_info["runtime"] = "docker"
            container_info["container_id"] = os.getenv("HOSTNAME", "unknown")
        
        # Kubernetes information
        if Path("/var/run/secrets/kubernetes.io/serviceaccount").exists():
            container_info["orchestrator"] = "kubernetes"
            container_info.update(self.kubernetes.get_pod_info())
        
        # Additional container metadata
        container_info.update({
            "image": os.getenv("CONTAINER_IMAGE"),
            "version": os.getenv("CONTAINER_VERSION"),
            "build_date": os.getenv("CONTAINER_BUILD_DATE"),
            "commit_sha": os.getenv("GIT_COMMIT_SHA")
        })
        
        return {k: v for k, v in container_info.items() if v is not None}
    
    def _detect_container_runtime(self) -> str:
        """Detect container runtime."""
        if Path("/.dockerenv").exists():
            return "docker"
        elif os.getenv("KUBERNETES_SERVICE_HOST"):
            return "containerd"  # Likely containerd in K8s
        elif Path("/proc/1/cgroup").exists():
            try:
                with open("/proc/1/cgroup", "r") as f:
                    content = f.read()
                    if "docker" in content:
                        return "docker"
                    elif "containerd" in content:
                        return "containerd"
                    elif "crio" in content:
                        return "crio"
            except Exception:
                pass
        return "unknown"
    
    def _detect_orchestrator(self) -> Optional[str]:
        """Detect container orchestrator."""
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            return "kubernetes"
        elif os.getenv("DOCKER_SWARM_MODE"):
            return "docker-swarm"
        elif os.getenv("NOMAD_ADDR"):
            return "nomad"
        return None
    
    async def _get_from_docker_secrets(self, key: str) -> Optional[str]:
        """Get configuration from Docker Secrets."""
        return await self.docker_secrets.get_secret(key)
    
    async def _get_from_kubernetes_config(self, key: str) -> Optional[str]:
        """Get configuration from Kubernetes ConfigMap."""
        return await self.kubernetes.get_config_value(key)
    
    async def _get_from_kubernetes_secrets(self, key: str) -> Optional[str]:
        """Get configuration from Kubernetes Secrets."""
        return await self.kubernetes.get_secret_value(key)
    
    async def _load_config_item(self, key: str) -> Optional[ConfigItem]:
        """Load configuration item with container sources."""
        validation = self._get_validation_for_key(key)
        value = None
        source = ConfigSource.DEFAULT
        
        # Extended source priority for containers
        sources_to_try = [
            (ConfigSource.ENVIRONMENT_VARIABLES, self._get_from_env),
            ("docker_secrets", self._get_from_docker_secrets),
            ("kubernetes_secrets", self._get_from_kubernetes_secrets),
            ("kubernetes_config", self._get_from_kubernetes_config),
            (ConfigSource.VAULT, self._get_from_vault),
            (ConfigSource.AWS_SECRETS_MANAGER, self._get_from_aws_secrets),
            (ConfigSource.CONFIG_FILE, self._get_from_file),
        ]
        
        for config_source, getter in sources_to_try:
            try:
                value = await getter(key)
                if value is not None:
                    source = ConfigSource(config_source) if isinstance(config_source, str) and hasattr(ConfigSource, config_source.upper()) else config_source
                    break
            except Exception as e:
                self.logger.warning(f"Failed to get '{key}' from {config_source}: {str(e)}")
        
        # Use default value if none found
        if value is None and validation and not validation.required:
            value = self._get_default_value(key)
            source = ConfigSource.DEFAULT
        
        if value is not None:
            config_item = ConfigItem(
                key=key,
                value=value,
                source=source,
                environment=self.environment,
                sensitive=validation.sensitive if validation else False,
                last_updated=datetime.now(),
                validation=validation
            )
            
            # Encrypt sensitive values
            if validation and validation.sensitive:
                config_item.encrypted = True
                config_item.value = self.secret_manager.encrypt(str(value))
            
            self._config_items[key] = config_item
            return config_item
        
        return None
    
    async def get_container_health_info(self) -> Dict[str, Any]:
        """Get container health information for health checks."""
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "container_info": self.container_info,
            "configuration_status": {
                "total_items": len(self._config_items),
                "sensitive_items": len([item for item in self._config_items.values() if item.sensitive]),
                "source_distribution": self._get_source_distribution()
            }
        }
        
        # Check critical configuration items
        critical_keys = ["DATABASE_URL", "JWT_SECRET_KEY", "REDIS_URL"]
        missing_critical = [key for key in critical_keys if key not in self._config_items]
        
        if missing_critical:
            health_info["status"] = "unhealthy"
            health_info["missing_critical_config"] = missing_critical
        
        return health_info
    
    def _get_source_distribution(self) -> Dict[str, int]:
        """Get distribution of configuration sources."""
        distribution = {}
        for item in self._config_items.values():
            source_name = item.source.value if hasattr(item.source, 'value') else str(item.source)
            distribution[source_name] = distribution.get(source_name, 0) + 1
        return distribution
    
    async def validate_container_deployment(self) -> Dict[str, Any]:
        """Validate configuration for container deployment."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "container_info": self.container_info,
            "timestamp": datetime.now().isoformat()
        }
        
        # Check container-specific requirements
        if self.environment == Environment.PRODUCTION:
            # Production container validation
            if not self.container_info.get("orchestrator"):
                validation_result["warnings"].append("No container orchestrator detected in production")
            
            if not self.container_info.get("image"):
                validation_result["warnings"].append("Container image information not available")
            
            # Check for production-required secrets
            production_secrets = ["JWT_SECRET_KEY", "DATABASE_URL", "REDIS_URL"]
            for secret in production_secrets:
                if secret not in self._config_items:
                    validation_result["errors"].append(f"Required production secret '{secret}' not configured")
        
        # Check Docker secrets availability
        if self.docker_secrets.config.enabled:
            available_secrets = self.docker_secrets.list_available_secrets()
            validation_result["docker_secrets"] = {
                "enabled": True,
                "available_count": len(available_secrets),
                "secrets": available_secrets
            }
        
        # Check Kubernetes integration
        if self.container_info.get("orchestrator") == "kubernetes":
            k8s_info = self.kubernetes.get_pod_info()
            validation_result["kubernetes_info"] = k8s_info
        
        if validation_result["errors"]:
            validation_result["valid"] = False
        
        return validation_result


# Global container configuration manager instance
container_config_manager = ContainerConfigurationManager()


def create_container_health_check():
    """Create a health check endpoint for containers."""
    async def container_health():
        """Container health check endpoint."""
        try:
            health_info = await container_config_manager.get_container_health_info()
            
            if health_info["status"] == "healthy":
                return health_info
            else:
                from fastapi import HTTPException
                raise HTTPException(status_code=503, detail=health_info)
                
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503, 
                detail={
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    return container_health


def create_container_readiness_check():
    """Create a readiness check endpoint for containers."""
    async def container_readiness():
        """Container readiness check endpoint."""
        try:
            # Check if configuration is loaded
            if not container_config_manager._config_items:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail={
                        "ready": False,
                        "reason": "Configuration not loaded",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Validate container deployment
            validation_result = await container_config_manager.validate_container_deployment()
            
            if validation_result["valid"]:
                return {
                    "ready": True,
                    "timestamp": datetime.now().isoformat(),
                    "config_items": len(container_config_manager._config_items)
                }
            else:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail={
                        "ready": False,
                        "validation_errors": validation_result["errors"],
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    return container_readiness


def add_container_routes(app):
    """Add container-specific health and readiness routes."""
    from fastapi import FastAPI
    
    # Health check (liveness probe)
    app.add_api_route(
        "/health",
        create_container_health_check(),
        methods=["GET"],
        tags=["Container Health"]
    )
    
    # Readiness check (readiness probe)
    app.add_api_route(
        "/ready", 
        create_container_readiness_check(),
        methods=["GET"],
        tags=["Container Health"]
    )
    
    # Container info endpoint
    @app.get("/container-info", tags=["Container Health"])
    async def get_container_info():
        """Get container information."""
        return {
            "container_info": container_config_manager.container_info,
            "environment": container_config_manager.environment.value,
            "config_sources": container_config_manager._get_source_distribution(),
            "timestamp": datetime.now().isoformat()
        }
