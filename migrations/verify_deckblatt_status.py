#!/usr/bin/env python3
"""
Verification script to check the status of Deckblatt sections in the database.
This script can be run before and after the migration to verify the changes.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to import project modules
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import from the main models module (not the migrations/models)
try:
    from models import SectionData, Document, ApprovedSubsection
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this script from the project root directory")
    print("Current working directory:", os.getcwd())
    print("Script location:", Path(__file__).parent.parent)
    sys.exit(1)

from tortoise import Tortoise
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_deckblatt_status():
    """Check the current status of Deckblatt sections across all documents"""
    
    # Initialize Tortoise
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"models": ["models"]}
    )
    
    try:
        logger.info("Checking Deckblatt section status...")
        
        # Get all documents by topic
        all_docs = await Document.all()
        docs_by_topic = {}
        for doc in all_docs:
            if doc.topic not in docs_by_topic:
                docs_by_topic[doc.topic] = []
            docs_by_topic[doc.topic].append(doc)
        
        logger.info(f"Found documents across {len(docs_by_topic)} topics:")
        for topic, docs in docs_by_topic.items():
            logger.info(f"  {topic}: {len(docs)} documents")
        
        # Check Deckblatt sections by topic
        all_deckblatt_sections = await SectionData.filter(section="Deckblatt").all()
        all_deckblatt_approved = await ApprovedSubsection.filter(section="Deckblatt").all()
        
        logger.info(f"\nFound {len(all_deckblatt_sections)} total Deckblatt sections")
        logger.info(f"Found {len(all_deckblatt_approved)} total approved Deckblatt subsections")
        
        # Group by topic
        sections_by_topic = {}
        approved_by_topic = {}
        
        for section in all_deckblatt_sections:
            doc = await section.document
            topic = doc.topic
            if topic not in sections_by_topic:
                sections_by_topic[topic] = []
            sections_by_topic[topic].append((doc.id, section.data))
        
        for approved in all_deckblatt_approved:
            doc = await approved.document
            topic = doc.topic
            if topic not in approved_by_topic:
                approved_by_topic[topic] = []
            approved_by_topic[topic].append((doc.id, approved.subsection, approved.approved_value))
        
        # Report by topic
        logger.info("\n" + "="*60)
        logger.info("DECKBLATT SECTIONS BY TOPIC")
        logger.info("="*60)
        
        for topic in sorted(set(list(sections_by_topic.keys()) + list(approved_by_topic.keys()))):
            sections = sections_by_topic.get(topic, [])
            approved = approved_by_topic.get(topic, [])
            
            logger.info(f"\n{topic}:")
            logger.info(f"  Deckblatt sections: {len(sections)}")
            logger.info(f"  Approved subsections: {len(approved)}")
            
            if sections:
                logger.info("  Documents with Deckblatt sections:")
                for doc_id, data in sections[:5]:  # Show first 5
                    data_preview = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                    logger.info(f"    {doc_id}: {data_preview}")
                if len(sections) > 5:
                    logger.info(f"    ... and {len(sections) - 5} more")
            
            if approved:
                logger.info("  Documents with approved Deckblatt subsections:")
                for doc_id, subsection, value in approved[:3]:  # Show first 3
                    value_preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    logger.info(f"    {doc_id}: {subsection} = {value_preview}")
                if len(approved) > 3:
                    logger.info(f"    ... and {len(approved) - 3} more")
        
        # Special focus on Deklarationsanalyse
        logger.info("\n" + "="*60)
        logger.info("DEKLARATIONSANALYSE SPECIFIC CHECK")
        logger.info("="*60)
        
        deklarationsanalyse_docs = await Document.filter(topic='Deklarationsanalyse').all()
        deklarationsanalyse_deckblatt = []
        deklarationsanalyse_approved = []
        
        for doc in deklarationsanalyse_docs:
            sections = await SectionData.filter(document=doc, section="Deckblatt").all()
            approved = await ApprovedSubsection.filter(document=doc, section="Deckblatt").all()
            
            if sections:
                deklarationsanalyse_deckblatt.extend([(doc.id, s.data) for s in sections])
            if approved:
                deklarationsanalyse_approved.extend([(doc.id, a.subsection, a.approved_value) for a in approved])
        
        logger.info(f"Deklarationsanalyse documents: {len(deklarationsanalyse_docs)}")
        logger.info(f"Deklarationsanalyse with Deckblatt sections: {len(deklarationsanalyse_deckblatt)}")
        logger.info(f"Deklarationsanalyse with approved Deckblatt: {len(deklarationsanalyse_approved)}")
        
        if deklarationsanalyse_deckblatt:
            logger.info("\nDeklarationsanalyse documents that still have Deckblatt sections:")
            for doc_id, data in deklarationsanalyse_deckblatt:
                logger.info(f"  {doc_id}: {str(data)[:100]}...")
        else:
            logger.info("\n✅ No Deckblatt sections found in Deklarationsanalyse documents")
        
        if deklarationsanalyse_approved:
            logger.info("\nDeklarationsanalyse documents that still have approved Deckblatt subsections:")
            for doc_id, subsection, value in deklarationsanalyse_approved:
                logger.info(f"  {doc_id}: {subsection}")
        else:
            logger.info("\n✅ No approved Deckblatt subsections found in Deklarationsanalyse documents")
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Deckblatt sections: {len(all_deckblatt_sections)}")
        logger.info(f"Total approved Deckblatt subsections: {len(all_deckblatt_approved)}")
        logger.info(f"Deklarationsanalyse Deckblatt sections: {len(deklarationsanalyse_deckblatt)}")
        logger.info(f"Deklarationsanalyse approved Deckblatt: {len(deklarationsanalyse_approved)}")
        
        migration_needed = len(deklarationsanalyse_deckblatt) > 0 or len(deklarationsanalyse_approved) > 0
        if migration_needed:
            logger.info("\n⚠️  Migration is needed to remove Deckblatt from Deklarationsanalyse")
        else:
            logger.info("\n✅ No migration needed - Deklarationsanalyse documents are clean")
        
        return {
            "total_deckblatt_sections": len(all_deckblatt_sections),
            "total_approved_deckblatt": len(all_deckblatt_approved),
            "deklarationsanalyse_deckblatt": len(deklarationsanalyse_deckblatt),
            "deklarationsanalyse_approved": len(deklarationsanalyse_approved),
            "migration_needed": migration_needed,
            "sections_by_topic": {topic: len(sections) for topic, sections in sections_by_topic.items()},
            "approved_by_topic": {topic: len(approved) for topic, approved in approved_by_topic.items()}
        }
        
    except Exception as e:
        logger.error(f"Error checking Deckblatt status: {str(e)}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    print("Deckblatt Section Status Verification")
    print("="*40)
    print("This script checks the current status of Deckblatt sections in the database.")
    print()
    
    # Run the verification
    result = asyncio.run(check_deckblatt_status())
    
    print(f"\n📊 Status Summary:")
    print(f"   Total Deckblatt sections: {result['total_deckblatt_sections']}")
    print(f"   Total approved Deckblatt: {result['total_approved_deckblatt']}")
    print(f"   Deklarationsanalyse Deckblatt: {result['deklarationsanalyse_deckblatt']}")
    print(f"   Deklarationsanalyse approved: {result['deklarationsanalyse_approved']}")
    
    if result['migration_needed']:
        print(f"\n⚠️  Migration recommended: Run remove_deckblatt_migration.py")
    else:
        print(f"\n✅ No migration needed")
    
    print(f"\nDone!") 