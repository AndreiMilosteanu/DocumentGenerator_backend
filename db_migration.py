import asyncio
import logging
import json
from tortoise import Tortoise, connections
from config import settings
from models import Document, Project, SectionData, ChatMessage

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
        ("chat_messages", ChatMessage)
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
    
    # Example migrations - uncomment and modify if you need to make specific changes:
    
    # 1. Add a column if it doesn't exist
    # if "documents" in existing_tables:
    #     # Check if pdf_data column exists
    #     column_query = """
    #         SELECT column_name 
    #         FROM information_schema.columns 
    #         WHERE table_name = 'documents' 
    #         AND table_schema = 'public';
    #     """
    #     columns_info = await connection.execute_query(column_query)
    #     existing_columns = [row[0] for row in columns_info[1]]
    #     
    #     if "pdf_data" not in existing_columns:
    #         logger.info("Adding pdf_data column to documents table")
    #         await connection.execute_query(
    #             "ALTER TABLE documents ADD COLUMN pdf_data BYTEA NULL;"
    #         )
    
    # 2. Rename a column (PostgreSQL supports it directly)
    # if "section_data" in existing_tables:
    #     # Check if old column exists and new column doesn't
    #     column_query = """
    #         SELECT column_name 
    #         FROM information_schema.columns 
    #         WHERE table_name = 'section_data' 
    #         AND table_schema = 'public';
    #     """
    #     columns_info = await connection.execute_query(column_query)
    #     existing_columns = [row[0] for row in columns_info[1]]
    #     
    #     if "old_column" in existing_columns and "new_column" not in existing_columns:
    #         logger.info("Renaming old_column to new_column in section_data table")
    #         await connection.execute_query(
    #             "ALTER TABLE section_data RENAME COLUMN old_column TO new_column;"
    #         )
    
    # 3. Change column type (PostgreSQL example)
    # if "section_data" in existing_tables:
    #     # Check if column exists and needs type change
    #     column_query = """
    #         SELECT column_name, data_type
    #         FROM information_schema.columns 
    #         WHERE table_name = 'section_data' 
    #         AND table_schema = 'public';
    #     """
    #     columns_info = await connection.execute_query(column_query)
    #     column_types = {row[0]: row[1] for row in columns_info[1]}
    #     
    #     if "data" in column_types and column_types["data"] != "jsonb":
    #         logger.info("Changing data column type to JSONB in section_data table")
    #         await connection.execute_query(
    #             "ALTER TABLE section_data ALTER COLUMN data TYPE JSONB USING data::JSONB;"
    #         )
    
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
    
    # Check for specific tables that might need complex migrations
    # Example: migrating a table with columns that need to be dropped or restructured
    
    # 1. Example for complex document restructuring (uncomment and modify if needed)
    # if "old_documents" in existing_tables and "documents" not in existing_tables:
    #     logger.info("Performing complex migration for documents table")
    #     
    #     # Step 1: Get current data
    #     old_rows = await connection.execute_query("SELECT * FROM old_documents")
    #     
    #     # Step 2: Create the new table (Tortoise will do this for us)
    #     
    #     # Step 3: Migrate data from old to new
    #     for row in old_rows[1]:
    #         # Adjust indices based on your old table structure
    #         id_val = row[0]
    #         topic_val = row[1]
    #         thread_id_val = row[2] if row[2] else "NULL"
    #         
    #         # Insert into new table with the correct structure
    #         await connection.execute_query(
    #             f"INSERT INTO documents (id, topic, thread_id, created_at) "
    #             f"VALUES ('{id_val}', '{topic_val}', {thread_id_val if thread_id_val != 'NULL' else 'NULL'}, NOW())"
    #         )
    #     
    #     # Step 4: Drop the old table after confirming data migration
    #     old_count = old_rows[0]
    #     new_count = (await connection.execute_query("SELECT COUNT(*) FROM documents"))[1][0][0]
    #     
    #     if new_count >= old_count:
    #         await connection.execute_query("DROP TABLE old_documents")
    #         logger.info(f"Dropped old_documents table after migrating {new_count} rows")
    #     else:
    #         logger.warning(f"Data migration incomplete! Old: {old_count}, New: {new_count}")
    
    # 2. Example for section_data migrations where we need to transform data format
    # if "section_data" in existing_tables:
    #     # Check if structure needs to be updated
    #     column_query = """
    #         SELECT column_name, data_type
    #         FROM information_schema.columns 
    #         WHERE table_name = 'section_data' 
    #         AND table_schema = 'public';
    #     """
    #     columns_info = await connection.execute_query(column_query)
    #     column_types = {row[0]: row[1] for row in columns_info[1]}
    #     
    #     if "data" in column_types and needs_data_format_change():
    #         logger.info("Migrating section_data table data format")
    #         
    #         # Get all rows
    #         rows = await connection.execute_query("SELECT id, document_id, section, data FROM section_data")
    #         
    #         # Process each row to transform data
    #         for row in rows[1]:
    #             row_id = row[0]
    #             old_data = row[3]
    #             
    #             # Transform data format (example: string to JSON)
    #             try:
    #                 if isinstance(old_data, str):
    #                     new_data = json.dumps(json.loads(old_data))
    #                 else:
    #                     new_data = json.dumps(old_data)
    #                     
    #                 # Update with transformed data
    #                 await connection.execute_query(
    #                     f"UPDATE section_data SET data = $1::jsonb WHERE id = $2",
    #                     [new_data, row_id]
    #                 )
    #             except Exception as e:
    #                 logger.error(f"Error transforming data for section_data id {row_id}: {e}")
    
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
            "timestamp": "timestamp without time zone"
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
        
        # Check for missing columns
        for col_name in expected_columns:
            if col_name not in actual_columns:
                logger.error(f"Column {col_name} is missing from table {table_name}!")
                all_valid = False
            # PostgreSQL type names may vary slightly, so we're flexible with exact matches
        
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
        "chat_messages": [("document_id", "documents", "id")]
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
    
    if all_valid:
        logger.info("✅ Database verification successful! Schema matches expected structure.")
    else:
        logger.warning("⚠️ Database verification found issues! Check logs above.")
    
    return all_valid

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