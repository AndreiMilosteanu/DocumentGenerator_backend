# Database Migrations with Aerich

This project uses Aerich for database migrations with Tortoise ORM.

## Setup

Make sure you have all required dependencies installed:

```bash
pip install -r requirements.txt
```

## Migration Commands

All migration commands are accessible through the `migrations.py` script.

### First-time Setup

When setting up Aerich for the first time on a new environment:

```bash
# Initialize Aerich (creates migration configuration files)
python migrations.py init

# Create initial migration and apply it
python migrations.py init-db
```

### Daily Usage

#### Creating a New Migration

After making changes to your models, create a new migration:

```bash
python migrations.py migrate "add_user_field"  # Name is optional
```

#### Applying Migrations

Apply all pending migrations:

```bash
python migrations.py upgrade
```

#### Other Useful Commands

```bash
# View migration history
python migrations.py history

# View current migration head
python migrations.py heads

# Downgrade to previous migration
python migrations.py downgrade
```

### Deployment Workflow

When deploying to a Digital Ocean droplet:

1. Pull the latest code
2. Install dependencies: `pip install -r requirements.txt`
3. Apply pending migrations: `python migrations.py upgrade`
4. Restart the application

## Migration File Structure

Migrations are stored in the `./migrations` directory. Each migration includes:

- Upgrade operations: Applied when upgrading to this version
- Downgrade operations: Applied when downgrading from this version

## Migrating from the Old System to Aerich

If you're transitioning from the previous custom migration system to Aerich, follow these steps:

1. First, run the transition script to ensure your database is in a consistent state:

```bash
python scripts/migrate_to_aerich.py
```

2. Initialize Aerich with your current database structure:

```bash
python migrations.py init
python migrations.py init-db
```

3. Test that everything works by making a small change to one of your models and creating a migration:

```bash
python migrations.py migrate "test_migration"
python migrations.py upgrade
```

4. Update any deployment scripts to use the new migration system

## Troubleshooting

- If you encounter issues with migrations, check the migration history with `python migrations.py history`
- When upgrading from the previous custom migration scripts, you may need to manually create the initial migration state

## References

- [Aerich Documentation](https://github.com/tortoise/aerich)
- [Tortoise ORM Documentation](https://tortoise-orm.readthedocs.io/) 