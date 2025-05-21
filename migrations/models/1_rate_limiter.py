from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "user_request_limits" (
            "id" SERIAL NOT NULL PRIMARY KEY,
            "daily_request_count" INT NOT NULL DEFAULT 0,
            "last_request_time" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "last_count_reset" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS "idx_user_request_limits_user_id" ON "user_request_limits" ("user_id");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "user_request_limits";
    """ 