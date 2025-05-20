#!/usr/bin/env python
import asyncio
import logging
import sys
import os
import json
import re

# Add parent directory to sys.path to allow imports from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_dictionary_formats")

from db_config import TORTOISE_ORM
from tortoise import Tortoise
from models import ApprovedSubsection, SectionData, Document

def fix_dict_string(value):
    """Format dictionary string into a readable format"""
    # If it's not a string, return as is
    if not isinstance(value, str):
        return value
        
    # Special case for address format
    if value.startswith("{'Adresse':") or value.startswith("{'Adresse': "):
        try:
            # Extract address value using regex for more robustness
            match = re.search(r"'Adresse':\s*'([^']+)'", value)
            if match:
                address = match.group(1)
                return f"Adresse: {address}"
        except Exception as e:
            logger.warning(f"Failed to parse address format: {str(e)}")
    
    # If it looks like a dictionary string
    if value.startswith("{") and value.endswith("}"):
        try:
            # Try to parse it as a dictionary
            dict_value = eval(value.strip())
            if isinstance(dict_value, dict):
                # Format it nicely
                result = ""
                for k, v in dict_value.items():
                    result += f"{k}: {v}\n"
                return result.strip()
        except Exception as e:
            # Manual parsing as fallback
            try:
                # Remove braces
                content = value.strip("{}").strip()
                # Check for key-value pattern
                if "': '" in content or "':" in content:
                    result = ""
                    parts = content.split("', '")
                    for part in parts:
                        if ": " in part:
                            key, val = part.split(": ", 1)
                            # Clean up quotes
                            key = key.strip("' ")
                            val = val.strip("' ")
                            result += f"{key}: {val}\n"
                    if result:
                        return result.strip()
            except Exception as nested_e:
                logger.warning(f"Failed both parsing methods: {str(e)}, {str(nested_e)}")
    
    # If nothing worked, return original
    return value

async def fix_approved_subsections():
    """Fix formatting in approved subsections"""
    # Get all approved subsections
    approved = await ApprovedSubsection.all()
    count = 0
    
    for item in approved:
        original = item.approved_value
        fixed = fix_dict_string(original)
        
        # If the value changed, update it
        if fixed != original:
            item.approved_value = fixed
            await item.save()
            count += 1
            logger.info(f"Fixed format in approved subsection {item.section}.{item.subsection}")
    
    return count

async def fix_section_data():
    """Fix formatting in section data"""
    # Get all section data records
    sections = await SectionData.all()
    count = 0
    
    for section in sections:
        data = section.data
        modified = False
        
        # Process each subsection
        for subsec, value in data.items():
            fixed = fix_dict_string(value)
            if fixed != value:
                data[subsec] = fixed
                modified = True
                logger.info(f"Fixed format in section data {section.section}.{subsec}")
        
        # If any value was modified, save the changes
        if modified:
            section.data = data
            await section.save()
            count += 1
    
    return count

async def run():
    """Run the fix script"""
    try:
        logger.info("Connecting to database...")
        await Tortoise.init(config=TORTOISE_ORM)
        
        logger.info("Fixing approved subsections...")
        approved_count = await fix_approved_subsections()
        
        logger.info("Fixing section data...")
        section_count = await fix_section_data()
        
        logger.info(f"Fix completed: {approved_count} approved subsections and {section_count} section data records updated")
        
    except Exception as e:
        logger.error(f"Error while fixing dictionary formats: {str(e)}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(run()) 