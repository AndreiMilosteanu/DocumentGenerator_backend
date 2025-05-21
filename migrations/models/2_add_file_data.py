from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Add file_data field to file_uploads table
        ALTER TABLE "file_uploads" ADD COLUMN IF NOT EXISTS "file_data" BYTEA;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Remove file_data field from file_uploads table
        ALTER TABLE "file_uploads" DROP COLUMN IF EXISTS "file_data";
    """ 