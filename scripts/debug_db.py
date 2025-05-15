import asyncio
import sys
import os
import logging
import json
from typing import List, Dict, Any

# Add parent directory to sys.path to allow importing from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("debug_db")

from tortoise import Tortoise
from config import settings
from models import User, Project

async def inspect_table(table_name: str) -> List[Dict[str, Any]]:
    """Get table schema information"""
    conn = Tortoise.get_connection("default")
    
    # Get column information
    columns_query = f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position;
    """
    columns_result = await conn.execute_query(columns_query)
    
    columns = []
    for row in columns_result[1]:
        columns.append({
            "name": row[0],
            "type": row[1],
            "nullable": row[2]
        })
    
    # Get key constraints
    constraints_query = f"""
        SELECT 
            tc.constraint_name, 
            tc.constraint_type,
            kcu.column_name
        FROM 
            information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
        WHERE 
            tc.table_name = '{table_name}'
            AND tc.constraint_schema = 'public'
        ORDER BY tc.constraint_type, tc.constraint_name;
    """
    constraints_result = await conn.execute_query(constraints_query)
    
    constraints = []
    for row in constraints_result[1]:
        constraints.append({
            "name": row[0],
            "type": row[1],
            "column": row[2]
        })
    
    # Get row count
    count_query = f"SELECT COUNT(*) FROM {table_name};"
    count_result = await conn.execute_query(count_query)
    row_count = count_result[1][0][0] if count_result[1] else 0
    
    return {
        "table_name": table_name,
        "columns": columns,
        "constraints": constraints,
        "row_count": row_count
    }

async def list_tables() -> List[str]:
    """List all tables in the database"""
    conn = Tortoise.get_connection("default")
    query = """
        SELECT tablename FROM pg_catalog.pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """
    result = await conn.execute_query(query)
    return [row[0] for row in result[1]]

async def inspect_users():
    """Inspect the users table"""
    conn = Tortoise.get_connection("default")
    
    # Check if users table exists
    tables_query = """
        SELECT tablename FROM pg_catalog.pg_tables
        WHERE schemaname = 'public' AND tablename = 'users';
    """
    tables_result = await conn.execute_query(tables_query)
    
    if not tables_result[1]:
        logger.error("Users table doesn't exist!")
        return
    
    # Get all users (limited to first 10)
    try:
        users_query = """
            SELECT id, email, role, is_active, created_at, last_login
            FROM users
            LIMIT 10;
        """
        users_result = await conn.execute_query(users_query)
        
        users = []
        for row in users_result[1]:
            users.append({
                "id": row[0],
                "email": row[1],
                "role": row[2],
                "is_active": row[3],
                "created_at": str(row[4]),
                "last_login": str(row[5]) if row[5] else None
            })
        
        if users:
            logger.info(f"Found {len(users)} users:")
            for user in users:
                logger.info(f"  - {user['email']} (role: {user['role']}, active: {user['is_active']})")
        else:
            logger.warning("No users found in the database!")
    except Exception as e:
        logger.error(f"Error querying users: {str(e)}")

async def inspect_projects():
    """Inspect the projects table and user associations"""
    conn = Tortoise.get_connection("default")
    
    # Check if projects table exists and has user_id field
    columns_query = """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'projects' AND column_name = 'user_id';
    """
    columns_result = await conn.execute_query(columns_query)
    
    if not columns_result[1]:
        logger.error("Projects table doesn't have user_id column!")
        return
    
    # Count projects by user
    try:
        projects_query = """
            SELECT u.email, COUNT(p.id)
            FROM users u
            LEFT JOIN projects p ON u.id = p.user_id
            GROUP BY u.email
            ORDER BY COUNT(p.id) DESC;
        """
        projects_result = await conn.execute_query(projects_query)
        
        logger.info("Projects by user:")
        for row in projects_result[1]:
            logger.info(f"  - {row[0]}: {row[1]} projects")
        
        # Count orphaned projects (no user)
        orphaned_query = """
            SELECT COUNT(*) FROM projects WHERE user_id IS NULL;
        """
        orphaned_result = await conn.execute_query(orphaned_query)
        orphaned_count = orphaned_result[1][0][0]
        
        logger.info(f"Orphaned projects (no user): {orphaned_count}")
    except Exception as e:
        logger.error(f"Error querying projects: {str(e)}")

async def run_diagnostics():
    """Run various database diagnostics"""
    logger.info("Connecting to database...")
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    try:
        # List all tables
        tables = await list_tables()
        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Check JWT settings
        if not hasattr(settings, 'JWT_SECRET_KEY'):
            logger.error("JWT_SECRET_KEY not found in settings!")
        elif not settings.JWT_SECRET_KEY:
            logger.error("JWT_SECRET_KEY is empty!")
        else:
            logger.info(f"JWT_SECRET_KEY is set (length: {len(settings.JWT_SECRET_KEY)})")
        
        # Inspect users and projects tables
        await inspect_users()
        await inspect_projects()
        
        # Ask which table to inspect in detail
        print("\nWhich table would you like to inspect in detail?")
        for i, table in enumerate(tables):
            print(f"{i+1}. {table}")
        print(f"{len(tables)+1}. Exit")
        
        choice = input("\nEnter choice: ")
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(tables):
                table_name = tables[choice_idx]
                schema_info = await inspect_table(table_name)
                
                print(f"\n=== Table: {table_name} ===")
                print(f"Row count: {schema_info['row_count']}")
                
                print("\nColumns:")
                for col in schema_info['columns']:
                    print(f"  - {col['name']} ({col['type']}, {'NULL' if col['nullable'] == 'YES' else 'NOT NULL'})")
                
                print("\nConstraints:")
                for constraint in schema_info['constraints']:
                    print(f"  - {constraint['name']} ({constraint['type']} on {constraint['column']})")
        except (ValueError, IndexError):
            pass
        
    except Exception as e:
        logger.error(f"Error during diagnostics: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Close connections
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(run_diagnostics()) 