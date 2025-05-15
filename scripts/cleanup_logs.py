import asyncio
import logging
from tortoise import Tortoise
import sys
import os

# Add parent directory to sys.path to allow importing from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cleanup")

async def cleanup_logs():
    """Clean up debug logs from the database"""
    # Connect to the database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    # Get database connection
    conn = Tortoise.get_connection("default")
    
    # Delete debug logs from the PostgreSQL log table
    # Note: This assumes PostgreSQL's pg_catalog schema
    try:
        logger.info("Cleaning up database logs...")
        
        # Get log count
        query = "SELECT COUNT(*) FROM pg_catalog.pg_logs WHERE log_level IN ('DEBUG', 'INFO');"
        try:
            result = await conn.execute_query(query)
            count = result[1][0][0] if result[1] else 0
            logger.info(f"Found {count} debug/info logs")
        except Exception as e:
            logger.warning(f"Could not count logs: {e}")
            
        # Delete logs with debug level
        try:
            query = "DELETE FROM pg_catalog.pg_logs WHERE log_level IN ('DEBUG', 'INFO');"
            await conn.execute_query(query)
            logger.info("Deleted debug and info logs")
        except Exception as e:
            logger.warning(f"Could not delete logs: {e}")
            logger.info("This is normal if you're not using PostgreSQL or the pg_catalog.pg_logs table doesn't exist")
        
        # Vacuum the database to reclaim space (if applicable)
        try:
            query = "VACUUM FULL;"
            await conn.execute_query(query)
            logger.info("Vacuumed database to reclaim space")
        except Exception as e:
            logger.warning(f"Could not vacuum database: {e}")
    
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
    
    # Close connections
    await Tortoise.close_connections()
    logger.info("Cleanup complete")

if __name__ == "__main__":
    asyncio.run(cleanup_logs()) 