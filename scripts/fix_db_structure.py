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

async def check_deklarationsanalyse_structure():
    """
    Check the current structure of Deklarationsanalyse documents.
    Note: Deckblatt sections have been removed from Deklarationsanalyse as of the latest migration.
    """
    # Get all documents with topic Deklarationsanalyse
    docs = await Document.filter(topic="Deklarationsanalyse").all()
    logger.info(f"Found {len(docs)} Deklarationsanalyse documents")
    
    # Expected sections for Deklarationsanalyse (after Deckblatt removal)
    expected_sections = ["Stellungnahme", "Anhänge"]
    
    for doc in docs:
        # Get all section data for this document
        sections = await SectionData.filter(document=doc).all()
        section_names = [s.section for s in sections]
        
        logger.info(f"Document {doc.id}: sections = {section_names}")
        
        # Check for any unexpected Deckblatt sections (should not exist)
        if "Deckblatt" in section_names:
            logger.warning(f"WARNING: Document {doc.id} still has a Deckblatt section! This should have been removed.")
        
        # Check for expected sections
        for expected in expected_sections:
            if expected in section_names:
                section_data = await SectionData.filter(document=doc, section=expected).first()
                if section_data and section_data.data:
                    logger.info(f"  {expected}: {len(section_data.data)} subsections")
                else:
                    logger.info(f"  {expected}: empty or no data")
            else:
                logger.info(f"  {expected}: missing")

async def show_document_structure():
    """
    Show the current document structure for Deklarationsanalyse
    """
    logger.info("Current DOCUMENT_STRUCTURE for Deklarationsanalyse:")
    if "Deklarationsanalyse" in DOCUMENT_STRUCTURE:
        structure = DOCUMENT_STRUCTURE["Deklarationsanalyse"]
        logger.info(json.dumps(structure, indent=2))
    else:
        logger.warning("Deklarationsanalyse not found in DOCUMENT_STRUCTURE")

async def main():
    await init_db()
    
    try:
        # Show the current document structure
        await show_document_structure()
        
        # Check the current state of documents
        logger.info("\nChecking current document structure:")
        await check_deklarationsanalyse_structure()
        
        logger.info("\nNote: Deckblatt sections have been removed from Deklarationsanalyse documents.")
        logger.info("The current structure should only contain 'Stellungnahme' and 'Anhänge' sections.")
        
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 