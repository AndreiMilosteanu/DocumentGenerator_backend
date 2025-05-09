import asyncio
from tortoise import Tortoise
from config import settings

async def generate_schema():
    # Initialize Tortoise
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={'models': ['models']}
    )
    
    # Generate schema
    print("Generating schema...")
    await Tortoise.generate_schemas()
    print("Schema generation completed!")
    
    # Close connections
    await Tortoise.close_connections()

if __name__ == "__main__":
    # Run the async function
    asyncio.run(generate_schema()) 