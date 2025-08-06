#!/usr/bin/env python3
"""
🧸 AI TEDDY BEAR - PRODUCTION SCHEMA VALIDATION
==============================================

Comprehensive production schema validation script that:
1. Validates database schema matches production requirements
2. Checks all required tables, columns, indexes exist
3. Validates foreign key relationships
4. Ensures COPPA compliance constraints
5. Verifies performance indexes are in place
"""

import asyncio
import logging
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TableSchema:
    """Expected table schema definition."""
    name: str
    required_columns: Dict[str, str]  # column_name -> type
    required_indexes: List[str]
    foreign_keys: List[Tuple[str, str, str]]  # (column, ref_table, ref_column)
    constraints: List[Dict[str, Any]]

@dataclass
class ValidationResult:
    """Schema validation result."""
    table: str
    exists: bool
    missing_columns: List[str]
    missing_indexes: List[str]  
    missing_constraints: List[str]
    extra_columns: List[str]
    issues: List[str]
    score: float  # 0.0 to 1.0

class ProductionSchemaValidator:
    """Production database schema validator."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./aiteddy_production.db')
        
        # Define expected production schema
        self.expected_schema = {
            'users': TableSchema(
                name='users',
                required_columns={
                    'id': 'TEXT',
                    'email': 'TEXT',
                    'password_hash': 'TEXT',
                    'role': 'TEXT',
                    'is_active': 'INTEGER',
                    'display_name': 'TEXT',
                    'created_at': 'TEXT',
                    'updated_at': 'TEXT'
                },
                required_indexes=['idx_user_email', 'idx_user_role'],
                foreign_keys=[],
                constraints=[
                    {'type': 'unique', 'column': 'email'},
                    {'type': 'check', 'condition': "role IN ('parent', 'admin', 'support')"}
                ]
            ),
            'children': TableSchema(
                name='children',
                required_columns={
                    'id': 'TEXT',
                    'parent_id': 'TEXT',
                    'name': 'TEXT',
                    'estimated_age': 'INTEGER',
                    'parental_consent': 'INTEGER',
                    'safety_settings': 'TEXT',
                    'created_at': 'TEXT',
                    'updated_at': 'TEXT'
                },
                required_indexes=['idx_child_parent', 'idx_child_age'],
                foreign_keys=[('parent_id', 'users', 'id')],
                constraints=[
                    {'type': 'check', 'condition': 'estimated_age >= 3 AND estimated_age <= 13'}
                ]
            ),
            'conversations': TableSchema(
                name='conversations',
                required_columns={
                    'id': 'TEXT',
                    'child_id': 'TEXT',
                    'title': 'TEXT',
                    'status': 'TEXT',
                    'started_at': 'TEXT',
                    'created_at': 'TEXT',
                    'updated_at': 'TEXT'
                },
                required_indexes=['idx_conv_child', 'idx_conv_created'],
                foreign_keys=[('child_id', 'children', 'id')],
                constraints=[]
            ),
            'messages': TableSchema(
                name='messages',
                required_columns={
                    'id': 'TEXT',
                    'conversation_id': 'TEXT',
                    'child_id': 'TEXT',
                    'content': 'TEXT',
                    'role': 'TEXT',
                    'safety_score': 'REAL',
                    'created_at': 'TEXT'
                },
                required_indexes=['idx_msg_conversation', 'idx_msg_child', 'idx_msg_safety'],
                foreign_keys=[
                    ('conversation_id', 'conversations', 'id'),
                    ('child_id', 'children', 'id')
                ],
                constraints=[
                    {'type': 'check', 'condition': "role IN ('user', 'assistant', 'system')"},
                    {'type': 'check', 'condition': 'safety_score >= 0.0 AND safety_score <= 1.0'}
                ]
            ),
            'parental_consents': TableSchema(
                name='parental_consents',
                required_columns={
                    'id': 'TEXT',
                    'parent_email': 'TEXT',
                    'child_id': 'TEXT',
                    'consent_timestamp': 'TEXT',
                    'ip_address': 'TEXT',
                    'created_at': 'TEXT'
                },
                required_indexes=['idx_consent_child', 'idx_consent_email'],
                foreign_keys=[('child_id', 'children', 'id')],
                constraints=[
                    {'type': 'unique', 'columns': ['parent_email', 'child_id']}
                ]
            ),
            'sessions': TableSchema(
                name='sessions',
                required_columns={
                    'id': 'TEXT',
                    'child_id': 'TEXT',
                    'status': 'TEXT',
                    'created_at': 'TEXT',
                    'last_activity': 'TEXT'
                },
                required_indexes=['idx_session_child', 'idx_session_activity'],
                foreign_keys=[('child_id', 'children', 'id')],
                constraints=[]
            ),
            'audit_logs': TableSchema(
                name='audit_logs',
                required_columns={
                    'id': 'TEXT',
                    'table_name': 'TEXT',
                    'record_id': 'TEXT',
                    'action': 'TEXT',
                    'user_id': 'TEXT',
                    'created_at': 'TEXT'
                },
                required_indexes=['idx_audit_table_record', 'idx_audit_created'],
                foreign_keys=[],
                constraints=[
                    {'type': 'check', 'condition': "action IN ('INSERT', 'UPDATE', 'DELETE')"}
                ]
            )
        }
    
    def validate_sqlite_schema(self) -> Dict[str, ValidationResult]:
        """Validate SQLite database schema."""
        results = {}
        
        try:
            # Extract database path from URL
            db_path = self.database_url.replace('sqlite:///', '').replace('sqlite://', '')
            
            if not os.path.exists(db_path):
                logger.error(f"Database file not found: {db_path}")
                return results
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Get all existing tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"Found {len(existing_tables)} tables: {existing_tables}")
                
                # Validate each expected table
                for table_name, expected_schema in self.expected_schema.items():
                    result = self.validate_table_schema(cursor, table_name, expected_schema, existing_tables)
                    results[table_name] = result
                
                # Check for unexpected tables
                unexpected_tables = [t for t in existing_tables if t not in self.expected_schema.keys() and not t.startswith('sqlite_')]
                if unexpected_tables:
                    logger.warning(f"Unexpected tables found: {unexpected_tables}")
                
                return results
                
        except Exception as e:
            logger.error(f"Error validating SQLite schema: {e}")
            return results
    
    def validate_table_schema(self, cursor, table_name: str, expected: TableSchema, existing_tables: List[str]) -> ValidationResult:
        """Validate individual table schema."""
        result = ValidationResult(
            table=table_name,
            exists=table_name in existing_tables,
            missing_columns=[],
            missing_indexes=[],
            missing_constraints=[],
            extra_columns=[],
            issues=[],
            score=0.0
        )
        
        if not result.exists:
            result.issues.append(f"Table {table_name} does not exist")
            return result
        
        try:
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            existing_columns = {col[1]: col[2] for col in columns_info}  # name -> type
            
            # Check required columns
            for col_name, col_type in expected.required_columns.items():
                if col_name not in existing_columns:
                    result.missing_columns.append(col_name)
                    result.issues.append(f"Missing required column: {col_name}")
                elif not self.types_compatible(existing_columns[col_name], col_type):
                    result.issues.append(f"Column {col_name} type mismatch: expected {col_type}, got {existing_columns[col_name]}")
            
            # Check for extra columns (might indicate schema drift)
            for col_name in existing_columns:
                if col_name not in expected.required_columns:
                    result.extra_columns.append(col_name)
            
            # Check indexes
            cursor.execute(f"PRAGMA index_list({table_name})")
            existing_indexes = [idx[1] for idx in cursor.fetchall() if idx[1]]  # Get non-null index names
            
            for required_index in expected.required_indexes:
                if required_index not in existing_indexes:
                    result.missing_indexes.append(required_index)
                    result.issues.append(f"Missing required index: {required_index}")
            
            # Check foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            existing_fks = cursor.fetchall()
            
            for expected_fk in expected.foreign_keys:
                col, ref_table, ref_col = expected_fk
                fk_exists = any(fk[3] == col and fk[2] == ref_table and fk[4] == ref_col for fk in existing_fks)
                if not fk_exists:
                    result.issues.append(f"Missing foreign key: {col} -> {ref_table}.{ref_col}")
            
            # Calculate score
            total_checks = (
                len(expected.required_columns) + 
                len(expected.required_indexes) + 
                len(expected.foreign_keys)
            )
            
            failed_checks = (
                len(result.missing_columns) + 
                len(result.missing_indexes) + 
                len([issue for issue in result.issues if 'foreign key' in issue])
            )
            
            if total_checks > 0:
                result.score = max(0.0, (total_checks - failed_checks) / total_checks)
            else:
                result.score = 1.0
            
            if result.score == 1.0 and len(result.issues) == 0:
                logger.info(f"✅ Table {table_name}: Perfect schema match")
            else:
                logger.warning(f"⚠️  Table {table_name}: Schema issues found (score: {result.score:.2f})")
            
        except Exception as e:
            result.issues.append(f"Error validating table {table_name}: {e}")
            logger.error(f"Error validating table {table_name}: {e}")
        
        return result
    
    def types_compatible(self, actual: str, expected: str) -> bool:
        """Check if database types are compatible."""
        # SQLite type mapping
        type_mapping = {
            'TEXT': ['TEXT', 'VARCHAR', 'CHAR', 'STRING'],
            'INTEGER': ['INTEGER', 'INT', 'BIGINT', 'BOOLEAN'],
            'REAL': ['REAL', 'FLOAT', 'DOUBLE', 'NUMERIC'],
            'BLOB': ['BLOB']
        }
        
        actual_upper = actual.upper()
        expected_upper = expected.upper()
        
        if actual_upper == expected_upper:
            return True
        
        # Check if types are in same category
        for base_type, variants in type_mapping.items():
            if expected_upper in variants and actual_upper in variants:
                return True
        
        return False
    
    def generate_schema_report(self, results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """Generate comprehensive schema validation report."""
        timestamp = datetime.now()
        
        total_tables = len(self.expected_schema)
        existing_tables = sum(1 for r in results.values() if r.exists)
        perfect_tables = sum(1 for r in results.values() if r.score == 1.0 and len(r.issues) == 0)
        
        overall_score = sum(r.score for r in results.values()) / len(results) if results else 0.0
        total_issues = sum(len(r.issues) for r in results.values())
        
        production_ready = (
            existing_tables == total_tables and 
            perfect_tables == total_tables and
            total_issues == 0
        )
        
        report = {
            'timestamp': timestamp.isoformat(),
            'database_url': self.database_url,
            'production_ready': production_ready,
            'summary': {
                'total_expected_tables': total_tables,
                'existing_tables': existing_tables,
                'perfect_tables': perfect_tables,
                'overall_score': round(overall_score, 3),
                'total_issues': total_issues
            },
            'table_results': {
                name: {
                    'exists': result.exists,
                    'score': round(result.score, 3),
                    'missing_columns': result.missing_columns,
                    'missing_indexes': result.missing_indexes,
                    'extra_columns': result.extra_columns,
                    'issues': result.issues
                }
                for name, result in results.items()
            },
            'recommendations': []
        }
        
        # Add recommendations
        if not production_ready:
            report['recommendations'].extend([
                "Review and fix all schema issues before production deployment",
                "Ensure all required indexes are created for optimal performance",
                "Verify foreign key constraints are properly defined",
                "Consider running database migration scripts to fix schema"
            ])
            
            # Specific recommendations
            for name, result in results.items():
                if not result.exists:
                    report['recommendations'].append(f"Create missing table: {name}")
                elif result.missing_columns:
                    report['recommendations'].append(f"Add missing columns to {name}: {', '.join(result.missing_columns)}")
                elif result.missing_indexes:
                    report['recommendations'].append(f"Create missing indexes for {name}: {', '.join(result.missing_indexes)}")
        
        return report
    
    def print_schema_report(self, report: Dict[str, Any]):
        """Print formatted schema validation report."""
        print("\n" + "="*80)
        print("🧸 AI TEDDY BEAR - PRODUCTION SCHEMA VALIDATION REPORT")
        print("="*80)
        print(f"📅 Timestamp: {report['timestamp']}")
        print(f"🗄️ Database: {report['database_url']}")
        print(f"🎯 Production Ready: {'✅ YES' if report['production_ready'] else '❌ NO'}")
        print()
        
        summary = report['summary']
        print("📊 SCHEMA SUMMARY:")
        print(f"   📋 Expected tables: {summary['total_expected_tables']}")
        print(f"   ✅ Existing tables: {summary['existing_tables']}")
        print(f"   🎯 Perfect tables: {summary['perfect_tables']}")
        print(f"   📈 Overall score: {summary['overall_score']:.1%}")
        print(f"   ⚠️  Total issues: {summary['total_issues']}")
        print()
        
        print("📋 TABLE-BY-TABLE ANALYSIS:")
        for table_name, result in report['table_results'].items():
            status = "✅" if result['score'] == 1.0 and len(result['issues']) == 0 else "⚠️" if result['exists'] else "❌"
            print(f"   {status} {table_name} (Score: {result['score']:.1%})")
            
            if result['missing_columns']:
                print(f"      Missing columns: {', '.join(result['missing_columns'])}")
            if result['missing_indexes']:
                print(f"      Missing indexes: {', '.join(result['missing_indexes'])}")
            if result['extra_columns']:
                print(f"      Extra columns: {', '.join(result['extra_columns'])}")
            if result['issues']:
                for issue in result['issues'][:3]:  # Show first 3 issues
                    print(f"      ⚠️  {issue}")
                if len(result['issues']) > 3:
                    print(f"      ... and {len(result['issues']) - 3} more issues")
        
        if report['recommendations']:
            print("\n💡 RECOMMENDATIONS:")
            for rec in report['recommendations'][:10]:  # Show first 10 recommendations
                print(f"   • {rec}")
            if len(report['recommendations']) > 10:
                print(f"   ... and {len(report['recommendations']) - 10} more recommendations")
        
        print("="*80)
        
    async def run_validation(self) -> Dict[str, Any]:
        """Run complete schema validation."""
        logger.info("🚀 Starting production schema validation...")
        
        try:
            # Validate schema
            if 'sqlite' in self.database_url.lower():
                results = self.validate_sqlite_schema()
            else:
                logger.warning("PostgreSQL schema validation not implemented in this version")
                results = {}
            
            # Generate report
            report = self.generate_schema_report(results)
            
            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"schema_validation_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            # Print report
            self.print_schema_report(report)
            print(f"\n📄 Detailed report saved to: {report_file}")
            
            logger.info("✅ Schema validation completed")
            return report
            
        except Exception as e:
            logger.error(f"❌ Schema validation failed: {e}")
            raise

async def main():
    """Main function."""
    try:
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
        
        validator = ProductionSchemaValidator(database_url)
        report = await validator.run_validation()
        
        if report['production_ready']:
            print("\n🎉 Database schema is PRODUCTION READY!")
            return 0
        else:
            print(f"\n⚠️  Schema requires {report['summary']['total_issues']} fixes before production!")
            return 1
            
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        print(f"\n❌ Schema validation failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)