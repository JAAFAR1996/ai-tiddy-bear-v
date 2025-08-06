"""
Tests for Latency Optimizer
===========================

Tests for optimizing streaming latency.
"""

import pytest
import time
from unittest.mock import patch

from src.application.services.streaming.latency_optimizer import LatencyOptimizer


class TestLatencyOptimizer:
    """Test latency optimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create latency optimizer instance."""
        return LatencyOptimizer(target_latency_ms=100)

    def test_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.target_latency_ms == 100

    def test_custom_target_latency(self):
        """Test custom target latency."""
        optimizer = LatencyOptimizer(target_latency_ms=50)
        assert optimizer.target_latency_ms == 50

    @patch('time.sleep')
    def test_optimize_with_sleep_needed(self, mock_sleep, optimizer):
        """Test optimization when sleep is needed."""
        # Simulate fast processing (10ms elapsed)
        start_time = time.time() - 0.01
        
        sleep_time = optimizer.optimize(start_time)
        
        # Should sleep for remaining time
        assert sleep_time > 0
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] > 0

    @patch('time.sleep')
    def test_optimize_no_sleep_needed(self, mock_sleep, optimizer):
        """Test optimization when no sleep is needed."""
        # Simulate slow processing (200ms elapsed)
        start_time = time.time() - 0.2
        
        sleep_time = optimizer.optimize(start_time)
        
        # Should not sleep
        assert sleep_time == 0
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    def test_optimize_exact_target(self, mock_sleep, optimizer):
        """Test optimization when exactly at target."""
        # Simulate processing exactly at target (100ms elapsed)
        start_time = time.time() - 0.1
        
        sleep_time = optimizer.optimize(start_time)
        
        # Should not sleep (or minimal sleep due to timing precision)
        assert sleep_time >= 0
        if sleep_time > 0:
            mock_sleep.assert_called_once()
        else:
            mock_sleep.assert_not_called()

    def test_optimize_calculation_accuracy(self, optimizer):
        """Test optimization calculation accuracy."""
        # Test with known timing
        start_time = time.time() - 0.05  # 50ms elapsed
        
        with patch('time.sleep') as mock_sleep:
            sleep_time = optimizer.optimize(start_time)
            
            # Should sleep for approximately 50ms (100 - 50)
            expected_sleep = 0.05  # 50ms in seconds
            assert abs(sleep_time - expected_sleep) < 0.01  # Allow 10ms tolerance

    def test_multiple_optimizations(self, optimizer):
        """Test multiple optimization calls."""
        results = []
        
        with patch('time.sleep'):
            for i in range(5):
                start_time = time.time() - (0.02 * i)  # Varying elapsed times
                sleep_time = optimizer.optimize(start_time)
                results.append(sleep_time)
        
        # Results should vary based on elapsed time
        assert len(set(results)) > 1  # Should have different values

    def test_zero_target_latency(self):
        """Test with zero target latency."""
        optimizer = LatencyOptimizer(target_latency_ms=0)
        start_time = time.time() - 0.01
        
        with patch('time.sleep') as mock_sleep:
            sleep_time = optimizer.optimize(start_time)
            
            assert sleep_time == 0
            mock_sleep.assert_not_called()

    def test_very_high_target_latency(self):
        """Test with very high target latency."""
        optimizer = LatencyOptimizer(target_latency_ms=10000)  # 10 seconds
        start_time = time.time() - 0.001  # 1ms elapsed
        
        with patch('time.sleep') as mock_sleep:
            sleep_time = optimizer.optimize(start_time)
            
            # Should sleep for almost the full target time
            assert sleep_time > 9.0  # Should be close to 9.999 seconds
            mock_sleep.assert_called_once()

    def test_negative_elapsed_time_handling(self, optimizer):
        """Test handling of future start time (edge case)."""
        # Start time in the future (should not happen in practice)
        start_time = time.time() + 0.1
        
        with patch('time.sleep') as mock_sleep:
            sleep_time = optimizer.optimize(start_time)
            
            # Should handle gracefully and sleep for full target time
            assert sleep_time >= 0
            mock_sleep.assert_called_once()