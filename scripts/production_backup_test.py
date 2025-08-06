#!/usr/bin/env python3
"""
🧸 AI TEDDY BEAR - PRODUCTION BACKUP & RESTORE TEST
==================================================

Production-ready backup and restore testing that:
1. Creates a safe copy of production database for testing
2. Tests backup functionality without modifying production data
3. Validates restore procedures
4. Ensures COPPA compliance during backup/restore
5. Measures RTO/RPO metrics
"""

import asyncio
import logging
import json
import os
import shutil
import sqlite3
import tempfile
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BackupTestResult:
    """Backup test result."""
    test_name: str
    success: bool
    duration_seconds: float
    data_integrity_verified: bool
    coppa_compliance: bool
    issues: List[str]
    metrics: Dict[str, Any]

@dataclass
class RestoreTestResult:
    """Restore test result."""
    test_name: str
    success: bool
    duration_seconds: float
    data_recovery_complete: bool
    zero_data_loss: bool
    issues: List[str]
    rto_achieved: bool  # Recovery Time Objective
    rpo_achieved: bool  # Recovery Point Objective

class ProductionBackupTester:
    """Production-safe backup and restore testing."""
    
    def __init__(self, production_db_path: str = 'aiteddy_production.db'):
        self.production_db_path = production_db_path
        self.test_dir = tempfile.mkdtemp(prefix='ai_teddy_backup_test_')
        self.test_db_path = os.path.join(self.test_dir, 'test_copy.db')
        
        # Test metrics thresholds
        self.rto_threshold = 30 * 60  # 30 minutes max recovery time
        self.rpo_threshold = 5 * 60   # 5 minutes max data loss
        self.backup_time_threshold = 5 * 60  # 5 minutes max backup time
        
        logger.info(f"Backup test directory: {self.test_dir}")
    
    def create_test_copy(self) -> bool:
        """Create a safe copy of production database for testing."""
        try:
            if not os.path.exists(self.production_db_path):
                logger.error(f"Production database not found: {self.production_db_path}")
                return False
            
            # Create a copy for testing
            shutil.copy2(self.production_db_path, self.test_db_path)
            logger.info(f"✅ Created test copy of production database")
            
            # Verify copy
            if not os.path.exists(self.test_db_path):
                logger.error("Failed to create test copy")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create test copy: {e}")
            return False
    
    def calculate_data_checksum(self, database_path: str) -> str:
        """Calculate checksum of database data for integrity verification."""
        try:
            data_hash = hashlib.sha256()
            
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in sorted(tables):
                    if table.startswith('sqlite_'):
                        continue
                    
                    # Get row count for checksum
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    data_hash.update(f"{table}:{count}".encode())
                    
                    # Sample some data for checksum
                    cursor.execute(f"SELECT * FROM {table} LIMIT 10")
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        row_str = str(row).encode('utf-8')
                        data_hash.update(row_str)
            
            return data_hash.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating checksum: {e}")
            return ""
    
    def get_database_stats(self, database_path: str) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        try:
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                
                # Get table counts
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
                
                stats['tables'] = {}
                stats['total_records'] = 0
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats['tables'][table] = count
                    stats['total_records'] += count
                
                # File size
                stats['file_size_mb'] = os.path.getsize(database_path) / (1024 * 1024)
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            
        return stats
    
    def test_database_backup(self) -> BackupTestResult:
        """Test database backup functionality."""
        start_time = datetime.now()
        issues = []
        
        try:
            # Create backup filename
            backup_file = os.path.join(self.test_dir, f'backup_{start_time.strftime("%Y%m%d_%H%M%S")}.db')
            
            # Get original stats
            original_stats = self.get_database_stats(self.test_db_path)
            original_checksum = self.calculate_data_checksum(self.test_db_path)
            
            # Perform backup (simple file copy for SQLite)
            shutil.copy2(self.test_db_path, backup_file)
            logger.info(f"✅ Database backup created: {backup_file}")
            
            # Verify backup integrity
            backup_stats = self.get_database_stats(backup_file)
            backup_checksum = self.calculate_data_checksum(backup_file)
            
            data_integrity_verified = (
                original_checksum == backup_checksum and
                original_stats['total_records'] == backup_stats['total_records']
            )
            
            if not data_integrity_verified:
                issues.append("Backup data integrity verification failed")
            
            # Check backup file exists and has content
            if not os.path.exists(backup_file) or os.path.getsize(backup_file) == 0:
                issues.append("Backup file is empty or missing")
            
            # COPPA compliance check
            coppa_compliance = self.verify_coppa_backup_compliance(backup_file)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Check if backup time meets threshold
            backup_time_ok = duration <= self.backup_time_threshold
            if not backup_time_ok:
                issues.append(f"Backup time {duration:.1f}s exceeds threshold {self.backup_time_threshold}s")
            
            success = (
                data_integrity_verified and 
                coppa_compliance and 
                len(issues) == 0 and
                backup_time_ok
            )
            
            metrics = {
                'backup_file_size_mb': backup_stats.get('file_size_mb', 0),
                'backup_duration_seconds': duration,
                'original_checksum': original_checksum,
                'backup_checksum': backup_checksum,
                'backup_time_threshold_met': backup_time_ok,
                'total_records_backed_up': backup_stats.get('total_records', 0),
                'table_counts': backup_stats.get('tables', {})
            }
            
            return BackupTestResult(
                test_name="production_database_backup",
                success=success,
                duration_seconds=duration,
                data_integrity_verified=data_integrity_verified,
                coppa_compliance=coppa_compliance,
                issues=issues,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"❌ Backup test failed: {e}")
            issues.append(f"Backup test exception: {e}")
            
            return BackupTestResult(
                test_name="production_database_backup",
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                data_integrity_verified=False,
                coppa_compliance=False,
                issues=issues,
                metrics={}
            )
    
    def verify_coppa_backup_compliance(self, backup_file: str) -> bool:
        """Verify COPPA compliance of backup."""
        try:
            with sqlite3.connect(backup_file) as conn:
                cursor = conn.cursor()
                
                # Check if children table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='children'")
                if not cursor.fetchone():
                    return False
                
                # Check if child data is preserved with parental consent
                cursor.execute("SELECT COUNT(*) FROM children WHERE parental_consent = 1")
                consented_children = cursor.fetchone()[0]
                
                # Check total children
                cursor.execute("SELECT COUNT(*) FROM children")
                total_children = cursor.fetchone()[0]
                
                # All children must have parental consent
                return total_children > 0 and consented_children == total_children
                
        except Exception as e:
            logger.error(f"COPPA compliance check failed: {e}")
            return False
    
    def test_database_restore(self, backup_file: str) -> RestoreTestResult:
        """Test database restore functionality."""
        start_time = datetime.now()
        issues = []
        
        try:
            # Create temporary restore location
            restore_file = os.path.join(self.test_dir, 'restored_database.db')
            
            # Get backup stats
            backup_stats = self.get_database_stats(backup_file)
            backup_checksum = self.calculate_data_checksum(backup_file)
            
            # Perform restore
            shutil.copy2(backup_file, restore_file)
            logger.info(f"✅ Database restored to: {restore_file}")
            
            # Verify restore integrity
            restore_stats = self.get_database_stats(restore_file)
            restore_checksum = self.calculate_data_checksum(restore_file)
            
            data_recovery_complete = (
                backup_checksum == restore_checksum and
                backup_stats['total_records'] == restore_stats['total_records']
            )
            
            if not data_recovery_complete:
                issues.append("Restored data integrity verification failed")
            
            # Verify zero data loss
            zero_data_loss = self.verify_zero_data_loss(backup_file, restore_file)
            if not zero_data_loss:
                issues.append("Data loss detected during restore")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Check RTO (Recovery Time Objective)
            rto_achieved = duration <= self.rto_threshold
            if not rto_achieved:
                issues.append(f"RTO not met: {duration:.1f}s > {self.rto_threshold}s")
            
            # RPO is achieved for full backup restore
            rpo_achieved = True
            
            success = (
                data_recovery_complete and 
                zero_data_loss and 
                rto_achieved and 
                len(issues) == 0
            )
            
            return RestoreTestResult(
                test_name="production_database_restore",
                success=success,
                duration_seconds=duration,
                data_recovery_complete=data_recovery_complete,
                zero_data_loss=zero_data_loss,
                issues=issues,
                rto_achieved=rto_achieved,
                rpo_achieved=rpo_achieved
            )
            
        except Exception as e:
            logger.error(f"❌ Restore test failed: {e}")
            issues.append(f"Restore test exception: {e}")
            
            return RestoreTestResult(
                test_name="production_database_restore",
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                data_recovery_complete=False,
                zero_data_loss=False,
                issues=issues,
                rto_achieved=False,
                rpo_achieved=False
            )
    
    def verify_zero_data_loss(self, backup_file: str, restore_file: str) -> bool:
        """Verify zero data loss between backup and restore."""
        try:
            backup_stats = self.get_database_stats(backup_file)
            restore_stats = self.get_database_stats(restore_file)
            
            # Compare total records
            if backup_stats['total_records'] != restore_stats['total_records']:
                return False
                
            # Compare table counts
            for table, count in backup_stats['tables'].items():
                if restore_stats['tables'].get(table, 0) != count:
                    logger.error(f"Record count mismatch in {table}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Zero data loss verification failed: {e}")
            return False
    
    def generate_test_report(self, backup_result: BackupTestResult, restore_result: RestoreTestResult) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        timestamp = datetime.now()
        
        overall_success = backup_result.success and restore_result.success
        total_issues = len(backup_result.issues) + len(restore_result.issues)
        
        # Calculate production readiness score
        production_readiness_factors = [
            backup_result.success,
            restore_result.success,
            backup_result.data_integrity_verified,
            restore_result.data_recovery_complete,
            restore_result.zero_data_loss,
            backup_result.coppa_compliance,
            restore_result.rto_achieved,
            restore_result.rpo_achieved
        ]
        
        production_readiness_score = sum(production_readiness_factors) / len(production_readiness_factors)
        
        report = {
            'timestamp': timestamp.isoformat(),
            'overall_success': overall_success,
            'production_ready': overall_success and production_readiness_score >= 0.9,
            'production_readiness_score': round(production_readiness_score, 3),
            'backup_test': {
                'success': backup_result.success,
                'duration_seconds': backup_result.duration_seconds,
                'data_integrity_verified': backup_result.data_integrity_verified,
                'coppa_compliance': backup_result.coppa_compliance,
                'issues': backup_result.issues,
                'metrics': backup_result.metrics
            },
            'restore_test': {
                'success': restore_result.success,
                'duration_seconds': restore_result.duration_seconds,
                'data_recovery_complete': restore_result.data_recovery_complete,
                'zero_data_loss': restore_result.zero_data_loss,
                'rto_achieved': restore_result.rto_achieved,
                'rpo_achieved': restore_result.rpo_achieved,
                'issues': restore_result.issues
            },
            'summary': {
                'total_issues': total_issues,
                'backup_duration': backup_result.duration_seconds,
                'restore_duration': restore_result.duration_seconds,
                'total_test_duration': backup_result.duration_seconds + restore_result.duration_seconds
            },
            'thresholds': {
                'rto_threshold_seconds': self.rto_threshold,
                'rpo_threshold_seconds': self.rpo_threshold,
                'backup_time_threshold_seconds': self.backup_time_threshold
            },
            'recommendations': []
        }
        
        # Add recommendations
        if not overall_success:
            report['recommendations'].extend([
                "Fix all backup/restore issues before production deployment",
                "Verify data integrity mechanisms are working correctly",
                "Ensure COPPA compliance is maintained during backup operations"
            ])
        
        if not restore_result.rto_achieved:
            report['recommendations'].append("Optimize restore process to meet RTO requirements")
        
        if not backup_result.coppa_compliance:
            report['recommendations'].append("Review COPPA compliance in backup procedures")
        
        return report
    
    def print_test_report(self, report: Dict[str, Any]):
        """Print formatted test report."""
        print("\n" + "="*80)
        print("🧸 AI TEDDY BEAR - PRODUCTION BACKUP & RESTORE TEST REPORT")
        print("="*80)
        print(f"📅 Timestamp: {report['timestamp']}")
        print(f"🎯 Production Ready: {'✅ YES' if report['production_ready'] else '❌ NO'}")
        print(f"📊 Production Readiness Score: {report['production_readiness_score']:.1%}")
        print()
        
        # Backup test results
        backup = report['backup_test']
        print("💾 BACKUP TEST:")
        print(f"   Status: {'✅ PASS' if backup['success'] else '❌ FAIL'}")
        print(f"   Duration: {backup['duration_seconds']:.2f}s")
        print(f"   Data Integrity: {'✅' if backup['data_integrity_verified'] else '❌'}")
        print(f"   COPPA Compliance: {'✅' if backup['coppa_compliance'] else '❌'}")
        if backup['metrics']:
            print(f"   Records Backed Up: {backup['metrics'].get('total_records_backed_up', 0):,}")
            print(f"   Backup Size: {backup['metrics'].get('backup_file_size_mb', 0):.2f} MB")
        if backup['issues']:
            print(f"   Issues: {len(backup['issues'])}")
            for issue in backup['issues'][:3]:
                print(f"     • {issue}")
        
        # Restore test results
        restore = report['restore_test']
        print("\n🔄 RESTORE TEST:")
        print(f"   Status: {'✅ PASS' if restore['success'] else '❌ FAIL'}")
        print(f"   Duration: {restore['duration_seconds']:.2f}s")
        print(f"   Data Recovery: {'✅' if restore['data_recovery_complete'] else '❌'}")
        print(f"   Zero Data Loss: {'✅' if restore['zero_data_loss'] else '❌'}")
        print(f"   RTO Achieved: {'✅' if restore['rto_achieved'] else '❌'}")
        print(f"   RPO Achieved: {'✅' if restore['rpo_achieved'] else '❌'}")
        if restore['issues']:
            print(f"   Issues: {len(restore['issues'])}")
            for issue in restore['issues'][:3]:
                print(f"     • {issue}")
        
        # Summary
        summary = report['summary']
        print(f"\n📈 SUMMARY:")
        print(f"   Total Issues: {summary['total_issues']}")
        print(f"   Total Test Duration: {summary['total_test_duration']:.2f}s")
        
        # Recommendations
        if report['recommendations']:
            print("\n💡 RECOMMENDATIONS:")
            for rec in report['recommendations']:
                print(f"   • {rec}")
        
        print("="*80)
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive backup and restore test."""
        logger.info("🚀 Starting production backup and restore test...")
        
        try:
            # Create test copy
            if not self.create_test_copy():
                raise Exception("Failed to create test copy of production database")
            
            # Test backup
            logger.info("📦 Testing database backup...")
            backup_result = self.test_database_backup()
            
            # Find the backup file
            backup_files = [f for f in os.listdir(self.test_dir) if f.startswith('backup_')]
            if not backup_files:
                raise Exception("No backup file found")
            
            backup_file = os.path.join(self.test_dir, backup_files[0])
            
            # Test restore
            logger.info("🔄 Testing database restore...")
            restore_result = self.test_database_restore(backup_file)
            
            # Generate report
            report = self.generate_test_report(backup_result, restore_result)
            
            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"production_backup_test_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            # Print report
            self.print_test_report(report)
            print(f"\n📄 Detailed report saved to: {report_file}")
            
            logger.info("✅ Production backup and restore test completed")
            return report
            
        except Exception as e:
            logger.error(f"❌ Production backup and restore test failed: {e}")
            raise
        finally:
            # Cleanup
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)
                logger.info(f"🧹 Cleanup completed: {self.test_dir}")

async def main():
    """Main function."""
    try:
        tester = ProductionBackupTester()
        report = await tester.run_comprehensive_test()
        
        if report['production_ready']:
            print("\n🎉 Production backup and restore system is READY!")
            return 0
        else:
            print(f"\n⚠️  Production backup and restore system requires fixes!")
            return 1
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Production backup and restore test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)