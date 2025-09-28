#!/usr/bin/env python3
"""
Test session validation step by step
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg
from datetime import datetime

load_dotenv()

async def test_session_validation():
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        
        print("🔍 Testing session validation...\n")
        
        # Get the most recent session
        session = await conn.fetchrow("""
            SELECT * FROM test_sessions 
            ORDER BY started_at DESC 
            LIMIT 1
        """)
        
        if not session:
            print("❌ No sessions found")
            return
        
        print(f"📋 Testing session: {session['id']}")
        print(f"   Token: {session['session_token'][:20]}...")
        print(f"   Test ID: {session['test_id']}")
        print(f"   Active: {session['is_active']}")
        print(f"   Expires: {session['expires_at']}")
        print(f"   Now: {datetime.utcnow()}")
        print(f"   Expired? {datetime.utcnow() > session['expires_at']}")
        
        # Test the exact query from the endpoint
        validation_result = await conn.fetchrow("""
            SELECT ts.*, t.title, t.is_public, t.created_by
            FROM test_sessions ts
            JOIN tests t ON ts.test_id = t.id
            WHERE ts.test_id = $1 AND ts.session_token = $2 
            AND ts.is_active = true AND ts.expires_at > NOW()
        """, session['test_id'], session['session_token'])
        
        if validation_result:
            print("✅ Session validation query PASSED")
            print(f"   Test: {validation_result['title']}")
            print(f"   Public: {validation_result['is_public']}")
        else:
            print("❌ Session validation query FAILED")
            
            # Check each condition separately
            print("\n🔍 Checking conditions separately:")
            
            # Check if session exists
            basic_session = await conn.fetchrow("""
                SELECT * FROM test_sessions 
                WHERE test_id = $1 AND session_token = $2
            """, session['test_id'], session['session_token'])
            print(f"   Session exists: {basic_session is not None}")
            
            # Check if active
            if basic_session:
                print(f"   Is active: {basic_session['is_active']}")
                print(f"   Expires at: {basic_session['expires_at']}")
                print(f"   Current time: {datetime.utcnow()}")
                print(f"   Not expired: {basic_session['expires_at'] > datetime.utcnow()}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_session_validation())
