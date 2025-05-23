"""
Migration to fix cover page datetime field to allow null values
"""

from tortoise import Tortoise

async def upgrade():
    """
    Update the cover page updated_at field to allow null values
    """
    conn = Tortoise.get_connection("default")
    
    # Alter the updated_at column to allow NULL
    await conn.execute_query("""
        ALTER TABLE cover_page_data 
        ALTER COLUMN updated_at DROP NOT NULL;
    """)
    
    print("✅ Migration 4: Cover page datetime field updated to allow null values")

async def downgrade():
    """
    Revert the cover page updated_at field changes
    """
    conn = Tortoise.get_connection("default")
    
    # Set a default value for any null updated_at fields
    await conn.execute_query("""
        UPDATE cover_page_data 
        SET updated_at = NOW() 
        WHERE updated_at IS NULL;
    """)
    
    # Make the column NOT NULL again
    await conn.execute_query("""
        ALTER TABLE cover_page_data 
        ALTER COLUMN updated_at SET NOT NULL;
    """)
    
    print("✅ Migration 4 downgrade: Cover page datetime field reverted") 