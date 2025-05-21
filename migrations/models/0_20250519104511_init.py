from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "documents" (
    "id" UUID NOT NULL PRIMARY KEY,
    "topic" VARCHAR(100) NOT NULL,
    "thread_id" VARCHAR(255),
    "pdf_data" BYTEA,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "documents" IS 'Represents a document (topic) and stores metadata and generated PDF bytes.';
CREATE TABLE IF NOT EXISTS "active_subsections" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "section" VARCHAR(100) NOT NULL,
    "subsection" VARCHAR(100) NOT NULL,
    "last_accessed" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_active_subs_documen_54b372" UNIQUE ("document_id", "section", "subsection")
);
COMMENT ON TABLE "active_subsections" IS 'Tracks which subsection is currently active for a document.';
CREATE TABLE IF NOT EXISTS "approved_subsections" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "section" VARCHAR(100) NOT NULL,
    "subsection" VARCHAR(100) NOT NULL,
    "approved_value" TEXT NOT NULL,
    "approved_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_approved_su_documen_c687fd" UNIQUE ("document_id", "section", "subsection")
);
COMMENT ON TABLE "approved_subsections" IS 'Tracks which subsections have been approved by the user for inclusion in the PDF.';
CREATE TABLE IF NOT EXISTS "chat_messages" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "role" VARCHAR(10) NOT NULL,
    "content" TEXT,
    "file_path" VARCHAR(255),
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "section" VARCHAR(100),
    "subsection" VARCHAR(100),
    "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "chat_messages" IS 'Persists chat history messages and file references for a document.';
CREATE TABLE IF NOT EXISTS "section_data" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "section" VARCHAR(100) NOT NULL,
    "data" JSONB NOT NULL,
    "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_section_dat_documen_6fca43" UNIQUE ("document_id", "section")
);
COMMENT ON TABLE "section_data" IS 'Stores structured JSON data for each section of a document.';
CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "password_hash" VARCHAR(255) NOT NULL,
    "role" VARCHAR(5) NOT NULL DEFAULT 'user',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_login" TIMESTAMPTZ,
    "is_active" BOOL NOT NULL DEFAULT True
);
COMMENT ON COLUMN "users"."role" IS 'ADMIN: admin\nUSER: user';
COMMENT ON TABLE "users" IS 'Represents a user in the system.';
CREATE TABLE IF NOT EXISTS "file_uploads" (
    "id" UUID NOT NULL PRIMARY KEY,
    "original_filename" VARCHAR(255) NOT NULL,
    "openai_file_id" VARCHAR(255) NOT NULL,
    "file_size" INT NOT NULL,
    "file_type" VARCHAR(50) NOT NULL,
    "status" VARCHAR(10) NOT NULL DEFAULT 'pending',
    "error_message" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "section" VARCHAR(100),
    "subsection" VARCHAR(100),
    "associated_message_id" INT REFERENCES "chat_messages" ("id") ON DELETE CASCADE,
    "document_id" UUID NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "file_uploads"."status" IS 'PENDING: pending\nPROCESSING: processing\nREADY: ready\nERROR: error';
COMMENT ON TABLE "file_uploads" IS 'Tracks files uploaded to OpenAI and associated with documents/conversations.';
CREATE TABLE IF NOT EXISTS "projects" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID REFERENCES "users" ("id") ON DELETE CASCADE,
    "document_id" UUID NOT NULL UNIQUE REFERENCES "documents" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "projects" IS 'Represents a user project that references a document.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
