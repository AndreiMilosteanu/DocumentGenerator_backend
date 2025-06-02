#!/usr/bin/env python3
"""
Cleanup script for stuck OpenAI runs

This script can be run periodically (e.g., via cron) to clean up runs that get stuck
and prevent the system from being blocked.

Usage:
    python scripts/cleanup_stuck_runs.py

Environment Variables:
    OPENAI_API_KEY - Required
    MAX_RUN_AGE_SECONDS - Optional, defaults to 300 (5 minutes)
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the parent directory to the Python path to import project modules
sys.path.append(str(Path(__file__).parent.parent))

from services.openai_client_optimized import get_optimized_client
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cleanup_stuck_runs")

async def cleanup_stuck_runs():
    """
    Clean up stuck OpenAI runs across all tracked threads
    """
    try:
        # Get the maximum age for runs (default 5 minutes)
        max_age = int(os.getenv('MAX_RUN_AGE_SECONDS', '300'))
        
        logger.info(f"Starting cleanup of runs older than {max_age} seconds")
        
        # Get the optimized client
        client = get_optimized_client()
        
        # Perform cleanup
        result = await client.cleanup_all_stuck_runs(max_age_seconds=max_age)
        
        # Log results
        logger.info(f"Cleanup completed:")
        logger.info(f"  - Threads checked: {result['threads_checked']}")
        logger.info(f"  - Stuck runs found: {result['stuck_runs_found']}")
        logger.info(f"  - Runs cancelled: {result['runs_cancelled']}")
        
        if result['errors']:
            logger.warning(f"  - Errors encountered: {len(result['errors'])}")
            for error in result['errors']:
                logger.warning(f"    {error}")
        
        # Also get and log current stats
        stats = client.get_cache_stats()
        logger.info(f"Current system stats:")
        logger.info(f"  - Active runs: {stats['active_runs']}")
        logger.info(f"  - Active threads: {stats['active_run_threads']}")
        
        print(f"✅ Cleanup completed successfully. Cancelled {result['runs_cancelled']} stuck runs.")
        return result
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        print(f"❌ Cleanup failed: {str(e)}")
        return None

async def main():
    """
    Main entry point
    """
    if not settings.OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    print("🧹 Starting OpenAI stuck run cleanup...")
    
    result = await cleanup_stuck_runs()
    
    if result is None:
        sys.exit(1)
    
    # Exit with non-zero code if there were errors
    if result['errors']:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 