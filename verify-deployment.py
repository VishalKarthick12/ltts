#!/usr/bin/env python3
"""
Deployment Verification Script for LTTS
Checks if all required files and configurations are ready for Render deployment
"""

import os
import json
import sys
from pathlib import Path

def check_file_exists(file_path, description):
    """Check if a file exists and print status"""
    path = Path(file_path)
    if path.exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ Missing {description}: {file_path}")
        return False

def check_package_json(file_path):
    """Verify package.json has correct scripts"""
    try:
        with open(file_path, 'r') as f:
            package = json.load(f)
        
        scripts = package.get('scripts', {})
        required_scripts = ['build', 'start', 'start:prod']
        
        missing_scripts = []
        for script in required_scripts:
            if script not in scripts:
                missing_scripts.append(script)
        
        if not missing_scripts:
            print("✅ Frontend package.json scripts are correctly configured")
            return True
        else:
            print(f"❌ Missing scripts in package.json: {', '.join(missing_scripts)}")
            return False
            
    except Exception as e:
        print(f"❌ Error reading package.json: {e}")
        return False

def main():
    """Main verification function"""
    print("🔍 LTTS Deployment Verification")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check deployment configuration files
    deployment_files = [
        ("render.yaml", "Render deployment configuration"),
        (".env.example", "Environment variables example"),
        ("DEPLOYMENT.md", "Deployment guide"),
        ("README.md", "Project documentation")
    ]
    
    for file_path, description in deployment_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Check frontend files
    print("\n📦 Frontend Verification")
    print("-" * 30)
    frontend_files = [
        ("frontend/package.json", "Frontend package configuration"),
        ("frontend/next.config.ts", "Next.js configuration"),
        ("frontend/env.example", "Frontend environment variables"),
        ("frontend/.next", "Production build output")
    ]
    
    for file_path, description in frontend_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Check package.json scripts
    if check_file_exists("frontend/package.json", "Package.json"):
        if not check_package_json("frontend/package.json"):
            all_checks_passed = False
    
    # Check backend files
    print("\n🐍 Backend Verification")
    print("-" * 30)
    backend_files = [
        ("backend/requirements.txt", "Python dependencies"),
        ("backend/app/main.py", "FastAPI main application"),
        ("backend/Dockerfile", "Docker configuration"),
        ("backend/start.py", "Production startup script"),
        ("backend/env.example", "Backend environment variables")
    ]
    
    for file_path, description in backend_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Summary
    print("\n📋 Verification Summary")
    print("=" * 50)
    
    if all_checks_passed:
        print("🎉 All deployment files are ready!")
        print("\n🚀 Next Steps:")
        print("1. Push code to GitHub repository")
        print("2. Create services on Render using render.yaml")
        print("3. Add environment variables in Render dashboard")
        print("4. Monitor deployment logs")
        print("5. Test deployed application")
        return 0
    else:
        print("⚠️  Some files are missing or incorrectly configured")
        print("Please fix the issues above before deploying")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
