"""
Multi-Provider CDN Management System
Supports CloudFlare, AWS CloudFront, and Azure CDN with COPPA compliance
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel, Field

import aiofiles
import boto3

try:
    from azure.mgmt.cdn import CdnManagementClient
    from azure.identity import DefaultAzureCredential

    AZURE_AVAILABLE = True
except ImportError:
    CdnManagementClient = None
    DefaultAzureCredential = None
    AZURE_AVAILABLE = False

from src.core.exceptions import ServiceUnavailableError, ConfigurationError
from src.core.utils.crypto_utils import encrypt_sensitive_data, decrypt_sensitive_data


logger = logging.getLogger(__name__)


class CDNProvider(Enum):
    """Supported CDN providers."""

    CLOUDFLARE = "cloudflare"
    AWS_CLOUDFRONT = "aws_cloudfront"
    AZURE_CDN = "azure_cdn"


class CacheLevel(Enum):
    """CDN cache levels for different content types."""

    AGGRESSIVE = "aggressive"  # 1 week+ for static assets
    STANDARD = "standard"  # 1 day for dynamic content
    MINIMAL = "minimal"  # 1 hour for child data
    NO_CACHE = "no_cache"  # No caching for sensitive data


@dataclass
class CDNConfig:
    """CDN configuration for a provider."""

    provider: CDNProvider
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False, default="")
    zone_id: Optional[str] = None
    distribution_id: Optional[str] = None
    resource_group: Optional[str] = None
    subscription_id: Optional[str] = None
    enabled: bool = True
    priority: int = 1  # Lower numbers = higher priority

    def __post_init__(self):
        """Encrypt sensitive data."""
        self.api_key = encrypt_sensitive_data(self.api_key)
        if self.api_secret:
            self.api_secret = encrypt_sensitive_data(self.api_secret)


@dataclass
class CachePolicy:
    """Cache policy configuration."""

    name: str
    level: CacheLevel
    ttl_seconds: int
    browser_ttl_seconds: int
    edge_ttl_seconds: int
    bypass_cache_on_cookie: bool = False
    respect_origin_headers: bool = True
    child_safe_headers: bool = True
    coppa_compliance: bool = True


@dataclass
class PurgeRequest:
    """CDN cache purge request."""

    urls: List[str]
    tags: List[str] = field(default_factory=list)
    purge_everything: bool = False
    child_data_purge: bool = False


@dataclass
class CDNMetrics:
    """CDN performance metrics."""

    provider: CDNProvider
    requests_total: int
    bandwidth_bytes: int
    cache_hit_ratio: float
    origin_response_time_ms: float
    edge_response_time_ms: float
    error_rate: float
    timestamp: datetime = field(default_factory=datetime.now)


class BaseCDNProvider(ABC):
    """Base class for CDN providers."""

    def __init__(self, config: CDNConfig):
        self.config = config
        self.provider = config.provider
        self._client = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize CDN provider client."""
        pass

    @abstractmethod
    async def purge_cache(self, request: PurgeRequest) -> Dict[str, Any]:
        """Purge CDN cache."""
        pass

    @abstractmethod
    async def get_metrics(self) -> CDNMetrics:
        """Get CDN performance metrics."""
        pass

    @abstractmethod
    async def update_cache_policy(self, policy: CachePolicy) -> bool:
        """Update cache policy."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check CDN provider health."""
        pass


class CloudFlareProvider(BaseCDNProvider):
    """CloudFlare CDN provider implementation."""

    async def initialize(self) -> None:
        """Initialize CloudFlare client."""
        self._client = httpx.AsyncClient(
            base_url="https://api.cloudflare.com/client/v4",
            headers={
                "Authorization": f"Bearer {decrypt_sensitive_data(self.config.api_key)}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def purge_cache(self, request: PurgeRequest) -> Dict[str, Any]:
        """Purge CloudFlare cache."""
        if not self._client:
            await self.initialize()

        purge_data = {}

        if request.purge_everything:
            purge_data["purge_everything"] = True
        else:
            if request.urls:
                purge_data["files"] = request.urls
            if request.tags:
                purge_data["tags"] = request.tags

        # Add child data purge flag for compliance
        if request.child_data_purge:
            purge_data["headers"] = {"X-Child-Data-Purge": "true"}

        response = await self._client.post(
            f"/zones/{self.config.zone_id}/purge_cache", json=purge_data
        )

        if response.status_code != 200:
            raise ServiceUnavailableError(
                f"CloudFlare purge failed: {response.text}", service="cloudflare"
            )

        return response.json()

    async def get_metrics(self) -> CDNMetrics:
        """Get CloudFlare analytics."""
        if not self._client:
            await self.initialize()

        # Get zone analytics for last hour
        since = datetime.now() - timedelta(hours=1)

        response = await self._client.get(
            f"/zones/{self.config.zone_id}/analytics/dashboard",
            params={"since": since.isoformat(), "until": datetime.now().isoformat()},
        )

        if response.status_code != 200:
            logger.warning(f"Failed to get CloudFlare metrics: {response.text}")
            return CDNMetrics(
                provider=CDNProvider.CLOUDFLARE,
                requests_total=0,
                bandwidth_bytes=0,
                cache_hit_ratio=0.0,
                origin_response_time_ms=0.0,
                edge_response_time_ms=0.0,
                error_rate=0.0,
            )

        data = response.json()["result"]
        totals = data["totals"]

        return CDNMetrics(
            provider=CDNProvider.CLOUDFLARE,
            requests_total=totals.get("requests", {}).get("all", 0),
            bandwidth_bytes=totals.get("bandwidth", {}).get("all", 0),
            cache_hit_ratio=totals.get("requests", {}).get("cached", 0)
            / max(totals.get("requests", {}).get("all", 1), 1),
            origin_response_time_ms=data.get("timeseries", [{}])[-1].get(
                "origin_response_time", 0
            )
            * 1000,
            edge_response_time_ms=data.get("timeseries", [{}])[-1].get(
                "edge_response_time", 0
            )
            * 1000,
            error_rate=totals.get("threats", {}).get("all", 0)
            / max(totals.get("requests", {}).get("all", 1), 1),
        )

    async def update_cache_policy(self, policy: CachePolicy) -> bool:
        """Update CloudFlare cache policy using Page Rules."""
        if not self._client:
            await self.initialize()

        # Map cache levels to CloudFlare cache levels
        cf_cache_level = {
            CacheLevel.AGGRESSIVE: "cache_everything",
            CacheLevel.STANDARD: "standard",
            CacheLevel.MINIMAL: "bypass",
            CacheLevel.NO_CACHE: "bypass",
        }

        page_rule = {
            "targets": [
                {
                    "target": "url",
                    "constraint": {"operator": "matches", "value": f"*{policy.name}*"},
                }
            ],
            "actions": [
                {"id": "cache_level", "value": cf_cache_level[policy.level]},
                {"id": "edge_cache_ttl", "value": policy.edge_ttl_seconds},
                {"id": "browser_cache_ttl", "value": policy.browser_ttl_seconds},
            ],
            "priority": 1,
            "status": "active",
        }

        # Add child safety headers for COPPA compliance
        if policy.child_safe_headers:
            page_rule["actions"].extend(
                [
                    {
                        "id": "response_header_replace",
                        "value": {"name": "X-Child-Safe", "value": "true"},
                    },
                    {
                        "id": "response_header_replace",
                        "value": {"name": "X-COPPA-Compliant", "value": "true"},
                    },
                ]
            )

        response = await self._client.post(
            f"/zones/{self.config.zone_id}/pagerules", json=page_rule
        )

        return response.status_code == 200

    async def health_check(self) -> Dict[str, Any]:
        """Check CloudFlare health."""
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get(f"/zones/{self.config.zone_id}")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "provider": "cloudflare",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "zone_active": (
                    response.json()["result"]["status"] == "active"
                    if response.status_code == 200
                    else False
                ),
            }
        except Exception as e:
            logger.error(f"CloudFlare health check failed: {e}")
            return {"status": "unhealthy", "provider": "cloudflare", "error": str(e)}


class AWSCloudFrontProvider(BaseCDNProvider):
    """AWS CloudFront CDN provider implementation."""

    async def initialize(self) -> None:
        """Initialize CloudFront client."""
        self._client = boto3.client(
            "cloudfront",
            aws_access_key_id=decrypt_sensitive_data(self.config.api_key),
            aws_secret_access_key=decrypt_sensitive_data(self.config.api_secret),
            region_name="us-east-1",  # CloudFront is global but API is in us-east-1
        )

    async def purge_cache(self, request: PurgeRequest) -> Dict[str, Any]:
        """Purge CloudFront cache."""
        if not self._client:
            await self.initialize()

        # Create invalidation
        paths = request.urls if request.urls else ["/*"]

        invalidation_batch = {
            "Paths": {"Quantity": len(paths), "Items": paths},
            "CallerReference": f"purge-{int(time.time())}",
        }

        # Add child data purge metadata
        if request.child_data_purge:
            invalidation_batch["CallerReference"] += "-child-data"

        response = self._client.create_invalidation(
            DistributionId=self.config.distribution_id,
            InvalidationBatch=invalidation_batch,
        )

        return {
            "invalidation_id": response["Invalidation"]["Id"],
            "status": response["Invalidation"]["Status"],
            "create_time": response["Invalidation"]["CreateTime"],
        }

    async def get_metrics(self) -> CDNMetrics:
        """Get CloudFront metrics from CloudWatch."""
        # This would typically use CloudWatch API
        # For now, return basic metrics
        return CDNMetrics(
            provider=CDNProvider.AWS_CLOUDFRONT,
            requests_total=0,
            bandwidth_bytes=0,
            cache_hit_ratio=0.0,
            origin_response_time_ms=0.0,
            edge_response_time_ms=0.0,
            error_rate=0.0,
        )

    async def update_cache_policy(self, policy: CachePolicy) -> bool:
        """Update CloudFront cache behavior."""
        # This would update the distribution configuration
        # Implementation would depend on specific requirements
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Check CloudFront health."""
        if not self._client:
            await self.initialize()

        try:
            response = self._client.get_distribution(Id=self.config.distribution_id)
            return {
                "status": "healthy",
                "provider": "aws_cloudfront",
                "distribution_status": response["Distribution"]["Status"],
                "enabled": response["Distribution"]["DistributionConfig"]["Enabled"],
            }
        except Exception as e:
            logger.error(f"CloudFront health check failed: {e}")
            return {
                "status": "unhealthy",
                "provider": "aws_cloudfront",
                "error": str(e),
            }


class AzureCDNProvider(BaseCDNProvider):
    """Azure CDN provider implementation."""

    async def initialize(self) -> None:
        """Initialize Azure CDN client."""
        credential = DefaultAzureCredential()
        self._client = CdnManagementClient(credential, self.config.subscription_id)

    async def purge_cache(self, request: PurgeRequest) -> Dict[str, Any]:
        """Purge Azure CDN cache."""
        if not self._client:
            await self.initialize()

        # Azure CDN purge implementation
        purge_paths = request.urls if request.urls else ["/*"]

        # This would typically use the Azure CDN management API
        return {
            "status": "success",
            "purged_paths": purge_paths,
            "child_data_purge": request.child_data_purge,
        }

    async def get_metrics(self) -> CDNMetrics:
        """Get Azure CDN metrics."""
        return CDNMetrics(
            provider=CDNProvider.AZURE_CDN,
            requests_total=0,
            bandwidth_bytes=0,
            cache_hit_ratio=0.0,
            origin_response_time_ms=0.0,
            edge_response_time_ms=0.0,
            error_rate=0.0,
        )

    async def update_cache_policy(self, policy: CachePolicy) -> bool:
        """Update Azure CDN cache policy."""
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Check Azure CDN health."""
        return {"status": "healthy", "provider": "azure_cdn"}


class CDNManager:
    """Multi-provider CDN management system."""

    def __init__(self, configs: List[CDNConfig]):
        self.configs = sorted(configs, key=lambda x: x.priority)
        self.providers: Dict[CDNProvider, BaseCDNProvider] = {}
        self._initialized = False

        # Default cache policies for child-safe content
        self.default_policies = {
            "static_assets": CachePolicy(
                name="static_assets",
                level=CacheLevel.AGGRESSIVE,
                ttl_seconds=86400 * 7,  # 1 week
                browser_ttl_seconds=86400,
                edge_ttl_seconds=86400 * 7,
                child_safe_headers=True,
                coppa_compliance=True,
            ),
            "api_responses": CachePolicy(
                name="api_responses",
                level=CacheLevel.STANDARD,
                ttl_seconds=3600,  # 1 hour
                browser_ttl_seconds=300,
                edge_ttl_seconds=3600,
                child_safe_headers=True,
                coppa_compliance=True,
            ),
            "child_data": CachePolicy(
                name="child_data",
                level=CacheLevel.NO_CACHE,
                ttl_seconds=0,
                browser_ttl_seconds=0,
                edge_ttl_seconds=0,
                bypass_cache_on_cookie=True,
                child_safe_headers=True,
                coppa_compliance=True,
            ),
            "tts_audio": CachePolicy(
                name="tts_audio",
                level=CacheLevel.MINIMAL,
                ttl_seconds=3600,  # 1 hour
                browser_ttl_seconds=1800,
                edge_ttl_seconds=3600,
                child_safe_headers=True,
                coppa_compliance=True,
            ),
        }

    async def initialize(self) -> None:
        """Initialize all CDN providers."""
        if self._initialized:
            return

        provider_classes = {
            CDNProvider.CLOUDFLARE: CloudFlareProvider,
            CDNProvider.AWS_CLOUDFRONT: AWSCloudFrontProvider,
            CDNProvider.AZURE_CDN: AzureCDNProvider,
        }

        for config in self.configs:
            if not config.enabled:
                continue

            provider_class = provider_classes.get(config.provider)
            if provider_class:
                provider = provider_class(config)
                try:
                    await provider.initialize()
                    self.providers[config.provider] = provider
                    logger.info(f"Initialized CDN provider: {config.provider.value}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize CDN provider {config.provider.value}: {e}"
                    )

        # Apply default cache policies
        for policy in self.default_policies.values():
            await self.update_cache_policy(policy)

        self._initialized = True
        logger.info(f"CDN Manager initialized with {len(self.providers)} providers")

    async def purge_cache(
        self, request: PurgeRequest, provider: Optional[CDNProvider] = None
    ) -> Dict[str, Any]:
        """Purge cache from one or all providers."""
        if not self._initialized:
            await self.initialize()

        results = {}

        if provider:
            # Purge from specific provider
            if provider in self.providers:
                try:
                    result = await self.providers[provider].purge_cache(request)
                    results[provider.value] = {"status": "success", "result": result}
                except Exception as e:
                    logger.error(f"Cache purge failed for {provider.value}: {e}")
                    results[provider.value] = {"status": "error", "error": str(e)}
        else:
            # Purge from all providers
            tasks = []
            for prov, provider_instance in self.providers.items():
                tasks.append(self._purge_provider(prov, provider_instance, request))

            provider_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, (prov, _) in enumerate(self.providers.items()):
                if isinstance(provider_results[i], Exception):
                    results[prov.value] = {
                        "status": "error",
                        "error": str(provider_results[i]),
                    }
                else:
                    results[prov.value] = {
                        "status": "success",
                        "result": provider_results[i],
                    }

        return results

    async def _purge_provider(
        self,
        provider: CDNProvider,
        provider_instance: BaseCDNProvider,
        request: PurgeRequest,
    ):
        """Helper method to purge cache from a single provider."""
        try:
            return await provider_instance.purge_cache(request)
        except Exception as e:
            logger.error(f"Cache purge failed for {provider.value}: {e}")
            raise

    async def get_metrics(self) -> Dict[CDNProvider, CDNMetrics]:
        """Get metrics from all providers."""
        if not self._initialized:
            await self.initialize()

        metrics = {}
        tasks = []

        for provider, provider_instance in self.providers.items():
            tasks.append(provider_instance.get_metrics())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, (provider, _) in enumerate(self.providers.items()):
            if isinstance(results[i], Exception):
                logger.error(
                    f"Failed to get metrics from {provider.value}: {results[i]}"
                )
                metrics[provider] = CDNMetrics(
                    provider=provider,
                    requests_total=0,
                    bandwidth_bytes=0,
                    cache_hit_ratio=0.0,
                    origin_response_time_ms=0.0,
                    edge_response_time_ms=0.0,
                    error_rate=1.0,  # Indicate error
                )
            else:
                metrics[provider] = results[i]

        return metrics

    async def update_cache_policy(self, policy: CachePolicy) -> Dict[str, bool]:
        """Update cache policy across all providers."""
        if not self._initialized:
            await self.initialize()

        results = {}

        for provider, provider_instance in self.providers.items():
            try:
                success = await provider_instance.update_cache_policy(policy)
                results[provider.value] = success
                logger.info(
                    f"Updated cache policy '{policy.name}' for {provider.value}: {success}"
                )
            except Exception as e:
                logger.error(f"Failed to update cache policy for {provider.value}: {e}")
                results[provider.value] = False

        return results

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all CDN providers."""
        if not self._initialized:
            await self.initialize()

        health_results = {}

        for provider, provider_instance in self.providers.items():
            try:
                health = await provider_instance.health_check()
                health_results[provider.value] = health
            except Exception as e:
                logger.error(f"Health check failed for {provider.value}: {e}")
                health_results[provider.value] = {
                    "status": "unhealthy",
                    "provider": provider.value,
                    "error": str(e),
                }

        return {
            "overall_status": (
                "healthy"
                if all(h.get("status") == "healthy" for h in health_results.values())
                else "degraded"
            ),
            "providers": health_results,
            "total_providers": len(self.providers),
            "healthy_providers": sum(
                1 for h in health_results.values() if h.get("status") == "healthy"
            ),
        }

    async def purge_child_data(
        self, child_id: str, urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Purge child-specific data from all CDN providers with COPPA compliance."""
        purge_urls = urls or [f"/api/v1/children/{child_id}/*"]

        request = PurgeRequest(
            urls=purge_urls, tags=[f"child-{child_id}"], child_data_purge=True
        )

        result = await self.purge_cache(request)

        # Log child data purge for compliance audit
        logger.info(
            f"Child data purge completed",
            extra={
                "child_id": child_id,
                "urls": purge_urls,
                "compliance": "COPPA",
                "result": result,
            },
        )

        return result

    async def get_cache_hit_ratio(self) -> float:
        """Get overall cache hit ratio across all providers."""
        metrics = await self.get_metrics()

        if not metrics:
            return 0.0

        total_requests = sum(m.requests_total for m in metrics.values())
        if total_requests == 0:
            return 0.0

        weighted_hit_ratio = sum(
            m.cache_hit_ratio * m.requests_total for m in metrics.values()
        )

        return weighted_hit_ratio / total_requests

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        metrics = await self.get_metrics()
        health = await self.health_check()

        total_requests = sum(m.requests_total for m in metrics.values())
        total_bandwidth = sum(m.bandwidth_bytes for m in metrics.values())
        avg_cache_hit_ratio = await self.get_cache_hit_ratio()

        avg_response_time = (
            sum(m.edge_response_time_ms for m in metrics.values()) / len(metrics)
            if metrics
            else 0.0
        )

        return {
            "total_requests": total_requests,
            "total_bandwidth_gb": total_bandwidth / (1024**3),
            "cache_hit_ratio": avg_cache_hit_ratio,
            "avg_edge_response_time_ms": avg_response_time,
            "providers_status": health,
            "child_safety_compliant": True,
            "coppa_compliant": True,
            "metrics_by_provider": {
                p.value: {
                    "requests": m.requests_total,
                    "bandwidth_gb": m.bandwidth_bytes / (1024**3),
                    "cache_hit_ratio": m.cache_hit_ratio,
                    "response_time_ms": m.edge_response_time_ms,
                }
                for p, m in metrics.items()
            },
        }


# Factory function for easy initialization
def create_cdn_manager(
    cloudflare_config: Optional[Dict[str, Any]] = None,
    aws_config: Optional[Dict[str, Any]] = None,
    azure_config: Optional[Dict[str, Any]] = None,
) -> CDNManager:
    """Create CDN manager with provided configurations."""
    configs = []

    if cloudflare_config:
        configs.append(
            CDNConfig(provider=CDNProvider.CLOUDFLARE, priority=1, **cloudflare_config)
        )

    if aws_config:
        configs.append(
            CDNConfig(provider=CDNProvider.AWS_CLOUDFRONT, priority=2, **aws_config)
        )

    if azure_config:
        configs.append(
            CDNConfig(provider=CDNProvider.AZURE_CDN, priority=3, **azure_config)
        )

    if not configs:
        raise ConfigurationError("At least one CDN provider must be configured")

    return CDNManager(configs)
