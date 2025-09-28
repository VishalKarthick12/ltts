"""
Database connection and utilities using Supabase Python client
"""

import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import uuid
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseManager:
    """Manages Supabase client connections and operations"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not all([self.supabase_url, self.supabase_service_key]):
            raise ValueError("Missing required Supabase environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
        
        self._client: Optional[Client] = None
        logger.info("SupabaseManager initialized")
    
    def get_client(self, use_service_key: bool = True) -> Client:
        """Get Supabase client (service key for admin operations, anon key for user operations)"""
        if self._client is None:
            key = self.supabase_service_key if use_service_key else self.supabase_anon_key
            self._client = create_client(self.supabase_url, key)
            logger.info(f"Supabase client created with {'service' if use_service_key else 'anon'} key")
        return self._client
    
    # Helper methods for common database operations
    def select(self, table: str, columns: str = "*") -> Any:
        """Select data from a table"""
        return self.get_client().table(table).select(columns)
    
    def insert(self, table: str, data: Dict[str, Any]) -> Any:
        """Insert data into a table"""
        return self.get_client().table(table).insert(data)
    
    def update(self, table: str, data: Dict[str, Any]) -> Any:
        """Update data in a table"""
        return self.get_client().table(table).update(data)
    
    def delete(self, table: str) -> Any:
        """Delete data from a table"""
        return self.get_client().table(table).delete()
    
    def upsert(self, table: str, data: Dict[str, Any]) -> Any:
        """Upsert data in a table"""
        return self.get_client().table(table).upsert(data)
    
    def rpc(self, function_name: str, params: Dict[str, Any] = None) -> Any:
        """Call a Supabase function"""
        return self.get_client().rpc(function_name, params or {})
    
    async def close(self):
        """Close connections (no-op for Supabase client)"""
        logger.info("Supabase connections closed")

# Global Supabase manager instance
supabase_manager = SupabaseManager()

def get_supabase() -> Client:
    """Dependency for getting Supabase client"""
    return supabase_manager.get_client()

def get_supabase_manager() -> SupabaseManager:
    """Dependency for getting Supabase manager"""
    return supabase_manager

# Database health check using Supabase client
async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and return status using Supabase"""
    try:
        client = get_supabase()
        
        # Test basic connectivity by checking a simple table
        response = client.table('users').select('id').limit(1).execute()
        
        # Check if required tables exist by attempting to query them
        tables_to_check = ['question_banks', 'questions', 'tests', 'users', 'test_submissions']
        tables_found = []
        tables_missing = []
        
        for table in tables_to_check:
            try:
                client.table(table).select('*').limit(1).execute()
                tables_found.append(table)
            except Exception:
                tables_missing.append(table)
        
        return {
            "status": "healthy",
            "database_type": "Supabase PostgreSQL",
            "tables_found": tables_found,
            "tables_missing": tables_missing,
            "connection_method": "Supabase Python Client"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection_method": "Supabase Python Client"
        }

