#!/usr/bin/env python3
"""
Test the complete test-taking flow to debug loading issues
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_test_taking_flow():
    print("🧪 Testing Test-Taking Flow\n")
    
    # Wait for server
    time.sleep(2)
    
    try:
        # 1. Get auth token
        print("1. Authenticating...")
        login_data = {"email": "admin@test.com", "password": "admin123"}
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            return False
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Authentication successful")
        
        # 2. Get available tests
        print("\n2. Getting available tests...")
        response = requests.get(f"{BASE_URL}/api/tests", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Failed to get tests: {response.status_code}")
            return False
        
        tests = response.json()
        if not tests:
            print("❌ No tests found")
            return False
        
        test_id = tests[0]['id']
        print(f"✅ Found test: {tests[0]['title']} (ID: {test_id})")
        
        # 3. Get test details (this should work for public tests without auth)
        print("\n3. Getting test details...")
        response = requests.get(f"{BASE_URL}/api/tests/{test_id}")
        
        if response.status_code == 200:
            test_details = response.json()
            print("✅ Test details retrieved successfully")
            print(f"   Title: {test_details['title']}")
            print(f"   Questions: {test_details['total_questions']}")
            print(f"   Time limit: {test_details.get('time_limit_minutes', 'None')} minutes")
        else:
            print(f"❌ Test details failed: {response.status_code} - {response.text}")
            return False
        
        # 4. Start test session
        print("\n4. Starting test session...")
        session_data = {
            "participant_name": "Test User",
            "participant_email": "test@example.com"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/test-taking/{test_id}/start", 
            json=session_data, 
            headers=headers
        )
        
        if response.status_code == 200:
            session = response.json()
            session_token = session['session_token']
            print("✅ Test session started successfully")
            print(f"   Session ID: {session['session_id']}")
            print(f"   Session Token: {session_token[:20]}...")
            print(f"   Expires at: {session['expires_at']}")
        else:
            print(f"❌ Session start failed: {response.status_code} - {response.text}")
            return False
        
        # 5. Get test questions with session token
        print("\n5. Getting test questions...")
        response = requests.get(
            f"{BASE_URL}/api/test-taking/{test_id}/questions?session_token={session_token}"
        )
        
        if response.status_code == 200:
            questions = response.json()
            print(f"✅ Questions retrieved successfully: {len(questions)} questions")
            for i, q in enumerate(questions):
                print(f"   {i+1}. {q['question_text'][:50]}... (Type: {q['question_type']})")
        else:
            print(f"❌ Questions failed: {response.status_code} - {response.text}")
            return False
        
        # 6. Test session status
        print("\n6. Checking session status...")
        response = requests.get(f"{BASE_URL}/api/test-taking/session/{session_token}/status")
        
        if response.status_code == 200:
            status = response.json()
            print("✅ Session status retrieved")
            print(f"   Active: {status['is_active']}")
            print(f"   Minutes remaining: {status['minutes_remaining']:.1f}")
            print(f"   Can submit: {status['can_submit']}")
        else:
            print(f"❌ Session status failed: {response.status_code}")
        
        # 7. Save an answer
        print("\n7. Testing answer save...")
        if questions:
            answer_data = {
                "question_id": questions[0]['id'],
                "selected_answer": "Test Answer",
                "question_number": 1
            }
            
            response = requests.post(
                f"{BASE_URL}/api/test-taking/session/{session_token}/save-answer",
                json=answer_data
            )
            
            if response.status_code == 200:
                save_result = response.json()
                print("✅ Answer saved successfully")
                print(f"   Answers saved: {save_result['answers_saved']}")
            else:
                print(f"❌ Answer save failed: {response.status_code} - {response.text}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("🔧 Test-Taking Flow Debug")
    print("=" * 50)
    
    success = test_test_taking_flow()
    
    if success:
        print(f"\n🎉 Test-taking flow is working!")
        print(f"✅ All endpoints responding correctly")
        print(f"✅ Session management working")
        print(f"✅ Questions loading properly")
        print(f"\n🔗 Frontend should now work correctly!")
    else:
        print(f"\n❌ Test-taking flow has issues")

if __name__ == "__main__":
    main()
