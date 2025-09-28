#!/usr/bin/env python3
"""
Create users table and add default admin user
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg
import bcrypt
import sys

load_dotenv()

# SQL for creating users table
CREATE_USERS_TABLE_SQL = """
-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Update trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

# SQL for updating question_banks table (run after users are created)
UPDATE_QUESTION_BANKS_SQL = """
-- First, change created_by to nullable to avoid constraint issues
ALTER TABLE question_banks 
ALTER COLUMN created_by DROP NOT NULL;

-- Drop existing constraint if it exists
ALTER TABLE question_banks 
DROP CONSTRAINT IF EXISTS fk_question_banks_created_by;

-- Add foreign key constraint with proper handling
ALTER TABLE question_banks 
ADD CONSTRAINT fk_question_banks_created_by 
FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;
"""

async def create_users_table():
    """Create users table and related constraints"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        print("📋 Creating users table...")
        await conn.execute(CREATE_USERS_TABLE_SQL)
        print("✅ Users table created successfully")
        
        # Create default admin user
        print("👤 Creating default admin user...")
        
        # Hash the password
        password = "admin123"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Check if admin user already exists
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1", 
            "admin@test.com"
        )
        
        if existing_user:
            print("ℹ️ Admin user already exists, updating password...")
            await conn.execute("""
                UPDATE users 
                SET password_hash = $1, name = $2, updated_at = NOW()
                WHERE email = $3
            """, password_hash, "Admin", "admin@test.com")
        else:
            print("➕ Creating new admin user...")
            await conn.execute("""
                INSERT INTO users (name, email, password_hash)
                VALUES ($1, $2, $3)
            """, "Admin", "admin@test.com", password_hash)
        
        print("✅ Default admin user created/updated:")
        print("   Email: admin@test.com")
        print("   Password: admin123")
        print("   Name: Admin")
        
        # Verify the user was created
        user = await conn.fetchrow(
            "SELECT id, name, email, created_at FROM users WHERE email = $1",
            "admin@test.com"
        )
        
        if user:
            print(f"✅ Verification successful - User ID: {user['id']}")
        
        # Now update question_banks table to add foreign key constraint
        print("\n🔗 Updating question_banks table with user constraints...")
        try:
            await conn.execute(UPDATE_QUESTION_BANKS_SQL)
            print("✅ Question banks table updated with user constraints")
        except Exception as e:
            print(f"⚠️ Warning: Could not update question_banks constraints: {e}")
            print("   This is normal if you have existing data. The system will still work.")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Users table creation failed: {e}")
        return False

async def verify_users_table():
    """Verify the users table setup"""
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check table structure
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'users' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        print("\n🔍 Users table verification:")
        print("Columns:")
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
        
        # Check constraints
        constraints = await conn.fetch("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'users' AND table_schema = 'public'
        """)
        
        print("\nConstraints:")
        for constraint in constraints:
            print(f"  - {constraint['constraint_name']}: {constraint['constraint_type']}")
        
        # Check if admin user exists
        admin_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE email = $1",
            "admin@test.com"
        )
        
        print(f"\n👤 Admin users found: {admin_count}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🚀 Creating Users Table and Authentication Setup\n")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found. Please create it with your database credentials.")
        return
    
    print("This will:")
    print("  - Create users table with proper constraints")
    print("  - Add foreign key relationship to question_banks")
    print("  - Create default admin user (admin@test.com / admin123)")
    print("  - Set up indexes and triggers")
    
    # Auto-confirm for script execution
    print("\nProceeding with users table setup...")
    # confirm = input("\nProceed with users table setup? (y/N): ").lower()
    # if confirm != 'y':
    #     print("Setup cancelled.")
    #     return
    
    success = await create_users_table()
    if success:
        await verify_users_table()
        print("\n✨ Users table setup completed successfully!")
        print("🔐 You can now use authentication with admin@test.com / admin123")
    else:
        print("\n❌ Setup failed. Please check your database configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
