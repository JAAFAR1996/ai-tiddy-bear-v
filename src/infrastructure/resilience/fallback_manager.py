"""
Production Fallback Manager - Service Resilience Core
====================================================
Enterprise-grade fallback strategy management with:
- Service-specific fallback definitions and policies
- Comprehensive failure detection and recovery logging
- Metrics collection and circuit breaker integration
- Multi-tier fallback cascading with health monitoring
- Cost-aware fallback selection and priority management
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from abc import ABC, abstractmethod


class FallbackTier(Enum):
    """Fallback tier levels in order of preference."""
    PRIMARY = "primary"      # Main service
    SECONDARY = "secondary"  # First fallback
    TERTIARY = "tertiary"   # Second fallback
    EMERGENCY = "emergency"  # Last resort
    OFFLINE = "offline"     # Local/cached response


class FailureReason(Enum):
    """Service failure reasons for targeted fallback selection."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"
    VALIDATION_ERROR = "validation_error"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    HEALTH_CHECK_FAILED = "health_check_failed"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FallbackRule:
    """Individual fallback rule configuration."""
    service_name: str
    failure_reasons: List[FailureReason]
    target_tier: FallbackTier
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    cost_multiplier: float = 1.0
    priority: int = 0  # Lower = higher priority
    health_check_required: bool = True
    
    def matches_failure(self, reason: FailureReason) -> bool:
        """Check if this rule applies to the given failure reason."""
        return reason in self.failure_reasons


@dataclass
class ServiceFallbackConfig:
    """Complete fallback configuration for a service."""
    service_name: str
    enabled: bool = True
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60
    
    # Tier definitions with providers
    tier_providers: Dict[FallbackTier, List[str]] = field(default_factory=dict)
    
    # Fallback rules
    rules: List[FallbackRule] = field(default_factory=list)
    
    # Health check configuration
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 10
    
    # Metrics and logging
    log_all_failures: bool = True
    log_fallback_decisions: bool = True
    track_response_times: bool = True
    
    def get_providers_for_tier(self, tier: FallbackTier) -> List[str]:
        """Get provider names for a specific tier."""
        return self.tier_providers.get(tier, [])
    
    def get_fallback_rule(self, failure_reason: FailureReason) -> Optional[FallbackRule]:
        """Get the most appropriate fallback rule for a failure reason."""
        matching_rules = [rule for rule in self.rules if rule.matches_failure(failure_reason)]
        if not matching_rules:
            return None
        
        # Return rule with highest priority (lowest priority number)
        return min(matching_rules, key=lambda rule: rule.priority)


@dataclass
class FallbackAttempt:
    """Record of a fallback attempt."""
    service_name: str
    original_provider: str
    failure_reason: FailureReason
    fallback_tier: FallbackTier
    fallback_provider: str
    attempt_number: int
    timestamp: datetime
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    cost_estimate: Optional[float] = None


@dataclass
class ServiceMetrics:
    """Service performance and fallback metrics."""
    service_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    fallback_triggered_count: int = 0
    fallback_success_count: int = 0
    average_response_time_ms: float = 0.0
    cost_total: float = 0.0
    
    # Per-tier metrics
    tier_usage_count: Dict[FallbackTier, int] = field(default_factory=dict)
    tier_success_rate: Dict[FallbackTier, float] = field(default_factory=dict)
    
    # Failure reason tracking
    failure_reasons: Dict[FailureReason, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def fallback_success_rate(self) -> float:
        """Calculate fallback success rate."""
        if self.fallback_triggered_count == 0:
            return 0.0
        return (self.fallback_success_count / self.fallback_triggered_count) * 100


class ServiceFallbackManager:
    """
    Production-grade fallback manager for service resilience.
    
    Features:
    - Service-specific fallback configurations
    - Multi-tier fallback cascading
    - Failure reason analysis and targeted fallback selection
    - Circuit breaker integration
    - Comprehensive metrics and logging
    - Cost-aware fallback decisions
    - Health monitoring and recovery detection
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Service configurations
        self.service_configs: Dict[str, ServiceFallbackConfig] = {}
        
        # Service metrics
        self.service_metrics: Dict[str, ServiceMetrics] = {}
        
        # Circuit breaker states
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Fallback attempt history (for analysis)
        self.fallback_history: List[FallbackAttempt] = []
        self.max_history_size = 10000
        
        # Health check results cache
        self.health_check_cache: Dict[str, Dict[str, Any]] = {}
        
        # Background tasks
        self.health_check_task: Optional[asyncio.Task] = None
        
        self.logger.info("ServiceFallbackManager initialized")
    
    def register_service(self, config: ServiceFallbackConfig) -> None:
        """Register a service with its fallback configuration."""
        service_name = config.service_name
        
        self.service_configs[service_name] = config
        self.service_metrics[service_name] = ServiceMetrics(service_name=service_name)
        
        # Initialize circuit breakers for each provider
        self.circuit_breakers[service_name] = {}
        for tier, providers in config.tier_providers.items():
            for provider in providers:
                provider_key = f"{service_name}:{provider}"
                self.circuit_breakers[service_name][provider] = {
                    "state": "closed",  # closed, open, half_open
                    "failure_count": 0,
                    "last_failure": None,
                    "next_attempt_time": None
                }
        
        self.logger.info(
            f"Registered service fallback configuration",
            extra={
                "service_name": service_name,
                "tier_count": len(config.tier_providers),
                "rule_count": len(config.rules),
                "circuit_breaker_enabled": config.circuit_breaker_enabled
            }
        )
    
    async def execute_with_fallback(
        self,
        service_name: str,
        operation: Callable,
        *args,
        failure_detector: Optional[Callable[[Exception], FailureReason]] = None,
        **kwargs
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Execute an operation with comprehensive fallback support.
        
        Args:
            service_name: Name of the service
            operation: Async callable to execute
            failure_detector: Function to categorize exceptions
            *args, **kwargs: Arguments for the operation
            
        Returns:
            Tuple of (result, metadata)
        """
        config = self.service_configs.get(service_name)
        if not config or not config.enabled:
            raise ValueError(f"Service {service_name} not registered or disabled")
        
        metrics = self.service_metrics[service_name]
        metrics.total_requests += 1
        
        start_time = time.time()
        metadata = {
            "service_name": service_name,
            "fallback_attempts": [],
            "total_attempts": 0,
            "final_tier": None,
            "final_provider": None,
            "success": False
        }
        
        # Try primary tier first
        for tier in [FallbackTier.PRIMARY, FallbackTier.SECONDARY, FallbackTier.TERTIARY, FallbackTier.EMERGENCY]:
            providers = config.get_providers_for_tier(tier)
            if not providers:
                continue
            
            for provider in providers:
                if not self._is_provider_available(service_name, provider):
                    self.logger.debug(
                        f"Skipping unavailable provider",
                        extra={
                            "service_name": service_name,
                            "provider": provider,
                            "tier": tier.value
                        }
                    )
                    continue
                
                try:
                    metadata["total_attempts"] += 1
                    attempt_start = time.time()
                    
                    # Execute operation
                    result = await operation(*args, provider=provider, **kwargs)
                    
                    # Success!
                    response_time = (time.time() - attempt_start) * 1000
                    
                    # Update metrics
                    metrics.successful_requests += 1
                    self._update_response_time(metrics, response_time)
                    self._update_tier_success(metrics, tier, True)
                    self._record_circuit_breaker_success(service_name, provider)
                    
                    metadata.update({
                        "final_tier": tier.value,
                        "final_provider": provider,
                        "success": True,
                        "response_time_ms": response_time
                    })
                    
                    self.logger.info(
                        f"Operation successful",
                        extra={
                            "service_name": service_name,
                            "provider": provider,
                            "tier": tier.value,
                            "response_time_ms": response_time,
                            "attempts": metadata["total_attempts"]
                        }
                    )
                    
                    return result, metadata
                    
                except Exception as e:
                    response_time = (time.time() - attempt_start) * 1000
                    failure_reason = self._detect_failure_reason(e, failure_detector)
                    
                    # Record failure
                    self._record_failure(service_name, provider, tier, failure_reason, str(e), response_time)
                    
                    # Update circuit breaker
                    self._record_circuit_breaker_failure(service_name, provider, config)
                    
                    # Log failure
                    if config.log_all_failures:
                        self.logger.warning(
                            f"Operation failed, attempting fallback",
                            extra={
                                "service_name": service_name,
                                "provider": provider,
                                "tier": tier.value,
                                "failure_reason": failure_reason.value,
                                "error": str(e),
                                "response_time_ms": response_time
                            }
                        )
                    
                    # Check if we should continue to next provider/tier
                    fallback_rule = config.get_fallback_rule(failure_reason)
                    if fallback_rule and tier.value != fallback_rule.target_tier.value:
                        # Skip to target tier
                        continue
        
        # All attempts failed
        total_time = (time.time() - start_time) * 1000
        metrics.failed_requests += 1
        
        self.logger.error(
            f"All fallback attempts failed",
            extra={
                "service_name": service_name,
                "total_attempts": metadata["total_attempts"],
                "total_time_ms": total_time
            }
        )
        
        # Try offline/cached response as last resort
        offline_result = await self._try_offline_fallback(service_name, *args, **kwargs)
        if offline_result is not None:
            metadata.update({
                "final_tier": FallbackTier.OFFLINE.value,
                "final_provider": "offline_cache",
                "success": True
            })
            return offline_result, metadata
        
        raise RuntimeError(f"All fallback attempts failed for service {service_name}")
    
    def _detect_failure_reason(
        self,
        exception: Exception,
        failure_detector: Optional[Callable[[Exception], FailureReason]] = None
    ) -> FailureReason:
        """Detect failure reason from exception."""
        if failure_detector:
            try:
                return failure_detector(exception)
            except Exception:
                pass
        
        # Default failure reason detection
        error_str = str(exception).lower()
        
        if "timeout" in error_str:
            return FailureReason.TIMEOUT
        elif "connection" in error_str or "network" in error_str:
            return FailureReason.CONNECTION_ERROR
        elif "auth" in error_str or "unauthorized" in error_str:
            return FailureReason.AUTHENTICATION_ERROR
        elif "rate limit" in error_str or "too many requests" in error_str:
            return FailureReason.RATE_LIMIT_EXCEEDED
        elif "quota" in error_str or "limit exceeded" in error_str:
            return FailureReason.QUOTA_EXCEEDED
        elif "unavailable" in error_str or "503" in error_str:
            return FailureReason.SERVICE_UNAVAILABLE
        elif "validation" in error_str or "invalid" in error_str:
            return FailureReason.VALIDATION_ERROR
        else:
            return FailureReason.UNKNOWN_ERROR
    
    def _is_provider_available(self, service_name: str, provider: str) -> bool:
        """Check if provider is available (circuit breaker state)."""
        circuit_breaker = self.circuit_breakers.get(service_name, {}).get(provider)
        if not circuit_breaker:
            return True
        
        state = circuit_breaker["state"]
        
        if state == "closed":
            return True
        elif state == "open":
            # Check if we should try half-open
            next_attempt = circuit_breaker.get("next_attempt_time")
            if next_attempt and datetime.now() >= next_attempt:
                circuit_breaker["state"] = "half_open"
                return True
            return False
        elif state == "half_open":
            return True
        
        return False
    
    def _record_circuit_breaker_failure(
        self,
        service_name: str,
        provider: str,
        config: ServiceFallbackConfig
    ) -> None:
        """Record circuit breaker failure."""
        if not config.circuit_breaker_enabled:
            return
        
        circuit_breaker = self.circuit_breakers.get(service_name, {}).get(provider)
        if not circuit_breaker:
            return
        
        circuit_breaker["failure_count"] += 1
        circuit_breaker["last_failure"] = datetime.now()
        
        # Check if we should open the circuit breaker
        if circuit_breaker["failure_count"] >= config.circuit_breaker_threshold:
            circuit_breaker["state"] = "open"
            circuit_breaker["next_attempt_time"] = (
                datetime.now() + timedelta(seconds=config.circuit_breaker_timeout_seconds)
            )
            
            self.logger.warning(
                f"Circuit breaker opened",
                extra={
                    "service_name": service_name,
                    "provider": provider,
                    "failure_count": circuit_breaker["failure_count"],
                    "threshold": config.circuit_breaker_threshold
                }
            )
    
    def _record_circuit_breaker_success(self, service_name: str, provider: str) -> None:
        """Record circuit breaker success."""
        circuit_breaker = self.circuit_breakers.get(service_name, {}).get(provider)
        if not circuit_breaker:
            return
        
        # Reset failure count and close circuit breaker
        circuit_breaker["failure_count"] = 0
        circuit_breaker["state"] = "closed"
        circuit_breaker["next_attempt_time"] = None
    
    def _record_failure(
        self,
        service_name: str,
        provider: str,
        tier: FallbackTier,
        failure_reason: FailureReason,
        error_message: str,
        response_time_ms: float
    ) -> None:
        """Record failure attempt for metrics and history."""
        metrics = self.service_metrics[service_name]
        
        # Update failure reason counts
        if failure_reason not in metrics.failure_reasons:
            metrics.failure_reasons[failure_reason] = 0
        metrics.failure_reasons[failure_reason] += 1
        
        # Update tier metrics
        self._update_tier_success(metrics, tier, False)
        
        # Record in history
        attempt = FallbackAttempt(
            service_name=service_name,
            original_provider=provider,
            failure_reason=failure_reason,
            fallback_tier=tier,
            fallback_provider=provider,
            attempt_number=len(self.fallback_history) + 1,
            timestamp=datetime.now(),
            success=False,
            response_time_ms=response_time_ms,
            error_message=error_message
        )
        
        self.fallback_history.append(attempt)
        
        # Limit history size
        if len(self.fallback_history) > self.max_history_size:
            self.fallback_history = self.fallback_history[-self.max_history_size//2:]
    
    def _update_response_time(self, metrics: ServiceMetrics, response_time_ms: float) -> None:
        """Update average response time."""
        total_successful = metrics.successful_requests
        if total_successful == 1:
            metrics.average_response_time_ms = response_time_ms
        else:
            total_time = metrics.average_response_time_ms * (total_successful - 1)
            metrics.average_response_time_ms = (total_time + response_time_ms) / total_successful
    
    def _update_tier_success(self, metrics: ServiceMetrics, tier: FallbackTier, success: bool) -> None:
        """Update tier usage and success rate."""
        if tier not in metrics.tier_usage_count:
            metrics.tier_usage_count[tier] = 0
            metrics.tier_success_rate[tier] = 0.0
        
        metrics.tier_usage_count[tier] += 1
        
        if success:
            current_success_count = metrics.tier_success_rate[tier] * (metrics.tier_usage_count[tier] - 1)
            new_success_count = current_success_count + 1
            metrics.tier_success_rate[tier] = new_success_count / metrics.tier_usage_count[tier]
        else:
            current_success_count = metrics.tier_success_rate[tier] * (metrics.tier_usage_count[tier] - 1)
            metrics.tier_success_rate[tier] = current_success_count / metrics.tier_usage_count[tier]
    
    async def _try_offline_fallback(self, service_name: str, *args, **kwargs) -> Optional[Any]:
        """Try offline/cached fallback as last resort."""
        # This would integrate with caching service
        # For now, return None to indicate no offline fallback available
        return None
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive metrics for a service."""
        metrics = self.service_metrics.get(service_name)
        if not metrics:
            return None
        
        return {
            "service_name": metrics.service_name,
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": metrics.success_rate,
            "fallback_triggered_count": metrics.fallback_triggered_count,
            "fallback_success_count": metrics.fallback_success_count,
            "fallback_success_rate": metrics.fallback_success_rate,
            "average_response_time_ms": metrics.average_response_time_ms,
            "cost_total": metrics.cost_total,
            "tier_usage": {tier.value: count for tier, count in metrics.tier_usage_count.items()},
            "tier_success_rates": {tier.value: rate for tier, rate in metrics.tier_success_rate.items()},
            "failure_reasons": {reason.value: count for reason, count in metrics.failure_reasons.items()},
            "circuit_breaker_states": {
                provider: state["state"] for provider, state in 
                self.circuit_breakers.get(service_name, {}).items()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all registered services."""
        return {
            service_name: self.get_service_metrics(service_name)
            for service_name in self.service_configs.keys()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on fallback manager."""
        try:
            total_services = len(self.service_configs)
            healthy_services = 0
            
            service_health = {}
            
            for service_name, config in self.service_configs.items():
                metrics = self.service_metrics[service_name]
                
                # Consider service healthy if success rate > 80%
                is_healthy = metrics.success_rate > 80.0 if metrics.total_requests > 0 else True
                
                if is_healthy:
                    healthy_services += 1
                
                service_health[service_name] = {
                    "healthy": is_healthy,
                    "success_rate": metrics.success_rate,
                    "total_requests": metrics.total_requests,
                    "circuit_breakers_open": len([
                        cb for cb in self.circuit_breakers.get(service_name, {}).values()
                        if cb["state"] == "open"
                    ])
                }
            
            overall_health = "healthy" if healthy_services / max(total_services, 1) > 0.8 else "degraded"
            
            return {
                "status": overall_health,
                "total_services": total_services,
                "healthy_services": healthy_services,
                "services": service_health,
                "fallback_history_size": len(self.fallback_history),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Fallback manager health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
