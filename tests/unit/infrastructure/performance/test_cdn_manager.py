"""
Tests for CDN Manager.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.infrastructure.performance.cdn_manager import (
    CDNManager,
    CloudFlareProvider,
    CDNProvider,
    CDNConfig,
    CachePolicy,
    CacheLevel,
    PurgeRequest,
    CDNMetrics,
    create_cdn_manager
)
from src.core.exceptions import ServiceUnavailableError, ConfigurationError


class TestCDNConfig:
    """Test CDN configuration."""

    def test_cdn_config_creation(self):
        """Test CDN config creation with encryption."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data') as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
            
            config = CDNConfig(
                provider=CDNProvider.CLOUDFLARE,
                api_key="test_key",
                api_secret="test_secret",
                zone_id="zone123"
            )
            
            assert config.provider == CDNProvider.CLOUDFLARE
            assert config.zone_id == "zone123"
            assert config.enabled is True
            assert config.priority == 1
            mock_encrypt.assert_called()

    def test_cdn_config_defaults(self):
        """Test CDN config default values."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data'):
            config = CDNConfig(
                provider=CDNProvider.AWS_CLOUDFRONT,
                api_key="test_key"
            )
            
            assert config.api_secret == ""
            assert config.enabled is True
            assert config.priority == 1


class TestCachePolicy:
    """Test cache policy configuration."""

    def test_cache_policy_creation(self):
        """Test cache policy creation."""
        policy = CachePolicy(
            name="test_policy",
            level=CacheLevel.STANDARD,
            ttl_seconds=3600,
            browser_ttl_seconds=1800,
            edge_ttl_seconds=3600
        )
        
        assert policy.name == "test_policy"
        assert policy.level == CacheLevel.STANDARD
        assert policy.ttl_seconds == 3600
        assert policy.child_safe_headers is True
        assert policy.coppa_compliance is True

    def test_cache_policy_defaults(self):
        """Test cache policy default values."""
        policy = CachePolicy(
            name="test",
            level=CacheLevel.MINIMAL,
            ttl_seconds=60,
            browser_ttl_seconds=30,
            edge_ttl_seconds=60
        )
        
        assert policy.bypass_cache_on_cookie is False
        assert policy.respect_origin_headers is True


class TestPurgeRequest:
    """Test purge request configuration."""

    def test_purge_request_creation(self):
        """Test purge request creation."""
        request = PurgeRequest(
            urls=["https://example.com/file1.js", "https://example.com/file2.css"],
            tags=["static", "assets"],
            child_data_purge=True
        )
        
        assert len(request.urls) == 2
        assert "static" in request.tags
        assert request.child_data_purge is True
        assert request.purge_everything is False

    def test_purge_request_defaults(self):
        """Test purge request default values."""
        request = PurgeRequest(urls=["https://example.com/test"])
        
        assert request.tags == []
        assert request.purge_everything is False
        assert request.child_data_purge is False


class TestCloudFlareProvider:
    """Test CloudFlare CDN provider."""

    @pytest.fixture
    def cloudflare_config(self):
        """Create CloudFlare config."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data') as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
            return CDNConfig(
                provider=CDNProvider.CLOUDFLARE,
                api_key="test_key",
                zone_id="zone123"
            )

    @pytest.fixture
    def cloudflare_provider(self, cloudflare_config):
        """Create CloudFlare provider."""
        return CloudFlareProvider(cloudflare_config)

    @pytest.mark.asyncio
    async def test_initialize(self, cloudflare_provider):
        """Test CloudFlare provider initialization."""
        with patch('httpx.AsyncClient') as mock_client:
            with patch('src.infrastructure.performance.cdn_manager.decrypt_sensitive_data') as mock_decrypt:
                mock_decrypt.return_value = "decrypted_key"
                
                await cloudflare_provider.initialize()
                
                mock_client.assert_called_once()
                assert cloudflare_provider._client is not None

    @pytest.mark.asyncio
    async def test_purge_cache_success(self, cloudflare_provider):
        """Test successful cache purge."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "result": {"id": "purge123"}}
        mock_client.post.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        request = PurgeRequest(urls=["https://example.com/test.js"])
        result = await cloudflare_provider.purge_cache(request)
        
        assert result["success"] is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_purge_cache_failure(self, cloudflare_provider):
        """Test cache purge failure."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client.post.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        request = PurgeRequest(urls=["https://example.com/test.js"])
        
        with pytest.raises(ServiceUnavailableError, match="CloudFlare purge failed"):
            await cloudflare_provider.purge_cache(request)

    @pytest.mark.asyncio
    async def test_get_metrics_success(self, cloudflare_provider):
        """Test successful metrics retrieval."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "totals": {
                    "requests": {"all": 1000, "cached": 800},
                    "bandwidth": {"all": 5000000},
                    "threats": {"all": 10}
                },
                "timeseries": [{"origin_response_time": 0.1, "edge_response_time": 0.05}]
            }
        }
        mock_client.get.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        metrics = await cloudflare_provider.get_metrics()
        
        assert isinstance(metrics, CDNMetrics)
        assert metrics.provider == CDNProvider.CLOUDFLARE
        assert metrics.requests_total == 1000
        assert metrics.cache_hit_ratio == 0.8

    @pytest.mark.asyncio
    async def test_get_metrics_failure(self, cloudflare_provider):
        """Test metrics retrieval failure."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.get.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        metrics = await cloudflare_provider.get_metrics()
        
        assert isinstance(metrics, CDNMetrics)
        assert metrics.requests_total == 0
        assert metrics.cache_hit_ratio == 0.0

    @pytest.mark.asyncio
    async def test_update_cache_policy(self, cloudflare_provider):
        """Test cache policy update."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        policy = CachePolicy(
            name="test_policy",
            level=CacheLevel.STANDARD,
            ttl_seconds=3600,
            browser_ttl_seconds=1800,
            edge_ttl_seconds=3600
        )
        
        result = await cloudflare_provider.update_cache_policy(policy)
        
        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cloudflare_provider):
        """Test healthy status check."""
        mock_client = AsyncMock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"status": "active"}}
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_client.get.return_value = mock_response
        cloudflare_provider._client = mock_client
        
        health = await cloudflare_provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "cloudflare"
        assert health["zone_active"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, cloudflare_provider):
        """Test unhealthy status check."""
        mock_client = AsyncMock(spec=True)
        mock_client.get.side_effect = Exception("Connection failed")
        cloudflare_provider._client = mock_client
        
        health = await cloudflare_provider.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health


class TestCDNManager:
    """Test CDN Manager functionality."""

    @pytest.fixture
    def cdn_configs(self):
        """Create test CDN configurations."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data') as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
            return [
                CDNConfig(
                    provider=CDNProvider.CLOUDFLARE,
                    api_key="cf_key",
                    zone_id="zone123",
                    priority=1
                ),
                CDNConfig(
                    provider=CDNProvider.AWS_CLOUDFRONT,
                    api_key="aws_key",
                    api_secret="aws_secret",
                    distribution_id="dist123",
                    priority=2
                )
            ]

    @pytest.fixture
    def cdn_manager(self, cdn_configs):
        """Create CDN manager."""
        return CDNManager(cdn_configs)

    def test_cdn_manager_initialization(self, cdn_manager):
        """Test CDN manager initialization."""
        assert len(cdn_manager.configs) == 2
        assert cdn_manager.configs[0].priority == 1
        assert cdn_manager.configs[1].priority == 2
        assert not cdn_manager._initialized

    def test_default_policies(self, cdn_manager):
        """Test default cache policies."""
        assert "static_assets" in cdn_manager.default_policies
        assert "child_data" in cdn_manager.default_policies
        assert "tts_audio" in cdn_manager.default_policies
        
        child_policy = cdn_manager.default_policies["child_data"]
        assert child_policy.level == CacheLevel.NO_CACHE
        assert child_policy.coppa_compliance is True

    @pytest.mark.asyncio
    async def test_initialize_providers(self, cdn_manager):
        """Test provider initialization."""
        with patch.object(CloudFlareProvider, 'initialize', new_callable=AsyncMock) as mock_cf_init:
            with patch('src.infrastructure.performance.cdn_manager.AWSCloudFrontProvider') as mock_aws_class:
                mock_aws_provider = AsyncMock(spec=True)
                mock_aws_class.return_value = mock_aws_provider
                
                await cdn_manager.initialize()
                
                assert cdn_manager._initialized is True
                assert len(cdn_manager.providers) >= 1
                mock_cf_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_purge_cache_all_providers(self, cdn_manager):
        """Test cache purge across all providers."""
        # Mock providers
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.purge_cache.return_value = {"success": True}
        mock_aws_provider = AsyncMock(spec=True)
        mock_aws_provider.purge_cache.return_value = {"invalidation_id": "inv123"}
        
        cdn_manager.providers = {
            CDNProvider.CLOUDFLARE: mock_cf_provider,
            CDNProvider.AWS_CLOUDFRONT: mock_aws_provider
        }
        cdn_manager._initialized = True
        
        request = PurgeRequest(urls=["https://example.com/test.js"])
        results = await cdn_manager.purge_cache(request)
        
        assert "cloudflare" in results
        assert "aws_cloudfront" in results
        assert results["cloudflare"]["status"] == "success"
        assert results["aws_cloudfront"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_purge_cache_specific_provider(self, cdn_manager):
        """Test cache purge for specific provider."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.purge_cache.return_value = {"success": True}
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        request = PurgeRequest(urls=["https://example.com/test.js"])
        results = await cdn_manager.purge_cache(request, CDNProvider.CLOUDFLARE)
        
        assert "cloudflare" in results
        assert results["cloudflare"]["status"] == "success"
        mock_cf_provider.purge_cache.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_get_metrics(self, cdn_manager):
        """Test metrics collection from all providers."""
        mock_cf_metrics = CDNMetrics(
            provider=CDNProvider.CLOUDFLARE,
            requests_total=1000,
            bandwidth_bytes=5000000,
            cache_hit_ratio=0.8,
            origin_response_time_ms=100,
            edge_response_time_ms=50,
            error_rate=0.01
        )
        
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.get_metrics.return_value = mock_cf_metrics
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        metrics = await cdn_manager.get_metrics()
        
        assert CDNProvider.CLOUDFLARE in metrics
        assert metrics[CDNProvider.CLOUDFLARE].requests_total == 1000

    @pytest.mark.asyncio
    async def test_update_cache_policy(self, cdn_manager):
        """Test cache policy update across providers."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.update_cache_policy.return_value = True
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        policy = CachePolicy(
            name="test_policy",
            level=CacheLevel.STANDARD,
            ttl_seconds=3600,
            browser_ttl_seconds=1800,
            edge_ttl_seconds=3600
        )
        
        results = await cdn_manager.update_cache_policy(policy)
        
        assert "cloudflare" in results
        assert results["cloudflare"] is True

    @pytest.mark.asyncio
    async def test_health_check(self, cdn_manager):
        """Test health check across all providers."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.health_check.return_value = {"status": "healthy", "provider": "cloudflare"}
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        health = await cdn_manager.health_check()
        
        assert health["overall_status"] == "healthy"
        assert "providers" in health
        assert health["total_providers"] == 1
        assert health["healthy_providers"] == 1

    @pytest.mark.asyncio
    async def test_purge_child_data(self, cdn_manager):
        """Test child data purge with COPPA compliance."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.purge_cache.return_value = {"success": True}
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        child_id = "child123"
        result = await cdn_manager.purge_child_data(child_id)
        
        assert "cloudflare" in result
        mock_cf_provider.purge_cache.assert_called_once()
        
        # Verify the purge request had child data flag
        call_args = mock_cf_provider.purge_cache.call_args[0][0]
        assert call_args.child_data_purge is True
        assert f"child-{child_id}" in call_args.tags

    @pytest.mark.asyncio
    async def test_get_cache_hit_ratio(self, cdn_manager):
        """Test overall cache hit ratio calculation."""
        metrics = {
            CDNProvider.CLOUDFLARE: CDNMetrics(
                provider=CDNProvider.CLOUDFLARE,
                requests_total=1000,
                bandwidth_bytes=0,
                cache_hit_ratio=0.8,
                origin_response_time_ms=0,
                edge_response_time_ms=0,
                error_rate=0
            ),
            CDNProvider.AWS_CLOUDFRONT: CDNMetrics(
                provider=CDNProvider.AWS_CLOUDFRONT,
                requests_total=500,
                bandwidth_bytes=0,
                cache_hit_ratio=0.9,
                origin_response_time_ms=0,
                edge_response_time_ms=0,
                error_rate=0
            )
        }
        
        with patch.object(cdn_manager, 'get_metrics', return_value=metrics):
            hit_ratio = await cdn_manager.get_cache_hit_ratio()
            
            # Weighted average: (0.8 * 1000 + 0.9 * 500) / 1500 = 0.833...
            assert abs(hit_ratio - 0.8333333333333334) < 0.001

    @pytest.mark.asyncio
    async def test_get_performance_summary(self, cdn_manager):
        """Test comprehensive performance summary."""
        metrics = {
            CDNProvider.CLOUDFLARE: CDNMetrics(
                provider=CDNProvider.CLOUDFLARE,
                requests_total=1000,
                bandwidth_bytes=1024**3,  # 1 GB
                cache_hit_ratio=0.8,
                origin_response_time_ms=100,
                edge_response_time_ms=50,
                error_rate=0.01
            )
        }
        
        health = {
            "overall_status": "healthy",
            "providers": {"cloudflare": {"status": "healthy"}}
        }
        
        with patch.object(cdn_manager, 'get_metrics', return_value=metrics):
            with patch.object(cdn_manager, 'health_check', return_value=health):
                summary = await cdn_manager.get_performance_summary()
                
                assert summary["total_requests"] == 1000
                assert summary["total_bandwidth_gb"] == 1.0
                assert summary["child_safety_compliant"] is True
                assert summary["coppa_compliant"] is True
                assert "metrics_by_provider" in summary


class TestCDNManagerFactory:
    """Test CDN manager factory function."""

    def test_create_cdn_manager_cloudflare_only(self):
        """Test creating CDN manager with CloudFlare only."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data'):
            manager = create_cdn_manager(
                cloudflare_config={
                    "api_key": "cf_key",
                    "zone_id": "zone123"
                }
            )
            
            assert len(manager.configs) == 1
            assert manager.configs[0].provider == CDNProvider.CLOUDFLARE

    def test_create_cdn_manager_multiple_providers(self):
        """Test creating CDN manager with multiple providers."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data'):
            manager = create_cdn_manager(
                cloudflare_config={"api_key": "cf_key", "zone_id": "zone123"},
                aws_config={"api_key": "aws_key", "api_secret": "aws_secret", "distribution_id": "dist123"}
            )
            
            assert len(manager.configs) == 2
            assert manager.configs[0].priority == 1  # CloudFlare first
            assert manager.configs[1].priority == 2  # AWS second

    def test_create_cdn_manager_no_config(self):
        """Test creating CDN manager with no configuration."""
        with pytest.raises(ConfigurationError, match="At least one CDN provider must be configured"):
            create_cdn_manager()


class TestCDNManagerErrorHandling:
    """Test CDN manager error handling."""

    @pytest.fixture
    def cdn_manager(self):
        """Create CDN manager with mock config."""
        with patch('src.infrastructure.performance.cdn_manager.encrypt_sensitive_data'):
            config = CDNConfig(
                provider=CDNProvider.CLOUDFLARE,
                api_key="test_key",
                zone_id="zone123"
            )
            return CDNManager([config])

    @pytest.mark.asyncio
    async def test_purge_cache_provider_error(self, cdn_manager):
        """Test cache purge with provider error."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.purge_cache.side_effect = Exception("Provider error")
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        request = PurgeRequest(urls=["https://example.com/test.js"])
        results = await cdn_manager.purge_cache(request)
        
        assert "cloudflare" in results
        assert results["cloudflare"]["status"] == "error"
        assert "Provider error" in results["cloudflare"]["error"]

    @pytest.mark.asyncio
    async def test_get_metrics_provider_error(self, cdn_manager):
        """Test metrics collection with provider error."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.get_metrics.side_effect = Exception("Metrics error")
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        metrics = await cdn_manager.get_metrics()
        
        assert CDNProvider.CLOUDFLARE in metrics
        assert metrics[CDNProvider.CLOUDFLARE].error_rate == 1.0  # Indicates error

    @pytest.mark.asyncio
    async def test_health_check_provider_error(self, cdn_manager):
        """Test health check with provider error."""
        mock_cf_provider = AsyncMock(spec=True)
        mock_cf_provider.health_check.side_effect = Exception("Health check error")
        
        cdn_manager.providers = {CDNProvider.CLOUDFLARE: mock_cf_provider}
        cdn_manager._initialized = True
        
        health = await cdn_manager.health_check()
        
        assert health["overall_status"] == "degraded"
        assert health["providers"]["cloudflare"]["status"] == "unhealthy"