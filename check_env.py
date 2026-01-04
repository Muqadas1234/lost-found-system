#!/usr/bin/env python3
"""
Check .env file configuration
"""

import os
from dotenv import load_dotenv
import sys
import io

# Set UTF-8 encoding for console output (Windows fix)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

print("\n" + "=" * 60)
print("  Current .env Configuration")
print("=" * 60)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

print("\n📧 Email Configuration:")
print("-" * 60)
if EMAIL_ADDRESS:
    print(f"   EMAIL_ADDRESS: {EMAIL_ADDRESS}")
else:
    print("   EMAIL_ADDRESS: ❌ NOT SET")

if EMAIL_PASSWORD:
    password_display = '*' * min(len(EMAIL_PASSWORD), 16)
    print(f"   EMAIL_PASSWORD: {password_display} (configured, length: {len(EMAIL_PASSWORD)})")
else:
    print("   EMAIL_PASSWORD: ❌ NOT SET")

print("\n🔐 Other Configuration:")
print("-" * 60)
if ADMIN_PASSWORD:
    print(f"   ADMIN_PASSWORD: {'*' * len(ADMIN_PASSWORD)} (configured)")
else:
    print("   ADMIN_PASSWORD: ❌ NOT SET (using default)")

if SECRET_KEY:
    print(f"   SECRET_KEY: {'*' * min(len(SECRET_KEY), 20)} (configured)")
else:
    print("   SECRET_KEY: ❌ NOT SET (using default)")

print("\n🔵 Google OAuth Configuration:")
print("-" * 60)
if GOOGLE_CLIENT_ID:
    client_id_display = GOOGLE_CLIENT_ID[:30] + "..." if len(GOOGLE_CLIENT_ID) > 30 else GOOGLE_CLIENT_ID
    print(f"   GOOGLE_CLIENT_ID: {client_id_display} (configured)")
else:
    print("   GOOGLE_CLIENT_ID: ❌ NOT SET")
    print("   ⚠️  Google Sign-In will not work without this!")

print("\n" + "=" * 60)
print("  ⚠️  IMPORTANT: If you changed .env file, restart Flask app!")
print("=" * 60)
print("\nTo restart Flask app:")
print("1. Stop the current Flask server (Ctrl+C)")
print("2. Start it again: python app.py")
print("\n")

