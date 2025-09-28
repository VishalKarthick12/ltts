#!/usr/bin/env python3
"""
Fix analytics function for type compatibility
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

FIX_FUNCTION_SQL = """
-- Drop and recreate the analytics function with proper type casting
DROP FUNCTION IF EXISTS update_test_analytics() CASCADE;

CREATE OR REPLACE FUNCTION update_test_analytics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO test_analytics (test_id, total_submissions, total_participants, average_score, pass_rate, average_time_minutes)
    SELECT 
        NEW.test_id,
        COUNT(*),
        COUNT(DISTINCT COALESCE(user_id::text, participant_email)),
        AVG(score),
        AVG(CASE WHEN is_passed THEN 1.0 ELSE 0.0 END) * 100,
        AVG(time_taken_minutes)
    FROM test_submissions 
    WHERE test_id = NEW.test_id
    ON CONFLICT (test_id) 
    DO UPDATE SET
        total_submissions = EXCLUDED.total_submissions,
        total_participants = EXCLUDED.total_participants,
        average_score = EXCLUDED.average_score,
        pass_rate = EXCLUDED.pass_rate,
        average_time_minutes = EXCLUDED.average_time_minutes,
        last_updated = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate the trigger
DROP TRIGGER IF EXISTS update_analytics_after_submission ON test_submissions;
CREATE TRIGGER update_analytics_after_submission
    AFTER INSERT OR UPDATE ON test_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_test_analytics();
"""

async def fix_function():
    database_url = os.getenv("DATABASE_URL")
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("🔧 Fixing analytics function...")
        await conn.execute(FIX_FUNCTION_SQL)
        print("✅ Analytics function fixed!")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(fix_function())

