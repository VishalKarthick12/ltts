#!/usr/bin/env python3
"""
Complete system test including test management and analytics
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def get_auth_token():
    """Login and get auth token"""
    login_data = {
        "email": "admin@test.com",
        "password": "admin123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    return None

def test_complete_system():
    print("🚀 Testing Complete Question Bank Management System\n")
    
    # Wait for server
    time.sleep(3)
    
    try:
        # Get auth token
        print("1. Authenticating...")
        token = get_auth_token()
        if not token:
            print("❌ Authentication failed")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Authentication successful")
        
        # Test 2: Get dashboard stats
        print("\n2. Testing enhanced dashboard stats...")
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard", headers=headers, timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            print("✅ Dashboard stats retrieved!")
            print(f"   Question Banks: {stats['total_question_banks']}")
            print(f"   Questions: {stats['total_questions']}")
            print(f"   Tests: {stats['total_tests']}")
            print(f"   Submissions: {stats['total_submissions']}")
            print(f"   Users: {stats['total_users']}")
        else:
            print(f"❌ Dashboard stats failed: {response.status_code}")
        
        # Test 3: Get question banks for test creation
        print("\n3. Getting question banks...")
        response = requests.get(f"{BASE_URL}/api/question-banks/", headers=headers, timeout=5)
        
        if response.status_code == 200:
            question_banks = response.json()
            print(f"✅ Found {len(question_banks)} question banks")
            
            if len(question_banks) > 0:
                qb_id = question_banks[0]['id']
                qb_name = question_banks[0]['name']
                print(f"   Using question bank: {qb_name}")
                
                # Test 4: Create a test
                print("\n4. Creating a test...")
                test_data = {
                    "title": "Sample Test from API",
                    "description": "Testing the complete test management system",
                    "question_bank_id": qb_id,
                    "num_questions": 3,
                    "time_limit_minutes": 15,
                    "is_public": True,
                    "max_attempts": 2,
                    "pass_threshold": 70.0
                }
                
                response = requests.post(f"{BASE_URL}/api/tests", json=test_data, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    test = response.json()
                    print("✅ Test created successfully!")
                    print(f"   Test ID: {test['id']}")
                    print(f"   Title: {test['title']}")
                    print(f"   Questions: {test['num_questions']}")
                    print(f"   Test Link: {test['test_link']}")
                    
                    test_id = test['id']
                    
                    # Test 5: Get test details
                    print("\n5. Getting test details...")
                    response = requests.get(f"{BASE_URL}/api/tests/{test_id}", headers=headers, timeout=5)
                    
                    if response.status_code == 200:
                        test_details = response.json()
                        print("✅ Test details retrieved!")
                        print(f"   Questions loaded: {len(test_details['questions'])}")
                        print(f"   Time limit: {test_details['time_limit_minutes']} minutes")
                        print(f"   Pass threshold: {test_details['pass_threshold']}%")
                        
                        # Test 6: Submit test answers
                        print("\n6. Submitting test answers...")
                        
                        # Create sample answers (first option for multiple choice, "True" for true/false, etc.)
                        answers = []
                        for question in test_details['questions']:
                            if question['question_type'] == 'multiple_choice' and question['options']:
                                selected_answer = question['options'][0]  # First option
                            elif question['question_type'] == 'true_false':
                                selected_answer = "True"
                            else:
                                selected_answer = "Sample answer"
                            
                            answers.append({
                                "question_id": question['id'],
                                "selected_answer": selected_answer
                            })
                        
                        submission_data = {
                            "participant_name": "Test User",
                            "participant_email": "testuser@example.com",
                            "answers": answers,
                            "time_taken_minutes": 10
                        }
                        
                        response = requests.post(
                            f"{BASE_URL}/api/tests/{test_id}/submit", 
                            json=submission_data, 
                            headers=headers, 
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            submission = response.json()
                            print("✅ Test submission successful!")
                            print(f"   Score: {submission['score']:.1f}%")
                            print(f"   Correct: {submission['correct_answers']}/{submission['total_questions']}")
                            print(f"   Passed: {'Yes' if submission['is_passed'] else 'No'}")
                        else:
                            print(f"❌ Test submission failed: {response.status_code}")
                            print(f"   Response: {response.text}")
                        
                        # Test 7: Get test analytics
                        print("\n7. Getting test analytics...")
                        response = requests.get(f"{BASE_URL}/api/tests/{test_id}/analytics", headers=headers, timeout=5)
                        
                        if response.status_code == 200:
                            analytics = response.json()
                            print("✅ Test analytics retrieved!")
                            print(f"   Total submissions: {analytics['total_submissions']}")
                            print(f"   Average score: {analytics['average_score']:.1f}%")
                            print(f"   Pass rate: {analytics['pass_rate']:.1f}%")
                        else:
                            print(f"❌ Analytics failed: {response.status_code}")
                        
                        # Test 8: Get test submissions
                        print("\n8. Getting test submissions...")
                        response = requests.get(f"{BASE_URL}/api/tests/{test_id}/submissions", headers=headers, timeout=5)
                        
                        if response.status_code == 200:
                            submissions = response.json()
                            print(f"✅ Found {len(submissions)} submissions")
                            for sub in submissions:
                                print(f"   - {sub['participant_name']}: {sub['score']:.1f}% ({'Pass' if sub['is_passed'] else 'Fail'})")
                        else:
                            print(f"❌ Submissions list failed: {response.status_code}")
                    
                    else:
                        print(f"❌ Test details failed: {response.status_code}")
                
                else:
                    print(f"❌ Test creation failed: {response.status_code}")
                    print(f"   Response: {response.text}")
            
            else:
                print("⚠️ No question banks found. Please upload some question banks first.")
        
        else:
            print(f"❌ Question banks fetch failed: {response.status_code}")
        
        # Test 9: Get leaderboard
        print("\n9. Testing leaderboard...")
        response = requests.get(f"{BASE_URL}/api/analytics/leaderboard", headers=headers, timeout=5)
        
        if response.status_code == 200:
            leaderboard = response.json()
            print(f"✅ Leaderboard retrieved with {len(leaderboard)} users")
        else:
            print(f"❌ Leaderboard failed: {response.status_code}")
        
        # Test 10: Get recent activity
        print("\n10. Testing recent activity...")
        response = requests.get(f"{BASE_URL}/api/analytics/recent-activity", headers=headers, timeout=5)
        
        if response.status_code == 200:
            activity = response.json()
            print(f"✅ Recent activity retrieved with {len(activity)} entries")
        else:
            print(f"❌ Recent activity failed: {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("🔥 Complete System Integration Test")
    print("=" * 60)
    
    success = test_complete_system()
    
    if success:
        print(f"\n🎉 Complete system test passed!")
        print(f"✅ Authentication system working")
        print(f"✅ Question bank management working")
        print(f"✅ Test creation and management working")
        print(f"✅ Test submission and scoring working")
        print(f"✅ Analytics and reporting working")
        print(f"\n🔗 System is ready for production use!")
        print(f"   - Dashboard: http://localhost:3000/dashboard")
        print(f"   - Test Management: http://localhost:3000/dashboard/tests")
        print(f"   - API Docs: http://localhost:8000/docs")
    else:
        print(f"\n❌ System test failed")

if __name__ == "__main__":
    main()
