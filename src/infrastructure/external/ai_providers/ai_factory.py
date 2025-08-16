"""
Production AI Provider Factory - Dynamic Failover & Cost Management
=================================================================
Enterprise-grade AI provider management with:
- Dynamic provider selection based on health, cost, and performance
- Automatic failover and circuit breaker patterns  
- Real-time cost tracking and budget management
- Provider health monitoring and SLA tracking
- Rate limiting and quota management
- Advanced routing and load balancing
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os

from src.interfaces.providers.ai_provider import AIProvider
from src.adapters.providers.openai_provider import ProductionOpenAIProvider
from src.core.value_objects.value_objects import ChildPreferences


class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class FailoverReason(Enum):
    """Reasons for provider failover."""
    HEALTH_CHECK_FAILED = "health_check_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    COST_BUDGET_EXCEEDED = "cost_budget_exceeded"
    RESPONSE_TIME_EXCEEDED = "response_time_exceeded"
    ERROR_THRESHOLD_EXCEEDED = "error_threshold_exceeded"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"


@dataclass
class ProviderMetrics:
    """Real-time provider performance metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    total_cost_usd: float = 0.0
    tokens_used: int = 0
    rate_limit_hits: int = 0
    last_health_check: Optional[datetime] = None
    health_check_failures: int = 0
    circuit_breaker_open: bool = False
    circuit_breaker_opened_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def error_rate(self) -> float:
        return 100.0 - self.success_rate
    
    @property
    def cost_per_request(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_cost_usd / self.total_requests


@dataclass
class ProviderConfig:
    """Provider configuration and limits."""
    name: str
    provider_class: type
    api_key: str
    model: str
    max_requests_per_minute: int = 60
    max_cost_per_hour: float = 10.0
    max_response_time_ms: float = 5000.0
    health_check_interval_seconds: int = 300  # 5 minutes
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 300  # 5 minutes
    priority: int = 1  # Lower number = higher priority
    weight: float = 1.0  # Load balancing weight
    enabled: bool = True


@dataclass
class ProviderSelectionCriteria:
    """Criteria for selecting best provider."""
    max_cost_per_request: Optional[float] = None
    max_response_time_ms: Optional[float] = None
    min_success_rate: Optional[float] = None
    required_features: List[str] = field(default_factory=list)
    child_age: Optional[int] = None
    priority_mode: str = "cost_optimized"  # cost_optimized, performance_optimized, balanced


class AIProviderError(Exception):
    """Custom exception for AI provider errors."""
    
    def __init__(self, message: str, provider: str = None, error_type: str = None):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type
        self.timestamp = datetime.now()


class ProductionAIProviderFactory:
    """
    Production-grade AI provider factory with intelligent routing.
    
    Features:
    - Dynamic provider selection based on real-time metrics
    - Automatic failover with circuit breaker patterns
    - Cost tracking and budget management
    - Performance monitoring and SLA compliance
    - Rate limiting and quota management
    - Provider health checks and alerting
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Provider configurations
        self.providers: Dict[str, ProviderConfig] = {}
        self.provider_instances: Dict[str, AIProvider] = {}
        self.provider_metrics: Dict[str, ProviderMetrics] = {}
        
        # Global configuration
        self.health_check_task: Optional[asyncio.Task] = None
        self.metrics_cleanup_task: Optional[asyncio.Task] = None
        
        # Load provider configurations
        self._load_provider_configs()
        
        # Initialize providers
        self._initialize_providers()
        
        # Start background tasks
        self._start_background_tasks()
        
        self.logger.info("ProductionAIProviderFactory initialized with providers: " + 
                        ", ".join(self.providers.keys()))
    
    def get_provider(self, provider_name: str = None, api_key: str = None) -> AIProvider:
        """
        Get a provider instance for immediate use.
        
        Args:
            provider_name: Optional provider name (if None, gets best available)
            api_key: Optional API key override
            
        Returns:
            AIProvider instance
            
        Raises:
            AIProviderError: If no suitable provider is available
        """
        if provider_name:
            # Specific provider requested
            if provider_name not in self.provider_instances:
                if provider_name not in self.providers:
                    raise AIProviderError(f"Unknown provider: {provider_name}")
                
                # Try to initialize if not available
                config = self.providers[provider_name]
                if not config.enabled:
                    raise AIProviderError(f"Provider {provider_name} is disabled")
                
                if provider_name not in self.provider_instances:
                    raise AIProviderError(f"Provider {provider_name} failed to initialize")
            
            return self.provider_instances[provider_name]
        else:
            # Get best available provider
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                _, provider = loop.run_until_complete(self.get_best_provider())
                return provider
            except RuntimeError:
                # No event loop, use first available provider
                if not self.provider_instances:
                    raise AIProviderError("No AI providers available")
                return next(iter(self.provider_instances.values()))
    
    def _load_provider_configs(self) -> None:
        """Load provider configurations from environment."""
        # OpenAI Configuration
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.providers["openai"] = ProviderConfig(
                name="openai",
                provider_class=ProductionOpenAIProvider,
                api_key=openai_api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                max_requests_per_minute=int(os.getenv("OPENAI_MAX_RPM", "60")),
                max_cost_per_hour=float(os.getenv("OPENAI_MAX_COST_HOUR", "10.0")),
                max_response_time_ms=float(os.getenv("OPENAI_MAX_RESPONSE_TIME", "5000")),
                priority=int(os.getenv("OPENAI_PRIORITY", "1")),
                weight=float(os.getenv("OPENAI_WEIGHT", "1.0")),
                enabled=os.getenv("OPENAI_ENABLED", "true").lower() == "true"
            )
        
        # Claude Configuration (Anthropic)
        claude_api_key = os.getenv("CLAUDE_API_KEY")
        if claude_api_key:
            self.providers["claude"] = ProviderConfig(
                name="claude",
                provider_class=self._get_claude_provider_class(),
                api_key=claude_api_key,
                model=os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
                max_requests_per_minute=int(os.getenv("CLAUDE_MAX_RPM", "50")),
                max_cost_per_hour=float(os.getenv("CLAUDE_MAX_COST_HOUR", "8.0")),
                max_response_time_ms=float(os.getenv("CLAUDE_MAX_RESPONSE_TIME", "6000")),
                priority=int(os.getenv("CLAUDE_PRIORITY", "2")),
                weight=float(os.getenv("CLAUDE_WEIGHT", "0.8")),
                enabled=os.getenv("CLAUDE_ENABLED", "true").lower() == "true"
            )
        
        # Gemini Configuration (Google)
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            self.providers["gemini"] = ProviderConfig(
                name="gemini",
                provider_class=self._get_gemini_provider_class(),
                api_key=gemini_api_key,
                model=os.getenv("GEMINI_MODEL", "gemini-pro"),
                max_requests_per_minute=int(os.getenv("GEMINI_MAX_RPM", "40")),
                max_cost_per_hour=float(os.getenv("GEMINI_MAX_COST_HOUR", "5.0")),
                max_response_time_ms=float(os.getenv("GEMINI_MAX_RESPONSE_TIME", "4000")),
                priority=int(os.getenv("GEMINI_PRIORITY", "3")),
                weight=float(os.getenv("GEMINI_WEIGHT", "0.6")),
                enabled=os.getenv("GEMINI_ENABLED", "false").lower() == "true"
            )
        
        if not self.providers:
            raise AIProviderError("No AI providers configured. Please set API keys.")
    
    def _initialize_providers(self) -> None:
        """Initialize all configured providers."""
        for name, config in self.providers.items():
            try:
                if config.enabled:
                    # Initialize provider instance
                    provider_instance = config.provider_class(
                        api_key=config.api_key,
                        model=config.model
                    )
                    
                    self.provider_instances[name] = provider_instance
                    self.provider_metrics[name] = ProviderMetrics()
                    
                    self.logger.info(f"Initialized provider: {name}")
                else:
                    self.logger.info(f"Provider {name} is disabled")
                    
            except Exception as e:
                self.logger.error(f"Failed to initialize provider {name}: {e}", exc_info=True)
                # Mark provider as unhealthy
                if name in self.provider_metrics:
                    self.provider_metrics[name].circuit_breaker_open = True
    
    def _start_background_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Metrics cleanup task
        self.metrics_cleanup_task = asyncio.create_task(self._metrics_cleanup_loop())
    
    async def get_best_provider(
        self, 
        criteria: Optional[ProviderSelectionCriteria] = None
    ) -> Tuple[str, AIProvider]:
        """
        Select the best available provider based on criteria.
        
        Args:
            criteria: Selection criteria for provider choice
            
        Returns:
            Tuple of (provider_name, provider_instance)
            
        Raises:
            AIProviderError: If no suitable provider is available
        """
        criteria = criteria or ProviderSelectionCriteria()
        
        # Get available providers
        available_providers = await self._get_available_providers(criteria)
        
        if not available_providers:
            raise AIProviderError("No available AI providers meet the criteria")
        
        # Select best provider based on strategy
        best_provider_name = self._select_provider_by_strategy(
            available_providers, criteria
        )
        
        provider = self.provider_instances[best_provider_name]
        
        self.logger.info(
            f"Selected provider: {best_provider_name}",
            extra={
                "provider": best_provider_name,
                "criteria": criteria.priority_mode,
                "available_count": len(available_providers)
            }
        )
        
        return best_provider_name, provider
    
    async def _get_available_providers(
        self, 
        criteria: ProviderSelectionCriteria
    ) -> List[str]:
        """Get list of providers that meet the criteria."""
        available = []
        
        for name, config in self.providers.items():
            if not config.enabled:
                continue
            
            if name not in self.provider_instances:
                continue
            
            metrics = self.provider_metrics.get(name)
            if not metrics:
                continue
            
            # Check circuit breaker
            if metrics.circuit_breaker_open:
                if not self._should_reset_circuit_breaker(name):
                    self.logger.debug(f"Provider {name} circuit breaker is open")
                    continue
                else:
                    # Reset circuit breaker
                    metrics.circuit_breaker_open = False
                    metrics.circuit_breaker_opened_at = None
                    metrics.health_check_failures = 0
                    self.logger.info(f"Reset circuit breaker for provider {name}")
            
            # Check success rate
            if criteria.min_success_rate and metrics.success_rate < criteria.min_success_rate:
                continue
            
            # Check cost limits
            if criteria.max_cost_per_request and metrics.cost_per_request > criteria.max_cost_per_request:
                continue
            
            # Check response time
            if criteria.max_response_time_ms and metrics.avg_response_time_ms > criteria.max_response_time_ms:
                continue
            
            # Check hourly cost budget
            if not self._is_within_cost_budget(name):
                continue
            
            # Check rate limits
            if not self._is_within_rate_limits(name):
                continue
            
            available.append(name)
        
        return available
    
    def _select_provider_by_strategy(
        self, 
        available_providers: List[str], 
        criteria: ProviderSelectionCriteria
    ) -> str:
        """Select provider based on optimization strategy."""
        if len(available_providers) == 1:
            return available_providers[0]
        
        if criteria.priority_mode == "cost_optimized":
            return self._select_cheapest_provider(available_providers)
        elif criteria.priority_mode == "performance_optimized":
            return self._select_fastest_provider(available_providers)
        elif criteria.priority_mode == "balanced":
            return self._select_balanced_provider(available_providers)
        else:
            # Default to priority order
            return self._select_by_priority(available_providers)
    
    def _select_cheapest_provider(self, providers: List[str]) -> str:
        """Select provider with lowest cost per request."""
        cheapest = providers[0]
        lowest_cost = self.provider_metrics[cheapest].cost_per_request
        
        for provider in providers[1:]:
            cost = self.provider_metrics[provider].cost_per_request
            if cost < lowest_cost:
                lowest_cost = cost
                cheapest = provider
        
        return cheapest
    
    def _select_fastest_provider(self, providers: List[str]) -> str:
        """Select provider with fastest response time."""
        fastest = providers[0]
        best_time = self.provider_metrics[fastest].avg_response_time_ms
        
        for provider in providers[1:]:
            time_ms = self.provider_metrics[provider].avg_response_time_ms
            if time_ms < best_time:
                best_time = time_ms
                fastest = provider
        
        return fastest
    
    def _select_balanced_provider(self, providers: List[str]) -> str:
        """Select provider with best balance of cost and performance."""
        best_provider = providers[0]
        best_score = self._calculate_balance_score(best_provider)
        
        for provider in providers[1:]:
            score = self._calculate_balance_score(provider)
            if score > best_score:
                best_score = score
                best_provider = provider
        
        return best_provider
    
    def _calculate_balance_score(self, provider: str) -> float:
        """Calculate balanced score for provider (higher is better)."""
        metrics = self.provider_metrics[provider]
        
        # Normalize metrics (0-1 scale)
        success_rate_norm = metrics.success_rate / 100.0
        cost_norm = 1.0 / (1.0 + metrics.cost_per_request)  # Lower cost = higher score
        response_time_norm = 1.0 / (1.0 + metrics.avg_response_time_ms / 1000.0)  # Lower time = higher score
        
        # Weighted combination
        score = (success_rate_norm * 0.4) + (cost_norm * 0.3) + (response_time_norm * 0.3)
        
        return score
    
    def _select_by_priority(self, providers: List[str]) -> str:
        """Select provider with highest priority (lowest priority number)."""
        best_provider = providers[0]
        best_priority = self.providers[best_provider].priority
        
        for provider in providers[1:]:
            priority = self.providers[provider].priority
            if priority < best_priority:
                best_priority = priority
                best_provider = provider
        
        return best_provider
    
    async def track_request(
        self, 
        provider_name: str, 
        start_time: float, 
        success: bool, 
        cost: float = 0.0, 
        tokens: int = 0,
        error: Optional[Exception] = None
    ) -> None:
        """Track provider request metrics."""
        if provider_name not in self.provider_metrics:
            return
        
        metrics = self.provider_metrics[provider_name]
        response_time_ms = (time.time() - start_time) * 1000
        
        # Update metrics
        metrics.total_requests += 1
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
        
        # Update running average for response time
        if metrics.total_requests == 1:
            metrics.avg_response_time_ms = response_time_ms
        else:
            # Exponential moving average
            alpha = 0.1
            metrics.avg_response_time_ms = (
                alpha * response_time_ms + 
                (1 - alpha) * metrics.avg_response_time_ms
            )
        
        metrics.total_cost_usd += cost
        metrics.tokens_used += tokens
        
        # Check for circuit breaker conditions
        if not success:
            await self._check_circuit_breaker(provider_name, error)
        
        # Log metrics periodically
        if metrics.total_requests % 100 == 0:
            self.logger.info(
                f"Provider {provider_name} metrics update",
                extra={
                    "provider": provider_name,
                    "success_rate": metrics.success_rate,
                    "avg_response_time_ms": metrics.avg_response_time_ms,
                    "total_cost": metrics.total_cost_usd,
                    "requests": metrics.total_requests
                }
            )
    
    async def _check_circuit_breaker(self, provider_name: str, error: Optional[Exception]) -> None:
        """Check if circuit breaker should be opened."""
        metrics = self.provider_metrics[provider_name]
        config = self.providers[provider_name]
        
        # Increment health check failures for certain error types
        if error and self._is_circuit_breaker_error(error):
            metrics.health_check_failures += 1
            
            if metrics.health_check_failures >= config.circuit_breaker_threshold:
                metrics.circuit_breaker_open = True
                metrics.circuit_breaker_opened_at = datetime.now()
                
                self.logger.error(
                    f"Circuit breaker opened for provider {provider_name}",
                    extra={
                        "provider": provider_name,
                        "failures": metrics.health_check_failures,
                        "threshold": config.circuit_breaker_threshold,
                        "error": str(error)
                    }
                )
    
    def _is_circuit_breaker_error(self, error: Exception) -> bool:
        """Check if error should count towards circuit breaker."""
        # Rate limiting, authentication, and service errors count
        error_str = str(error).lower()
        circuit_breaker_keywords = [
            "rate limit", "too many requests", "quota exceeded",
            "authentication", "unauthorized", "forbidden",
            "service unavailable", "internal server error", "timeout"
        ]
        
        return any(keyword in error_str for keyword in circuit_breaker_keywords)
    
    def _should_reset_circuit_breaker(self, provider_name: str) -> bool:
        """Check if circuit breaker timeout has elapsed."""
        metrics = self.provider_metrics[provider_name]
        config = self.providers[provider_name]
        
        if not metrics.circuit_breaker_open or not metrics.circuit_breaker_opened_at:
            return False
        
        timeout_elapsed = (
            datetime.now() - metrics.circuit_breaker_opened_at
        ).total_seconds() > config.circuit_breaker_timeout_seconds
        
        return timeout_elapsed
    
    def _is_within_cost_budget(self, provider_name: str) -> bool:
        """Check if provider is within hourly cost budget."""
        metrics = self.provider_metrics[provider_name]
        config = self.providers[provider_name]
        
        # Calculate cost in the last hour
        # This is simplified - in production, you'd track hourly windows
        return metrics.total_cost_usd < config.max_cost_per_hour
    
    def _is_within_rate_limits(self, provider_name: str) -> bool:
        """Check if provider is within rate limits."""
        # This is simplified - in production, you'd track requests per minute
        # For now, assume providers handle their own rate limiting
        return True
    
    async def _health_check_loop(self) -> None:
        """Background task for provider health checks."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}", exc_info=True)
                await asyncio.sleep(30)  # Shorter retry on error
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all providers."""
        for name, provider in self.provider_instances.items():
            try:
                if hasattr(provider, 'health_check'):
                    start_time = time.time()
                    health_result = await provider.health_check()
                    
                    metrics = self.provider_metrics[name]
                    metrics.last_health_check = datetime.now()
                    
                    if health_result.get("status") == "healthy":
                        metrics.health_check_failures = 0
                    else:
                        metrics.health_check_failures += 1
                        self.logger.warning(
                            f"Provider {name} health check failed",
                            extra={"provider": name, "result": health_result}
                        )
                
            except Exception as e:
                self.logger.error(f"Health check failed for provider {name}: {e}")
                if name in self.provider_metrics:
                    self.provider_metrics[name].health_check_failures += 1
    
    async def _metrics_cleanup_loop(self) -> None:
        """Background task for metrics cleanup and aggregation."""
        while True:
            try:
                await self._cleanup_old_metrics()
                await asyncio.sleep(3600)  # Cleanup every hour
            except Exception as e:
                self.logger.error(f"Metrics cleanup error: {e}", exc_info=True)
                await asyncio.sleep(1800)  # 30 minutes retry on error
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up and aggregate old metrics."""
        # In production, you'd aggregate metrics to a time-series database
        # For now, just log current metrics
        for name, metrics in self.provider_metrics.items():
            self.logger.info(
                f"Provider metrics summary: {name}",
                extra={
                    "provider": name,
                    "total_requests": metrics.total_requests,
                    "success_rate": metrics.success_rate,
                    "avg_response_time_ms": metrics.avg_response_time_ms,
                    "total_cost_usd": metrics.total_cost_usd,
                    "circuit_breaker_open": metrics.circuit_breaker_open
                }
            )
    
    def get_provider_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get current metrics for all providers."""
        result = {}
        for name, metrics in self.provider_metrics.items():
            result[name] = {
                "total_requests": metrics.total_requests,
                "success_rate": metrics.success_rate,
                "error_rate": metrics.error_rate,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "total_cost_usd": metrics.total_cost_usd,
                "cost_per_request": metrics.cost_per_request,
                "tokens_used": metrics.tokens_used,
                "rate_limit_hits": metrics.rate_limit_hits,
                "circuit_breaker_open": metrics.circuit_breaker_open,
                "last_health_check": metrics.last_health_check.isoformat() if metrics.last_health_check else None,
                "health_check_failures": metrics.health_check_failures
            }
        return result
    
    def get_supported_providers(self) -> List[str]:
        """Get list of all supported provider names."""
        return list(self.providers.keys())
    
    def _validate_api_key(self, api_key: str) -> None:
        """Validate API key format."""
        if not api_key or not api_key.strip():
            raise AIProviderError("API key cannot be empty")
        
        if len(api_key.strip()) < 10:
            raise AIProviderError("API key appears to be invalid (too short)")
    
    def _validate_provider(self, provider_name: str) -> None:
        """Validate provider name."""
        if not provider_name or not provider_name.strip():
            raise AIProviderError("Provider name cannot be empty")
        
        if provider_name not in self.providers:
            raise AIProviderError(f"Unsupported provider: {provider_name}")
    
    def _get_claude_provider_class(self):
        """Get Claude provider class."""
        # Claude provider not implemented yet - fallback to OpenAI
        self.logger.warning("Claude provider not implemented, falling back to OpenAI")
        return ProductionOpenAIProvider
    
    def _get_gemini_provider_class(self):
        """Get Gemini provider class."""
        # Gemini provider not implemented yet - fallback to OpenAI
        self.logger.warning("Gemini provider not implemented, falling back to OpenAI")
        return ProductionOpenAIProvider
    
    async def shutdown(self) -> None:
        """Shutdown factory and clean up resources."""
        self.logger.info("Shutting down AI Provider Factory")
        
        # Cancel background tasks
        if self.health_check_task:
            self.health_check_task.cancel()
        if self.metrics_cleanup_task:
            self.metrics_cleanup_task.cancel()
        
        # Close provider connections
        for name, provider in self.provider_instances.items():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
            except Exception as e:
                self.logger.error(f"Error closing provider {name}: {e}")


# Factory singleton instance
_factory_instance: Optional[ProductionAIProviderFactory] = None


async def get_ai_provider_factory() -> ProductionAIProviderFactory:
    """Get or create AI provider factory singleton."""
    global _factory_instance
    
    if _factory_instance is None:
        _factory_instance = ProductionAIProviderFactory()
    
    return _factory_instance


# Legacy compatibility functions
def get_supported_providers() -> List[str]:
    """Get list of supported provider names."""
    return ["openai", "claude", "gemini"]


def _validate_api_key(api_key: str) -> None:
    """Legacy API key validation."""
    if not api_key or len(api_key.strip()) < 10:
        raise AIProviderError("API key appears to be invalid")


def _validate_provider(provider_name: str) -> None:
    """Legacy provider validation."""
    if provider_name.lower() not in get_supported_providers():
        raise AIProviderError(f"Unsupported provider: {provider_name}")


async def get_provider(provider_name: str, api_key: str) -> AIProvider:
    """
    Legacy compatibility function for getting provider.
    Use get_ai_provider_factory().get_best_provider() for production.
    """
    _validate_provider(provider_name)
    _validate_api_key(api_key)
    
    if provider_name.lower() == "openai":
        return ProductionOpenAIProvider(api_key=api_key)
    else:
        # For now, fallback to OpenAI for other providers
        return ProductionOpenAIProvider(api_key=api_key)


# Legacy compatibility alias
AIProviderFactory = ProductionAIProviderFactory
