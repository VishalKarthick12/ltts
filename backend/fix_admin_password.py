#!/usr/bin/env python3
"""
Fix admin password hash to be compatible with passlib
"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg
import bcrypt

load_dotenv()

async def fix_admin_password():
    """Fix admin password hash"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    try:
        print("🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        # Hash password using direct bcrypt
        password = "admin123"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        print("🔐 Updating admin password hash...")
        result = await conn.execute("""
            UPDATE users 
            SET password_hash = $1, updated_at = NOW()
            WHERE email = $2
        """, password_hash, "admin@test.com")
        
        if result == "UPDATE 1":
            print("✅ Admin password hash updated successfully")
            print(f"   Email: admin@test.com")
            print(f"   Password: admin123")
        else:
            print("❌ Admin user not found")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to fix password: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(fix_admin_password())
