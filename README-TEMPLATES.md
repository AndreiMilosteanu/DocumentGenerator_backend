# Topic-Specific PDF Templates

This document explains how to use and customize the topic-specific PDF templates in the DocumentGenerator system.

## Overview

The system now supports custom PDF templates for each document topic:
- Baugrundgutachten
- Deklarationsanalyse
- Bodenuntersuchung
- Plattendruckversuch

Each topic can have its own custom design for the cover page, table of contents, and content sections.

## Directory Structure

Templates are stored in the following directory structure:
```
templates/
  ├── pdf_templates/
  │   ├── Baugrundgutachten/
  │   │   └── base.html
  │   ├── Deklarationsanalyse/
  │   │   └── base.html
  │   ├── Bodenuntersuchung/
  │   │   └── base.html
  │   └── Plattendruckversuch/
  │       └── base.html
  ├── structure.py
  ├── doc.html (fallback template)
  └── structure_debug.txt
```

## How it Works

1. When a PDF is generated, the system looks for a topic-specific template in the corresponding directory.
2. If a template is found, it is used for rendering; otherwise, the system falls back to the default template (`doc.html`).
3. The templates are Jinja2 HTML templates that are converted to PDF using wkhtmltopdf.

## Template Components

Each template includes:

1. **Cover Page**
   - The first page of the document with the title, project name, and basic metadata
   - Customizable per topic

2. **Table of Contents**
   - Automatically generated based on the document structure
   - Section and subsection numbering

3. **Content Sections**
   - Dynamic rendering of all sections and subsections
   - Content populated from the document data

4. **Footer**
   - Page numbering
   - Document identification

## Automatic PDF Generation

PDFs are automatically generated in the following scenarios:
1. When a file is uploaded through regular file upload
2. When a file is attached to a message in a conversation
3. When document sections are explicitly approved

## Template Customization

To customize the templates:

1. Edit the HTML/CSS in the corresponding `base.html` file
2. Customize the template variables as needed
3. Add custom styling for specific sections or topics

## Available Variables

Templates have access to the following variables:

- `title`: The document topic name
- `project_name`: The name of the project
- `client_name`: The name of the client
- `project_number`: The project number or ID
- `date`: The document date (defaults to current date)
- `author`: The document author
- `structure`: The complete structure of the document (sections and subsections)
- `section_data`: The content of each section and subsection

## Adding New Templates

To add a template for a new topic:

1. Add the new topic and its structure to `templates/structure.py`
2. Create a new directory under `templates/pdf_templates/` with the exact name of the topic
3. Create a `base.html` file in the new directory, using an existing template as a starting point
4. Customize the template as needed 