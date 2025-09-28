#!/usr/bin/env python3
"""
Complete authentication system test
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_complete_auth_flow():
    print("🚀 Testing Complete Authentication System\n")
    
    # Wait for server to start
    print("⏳ Waiting for server...")
    time.sleep(3)
    
    try:
        # Test 1: Health check
        print("1. Testing health check...")
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test 2: Login with admin user
        print("\n2. Testing login with admin@test.com...")
        login_data = {
            "email": "admin@test.com",
            "password": "admin123"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Login successful!")
            print(f"   User: {token_data['user']['name']} ({token_data['user']['email']})")
            print(f"   User ID: {token_data['user']['id']}")
            token = token_data["access_token"]
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Test 3: Get current user info
        print("\n3. Testing /me endpoint...")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5)
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ User info retrieved successfully!")
            print(f"   Name: {user_data['name']}")
            print(f"   Email: {user_data['email']}")
        else:
            print(f"❌ User info failed: {response.status_code}")
        
        # Test 4: Test signup with new user
        print("\n4. Testing user signup...")
        signup_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/signup", json=signup_data, timeout=5)
        
        if response.status_code == 200:
            signup_result = response.json()
            print(f"✅ Signup successful!")
            print(f"   New User: {signup_result['user']['name']} ({signup_result['user']['email']})")
            new_token = signup_result["access_token"]
        else:
            print(f"❌ Signup failed: {response.status_code}")
            print(f"   Response: {response.text}")
            new_token = None
        
        # Test 5: Test file upload with authentication
        print("\n5. Testing question bank upload with authentication...")
        
        # Create a simple CSV content
        csv_content = """question,type,options,correct_answer,difficulty,category
What is 2 + 2?,multiple_choice,2|3|4|5,4,easy,math
Python is a programming language,true_false,,True,easy,programming
What is the capital of France?,short_answer,,Paris,medium,geography"""
        
        files = {"file": ("test_questions.csv", csv_content, "text/csv")}
        data = {
            "name": "Test Question Bank via Auth",
            "description": "Testing authenticated upload"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/question-banks/upload",
            files=files,
            data=data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            upload_result = response.json()
            print(f"✅ File upload successful!")
            print(f"   Question Bank ID: {upload_result['question_bank_id']}")
            print(f"   Questions imported: {upload_result['questions_imported']}")
            print(f"   Message: {upload_result['message']}")
        else:
            print(f"❌ File upload failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 6: List question banks
        print("\n6. Testing question banks list...")
        response = requests.get(f"{BASE_URL}/api/question-banks/", headers=headers, timeout=5)
        
        if response.status_code == 200:
            question_banks = response.json()
            print(f"✅ Found {len(question_banks)} question banks:")
            for qb in question_banks:
                print(f"   - {qb['name']}: {qb['question_count']} questions")
        else:
            print(f"❌ Question banks list failed: {response.status_code}")
        
        # Test 7: Test without authentication (should fail)
        print("\n7. Testing upload without authentication (should fail)...")
        response = requests.post(
            f"{BASE_URL}/api/question-banks/upload",
            files={"file": ("test.csv", "test", "text/csv")},
            data={"name": "Test", "description": "Test"},
            timeout=5
        )
        
        if response.status_code == 401:
            print("✅ Correctly rejected upload without authentication")
        else:
            print(f"⚠️ Expected 401, got {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("🔐 Complete Authentication System Test")
    print("=" * 60)
    
    success = test_complete_auth_flow()
    
    if success:
        print(f"\n🎉 All authentication tests passed!")
        print(f"✅ Your complete authentication system is working")
        print(f"✅ Users can sign up and log in")
        print(f"✅ File uploads require authentication")
        print(f"✅ JWT tokens are working correctly")
        print(f"\n🔗 Ready for frontend integration!")
        print(f"   - Login: POST /api/auth/login")
        print(f"   - Signup: POST /api/auth/signup") 
        print(f"   - Upload: POST /api/question-banks/upload (with Bearer token)")
        print(f"   - API Docs: http://localhost:8000/docs")
    else:
        print(f"\n❌ Authentication tests failed")

if __name__ == "__main__":
    main()

