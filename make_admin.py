"""
Script to make a user an admin
Usage: python make_admin.py <email>
"""

import sqlite3
import sys

def make_admin(email):
    """Make a user admin by email"""
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id, full_name, is_admin FROM users WHERE email = ?", (email.lower(),))
    user = cursor.fetchone()
    
    if not user:
        print(f"❌ Error: User with email '{email}' not found!")
        print("\nAvailable users:")
        cursor.execute("SELECT email, full_name FROM users")
        users = cursor.fetchall()
        for u_email, u_name in users:
            print(f"  - {u_email} ({u_name})")
        conn.close()
        return False
    
    user_id, full_name, is_admin = user
    
    if is_admin:
        print(f"✅ User '{email}' ({full_name}) is already an admin!")
        conn.close()
        return True
    
    # Make user admin
    cursor.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email.lower(),))
    conn.commit()
    conn.close()
    
    print(f"✅ Success! User '{email}' ({full_name}) is now an admin!")
    print(f"   They can now login at: http://127.0.0.1:5000/admin/login")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        print("\nExample: python make_admin.py admin@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    make_admin(email)

