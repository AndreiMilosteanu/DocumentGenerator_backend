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
logger = logging.getLogger("check_auth")

from tortoise import Tortoise
from config import settings
from models import User, Project

async def check_auth_setup():
    """
    Check that the authentication setup is working correctly
    """
    logger.info("Checking authentication setup...")
    
    # Connect to the database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    try:
        # Make sure JWT settings are configured
        if not hasattr(settings, 'JWT_SECRET_KEY'):
            logger.error("JWT_SECRET_KEY not found in settings! Update your .env file")
            return
        
        if not settings.JWT_SECRET_KEY:
            logger.error("JWT_SECRET_KEY is empty! Update your .env file")
            return
        
        # Check if users table exists and can be queried
        try:
            user_count = await User.all().count()
            logger.info(f"Found {user_count} existing users")
        except Exception as e:
            logger.error(f"Error querying users table: {str(e)}")
            logger.info("You need to run the migration script to create the users table")
            return
        
        # Check if projects have user field
        try:
            project_count = await Project.all().count()
            orphaned_projects = await Project.filter(user=None).count()
            logger.info(f"Found {project_count} projects, {orphaned_projects} without a user")
        except Exception as e:
            logger.error(f"Error querying projects: {str(e)}")
            logger.info("The Project model may not have the user field yet")
            return
            
        logger.info("Authentication setup check completed!")
        if user_count == 0:
            logger.info("No users found. Run scripts/migrate_users.py to create an admin user")
        else:
            logger.info("Users exist. Authentication should be working correctly")
        
    except Exception as e:
        logger.error(f"Error during authentication check: {str(e)}")
    
    # Close connections
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(check_auth_setup()) 