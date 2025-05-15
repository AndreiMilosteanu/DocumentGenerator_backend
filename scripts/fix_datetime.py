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
logger = logging.getLogger("fix_datetime")

async def fix_datetime_fields():
    """Fix the approved_at field in approved_subsections to use naive datetimes"""
    # Connect to the database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    # Get database connection
    conn = Tortoise.get_connection("default")
    
    try:
        logger.info("Checking approved_subsections table...")
        
        # Check if the column exists and its type
        column_query = """
            SELECT data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'approved_subsections' 
            AND column_name = 'approved_at';
        """
        result = await conn.execute_query(column_query)
        
        if result[1]:
            data_type = result[1][0][0]
            is_nullable = result[1][0][1]
            logger.info(f"Found approved_at column with type {data_type}, nullable: {is_nullable}")
            
            # Modify the column to use timestamp without time zone
            alter_query = """
                ALTER TABLE approved_subsections 
                ALTER COLUMN approved_at TYPE timestamp without time zone;
            """
            await conn.execute_query(alter_query)
            logger.info("Modified approved_at to use timestamp without time zone")
            
            # Update existing values to use current time
            update_query = """
                UPDATE approved_subsections 
                SET approved_at = CURRENT_TIMESTAMP;
            """
            result = await conn.execute_query(update_query)
            logger.info(f"Updated {result[0]} records with current timestamp")
            
        else:
            logger.warning("approved_at column not found in approved_subsections table")
    
    except Exception as e:
        logger.error(f"Error fixing datetime fields: {e}")
    
    # Close connections
    await Tortoise.close_connections()
    logger.info("Fix complete")

if __name__ == "__main__":
    asyncio.run(fix_datetime_fields()) 