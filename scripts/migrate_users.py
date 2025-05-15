import asyncio
import logging
from tortoise import Tortoise
import sys
import os
import uuid
from getpass import getpass
from passlib.context import CryptContext

# Add parent directory to sys.path to allow importing from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from models import User, Project, UserRole, Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migrate_users")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password for storing"""
    return pwd_context.hash(password)

async def migrate_users():
    """
    Set up initial admin user and associate existing projects with this user
    """
    # Connect to the database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    try:
        logger.info("Starting user migration...")
        
        # Check if users table exists
        conn = Tortoise.get_connection("default")
        tables_query = """
            SELECT tablename FROM pg_catalog.pg_tables
            WHERE schemaname = 'public';
        """
        result = await conn.execute_query(tables_query)
        tables = [row[0] for row in result[1]]
        
        if 'users' not in tables:
            logger.info("Users table doesn't exist yet. Will be created by schema generation.")
        
        # Generate schema first to ensure all tables and columns exist
        logger.info("Generating schema to create necessary tables and columns...")
        await Tortoise.generate_schemas(safe=True)
        
        # Check if any users exist
        user_count = await User.all().count()
        
        if user_count == 0:
            logger.info("No users found - creating first admin user")
            
            # Get admin email and password from console input
            print("\n==== Create First Admin User ====")
            admin_email = input("Enter admin email: ")
            admin_password = getpass("Enter admin password: ")
            
            # Create admin user
            admin_user = await User.create(
                id=str(uuid.uuid4()),
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                role=UserRole.ADMIN
            )
            
            logger.info(f"Created admin user: {admin_email}")
            
            # Collect project IDs first
            project_ids = []
            projects_query = "SELECT id FROM projects;"
            projects_result = await conn.execute_query(projects_query)
            for row in projects_result[1]:
                project_ids.append(row[0])
            
            project_count = len(project_ids)
            if project_count > 0:
                logger.info(f"Found {project_count} existing projects - attaching to admin user")
                
                # Check if user_id column exists in projects table
                columns_query = """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'projects' AND column_name = 'user_id';
                """
                columns_result = await conn.execute_query(columns_query)
                
                if len(columns_result[1]) > 0:
                    # Update projects directly with SQL
                    logger.info("Updating projects to associate with admin user...")
                    update_query = """
                        UPDATE projects SET user_id = $1 WHERE user_id IS NULL;
                    """
                    await conn.execute_query(update_query, [str(admin_user.id)])
                    logger.info(f"All projects attached to admin user")
                else:
                    # Column doesn't exist yet, need to add it first
                    logger.info("Adding user_id column to projects table...")
                    alter_table_query = """
                        ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
                    """
                    await conn.execute_query(alter_table_query)
                    
                    # Then update projects
                    update_query = """
                        UPDATE projects SET user_id = $1 WHERE user_id IS NULL;
                    """
                    await conn.execute_query(update_query, [str(admin_user.id)])
                    logger.info(f"All projects attached to admin user")
        else:
            logger.info(f"Found {user_count} existing users - skipping admin creation")
            
            # Check if any projects don't have a user association
            # First check if the column exists
            columns_query = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'user_id';
            """
            columns_result = await conn.execute_query(columns_query)
            
            if len(columns_result[1]) > 0:
                # Count orphaned projects
                orphan_query = """
                    SELECT COUNT(*) FROM projects WHERE user_id IS NULL;
                """
                orphan_result = await conn.execute_query(orphan_query)
                orphan_projects = orphan_result[1][0][0]
                
                if orphan_projects > 0:
                    # Find admin user
                    admin = await User.filter(role=UserRole.ADMIN).first()
                    
                    if admin:
                        logger.info(f"Found {orphan_projects} projects without a user - attaching to admin")
                        update_query = """
                            UPDATE projects SET user_id = $1 WHERE user_id IS NULL;
                        """
                        await conn.execute_query(update_query, [str(admin.id)])
                        logger.info(f"All {orphan_projects} orphaned projects attached to admin user")
                    else:
                        logger.warning(f"Found {orphan_projects} projects without a user but no admin user exists")
            else:
                logger.info("The user_id column doesn't exist in projects table yet. Will be created by schema generation.")
        
        logger.info("User migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during user migration: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Close connections
    await Tortoise.close_connections()

async def migrate_projects_to_users():
    """
    Migrate all orphaned projects (with no user association) to a specific user.
    Default to the first admin user found, or prompt to create one if no admin exists.
    """
    logger.info("Connecting to database...")
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    try:
        # Check if there are orphaned projects
        orphaned_projects = await Project.filter(user_id=None).all()
        orphaned_count = len(orphaned_projects)
        
        if orphaned_count == 0:
            logger.info("No orphaned projects found. All projects are already associated with users.")
            return
        
        logger.info(f"Found {orphaned_count} projects with no user association.")
        
        # Find an admin user to assign the projects to
        admin_user = await User.filter(role=UserRole.ADMIN).first()
        
        if not admin_user:
            logger.warning("No admin user found. Creating a new admin user...")
            
            # Get admin user details
            admin_email = input("Enter email for admin user: ")
            admin_password = getpass("Enter password for admin user: ")
            
            from utils.auth import get_password_hash
            
            # Create admin user
            admin_user = await User.create(
                id=str(uuid.uuid4()),
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                role=UserRole.ADMIN
            )
            
            logger.info(f"Created new admin user with email: {admin_email}")
        
        # Assign all orphaned projects to the admin user
        for project in orphaned_projects:
            project.user = admin_user
            await project.save()
            logger.info(f"Assigned project '{project.name}' to user {admin_user.email}")
        
        logger.info(f"Successfully assigned {orphaned_count} projects to user {admin_user.email}")
        
        # Print project overview
        projects_by_user = {}
        all_projects = await Project.all().prefetch_related('user')
        
        for project in all_projects:
            user_email = project.user.email if project.user else "No User"
            if user_email not in projects_by_user:
                projects_by_user[user_email] = []
            projects_by_user[user_email].append(project.name)
        
        logger.info("\nProjects by user:")
        for user_email, project_names in projects_by_user.items():
            logger.info(f"User: {user_email}")
            for name in project_names:
                logger.info(f"  - {name}")
    
    except Exception as e:
        logger.error(f"Error during project migration: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Close connections
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(migrate_users())
    asyncio.run(migrate_projects_to_users()) 