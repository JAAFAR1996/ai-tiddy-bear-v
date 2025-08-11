"""
Smart Alert Management System - AI Teddy Bear
===========================================
Advanced alert processing to minimize false positives while maintaining
rapid response for genuine incidents.

Features:
- Context-aware alert filtering
- Machine learning-based anomaly detection
- Deployment-aware alert suppression
- Escalation path management
- Alert correlation and grouping

Author: Senior Engineering Team
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels with numeric values for comparison."""
    CRITICAL = 1  # P0 - Child safety, COPPA violations
    HIGH = 2      # P1 - System reliability issues  
    MEDIUM = 3    # P2 - Performance degradation
    LOW = 4       # P3 - Business metrics


class AlertState(Enum):
    """Alert lifecycle states."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class AlertContext:
    """Contextual information for intelligent alert processing."""
    deployment_in_progress: bool = False
    maintenance_window: bool = False
    load_test_active: bool = False
    weekend_mode: bool = False
    peak_hours: bool = False
    child_sleep_hours: bool = False  # Reduced activity expected
    school_hours: bool = False
    
    # Historical patterns
    typical_error_rate: float = 0.001
    typical_response_time: float = 0.5
    typical_concurrent_users: int = 1000


@dataclass  
class Alert:
    """Enhanced alert object with context and intelligence."""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime
    source_service: str
    
    # Context
    context: Optional[AlertContext] = None
    
    # Lifecycle
    state: AlertState = AlertState.NEW
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    
    # Correlation
    correlated_alerts: List[str] = None
    root_cause_candidate: bool = False
    
    # ML features
    anomaly_score: float = 0.0
    confidence: float = 1.0
    
    def __post_init__(self):
        if self.correlated_alerts is None:
            self.correlated_alerts = []


class SmartAlertManager:
    """
    Production-grade alert management system with ML-based filtering.
    
    Key Features:
    1. Context-aware alert processing
    2. False positive reduction through historical analysis
    3. Intelligent alert correlation and grouping
    4. Deployment-aware suppression
    5. Child safety prioritization
    """
    
    def __init__(
        self,
        config: Optional[Dict] = None,
        enable_ml_filtering: bool = True
    ):
        self.config = config or self._default_config()
        self.enable_ml_filtering = enable_ml_filtering
        
        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.resolved_alerts: deque = deque(maxlen=10000)
        self.alert_history: defaultdict = defaultdict(list)
        
        # Context tracking
        self.current_context = AlertContext()
        
        # ML components
        if enable_ml_filtering:
            self.anomaly_detector = IsolationForest(
                contamination=0.1,  # 10% of data points are anomalies
                random_state=42
            )
            self.scaler = StandardScaler()
            self.ml_trained = False
            self.training_data = []
            
        # Alert correlation
        self.correlation_rules = self._load_correlation_rules()
        
        # Metrics
        self.metrics = {
            'total_alerts': 0,
            'false_positives_avoided': 0,
            'suppressed_during_deployment': 0,
            'child_safety_alerts': 0,
            'escalated_alerts': 0
        }

    def _default_config(self) -> Dict:
        """Default configuration for smart alert management."""
        return {
            # False positive reduction
            'min_duration_for_alert': {
                AlertSeverity.CRITICAL: 0,      # Immediate for child safety
                AlertSeverity.HIGH: 30,         # 30 seconds
                AlertSeverity.MEDIUM: 120,      # 2 minutes  
                AlertSeverity.LOW: 300          # 5 minutes
            },
            
            # Context-based threshold adjustments
            'context_multipliers': {
                'deployment_in_progress': {
                    'error_rate': 3.0,          # 3x higher error rate allowed
                    'response_time': 2.0        # 2x higher response time allowed
                },
                'load_test_active': {
                    'error_rate': 5.0,
                    'response_time': 3.0,
                    'resource_usage': 2.0
                },
                'maintenance_window': {
                    'availability': 0.5,        # 50% availability acceptable
                    'error_rate': 10.0
                },
                'peak_hours': {
                    'response_time': 1.5,       # 50% higher response time allowed
                    'resource_usage': 1.3
                },
                'child_sleep_hours': {
                    'low_engagement': 0.1       # Very low engagement is normal
                }
            },
            
            # Escalation timing
            'escalation_intervals': {
                AlertSeverity.CRITICAL: 0,      # Immediate escalation
                AlertSeverity.HIGH: 300,        # 5 minutes
                AlertSeverity.MEDIUM: 1800,     # 30 minutes
                AlertSeverity.LOW: 7200         # 2 hours
            },
            
            # Correlation settings
            'correlation_time_window': 300,     # 5 minutes
            'max_correlated_alerts': 20
        }

    async def process_alert(
        self,
        alert_data: Dict
    ) -> Tuple[bool, Optional[Alert], str]:
        """
        Process incoming alert with intelligent filtering.
        
        Returns:
            (should_fire, processed_alert, reason)
        """
        try:
            # Create alert object
            alert = self._create_alert_from_data(alert_data)
            
            # Update metrics
            self.metrics['total_alerts'] += 1
            
            # Special handling for child safety alerts
            if self._is_child_safety_alert(alert):
                self.metrics['child_safety_alerts'] += 1
                return await self._handle_child_safety_alert(alert)
            
            # Context-aware filtering
            if not await self._should_fire_with_context(alert):
                self.metrics['false_positives_avoided'] += 1
                return False, None, "Suppressed by context analysis"
            
            # ML-based anomaly detection
            if self.enable_ml_filtering and self.ml_trained:
                if not await self._ml_anomaly_check(alert):
                    self.metrics['false_positives_avoided'] += 1
                    return False, None, "Suppressed by ML anomaly detection"
            
            # Duration-based filtering
            if not await self._duration_check(alert):
                return False, None, "Waiting for minimum duration threshold"
            
            # Alert correlation
            await self._correlate_alert(alert)
            
            # Store active alert
            self.active_alerts[alert.id] = alert
            
            # Schedule escalation if needed
            if alert.severity in [AlertSeverity.HIGH, AlertSeverity.MEDIUM]:
                asyncio.create_task(self._schedule_escalation(alert))
            
            return True, alert, "Alert passed all filters"
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}", exc_info=True)
            return False, None, f"Processing error: {e}"

    def _is_child_safety_alert(self, alert: Alert) -> bool:
        """Check if alert is related to child safety."""
        safety_keywords = [
            'child_safety',
            'coppa',
            'predatory',
            'inappropriate_content',
            'parental_consent',
            'data_retention'
        ]
        
        alert_text = f"{alert.name} {alert.message}".lower()
        return any(keyword in alert_text for keyword in safety_keywords)

    async def _handle_child_safety_alert(self, alert: Alert) -> Tuple[bool, Alert, str]:
        """Special handling for child safety alerts - always fire immediately."""
        alert.severity = AlertSeverity.CRITICAL
        alert.state = AlertState.ESCALATED  # Skip normal escalation
        
        # Immediate escalation
        await self._escalate_alert(alert)
        
        # Store in active alerts
        self.active_alerts[alert.id] = alert
        
        logger.critical(f"CHILD SAFETY ALERT: {alert.name} - {alert.message}")
        
        return True, alert, "Child safety alert - immediate escalation"

    async def _should_fire_with_context(self, alert: Alert) -> bool:
        """Context-aware alert filtering."""
        # Get current context
        context = await self._get_current_context()
        alert.context = context
        
        # Check deployment suppression
        if context.deployment_in_progress:
            if self._should_suppress_during_deployment(alert):
                self.metrics['suppressed_during_deployment'] += 1
                return False
        
        # Check maintenance window
        if context.maintenance_window:
            if alert.severity not in [AlertSeverity.CRITICAL]:
                return False
        
        # Adjust thresholds based on context
        adjusted_threshold = self._get_context_adjusted_threshold(alert, context)
        if alert.metric_value < adjusted_threshold:
            return False
            
        return True

    def _should_suppress_during_deployment(self, alert: Alert) -> bool:
        """Determine if alert should be suppressed during deployment."""
        # Never suppress child safety alerts
        if self._is_child_safety_alert(alert):
            return False
            
        # Suppress performance-related alerts during deployment
        performance_alerts = [
            'high_error_rate',
            'slow_response_time', 
            'high_memory_usage',
            'database_connection_pool'
        ]
        
        return any(perf_alert in alert.name.lower() for perf_alert in performance_alerts)

    def _get_context_adjusted_threshold(
        self, 
        alert: Alert, 
        context: AlertContext
    ) -> float:
        """Adjust alert threshold based on current context."""
        base_threshold = alert.threshold
        multiplier = 1.0
        
        # Get metric type from alert name
        if 'error_rate' in alert.name.lower():
            metric_type = 'error_rate'
        elif 'response_time' in alert.name.lower():
            metric_type = 'response_time'
        elif 'memory' in alert.name.lower():
            metric_type = 'resource_usage'
        elif 'engagement' in alert.name.lower():
            metric_type = 'low_engagement'
        else:
            metric_type = 'default'
            
        # Apply context-based multipliers
        context_multipliers = self.config['context_multipliers']
        
        if context.deployment_in_progress and metric_type in context_multipliers['deployment_in_progress']:
            multiplier *= context_multipliers['deployment_in_progress'][metric_type]
            
        if context.load_test_active and metric_type in context_multipliers['load_test_active']:
            multiplier *= context_multipliers['load_test_active'][metric_type]
            
        if context.peak_hours and metric_type in context_multipliers['peak_hours']:
            multiplier *= context_multipliers['peak_hours'][metric_type]
            
        if context.child_sleep_hours and metric_type in context_multipliers['child_sleep_hours']:
            multiplier *= context_multipliers['child_sleep_hours'][metric_type]
            
        return base_threshold * multiplier

    async def _ml_anomaly_check(self, alert: Alert) -> bool:
        """Use ML to determine if alert represents a genuine anomaly."""
        if not self.ml_trained or len(self.training_data) < 100:
            return True  # Default to firing if ML not ready
            
        try:
            # Extract features for ML analysis
            features = self._extract_alert_features(alert)
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Get anomaly score
            anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
            alert.anomaly_score = anomaly_score
            
            # Determine if this is a genuine anomaly
            # More negative scores indicate anomalies
            is_anomaly = anomaly_score < -0.1
            
            # Calculate confidence based on how far from decision boundary
            alert.confidence = min(1.0, abs(anomaly_score))
            
            return is_anomaly
            
        except Exception as e:
            logger.warning(f"ML anomaly detection failed: {e}")
            return True  # Fail open - better false positive than missed alert

    def _extract_alert_features(self, alert: Alert) -> List[float]:
        """Extract numerical features from alert for ML analysis."""
        features = [
            alert.metric_value,
            alert.threshold,
            alert.metric_value / alert.threshold if alert.threshold > 0 else 0,
            
            # Time-based features  
            alert.timestamp.hour,
            alert.timestamp.weekday(),
            
            # Context features
            1.0 if alert.context and alert.context.deployment_in_progress else 0.0,
            1.0 if alert.context and alert.context.maintenance_window else 0.0,
            1.0 if alert.context and alert.context.peak_hours else 0.0,
            
            # Historical features (recent alert frequency)
            len([a for a in self.alert_history[alert.name] 
                 if (alert.timestamp - a['timestamp']).total_seconds() < 3600])
        ]
        
        return features

    async def _duration_check(self, alert: Alert) -> bool:
        """Check if alert has been active long enough to fire."""
        min_duration = self.config['min_duration_for_alert'][alert.severity]
        
        # Critical alerts (child safety) fire immediately
        if alert.severity == AlertSeverity.CRITICAL:
            return True
            
        # Check if we've seen this alert before recently
        recent_alerts = [
            a for a in self.alert_history[alert.name]
            if (alert.timestamp - a['timestamp']).total_seconds() < min_duration
        ]
        
        if len(recent_alerts) == 0:
            # First occurrence, wait for minimum duration
            asyncio.create_task(self._delayed_firing(alert, min_duration))
            return False
        
        # Alert has been active long enough
        return True

    async def _delayed_firing(self, alert: Alert, delay_seconds: int):
        """Fire alert after specified delay if condition persists."""
        await asyncio.sleep(delay_seconds)
        
        # Re-check if alert condition still exists
        # This would normally query the monitoring system
        # For now, assume condition persists
        if alert.id not in self.active_alerts:
            logger.info(f"Delayed firing alert {alert.id}: {alert.name}")
            self.active_alerts[alert.id] = alert

    async def _correlate_alert(self, alert: Alert):
        """Find and correlate related alerts."""
        time_window = timedelta(seconds=self.config['correlation_time_window'])
        recent_alerts = [
            a for a in self.active_alerts.values()
            if (alert.timestamp - a.timestamp) < time_window
        ]
        
        for rule in self.correlation_rules:
            matches = []
            for pattern in rule['patterns']:
                matching_alerts = [
                    a for a in recent_alerts
                    if pattern in a.name.lower()
                ]
                matches.extend(matching_alerts)
            
            if len(matches) >= rule['min_matches']:
                # Found correlation
                root_cause = self._identify_root_cause(matches)
                for matched_alert in matches:
                    if matched_alert.id != root_cause.id:
                        matched_alert.correlated_alerts.append(root_cause.id)
                    else:
                        matched_alert.root_cause_candidate = True

    def _identify_root_cause(self, correlated_alerts: List[Alert]) -> Alert:
        """Identify most likely root cause from correlated alerts."""
        # Simple heuristic: earliest alert with highest severity
        return min(
            correlated_alerts,
            key=lambda a: (a.timestamp, a.severity.value)
        )

    async def _schedule_escalation(self, alert: Alert):
        """Schedule alert escalation based on severity."""
        escalation_delay = self.config['escalation_intervals'][alert.severity]
        
        if escalation_delay > 0:
            await asyncio.sleep(escalation_delay)
            
            # Check if alert is still active and not acknowledged
            if (alert.id in self.active_alerts and 
                alert.state not in [AlertState.ACKNOWLEDGED, AlertState.RESOLVED]):
                await self._escalate_alert(alert)

    async def _escalate_alert(self, alert: Alert):
        """Escalate alert to next level."""
        alert.state = AlertState.ESCALATED
        self.metrics['escalated_alerts'] += 1
        
        # Implementation would send to escalation channels
        logger.warning(f"ESCALATING ALERT: {alert.name} - {alert.message}")

    async def _get_current_context(self) -> AlertContext:
        """Get current operational context."""
        now = datetime.now()
        
        context = AlertContext()
        
        # Time-based context
        context.weekend_mode = now.weekday() >= 5  # Saturday/Sunday
        context.peak_hours = 19 <= now.hour <= 21  # 7-9 PM peak usage
        context.child_sleep_hours = now.hour <= 6 or now.hour >= 22
        context.school_hours = 8 <= now.hour <= 15 and not context.weekend_mode
        
        # This would normally query deployment/maintenance systems
        # context.deployment_in_progress = await self._check_deployment_status()
        # context.maintenance_window = await self._check_maintenance_window()
        # context.load_test_active = await self._check_load_test_status()
        
        return context

    def _load_correlation_rules(self) -> List[Dict]:
        """Load alert correlation rules."""
        return [
            {
                'name': 'database_cascade',
                'patterns': ['database_connection', 'slow_query', 'high_cpu'],
                'min_matches': 2,
                'root_cause_priority': ['database_connection', 'slow_query']
            },
            {
                'name': 'ai_provider_cascade', 
                'patterns': ['openai', 'elevenlabs', 'circuit_breaker'],
                'min_matches': 2,
                'root_cause_priority': ['circuit_breaker']
            },
            {
                'name': 'memory_pressure',
                'patterns': ['high_memory', 'gc_pressure', 'slow_response'],
                'min_matches': 2,
                'root_cause_priority': ['high_memory']
            }
        ]

    def _create_alert_from_data(self, alert_data: Dict) -> Alert:
        """Create Alert object from incoming data."""
        return Alert(
            id=alert_data.get('id', f"alert_{int(time.time() * 1000)}"),
            name=alert_data['alertname'],
            severity=AlertSeverity[alert_data.get('severity', 'MEDIUM').upper()],
            message=alert_data.get('description', ''),
            metric_value=float(alert_data.get('value', 0)),
            threshold=float(alert_data.get('threshold', 1)),
            timestamp=datetime.now(),
            source_service=alert_data.get('service', 'unknown')
        )

    async def train_ml_model(self, historical_alerts: List[Dict]):
        """Train ML model on historical alert data."""
        if not self.enable_ml_filtering:
            return
            
        try:
            # Prepare training data
            training_features = []
            for alert_data in historical_alerts:
                alert = self._create_alert_from_data(alert_data)
                features = self._extract_alert_features(alert)
                training_features.append(features)
                
            if len(training_features) < 100:
                logger.warning("Insufficient training data for ML model")
                return
                
            # Scale features
            self.scaler.fit(training_features)
            features_scaled = self.scaler.transform(training_features)
            
            # Train anomaly detector
            self.anomaly_detector.fit(features_scaled)
            
            self.ml_trained = True
            self.training_data = training_features
            
            logger.info(f"ML model trained on {len(training_features)} historical alerts")
            
        except Exception as e:
            logger.error(f"Failed to train ML model: {e}", exc_info=True)

    def get_metrics(self) -> Dict:
        """Get alert management metrics."""
        total_active = len(self.active_alerts)
        by_severity = defaultdict(int)
        
        for alert in self.active_alerts.values():
            by_severity[alert.severity.name] += 1
            
        return {
            **self.metrics,
            'active_alerts': total_active,
            'active_by_severity': dict(by_severity),
            'ml_model_trained': self.ml_trained,
            'false_positive_reduction_rate': (
                self.metrics['false_positives_avoided'] / 
                max(1, self.metrics['total_alerts']) * 100
            )
        }

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.state = AlertState.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now()
            
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")

    async def resolve_alert(self, alert_id: str):
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert.state = AlertState.RESOLVED
            
            # Store in resolved alerts
            self.resolved_alerts.append({
                'alert': asdict(alert),
                'resolved_at': datetime.now()
            })
            
            # Add to historical data for ML training
            self.alert_history[alert.name].append({
                'timestamp': alert.timestamp,
                'value': alert.metric_value,
                'resolved': True
            })
            
            logger.info(f"Alert {alert_id} resolved")


# Factory function for production use
async def create_smart_alert_manager(
    config_path: Optional[str] = None,
    enable_ml: bool = True
) -> SmartAlertManager:
    """Create and initialize smart alert manager."""
    config = None
    if config_path:
        with open(config_path, 'r') as f:
            config = json.load(f)
    
    manager = SmartAlertManager(config=config, enable_ml_filtering=enable_ml)
    
    # Train ML model if historical data available
    if enable_ml:
        # This would load from your monitoring database
        # historical_data = await load_historical_alerts()
        # await manager.train_ml_model(historical_data)
        pass
    
    return manager


# Example usage for production deployment
if __name__ == "__main__":
    async def main():
        # Create alert manager
        manager = await create_smart_alert_manager(enable_ml=True)
        
        # Example alert processing
        sample_alert = {
            'alertname': 'HighErrorRate',
            'severity': 'HIGH',
            'description': 'Error rate is 5% for the last 5 minutes',
            'value': 0.05,
            'threshold': 0.02,
            'service': 'api-gateway'
        }
        
        should_fire, processed_alert, reason = await manager.process_alert(sample_alert)
        
        print(f"Alert decision: {should_fire}")
        print(f"Reason: {reason}")
        if processed_alert:
            print(f"Alert details: {processed_alert.name} - {processed_alert.message}")
            
        # Get metrics
        metrics = manager.get_metrics()
        print(f"Manager metrics: {json.dumps(metrics, indent=2)}")
    
    asyncio.run(main())