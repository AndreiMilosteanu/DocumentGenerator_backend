from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cover_page_data" (
            "id" SERIAL NOT NULL PRIMARY KEY,
            "data" JSONB NOT NULL DEFAULT '{}',
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE,
            UNIQUE ("document_id")
        );
        COMMENT ON TABLE "cover_page_data" IS 'Stores cover page data for documents. Each document can have customizable cover page fields.';
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "cover_page_data";
        """ 