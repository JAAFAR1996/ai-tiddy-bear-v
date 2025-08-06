#!/usr/bin/env python3
"""
🧸 AI TEDDY BEAR - DATABASE CLEANUP & VALIDATION SCRIPT
=====================================================

Production readiness script that:
1. Identifies and removes ALL test/mock/demo data from the database
2. Validates production schema integrity
3. Ensures COPPA compliance for all remaining data
4. Generates detailed cleanup report

⚠️ CRITICAL: This script performs IRREVERSIBLE data deletion
Only run in controlled environments with proper backups
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Database imports
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

try:
    from src.infrastructure.config.production_config import get_config, load_config
except ImportError:
    # Fallback if config is not available
    logger.warning("Config module not available, using environment variables")
    
    class MockConfig:
        def __init__(self):
            self.DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+asyncpg://username:password@localhost/ai_teddy_bear')
    
    def get_config():
        return MockConfig()
    
    def load_config():
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'database_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CleanupResult:
    """Result of cleanup operation."""
    table: str
    test_records_found: int
    test_records_deleted: int
    production_records_remaining: int
    issues_found: List[str]
    coppa_violations: List[str]

@dataclass
class ValidationResult:
    """Database validation result."""
    is_production_ready: bool
    total_test_records_found: int
    total_test_records_deleted: int
    issues: List[str]
    coppa_compliance_issues: List[str]
    schema_issues: List[str]
    cleanup_results: List[CleanupResult]


class DatabaseCleanupValidator:
    """Production database cleanup and validation system."""
    
    def __init__(self):
        """Initialize with configuration."""
        try:
            load_config()
            self.config = get_config()
            self.async_engine = None
            self.sync_engine = None
            self.session_factory = None
            
            # Test data patterns to identify and remove
            self.TEST_PATTERNS = {
                'emails': [
                    'test@test.com', 'a@a.com', 'demo@demo.com', 'sample@sample.com',
                    'example@example.com', 'dev@dev.com', 'staging@staging.com',
                    '.test.', '@test', 'testuser', 'demouser', 'sampleuser'
                ],
                'usernames': [
                    'test', 'demo', 'sample', 'admin', 'user', 'example', 
                    'testuser', 'testparent', 'demo_parent', 'sample_parent',
                    'dev_user', 'staging_user'
                ],
                'names': [
                    'test', 'demo', 'sample', 'example', 'TestChild', 'DemoChild',
                    'SampleChild', 'NoConsentChild', 'TestParent', 'DevChild'
                ],
                'metadata_patterns': [
                    'seeded', 'test', 'demo', 'sample', 'generated', 'mock',
                    'development', 'staging', 'qa_test', 'unittest'
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    async def initialize_connections(self):
        """Initialize database connections."""
        try:
            # Create async engine
            self.async_engine = create_async_engine(
                self.config.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create sync engine for schema inspection
            sync_url = self.config.DATABASE_URL.replace('+asyncpg', '+psycopg2')
            self.sync_engine = create_engine(sync_url, echo=False)
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("✅ Database connections initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connections: {e}")
            raise

    async def validate_schema_integrity(self) -> List[str]:
        """Validate database schema for production readiness."""
        issues = []
        
        try:
            # Get schema inspector
            inspector = inspect(self.sync_engine)
            tables = inspector.get_table_names()
            
            logger.info(f"🔍 Validating schema for {len(tables)} tables...")
            
            # Required production tables
            required_tables = [
                'users', 'children', 'conversations', 'messages', 
                'parental_consents', 'audit_logs', 'sessions'
            ]
            
            # Check required tables exist
            missing_tables = [table for table in required_tables if table not in tables]
            if missing_tables:
                issues.append(f"Missing required tables: {missing_tables}")
            
            # Validate critical indexes exist
            async with self.session_factory() as session:
                # Check for performance indexes
                index_checks = [
                    "SELECT 1 FROM pg_indexes WHERE tablename = 'users' AND indexname = 'idx_user_email'",
                    "SELECT 1 FROM pg_indexes WHERE tablename = 'children' AND indexname = 'idx_child_parent'",
                    "SELECT 1 FROM pg_indexes WHERE tablename = 'messages' AND indexname = 'idx_msg_conversation'"
                ]
                
                for check_query in index_checks:
                    try:
                        result = await session.execute(text(check_query))
                        if not result.scalar():
                            issues.append(f"Missing critical index: {check_query}")
                    except Exception as e:
                        logger.warning(f"Index check failed: {e}")
            
            # Check for test/development tables that shouldn't exist in production
            test_tables = [table for table in tables if any(
                pattern in table.lower() for pattern in ['test', 'demo', 'sample', 'dev', 'staging']
            )]
            
            if test_tables:
                issues.append(f"Test/development tables found: {test_tables}")
            
            logger.info(f"✅ Schema validation completed. Issues found: {len(issues)}")
            return issues
            
        except Exception as e:
            error_msg = f"Schema validation failed: {e}"
            logger.error(f"❌ {error_msg}")
            issues.append(error_msg)
            return issues

    async def identify_test_data_in_table(self, table: str) -> Dict[str, Any]:
        """Identify test data in a specific table."""
        test_records = []
        
        try:
            async with self.session_factory() as session:
                # Build WHERE conditions for test data patterns
                conditions = []
                
                # Check email patterns
                if table in ['users']:
                    email_conditions = [f"email ILIKE '%{pattern}%'" for pattern in self.TEST_PATTERNS['emails']]
                    conditions.extend(email_conditions)
                    
                    username_conditions = [f"username ILIKE '%{pattern}%'" for pattern in self.TEST_PATTERNS['usernames']]
                    conditions.extend(username_conditions)
                
                # Check name patterns
                if table in ['children']:
                    name_conditions = [f"name ILIKE '%{pattern}%'" for pattern in self.TEST_PATTERNS['names']]
                    conditions.extend(name_conditions)
                
                # Check metadata patterns (applies to all tables with metadata_json)
                metadata_conditions = []
                for pattern in self.TEST_PATTERNS['metadata_patterns']:
                    metadata_conditions.append(f"metadata_json::text ILIKE '%{pattern}%'")
                conditions.extend(metadata_conditions)
                
                # Check for specific test identifiers
                if table == 'users':
                    conditions.extend([
                        "display_name ILIKE '%test%'",
                        "display_name ILIKE '%demo%'",
                        "display_name ILIKE '%sample%'"
                    ])
                
                if conditions:
                    where_clause = " OR ".join(conditions)
                    query = f"SELECT id, created_at FROM {table} WHERE {where_clause}"
                    
                    result = await session.execute(text(query))
                    test_records = result.fetchall()
            
            return {
                'table': table,
                'test_records_count': len(test_records),
                'test_record_ids': [str(record[0]) for record in test_records]
            }
            
        except Exception as e:
            logger.error(f"❌ Error identifying test data in {table}: {e}")
            return {'table': table, 'test_records_count': 0, 'test_record_ids': [], 'error': str(e)}

    async def clean_test_data_from_table(self, table: str, test_record_ids: List[str]) -> CleanupResult:
        """Clean test data from a specific table."""
        issues = []
        coppa_violations = []
        records_deleted = 0
        
        try:
            if not test_record_ids:
                # Count remaining production records
                async with self.session_factory() as session:
                    count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    production_count = count_result.scalar()
                
                return CleanupResult(
                    table=table,
                    test_records_found=0,
                    test_records_deleted=0,
                    production_records_remaining=production_count,
                    issues_found=[],
                    coppa_violations=[]
                )
            
            async with self.session_factory() as session:
                # Before deletion, check for COPPA violations
                if table == 'children':
                    coppa_check_query = f"""
                        SELECT id, name, parental_consent, age_verified 
                        FROM {table} 
                        WHERE id = ANY(ARRAY{test_record_ids}::uuid[])
                        AND (parental_consent = false OR age_verified = false)
                    """
                    coppa_result = await session.execute(text(coppa_check_query))
                    coppa_issues = coppa_result.fetchall()
                    
                    for issue in coppa_issues:
                        coppa_violations.append(f"Child {issue[1]} (ID: {issue[0]}) lacks proper consent/verification")
                
                # Get foreign key dependencies and clean in proper order
                if table == 'users':
                    # Delete dependent records first
                    dependent_queries = [
                        f"DELETE FROM audit_logs WHERE user_id = ANY(ARRAY{test_record_ids}::uuid[])",
                        f"DELETE FROM sessions WHERE child_id IN (SELECT id FROM children WHERE parent_id = ANY(ARRAY{test_record_ids}::uuid[]))",
                        f"DELETE FROM messages WHERE child_id IN (SELECT id FROM children WHERE parent_id = ANY(ARRAY{test_record_ids}::uuid[]))",
                        f"DELETE FROM conversations WHERE child_id IN (SELECT id FROM children WHERE parent_id = ANY(ARRAY{test_record_ids}::uuid[]))",
                        f"DELETE FROM parental_consents WHERE child_id IN (SELECT id FROM children WHERE parent_id = ANY(ARRAY{test_record_ids}::uuid[]))",
                        f"DELETE FROM children WHERE parent_id = ANY(ARRAY{test_record_ids}::uuid[])"
                    ]
                    
                    for dep_query in dependent_queries:
                        try:
                            await session.execute(text(dep_query))
                        except Exception as e:
                            issues.append(f"Failed to delete dependent records: {e}")
                
                # Delete main records
                delete_query = f"DELETE FROM {table} WHERE id = ANY(ARRAY{test_record_ids}::uuid[])"
                result = await session.execute(text(delete_query))
                records_deleted = result.rowcount
                
                await session.commit()
                
                # Count remaining production records
                count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                production_count = count_result.scalar()
                
                logger.info(f"✅ Cleaned {records_deleted} test records from {table}")
                
                return CleanupResult(
                    table=table,
                    test_records_found=len(test_record_ids),
                    test_records_deleted=records_deleted,
                    production_records_remaining=production_count,
                    issues_found=issues,
                    coppa_violations=coppa_violations
                )
                
        except Exception as e:
            error_msg = f"Failed to clean test data from {table}: {e}"
            logger.error(f"❌ {error_msg}")
            issues.append(error_msg)
            
            return CleanupResult(
                table=table,
                test_records_found=len(test_record_ids),
                test_records_deleted=0,
                production_records_remaining=0,
                issues_found=issues,
                coppa_violations=coppa_violations
            )

    async def validate_coppa_compliance(self) -> List[str]:
        """Validate COPPA compliance across all remaining data."""
        violations = []
        
        try:
            async with self.session_factory() as session:
                # Check for children without parental consent
                consent_check = await session.execute(text("""
                    SELECT c.id, c.name, c.estimated_age 
                    FROM children c 
                    WHERE c.parental_consent = false 
                    AND c.interaction_logging_enabled = true
                """))
                
                consent_violations = consent_check.fetchall()
                for violation in consent_violations:
                    violations.append(f"Child {violation[1]} (age {violation[2]}) lacks parental consent but has logging enabled")
                
                # Check for children with invalid ages (outside COPPA range)
                age_check = await session.execute(text("""
                    SELECT c.id, c.name, c.estimated_age 
                    FROM children c 
                    WHERE c.estimated_age NOT BETWEEN 3 AND 13
                """))
                
                age_violations = age_check.fetchall()
                for violation in age_violations:
                    violations.append(f"Child {violation[1]} has invalid age: {violation[2]} (must be 3-13)")
                
                # Check for data retention violations
                retention_check = await session.execute(text("""
                    SELECT c.id, c.name, c.data_retention_days 
                    FROM children c 
                    WHERE c.data_retention_days > 2555  -- 7 years max
                """))
                
                retention_violations = retention_check.fetchall()
                for violation in retention_violations:
                    violations.append(f"Child {violation[1]} has excessive data retention: {violation[2]} days")
                
                # Check for missing consent records
                missing_consent_check = await session.execute(text("""
                    SELECT c.id, c.name 
                    FROM children c 
                    LEFT JOIN parental_consents pc ON c.id = pc.child_id 
                    WHERE c.parental_consent = true AND pc.id IS NULL
                """))
                
                missing_consent = missing_consent_check.fetchall()
                for violation in missing_consent:
                    violations.append(f"Child {violation[1]} marked as consented but no consent record found")
                
                logger.info(f"✅ COPPA compliance check completed. Violations: {len(violations)}")
                return violations
                
        except Exception as e:
            error_msg = f"COPPA compliance validation failed: {e}"
            logger.error(f"❌ {error_msg}")
            violations.append(error_msg)
            return violations

    async def run_comprehensive_cleanup(self) -> ValidationResult:
        """Run comprehensive database cleanup and validation."""
        logger.info("🚀 Starting comprehensive database cleanup and validation...")
        
        try:
            await self.initialize_connections()
            
            # Step 1: Validate schema integrity
            logger.info("📋 Step 1: Validating schema integrity...")
            schema_issues = await self.validate_schema_integrity()
            
            # Step 2: Identify test data across all tables
            logger.info("🔍 Step 2: Identifying test data...")
            tables_to_check = ['users', 'children', 'conversations', 'messages', 'parental_consents', 'audit_logs', 'sessions']
            
            test_data_identification = {}
            for table in tables_to_check:
                test_data_identification[table] = await self.identify_test_data_in_table(table)
            
            # Step 3: Clean test data (in proper order for foreign key constraints)
            logger.info("🧹 Step 3: Cleaning test data...")
            cleanup_results = []
            cleanup_order = ['sessions', 'messages', 'conversations', 'parental_consents', 'children', 'users', 'audit_logs']
            
            for table in cleanup_order:
                if table in test_data_identification:
                    test_ids = test_data_identification[table]['test_record_ids']
                    cleanup_result = await self.clean_test_data_from_table(table, test_ids)
                    cleanup_results.append(cleanup_result)
            
            # Step 4: Validate COPPA compliance
            logger.info("🔒 Step 4: Validating COPPA compliance...")
            coppa_violations = await self.validate_coppa_compliance()
            
            # Step 5: Generate final validation result
            total_test_found = sum(result.test_records_found for result in cleanup_results)
            total_test_deleted = sum(result.test_records_deleted for result in cleanup_results)
            
            all_issues = schema_issues.copy()
            for result in cleanup_results:
                all_issues.extend(result.issues_found)
            
            all_coppa_issues = coppa_violations.copy()
            for result in cleanup_results:
                all_coppa_issues.extend(result.coppa_violations)
            
            is_production_ready = (
                len(all_issues) == 0 and 
                len(all_coppa_issues) == 0 and 
                total_test_found == total_test_deleted
            )
            
            validation_result = ValidationResult(
                is_production_ready=is_production_ready,
                total_test_records_found=total_test_found,
                total_test_records_deleted=total_test_deleted,
                issues=all_issues,
                coppa_compliance_issues=all_coppa_issues,
                schema_issues=schema_issues,
                cleanup_results=cleanup_results
            )
            
            # Generate detailed report
            await self.generate_cleanup_report(validation_result)
            
            logger.info("✅ Comprehensive database cleanup completed!")
            return validation_result
            
        except Exception as e:
            logger.error(f"❌ Database cleanup failed: {e}")
            raise
        finally:
            if self.async_engine:
                await self.async_engine.dispose()
            if self.sync_engine:
                self.sync_engine.dispose()

    async def generate_cleanup_report(self, result: ValidationResult):
        """Generate detailed cleanup and validation report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = {
            "timestamp": timestamp,
            "production_ready": result.is_production_ready,
            "summary": {
                "test_records_found": result.total_test_records_found,
                "test_records_deleted": result.total_test_records_deleted,
                "issues_count": len(result.issues),
                "coppa_violations_count": len(result.coppa_compliance_issues),
                "schema_issues_count": len(result.schema_issues)
            },
            "table_cleanup_details": [
                {
                    "table": cr.table,
                    "test_records_found": cr.test_records_found,
                    "test_records_deleted": cr.test_records_deleted,
                    "production_records_remaining": cr.production_records_remaining,
                    "issues": cr.issues_found,
                    "coppa_violations": cr.coppa_violations
                }
                for cr in result.cleanup_results
            ],
            "schema_issues": result.schema_issues,
            "coppa_compliance_issues": result.coppa_compliance_issues,
            "general_issues": result.issues
        }
        
        # Save JSON report
        report_file = f"database_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("🧸 AI TEDDY BEAR - DATABASE CLEANUP REPORT")
        print("="*80)
        print(f"📅 Timestamp: {timestamp}")
        print(f"🎯 Production Ready: {'✅ YES' if result.is_production_ready else '❌ NO'}")
        print()
        print("📊 CLEANUP SUMMARY:")
        print(f"   🔍 Test records found: {result.total_test_records_found}")
        print(f"   🧹 Test records deleted: {result.total_test_records_deleted}")
        print(f"   ⚠️  Issues found: {len(result.issues)}")
        print(f"   🔒 COPPA violations: {len(result.coppa_compliance_issues)}")
        print(f"   📋 Schema issues: {len(result.schema_issues)}")
        print()
        
        if result.cleanup_results:
            print("📋 TABLE-BY-TABLE CLEANUP:")
            for cr in result.cleanup_results:
                print(f"   {cr.table}:")
                print(f"     - Test records: {cr.test_records_found} found, {cr.test_records_deleted} deleted")
                print(f"     - Production records remaining: {cr.production_records_remaining}")
                if cr.issues_found:
                    print(f"     - Issues: {len(cr.issues_found)}")
        
        if result.coppa_compliance_issues:
            print("\n🔒 COPPA COMPLIANCE ISSUES:")
            for issue in result.coppa_compliance_issues:
                print(f"   ❌ {issue}")
        
        if result.schema_issues:
            print("\n📋 SCHEMA ISSUES:")
            for issue in result.schema_issues:
                print(f"   ❌ {issue}")
        
        if result.issues:
            print("\n⚠️  GENERAL ISSUES:")
            for issue in result.issues:
                print(f"   ❌ {issue}")
        
        print()
        print(f"📄 Detailed report saved to: {report_file}")
        print("="*80)
        
        logger.info(f"✅ Cleanup report generated: {report_file}")


async def main():
    """Main function to run database cleanup and validation."""
    try:
        validator = DatabaseCleanupValidator()
        result = await validator.run_comprehensive_cleanup()
        
        # Return appropriate exit code
        if result.is_production_ready:
            print("\n🎉 Database is PRODUCTION READY!")
            return 0
        else:
            print("\n⚠️  Database requires attention before production deployment!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Database cleanup failed: {e}")
        print(f"\n❌ Database cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)