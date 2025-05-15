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
logger = logging.getLogger("migrations")

# Import migration scripts
from scripts.fix_datetime import fix_datetime_fields
from scripts.migrate_users import migrate_users

async def run_all_migrations():
    """
    Run all migration scripts in sequence
    """
    try:
        logger.info("Starting all migrations...")
        
        # Fix datetime fields
        logger.info("Running datetime field fix...")
        await fix_datetime_fields()
        
        # Create users and attach projects
        logger.info("Running user migration...")
        await migrate_users()
        
        logger.info("All migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during migrations: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_all_migrations()) 