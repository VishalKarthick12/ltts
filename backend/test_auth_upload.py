#!/usr/bin/env python3
"""
Test script for authentication and file upload
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_authentication():
    """Test login and get token"""
    print("🔐 Testing authentication...")
    
    # Test login
    login_data = {
        "email": "admin@test.com",
        "password": "admin123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    
    if response.status_code == 200:
        token_data = response.json()
        print(f"✅ Login successful! Token type: {token_data['token_type']}")
        return token_data["access_token"]
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None

def test_file_upload(token):
    """Test file upload with authentication"""
    print("\n📁 Testing file upload...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check if sample file exists
    sample_file = Path("sample_questions.csv")
    if not sample_file.exists():
        print("❌ Sample file not found. Creating one...")
        return False
    
    # Upload file
    with open(sample_file, 'rb') as f:
        files = {"file": ("sample_questions.csv", f, "text/csv")}
        data = {
            "name": "Test Question Bank",
            "description": "Sample questions for testing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/question-banks/upload",
            files=files,
            data=data,
            headers=headers
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Upload successful!")
        print(f"   Question Bank ID: {result['question_bank_id']}")
        print(f"   Questions imported: {result['questions_imported']}")
        return result['question_bank_id']
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def test_question_banks_list(token):
    """Test getting question banks list"""
    print("\n📋 Testing question banks list...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/question-banks/", headers=headers)
    
    if response.status_code == 200:
        question_banks = response.json()
        print(f"✅ Found {len(question_banks)} question banks")
        for qb in question_banks:
            print(f"   - {qb['name']}: {qb['question_count']} questions")
        return question_banks
    else:
        print(f"❌ Failed to get question banks: {response.status_code}")
        return []

def test_without_auth():
    """Test endpoints without authentication (should still work with fallback)"""
    print("\n🔓 Testing without authentication...")
    
    # Test health check (should work)
    response = requests.get(f"{BASE_URL}/api/health")
    if response.status_code == 200:
        print("✅ Health check works without auth")
    else:
        print("❌ Health check failed")
    
    # Test question banks list without auth (should work with fallback user)
    response = requests.get(f"{BASE_URL}/api/question-banks/")
    if response.status_code == 200:
        print("✅ Question banks list works without auth (fallback user)")
    else:
        print("❌ Question banks list failed without auth")

def main():
    print("🚀 Testing Question Bank Management System Authentication\n")
    
    # Test without authentication first
    test_without_auth()
    
    # Test with authentication
    token = test_authentication()
    if not token:
        print("\n❌ Cannot proceed without valid token")
        return
    
    # Test file upload
    question_bank_id = test_file_upload(token)
    
    # Test listing question banks
    question_banks = test_question_banks_list(token)
    
    print(f"\n🎉 Testing completed!")
    if question_bank_id:
        print(f"✅ Successfully uploaded and can manage question banks")
        print(f"\n📊 Next steps:")
        print(f"   1. Visit http://localhost:8000/docs to see all endpoints")
        print(f"   2. Use the uploaded question bank ID: {question_bank_id}")
        print(f"   3. Test the frontend integration")
    else:
        print(f"❌ Some tests failed - check the backend logs")

if __name__ == "__main__":
    main()
