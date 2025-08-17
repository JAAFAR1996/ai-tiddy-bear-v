"""
Enhanced Latency Optimizer for Real-Time Audio Processing
========================================================
Comprehensive latency optimization for <2s response time targets in AI audio pipelines.
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from collections import deque
from dataclasses import dataclass
from enum import Enum


class LatencyMode(Enum):
    """Latency optimization modes."""
    LOW_LATENCY = "low_latency"      # Target <1s
    BALANCED = "balanced"            # Target <2s  
    HIGH_QUALITY = "high_quality"    # Target <3s


@dataclass
class LatencyMetrics:
    """Latency metrics for pipeline components."""
    whisper_stt_ms: float = 0.0
    ai_processing_ms: float = 0.0
    tts_generation_ms: float = 0.0
    total_pipeline_ms: float = 0.0
    esp32_buffer_ms: float = 0.0
    network_transmission_ms: float = 0.0
    cache_hit_ratio: float = 0.0


@dataclass
class OptimizationConfig:
    """Configuration for latency optimizations."""
    whisper_model_size: str = "turbo"
    enable_adaptive_model: bool = True
    tts_streaming: bool = True
    esp32_buffer_size: int = 8192
    target_response_time_ms: int = 2000
    cache_aggressive: bool = True


class ComponentProfiler:
    """Profiles individual pipeline components for latency optimization."""
    
    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.component_times = {
            "whisper_stt": deque(maxlen=max_samples),
            "ai_processing": deque(maxlen=max_samples),
            "tts_generation": deque(maxlen=max_samples),
            "esp32_buffer": deque(maxlen=max_samples),
            "network": deque(maxlen=max_samples),
        }
        self.logger = logging.getLogger(__name__)
    
    def record_component_time(self, component: str, duration_ms: float) -> None:
        """Record timing for a pipeline component."""
        if component in self.component_times:
            self.component_times[component].append(duration_ms)
            
    def get_component_stats(self, component: str) -> Dict[str, float]:
        """Get statistics for a component."""
        times = list(self.component_times.get(component, []))
        if not times:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
            
        times.sort()
        return {
            "avg": sum(times) / len(times),
            "p50": times[len(times) // 2],
            "p95": times[int(0.95 * len(times))],
            "p99": times[int(0.99 * len(times))],
        }
    
    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks in the pipeline."""
        bottlenecks = []
        
        for component, times in self.component_times.items():
            if not times:
                continue
                
            stats = self.get_component_stats(component)
            avg_time = stats["avg"]
            p95_time = stats["p95"]
            
            # Define bottleneck thresholds per component
            thresholds = {
                "whisper_stt": {"avg": 800, "p95": 1200},
                "ai_processing": {"avg": 400, "p95": 800},
                "tts_generation": {"avg": 1000, "p95": 1500},
                "esp32_buffer": {"avg": 100, "p95": 200},
                "network": {"avg": 100, "p95": 200},
            }
            
            threshold = thresholds.get(component, {"avg": 500, "p95": 1000})
            
            if avg_time > threshold["avg"] or p95_time > threshold["p95"]:
                severity = "critical" if p95_time > threshold["p95"] * 1.5 else "warning"
                bottlenecks.append({
                    "component": component,
                    "severity": severity,
                    "avg_time_ms": avg_time,
                    "p95_time_ms": p95_time,
                    "threshold_avg": threshold["avg"],
                    "threshold_p95": threshold["p95"],
                    "recommendation": self._get_optimization_recommendation(component, avg_time)
                })
        
        return sorted(bottlenecks, key=lambda x: x["p95_time_ms"], reverse=True)
    
    def _get_optimization_recommendation(self, component: str, avg_time_ms: float) -> str:
        """Get optimization recommendation for a component."""
        recommendations = {
            "whisper_stt": [
                "Switch to smaller Whisper model (tiny/base)",
                "Enable GPU acceleration", 
                "Implement audio chunking",
                "Use VAD to reduce processing"
            ],
            "ai_processing": [
                "Optimize prompts for shorter responses",
                "Use faster AI model",
                "Implement response caching",
                "Enable streaming responses"
            ],
            "tts_generation": [
                "Enable sentence-level streaming",
                "Use lower quality/faster models",
                "Implement aggressive caching",
                "Pre-generate common responses"
            ],
            "esp32_buffer": [
                "Optimize buffer size",
                "Implement adaptive buffering",
                "Use compression",
                "Reduce audio quality"
            ],
            "network": [
                "Optimize network connection",
                "Use compression", 
                "Implement connection pooling",
                "Consider edge deployment"
            ]
        }
        
        return recommendations.get(component, ["General optimization needed"])[0]


class LatencyOptimizer:
    """Enhanced latency optimizer for real-time audio processing."""
    
    def __init__(
        self, 
        target_latency_ms: int = 2000,
        mode: LatencyMode = LatencyMode.BALANCED,
        adaptive: bool = True
    ):
        self.target_latency_ms = target_latency_ms
        self.mode = mode
        self.adaptive = adaptive
        self.profiler = ComponentProfiler()
        self.logger = logging.getLogger(__name__)
        
        # Optimization state
        self._current_config = OptimizationConfig()
        self._recent_latencies = deque(maxlen=50)
        self._optimization_callbacks: Dict[str, Callable] = {}
        
        # Performance targets by mode
        self.mode_targets = {
            LatencyMode.LOW_LATENCY: 1000,   # 1s target
            LatencyMode.BALANCED: 2000,      # 2s target  
            LatencyMode.HIGH_QUALITY: 3000   # 3s target
        }
        
        self.target_latency_ms = self.mode_targets[mode]
        
    def register_optimization_callback(self, component: str, callback: Callable) -> None:
        """Register callback for component optimization."""
        self._optimization_callbacks[component] = callback
        
    def record_pipeline_latency(self, metrics: LatencyMetrics) -> None:
        """Record complete pipeline latency metrics."""
        total_latency = metrics.total_pipeline_ms
        self._recent_latencies.append(total_latency)
        
        # Record individual component times
        self.profiler.record_component_time("whisper_stt", metrics.whisper_stt_ms)
        self.profiler.record_component_time("ai_processing", metrics.ai_processing_ms)
        self.profiler.record_component_time("tts_generation", metrics.tts_generation_ms)
        self.profiler.record_component_time("esp32_buffer", metrics.esp32_buffer_ms)
        self.profiler.record_component_time("network", metrics.network_transmission_ms)
        
        # Trigger adaptive optimizations if needed
        if self.adaptive and len(self._recent_latencies) >= 10:
            asyncio.create_task(self._check_and_optimize())
    
    async def _check_and_optimize(self) -> None:
        """Check performance and trigger optimizations if needed."""
        recent_avg = sum(self._recent_latencies) / len(self._recent_latencies)
        
        if recent_avg > self.target_latency_ms * 1.2:  # 20% over target
            self.logger.warning(
                f"Performance degraded: {recent_avg:.0f}ms > {self.target_latency_ms}ms target"
            )
            await self._apply_optimizations()
    
    async def _apply_optimizations(self) -> None:
        """Apply automatic optimizations based on bottleneck analysis."""
        bottlenecks = self.profiler.identify_bottlenecks()
        
        for bottleneck in bottlenecks[:3]:  # Focus on top 3 bottlenecks
            component = bottleneck["component"]
            severity = bottleneck["severity"]
            
            self.logger.info(
                f"Optimizing {component} ({severity}): {bottleneck['avg_time_ms']:.0f}ms avg"
            )
            
            # Apply component-specific optimizations
            if component == "whisper_stt" and severity == "critical":
                await self._optimize_whisper()
            elif component == "tts_generation" and severity in ["critical", "warning"]:
                await self._optimize_tts()
            elif component == "esp32_buffer":
                await self._optimize_esp32_buffer()
                
            # Call registered optimization callbacks
            if component in self._optimization_callbacks:
                try:
                    await self._optimization_callbacks[component](bottleneck)
                except Exception as e:
                    self.logger.error(f"Optimization callback failed for {component}: {e}")
    
    async def _optimize_whisper(self) -> None:
        """Optimize Whisper STT performance."""
        if self._current_config.whisper_model_size == "turbo":
            self._current_config.whisper_model_size = "base"
            self.logger.info("Downgraded Whisper model from turbo to base for performance")
        elif self._current_config.whisper_model_size == "base":
            self._current_config.whisper_model_size = "tiny"
            self.logger.info("Downgraded Whisper model from base to tiny for performance")
            
        self._current_config.enable_adaptive_model = True
    
    async def _optimize_tts(self) -> None:
        """Optimize TTS performance."""
        if not self._current_config.tts_streaming:
            self._current_config.tts_streaming = True
            self.logger.info("Enabled TTS sentence-level streaming")
            
        self._current_config.cache_aggressive = True
        
    async def _optimize_esp32_buffer(self) -> None:
        """Optimize ESP32 buffer settings."""
        if self._current_config.esp32_buffer_size > 2048:
            self._current_config.esp32_buffer_size = max(2048, self._current_config.esp32_buffer_size // 2)
            self.logger.info(f"Reduced ESP32 buffer size to {self._current_config.esp32_buffer_size}")
    
    def get_current_performance(self) -> Dict[str, Any]:
        """Get current performance summary."""
        if not self._recent_latencies:
            return {"status": "no_data"}
            
        recent_avg = sum(self._recent_latencies) / len(self._recent_latencies)
        recent_p95 = sorted(self._recent_latencies)[int(0.95 * len(self._recent_latencies))]
        
        # Component stats
        component_stats = {}
        for component in self.profiler.component_times:
            component_stats[component] = self.profiler.get_component_stats(component)
            
        # Performance assessment
        status = "healthy"
        if recent_avg > self.target_latency_ms * 1.5:
            status = "critical"
        elif recent_avg > self.target_latency_ms * 1.2:
            status = "degraded"
        elif recent_avg > self.target_latency_ms:
            status = "warning"
            
        return {
            "status": status,
            "target_latency_ms": self.target_latency_ms,
            "current_avg_latency_ms": recent_avg,
            "current_p95_latency_ms": recent_p95,
            "mode": self.mode.value,
            "component_stats": component_stats,
            "bottlenecks": self.profiler.identify_bottlenecks(),
            "current_config": self._current_config.__dict__,
            "sample_count": len(self._recent_latencies)
        }
    
    def optimize(self, start_time: float) -> float:
        """Legacy method for backward compatibility."""
        elapsed = (time.time() - start_time) * 1000
        sleep_time = max(0, self.target_latency_ms - elapsed) / 1000
        if sleep_time > 0:
            time.sleep(sleep_time)
        return sleep_time
    
    async def optimize_async(self, component_times: Dict[str, float]) -> Dict[str, Any]:
        """Async optimization with detailed component analysis."""
        total_time = sum(component_times.values())
        
        # Create metrics object
        metrics = LatencyMetrics(
            whisper_stt_ms=component_times.get("whisper_stt", 0),
            ai_processing_ms=component_times.get("ai_processing", 0),
            tts_generation_ms=component_times.get("tts_generation", 0),
            esp32_buffer_ms=component_times.get("esp32_buffer", 0),
            network_transmission_ms=component_times.get("network", 0),
            total_pipeline_ms=total_time
        )
        
        # Record metrics
        self.record_pipeline_latency(metrics)
        
        # Return optimization recommendations
        recommendations = []
        if total_time > self.target_latency_ms:
            bottlenecks = self.profiler.identify_bottlenecks()
            recommendations = [b["recommendation"] for b in bottlenecks[:3]]
            
        return {
            "total_latency_ms": total_time,
            "target_latency_ms": self.target_latency_ms,
            "performance_ratio": total_time / self.target_latency_ms,
            "needs_optimization": total_time > self.target_latency_ms,
            "recommendations": recommendations,
            "bottlenecks": self.profiler.identify_bottlenecks()[:3]
        }
