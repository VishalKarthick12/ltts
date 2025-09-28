#!/usr/bin/env python3
"""
Test file upload functionality
"""

import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_file_upload():
    print("🚀 Testing File Upload with Authentication\n")
    
    # Step 1: Login
    print("1. Logging in...")
    login_data = {
        "email": "admin@test.com",
        "password": "admin123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful!")
    
    # Step 2: Check if sample file exists
    sample_file = Path("sample_questions.csv")
    if not sample_file.exists():
        print("❌ Sample CSV file not found")
        return
    
    print(f"✅ Found sample file: {sample_file}")
    
    # Step 3: Upload file
    print("\n2. Uploading question bank file...")
    
    with open(sample_file, 'rb') as f:
        files = {"file": ("sample_questions.csv", f, "text/csv")}
        data = {
            "name": "Test Question Bank from API",
            "description": "Sample questions uploaded via API test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/question-banks/upload",
            files=files,
            data=data,
            headers=headers
        )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ File upload successful!")
        print(f"   Question Bank ID: {result['question_bank_id']}")
        print(f"   Questions imported: {result['questions_imported']}")
        print(f"   Message: {result['message']}")
        
        # Step 4: Verify the upload by listing question banks
        print("\n3. Verifying upload...")
        response = requests.get(f"{BASE_URL}/api/question-banks/", headers=headers)
        
        if response.status_code == 200:
            question_banks = response.json()
            print(f"✅ Found {len(question_banks)} question banks:")
            for qb in question_banks:
                print(f"   - {qb['name']}: {qb['question_count']} questions")
                
                # Get questions from this question bank
                qb_id = qb['id']
                response = requests.get(f"{BASE_URL}/api/question-banks/{qb_id}/questions", headers=headers)
                if response.status_code == 200:
                    questions = response.json()
                    print(f"     Sample questions:")
                    for i, q in enumerate(questions[:3]):  # Show first 3 questions
                        print(f"     {i+1}. {q['question_text']} (Type: {q['question_type']})")
                    if len(questions) > 3:
                        print(f"     ... and {len(questions) - 3} more questions")
        
        return True
        
    else:
        print(f"❌ File upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    print("📁 File Upload Test for Question Bank Management System")
    print("=" * 60)
    
    success = test_file_upload()
    
    if success:
        print(f"\n🎉 File upload test completed successfully!")
        print(f"✅ Your authentication system is working")
        print(f"✅ File processing is working")
        print(f"✅ Database storage is working")
        print(f"\n🔗 Next steps:")
        print(f"   1. Visit http://localhost:8000/docs to explore all endpoints")
        print(f"   2. Test the frontend integration")
        print(f"   3. Build test generation features")
    else:
        print(f"\n❌ File upload test failed")

if __name__ == "__main__":
    main()
