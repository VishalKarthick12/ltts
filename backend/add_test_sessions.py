#!/usr/bin/env python3
"""
Add test session tracking for better test-taking flow
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

ADD_SESSION_TRACKING = """
-- Add test sessions table for tracking active test attempts
CREATE TABLE IF NOT EXISTS test_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    participant_name VARCHAR(100) NOT NULL,
    participant_email VARCHAR(255),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    current_question INTEGER DEFAULT 1,
    answers_draft JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT
);

-- Indexes for test sessions
CREATE INDEX IF NOT EXISTS idx_test_sessions_test_id ON test_sessions(test_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_user_id ON test_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_token ON test_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_test_sessions_expires_at ON test_sessions(expires_at);

-- Add submission_id to test_sessions for linking
ALTER TABLE test_sessions 
ADD COLUMN IF NOT EXISTS submission_id UUID REFERENCES test_submissions(id) ON DELETE SET NULL;

-- Add session_id to test_submissions for reverse linking
ALTER TABLE test_submissions 
ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES test_sessions(id) ON DELETE SET NULL;

-- Function to cleanup expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    UPDATE test_sessions 
    SET is_active = FALSE 
    WHERE expires_at < NOW() AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Add some useful views for test taking
CREATE OR REPLACE VIEW active_test_sessions AS
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

async def add_session_tracking():
    """Add test session tracking tables"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("📋 Adding test session tracking...")
        await conn.execute(ADD_SESSION_TRACKING)
        print("✅ Test session tracking added successfully")
        
        # Verify new table
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'test_sessions' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        print(f"\n📊 test_sessions table created with {len(columns)} columns:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to add session tracking: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(add_session_tracking())

