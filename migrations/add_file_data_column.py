"""
Migration to add the file_data field to the FileUpload model.
Specific to PostgreSQL database.
"""

from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient) -> str:
    """
    Add the file_data BinaryField to the FileUpload model.
    """
    # PostgreSQL-specific migration
    await db.execute_script("""
    ALTER TABLE "file_uploads" 
    ADD COLUMN IF NOT EXISTS "file_data" BYTEA;
    """)
    
    return "Added file_data field to FileUpload model"


async def downgrade(db: BaseDBAsyncClient) -> str:
    """
    Remove the file_data field from the FileUpload model.
    """
    # PostgreSQL-specific migration
    await db.execute_script("""
    ALTER TABLE "file_uploads" 
    DROP COLUMN IF EXISTS "file_data";
    """)
    
    return "Removed file_data field from FileUpload model" 