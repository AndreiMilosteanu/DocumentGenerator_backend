import asyncio
import typer
from aerich import Command
from db_config import TORTOISE_ORM

app = typer.Typer()
command = Command(tortoise_config=TORTOISE_ORM)

@app.command()
def init():
    """Initialize Aerich for migrations"""
    print("Initializing Aerich...")
    asyncio.run(command.init())
    
@app.command()
def init_db(safe: bool = True):
    """Initialize the database with initial migration"""
    print("Initializing database...")
    asyncio.run(command.init_db(safe))
    
@app.command()
def migrate(name: str = "update"):
    """Create a new migration"""
    print(f"Creating migration '{name}'...")
    asyncio.run(command.migrate(name))
    
@app.command()
def upgrade():
    """Apply all pending migrations"""
    print("Applying pending migrations...")
    asyncio.run(command.upgrade(run_in_transaction=True))
    
@app.command()
def downgrade(version: str = None):
    """Downgrade to a specific version"""
    if version:
        print(f"Downgrading to version {version}...")
        asyncio.run(command.downgrade(version))
    else:
        print("Downgrading to previous version...")
        asyncio.run(command.downgrade())
    
@app.command()
def history():
    """Show migration history"""
    print("Migration history:")
    asyncio.run(command.history())
    
@app.command()
def heads():
    """Show current migration heads"""
    print("Current migration heads:")
    asyncio.run(command.heads())

if __name__ == "__main__":
    app() 