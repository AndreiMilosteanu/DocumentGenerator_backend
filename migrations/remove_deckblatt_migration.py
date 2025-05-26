#!/usr/bin/env python3
"""
Migration script to remove Deckblatt sections from Deklarationsanalyse documents.
This script will:
1. Find all Deklarationsanalyse documents with Deckblatt sections
2. Remove the Deckblatt section data
3. Remove any approved subsections for Deckblatt sections
4. Provide a summary of changes made
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to import project modules
sys.path.append(str(Path(__file__).parent.parent))

from models import SectionData, Document, ApprovedSubsection
from tortoise import Tortoise
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def remove_deckblatt_sections():
    """Remove all Deckblatt sections from Deklarationsanalyse documents"""
    
    # Initialize Tortoise
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"models": ["models"]}
    )
    
    try:
        logger.info("Starting Deckblatt section removal migration...")
        
        # Get all Deklarationsanalyse documents
        docs = await Document.filter(topic='Deklarationsanalyse').all()
        logger.info(f"Found {len(docs)} Deklarationsanalyse documents")
        
        deckblatt_sections_removed = 0
        approved_subsections_removed = 0
        documents_affected = []
        
        for doc in docs:
            # Find Deckblatt sections for this document
            deckblatt_sections = await SectionData.filter(document=doc, section="Deckblatt").all()
            
            if deckblatt_sections:
                logger.info(f"Document {doc.id}: Found {len(deckblatt_sections)} Deckblatt sections")
                documents_affected.append(str(doc.id))
                
                # Remove each Deckblatt section
                for section in deckblatt_sections:
                    logger.info(f"  Removing Deckblatt section with data: {section.data}")
                    await section.delete()
                    deckblatt_sections_removed += 1
                
                # Remove any approved subsections for Deckblatt
                approved_deckblatt = await ApprovedSubsection.filter(document=doc, section="Deckblatt").all()
                if approved_deckblatt:
                    logger.info(f"  Found {len(approved_deckblatt)} approved Deckblatt subsections to remove")
                    for approved in approved_deckblatt:
                        logger.info(f"    Removing approved subsection: {approved.subsection}")
                        await approved.delete()
                        approved_subsections_removed += 1
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Documents processed: {len(docs)}")
        logger.info(f"Documents affected: {len(documents_affected)}")
        logger.info(f"Deckblatt sections removed: {deckblatt_sections_removed}")
        logger.info(f"Approved subsections removed: {approved_subsections_removed}")
        
        if documents_affected:
            logger.info(f"\nAffected document IDs:")
            for doc_id in documents_affected:
                logger.info(f"  - {doc_id}")
        
        logger.info("\nMigration completed successfully!")
        
        return {
            "documents_processed": len(docs),
            "documents_affected": len(documents_affected),
            "sections_removed": deckblatt_sections_removed,
            "approved_subsections_removed": approved_subsections_removed,
            "affected_document_ids": documents_affected
        }
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise
    finally:
        await Tortoise.close_connections()

async def verify_removal():
    """Verify that all Deckblatt sections have been removed"""
    
    # Initialize Tortoise
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"models": ["models"]}
    )
    
    try:
        logger.info("Verifying Deckblatt section removal...")
        
        # Check for any remaining Deckblatt sections in Deklarationsanalyse documents
        deklarationsanalyse_docs = await Document.filter(topic='Deklarationsanalyse').all()
        remaining_sections = []
        remaining_approved = []
        
        for doc in deklarationsanalyse_docs:
            sections = await SectionData.filter(document=doc, section="Deckblatt").all()
            approved = await ApprovedSubsection.filter(document=doc, section="Deckblatt").all()
            
            remaining_sections.extend(sections)
            remaining_approved.extend(approved)
        
        if remaining_sections:
            logger.warning(f"WARNING: Found {len(remaining_sections)} remaining Deckblatt sections in Deklarationsanalyse documents!")
            for section in remaining_sections:
                doc = await section.document
                logger.warning(f"  Document {doc.id} ({doc.topic}): {section.section}")
        else:
            logger.info("✅ No remaining Deckblatt sections found in Deklarationsanalyse documents")
        
        if remaining_approved:
            logger.warning(f"WARNING: Found {len(remaining_approved)} remaining approved Deckblatt subsections in Deklarationsanalyse documents!")
            for approved in remaining_approved:
                doc = await approved.document
                logger.warning(f"  Document {doc.id} ({doc.topic}): {approved.section}.{approved.subsection}")
        else:
            logger.info("✅ No remaining approved Deckblatt subsections found in Deklarationsanalyse documents")
        
        # Also check for any Deckblatt sections in other document types (should remain)
        all_deckblatt_sections = await SectionData.filter(section="Deckblatt").all()
        other_doc_deckblatt = []
        
        for section in all_deckblatt_sections:
            doc = await section.document
            if doc.topic != 'Deklarationsanalyse':
                other_doc_deckblatt.append((doc.topic, doc.id))
        
        if other_doc_deckblatt:
            logger.info(f"Found {len(other_doc_deckblatt)} Deckblatt sections in other document types (this is expected):")
            topic_counts = {}
            for topic, doc_id in other_doc_deckblatt:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            for topic, count in topic_counts.items():
                logger.info(f"  {topic}: {count} documents")
        
        return len(remaining_sections) == 0 and len(remaining_approved) == 0
        
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    print("Deckblatt Section Removal Migration")
    print("="*40)
    print("This will remove all Deckblatt sections from Deklarationsanalyse documents.")
    print("Deckblatt sections in other document types (like Baugrundgutachten) will remain unchanged.")
    print()
    
    # Ask for confirmation
    response = input("Continue with the migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        exit(0)
    
    # Run the migration
    result = asyncio.run(remove_deckblatt_sections())
    
    # Verify the removal
    print("\nVerifying removal...")
    verification_passed = asyncio.run(verify_removal())
    
    if verification_passed:
        print("\n✅ Migration completed successfully and verified!")
    else:
        print("\n❌ Migration completed but verification found issues. Please check the logs.") 