# Database Migration Scripts

This directory contains migration scripts for the DocumentGenerator backend.

## Deckblatt Section Removal Migration

These scripts handle the removal of "Deckblatt" sections from Deklarationsanalyse documents while preserving them in other document types (like Baugrundgutachten).

### Files

1. **`verify_deckblatt_status.py`** - Verification script to check current status
2. **`remove_deckblatt_migration.py`** - Main migration script to remove Deckblatt sections
3. **`README.md`** - This documentation file

### Usage Instructions

#### Step 1: Check Current Status (Before Migration)

First, run the verification script to see the current state of your database:

```bash
python migrations/verify_deckblatt_status.py
```

This will show you:
- How many Deckblatt sections exist across all document types
- Specifically how many exist in Deklarationsanalyse documents
- Whether migration is needed

#### Step 2: Run the Migration

If the verification shows that Deklarationsanalyse documents have Deckblatt sections, run the migration:

```bash
python migrations/remove_deckblatt_migration.py
```

The script will:
- Ask for confirmation before proceeding
- Remove all Deckblatt sections from Deklarationsanalyse documents
- Remove any approved subsections for those Deckblatt sections
- Preserve Deckblatt sections in other document types
- Show a detailed summary of changes made
- Automatically verify the migration was successful

#### Step 3: Verify Migration (After Migration)

Optionally, run the verification script again to confirm the migration worked:

```bash
python migrations/verify_deckblatt_status.py
```

This should show:
- ✅ No Deckblatt sections found in Deklarationsanalyse documents
- ✅ No approved Deckblatt subsections found in Deklarationsanalyse documents
- Deckblatt sections still present in other document types (expected)

### What the Migration Does

**Removes from Deklarationsanalyse documents:**
- All `SectionData` records where `section = "Deckblatt"`
- All `ApprovedSubsection` records where `section = "Deckblatt"`

**Preserves in other document types:**
- Deckblatt sections in Baugrundgutachten documents remain unchanged
- Any other document types with Deckblatt sections remain unchanged

### Safety Features

- **Confirmation prompt**: The migration asks for confirmation before proceeding
- **Automatic verification**: After migration, it automatically verifies the changes
- **Detailed logging**: Shows exactly what was removed
- **Topic-specific**: Only affects Deklarationsanalyse documents
- **Rollback information**: Logs all changes for potential rollback if needed

### Example Output

```
Deckblatt Section Removal Migration
========================================
This will remove all Deckblatt sections from Deklarationsanalyse documents.
Deckblatt sections in other document types (like Baugrundgutachten) will remain unchanged.

Continue with the migration? (y/N): y

INFO:__main__:Starting Deckblatt section removal migration...
INFO:__main__:Found 25 Deklarationsanalyse documents
INFO:__main__:Document abc123: Found 1 Deckblatt sections
INFO:__main__:  Removing Deckblatt section with data: {...}
...

============================================================
MIGRATION SUMMARY
============================================================
Documents processed: 25
Documents affected: 25
Deckblatt sections removed: 25
Approved subsections removed: 9

✅ Migration completed successfully and verified!
```

### Prerequisites

- Python environment with access to the project modules
- Database connection configured in `config.py`
- Tortoise ORM properly set up
- All required dependencies installed

### Troubleshooting

If you encounter issues:

1. **Import errors**: Make sure you're running from the project root directory
2. **Database connection errors**: Verify your `DATABASE_URL` in config
3. **Permission errors**: Ensure the database user has DELETE permissions
4. **Partial migration**: The verification script will show what still needs to be cleaned up

### Recovery

If you need to rollback the migration, you would need to:
1. Restore from a database backup taken before the migration
2. Or manually recreate the Deckblatt sections using the logged data from the migration output

**Important**: Always backup your database before running migrations in production! 