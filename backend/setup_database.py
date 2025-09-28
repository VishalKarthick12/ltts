#!/usr/bin/env python3
"""
Database setup script - creates tables and initial data
Run this after setting up your Supabase project
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg
import sys

load_dotenv()

# SQL for creating tables
CREATE_TABLES_SQL = """
-- Create question_banks table
CREATE TABLE IF NOT EXISTS question_banks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'
);

-- Create questions table
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN ('multiple_choice', 'true_false', 'short_answer', 'essay')),
    options TEXT[], -- Array of options for multiple choice questions
    correct_answer TEXT NOT NULL,
    difficulty_level VARCHAR(20) CHECK (difficulty_level IN ('easy', 'medium', 'hard')),
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create tests table (for future use)
CREATE TABLE IF NOT EXISTS tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    question_bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
    num_questions INTEGER NOT NULL,
    time_limit_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired'))
);

-- Create test_submissions table (for future use)
CREATE TABLE IF NOT EXISTS test_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    participant_name VARCHAR(100) NOT NULL,
    participant_email VARCHAR(255),
    score DECIMAL(5,2),
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    time_taken_minutes INTEGER,
    answers JSONB, -- Store answers as JSON
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_questions_question_bank_id ON questions(question_bank_id);
CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_question_banks_created_at ON question_banks(created_at);
CREATE INDEX IF NOT EXISTS idx_tests_question_bank_id ON tests(question_bank_id);
CREATE INDEX IF NOT EXISTS idx_test_submissions_test_id ON test_submissions(test_id);

-- Update updated_at timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for question_banks
DROP TRIGGER IF EXISTS update_question_banks_updated_at ON question_banks;
CREATE TRIGGER update_question_banks_updated_at
    BEFORE UPDATE ON question_banks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

# RLS Policies (optional - uncomment if you want Row Level Security)
RLS_POLICIES_SQL = """
-- Enable RLS (uncomment if needed)
-- ALTER TABLE question_banks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tests ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE test_submissions ENABLE ROW LEVEL SECURITY;

-- Example policies (uncomment and modify as needed)
-- CREATE POLICY "Users can view own question banks" ON question_banks
--   FOR SELECT USING (auth.uid()::text = created_by::text);

-- CREATE POLICY "Users can insert own question banks" ON question_banks
--   FOR INSERT WITH CHECK (auth.uid()::text = created_by::text);
"""

async def setup_database():
    """Set up database tables and indexes"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("📋 Creating tables and indexes...")
        await conn.execute(CREATE_TABLES_SQL)
        print("✅ Tables and indexes created successfully")
        
        # Optionally set up RLS policies
        setup_rls = input("Do you want to set up Row Level Security policies? (y/N): ").lower() == 'y'
        if setup_rls:
            await conn.execute(RLS_POLICIES_SQL)
            print("✅ RLS policies created")
        
        # Verify tables were created
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('question_banks', 'questions', 'tests', 'test_submissions')
            ORDER BY table_name
        """)
        
        print(f"\n📊 Created tables: {[t['table_name'] for t in tables]}")
        
        await conn.close()
        print("\n🎉 Database setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

async def verify_setup():
    """Verify the database setup"""
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check tables
        tables = await conn.fetch("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name AND table_schema = 'public') as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' 
            AND table_name IN ('question_banks', 'questions', 'tests', 'test_submissions')
            ORDER BY table_name
        """)
        
        print("\n🔍 Database verification:")
        for table in tables:
            print(f"  ✅ {table['table_name']} ({table['column_count']} columns)")
        
        # Check indexes
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname LIKE 'idx_%'
            ORDER BY indexname
        """)
        
        print(f"\n📊 Indexes created: {len(indexes)}")
        for idx in indexes:
            print(f"  ✅ {idx['indexname']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🚀 Question Bank Database Setup\n")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found. Please create it with your database credentials.")
        return
    
    print("This will create the following tables:")
    print("  - question_banks")
    print("  - questions") 
    print("  - tests")
    print("  - test_submissions")
    print("  - Associated indexes and triggers")
    
    confirm = input("\nProceed with database setup? (y/N): ").lower()
    if confirm != 'y':
        print("Setup cancelled.")
        return
    
    success = await setup_database()
    if success:
        await verify_setup()
        print("\n✨ You can now start the FastAPI server and begin uploading question banks!")
    else:
        print("\n❌ Setup failed. Please check your database configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
