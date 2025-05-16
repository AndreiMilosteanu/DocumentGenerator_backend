#!/usr/bin/env python
import sys
import os
import logging
import json
from pathlib import Path

# Add the parent directory to the Python path to import project modules
sys.path.append(str(Path(__file__).parent.parent))

from tortoise import Tortoise
from config import settings
from models import Document, SectionData
from templates.structure import DOCUMENT_STRUCTURE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_db_structure")

async def init_db():
    """Initialize database connection"""
    logger.info("Connecting to database...")
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )

async def fix_invalid_structure():
    """
    Find and fix invalid structure in section_data records for Deklarationsanalyse documents.
    Specifically fixing incorrect structure in "Deckblatt" section.
    """
    # Get all documents with topic Deklarationsanalyse
    docs = await Document.filter(topic="Deklarationsanalyse").all()
    logger.info(f"Found {len(docs)} Deklarationsanalyse documents")
    
    fixed_count = 0
    
    for doc in docs:
        # Get section data for this document
        section_data = await SectionData.filter(document=doc, section="Deckblatt").first()
        
        if not section_data:
            logger.warning(f"Document {doc.id} has no Deckblatt section data")
            continue
        
        data = section_data.data
        modified = False
        
        # Check and fix the Projekt field
        if "Projekt" in data and isinstance(data["Projekt"], dict):
            if data["Projekt"] and "Name" in data["Projekt"]:
                # Fix nested structure: {"Projekt": {"Name": "Value"}} -> {"Projekt": "Value"}
                data["Projekt"] = data["Projekt"]["Name"]
                logger.info(f"Fixed Projekt field for document {doc.id}")
                modified = True
            elif not data["Projekt"]:
                # Empty dict -> empty string
                data["Projekt"] = ""
                logger.info(f"Fixed empty Projekt dict for document {doc.id}")
                modified = True
        
        # Check and fix the Auftraggeber field
        if "Auftraggeber" in data and isinstance(data["Auftraggeber"], dict):
            if data["Auftraggeber"] and "Name" in data["Auftraggeber"]:
                # Fix nested structure: {"Auftraggeber": {"Name": "Value"}} -> {"Auftraggeber": "Value"}
                data["Auftraggeber"] = data["Auftraggeber"]["Name"]
                logger.info(f"Fixed Auftraggeber field for document {doc.id}")
                modified = True
            elif not data["Auftraggeber"]:
                # Empty dict -> empty string
                data["Auftraggeber"] = ""
                logger.info(f"Fixed empty Auftraggeber dict for document {doc.id}")
                modified = True
        
        # Check and fix the Dienstleistungsnummer field
        if "Dienstleistungsnummer" in data and isinstance(data["Dienstleistungsnummer"], dict):
            if data["Dienstleistungsnummer"] and "Name" in data["Dienstleistungsnummer"]:
                data["Dienstleistungsnummer"] = data["Dienstleistungsnummer"]["Name"]
                logger.info(f"Fixed Dienstleistungsnummer field for document {doc.id}")
                modified = True
            elif not data["Dienstleistungsnummer"]:
                data["Dienstleistungsnummer"] = ""
                logger.info(f"Fixed empty Dienstleistungsnummer dict for document {doc.id}")
                modified = True
        
        # Check and fix the Probenahmedatum field
        if "Probenahmedatum" in data and isinstance(data["Probenahmedatum"], dict):
            if data["Probenahmedatum"] and "Name" in data["Probenahmedatum"]:
                data["Probenahmedatum"] = data["Probenahmedatum"]["Name"]
                logger.info(f"Fixed Probenahmedatum field for document {doc.id}")
                modified = True
            elif not data["Probenahmedatum"]:
                data["Probenahmedatum"] = ""
                logger.info(f"Fixed empty Probenahmedatum dict for document {doc.id}")
                modified = True
        
        # Save if modified
        if modified:
            logger.info(f"Saving fixed data for document {doc.id}: {json.dumps(data, indent=2)}")
            section_data.data = data
            await section_data.save()
            fixed_count += 1
        else:
            logger.info(f"No invalid structure found for document {doc.id}")
    
    logger.info(f"Fixed structure for {fixed_count} documents")
    return fixed_count

async def show_section_data():
    """
    Show the structure of Deckblatt section data for all Deklarationsanalyse documents
    """
    docs = await Document.filter(topic="Deklarationsanalyse").all()
    
    for doc in docs:
        section_data = await SectionData.filter(document=doc, section="Deckblatt").first()
        
        if section_data:
            logger.info(f"Document {doc.id} Deckblatt data: {json.dumps(section_data.data, indent=2)}")
        else:
            logger.info(f"Document {doc.id} has no Deckblatt section data")

async def main():
    await init_db()
    
    try:
        # First show the current state
        logger.info("Current section data structure:")
        await show_section_data()
        
        # Fix invalid structure
        fixed_count = await fix_invalid_structure()
        
        if fixed_count > 0:
            # Show the fixed state
            logger.info("Section data structure after fixes:")
            await show_section_data()
        
        logger.info("Done!")
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 