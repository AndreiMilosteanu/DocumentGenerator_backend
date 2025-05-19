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
logger = logging.getLogger("migrate_to_aerich")

from db_config import TORTOISE_ORM
from tortoise import Tortoise

async def prepare_for_aerich():
    """
    Run this script to ensure the database is in a consistent state before
    migrating to Aerich. It runs all previous migration scripts.
    """
    try:
        logger.info("Connecting to database...")
        await Tortoise.init(config=TORTOISE_ORM)
        
        logger.info("Running database structure check...")
        # Import the db_migration functionality
        from db_migration import run_migration
        await run_migration()
        
        logger.info("Ready to initialize Aerich!")
        logger.info("Please run the following commands:")
        logger.info("1. python migrations.py init")
        logger.info("2. python migrations.py init-db")
        
    except Exception as e:
        logger.error(f"Error while preparing for Aerich: {str(e)}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(prepare_for_aerich()) 