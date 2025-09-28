#!/usr/bin/env python3
"""
Quick test script for authentication
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def quick_test():
    print("🚀 Quick Authentication Test\n")
    
    # Wait a moment for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)
    
    try:
        # Test health check first
        print("1. Testing health check...")
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
        
        # Test login
        print("\n2. Testing login with admin@test.com...")
        login_data = {
            "email": "admin@test.com",
            "password": "admin123"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Login successful!")
            print(f"   Token type: {token_data['token_type']}")
            token = token_data["access_token"]
            
            # Test authenticated endpoint
            print("\n3. Testing authenticated endpoint...")
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5)
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ Authenticated request successful!")
                print(f"   User: {user_data['email']} ({user_data['username']})")
                
                # Test question banks list
                print("\n4. Testing question banks list...")
                response = requests.get(f"{BASE_URL}/api/question-banks/", headers=headers, timeout=5)
                if response.status_code == 200:
                    question_banks = response.json()
                    print(f"✅ Question banks endpoint working!")
                    print(f"   Found {len(question_banks)} question banks")
                else:
                    print(f"❌ Question banks failed: {response.status_code}")
                
            else:
                print(f"❌ Authenticated request failed: {response.status_code}")
                
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    print(f"\n🎯 Test completed!")

if __name__ == "__main__":
    quick_test()
