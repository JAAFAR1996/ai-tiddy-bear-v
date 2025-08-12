#!/usr/bin/env python3
"""
🧸 AI Teddy Bear - Unified CLI Tool
==================================
Unified command-line interface for all AI Teddy Bear project operations.

Usage:
    python ai_teddy_cli.py [COMMAND] [OPTIONS]

Commands:
    check --full                    # Complete system analysis  
    check --connectivity            # ESP32-Server connection tests
    check --features               # Feature mapping analysis
    check --security               # Security vulnerability scan
    check --performance            # Performance validation
    test --all                     # Run all tests
    test --security                # Security tests only
    test --esp32                   # ESP32-specific tests
    deploy --production            # Production deployment
    deploy --staging               # Staging deployment
    monitor --health               # Health monitoring
    monitor --logs                 # Live log monitoring
    backup --create                # Create system backup
    backup --restore [FILE]        # Restore from backup
    
Author: AI Teddy Bear Development Team
Version: 5.0.0
"""

import os
import sys
import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import subprocess
import importlib.util

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    """Print AI Teddy Bear CLI banner."""
    banner = f"""
{Colors.HEADER}
🧸 AI Teddy Bear - Unified CLI Tool v5.0.0
==========================================
{Colors.ENDC}
Production-ready command-line interface for:
• System Analysis & Health Checks
• Security Vulnerability Scanning  
• ESP32-Server Connectivity Testing
• Performance Monitoring & Optimization
• Automated Deployment & Backup

{Colors.OKGREEN}Ready for production deployment!{Colors.ENDC}
"""
    print(banner)

class AITeddyCLI:
    """Main CLI controller class."""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.scripts_dir = self.project_root / "scripts"
        self.monitoring_dir = self.project_root / "monitoring"
        self.security_dir = self.project_root / "security_system"
        
    def _run_script(self, script_path: Path, args: List[str] = None) -> int:
        """Run a Python script with optional arguments."""
        if not script_path.exists():
            print(f"{Colors.FAIL}❌ Script not found: {script_path}{Colors.ENDC}")
            return 1
            
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
            
        try:
            print(f"{Colors.OKBLUE}🚀 Running: {script_path.name}{Colors.ENDC}")
            result = subprocess.run(cmd, capture_output=False, text=True)
            return result.returncode
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error running script: {e}{Colors.ENDC}")
            return 1
    
    def _run_async_script(self, script_path: Path) -> int:
        """Run an async Python script."""
        try:
            spec = importlib.util.spec_from_file_location("script", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'main'):
                if asyncio.iscoroutinefunction(module.main):
                    return asyncio.run(module.main())
                else:
                    return module.main()
            return 0
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error running async script: {e}{Colors.ENDC}")
            return 1

    def check_full(self) -> int:
        """Complete system analysis."""
        print(f"{Colors.HEADER}🔍 Running Complete System Analysis{Colors.ENDC}")
        
        scripts = [
            "validate_production_readiness.py",
            "security_dependency_audit.py", 
            "dead_code_scanner.py",
            "test_coverage_report.py",
            "esp32_network_connectivity_test.py",
        ]
        
        total_errors = 0
        for script in scripts:
            script_path = self.scripts_dir / script
            result = self._run_script(script_path)
            if result != 0:
                total_errors += 1
                
        if total_errors == 0:
            print(f"{Colors.OKGREEN}✅ Complete system analysis PASSED{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}❌ System analysis completed with {total_errors} errors{Colors.ENDC}")
            
        return total_errors

    def check_connectivity(self) -> int:
        """ESP32-Server connection tests."""
        print(f"{Colors.HEADER}🔗 Testing ESP32-Server Connectivity{Colors.ENDC}")
        
        scripts = [
            "esp32_network_connectivity_test.py",
            "esp32_ssl_tls_security_test.py",
            "esp32_security_authentication_test.py",
        ]
        
        total_errors = 0
        for script in scripts:
            script_path = self.scripts_dir / script
            result = self._run_script(script_path)
            if result != 0:
                total_errors += 1
                
        return total_errors

    def check_security(self) -> int:
        """Security vulnerability scanning."""
        print(f"{Colors.HEADER}🛡️ Running Security Vulnerability Scan{Colors.ENDC}")
        
        # Run main security system
        security_script = self.security_dir / "run_security.py"
        if security_script.exists():
            result1 = self._run_script(security_script)
        else:
            result1 = 1
            
        # Run additional security checks
        scripts = [
            "security_dependency_audit.py",
            "jwt_security_test.py",
            "secrets_audit.py",
            "child_safety_validator.py",
        ]
        
        total_errors = result1
        for script in scripts:
            script_path = self.scripts_dir / script
            result = self._run_script(script_path)
            if result != 0:
                total_errors += 1
                
        return total_errors

    def check_performance(self) -> int:
        """Performance validation."""
        print(f"{Colors.HEADER}⚡ Running Performance Validation{Colors.ENDC}")
        
        scripts = [
            "performance_optimizer.py",
            "esp32_performance_measurement_test.py",
            "database_cleanup_validator.py",
        ]
        
        total_errors = 0
        for script in scripts:
            script_path = self.scripts_dir / script
            result = self._run_script(script_path)
            if result != 0:
                total_errors += 1
                
        return total_errors

    def test_all(self) -> int:
        """Run all tests."""
        print(f"{Colors.HEADER}🧪 Running All Tests{Colors.ENDC}")
        
        test_script = self.scripts_dir / "run_tests.py"
        return self._run_script(test_script)

    def test_security(self) -> int:
        """Security tests only."""
        print(f"{Colors.HEADER}🔒 Running Security Tests{Colors.ENDC}")
        
        scripts = [
            "jwt_penetration_test.py",
            "jwt_security_test.py", 
            "environment_security_test.py",
        ]
        
        total_errors = 0
        for script in scripts:
            script_path = self.scripts_dir / script
            result = self._run_script(script_path)
            if result != 0:
                total_errors += 1
                
        return total_errors

    def deploy_production(self) -> int:
        """Production deployment."""
        print(f"{Colors.HEADER}🚀 Starting Production Deployment{Colors.ENDC}")
        
        deploy_script = self.scripts_dir / "production" / "deploy.sh"
        if deploy_script.exists():
            try:
                result = subprocess.run(["bash", str(deploy_script)], 
                                      capture_output=False, text=True)
                return result.returncode
            except Exception as e:
                print(f"{Colors.FAIL}❌ Deployment failed: {e}{Colors.ENDC}")
                return 1
        else:
            print(f"{Colors.FAIL}❌ Deployment script not found{Colors.ENDC}")
            return 1

    def monitor_health(self) -> int:
        """Health monitoring."""
        print(f"{Colors.HEADER}📊 Starting Health Monitoring{Colors.ENDC}")
        
        health_script = self.monitoring_dir / "comprehensive-health-monitoring.py"
        return self._run_script(health_script)

    def backup_create(self) -> int:
        """Create system backup."""
        print(f"{Colors.HEADER}💾 Creating System Backup{Colors.ENDC}")
        
        backup_script = self.scripts_dir / "backup_scheduler.py"
        return self._run_script(backup_script, ["--create"])

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI Teddy Bear Unified CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python ai_teddy_cli.py check --full
    python ai_teddy_cli.py test --security  
    python ai_teddy_cli.py deploy --production
    python ai_teddy_cli.py monitor --health
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Check commands
    check_parser = subparsers.add_parser('check', help='System analysis commands')
    check_group = check_parser.add_mutually_exclusive_group(required=True)
    check_group.add_argument('--full', action='store_true', help='Complete analysis')
    check_group.add_argument('--connectivity', action='store_true', help='Connection tests')  
    check_group.add_argument('--security', action='store_true', help='Security scan')
    check_group.add_argument('--performance', action='store_true', help='Performance validation')
    
    # Test commands
    test_parser = subparsers.add_parser('test', help='Testing commands')
    test_group = test_parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument('--all', action='store_true', help='Run all tests')
    test_group.add_argument('--security', action='store_true', help='Security tests only')
    
    # Deploy commands  
    deploy_parser = subparsers.add_parser('deploy', help='Deployment commands')
    deploy_group = deploy_parser.add_mutually_exclusive_group(required=True)
    deploy_group.add_argument('--production', action='store_true', help='Production deployment')
    deploy_group.add_argument('--staging', action='store_true', help='Staging deployment')
    
    # Monitor commands
    monitor_parser = subparsers.add_parser('monitor', help='Monitoring commands')
    monitor_group = monitor_parser.add_mutually_exclusive_group(required=True)
    monitor_group.add_argument('--health', action='store_true', help='Health monitoring')
    monitor_group.add_argument('--logs', action='store_true', help='Live log monitoring')
    
    # Backup commands
    backup_parser = subparsers.add_parser('backup', help='Backup commands')
    backup_group = backup_parser.add_mutually_exclusive_group(required=True)
    backup_group.add_argument('--create', action='store_true', help='Create backup')
    backup_group.add_argument('--restore', metavar='FILE', help='Restore from backup')
    
    args = parser.parse_args()
    
    if not args.command:
        print_banner()
        parser.print_help()
        return 0
        
    cli = AITeddyCLI()
    print_banner()
    
    try:
        if args.command == 'check':
            if args.full:
                return cli.check_full()
            elif args.connectivity:
                return cli.check_connectivity() 
            elif args.security:
                return cli.check_security()
            elif args.performance:
                return cli.check_performance()
                
        elif args.command == 'test':
            if args.all:
                return cli.test_all()
            elif args.security:
                return cli.test_security()
                
        elif args.command == 'deploy':
            if args.production:
                return cli.deploy_production()
            elif args.staging:
                print(f"{Colors.WARNING}⚠️ Staging deployment not yet implemented{Colors.ENDC}")
                return 1
                
        elif args.command == 'monitor':
            if args.health:
                return cli.monitor_health()
            elif args.logs:
                print(f"{Colors.WARNING}⚠️ Live log monitoring not yet implemented{Colors.ENDC}")
                return 1
                
        elif args.command == 'backup':
            if args.create:
                return cli.backup_create()
            elif args.restore:
                print(f"{Colors.WARNING}⚠️ Backup restore not yet implemented{Colors.ENDC}")
                return 1
                
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️ Operation cancelled by user{Colors.ENDC}")
        return 1
    except Exception as e:
        print(f"{Colors.FAIL}❌ Unexpected error: {e}{Colors.ENDC}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())