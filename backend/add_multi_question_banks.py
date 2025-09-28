#!/usr/bin/env python3
"""
Add multi-question bank support by adding tests.question_bank_ids (JSONB) and backfilling existing rows.
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

SQL = """
ALTER TABLE IF EXISTS tests
    ADD COLUMN IF NOT EXISTS question_bank_ids JSONB;

-- Backfill: set question_bank_ids to [question_bank_id] for existing tests
UPDATE tests
SET question_bank_ids = to_jsonb(ARRAY[question_bank_id::text])
WHERE question_bank_ids IS NULL AND question_bank_id IS NOT NULL;
"""

async def migrate():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        print("📋 Applying multi-bank migration...")
        await conn.execute(SQL)
        print("✅ Migration completed (question_bank_ids ready)")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(migrate())
