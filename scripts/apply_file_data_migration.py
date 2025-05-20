#!/usr/bin/env python
import asyncio
import logging
import sys
import os

# Add parent directory to sys.path to allow importing from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("apply_file_data_migration")

from db_config import TORTOISE_ORM
from tortoise import Tortoise

async def apply_migration():
    """
    Apply the file_data column migration directly.
    """
    try:
        logger.info("Connecting to database...")
        await Tortoise.init(config=TORTOISE_ORM)
        
        logger.info("Adding file_data column to file_uploads table...")
        conn = Tortoise.get_connection("default")
        
        # Execute the SQL from the migration file
        await conn.execute_query("""
            -- Add file_data field to file_uploads table
            ALTER TABLE "file_uploads" ADD COLUMN IF NOT EXISTS "file_data" BYTEA;
        """)
        
        logger.info("Migration applied successfully!")
        
    except Exception as e:
        logger.error(f"Error while applying migration: {str(e)}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(apply_migration()) 