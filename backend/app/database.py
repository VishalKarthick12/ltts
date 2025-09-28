"""
Database connection and utilities for Supabase/PostgreSQL
"""

import os
from typing import Optional
import asyncpg
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not all([self.database_url, self.supabase_url, self.supabase_service_key]):
            raise ValueError("Missing required environment variables for database connection")
        
        self._pool: Optional[asyncpg.Pool] = None
        self._supabase_client: Optional[Client] = None
    
    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("Database connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                raise
        return self._pool
    
    def get_supabase_client(self, use_service_key: bool = True) -> Client:
        """Get Supabase client (service key for admin operations, anon key for user operations)"""
        if self._supabase_client is None:
            key = self.supabase_service_key if use_service_key else self.supabase_anon_key
            self._supabase_client = create_client(self.supabase_url, key)
            logger.info(f"Supabase client created with {'service' if use_service_key else 'anon'} key")
        return self._supabase_client
    
    async def execute_query(self, query: str, *args):
        """Execute a single query"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def execute_single(self, query: str, *args):
        """Execute query and return single result"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def execute_scalar(self, query: str, *args):
        """Execute query and return single value"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")

# Global database manager instance
db_manager = DatabaseManager()

async def get_db_pool() -> asyncpg.Pool:
    """Dependency for getting database pool"""
    return await db_manager.get_pool()

def get_supabase() -> Client:
    """Dependency for getting Supabase client"""
    return db_manager.get_supabase_client()

# Database health check
async def check_database_health() -> dict:
    """Check database connectivity and return status"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Test basic connectivity
            version = await conn.fetchval('SELECT version()')
            
            # Check if required tables exist
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('question_banks', 'questions')
            """)
            
            return {
                "status": "healthy",
                "database_version": version[:50] + "..." if version else "Unknown",
                "tables_found": [row['table_name'] for row in tables],
                "tables_missing": [t for t in ['question_banks', 'questions'] 
                                 if t not in [row['table_name'] for row in tables]]
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
