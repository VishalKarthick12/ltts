#!/usr/bin/env python3
"""
Add test sharing functionality with invites and public links
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

ADD_TEST_SHARING = """
-- Test invites table for sharing tests with specific users
CREATE TABLE IF NOT EXISTS test_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invited_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    invited_email VARCHAR(255),
    invite_token VARCHAR(255) UNIQUE NOT NULL,
    invite_type VARCHAR(20) NOT NULL CHECK (invite_type IN ('user', 'email', 'public')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    message TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Public test links table for shareable URLs
CREATE TABLE IF NOT EXISTS test_public_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    link_token VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    max_uses INTEGER, -- NULL = unlimited
    current_uses INTEGER DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Track link usage
CREATE TABLE IF NOT EXISTS test_link_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    link_id UUID NOT NULL REFERENCES test_public_links(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET,
    user_agent TEXT,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_test_invites_test_id ON test_invites(test_id);
CREATE INDEX IF NOT EXISTS idx_test_invites_token ON test_invites(invite_token);
CREATE INDEX IF NOT EXISTS idx_test_invites_invited_user ON test_invites(invited_user_id);
CREATE INDEX IF NOT EXISTS idx_test_invites_email ON test_invites(invited_email);
CREATE INDEX IF NOT EXISTS idx_test_invites_status ON test_invites(status);

CREATE INDEX IF NOT EXISTS idx_test_public_links_test_id ON test_public_links(test_id);
CREATE INDEX IF NOT EXISTS idx_test_public_links_token ON test_public_links(link_token);
CREATE INDEX IF NOT EXISTS idx_test_public_links_active ON test_public_links(is_active);

CREATE INDEX IF NOT EXISTS idx_test_link_usage_link_id ON test_link_usage(link_id);
CREATE INDEX IF NOT EXISTS idx_test_link_usage_user_id ON test_link_usage(user_id);

-- View for shared tests with me
CREATE OR REPLACE VIEW shared_tests_with_me AS
SELECT 
    ti.id as invite_id,
    ti.test_id,
    ti.invite_token,
    ti.status as invite_status,
    ti.message,
    ti.expires_at as invite_expires_at,
    ti.created_at as invited_at,
    t.title,
    t.description,
    t.num_questions,
    t.time_limit_minutes,
    t.pass_threshold,
    t.is_active,
    creator.name as creator_name,
    creator.email as creator_email
FROM test_invites ti
JOIN tests t ON ti.test_id = t.id
JOIN users creator ON ti.created_by = creator.id
WHERE ti.status = 'pending' 
AND (ti.expires_at IS NULL OR ti.expires_at > NOW());

-- Function to update link usage count
CREATE OR REPLACE FUNCTION increment_link_usage()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE test_public_links 
    SET current_uses = current_uses + 1
    WHERE id = NEW.link_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update link usage (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_link_usage_trigger'
    ) THEN
        CREATE TRIGGER update_link_usage_trigger
            AFTER INSERT ON test_link_usage
            FOR EACH ROW
            EXECUTE FUNCTION increment_link_usage();
    END IF;
END;
$$;

-- Ensure invite_token columns exist for linking sessions and submissions to shares
ALTER TABLE IF EXISTS test_sessions 
    ADD COLUMN IF NOT EXISTS invite_token VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_test_sessions_invite_token ON test_sessions(invite_token);

ALTER TABLE IF EXISTS test_submissions 
    ADD COLUMN IF NOT EXISTS invite_token VARCHAR(255);

-- Ensure is_passed exists for analytics and CSV export
ALTER TABLE IF EXISTS test_submissions 
    ADD COLUMN IF NOT EXISTS is_passed BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_test_submissions_invite_token ON test_submissions(invite_token);

-- Analytics summary table (idempotent)
CREATE TABLE IF NOT EXISTS test_analytics (
    test_id UUID PRIMARY KEY REFERENCES tests(id) ON DELETE CASCADE,
    total_submissions INTEGER DEFAULT 0,
    total_participants INTEGER DEFAULT 0,
    average_score NUMERIC DEFAULT 0,
    pass_rate NUMERIC DEFAULT 0,
    average_time_minutes NUMERIC DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed analytics rows for existing tests
INSERT INTO test_analytics (test_id)
SELECT id FROM tests
ON CONFLICT (test_id) DO NOTHING;
"""

async def add_test_sharing():
    """Add test sharing tables and functionality"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("📋 Adding test sharing functionality...")
        await conn.execute(ADD_TEST_SHARING)
        print("✅ Test sharing tables created successfully")
        
        # Verify tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('test_invites', 'test_public_links', 'test_link_usage')
            ORDER BY table_name
        """)
        
        print(f"\n📊 Created sharing tables: {[t['table_name'] for t in tables]}")
        
        # Check view
        view_exists = await conn.fetchval("""
            SELECT EXISTS(SELECT 1 FROM information_schema.views 
                         WHERE table_name = 'shared_tests_with_me' AND table_schema = 'public')
        """)
        
        print(f"📈 Shared tests view created: {view_exists}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to add test sharing: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(add_test_sharing())

