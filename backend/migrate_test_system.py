#!/usr/bin/env python3
"""
Database migration for test management and analytics system
Adds tables for tests, submissions, and analytics while preserving existing data
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg
import sys

load_dotenv()

# SQL for creating test management tables
CREATE_TEST_SYSTEM_TABLES = """
-- Enhanced tests table with more features
DROP TABLE IF EXISTS test_submissions CASCADE;
DROP TABLE IF EXISTS tests CASCADE;

CREATE TABLE tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    question_bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    num_questions INTEGER NOT NULL CHECK (num_questions > 0),
    time_limit_minutes INTEGER CHECK (time_limit_minutes > 0),
    difficulty_filter VARCHAR(20) CHECK (difficulty_filter IN ('easy', 'medium', 'hard')),
    category_filter VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    scheduled_start TIMESTAMP WITH TIME ZONE,
    scheduled_end TIMESTAMP WITH TIME ZONE,
    max_attempts INTEGER DEFAULT 1 CHECK (max_attempts > 0),
    pass_threshold DECIMAL(5,2) DEFAULT 60.0 CHECK (pass_threshold >= 0 AND pass_threshold <= 100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Test submissions with enhanced tracking
CREATE TABLE test_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    participant_name VARCHAR(100) NOT NULL,
    participant_email VARCHAR(255),
    score DECIMAL(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    time_taken_minutes INTEGER,
    answers JSONB NOT NULL, -- Store detailed answers
    ip_address INET,
    user_agent TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_passed BOOLEAN DEFAULT FALSE
);

-- Test questions mapping (for consistent test generation)
CREATE TABLE test_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    question_order INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(test_id, question_id),
    UNIQUE(test_id, question_order)
);

-- Analytics summary table (for performance)
CREATE TABLE test_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    total_submissions INTEGER DEFAULT 0,
    total_participants INTEGER DEFAULT 0,
    average_score DECIMAL(5,2) DEFAULT 0,
    pass_rate DECIMAL(5,2) DEFAULT 0,
    average_time_minutes DECIMAL(8,2) DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(test_id)
);

-- User performance tracking
CREATE TABLE user_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    best_score DECIMAL(5,2) NOT NULL,
    attempts_count INTEGER DEFAULT 1,
    total_time_minutes INTEGER DEFAULT 0,
    first_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, test_id)
);

-- Create indexes for performance
CREATE INDEX idx_tests_question_bank_id ON tests(question_bank_id);
CREATE INDEX idx_tests_created_by ON tests(created_by);
CREATE INDEX idx_tests_is_active ON tests(is_active);
CREATE INDEX idx_tests_scheduled_start ON tests(scheduled_start);
CREATE INDEX idx_tests_scheduled_end ON tests(scheduled_end);

CREATE INDEX idx_test_submissions_test_id ON test_submissions(test_id);
CREATE INDEX idx_test_submissions_user_id ON test_submissions(user_id);
CREATE INDEX idx_test_submissions_submitted_at ON test_submissions(submitted_at);
CREATE INDEX idx_test_submissions_score ON test_submissions(score);

CREATE INDEX idx_test_questions_test_id ON test_questions(test_id);
CREATE INDEX idx_test_questions_question_id ON test_questions(question_id);
CREATE INDEX idx_test_questions_order ON test_questions(test_id, question_order);

CREATE INDEX idx_test_analytics_test_id ON test_analytics(test_id);
CREATE INDEX idx_user_performance_user_id ON user_performance(user_id);
CREATE INDEX idx_user_performance_test_id ON user_performance(test_id);

-- Update triggers for updated_at timestamps
CREATE TRIGGER update_tests_updated_at
    BEFORE UPDATE ON tests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update test analytics
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

-- Trigger to update analytics after each submission
CREATE TRIGGER update_analytics_after_submission
    AFTER INSERT OR UPDATE ON test_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_test_analytics();

-- Function to update user performance
CREATE OR REPLACE FUNCTION update_user_performance()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_performance (user_id, test_id, best_score, attempts_count, total_time_minutes, first_attempt_at, last_attempt_at)
    SELECT 
        NEW.user_id,
        NEW.test_id,
        NEW.score,
        1,
        COALESCE(NEW.time_taken_minutes, 0),
        NEW.submitted_at,
        NEW.submitted_at
    WHERE NEW.user_id IS NOT NULL
    ON CONFLICT (user_id, test_id)
    DO UPDATE SET
        best_score = GREATEST(user_performance.best_score, NEW.score),
        attempts_count = user_performance.attempts_count + 1,
        total_time_minutes = user_performance.total_time_minutes + COALESCE(NEW.time_taken_minutes, 0),
        last_attempt_at = NEW.submitted_at;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update user performance after each submission
CREATE TRIGGER update_user_performance_after_submission
    AFTER INSERT ON test_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_user_performance();

-- Function to update is_passed field
CREATE OR REPLACE FUNCTION update_is_passed()
RETURNS TRIGGER AS $$
BEGIN
    NEW.is_passed := NEW.score >= (
        SELECT pass_threshold FROM tests WHERE id = NEW.test_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update is_passed before insert/update
CREATE TRIGGER update_is_passed_trigger
    BEFORE INSERT OR UPDATE ON test_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_is_passed();
"""

# Views for analytics
CREATE_ANALYTICS_VIEWS = """
-- View for test performance summary
CREATE OR REPLACE VIEW test_performance_summary AS
SELECT 
    t.id as test_id,
    t.title,
    t.created_by,
    u.name as creator_name,
    qb.name as question_bank_name,
    ta.total_submissions,
    ta.total_participants,
    ta.average_score,
    ta.pass_rate,
    ta.average_time_minutes,
    t.created_at,
    ta.last_updated
FROM tests t
LEFT JOIN test_analytics ta ON t.id = ta.test_id
LEFT JOIN users u ON t.created_by = u.id
LEFT JOIN question_banks qb ON t.question_bank_id = qb.id
WHERE t.is_active = true;

-- View for user leaderboard
CREATE OR REPLACE VIEW user_leaderboard AS
SELECT 
    u.id as user_id,
    u.name,
    u.email,
    COUNT(DISTINCT up.test_id) as tests_taken,
    AVG(up.best_score) as average_best_score,
    SUM(up.attempts_count) as total_attempts,
    SUM(up.total_time_minutes) as total_time_minutes,
    COUNT(CASE WHEN ts.is_passed THEN 1 END) as tests_passed
FROM users u
LEFT JOIN user_performance up ON u.id = up.user_id
LEFT JOIN test_submissions ts ON u.id = ts.user_id AND ts.score = up.best_score
GROUP BY u.id, u.name, u.email
HAVING COUNT(DISTINCT up.test_id) > 0
ORDER BY average_best_score DESC;

-- View for recent test activity
CREATE OR REPLACE VIEW recent_test_activity AS
SELECT 
    ts.id,
    ts.test_id,
    t.title as test_title,
    ts.participant_name,
    ts.participant_email,
    ts.score,
    ts.is_passed,
    ts.time_taken_minutes,
    ts.submitted_at,
    u.name as user_name
FROM test_submissions ts
JOIN tests t ON ts.test_id = t.id
LEFT JOIN users u ON ts.user_id = u.id
ORDER BY ts.submitted_at DESC;
"""

async def migrate_test_system():
    """Create test management tables and views"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("📋 Creating test management tables...")
        await conn.execute(CREATE_TEST_SYSTEM_TABLES)
        print("✅ Test management tables created successfully")
        
        print("📊 Creating analytics views...")
        await conn.execute(CREATE_ANALYTICS_VIEWS)
        print("✅ Analytics views created successfully")
        
        # Verify tables were created
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('tests', 'test_submissions', 'test_questions', 'test_analytics', 'user_performance')
            ORDER BY table_name
        """)
        
        print(f"\n📊 Created tables: {[t['table_name'] for t in tables]}")
        
        # Verify views were created
        views = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            AND table_name IN ('test_performance_summary', 'user_leaderboard', 'recent_test_activity')
            ORDER BY table_name
        """)
        
        print(f"📈 Created views: {[v['table_name'] for v in views]}")
        
        await conn.close()
        print("\n🎉 Test system migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

async def verify_migration():
    """Verify the migration was successful"""
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check table structures
        for table in ['tests', 'test_submissions', 'test_questions', 'test_analytics', 'user_performance']:
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = $1 AND table_schema = 'public'
                ORDER BY ordinal_position
            """, table)
            
            print(f"\n📋 {table} ({len(columns)} columns):")
            for col in columns[:5]:  # Show first 5 columns
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
            if len(columns) > 5:
                print(f"  ... and {len(columns) - 5} more columns")
        
        # Check foreign key constraints
        constraints = await conn.fetch("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu 
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name IN ('tests', 'test_submissions', 'test_questions', 'user_performance')
            ORDER BY tc.table_name, tc.constraint_name
        """)
        
        print(f"\n🔗 Foreign Key Constraints: {len(constraints)}")
        for constraint in constraints:
            print(f"  - {constraint['table_name']}.{constraint['column_name']} → {constraint['foreign_table_name']}.{constraint['foreign_column_name']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main migration function"""
    print("🚀 Test Management System Database Migration\n")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found. Please create it with your database credentials.")
        return
    
    print("This will create the following tables:")
    print("  - tests (enhanced test management)")
    print("  - test_submissions (detailed submission tracking)")
    print("  - test_questions (test-question mapping)")
    print("  - test_analytics (performance analytics)")
    print("  - user_performance (user progress tracking)")
    print("\nAnd these views:")
    print("  - test_performance_summary")
    print("  - user_leaderboard") 
    print("  - recent_test_activity")
    
    print("\n⚠️  This will DROP and recreate tests and test_submissions tables!")
    print("   (This is safe since they were empty from the previous setup)")
    
    # Auto-confirm for development
    print("\nProceeding with migration...")
    
    success = await migrate_test_system()
    if success:
        await verify_migration()
        print("\n✨ Test management system is ready!")
        print("🔗 You can now create tests, track submissions, and view analytics!")
    else:
        print("\n❌ Migration failed. Please check your database configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
