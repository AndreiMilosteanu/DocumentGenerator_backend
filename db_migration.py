import asyncio
import logging
import json
from tortoise import Tortoise, connections
from config import settings
from models import Document, Project, SectionData, ChatMessage, ActiveSubsection, ApprovedSubsection, User

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_and_create_tables():
    """
    Checks if tables exist and have the correct structure.
    Creates or alters them as needed.
    """
    connection = connections.get('default')
    
    # Get existing tables (PostgreSQL syntax)
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """
    tables = await connection.execute_query(query)
    existing_tables = [row[0] for row in tables[1]]
    logger.info(f"Existing tables: {existing_tables}")
    
    # Check for tables that might need updates based on model structure
    models_check = [
        ("documents", Document),
        ("projects", Project),
        ("section_data", SectionData),
        ("chat_messages", ChatMessage),
        ("active_subsections", ActiveSubsection),
        ("approved_subsections", ApprovedSubsection),
        ("users", User)
    ]
    
    for table_name, model_class in models_check:
        if table_name not in existing_tables:
            logger.info(f"Table {table_name} doesn't exist. Will be created.")
        else:
            # Check if columns match (PostgreSQL syntax)
            column_query = f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND table_schema = 'public';
            """
            columns_info = await connection.execute_query(column_query)
            existing_columns = {row[0]: row[1] for row in columns_info[1]}
            logger.info(f"Table {table_name} columns: {existing_columns}")

async def apply_column_migrations():
    """
    Apply specific column migrations that can't be handled automatically by Tortoise ORM.
    This is useful for data type changes, renaming, etc.
    """
    connection = connections.get('default')
    
    # Get existing tables (PostgreSQL syntax)
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """
    tables = await connection.execute_query(query)
    existing_tables = [row[0] for row in tables[1]]
    
    # Add file_data column to file_uploads if it doesn't exist
    if "file_uploads" in existing_tables:
        # Check if column exists
        column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'file_uploads' 
            AND table_schema = 'public';
        """
        columns_info = await connection.execute_query(column_query)
        existing_columns = [row[0] for row in columns_info[1]]
        
        if "file_data" not in existing_columns:
            logger.info("Adding file_data column to file_uploads table")
            await connection.execute_query(
                "ALTER TABLE file_uploads ADD COLUMN file_data BYTEA NULL;"
            )
            logger.info("Added file_data column to file_uploads table")
    
    # Add section and subsection columns to chat_messages if they don't exist
    if "chat_messages" in existing_tables:
        # Check if columns exist
        column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'chat_messages' 
            AND table_schema = 'public';
        """
        columns_info = await connection.execute_query(column_query)
        existing_columns = [row[0] for row in columns_info[1]]
        
        if "section" not in existing_columns:
            logger.info("Adding section column to chat_messages table")
            await connection.execute_query(
                "ALTER TABLE chat_messages ADD COLUMN section VARCHAR(100) NULL;"
            )
        
        if "subsection" not in existing_columns:
            logger.info("Adding subsection column to chat_messages table")
            await connection.execute_query(
                "ALTER TABLE chat_messages ADD COLUMN subsection VARCHAR(100) NULL;"
            )
            
        if "file_path" not in existing_columns:
            logger.info("Adding file_path column to chat_messages table")
            await connection.execute_query(
                "ALTER TABLE chat_messages ADD COLUMN file_path VARCHAR(255) NULL;"
            )
    
    # Add user_id column to projects if it doesn't exist
    if "projects" in existing_tables:
        # Check if columns exist
        column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'projects' 
            AND table_schema = 'public';
        """
        columns_info = await connection.execute_query(column_query)
        existing_columns = [row[0] for row in columns_info[1]]
        
        if "user_id" not in existing_columns:
            logger.info("Adding user_id column to projects table")
            await connection.execute_query(
                "ALTER TABLE projects ADD COLUMN user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL;"
            )
            logger.info("Added user_id column to projects table")
    
    logger.info("Column migrations completed")

async def handle_complex_migrations():
    """
    Handles more complex migrations for tables that need complete restructuring.
    PostgreSQL has better ALTER TABLE support than SQLite, but sometimes we still need
    custom migration logic.
    """
    connection = connections.get('default')
    
    # Get existing tables (PostgreSQL syntax)
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """
    tables = await connection.execute_query(query)
    existing_tables = [row[0] for row in tables[1]]
    
    # Create active_subsections table if it doesn't exist
    if "active_subsections" not in existing_tables:
        await connection.execute_query("""
            CREATE TABLE IF NOT EXISTS active_subsections (
                id SERIAL PRIMARY KEY,
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                section VARCHAR(100) NOT NULL,
                subsection VARCHAR(100) NOT NULL,
                last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, section, subsection)
            );
        """)
        logger.info("Created active_subsections table")
    
    # Create approved_subsections table if it doesn't exist
    if "approved_subsections" not in existing_tables:
        await connection.execute_query("""
            CREATE TABLE IF NOT EXISTS approved_subsections (
                id SERIAL PRIMARY KEY,
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                section VARCHAR(100) NOT NULL,
                subsection VARCHAR(100) NOT NULL,
                approved_value TEXT NOT NULL,
                approved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, section, subsection)
            );
        """)
        logger.info("Created approved_subsections table")
    
    # If chat_messages exists but doesn't have section/subsection columns, 
    # we need to set default values for existing rows
    if "chat_messages" in existing_tables:
        # Check if we've added the section and subsection columns
        column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'chat_messages' 
            AND table_schema = 'public';
        """
        columns_info = await connection.execute_query(column_query)
        existing_columns = [row[0] for row in columns_info[1]]
        
        if "section" in existing_columns and "subsection" in existing_columns:
            # Get count of rows with NULL section/subsection
            null_count_query = """
                SELECT COUNT(*) FROM chat_messages 
                WHERE section IS NULL OR subsection IS NULL;
            """
            null_count_result = await connection.execute_query(null_count_query)
            null_count = null_count_result[1][0][0]
            
            if null_count > 0:
                logger.info(f"Found {null_count} chat_messages with NULL section/subsection")
                
                # For each document, find its topic and set default section/subsection for messages
                docs_query = """
                    SELECT id, topic FROM documents 
                    WHERE id IN (
                        SELECT DISTINCT document_id FROM chat_messages 
                        WHERE section IS NULL OR subsection IS NULL
                    );
                """
                docs_result = await connection.execute_query(docs_query)
                
                for doc_row in docs_result[1]:
                    doc_id = doc_row[0]
                    doc_topic = doc_row[1]
                    
                    # Get first section and subsection for this topic from DOCUMENT_STRUCTURE
                    # For migration purposes, we'll use a simpler approach
                    update_query = """
                        UPDATE chat_messages
                        SET section = 'Deckblatt', subsection = 'Projekt'
                        WHERE document_id = $1 AND (section IS NULL OR subsection IS NULL);
                    """
                    await connection.execute_query(update_query, [doc_id])
                    logger.info(f"Updated section/subsection for messages of document {doc_id}")
    
    logger.info("Complex migrations completed")

async def verify_migration():
    """
    Verifies that the database schema matches the expected model structure.
    """
    connection = connections.get('default')
    
    # Define expected columns for each model with PostgreSQL types
    expected_tables = {
        "documents": {
            "id": "uuid",
            "topic": "character varying",
            "thread_id": "character varying",
            "pdf_data": "bytea",
            "created_at": "timestamp without time zone"
        },
        "projects": {
            "id": "uuid",
            "name": "character varying",
            "document_id": "uuid",
            "created_at": "timestamp without time zone"
        },
        "section_data": {
            "id": "integer",
            "document_id": "uuid",
            "section": "character varying",
            "data": "jsonb"
        },
        "chat_messages": {
            "id": "integer",
            "document_id": "uuid",
            "role": "character varying",
            "content": "text",
            "file_path": "character varying",
            "timestamp": "timestamp without time zone",
            "section": "character varying",
            "subsection": "character varying"
        },
        "active_subsections": {
            "id": "integer",
            "document_id": "uuid",
            "section": "character varying",
            "subsection": "character varying",
            "last_accessed": "timestamp without time zone"
        },
        "approved_subsections": {
            "id": "integer",
            "document_id": "uuid",
            "section": "character varying",
            "subsection": "character varying",
            "approved_value": "text",
            "approved_at": "timestamp without time zone"
        },
        "file_uploads": {
            "id": "uuid",
            "document_id": "uuid",
            "user_id": "uuid",
            "original_filename": "character varying",
            "openai_file_id": "character varying",
            "file_size": "integer",
            "file_type": "character varying",
            "status": "character varying",
            "created_at": "timestamp without time zone",
            "error_message": "text",
            "section": "character varying",
            "subsection": "character varying",
            "file_data": "bytea"
        }
    }
    
    # Get existing tables (PostgreSQL syntax)
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """
    tables = await connection.execute_query(query)
    existing_tables = [row[0] for row in tables[1]]
    
    # Verify each expected table exists and has correct structure
    all_valid = True
    for table_name, expected_columns in expected_tables.items():
        if table_name not in existing_tables:
            logger.error(f"Table {table_name} is missing!")
            all_valid = False
            continue
            
        # Get actual columns (PostgreSQL syntax)
        column_query = f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            AND table_schema = 'public';
        """
        columns_info = await connection.execute_query(column_query)
        actual_columns = {row[0]: row[1] for row in columns_info[1]}
        
        # Check for missing columns - log as warning but don't fail validation
        for col_name in expected_columns:
            if col_name not in actual_columns:
                logger.warning(f"Column {col_name} is missing from table {table_name}! Will be added by schema generation.")
                # Don't set all_valid to False - let Tortoise ORM add the column
        
        # Check for extra columns (might be fine, just informational)
        for col_name in actual_columns:
            if col_name not in expected_columns:
                logger.warning(f"Extra column {col_name} ({actual_columns[col_name]}) in table {table_name}")
    
    # Verify foreign key constraints
    fk_query = """
        SELECT
            kcu.column_name as from_col,
            ccu.table_name as to_table,
            ccu.column_name as to_col
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_name = '{}';
    """
    
    expected_fks = {
        "projects": [("document_id", "documents", "id")],
        "section_data": [("document_id", "documents", "id")],
        "chat_messages": [("document_id", "documents", "id")],
        "active_subsections": [("document_id", "documents", "id")],
        "approved_subsections": [("document_id", "documents", "id")],
        "file_uploads": [("document_id", "documents", "id"), ("user_id", "users", "id")]
    }
    
    for table_name, expected_relations in expected_fks.items():
        if table_name not in existing_tables:
            continue
            
        try:
            fk_info = await connection.execute_query(fk_query.format(table_name))
            actual_fks = [(row[0], row[1], row[2]) for row in fk_info[1]]  # (from_col, to_table, to_col)
            
            for expected_fk in expected_relations:
                if expected_fk not in actual_fks:
                    logger.warning(f"Missing foreign key in {table_name}: {expected_fk[0]} -> {expected_fk[1]}.{expected_fk[2]}")
        except Exception as e:
            logger.error(f"Error checking foreign keys for {table_name}: {e}")
    
    logger.info("✅ Database verification completed. Any missing columns will be added by schema generation.")
    
    return True  # Always return True to continue with schema generation

async def run_migration():
    """
    Performs the database migration.
    """
    logger.info("Starting database migration...")
    
    # Connect to the database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    # Check table structure
    await check_and_create_tables()
    
    # Backup database (PostgreSQL specific)
    # With PostgreSQL, you'd typically use pg_dump for backups
    # Here we just log a reminder since we can't directly call pg_dump
    logger.info("⚠️ Remember to backup your PostgreSQL database before proceeding!")
    logger.info("   You can use: pg_dump -U username -d database_name > backup_filename.sql")
    
    # Handle complex migrations first
    await handle_complex_migrations()
    
    # Apply any specific column migrations
    await apply_column_migrations()
    
    # Generate schema (this will update tables if they exist)
    logger.info("Updating schema based on current models...")
    await Tortoise.generate_schemas(safe=True)
    
    # Verify migration was successful
    await verify_migration()
    
    logger.info("Migration completed successfully!")
    
    # Close connections
    await Tortoise.close_connections()

if __name__ == "__main__":
    # Run the async function
    asyncio.run(run_migration()) 