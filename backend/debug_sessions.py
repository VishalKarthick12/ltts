#!/usr/bin/env python3
"""
Debug test sessions to understand the validation issue
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def debug_sessions():
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        
        print("🔍 Debugging test sessions...\n")
        
        # Check recent test sessions
        sessions = await conn.fetch("""
            SELECT ts.*, t.title, t.is_public
            FROM test_sessions ts
            JOIN tests t ON ts.test_id = t.id
            ORDER BY ts.started_at DESC
            LIMIT 5
        """)
        
        print(f"📊 Found {len(sessions)} recent sessions:")
        for session in sessions:
            print(f"  - Session: {session['id']}")
            print(f"    Test: {session['title']} (Public: {session['is_public']})")
            print(f"    Token: {session['session_token'][:20]}...")
            print(f"    Active: {session['is_active']}")
            print(f"    Expires: {session['expires_at']}")
            print(f"    User ID: {session['user_id']}")
            print()
        
        # Check if any sessions are currently active
        active_sessions = await conn.fetch("""
            SELECT * FROM active_test_sessions
            ORDER BY started_at DESC
            LIMIT 3
        """)
        
        print(f"🔴 Active sessions: {len(active_sessions)}")
        for session in active_sessions:
            print(f"  - {session['test_title']}: {session['minutes_remaining']:.1f} min remaining")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_sessions())

