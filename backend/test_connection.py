#!/usr/bin/env python3
"""
Test script to verify Supabase/PostgreSQL connection
Run this before proceeding with development
"""

import os
import sys
from dotenv import load_dotenv
import asyncpg
import asyncio
from supabase import create_client, Client

# Load environment variables
load_dotenv()

async def test_postgres_connection():
    """Test direct PostgreSQL connection"""
    print("🔍 Testing PostgreSQL connection...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    try:
        # Parse the connection string
        conn = await asyncpg.connect(database_url)
        
        # Test a simple query
        version = await conn.fetchval('SELECT version()')
        print(f"✅ PostgreSQL connection successful!")
        print(f"   Version: {version[:50]}...")
        
        # Test if our tables exist (they might not yet)
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('question_banks', 'questions')
        """)
        
        if tables:
            print(f"✅ Found {len(tables)} expected tables: {[t['table_name'] for t in tables]}")
        else:
            print("⚠️  Tables 'question_banks' and 'questions' not found - you'll need to run the SQL schema")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {str(e)}")
        return False

def test_supabase_client():
    """Test Supabase client connection"""
    print("\n🔍 Testing Supabase client connection...")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not found in .env file")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Test a simple query - get user count (should work even with empty auth.users)
        response = supabase.rpc('get_auth_users_count').execute()
        print("✅ Supabase client connection successful!")
        print(f"   Auth users count: {response.data if response.data is not None else 'N/A'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Supabase client connection failed: {str(e)}")
        print("   This might be normal if RLS policies are strict or the RPC doesn't exist")
        return False

async def main():
    """Run all connection tests"""
    print("🚀 Testing Supabase/PostgreSQL connections...\n")
    
    postgres_ok = await test_postgres_connection()
    supabase_ok = test_supabase_client()
    
    print(f"\n📊 Connection Test Results:")
    print(f"   PostgreSQL: {'✅ PASS' if postgres_ok else '❌ FAIL'}")
    print(f"   Supabase Client: {'✅ PASS' if supabase_ok else '❌ FAIL'}")
    
    if postgres_ok:
        print(f"\n🎉 Ready to proceed with development!")
        return True
    else:
        print(f"\n🔧 Please check your .env configuration:")
        print(f"   - DATABASE_URL should be your Supabase PostgreSQL connection string")
        print(f"   - SUPABASE_URL should be your Supabase project URL")
        print(f"   - SUPABASE_SERVICE_KEY should be your service role key")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
