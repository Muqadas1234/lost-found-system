#!/usr/bin/env python3
"""
Check admin setup and configuration
"""

import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("\n" + "=" * 60)
print("  Admin Setup Check")
print("=" * 60)

# Check ADMIN_EMAIL
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip()
ADMIN_EMAILS = [email.strip().lower() for email in ADMIN_EMAIL.split(",") if email.strip()] if ADMIN_EMAIL else []

print("\n📧 Environment Variables:")
print("-" * 60)
if ADMIN_EMAIL:
    print(f"   ADMIN_EMAIL: {ADMIN_EMAIL}")
    print(f"   Parsed emails: {ADMIN_EMAILS}")
else:
    print("   ADMIN_EMAIL: ❌ NOT SET")
    print("   ⚠️  Admin login will use database check (is_admin column)")

SECRET_KEY = os.getenv("SECRET_KEY")
if SECRET_KEY:
    print(f"   SECRET_KEY: {'*' * min(len(SECRET_KEY), 20)} (configured)")
    print("   ℹ️  SECRET_KEY is for session security, NOT for login")
else:
    print("   SECRET_KEY: ❌ NOT SET (using default)")

# Check database
print("\n👥 Database Users:")
print("-" * 60)
try:
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute("SELECT email, full_name, is_admin, is_verified FROM users")
    users = cursor.fetchall()
    
    if not users:
        print("   ❌ No users found in database")
        print("   💡 First register a user at: http://127.0.0.1:5000/signup")
    else:
        print(f"   Found {len(users)} user(s):\n")
        for email, name, is_admin, is_verified in users:
            admin_status = "✅ Admin" if is_admin else "❌ Not Admin"
            verified_status = "✅ Verified" if is_verified else "❌ Not Verified"
            in_env = "✅ In ADMIN_EMAIL" if ADMIN_EMAILS and email.lower() in ADMIN_EMAILS else ""
            
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Status: {admin_status} | {verified_status} {in_env}")
            print()
    
    conn.close()
    
except sqlite3.Error as e:
    print(f"   ❌ Database error: {e}")

# Summary
print("\n📋 Summary:")
print("-" * 60)
if ADMIN_EMAILS:
    print("   ✅ ADMIN_EMAIL is set")
    print("   ℹ️  Only these emails can login as admin:")
    for email in ADMIN_EMAILS:
        print(f"      - {email}")
    print("\n   ⚠️  Make sure:")
    print("      1. User is registered in database")
    print("      2. User's email matches ADMIN_EMAIL")
    print("      3. User has verified their email")
    print("      4. You know the user's password")
else:
    print("   ⚠️  ADMIN_EMAIL is not set")
    print("   ℹ️  Admin login will check database 'is_admin' column")
    print("   💡 To use ADMIN_EMAIL, add to .env file:")
    print("      ADMIN_EMAIL=your-email@example.com")

print("\n" + "=" * 60)
print("  Login Steps:")
print("=" * 60)
print("1. Go to: http://127.0.0.1:5000/admin/login")
print("2. Enter the EMAIL (from ADMIN_EMAIL or database)")
print("3. Enter the PASSWORD (user's password, NOT SECRET_KEY)")
print("4. Click 'Access Dashboard'")
print("\n" + "=" * 60)




