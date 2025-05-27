#!/usr/bin/env python3
"""
Performance Optimization Script for Document Generator Backend

This script helps optimize the application for better performance by:
1. Checking current configuration
2. Suggesting optimizations
3. Testing OpenAI API performance
4. Providing recommendations for deployment
"""

import asyncio
import time
import os
import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.openai_client_optimized import get_optimized_client
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("performance_optimizer")

async def test_openai_performance():
    """Test OpenAI API performance with optimizations"""
    print("🚀 Testing OpenAI API Performance")
    print("=" * 50)
    
    client = get_optimized_client()
    
    # Test thread creation speed
    start_time = time.time()
    try:
        thread_id = await client.create_thread_optimized()
        thread_creation_time = time.time() - start_time
        print(f"✓ Thread creation: {thread_creation_time:.2f}s")
    except Exception as e:
        print(f"✗ Thread creation failed: {e}")
        return False
    
    # Test message sending speed
    start_time = time.time()
    try:
        await client.send_message_optimized(thread_id, "Test message for performance testing")
        message_send_time = time.time() - start_time
        print(f"✓ Message sending: {message_send_time:.2f}s")
    except Exception as e:
        print(f"✗ Message sending failed: {e}")
        return False
    
    # Test assistant run speed (this will be the longest)
    print("⏳ Testing assistant run (this may take 10-30 seconds)...")
    start_time = time.time()
    try:
        # Use a simple assistant ID for testing
        assistant_id = (settings.ASSISTANT_ID or 
                       settings.DEKLARATIONSANALYSE_ASSISTANT_ID or
                       list(settings.TOPIC_ASSISTANTS.values())[0])
        
        if not assistant_id:
            print("✗ No assistant ID configured. Please set ASSISTANT_ID in your .env file")
            return False
            
        data, message = await client.run_assistant_optimized(thread_id, assistant_id)
        assistant_run_time = time.time() - start_time
        print(f"✓ Assistant run: {assistant_run_time:.2f}s")
        print(f"  Response length: {len(message)} characters")
        print(f"  Data keys: {len(data)}")
    except Exception as e:
        print(f"✗ Assistant run failed: {e}")
        return False
    
    # Get cache stats
    stats = client.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Valid entries: {stats['valid_entries']}")
    print(f"  Active runs: {stats['active_runs']}")
    
    total_time = thread_creation_time + message_send_time + assistant_run_time
    print(f"\n⏱ Total time: {total_time:.2f}s")
    
    # Performance assessment
    if total_time < 15:
        print("🎉 Excellent performance!")
    elif total_time < 30:
        print("👍 Good performance")
    elif total_time < 60:
        print("⚠ Moderate performance - consider optimizations")
    else:
        print("🐌 Slow performance - optimization needed")
    
    return True

def check_environment_optimizations():
    """Check environment for performance optimizations"""
    print("\n🔧 Environment Optimization Check")
    print("=" * 50)
    
    optimizations = []
    warnings = []
    
    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 9):
        print(f"✓ Python version: {python_version.major}.{python_version.minor}")
    else:
        warnings.append(f"Python {python_version.major}.{python_version.minor} - consider upgrading to 3.9+")
    
    # Check if running in production mode
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    if not debug_mode:
        print("✓ Debug mode: Disabled (good for production)")
    else:
        warnings.append("Debug mode enabled - disable for production")
    
    # Check database configuration
    db_url = settings.DATABASE_URL
    if "sqlite" in db_url.lower():
        warnings.append("Using SQLite - consider PostgreSQL for better performance")
    else:
        print("✓ Database: Non-SQLite (good for performance)")
    
    # Check OpenAI model configuration
    model = settings.GPT_MODEL
    if "gpt-4" in model.lower():
        if "turbo" in model.lower():
            print(f"✓ OpenAI Model: {model} (optimized)")
        else:
            optimizations.append("Consider using gpt-4-turbo for better performance")
    else:
        print(f"✓ OpenAI Model: {model}")
    
    # Check if multiple assistants are configured
    assistant_count = sum(1 for aid in settings.TOPIC_ASSISTANTS.values() if aid)
    if assistant_count > 1:
        print(f"✓ Multiple assistants configured: {assistant_count}")
    else:
        optimizations.append("Configure topic-specific assistants for better performance")
    
    # Environment variables for performance
    performance_vars = {
        'UVICORN_WORKERS': 'Multiple workers for better concurrency',
        'UVICORN_WORKER_CLASS': 'uvicorn.workers.UvicornWorker for async performance',
        'PYTHONUNBUFFERED': '1 for better logging in production'
    }
    
    for var, description in performance_vars.items():
        if os.environ.get(var):
            print(f"✓ {var}: Set")
        else:
            optimizations.append(f"Set {var}: {description}")
    
    # Print recommendations
    if warnings:
        print(f"\n⚠ Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    
    if optimizations:
        print(f"\n💡 Optimization Suggestions ({len(optimizations)}):")
        for opt in optimizations:
            print(f"  - {opt}")
    
    if not warnings and not optimizations:
        print("\n🎉 Environment is well optimized!")

def generate_performance_recommendations():
    """Generate performance recommendations"""
    print("\n📋 Performance Recommendations")
    print("=" * 50)
    
    recommendations = [
        {
            "category": "OpenAI API",
            "items": [
                "Use the optimized client (already implemented)",
                "Configure topic-specific assistants",
                "Monitor cache hit rates",
                "Use faster polling intervals (250ms vs 500ms)"
            ]
        },
        {
            "category": "Database",
            "items": [
                "Use PostgreSQL instead of SQLite for production",
                "Enable connection pooling",
                "Add database indexes for frequently queried fields",
                "Consider read replicas for heavy read workloads"
            ]
        },
        {
            "category": "Application Server",
            "items": [
                "Use multiple Uvicorn workers",
                "Enable async request handling",
                "Configure proper timeout values",
                "Use a reverse proxy (nginx) for static files"
            ]
        },
        {
            "category": "Deployment",
            "items": [
                "Use a CDN for static assets",
                "Enable gzip compression",
                "Configure proper caching headers",
                "Monitor application metrics"
            ]
        },
        {
            "category": "Droplet Specific",
            "items": [
                "Ensure adequate RAM (2GB+ recommended)",
                "Use SSD storage",
                "Configure swap if needed",
                "Monitor CPU and memory usage"
            ]
        }
    ]
    
    for rec in recommendations:
        print(f"\n{rec['category']}:")
        for item in rec['items']:
            print(f"  • {item}")

def create_optimized_env_template():
    """Create an optimized .env template"""
    print("\n📝 Creating Optimized Environment Template")
    print("=" * 50)
    
    template = """# Optimized Environment Configuration for Document Generator Backend

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
GPT_MODEL=gpt-4-turbo  # Faster than regular gpt-4

# Assistant IDs (configure topic-specific assistants for better performance)
ASSISTANT_ID=your_default_assistant_id
DEKLARATIONSANALYSE_ASSISTANT_ID=your_deklarationsanalyse_assistant_id
BODENUNTERSUCHUNG_ASSISTANT_ID=your_bodenuntersuchung_assistant_id
BAUGRUNDGUTACHTEN_ASSISTANT_ID=your_baugrundgutachten_assistant_id
PLATTENDRUCKVERSUCH_ASSISTANT_ID=your_plattendruckversuch_assistant_id

# Database (use PostgreSQL for better performance)
DATABASE_URL=postgresql://user:password@localhost/dbname

# PDF Generation
WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf

# Security
JWT_SECRET_KEY=your_jwt_secret_key_here

# Performance Optimizations
DEBUG=False
PYTHONUNBUFFERED=1

# Server Configuration (for production)
UVICORN_WORKERS=2
UVICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000

# PDF Environment (for droplet)
QT_QPA_PLATFORM=offscreen
DISPLAY=:99
"""
    
    with open('.env.optimized', 'w') as f:
        f.write(template)
    
    print("✓ Created .env.optimized template")
    print("  Review and rename to .env to use these optimizations")

async def main():
    """Main optimization check"""
    print("🔍 Document Generator Performance Optimization")
    print("=" * 60)
    
    # Check environment
    check_environment_optimizations()
    
    # Test OpenAI performance
    try:
        await test_openai_performance()
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        print("   Make sure your OpenAI API key is configured correctly")
    
    # Generate recommendations
    generate_performance_recommendations()
    
    # Create optimized env template
    create_optimized_env_template()
    
    print("\n✅ Performance optimization check complete!")
    print("   Review the recommendations above to improve your application performance.")

if __name__ == "__main__":
    asyncio.run(main()) 