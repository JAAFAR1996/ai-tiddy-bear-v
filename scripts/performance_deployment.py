#!/usr/bin/env python3
"""
Performance System Deployment Script
Automated deployment and configuration of the comprehensive performance optimization system
"""

import asyncio
import argparse
import logging
import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.performance import create_performance_system, PerformanceConfig
from infrastructure.performance.load_testing import create_load_test_runner


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceDeployment:
    """Handles deployment of the performance optimization system."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config = self._load_configuration()
        self.performance_system = None
    
    def _load_configuration(self) -> PerformanceConfig:
        """Load performance system configuration."""
        
        # Default configuration
        default_config = {
            "cdn": {
                "enabled": True,
                "cloudflare": {
                    "enabled": False,
                    "api_key": "",
                    "zone_id": ""
                },
                "aws_cloudfront": {
                    "enabled": False,
                    "access_key": "",
                    "secret_key": "",
                    "distribution_id": ""
                }
            },
            "cache": {
                "enabled": True,
                "redis_url": "redis://localhost:6379"
            },
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "ai_teddy_bear",
                "username": "app_user",
                "password": "",
                "pool_size": 10
            },
            "compression": {
                "enabled": True,
                "gzip_level": 6,
                "brotli_level": 6,
                "webp_quality": 85
            },
            "monitoring": {
                "enabled": True,
                "interval_seconds": 60,
                "webhook_alert_url": None
            },
            "optimization": {
                "auto_enabled": True,
                "interval_minutes": 60
            },
            "child_safety": {
                "data_encryption": True,
                "coppa_monitoring": True
            }
        }
        
        # Load from file if provided
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r') as f:
                    if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                        file_config = yaml.safe_load(f)
                    else:
                        file_config = json.load(f)
                
                # Merge configurations
                self._deep_merge(default_config, file_config)
                logger.info(f"Configuration loaded from {self.config_file}")
                
            except Exception as e:
                logger.error(f"Failed to load configuration from {self.config_file}: {e}")
                logger.info("Using default configuration")
        
        # Override with environment variables
        self._load_env_overrides(default_config)
        
        # Create PerformanceConfig object
        return PerformanceConfig(
            # CDN Configuration
            cdn_enabled=default_config["cdn"]["enabled"],
            cloudflare_config=default_config["cdn"]["cloudflare"] if default_config["cdn"]["cloudflare"]["enabled"] else None,
            aws_cloudfront_config=default_config["cdn"]["aws_cloudfront"] if default_config["cdn"]["aws_cloudfront"]["enabled"] else None,
            
            # Cache Configuration
            cache_enabled=default_config["cache"]["enabled"],
            redis_url=default_config["cache"]["redis_url"],
            
            # Database Configuration
            db_host=default_config["database"]["host"],
            db_port=default_config["database"]["port"],
            db_name=default_config["database"]["name"],
            db_username=default_config["database"]["username"],
            db_password=default_config["database"]["password"],
            db_pool_size=default_config["database"]["pool_size"],
            
            # Compression Configuration
            compression_enabled=default_config["compression"]["enabled"],
            gzip_level=default_config["compression"]["gzip_level"],
            brotli_level=default_config["compression"]["brotli_level"],
            webp_quality=default_config["compression"]["webp_quality"],
            
            # Monitoring Configuration
            monitoring_enabled=default_config["monitoring"]["enabled"],
            monitoring_interval_seconds=default_config["monitoring"]["interval_seconds"],
            webhook_alert_url=default_config["monitoring"]["webhook_alert_url"],
            
            # Optimization Configuration
            auto_optimization_enabled=default_config["optimization"]["auto_enabled"],
            optimization_interval_minutes=default_config["optimization"]["interval_minutes"],
            
            # Child Safety Configuration
            child_data_encryption=default_config["child_safety"]["data_encryption"],
            coppa_compliance_monitoring=default_config["child_safety"]["coppa_monitoring"]
        )
    
    def _deep_merge(self, base_dict: Dict[str, Any], override_dict: Dict[str, Any]) -> None:
        """Deep merge two dictionaries."""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _load_env_overrides(self, config: Dict[str, Any]) -> None:
        """Load configuration overrides from environment variables."""
        
        # Database overrides
        if os.getenv("DB_HOST"):
            config["database"]["host"] = os.getenv("DB_HOST")
        if os.getenv("DB_PORT"):
            config["database"]["port"] = int(os.getenv("DB_PORT"))
        if os.getenv("DB_NAME"):
            config["database"]["name"] = os.getenv("DB_NAME")
        if os.getenv("DB_USERNAME"):
            config["database"]["username"] = os.getenv("DB_USERNAME")
        if os.getenv("DB_PASSWORD"):
            config["database"]["password"] = os.getenv("DB_PASSWORD")
        
        # Redis override
        if os.getenv("REDIS_URL"):
            config["cache"]["redis_url"] = os.getenv("REDIS_URL")
        
        # CDN overrides
        if os.getenv("CLOUDFLARE_API_KEY"):
            config["cdn"]["cloudflare"]["api_key"] = os.getenv("CLOUDFLARE_API_KEY")
            config["cdn"]["cloudflare"]["enabled"] = True
        if os.getenv("CLOUDFLARE_ZONE_ID"):
            config["cdn"]["cloudflare"]["zone_id"] = os.getenv("CLOUDFLARE_ZONE_ID")
        
        # Alert webhook
        if os.getenv("WEBHOOK_ALERT_URL"):
            config["monitoring"]["webhook_alert_url"] = os.getenv("WEBHOOK_ALERT_URL")
    
    async def deploy(self) -> bool:
        """Deploy the performance system."""
        try:
            logger.info("Starting performance system deployment...")
            
            # Create performance system
            self.performance_system = create_performance_system(
                redis_url=self.config.redis_url,
                db_host=self.config.db_host,
                db_port=self.config.db_port,
                db_name=self.config.db_name,
                db_username=self.config.db_username,
                db_password=self.config.db_password,
                webhook_alert_url=self.config.webhook_alert_url,
                cloudflare_config=self.config.cloudflare_config,
                auto_optimization=self.config.auto_optimization_enabled
            )
            
            # Initialize and start the system
            await self.performance_system.initialize()
            await self.performance_system.start()
            
            logger.info("Performance system deployed successfully")
            
            # Run initial health check
            status = await self.performance_system.get_comprehensive_status()
            
            logger.info(f"System status: {status['overall_status']}")
            
            # Log component status
            for component, component_status in status.items():
                if isinstance(component_status, dict) and "status" in component_status:
                    logger.info(f"{component}: {component_status['status']}")
            
            return status['overall_status'] in ['healthy', 'partial']
            
        except Exception as e:
            logger.error(f"Performance system deployment failed: {e}")
            return False
    
    async def run_deployment_tests(self) -> Dict[str, Any]:
        """Run deployment validation tests."""
        if not self.performance_system:
            raise RuntimeError("Performance system not deployed")
        
        logger.info("Running deployment validation tests...")
        
        test_results = {
            "system_health": "unknown",
            "load_test": "not_run",
            "optimization_test": "not_run",
            "overall_status": "failed"
        }
        
        try:
            # System health check
            status = await self.performance_system.get_comprehensive_status()
            test_results["system_health"] = status['overall_status']
            
            # Quick load test (2 minutes)
            logger.info("Running quick load test...")
            benchmark_results = await self.performance_system.run_performance_benchmark(duration_minutes=2)
            
            test_results["load_test"] = {
                "grade": benchmark_results["performance_grade"],
                "requests_per_second": benchmark_results["load_test_results"]["requests_per_second"],
                "avg_response_time_ms": benchmark_results["load_test_results"]["avg_response_time_ms"],
                "error_rate": benchmark_results["load_test_results"]["error_rate"],
                "coppa_violations": benchmark_results["load_test_results"]["coppa_violations"]
            }
            
            # Test optimization engine if available
            if self.performance_system.optimization_engine:
                logger.info("Testing optimization engine...")
                opt_report = await self.performance_system.optimization_engine.get_optimization_report()
                test_results["optimization_test"] = {
                    "engine_running": opt_report["summary"]["engine_running"],
                    "pending_recommendations": opt_report["summary"]["pending_recommendations"]
                }
            
            # Determine overall status
            if (test_results["system_health"] in ["healthy", "partial"] and
                isinstance(test_results["load_test"], dict) and
                test_results["load_test"]["grade"] in ["A", "B", "C"]):
                test_results["overall_status"] = "passed"
            
            logger.info(f"Deployment tests completed. Status: {test_results['overall_status']}")
            
        except Exception as e:
            logger.error(f"Deployment tests failed: {e}")
            test_results["error"] = str(e)
        
        return test_results
    
    async def generate_deployment_report(self, output_dir: str) -> str:
        """Generate deployment report."""
        if not self.performance_system:
            raise RuntimeError("Performance system not deployed")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export comprehensive performance report
        report_file = output_path / "performance_deployment_report.json"
        await self.performance_system.export_performance_report(str(report_file))
        
        # Create deployment summary
        summary_file = output_path / "deployment_summary.json"
        
        status = await self.performance_system.get_comprehensive_status()
        
        summary = {
            "deployment_timestamp": asyncio.get_event_loop().time(),
            "configuration": {
                "cdn_enabled": self.config.cdn_enabled,
                "cache_enabled": self.config.cache_enabled,
                "compression_enabled": self.config.compression_enabled,
                "monitoring_enabled": self.config.monitoring_enabled,
                "auto_optimization_enabled": self.config.auto_optimization_enabled,
                "child_data_encryption": self.config.child_data_encryption,
                "coppa_compliance_monitoring": self.config.coppa_compliance_monitoring
            },
            "system_status": status,
            "deployment_success": status['overall_status'] in ['healthy', 'partial'],
            "next_steps": [
                "Monitor system performance for 24 hours",
                "Review optimization recommendations",
                "Configure alerting and notifications",
                "Schedule regular performance benchmarks",
                "Review child safety compliance reports"
            ]
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Deployment reports generated in {output_dir}")
        return str(output_dir)
    
    async def shutdown(self) -> None:
        """Shutdown the performance system."""
        if self.performance_system:
            await self.performance_system.stop()
            logger.info("Performance system shutdown completed")


async def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy AI Teddy Bear Performance System")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--test", "-t", action="store_true", help="Run deployment tests")
    parser.add_argument("--report", "-r", help="Generate deployment report in directory")
    parser.add_argument("--no-deploy", action="store_true", help="Skip deployment, only run tests")
    
    args = parser.parse_args()
    
    deployment = PerformanceDeployment(args.config)
    
    try:
        if not args.no_deploy:
            # Deploy the system
            success = await deployment.deploy()
            
            if not success:
                logger.error("Deployment failed")
                sys.exit(1)
        
        # Run tests if requested
        if args.test:
            test_results = await deployment.run_deployment_tests()
            
            print("\n" + "="*50)
            print("DEPLOYMENT TEST RESULTS")
            print("="*50)
            print(f"System Health: {test_results['system_health']}")
            
            if isinstance(test_results.get('load_test'), dict):
                load_test = test_results['load_test']
                print(f"Load Test Grade: {load_test['grade']}")
                print(f"Requests/Second: {load_test['requests_per_second']:.1f}")
                print(f"Avg Response Time: {load_test['avg_response_time_ms']:.1f}ms")
                print(f"Error Rate: {load_test['error_rate']:.1%}")
                print(f"COPPA Violations: {load_test['coppa_violations']}")
            
            print(f"Overall Status: {test_results['overall_status'].upper()}")
            print("="*50)
            
            if test_results['overall_status'] != 'passed':
                sys.exit(1)
        
        # Generate report if requested
        if args.report:
            report_dir = await deployment.generate_deployment_report(args.report)
            print(f"\nDeployment report generated: {report_dir}")
        
        print("\nPerformance system deployment completed successfully!")
        print("\nNext steps:")
        print("1. Monitor system performance for 24 hours")
        print("2. Review optimization recommendations")
        print("3. Configure alerting and notifications")
        print("4. Schedule regular performance benchmarks")
        print("5. Review child safety compliance reports")
        
        # Keep system running if deployed
        if not args.no_deploy:
            print("\nPress Ctrl+C to shutdown the performance system...")
            try:
                while True:
                    await asyncio.sleep(60)
                    status = await deployment.performance_system.get_comprehensive_status()
                    logger.info(f"System status: {status['overall_status']}")
            except KeyboardInterrupt:
                print("\nShutting down performance system...")
                await deployment.shutdown()
    
    except Exception as e:
        logger.error(f"Deployment script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())