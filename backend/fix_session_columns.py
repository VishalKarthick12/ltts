#!/usr/bin/env python3
"""
Fix missing columns in test_sessions table
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

FIX_COLUMNS_SQL = """
-- Add missing current_question column if it doesn't exist
ALTER TABLE test_sessions 
ADD COLUMN IF NOT EXISTS current_question INTEGER DEFAULT 1;

-- Recreate the active_test_sessions view
DROP VIEW IF EXISTS active_test_sessions;

CREATE VIEW active_test_sessions AS
SELECT 
    ts.*,
    t.title as test_title,
    t.time_limit_minutes,
    t.num_questions,
    u.name as user_name,
    EXTRACT(EPOCH FROM (ts.expires_at - NOW()))/60 as minutes_remaining
FROM test_sessions ts
JOIN tests t ON ts.test_id = t.id
LEFT JOIN users u ON ts.user_id = u.id
WHERE ts.is_active = TRUE AND ts.expires_at > NOW();
"""

async def fix_columns():
    database_url = os.getenv("DATABASE_URL")
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("🔧 Fixing session columns and view...")
        await conn.execute(FIX_COLUMNS_SQL)
        print("✅ Columns and view fixed!")
        
        # Test the view
        active_count = await conn.fetchval("SELECT COUNT(*) FROM active_test_sessions")
        print(f"📊 Active sessions now: {active_count}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(fix_columns())
