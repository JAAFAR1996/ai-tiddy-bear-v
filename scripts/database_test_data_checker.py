#!/usr/bin/env python3
"""
🧸 DATABASE TEST DATA CHECKER
============================

Simple script to identify and report development/testing data in the database.
This script provides a comprehensive report without making changes.
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test patterns to look for
TEST_PATTERNS = {
    'emails': [
        'test@test.com', 'a@a.com', 'demo@demo.com', 'sample@sample.com',
        'example@example.com', 'dev@dev.com', 'staging@staging.com',
        'sarah.johnson@email.com', 'ahmed.hassan@email.com', 'maria.garcia@email.com'
    ],
    'usernames': [
        'test', 'demo', 'sample', 'admin', 'user', 'example', 
        'testuser', 'testparent', 'demo_parent', 'sample_parent',
        'dev_user', 'staging_user', 'sarah_mom', 'ahmed_dad', 'maria_mama'
    ],
    'names': [
        'test', 'demo', 'sample', 'example', 'TestChild', 'DemoChild',
        'SampleChild', 'NoConsentChild', 'TestParent', 'DevChild',
        'Emma', 'Oliver', 'Sofia', # From seeder script
    ],
    'content_keywords': [
        'seeded', 'test', 'demo', 'sample', 'generated', 'mock',
        'development', 'staging', 'qa_test', 'unittest', 'realistic_test'
    ]
}

class DatabaseTestDataChecker:
    """Check for test data in database without making changes."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./aiteddy_production.db')
        
    async def check_for_test_data(self) -> Dict[str, Any]:
        """Check all tables for test data patterns."""
        logger.info("🔍 Scanning database for development/testing data...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'database_url': self.database_url,
            'tables_checked': {},
            'summary': {
                'total_test_records': 0,
                'tables_with_test_data': 0,
                'production_ready': True
            },
            'issues': [],
            'recommendations': []
        }
        
        # For SQLite (development)
        if 'sqlite' in self.database_url.lower():
            return await self.check_sqlite_database(results)
        
        # For PostgreSQL (production)
        try:
            import asyncpg
            return await self.check_postgresql_database(results)
        except ImportError:
            logger.error("asyncpg not installed for PostgreSQL checking")
            results['issues'].append("asyncpg not available for PostgreSQL checks")
            return results
    
    async def check_sqlite_database(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Check SQLite database for test data."""
        try:
            import sqlite3
            
            # Extract database path from URL
            db_path = self.database_url.replace('sqlite:///', '').replace('sqlite:///', '')
            
            if not os.path.exists(db_path):
                results['issues'].append(f"Database file not found: {db_path}")
                return results
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"Found {len(tables)} tables: {tables}")
                
                for table in tables:
                    if table.startswith('sqlite_'):
                        continue
                        
                    table_result = await self.check_table_sqlite(cursor, table)
                    results['tables_checked'][table] = table_result
                    
                    if table_result['test_records_found'] > 0:
                        results['summary']['tables_with_test_data'] += 1
                        results['summary']['total_test_records'] += table_result['test_records_found']
                        results['summary']['production_ready'] = False
                
                # Add recommendations
                if results['summary']['total_test_records'] > 0:
                    results['recommendations'].extend([
                        "Remove all test/demo user accounts before production",
                        "Clear test conversation data",
                        "Ensure only real parent accounts remain",
                        "Verify COPPA compliance for all child records"
                    ])
                
                return results
                
        except Exception as e:
            logger.error(f"Error checking SQLite database: {e}")
            results['issues'].append(f"SQLite check failed: {e}")
            return results
    
    async def check_table_sqlite(self, cursor, table: str) -> Dict[str, Any]:
        """Check specific table for test data in SQLite."""
        result = {
            'test_records_found': 0,
            'total_records': 0,
            'test_patterns_detected': [],
            'sample_test_records': []
        }
        
        try:
            # Get total record count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            result['total_records'] = cursor.fetchone()[0]
            
            # Get column info
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Check for test patterns based on table type
            test_conditions = []
            
            if 'email' in columns:
                for email in TEST_PATTERNS['emails']:
                    test_conditions.append(f"email LIKE '%{email}%'")
            
            if 'username' in columns:
                for username in TEST_PATTERNS['usernames']:
                    test_conditions.append(f"username LIKE '%{username}%'")
            
            if 'name' in columns:
                for name in TEST_PATTERNS['names']:
                    test_conditions.append(f"name LIKE '%{name}%'")
            
            if 'display_name' in columns:
                test_conditions.extend([
                    "display_name LIKE '%test%'",
                    "display_name LIKE '%demo%'",
                    "display_name LIKE '%sample%'"
                ])
            
            # Check metadata/JSON fields
            json_columns = [col for col in columns if 'json' in col.lower() or 'metadata' in col.lower()]
            for json_col in json_columns:
                for keyword in TEST_PATTERNS['content_keywords']:
                    test_conditions.append(f"{json_col} LIKE '%{keyword}%'")
            
            if test_conditions:
                where_clause = " OR ".join(test_conditions)
                query = f"SELECT * FROM {table} WHERE {where_clause} LIMIT 5"
                
                cursor.execute(query)
                test_records = cursor.fetchall()
                
                result['test_records_found'] = len(test_records)
                result['sample_test_records'] = [dict(zip(columns, record)) for record in test_records[:3]]
                
                # Count total test records
                count_query = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
                cursor.execute(count_query)
                result['test_records_found'] = cursor.fetchone()[0]
            
            if result['test_records_found'] > 0:
                logger.warning(f"⚠️  Found {result['test_records_found']} test records in {table}")
            else:
                logger.info(f"✅ No test data found in {table}")
            
        except Exception as e:
            logger.error(f"Error checking table {table}: {e}")
            result['error'] = str(e)
        
        return result
    
    async def check_postgresql_database(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Check PostgreSQL database for test data."""
        try:
            import asyncpg
            
            conn = await asyncpg.connect(self.database_url)
            
            # Get all tables
            tables_query = """
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename NOT LIKE 'pg_%'
            """
            tables = await conn.fetch(tables_query)
            table_names = [table['tablename'] for table in tables]
            
            logger.info(f"Found {len(table_names)} tables: {table_names}")
            
            for table in table_names:
                table_result = await self.check_table_postgresql(conn, table)
                results['tables_checked'][table] = table_result
                
                if table_result['test_records_found'] > 0:
                    results['summary']['tables_with_test_data'] += 1
                    results['summary']['total_test_records'] += table_result['test_records_found']
                    results['summary']['production_ready'] = False
            
            await conn.close()
            
            # Add recommendations
            if results['summary']['total_test_records'] > 0:
                results['recommendations'].extend([
                    "Remove all test/demo user accounts before production",
                    "Clear test conversation data", 
                    "Ensure only real parent accounts remain",
                    "Verify COPPA compliance for all child records",
                    "Run database cleanup script to remove test data"
                ])
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking PostgreSQL database: {e}")
            results['issues'].append(f"PostgreSQL check failed: {e}")
            return results
    
    async def check_table_postgresql(self, conn, table: str) -> Dict[str, Any]:
        """Check specific table for test data in PostgreSQL."""
        result = {
            'test_records_found': 0,
            'total_records': 0,
            'test_patterns_detected': [],
            'sample_test_records': []
        }
        
        try:
            # Get total record count
            total_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            result['total_records'] = total_count
            
            # Get column info
            columns_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = $1
            """
            columns = await conn.fetch(columns_query, table)
            column_names = [col['column_name'] for col in columns]
            
            # Build test conditions
            test_conditions = []
            
            if 'email' in column_names:
                for email in TEST_PATTERNS['emails']:
                    test_conditions.append(f"email ILIKE '%{email}%'")
            
            if 'username' in column_names:
                for username in TEST_PATTERNS['usernames']:
                    test_conditions.append(f"username ILIKE '%{username}%'")
            
            if 'name' in column_names:
                for name in TEST_PATTERNS['names']:
                    test_conditions.append(f"name ILIKE '%{name}%'")
            
            if 'display_name' in column_names:
                test_conditions.extend([
                    "display_name ILIKE '%test%'",
                    "display_name ILIKE '%demo%'", 
                    "display_name ILIKE '%sample%'"
                ])
            
            # Check JSON/metadata columns
            json_columns = [col for col in column_names if 'json' in col.lower() or 'metadata' in col.lower()]
            for json_col in json_columns:
                for keyword in TEST_PATTERNS['content_keywords']:
                    test_conditions.append(f"{json_col}::text ILIKE '%{keyword}%'")
            
            if test_conditions:
                where_clause = " OR ".join(test_conditions)
                
                # Count test records
                count_query = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
                test_count = await conn.fetchval(count_query)
                result['test_records_found'] = test_count
                
                # Get sample records
                if test_count > 0:
                    sample_query = f"SELECT * FROM {table} WHERE {where_clause} LIMIT 3"
                    sample_records = await conn.fetch(sample_query)
                    result['sample_test_records'] = [dict(record) for record in sample_records]
            
            if result['test_records_found'] > 0:
                logger.warning(f"⚠️  Found {result['test_records_found']} test records in {table}")
            else:
                logger.info(f"✅ No test data found in {table}")
                
        except Exception as e:
            logger.error(f"Error checking table {table}: {e}")
            result['error'] = str(e)
        
        return result
    
    def generate_report(self, results: Dict[str, Any]):
        """Generate detailed report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"database_test_data_report_{timestamp}.json"
        
        # Save JSON report
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("🧸 AI TEDDY BEAR - DATABASE TEST DATA REPORT")
        print("="*80)
        print(f"📅 Timestamp: {results['timestamp']}")
        print(f"🗄️ Database: {results['database_url']}")
        print(f"🎯 Production Ready: {'✅ YES' if results['summary']['production_ready'] else '❌ NO'}")
        print()
        print("📊 SUMMARY:")
        print(f"   📋 Tables checked: {len(results['tables_checked'])}")
        print(f"   ⚠️  Tables with test data: {results['summary']['tables_with_test_data']}")
        print(f"   🔍 Total test records: {results['summary']['total_test_records']}")
        print()
        
        if results['tables_checked']:
            print("📋 TABLE DETAILS:")
            for table, data in results['tables_checked'].items():
                if data['test_records_found'] > 0:
                    print(f"   ❌ {table}: {data['test_records_found']} test records out of {data['total_records']} total")
                else:
                    print(f"   ✅ {table}: Clean ({data['total_records']} total records)")
        
        if results['issues']:
            print("\n⚠️  ISSUES:")
            for issue in results['issues']:
                print(f"   ❌ {issue}")
        
        if results['recommendations']:
            print("\n💡 RECOMMENDATIONS:")
            for rec in results['recommendations']:
                print(f"   • {rec}")
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        print("="*80)
        
        return report_file

async def main():
    """Main function."""
    try:
        # Try to get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            # Look for local SQLite database
            sqlite_files = ['aiteddy_production.db', 'ai_teddy_bear.db', 'database.db']
            for db_file in sqlite_files:
                if os.path.exists(db_file):
                    database_url = f'sqlite:///{db_file}'
                    break
            
            if not database_url:
                database_url = 'sqlite:///./aiteddy_production.db'
                logger.warning(f"No DATABASE_URL found, using default: {database_url}")
        
        checker = DatabaseTestDataChecker(database_url)
        results = await checker.check_for_test_data()
        report_file = checker.generate_report(results)
        
        if results['summary']['production_ready']:
            print("\n🎉 Database appears to be PRODUCTION READY!")
            return 0
        else:
            print(f"\n⚠️  Database contains {results['summary']['total_test_records']} test records that should be cleaned before production!")
            return 1
            
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        print(f"\n❌ Database check failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)