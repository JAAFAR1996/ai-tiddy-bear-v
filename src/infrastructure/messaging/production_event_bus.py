"""
Production Event Bus - Legacy Compatibility Module
=================================================
Provides backward compatibility by importing from the advanced event bus.
"""

from .production_event_bus_advanced import *

# Legacy alias for backward compatibility
production_event_bus = ProductionEventBus