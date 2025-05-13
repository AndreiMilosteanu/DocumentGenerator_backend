# Erdbaron Document Generator Backend

A FastAPI backend for AI-guided document creation with document/project management capabilities.

## Features

- AI-assisted document generation with OpenAI's Assistants API
- Document structure templates for various document types
- PDF generation from collected data
- Project management for organizing documents
- Persistent storage of conversations and document data
- RESTful API for frontend integration

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL database
- wkhtmltopdf (for PDF generation)
- OpenAI API key and Assistant ID

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ASSISTANT_ID=your_openai_assistant_id
   DATABASE_URL=postgresql://user:password@localhost:5432/erdbaron
   WKHTMLTOPDF_PATH=/path/to/wkhtmltopdf
   ```
4. Run the schema generation script to create database tables:
   ```
   python generate_schema.py
   ```
5. Start the server:
   ```
   uvicorn main:app --reload
   ```

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
- `POST /conversation/{document_id}/reply` - Reply to a conversation
- `GET /conversation/{document_id}/debug` - Debug conversation data (development only)
- `GET /conversation/{document_id}/analyze_format` - Analyze message format (development only)

### Documents

- `GET /documents/{document_id}/pdf` - Generate and view PDF
- `GET /documents/{document_id}/download` - Download the PDF

## Project Structure

```
├── config.py              # Configuration and settings
├── main.py                # FastAPI application entry point
├── models.py              # Database models
├── generate_schema.py     # Database schema generation
├── templates/             # HTML and document structure templates
├── routers/               # API routes
│   ├── conversation.py    # Conversation endpoints
│   ├── pdfgen.py          # PDF generation endpoints
│   └── projects.py        # Project management endpoints
└── services/              # Business logic services
    ├── openai_client.py   # OpenAI API integration
    └── pdf_renderer.py    # PDF rendering service
```

## Workflow Examples

### Creating a new document

1. Create a project: `POST /projects/create`
2. Start a conversation: `POST /conversation/{document_id}/start`
3. Have conversation: `POST /conversation/{document_id}/reply`
4. Generate PDF: `GET /documents/{document_id}/pdf`

### Working with existing documents

1. List projects: `GET /projects/list`
2. Get project details: `GET /projects/{project_id}`
3. Continue conversation: `POST /conversation/{document_id}/reply`
4. Check status: `GET /projects/{project_id}/status` 