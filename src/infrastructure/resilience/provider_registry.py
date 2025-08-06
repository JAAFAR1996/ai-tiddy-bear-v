"""
Provider Registry - Centralized Provider Management
=================================================
Enterprise provider registry with circuit breakers and health monitoring:
- Centralized provider configuration and management
- Automatic circuit breaker and health monitor setup
- Provider discovery and load balancing
- Geographic and cost-aware routing
- Real-time provider status dashboard
- Automated failover and recovery
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .provider_circuit_breaker import ProviderCircuitBreaker, CircuitBreakerConfig, ProviderType, CircuitState
from .provider_health_monitor import ProviderHealthMonitor, HealthStatus, HealthCheckType, SLAMetrics
from .fallback_logger import FallbackLogger, LogContext, EventType
from ..messaging.event_bus_integration import EventPublisher


class ProviderStatus(Enum):
    """Overall provider status."""
    ACTIVE = "active"                    # Healthy and accepting requests
    DEGRADED = "degraded"               # Functional but with issues
    MAINTENANCE = "maintenance"          # Planned maintenance
    UNAVAILABLE = "unavailable"         # Not accessible
    DISABLED = "disabled"               # Manually disabled


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    HEALTH_WEIGHTED = "health_weighted"
    COST_OPTIMIZED = "cost_optimized"
    GEOGRAPHIC = "geographic"
    CAPACITY_BASED = "capacity_based"


@dataclass
class ProviderConfiguration:
    """Provider configuration."""
    provider_id: str
    provider_type: ProviderType
    name: str
    description: str = ""
    
    # Connection settings
    endpoint_url: str = ""
    api_key: str = ""
    region: str = "unknown"
    
    # Circuit breaker configuration
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    
    # Health monitoring configuration
    enable_health_monitoring: bool = True
    health_check_interval: int = 60
    
    # Load balancing settings
    weight: int = 100                    # Load balancing weight
    max_concurrent_requests: int = 100   # Maximum concurrent requests
    priority: int = 1                    # Priority (1 = highest)
    
    # Cost settings
    cost_per_request: float = 0.0
    cost_per_gb: float = 0.0
    monthly_quota: float = 0.0
    
    # Feature flags
    enabled: bool = True
    maintenance_mode: bool = False
    
    # Tags and metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderMetrics:
    """Runtime provider metrics."""
    provider_id: str
    status: ProviderStatus = ProviderStatus.ACTIVE
    
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    active_requests: int = 0
    
    # Performance metrics
    average_response_time: float = 0.0
    p95_response_time: float = 0.0
    success_rate: float = 100.0
    
    # Health metrics
    health_score: float = 100.0
    last_health_check: Optional[datetime] = None
    circuit_breaker_state: str = "closed"
    
    # Cost metrics
    total_cost: float = 0.0
    cost_per_minute: float = 0.0
    
    # Load balancing metrics
    current_weight: int = 100
    load_factor: float = 0.0
    
    # Timestamps
    last_request_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ProviderRegistry:
    """
    Centralized provider registry with circuit breakers and health monitoring.
    
    Features:
    - Automatic circuit breaker and health monitor setup
    - Provider discovery and selection
    - Load balancing with multiple strategies
    - Geographic and cost-aware routing
    - Real-time metrics and monitoring
    - Automated failover and recovery
    """
    
    def __init__(self):
        self.logger = FallbackLogger("provider_registry")
        
        # Provider storage
        self.providers: Dict[str, ProviderConfiguration] = {}
        self.circuit_breakers: Dict[str, ProviderCircuitBreaker] = {}
        self.health_monitors: Dict[str, ProviderHealthMonitor] = {}
        self.provider_metrics: Dict[str, ProviderMetrics] = {}
        
        # Provider grouping
        self.providers_by_type: Dict[ProviderType, List[str]] = defaultdict(list)
        self.providers_by_region: Dict[str, List[str]] = defaultdict(list)
        self.providers_by_status: Dict[ProviderStatus, Set[str]] = defaultdict(set)
        
        # Load balancing
        self.load_balancing_strategies: Dict[str, Callable] = {
            LoadBalancingStrategy.ROUND_ROBIN.value: self._round_robin_selection,
            LoadBalancingStrategy.LEAST_LATENCY.value: self._least_latency_selection,
            LoadBalancingStrategy.HEALTH_WEIGHTED.value: self._health_weighted_selection,
            LoadBalancingStrategy.COST_OPTIMIZED.value: self._cost_optimized_selection,
            LoadBalancingStrategy.GEOGRAPHIC.value: self._geographic_selection,
            LoadBalancingStrategy.CAPACITY_BASED.value: self._capacity_based_selection
        }
        
        # Round robin state
        self._round_robin_counters: Dict[str, int] = defaultdict(int)
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Event callbacks
        self.on_provider_status_change: Optional[Callable] = None
        self.on_provider_failure: Optional[Callable] = None
        self.on_provider_recovery: Optional[Callable] = None
    
    async def start(self):
        """Start the provider registry."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start background tasks
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Provider registry started")
    
    async def stop(self):
        """Stop the provider registry."""
        self.is_running = False
        
        # Stop all health monitors
        for health_monitor in self.health_monitors.values():
            await health_monitor.stop_monitoring()
        
        # Cancel background tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Wait for tasks to complete
        tasks = [t for t in [self._monitoring_task, self._cleanup_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.logger.info("Provider registry stopped")
    
    async def register_provider(self, config: ProviderConfiguration) -> str:
        """Register a new provider."""
        provider_id = config.provider_id
        
        # Store provider configuration
        self.providers[provider_id] = config
        
        # Initialize metrics
        self.provider_metrics[provider_id] = ProviderMetrics(provider_id=provider_id)
        
        # Create circuit breaker
        if config.circuit_breaker_config:
            cb_config = config.circuit_breaker_config
        else:
            cb_config = CircuitBreakerConfig(
                provider_id=provider_id,
                provider_type=config.provider_type
            )
        
        circuit_breaker = ProviderCircuitBreaker(cb_config)
        self.circuit_breakers[provider_id] = circuit_breaker
        
        # Set up circuit breaker callbacks
        circuit_breaker.on_state_change = self._on_circuit_breaker_state_change
        circuit_breaker.on_failure = self._on_circuit_breaker_failure
        circuit_breaker.on_success = self._on_circuit_breaker_success
        
        # Create health monitor if enabled
        if config.enable_health_monitoring:
            health_monitor = ProviderHealthMonitor(
                provider_id=provider_id,
                provider_type=config.provider_type,
                circuit_breaker=circuit_breaker
            )
            
            self.health_monitors[provider_id] = health_monitor
            await health_monitor.start_monitoring()
        
        # Update provider groupings
        self.providers_by_type[config.provider_type].append(provider_id)
        self.providers_by_region[config.region].append(provider_id)
        
        if config.enabled and not config.maintenance_mode:
            self.providers_by_status[ProviderStatus.ACTIVE].add(provider_id)
        else:
            self.providers_by_status[ProviderStatus.DISABLED].add(provider_id)
        
        self.logger.info(
            f"Provider registered: {provider_id}",
            extra={
                "provider_id": provider_id,
                "provider_type": config.provider_type.value,
                "region": config.region,
                "enabled": config.enabled
            }
        )
        
        # Publish registration event
        await EventPublisher.publish_system_event(
            event_type="provider.registered",
            payload={
                "provider_id": provider_id,
                "provider_type": config.provider_type.value,
                "region": config.region,
                "enabled": config.enabled,
                "has_circuit_breaker": True,
                "has_health_monitoring": config.enable_health_monitoring
            }
        )
        
        return provider_id
    
    async def unregister_provider(self, provider_id: str):
        """Unregister a provider."""
        if provider_id not in self.providers:
            return
        
        config = self.providers[provider_id]
        
        # Stop health monitoring
        if provider_id in self.health_monitors:
            await self.health_monitors[provider_id].stop_monitoring()
            del self.health_monitors[provider_id]
        
        # Remove from groupings
        self.providers_by_type[config.provider_type].remove(provider_id)
        self.providers_by_region[config.region].remove(provider_id)
        
        for status, provider_set in self.providers_by_status.items():
            provider_set.discard(provider_id)
        
        # Clean up
        del self.providers[provider_id]
        del self.circuit_breakers[provider_id]
        del self.provider_metrics[provider_id]
        
        self.logger.info(f"Provider unregistered: {provider_id}")
        
        # Publish unregistration event
        await EventPublisher.publish_system_event(
            event_type="provider.unregistered",
            payload={"provider_id": provider_id}
        )
    
    async def select_provider(
        self,
        provider_type: Optional[ProviderType] = None,
        region: Optional[str] = None,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.HEALTH_WEIGHTED,
        exclude: Optional[List[str]] = None,
        max_cost: Optional[float] = None
    ) -> Optional[str]:
        """Select best provider based on criteria."""
        # Get candidate providers
        candidates = self._get_candidate_providers(
            provider_type=provider_type,
            region=region,
            exclude=exclude or [],
            max_cost=max_cost
        )
        
        if not candidates:
            return None
        
        # Apply load balancing strategy
        strategy_func = self.load_balancing_strategies.get(strategy.value)
        if strategy_func:
            selected = strategy_func(candidates)
            if selected:
                return selected[0]  # Return the top choice
        
        # Fallback to first available
        return candidates[0] if candidates else None
    
    async def select_providers(
        self,
        count: int,
        provider_type: Optional[ProviderType] = None,
        region: Optional[str] = None,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.HEALTH_WEIGHTED,
        exclude: Optional[List[str]] = None,
        max_cost: Optional[float] = None
    ) -> List[str]:
        """Select multiple providers based on criteria."""
        candidates = self._get_candidate_providers(
            provider_type=provider_type,
            region=region,
            exclude=exclude or [],
            max_cost=max_cost
        )
        
        if not candidates:
            return []
        
        # Apply load balancing strategy
        strategy_func = self.load_balancing_strategies.get(strategy.value)
        if strategy_func:
            ordered = strategy_func(candidates)
            return ordered[:min(count, len(ordered))]
        
        return candidates[:min(count, len(candidates))]
    
    def _get_candidate_providers(
        self,
        provider_type: Optional[ProviderType] = None,
        region: Optional[str] = None,
        exclude: List[str] = None,
        max_cost: Optional[float] = None
    ) -> List[str]:
        """Get list of candidate providers based on filters."""
        exclude = exclude or []
        candidates = []
        
        # Start with all active providers
        active_providers = self.providers_by_status[ProviderStatus.ACTIVE].copy()
        
        # Filter by type
        if provider_type:
            type_providers = set(self.providers_by_type[provider_type])
            active_providers &= type_providers
        
        # Filter by region
        if region:
            region_providers = set(self.providers_by_region[region])
            active_providers &= region_providers
        
        # Remove excluded providers
        active_providers -= set(exclude)
        
        # Filter by additional criteria
        for provider_id in active_providers:
            config = self.providers[provider_id]
            metrics = self.provider_metrics[provider_id]
            circuit_breaker = self.circuit_breakers[provider_id]
            
            # Skip disabled providers
            if not config.enabled or config.maintenance_mode:
                continue
            
            # Skip providers with open circuit breakers
            if circuit_breaker.state == CircuitState.OPEN:
                continue
            
            # Check cost limit
            if max_cost is not None and config.cost_per_request > max_cost:
                continue
            
            # Check capacity
            if metrics.active_requests >= config.max_concurrent_requests:
                continue
            
            candidates.append(provider_id)
        
        return candidates
    
    def _round_robin_selection(self, candidates: List[str]) -> List[str]:
        """Round robin provider selection."""
        if not candidates:
            return []
        
        # Use combined key for round robin counter
        key = "_".join(sorted(candidates))
        counter = self._round_robin_counters[key]
        
        # Select next provider
        selected = candidates[counter % len(candidates)]
        self._round_robin_counters[key] = (counter + 1) % len(candidates)
        
        # Return selected first, then others
        result = [selected]
        result.extend([p for p in candidates if p != selected])
        return result
    
    def _least_latency_selection(self, candidates: List[str]) -> List[str]:
        """Select providers by lowest latency."""
        def get_latency(provider_id: str) -> float:
            metrics = self.provider_metrics[provider_id]
            return metrics.average_response_time
        
        return sorted(candidates, key=get_latency)
    
    def _health_weighted_selection(self, candidates: List[str]) -> List[str]:
        """Select providers weighted by health score."""
        def get_health_score(provider_id: str) -> float:
            metrics = self.provider_metrics[provider_id]
            return -metrics.health_score  # Negative for descending sort
        
        return sorted(candidates, key=get_health_score)
    
    def _cost_optimized_selection(self, candidates: List[str]) -> List[str]:
        """Select providers by lowest cost."""
        def get_cost(provider_id: str) -> float:
            config = self.providers[provider_id]
            return config.cost_per_request
        
        return sorted(candidates, key=get_cost)
    
    def _geographic_selection(self, candidates: List[str]) -> List[str]:
        """Select providers by geographic preference."""
        # Group by region and prioritize local regions
        regions = defaultdict(list)
        for provider_id in candidates:
            config = self.providers[provider_id]
            regions[config.region].append(provider_id)
        
        # Prefer US regions, then EU, then others
        preferred_order = ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1"]
        result = []
        
        for region in preferred_order:
            if region in regions:
                # Sort by health score within region
                region_providers = self._health_weighted_selection(regions[region])
                result.extend(region_providers)
                del regions[region]
        
        # Add remaining regions
        for region_providers in regions.values():
            region_providers = self._health_weighted_selection(region_providers)
            result.extend(region_providers)
        
        return result
    
    def _capacity_based_selection(self, candidates: List[str]) -> List[str]:
        """Select providers by available capacity."""
        def get_capacity_score(provider_id: str) -> float:
            config = self.providers[provider_id]
            metrics = self.provider_metrics[provider_id]
            
            if config.max_concurrent_requests == 0:
                return 0.0
            
            utilization = metrics.active_requests / config.max_concurrent_requests
            return utilization  # Lower utilization is better
        
        return sorted(candidates, key=get_capacity_score)
    
    async def call_provider(self, provider_id: str, func: Callable, *args, **kwargs) -> Any:
        """Call provider through circuit breaker."""
        if provider_id not in self.circuit_breakers:
            raise ValueError(f"Provider {provider_id} not registered")
        
        circuit_breaker = self.circuit_breakers[provider_id]
        metrics = self.provider_metrics[provider_id]
        
        # Update active request count
        metrics.active_requests += 1
        metrics.last_request_time = datetime.now()
        
        try:
            result = await circuit_breaker.call(func, *args, **kwargs)
            return result
        finally:
            metrics.active_requests = max(0, metrics.active_requests - 1)
    
    async def _on_circuit_breaker_state_change(self, provider_id: str, old_state: CircuitState, new_state: CircuitState):
        """Handle circuit breaker state changes."""
        metrics = self.provider_metrics[provider_id]
        metrics.circuit_breaker_state = new_state.value
        metrics.updated_at = datetime.now()
        
        # Update provider status
        if new_state == CircuitState.OPEN:
            await self._update_provider_status(provider_id, ProviderStatus.UNAVAILABLE)
        elif new_state == CircuitState.CLOSED:
            await self._update_provider_status(provider_id, ProviderStatus.ACTIVE)
        
        self.logger.info(
            f"Circuit breaker state changed for {provider_id}: {old_state.value} -> {new_state.value}",
            extra={
                "provider_id": provider_id,
                "old_state": old_state.value,
                "new_state": new_state.value
            }
        )
        
        # Trigger callback
        if self.on_provider_status_change:
            await self.on_provider_status_change(provider_id, old_state.value, new_state.value)
    
    async def _on_circuit_breaker_failure(self, provider_id: str, failure_event):
        """Handle circuit breaker failures."""
        metrics = self.provider_metrics[provider_id]
        metrics.failed_requests += 1
        metrics.updated_at = datetime.now()
        
        # Trigger callback
        if self.on_provider_failure:
            await self.on_provider_failure(provider_id, failure_event)
    
    async def _on_circuit_breaker_success(self, provider_id: str, request_id: str, response_time: float):
        """Handle circuit breaker successes."""
        metrics = self.provider_metrics[provider_id]
        metrics.successful_requests += 1
        metrics.total_requests += 1
        
        # Update response time (exponential moving average)
        if metrics.average_response_time == 0:
            metrics.average_response_time = response_time
        else:
            metrics.average_response_time = 0.9 * metrics.average_response_time + 0.1 * response_time
        
        # Update success rate
        if metrics.total_requests > 0:
            metrics.success_rate = (metrics.successful_requests / metrics.total_requests) * 100
        
        metrics.updated_at = datetime.now()
        
        # Trigger callback
        if self.on_provider_recovery:
            await self.on_provider_recovery(provider_id, response_time)
    
    async def _update_provider_status(self, provider_id: str, new_status: ProviderStatus):
        """Update provider status."""
        metrics = self.provider_metrics[provider_id]
        old_status = metrics.status
        
        if old_status == new_status:
            return
        
        # Remove from old status group
        self.providers_by_status[old_status].discard(provider_id)
        
        # Add to new status group
        self.providers_by_status[new_status].add(provider_id)
        
        # Update metrics
        metrics.status = new_status
        metrics.updated_at = datetime.now()
        
        self.logger.info(
            f"Provider status changed: {provider_id} {old_status.value} -> {new_status.value}",
            extra={
                "provider_id": provider_id,
                "old_status": old_status.value,
                "new_status": new_status.value
            }
        )
        
        # Publish status change event
        await EventPublisher.publish_system_event(
            event_type="provider.status.changed",
            payload={
                "provider_id": provider_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Update provider metrics from circuit breakers and health monitors
                for provider_id in self.providers:
                    await self._update_provider_metrics(provider_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {str(e)}")
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Reset round robin counters periodically
                self._round_robin_counters.clear()
                
                # Log registry statistics
                await self._log_registry_statistics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {str(e)}")
    
    async def _update_provider_metrics(self, provider_id: str):
        """Update provider metrics from circuit breaker and health monitor."""
        metrics = self.provider_metrics[provider_id]
        
        # Update from circuit breaker
        if provider_id in self.circuit_breakers:
            cb = self.circuit_breakers[provider_id]
            cb_metrics = cb.metrics
            
            metrics.total_requests = cb_metrics.total_requests
            metrics.successful_requests = cb_metrics.successful_requests
            metrics.failed_requests = cb_metrics.failed_requests
            metrics.average_response_time = cb_metrics.average_response_time
            metrics.p95_response_time = cb_metrics.p95_response_time
            metrics.health_score = cb_metrics.health_score
            metrics.total_cost = cb_metrics.total_cost_impact
            metrics.circuit_breaker_state = cb.state.value
            
            if cb_metrics.total_requests > 0:
                metrics.success_rate = (cb_metrics.successful_requests / cb_metrics.total_requests) * 100
        
        # Update from health monitor
        if provider_id in self.health_monitors:
            hm = self.health_monitors[provider_id]
            if hm.recent_checks:
                latest_check = list(hm.recent_checks.values())[-1]
                metrics.last_health_check = latest_check.timestamp
        
        metrics.updated_at = datetime.now()
    
    async def _log_registry_statistics(self):
        """Log registry statistics."""
        total_providers = len(self.providers)
        active_providers = len(self.providers_by_status[ProviderStatus.ACTIVE])
        degraded_providers = len(self.providers_by_status[ProviderStatus.DEGRADED])
        unavailable_providers = len(self.providers_by_status[ProviderStatus.UNAVAILABLE])
        
        # Calculate total requests and success rate
        total_requests = sum(m.total_requests for m in self.provider_metrics.values())
        total_successful = sum(m.successful_requests for m in self.provider_metrics.values())
        overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 100
        
        self.logger.info(
            "Provider registry statistics",
            extra={
                "total_providers": total_providers,
                "active_providers": active_providers,
                "degraded_providers": degraded_providers,
                "unavailable_providers": unavailable_providers,
                "total_requests": total_requests,
                "overall_success_rate": overall_success_rate
            }
        )
    
    def get_provider_status(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive provider status."""
        if provider_id not in self.providers:
            return None
        
        config = self.providers[provider_id]
        metrics = self.provider_metrics[provider_id]
        
        status = {
            "provider_id": provider_id,
            "provider_type": config.provider_type.value,
            "name": config.name,
            "region": config.region,
            "status": metrics.status.value,
            "enabled": config.enabled,
            "maintenance_mode": config.maintenance_mode,
            "metrics": {
                "total_requests": metrics.total_requests,
                "success_rate": metrics.success_rate,
                "average_response_time": metrics.average_response_time,
                "p95_response_time": metrics.p95_response_time,
                "health_score": metrics.health_score,
                "active_requests": metrics.active_requests,
                "total_cost": metrics.total_cost,
                "cost_per_minute": metrics.cost_per_minute,
                "circuit_breaker_state": metrics.circuit_breaker_state,
                "last_request_time": metrics.last_request_time.isoformat() if metrics.last_request_time else None,
                "last_health_check": metrics.last_health_check.isoformat() if metrics.last_health_check else None
            },
            "configuration": {
                "weight": config.weight,
                "max_concurrent_requests": config.max_concurrent_requests,
                "priority": config.priority,
                "cost_per_request": config.cost_per_request,
                "health_check_interval": config.health_check_interval
            }
        }
        
        # Add circuit breaker status
        if provider_id in self.circuit_breakers:
            cb = self.circuit_breakers[provider_id]
            status["circuit_breaker"] = cb.get_status()
        
        # Add health monitor status
        if provider_id in self.health_monitors:
            hm = self.health_monitors[provider_id]
            status["health_monitor"] = hm.get_health_report()
        
        return status
    
    def get_registry_overview(self) -> Dict[str, Any]:
        """Get registry overview."""
        provider_counts = {
            status.value: len(providers)
            for status, providers in self.providers_by_status.items()
        }
        
        type_counts = {
            ptype.value: len(providers)
            for ptype, providers in self.providers_by_type.items()
        }
        
        region_counts = {
            region: len(providers)
            for region, providers in self.providers_by_region.items()
        }
        
        # Calculate aggregate metrics
        total_requests = sum(m.total_requests for m in self.provider_metrics.values())
        total_successful = sum(m.successful_requests for m in self.provider_metrics.values())
        total_cost = sum(m.total_cost for m in self.provider_metrics.values())
        
        avg_response_time = 0.0
        avg_health_score = 0.0
        if self.provider_metrics:
            avg_response_time = sum(m.average_response_time for m in self.provider_metrics.values()) / len(self.provider_metrics)
            avg_health_score = sum(m.health_score for m in self.provider_metrics.values()) / len(self.provider_metrics)
        
        return {
            "total_providers": len(self.providers),
            "status_distribution": provider_counts,
            "type_distribution": type_counts,
            "region_distribution": region_counts,
            "aggregate_metrics": {
                "total_requests": total_requests,
                "overall_success_rate": (total_successful / total_requests * 100) if total_requests > 0 else 100,
                "average_response_time": avg_response_time,
                "average_health_score": avg_health_score,
                "total_cost": total_cost
            },
            "monitoring_status": {
                "is_running": self.is_running,
                "active_health_monitors": len(self.health_monitors),
                "active_circuit_breakers": len(self.circuit_breakers)
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def enable_provider(self, provider_id: str):
        """Enable a provider."""
        if provider_id not in self.providers:
            return
        
        config = self.providers[provider_id]
        config.enabled = True
        
        await self._update_provider_status(provider_id, ProviderStatus.ACTIVE)
        self.logger.info(f"Provider enabled: {provider_id}")
    
    async def disable_provider(self, provider_id: str, reason: str = "Manual disable"):
        """Disable a provider."""
        if provider_id not in self.providers:
            return
        
        config = self.providers[provider_id]
        config.enabled = False
        
        await self._update_provider_status(provider_id, ProviderStatus.DISABLED)
        
        # Force circuit breaker open
        if provider_id in self.circuit_breakers:
            await self.circuit_breakers[provider_id].force_open(reason)
        
        self.logger.info(f"Provider disabled: {provider_id}, reason: {reason}")
    
    async def set_maintenance_mode(self, provider_id: str, maintenance: bool, reason: str = ""):
        """Set provider maintenance mode."""
        if provider_id not in self.providers:
            return
        
        config = self.providers[provider_id]
        config.maintenance_mode = maintenance
        
        if maintenance:
            await self._update_provider_status(provider_id, ProviderStatus.MAINTENANCE)
        else:
            await self._update_provider_status(provider_id, ProviderStatus.ACTIVE)
        
        self.logger.info(
            f"Provider maintenance mode {'enabled' if maintenance else 'disabled'}: {provider_id}",
            extra={"reason": reason}
        )