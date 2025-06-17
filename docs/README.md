# Document Generator Backend

This application generates specialized documents based on different topics by leveraging OpenAI assistants.

## Environment Variables Setup

Create a `.env` file in the root directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key
ASSISTANT_ID=your_default_assistant_id
DATABASE_URL=postgresql://username:password@hostname:port/database
WKHTMLTOPDF_PATH=/path/to/wkhtmltopdf

# Topic-specific OpenAI Assistants
DEKLARATIONSANALYSE_ASSISTANT_ID=assistant_id_for_deklarationsanalyse
BODENUNTERSUCHUNG_ASSISTANT_ID=assistant_id_for_bodenuntersuchung
BAUGRUNDGUTACHTEN_ASSISTANT_ID=assistant_id_for_baugrundgutachten
PLATTENDRUCKVERSUCH_ASSISTANT_ID=assistant_id_for_plattendruckversuch
```

### Assistant Configuration

1. Create a separate OpenAI assistant for each topic in the OpenAI platform.
2. Configure each assistant with specialized knowledge for its specific topic.
3. Copy each assistant's ID to the corresponding environment variable.
4. The `ASSISTANT_ID` variable serves as a fallback if a topic-specific assistant is not configured.

## Installation and Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the database migration to create the necessary tables:
   ```
   python db_migration.py
   ```

3. Start the application:
   ```
   uvicorn main:app --reload
   ```

## Features

- Automatically selects the appropriate OpenAI assistant based on the document topic
- Generates structured documents following predefined templates
- Stores conversation history and document data in a PostgreSQL database
- Exports documents in PDF format
- Supports subsection-specific conversations within the same context thread
- Subsection approval system for granular control over document content

## API Overview

### Projects

- `GET /projects/list` - List all projects
- `GET /projects/{project_id}` - Get project details with sections and chat history
- `POST /projects/create` - Create a new project and document
- `PUT /projects/{project_id}` - Update project (rename)
- `DELETE /projects/{project_id}` - Delete a project
- `GET /projects/{project_id}/status` - Get project completion status
- `GET /projects/{project_id}/chat-history` - Get project chat history
- `GET /projects/{project_id}/conversation` - Get conversation thread info
- `POST /projects/link-document` - Link existing document to a new project
- `GET /projects/document/{document_id}` - Find project by document ID

### Conversations

- `POST /conversation/{document_id}/start` - Start a conversation for a document
- `POST /conversation/{document_id}/reply` - Reply to the active subsection's conversation
- `GET /conversation/{document_id}/subsections` - List all subsections and their conversation status
- `POST /conversation/{document_id}/select-subsection` - Select a subsection for conversation
- `POST /conversation/{document_id}/subsection/start` - Start or switch to a subsection conversation
- `GET /conversation/{document_id}/messages/{section}/{subsection}` - Get messages for a subsection
- `POST /conversation/{document_id}/extract-and-approve/{section}/{subsection}` - Extract and approve subsection content
- `POST /conversation/{document_id}/approve/{section}/{subsection}` - Approve custom subsection content
- `GET /conversation/{document_id}/debug` - Debug conversation data (development only)
- `GET /conversation/{document_id}/analyze_format` - Analyze message format (development only)

### Document Content & PDF Generation

- `GET /documents/{document_id}/pdf` - Generate and view PDF with approved content
- `GET /documents/{document_id}/download` - Download the PDF with approved content
- `GET /documents/{document_id}/current-data` - Get current section data
- `POST /documents/{document_id}/approve` - Approve a subsection for inclusion in PDF
- `POST /documents/{document_id}/approve-batch` - Approve multiple subsections at once
- `GET /documents/{document_id}/approved` - List all approved subsections

## Project Structure

```
├── config.py              # Configuration and settings
├── main.py                # FastAPI application entry point
├── models.py              # Database models
├── db_migration.py        # Database migration script
├── templates/             # HTML and document structure templates
├── routers/               # API routes
│   ├── conversation.py    # Conversation endpoints
│   ├── pdfgen.py          # PDF generation endpoints
│   └── projects.py        # Project management endpoints
└── services/              # Business logic services
    ├── openai_client.py   # OpenAI API integration
    ├── function_schemas.py # Schema definitions for functions
    └── pdf_renderer.py    # PDF rendering service
```

## Workflow Examples

### Creating a document with subsection-based conversations and approval

1. Create a project: `POST /projects/create`
2. Start a conversation for the first subsection: `POST /conversation/{document_id}/start`
3. Continue the conversation: `POST /conversation/{document_id}/reply`
4. Extract and approve content from current subsection: `POST /conversation/{document_id}/extract-and-approve/{section}/{subsection}`
5. Switch to a different subsection: `POST /conversation/{document_id}/select-subsection`
6. Start conversation for the new subsection: `POST /conversation/{document_id}/subsection/start`
7. Reply in the context of the new subsection: `POST /conversation/{document_id}/reply`
8. Approve content from this subsection: `POST /conversation/{document_id}/extract-and-approve/{section}/{subsection}`
9. Generate PDF with only approved content: `GET /documents/{document_id}/pdf`

### Subsection-Based Conversation Flow

The system uses a single OpenAI thread for the entire document but maintains context for each subsection:

1. Each document has sections (e.g., "Project Details") and subsections (e.g., "Location", "Client")
2. When creating a project, the first subsection is automatically selected
3. The UI allows switching between subsections while maintaining the conversation context
4. When switching to a new subsection, the assistant is informed of the context change
5. All messages are tagged with their section and subsection for proper organization
6. The system tracks which subsection is currently active for each document

### Content Approval Flow

The system allows granular control over what content appears in the generated PDF:

1. As the assistant extracts information during conversations, it's stored in the SectionData model
2. The user can review the extracted content for each subsection
3. The user explicitly approves specific subsection content for inclusion in the PDF
4. Only approved content will appear in the generated PDF document
5. The user can modify content before approval if the assistant's extraction isn't perfect
6. Approved content is stored separately from the conversation data 