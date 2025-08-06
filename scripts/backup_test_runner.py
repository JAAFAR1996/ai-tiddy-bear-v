#!/usr/bin/env python3
"""
Backup Test Runner for AI Teddy Bear Application

Automated testing framework runner for backup and restore operations
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.backup.testing_framework import (
    BackupTestingFramework, TestExecution, TestStatus
)
from src.infrastructure.backup.orchestrator import BackupOrchestrator
from src.infrastructure.backup.database_backup import DatabaseBackupService
from src.infrastructure.backup.file_backup import FileBackupService, StorageProvider
from src.infrastructure.backup.config_backup import ConfigBackupService
from src.infrastructure.backup.restore_service import RestoreService
from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetricsCollector


class BackupTestRunner:
    """
    Test runner service for backup and restore operations
    """

    def __init__(self):
        self.logger = self._setup_logging()
        self.testing_framework = self._initialize_testing_framework()
        self.test_results_path = os.getenv('TEST_RESULTS_PATH', '/app/test_results')
        
        # Ensure test results directory exists
        os.makedirs(self.test_results_path, exist_ok=True)

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _initialize_testing_framework(self) -> BackupTestingFramework:
        """Initialize the backup testing framework"""
        # Initialize services (similar to scheduler)
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        database_service = DatabaseBackupService(
            database_url=database_url,
            backup_base_path='/app/test_data/database',
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        # File service with storage backends
        storage_backends = {}
        
        from src.infrastructure.backup.file_backup import LocalBackend
        storage_backends[StorageProvider.LOCAL] = LocalBackend('/app/test_data/files')
        
        file_service = FileBackupService(
            backup_base_path='/app/test_data/files',
            storage_backends=storage_backends,
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        config_service = ConfigBackupService(
            backup_base_path='/app/test_data/config',
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        backup_orchestrator = BackupOrchestrator(
            database_service=database_service,
            file_service=file_service,
            config_service=config_service
        )
        
        restore_service = RestoreService(
            database_service=database_service,
            file_service=file_service,
            config_service=config_service,
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        return BackupTestingFramework(
            backup_orchestrator=backup_orchestrator,
            database_service=database_service,
            file_service=file_service,
            config_service=config_service,
            restore_service=restore_service,
            test_data_path=os.getenv('TEST_DATA_PATH', '/app/test_data')
        )

    async def run_test_suite(self, suite_name: str) -> TestExecution:
        """Run a specific test suite"""
        self.logger.info(f"Running test suite: {suite_name}")
        
        try:
            execution = await self.testing_framework.execute_test_suite(
                suite_id=suite_name,
                environment="testing"
            )
            
            # Save test results
            await self._save_test_results(execution)
            
            self.logger.info(f"Test suite completed: {suite_name} - Status: {execution.overall_status.value}")
            return execution
            
        except Exception as e:
            self.logger.error(f"Test suite {suite_name} failed: {e}")
            raise

    async def run_all_tests(self) -> Dict[str, TestExecution]:
        """Run all available test suites"""
        self.logger.info("Running all test suites")
        
        results = {}
        test_suites = [
            'backup_integrity',
            'restore_functionality',
            'coppa_compliance',
            'performance'
        ]
        
        # Add disaster recovery if enabled
        if os.getenv('DISASTER_RECOVERY_TESTING', 'false').lower() == 'true':
            test_suites.append('disaster_recovery')
        
        for suite_name in test_suites:
            try:
                execution = await self.run_test_suite(suite_name)
                results[suite_name] = execution
                
            except Exception as e:
                self.logger.error(f"Test suite {suite_name} failed: {e}")
                # Continue with other test suites
                continue
        
        # Generate summary report
        await self._generate_summary_report(results)
        
        return results

    async def run_daily_tests(self) -> Dict[str, TestExecution]:
        """Run daily automated tests"""
        self.logger.info("Running daily tests")
        
        return await self.testing_framework.run_daily_tests()

    async def run_weekly_tests(self) -> Dict[str, TestExecution]:
        """Run weekly comprehensive tests"""
        self.logger.info("Running weekly tests")
        
        return await self.testing_framework.run_weekly_tests()

    async def run_disaster_recovery_drill(self) -> TestExecution:
        """Run disaster recovery drill"""
        self.logger.info("Running disaster recovery drill")
        
        return await self.testing_framework.run_disaster_recovery_drill()

    async def _save_test_results(self, execution: TestExecution) -> None:
        """Save test execution results to file"""
        timestamp = execution.start_time.strftime('%Y%m%d_%H%M%S')
        filename = f"test_results_{execution.execution_id}_{timestamp}.json"
        filepath = os.path.join(self.test_results_path, filename)
        
        # Convert execution to serializable format
        results_data = {
            'execution_id': execution.execution_id,
            'start_time': execution.start_time.isoformat(),
            'end_time': execution.end_time.isoformat() if execution.end_time else None,
            'environment': execution.environment,
            'overall_status': execution.overall_status.value,
            'summary': execution.summary,
            'test_results': [
                {
                    'test_id': result.test_id,
                    'test_type': result.test_type.value,
                    'status': result.status.value,
                    'start_time': result.start_time.isoformat(),
                    'end_time': result.end_time.isoformat() if result.end_time else None,
                    'duration_seconds': result.duration_seconds,
                    'success_rate': result.success_rate,
                    'metrics': result.metrics,
                    'error_message': result.error_message,
                    'warnings': result.warnings,
                    'artifacts': result.artifacts
                }
                for result in execution.test_results
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        self.logger.info(f"Test results saved to: {filepath}")

    async def _generate_summary_report(self, results: Dict[str, TestExecution]) -> None:
        """Generate a summary report of all test results"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"test_summary_{timestamp}.json"
        filepath = os.path.join(self.test_results_path, filename)
        
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_suites': len(results),
            'passed_suites': len([r for r in results.values() if r.overall_status == TestStatus.PASSED]),
            'failed_suites': len([r for r in results.values() if r.overall_status == TestStatus.FAILED]),
            'warning_suites': len([r for r in results.values() if r.overall_status == TestStatus.WARNING]),
            'suite_results': {
                suite_name: {
                    'status': execution.overall_status.value,
                    'duration_seconds': (execution.end_time - execution.start_time).total_seconds() if execution.end_time else 0,
                    'test_count': len(execution.test_results),
                    'summary': execution.summary
                }
                for suite_name, execution in results.items()
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        self.logger.info(f"Summary report saved to: {filepath}")
        
        # Log summary to console
        self.logger.info(f"Test Summary: {summary['passed_suites']}/{summary['total_suites']} suites passed")

    def get_test_history(self, limit: int = 10) -> List[Dict]:
        """Get recent test execution history"""
        results = []
        
        try:
            # List test result files
            files = [f for f in os.listdir(self.test_results_path) if f.startswith('test_results_')]
            files.sort(reverse=True)  # Most recent first
            
            for filename in files[:limit]:
                filepath = os.path.join(self.test_results_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        results.append(data)
                except Exception as e:
                    self.logger.error(f"Error reading test results file {filename}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error getting test history: {e}")
        
        return results

    def cleanup_old_results(self, days: int = 30) -> None:
        """Clean up old test result files"""
        import time
        
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            for filename in os.listdir(self.test_results_path):
                filepath = os.path.join(self.test_results_path, filename)
                
                # Check file age
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    self.logger.info(f"Removed old test result file: {filename}")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up old test results: {e}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Teddy Bear Backup Test Runner')
    parser.add_argument('--suite', help='Run specific test suite')
    parser.add_argument('--all', action='store_true', help='Run all test suites')
    parser.add_argument('--daily', action='store_true', help='Run daily tests')
    parser.add_argument('--weekly', action='store_true', help='Run weekly tests')
    parser.add_argument('--dr-drill', action='store_true', help='Run disaster recovery drill')
    parser.add_argument('--history', action='store_true', help='Show test history')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Clean up test results older than N days')
    
    args = parser.parse_args()
    
    # Create test runner
    test_runner = BackupTestRunner()
    
    try:
        if args.history:
            # Show test history
            history = test_runner.get_test_history()
            print(json.dumps(history, indent=2, default=str))
            
        elif args.cleanup:
            # Clean up old results
            test_runner.cleanup_old_results(args.cleanup)
            print(f"Cleaned up test results older than {args.cleanup} days")
            
        elif args.suite:
            # Run specific test suite
            execution = await test_runner.run_test_suite(args.suite)
            print(f"Test suite {args.suite} completed with status: {execution.overall_status.value}")
            
        elif args.all:
            # Run all test suites
            results = await test_runner.run_all_tests()
            passed = len([r for r in results.values() if r.overall_status == TestStatus.PASSED])
            total = len(results)
            print(f"All tests completed: {passed}/{total} suites passed")
            
        elif args.daily:
            # Run daily tests
            results = await test_runner.run_daily_tests()
            passed = len([r for r in results.values() if r.overall_status == TestStatus.PASSED])
            total = len(results)
            print(f"Daily tests completed: {passed}/{total} suites passed")
            
        elif args.weekly:
            # Run weekly tests
            results = await test_runner.run_weekly_tests()
            passed = len([r for r in results.values() if r.overall_status == TestStatus.PASSED])
            total = len(results)
            print(f"Weekly tests completed: {passed}/{total} suites passed")
            
        elif args.dr_drill:
            # Run disaster recovery drill
            execution = await test_runner.run_disaster_recovery_drill()
            print(f"Disaster recovery drill completed with status: {execution.overall_status.value}")
            
        else:
            # Default: run basic integrity tests
            execution = await test_runner.run_test_suite('backup_integrity')
            print(f"Backup integrity tests completed with status: {execution.overall_status.value}")
        
        return 0
        
    except Exception as e:
        logging.error(f"Test runner failed: {e}")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)