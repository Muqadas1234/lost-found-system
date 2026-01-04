from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
import sqlite3
import smtplib
import os
import hashlib
import secrets
import string
import random
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
import numpy as np
import re
import base64
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Add CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Check if email is configured
EMAIL_CONFIGURED = EMAIL_ADDRESS and EMAIL_PASSWORD

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID != "")

# Initialize NLP model
def load_nlp_model():
    # Use a smaller model for efficiency - this is a multilingual model that works well for English and many other languages
    try:
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return model
    except Exception as e:
        print(f"Warning: Could not load AI model: {e}")
        return None

# Global model variable
nlp_model = None

def get_nlp_model():
    global nlp_model
    if nlp_model is None:
        nlp_model = load_nlp_model()
    return nlp_model

# ------------------- DB Setup -------------------
def add_column_if_missing(column_name, column_def):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    try:
        cursor.execute(f"ALTER TABLE reports ADD COLUMN {column_name} {column_def};")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

def init_db():
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0,
            secret TEXT,
            category TEXT,
            embedding BLOB,
            matched INTEGER DEFAULT 0,
            image BLOB,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create users table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            student_id TEXT,
            phone TEXT,
            is_verified INTEGER DEFAULT 0,
            verification_code TEXT,
            verification_expires TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    add_column_if_missing("secret", "TEXT")
    add_column_if_missing("category", "TEXT")
    add_column_if_missing("embedding", "BLOB")
    add_column_if_missing("matched", "INTEGER DEFAULT 0")
    add_column_if_missing("image", "BLOB")
    add_column_if_missing("user_id", "INTEGER")
    
    # Add reset token columns to users table
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_expires TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Add is_admin column to users table
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Add Google OAuth columns to users table
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'email';")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Make password_hash nullable for OAuth users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash_backup TEXT;")
        conn.commit()
        # Copy existing password_hash to backup
        cursor.execute("UPDATE users SET password_hash_backup = password_hash WHERE password_hash IS NOT NULL;")
        # SQLite doesn't support ALTER COLUMN, so we'll handle NULL passwords in code
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

# ------------------- Email Templates -------------------
def create_lost_item_found_email(name, match_description, finder_name, finder_contact):
    """Create a simple single card email template for when a lost item is found"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lost Item Found!</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #6b7280, #4b5563); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .contact-btn {{ display: inline-block; background: linear-gradient(135deg, #6b7280, #4b5563); color: white !important; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: 600; text-align: center; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #6b7280; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🎉</span> Great News!</h1>
            <p>Your lost item might have been found!</p>
        </div>
        
        <div class="content">
            <h2>Hello {name},</h2>
            
            <div class="info-section">
                <h3><span class="emoji">📱</span> Found Item Details:</h3>
                <p><strong>Description:</strong> {match_description}</p>
                <p><strong>Found By:</strong> {finder_name}</p>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">📞</span> Contact Information:</h3>
                <p><strong>Contact:</strong> {finder_contact}</p>
            </div>
            
            <div style="text-align: center;">
                <a href="mailto:{finder_contact}" class="contact-btn" style="color: white !important;">📧 Contact Finder</a>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">📋</span> Next Steps:</h3>
                <div class="step">Visit the Admin Office to complete the verification process</div>
                <div class="step">Present your identification and collect your item from the Admin Office</div>
                <div class="step">Sign the collection receipt to complete the handover process</div>
            </div>
            
            <p style="text-align: center; margin-top: 25px; font-weight: 600; color: #4b5563;">
                <span class="emoji">✅</span> Please note: All items are collected through the Admin Office for security and verification purposes.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
        </div>
    </div>
</body>
</html>
"""

def create_found_item_match_email(finder_name, lost_description, reporter_name, reporter_contact, secret_detail):
    """Create a simple single card email template for when a found item matches a lost report"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lost Item Match Found!</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #6b7280, #4b5563); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .contact-btn {{ display: inline-block; background: linear-gradient(135deg, #6b7280, #4b5563); color: white !important; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: 600; text-align: center; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #6b7280; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🔔</span> Match Alert!</h1>
            <p>Someone is looking for the item you found!</p>
        </div>
        
        <div class="content">
            <h2>Hello {finder_name},</h2>
            
            <div class="info-section">
                <h3><span class="emoji">📱</span> Lost Item Details:</h3>
                <p><strong>Description:</strong> {lost_description}</p>
                <p><strong>Reported By:</strong> {reporter_name}</p>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">📞</span> Contact Information:</h3>
                <p><strong>Contact:</strong> {reporter_contact}</p>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">🔐</span> Secret Details:</h3>
                <p><strong>Secret:</strong> {secret_detail}</p>
                <p><em>Use this to verify the true owner!</em></p>
            </div>
            
            <div style="text-align: center;">
                <a href="mailto:{reporter_contact}" class="contact-btn" style="color: white !important;">📧 Contact Owner</a>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">📋</span> Next Steps:</h3>
                <div class="step">Submit the found item to the Admin Office immediately</div>
                <div class="step">The lost reporter is waiting for their item</div>
                <div class="step">Complete the handover documentation with Admin Office staff</div>
            </div>
            
            <p style="text-align: center; margin-top: 25px; font-weight: 600; color: #4b5563;">
                <span class="emoji">✅</span> Please note: All found items must be submitted to the Admin Office for verification and safe return to rightful owners.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
        </div>
    </div>
</body>
</html>
"""

def create_finder_summary_email(finder_name, matches_count, matches_details):
    """Create a simple single card email template for finder with multiple matches"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multiple Matches Found!</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #6b7280, #4b5563); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .match-item {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin: 10px 0; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #6b7280; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🔍</span> Multiple Matches!</h1>
            <p>Your found item matches {matches_count} lost reports!</p>
        </div>
        
        <div class="content">
            <h2>Hello {finder_name},</h2>
            
            <div class="info-section">
                <h3><span class="emoji">🎉</span> Amazing News!</h3>
                <p>Your found item report has matched with <strong>{matches_count}</strong> lost item reports. Multiple people are looking for similar items!</p>
            </div>
            
            <h3><span class="emoji">📋</span> Match Details:</h3>
            {matches_details}
            
            <div class="steps-section">
                <h3><span class="emoji">📋</span> Next Steps:</h3>
                <div class="step">Submit the found item to the Admin Office immediately</div>
                <div class="step">The lost reporter is waiting for their item</div>
                <div class="step">Complete the handover documentation with Admin Office staff</div>
            </div>
            
            <p style="text-align: center; margin-top: 25px; font-weight: 600; color: #4b5563;">
                <span class="emoji">✅</span> Please note: All found items must be submitted to the Admin Office for verification and safe return to rightful owners.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
        </div>
    </div>
</body>
</html>
"""

# ------------------- Authentication Functions -------------------
def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password, password_hash):
    """Verify password against hash"""
    try:
        salt, hash_part = password_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == hash_part
    except:
        return False

def generate_verification_code():
    """Generate a 6-digit verification code"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def is_valid_email(email):
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """Decorator to require login for API routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in'):
            return jsonify({'success': False, 'message': 'Not logged in'})
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin authentication for routes - checks database for admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        
        # Check if user is logged in and is admin in database
        if not user_id:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Not logged in'}), 403
            return redirect(url_for('admin_login'))
        
        # Check database for admin status
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        # User must be admin (is_admin = 1)
        if not result or not result[0]:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
            return redirect(url_for('admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user info"""
    if session.get('user_logged_in'):
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, student_id, phone, is_verified FROM users WHERE id = ?", (session.get('user_id'),))
        user = cursor.fetchone()
        conn.close()
        return user
    return None

# ------------------- Email Templates for Authentication -------------------
def create_verification_email(full_name, verification_code):
    """Create verification email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Verification - Item Recovery Portal</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .verification-code {{ background: #f8f9fa; border: 2px solid #667eea; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }}
        .verification-code h2 {{ color: #667eea; font-size: 32px; letter-spacing: 8px; margin: 0; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #667eea; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">📧</span> Email Verification</h1>
            <p>Welcome to Item Recovery Portal</p>
        </div>
        
        <div class="content">
            <h2>Hello {full_name},</h2>
            
            <p>Thank you for registering with the Item Recovery Portal! To complete your registration and start using our services, please verify your email address.</p>
            
            <div class="verification-code">
                <h2>{verification_code}</h2>
                <p style="margin: 10px 0 0 0; color: #6b7280;">Enter this code in the verification form</p>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">📋</span> Next Steps:</h3>
                <div class="step">Copy the verification code above</div>
                <div class="step">Return to the verification page</div>
                <div class="step">Enter the code to complete your registration</div>
                <div class="step">Start using Item Recovery Portal!</div>
            </div>
            
            <p style="text-align: center; margin-top: 25px; font-weight: 600; color: #4b5563;">
                <span class="emoji">⏰</span> This code will expire in 15 minutes for security reasons.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
        </div>
    </div>
</body>
</html>
"""

def create_welcome_email(full_name):
    """Create welcome email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Item Recovery Portal</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .features-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .feature {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .feature::before {{ content: "✓"; position: absolute; left: 0; top: 0; background: #10b981; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🎉</span> Welcome!</h1>
            <p>Your account has been successfully verified</p>
        </div>
        
        <div class="content">
            <h2>Hello {full_name},</h2>
            
            <p>Congratulations! Your email has been successfully verified and your account is now active. You can now access all features of the Item Recovery Portal.</p>
            
            <div class="features-section">
                <h3><span class="emoji">🚀</span> What you can do now:</h3>
                <div class="feature">Report lost items with detailed descriptions</div>
                <div class="feature">Report found items to help others</div>
                <div class="feature">Search for your lost belongings</div>
                <div class="feature">Get instant notifications when matches are found</div>
                <div class="feature">Chat with other users about items</div>
                <div class="feature">Track your report history</div>
            </div>
            
            <p style="text-align: center; margin-top: 25px; font-weight: 600; color: #4b5563;">
                <span class="emoji">🔗</span> Visit our website to get started: <a href="http://127.0.0.1:5000" style="color: #667eea;">Item Recovery Portal</a>
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
        </div>
    </div>
</body>
</html>
"""

def create_password_reset_email(full_name, reset_url):
    """Create password reset email template matching the lost & found format"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset Request</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #6b7280, #4b5563); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .reset-btn {{ display: inline-block; background: linear-gradient(135deg, #6b7280, #4b5563); color: white !important; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: 600; text-align: center; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #6b7280; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🔒</span> Password Reset Request</h1>
            <p>Reset your Item Recovery Portal account password</p>
        </div>
        
        <div class="content">
            <h2>Hello {full_name},</h2>
            
            <div class="info-section">
                <h3><span class="emoji">🔑</span> Password Reset Request:</h3>
                <p>You requested a password reset for your Item Recovery Portal account.</p>
                <p>Click the button below to reset your password:</p>
            </div>
            
            <div style="text-align: center;">
                <a href="{reset_url}" class="reset-btn">Reset Password</a>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">⏰</span> Important Information:</h3>
                <div class="step">This reset link will expire in 1 hour</div>
                <div class="step">If you didn't request this reset, please ignore this email</div>
                <div class="step">Your password will remain unchanged until you click the link</div>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">🛡️</span> Security Note:</h3>
                <p>For your security, never share this reset link with anyone. Our team will never ask for your password or reset links.</p>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
            <p>If you have any questions, please contact our support team.</p>
        </div>
    </div>
</body>
</html>
    """

def create_password_reset_code_email(full_name, reset_code):
    """Create password reset code email template matching the lost & found format"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset Code</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #6b7280, #4b5563); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .code-section {{ background: #f9fafb; border: 2px solid #d1d5db; border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center; }}
        .reset-code {{ font-size: 32px; font-weight: 700; color: #1f2937; letter-spacing: 8px; margin: 10px 0; font-family: 'Courier New', monospace; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #6b7280; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🔒</span> Password Reset Code</h1>
            <p>Your verification code for password reset</p>
        </div>
        
        <div class="content">
            <h2>Hello {full_name},</h2>
            
            <div class="info-section">
                <h3><span class="emoji">🔑</span> Password Reset Request:</h3>
                <p>You requested a password reset for your Item Recovery Portal account.</p>
                <p>Use the verification code below to reset your password:</p>
            </div>
            
            <div class="code-section">
                <h3><span class="emoji">🔢</span> Your Verification Code:</h3>
                <div class="reset-code">{reset_code}</div>
                <p style="color: #6b7280; font-size: 14px; margin-top: 10px;">Enter this code on the password reset page</p>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">⏰</span> Important Information:</h3>
                <div class="step">This code will expire in 15 minutes</div>
                <div class="step">If you didn't request this reset, please ignore this email</div>
                <div class="step">Your password will remain unchanged until you enter the code</div>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">🛡️</span> Security Note:</h3>
                <p>For your security, never share this code with anyone. Our team will never ask for your password or verification codes.</p>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
            <p>If you have any questions, please contact our support team.</p>
        </div>
    </div>
</body>
</html>
    """

def create_password_change_notification_email(full_name, change_time):
    """Create password change notification email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Changed Successfully</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .email-card {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px; }}
        .info-section {{ margin: 20px 0; }}
        .info-section h3 {{ color: #4b5563; margin-bottom: 10px; font-size: 16px; }}
        .info-section p {{ margin: 5px 0; color: #374151; }}
        .success-section {{ background: #f0fdf4; border: 2px solid #10b981; border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center; }}
        .success-icon {{ font-size: 48px; margin-bottom: 15px; }}
        .steps-section {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .steps-section h3 {{ color: #4b5563; margin-bottom: 15px; }}
        .step {{ margin: 8px 0; padding-left: 20px; position: relative; color: #374151; }}
        .step::before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 0; background: #10b981; color: white; width: 16px; height: 16px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
        .steps-section {{ counter-reset: step-counter; }}
        .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 14px; }}
        .emoji {{ font-size: 20px; }}
        .warning-section {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 20px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="email-card">
        <div class="header">
            <h1><span class="emoji">🔐</span> Password Changed Successfully</h1>
            <p>Your account security has been updated</p>
        </div>
        
        <div class="content">
            <h2>Hello {full_name},</h2>
            
            <div class="success-section">
                <div class="success-icon">✅</div>
                <h3 style="color: #059669; margin: 0;">Password Successfully Changed!</h3>
                <p style="color: #6b7280; margin: 10px 0 0 0;">Your password was changed on {change_time}</p>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">🔒</span> What This Means:</h3>
                <p>Your Item Recovery Portal account password has been successfully updated. You can now use your new password to log in to your account.</p>
            </div>
            
            <div class="steps-section">
                <h3><span class="emoji">📋</span> Next Steps:</h3>
                <div class="step">Use your new password to log in to your account</div>
                <div class="step">Update your password in any password managers you use</div>
                <div class="step">Keep your new password secure and don't share it with anyone</div>
            </div>
            
            <div class="warning-section">
                <h3><span class="emoji">⚠️</span> Important Security Notice:</h3>
                <p><strong>If you did not change your password:</strong></p>
                <p>If you did not make this change, please contact our support team immediately. Your account may have been compromised.</p>
            </div>
            
            <div class="info-section">
                <h3><span class="emoji">🛡️</span> Security Tips:</h3>
                <p>• Use a strong, unique password</p>
                <p>• Don't reuse passwords across different accounts</p>
                <p>• Enable two-factor authentication if available</p>
                <p>• Log out from shared or public computers</p>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Item Recovery Portal</strong></p>
            <p>This is an automated security notification. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
    """

# ------------------- Email -------------------
def send_email(to_email, subject, body, is_html=False):
    if is_html:
        msg = MIMEText(body, "html")
    else:
        msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Email Error:", e)
        return False

# ------------------- NLP Functions -------------------
def generate_embedding(text):
    """Convert text to embedding vector using the sentence transformer model"""
    # Clean and preprocess text
    text = text.lower().strip()
    # Generate embedding
    model = get_nlp_model()
    if model is None:
        return None
    embedding = model.encode(text)
    return embedding

def compute_similarity(embedding1, embedding2):
    """Compute cosine similarity between two embeddings"""
    embedding1_norm = embedding1 / np.linalg.norm(embedding1)
    embedding2_norm = embedding2 / np.linalg.norm(embedding2)
    similarity = np.dot(embedding1_norm, embedding2_norm)
    return float(similarity * 100)

def extract_entities(text):
    """Extract key entities from text using regex patterns"""
    entities = {}
    
    # Brand detection
    brands = ["apple", "samsung", "sony", "nokia", "oppo", "vivo", "xiaomi", 
              "realme", "dell", "hp", "lenovo", "asus", "acer", "huawei"]
    
    for brand in brands:
        if re.search(r'\b' + brand + r'\b', text.lower()):
            entities["brand"] = brand
            break
    
    # Color detection
    colors = ["black", "white", "red", "blue", "green", "yellow", "purple", 
              "pink", "brown", "grey", "gray", "silver", "gold"]
    
    for color in colors:
        if re.search(r'\b' + color + r'\b', text.lower()):
            entities["color"] = color
            break
    
    # Item type detection - simplified version
    item_types = {
        "phone": ["phone", "mobile", "smartphone", "iphone", "android"],
        "charger": ["charger", "adapter", "power bank"],
        "laptop": ["laptop", "notebook", "macbook", "computer"],
        "wallet": ["wallet", "purse", "money", "card holder"],
        "keys": ["key", "keys", "keychain"],
        "id": ["id", "card", "identity", "license", "passport"],
        "bag": ["bag", "backpack", "handbag", "luggage", "suitcase"],
        "book": ["book", "notebook", "textbook"],
        "headphone": ["headphone", "earphone", "earbuds", "airpod"],
        "watch": ["watch", "smartwatch", "apple watch"]
    }
    
    for item_type, keywords in item_types.items():
        for keyword in keywords:
            if re.search(r'\b' + keyword + r'\b', text.lower()):
                entities["item_type"] = item_type
                break
        if "item_type" in entities:
            break
            
    return entities

def detect_item_category(description):
    """Extract the likely category of the item from its description using NLP"""
    description = description.lower()
    entities = extract_entities(description)
    
    if "item_type" in entities:
        item_type = entities["item_type"]
        if item_type == "charger" and "phone" in description:
            return "phone charger"
        return item_type
    
    categories = {
        "phone": ["phone", "mobile", "smartphone", "iphone", "android", "samsung", "xiaomi", "oppo", "vivo", "realme", "handset"],
        "charger": ["charger", "adapter", "power bank", "charging", "usb-c", "lightning", "cable"],
        "laptop": ["laptop", "notebook", "macbook", "computer", "pc", "chromebook", "ultrabook"],
        "wallet": ["wallet", "purse", "money", "cash", "card holder", "billfold"],
        "keys": ["key", "keys", "keychain", "car key", "home key", "room key", "lock key"],
        "id": ["id", "card", "identity card", "driver license", "passport", "student card", "employee id"],
        "bag": ["bag", "backpack", "handbag", "luggage", "suitcase", "tote", "duffel"],
        "book": ["book", "notebook", "textbook", "novel", "diary", "journal", "magazine"],
        "headphone": ["headphone", "earphone", "earbuds", "airpod", "earpods", "headset"],
        "watch": ["watch", "smartwatch", "wristwatch", "apple watch", "timepiece"],
        "clothing": ["jacket", "hoodie", "shirt", "pants", "dress", "scarf", "hat", "cap", "glasses", "sweater"],
        "jewelry": ["ring", "necklace", "bracelet", "earring", "chain", "pendant"],
        "electronics": ["tablet", "ipad", "kindle", "camera", "speaker", "power bank"],
        "stationery": ["pen", "pencil", "marker", "highlighter", "notepad", "folder"]
    }
    
    best_category = "other"
    best_score = 0
    
    for category, keywords in categories.items():
        score = 0
        for keyword in keywords:
            if keyword in description:
                score += 1
        
        if score > best_score:
            best_score = score
            best_category = category
    
    if best_category == "charger" and any(device in description for device in categories["phone"]):
        return "phone charger"
    
    return best_category

# ------------------- Matching (NLP-based) -------------------
def check_for_matches(description, status, category=None, exclude_id=None):
    # Generate embedding for the query
    query_embedding = generate_embedding(description)
    query_entities = extract_entities(description)
    
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    # Explicitly request all columns to ensure we get the secret column and embedding
    query = "SELECT id, name, contact, description, status, timestamp, resolved, secret, category, embedding FROM reports WHERE status = ? AND resolved = 0"
    params = [status]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    matches = []
    for item in items:
        # Get embedding from db if it exists, otherwise generate it
        item_embedding = None
        if item[9] is not None:  # Check if embedding exists in database
            # Convert from binary to numpy array
            item_embedding = np.frombuffer(item[9], dtype=np.float32)
        else:
            # Generate embedding if not found in database
            item_embedding = generate_embedding(item[3])
        
        # Calculate semantic similarity using embeddings
        similarity_score = compute_similarity(query_embedding, item_embedding)
        
        # Extract entities from item description
        item_entities = extract_entities(item[3])
        
        # Entity matching bonus
        entity_bonus = 0
        
        # Brand matching - strong signal
        if "brand" in query_entities and "brand" in item_entities:
            if query_entities["brand"] == item_entities["brand"]:
                entity_bonus += 25
                
        # Color matching - good signal
        if "color" in query_entities and "color" in item_entities:
            if query_entities["color"] == item_entities["color"]:
                entity_bonus += 15
                
        # Item type matching - important signal
        if "item_type" in query_entities and "item_type" in item_entities:
            if query_entities["item_type"] == item_entities["item_type"]:
                entity_bonus += 20
        
        # Category matching bonus (if categories exist and match)
        category_bonus = 0
        item_category = item[8] if len(item) > 8 and item[8] else None
        
        if category and item_category and category == item_category:
            category_bonus = 10  # Boost for same category
        
        # Final score combines semantic similarity with entity matching bonuses
        final_score = similarity_score + entity_bonus + category_bonus
        
        # Threshold for considering a match - increased for better accuracy
        if final_score >= 85:
            matches.append((item, final_score))
    
    # Sort matches by score (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return [match[0] for match in matches]

# ------------------- Add Report -------------------
def add_report(name, contact, description, status, secret=None, image=None, user_id=None):
    # Generate embedding
    embedding = generate_embedding(description)
    
    # Detect item category using improved NLP approach
    category = detect_item_category(description)
    
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Convert embedding to binary for storage
    embedding_binary = embedding.tobytes()
    
    cursor.execute("INSERT INTO reports (name, contact, description, status, timestamp, secret, category, embedding, matched, image, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (name.strip(), contact.strip(), description.strip().lower(), status, timestamp, secret, category, embedding_binary, 0, image, user_id))
    conn.commit()
    new_report_id = cursor.lastrowid
    matches = []
    email_sent = False

    if status == "Lost":
        matches = check_for_matches(description, "Found", category=category, exclude_id=new_report_id)
        
        # Send email to lost item reporter about found matches
        for match in matches:
            email_body = create_lost_item_found_email(name, match[3], match[1], match[2])
            send_email(contact, "🎉 Your lost item might be found!", email_body, is_html=True)
            
            # Also send email to the finder that a matching lost item has been reported
            finder_email_body = create_found_item_match_email(match[1], description, name, contact, secret or "No secret provided")
            send_email(match[2], "🔔 A matching lost item has been reported", finder_email_body, is_html=True)
        
        if matches:
            email_sent = True

    else:  # status == "Found"
        matches = check_for_matches(description, "Lost", category=category, exclude_id=new_report_id)
        
        # Send individual emails to each person who lost an item
        for lost in matches:
            email_body = create_lost_item_found_email(lost[1], description, name, contact)
            send_email(lost[2], "🎉 Your lost item might be found!", email_body, is_html=True)
        
        # Send a summary email to finder with all matched lost items
        if matches and len(matches) > 0:
            matches_details = ""
            for i, lost in enumerate(matches):
                # lost is a tuple: (id, name, contact, description, status, timestamp, resolved, secret, category, embedding)
                lost_secret = lost[7] if len(lost) > 7 and lost[7] else "No secret provided"
                # Get embeddings and compute similarity
                item_embedding = None
                if lost[9] is not None and len(lost) > 9:  # Check if embedding exists in database
                    item_embedding = np.frombuffer(lost[9], dtype=np.float32)
                else:
                    item_embedding = generate_embedding(lost[3])
                    
                similarity_score = compute_similarity(embedding, item_embedding)
                
                matches_details += f"""
                <div class="match-item">
                    <h4>Match #{i+1}</h4>
                    <p><strong>Description:</strong> {lost[3]}</p>
                    <p><strong>Reported By:</strong> {lost[1]}</p>
                    <p><strong>Contact:</strong> {lost[2]}</p>
                    <p><strong>Secret Detail:</strong> {lost_secret}</p>
                    <p><strong>Match Score:</strong> {similarity_score:.1f}%</p>
                </div>
                """
            
            summary_body = create_finder_summary_email(name, len(matches), matches_details)
            send_email(contact, f"🔍 Your found item matches {len(matches)} lost reports", summary_body, is_html=True)
            email_sent = True

    if matches:
        ids = tuple([new_report_id] + [m[0] for m in matches])
        qmarks = ','.join(['?'] * len(ids))
        # Update matched status instead of resolved
        cursor.execute(f"UPDATE reports SET matched = 1 WHERE id IN ({qmarks})", ids)
        conn.commit()

    conn.close()
    return matches, email_sent, category

def get_reports():
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, contact, description, status, timestamp, resolved, secret, category, embedding, matched, image FROM reports ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ------------------- Context Processor -------------------
@app.context_processor
def inject_admin_status():
    """Make admin_logged_in available in all templates - checks database"""
    is_admin = False
    user_id = session.get('user_id')
    if user_id:
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        is_admin = result and result[0] == 1
    return dict(admin_logged_in=is_admin)

# ------------------- Admin Login Route -------------------
@app.route('/admin/login')
def admin_login():
    """Admin login page - redirects to dashboard if already logged in"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    return render_template('admin_login.html')

# ------------------- Routes -------------------
@app.route('/favicon.ico')
def favicon():
    return '', 204  # Return no content for favicon to avoid 404 errors

@app.route('/')
def index():
    # Check if user is logged in
    if session.get('user_logged_in'):
        return render_template('index.html')
    else:
        # Redirect to login if not logged in
        return redirect(url_for('login'))

@app.route('/home')
@login_required
def home():
    return render_template('index.html')

@app.route('/report')
@login_required
def report():
    return render_template('report.html')

@app.route('/search')
@login_required
def search():
    return render_template('search.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/api/report', methods=['POST'])
@api_login_required
def report_item():
    try:
        data = request.get_json()
        name = data.get('name')
        contact = data.get('contact')
        description = data.get('description')
        status = data.get('status')
        secret = data.get('secret', '')
        
        # Handle image upload if present
        image_data = None
        if 'image' in data and data['image']:
            # Convert base64 image to bytes
            image_data = base64.b64decode(data['image'].split(',')[1])
        
        # Get current user ID
        user_id = session.get('user_id')
        
        matches, email_sent, category = add_report(name, contact, description, status, secret, image_data, user_id)
        
        return jsonify({
            'success': True,
            'message': f'{status} item report submitted successfully!',
            'category': category,
            'matches': len(matches),
            'email_sent': email_sent,
            'match_details': [{'description': m[3], 'contact': m[2], 'name': m[1]} for m in matches]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/search/refresh', methods=['POST'])
def refresh_search():
    """Force refresh search results - clears any potential cache"""
    try:
        all_reports = get_reports()
        return jsonify({'success': True, 'message': f'Search refreshed - {len(all_reports)} reports available'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/search', methods=['POST'])
def search_items():
    try:
        data = request.get_json()
        search_query = data.get('query', '')
        
        all_reports = get_reports()
        results = []
        
        if search_query.lower() == "lost":
            for r in all_reports:
                if r[4] == "Lost":
                    results.append((r, 100))
        elif search_query.lower() == "found":
            for r in all_reports:
                if r[4] == "Found":
                    results.append((r, 100))
        elif search_query.lower() == "all":
            for r in all_reports:
                results.append((r, 100))
        else:
            query_embedding = generate_embedding(search_query)
            
            for r in all_reports:
                similarity_score = 0
                if len(r) > 9 and r[9] is not None:
                    item_embedding = np.frombuffer(r[9], dtype=np.float32)
                    similarity_score = compute_similarity(query_embedding, item_embedding)
                else:
                    item_embedding = generate_embedding(r[3])
                    similarity_score = compute_similarity(query_embedding, item_embedding)
                    
                if similarity_score > 75:
                    results.append((r, similarity_score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        formatted_results = []
        for r, score in results:
            image_base64 = None
            if len(r) > 11 and r[11] is not None:
                image_base64 = base64.b64encode(r[11]).decode('utf-8')
            
            formatted_results.append({
                'id': r[0],
                'name': r[1],
                'contact': r[2],
                'description': r[3],
                'status': r[4],
                'timestamp': r[5],
                'resolved': r[6] if len(r) > 6 else 0,
                'category': r[8] if len(r) > 8 else None,
                'secret': r[7] if len(r) > 7 else None,
                'score': score,
                'image': image_base64
            })
        
        return jsonify({'success': True, 'results': formatted_results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/chat', methods=['POST'])
def send_chat():
    try:
        data = request.get_json()
        sender_name = data.get('sender_name')
        sender_email = data.get('sender_email')
        receiver_email = data.get('receiver_email')
        message = data.get('message')
        
        if not EMAIL_CONFIGURED:
            return jsonify({
                'success': False, 
                'message': 'Email not configured. Please set up EMAIL_ADDRESS and EMAIL_PASSWORD in .env file to send messages.'
            })
        
        body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 20px; }}
        .message-box {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; }}
        .sender-info {{ background-color: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📧 Message from Item Recovery Portal</h2>
        </div>
        
        <div class="sender-info">
            <h3>From: {sender_name}</h3>
            <p><strong>Email:</strong> {sender_email}</p>
        </div>
        
        <div class="message-box">
            <h3>Message:</h3>
            <p>{message}</p>
        </div>
        
        <p style="text-align: center; color: #666; margin-top: 30px;">
            <em>This message was sent through Item Recovery Portal</em>
        </p>
    </div>
</body>
</html>
"""
        success = send_email(receiver_email, "Message from Item Recovery Portal", body, is_html=True)
        
        return jsonify({
            'success': success, 
            'message': 'Message sent successfully!' if success else 'Failed to send message. Check email configuration.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/change-password', methods=['POST'])
@api_login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': 'Please provide both current and new password'})
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'New password must be at least 6 characters long'})
        
        # Get user info from session
        user_id = session.get('user_id')
        user_email = session.get('user_email')
        
        if not user_id or not user_email:
            return jsonify({'success': False, 'message': 'User session not found'})
        
        # Connect to database
        conn = sqlite3.connect('lost_found.db')
        cursor = conn.cursor()
        
        # Get current password hash from database
        cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'})
        
        stored_password_hash = result[0]
        
        # Verify current password
        if not verify_password(current_password, stored_password_hash):
            conn.close()
            return jsonify({'success': False, 'message': 'Current password is incorrect'})
        
        # Hash new password
        new_password_hash = hash_password(new_password)
        
        # Update password in database
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, user_id))
        conn.commit()
        
        # Get user's full name and email for notification
        cursor.execute('SELECT full_name, email FROM users WHERE id = ?', (user_id,))
        user_info = cursor.fetchone()
        conn.close()
        
        # Send password change notification email
        if EMAIL_CONFIGURED and user_info:
            full_name, user_email = user_info
            change_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            email_body = create_password_change_notification_email(full_name, change_time)
            send_email(user_email, "🔐 Password Changed Successfully - Item Recovery Portal", email_body, is_html=True)
        return jsonify({'success': True, 'message': 'Password changed successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred while changing password'})

@app.route('/admin')
@admin_required
def admin():
    """Admin dashboard - only accessible to authenticated admins"""
    return render_template('admin.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login_api():
    """API endpoint for admin login - requires email and password, checks database for admin role"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'})
        
        # Check if email exists and is admin
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, password_hash, full_name, is_admin, is_verified, is_active 
            FROM users 
            WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid email or password'})
        
        user_id, password_hash, full_name, is_admin, is_verified, is_active = user
        
        # Check if account is active
        if not is_active:
            conn.close()
            return jsonify({'success': False, 'message': 'Account is deactivated. Please contact support.'})
        
        # Check if email is verified
        if not is_verified:
            conn.close()
            return jsonify({'success': False, 'message': 'Please verify your email before logging in.'})
        
        # Verify password
        if not verify_password(password, password_hash):
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid email or password'})
        
        # Check if user is admin
        if not is_admin:
            conn.close()
            return jsonify({'success': False, 'message': 'Access denied. This account does not have admin privileges.'})
        
        # Update last login
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                      (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        conn.close()
        
        # Set session variables
        session['user_logged_in'] = True
        session['user_id'] = user_id
        session['user_email'] = email
        session['user_name'] = full_name
        session['admin_logged_in'] = True  # Keep for backward compatibility
        
        return jsonify({
            'success': True,
            'message': 'Admin login successful!',
            'user': {
                'id': user_id,
                'email': email,
                'full_name': full_name
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login error: {str(e)}'})

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Admin logout - clears all session variables"""
    # Clear all session variables for complete logout
    session.pop('admin_logged_in', None)
    session.pop('user_logged_in', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/admin/reports')
@admin_required
def admin_reports():
    """Get all reports for admin dashboard"""
    
    try:
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, contact, description, status, timestamp, resolved, secret, category, embedding, matched, image FROM reports ORDER BY timestamp DESC")
        reports_data = cursor.fetchall()
        conn.close()
        
        reports = []
        for report_tuple in reports_data:
            image_base64 = None
            if len(report_tuple) > 11 and report_tuple[11] is not None:
                image_base64 = base64.b64encode(report_tuple[11]).decode('utf-8')
            
            reports.append({
                'id': report_tuple[0],
                'name': report_tuple[1],
                'contact': report_tuple[2],
                'description': report_tuple[3],
                'status': report_tuple[4],
                'timestamp': report_tuple[5],
                'resolved': report_tuple[6],
                'secret': report_tuple[7],
                'category': report_tuple[8],
                'matched': report_tuple[10],
                'image': image_base64
            })
        
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/delete/<int:report_id>', methods=['DELETE'])
@admin_required
def delete_report(report_id):
    """Delete a report - admin only"""
    
    try:
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        # First check if the report exists
        cursor.execute("SELECT id FROM reports WHERE id = ?", (report_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': f'Report {report_id} not found'})
        
        # Delete the report
        cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()
        
        # Verify the report was deleted
        cursor.execute("SELECT id FROM reports WHERE id = ?", (report_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': f'Failed to delete report {report_id}'})
        
        conn.close()
        return jsonify({'success': True, 'message': f'Report {report_id} deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user/delete-report/<int:report_id>', methods=['DELETE'])
@api_login_required
def user_delete_report(report_id):
    """Allow users to delete their own reports"""
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User not logged in'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        # Check if report exists and belongs to user
        cursor.execute("SELECT id, user_id FROM reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            conn.close()
            return jsonify({'success': False, 'message': 'Report not found'})
        
        report_user_id = report[1]
        
        # Verify ownership
        if report_user_id != user_id:
            conn.close()
            return jsonify({'success': False, 'message': 'You can only delete your own reports'})
        
        # Delete the report
        cursor.execute("DELETE FROM reports WHERE id = ? AND user_id = ?", (report_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Report deleted successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user/edit-report/<int:report_id>', methods=['PUT'])
@api_login_required
def user_edit_report(report_id):
    """Allow users to edit their own reports"""
    try:
        user_id = session.get('user_id')
        data = request.get_json()
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User not logged in'})
        
        # Get fields from request
        name = data.get('name')
        contact = data.get('contact')
        description = data.get('description')
        secret = data.get('secret', '')
        image_base64 = data.get('image')  # optional data URL
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        # Check if report exists and belongs to user
        cursor.execute("SELECT id, user_id FROM reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            conn.close()
            return jsonify({'success': False, 'message': 'Report not found'})
        
        report_user_id = report[1]
        
        # Verify ownership
        if report_user_id != user_id:
            conn.close()
            return jsonify({'success': False, 'message': 'You can only edit your own reports'})
        
        # Prepare updates: recompute category and embedding if description provided
        updated_description = description.strip().lower() if description else None
        updated_category = detect_item_category(updated_description) if updated_description else None
        updated_embedding = generate_embedding(updated_description) if updated_description else None
        embedding_binary = updated_embedding.tobytes() if updated_embedding is not None else None
        
        # Optional image decode
        image_bytes = None
        if image_base64:
            try:
                # Expect data URL like 'data:image/jpeg;base64,....'
                image_bytes = base64.b64decode(image_base64.split(',')[1] if ',' in image_base64 else image_base64)
            except Exception:
                image_bytes = None
        
        # Build dynamic SQL to avoid overwriting when not provided (defensive)
        update_fields = ["name = ?", "contact = ?", "description = ?", "secret = ?"]
        params = [name.strip(), contact.strip(), updated_description, secret]
        
        if embedding_binary is not None:
            update_fields.append("embedding = ?")
            params.append(embedding_binary)
        if updated_category is not None:
            update_fields.append("category = ?")
            params.append(updated_category)
        if image_bytes is not None:
            update_fields.append("image = ?")
            params.append(image_bytes)
        
        params.extend([report_id, user_id])
        sql = f"UPDATE reports SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?"
        cursor.execute(sql, tuple(params))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Report updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/resolve/<int:report_id>', methods=['PUT'])
@admin_required
def resolve_report(report_id):
    """Resolve a report - admin only"""
    
    try:
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE reports SET resolved = 1 WHERE id = ?", (report_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Report {report_id} marked as resolved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/notify', methods=['POST'])
@admin_required
def send_notification():
    """Send notification - admin only"""
    
    try:
        data = request.get_json()
        contact = data.get('contact')
        message = data.get('message')
        
        if not EMAIL_CONFIGURED:
            return jsonify({
                'success': False, 
                'message': 'Email not configured. Please set up EMAIL_ADDRESS and EMAIL_PASSWORD in .env file to send notifications.'
            })
        
        notification_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 20px; }}
        .message-box {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #e74c3c; }}
        .admin-info {{ background-color: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #ffeaa7; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🔔 Item Recovery Portal Notification</h2>
        </div>
        
        <div class="admin-info">
            <h3>📋 Admin Message</h3>
            <p><em>This is an official notification from the Item Recovery Portal administrators.</em></p>
        </div>
        
        <div class="message-box">
            <h3>Message:</h3>
            <p>{message}</p>
        </div>
        
        <p style="text-align: center; color: #666; margin-top: 30px;">
            <em>Item Recovery Portal System</em>
        </p>
    </div>
</body>
</html>
"""
        success = send_email(contact, "Item Recovery Portal Notification", notification_body, is_html=True)
        return jsonify({
            'success': success, 
            'message': 'Notification sent successfully!' if success else 'Failed to send notification. Check email configuration.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def get_stats():
    """Helper function to get statistics from database"""
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'Lost'")
    lost_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'Found'")
    found_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE resolved = 1")
    resolved_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reports WHERE matched = 1")
    matched_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_reports': total_reports,
        'lost_count': lost_count,
        'found_count': found_count,
        'resolved_count': resolved_count,
        'matched_count': matched_count
    }

@app.route('/api/stats')
def public_stats():
    """Public stats endpoint for homepage pie charts"""
    try:
        stats = get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Get admin statistics - admin only"""
    
    try:
        stats = get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ------------------- Authentication Routes -------------------
@app.route('/login')
def login():
    if session.get('user_logged_in'):
        return redirect(url_for('home'))
    return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/signup')
def signup():
    if session.get('user_logged_in'):
        return redirect(url_for('home'))
    return render_template('signup.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/verify')
def verify():
    if session.get('user_logged_in'):
        return redirect(url_for('home'))
    return render_template('verify.html')

@app.route('/api/signup', methods=['POST'])
def user_signup():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        student_id = data.get('student_id', '').strip()
        phone = data.get('phone', '').strip()
        
        # Validation
        if not email or not password or not full_name:
            return jsonify({'success': False, 'message': 'Email, password, and full name are required'})
        
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters long'})
        
        # Check if email already exists
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Email already registered. Please use a different email or try logging in.'})
        
        # Hash password and create user
        password_hash = hash_password(password)
        verification_code = generate_verification_code()
        verification_expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, student_id, phone, verification_code, verification_expires)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (email, password_hash, full_name, student_id, phone, verification_code, verification_expires))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Send verification email
        if EMAIL_CONFIGURED:
            email_body = create_verification_email(full_name, verification_code)
            email_sent = send_email(email, "📧 Verify Your Email - Item Recovery Portal", email_body, is_html=True)
            
            if email_sent:
                return jsonify({
                    'success': True, 
                    'message': 'Account created successfully! Please check your email for verification code.',
                    'user_id': user_id
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': 'Account created but failed to send verification email. Please contact support.'
                })
        else:
            # Auto-verify user when email is not configured
            conn = sqlite3.connect("lost_found.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True, 
                'message': 'Account created successfully! You can now login.',
                'user_id': user_id
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/verify', methods=['POST'])
def verify_email():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        verification_code = data.get('verification_code', '').strip()
        
        if not email or not verification_code:
            return jsonify({'success': False, 'message': 'Email and verification code are required'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, full_name, verification_code, verification_expires 
            FROM users 
            WHERE email = ? AND is_verified = 0
        """, (email,))
        
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid email or account already verified'})
        
        user_id, full_name, stored_code, expires_str = user
        
        # Check if code is expired
        expires = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expires:
            conn.close()
            return jsonify({'success': False, 'message': 'Verification code has expired. Please request a new one.'})
        
        # Verify code
        if verification_code != stored_code:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid verification code'})
        
        # Mark as verified
        cursor.execute("UPDATE users SET is_verified = 1, verification_code = NULL, verification_expires = NULL WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        # Send welcome email
        if EMAIL_CONFIGURED:
            welcome_body = create_welcome_email(full_name)
            send_email(email, "🎉 Welcome to Item Recovery Portal!", welcome_body, is_html=True)
        
        return jsonify({
            'success': True, 
            'message': 'Email verified successfully! You can now log in.',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/login', methods=['POST'])
def user_login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, password_hash, full_name, is_verified, is_active, is_admin, COALESCE(auth_provider, 'email') as auth_provider
            FROM users 
            WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid email or password'})
        
        user_id, password_hash, full_name, is_verified, is_active, is_admin, auth_provider = user
        
        if not is_active:
            conn.close()
            return jsonify({'success': False, 'message': 'Account is deactivated. Please contact support.'})
        
        # Check if user is OAuth-only (placeholder password)
        if password_hash == 'oauth_user_no_password' or not password_hash or password_hash.strip() == '':
            conn.close()
            return jsonify({'success': False, 'message': 'This account uses Google Sign-In. Please use "Continue with Google" to log in.'})
        
        if not verify_password(password, password_hash):
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid email or password'})
        
        if not is_verified:
            conn.close()
            return jsonify({'success': False, 'message': 'Please verify your email before logging in.'})
        
        # Update last login
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        conn.close()
        
        # Set session
        session['user_logged_in'] = True
        session['user_id'] = user_id
        session['user_email'] = email
        session['user_name'] = full_name
        # Set admin status if user is admin
        if is_admin:
            session['admin_logged_in'] = True
        
        return jsonify({
            'success': True, 
            'message': 'Login successful!',
            'user': {
                'id': user_id,
                'email': email,
                'full_name': full_name
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logout', methods=['POST'])
def user_logout():
    session.pop('user_logged_in', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('admin_logged_in', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/user/info')
@api_login_required
def get_user_info():
    """Get current user information"""
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User not logged in'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT full_name, email, student_id, phone 
            FROM users 
            WHERE id = ?
        """, (user_id,))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            full_name, email, student_id, phone = user_data
            return jsonify({
                'success': True,
                'user': {
                    'full_name': full_name,
                    'email': email,
                    'student_id': student_id,
                    'phone': phone
                }
            })
        else:
            return jsonify({'success': False, 'message': 'User not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user/reports')
@api_login_required
def get_user_reports():
    """Get all reports submitted by the current user"""
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User not logged in'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, contact, description, status, timestamp, resolved, secret, category, matched, image 
            FROM reports 
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """, (user_id,))
        
        reports_data = cursor.fetchall()
        conn.close()
        
        reports = []
        for report_tuple in reports_data:
            image_base64 = None
            if len(report_tuple) > 10 and report_tuple[10] is not None:
                image_base64 = base64.b64encode(report_tuple[10]).decode('utf-8')
            
            # Determine status text
            status_text = "Pending"
            if report_tuple[6] == 1:  # resolved
                status_text = "Resolved"
            elif report_tuple[9] == 1:  # matched
                status_text = "Matched"
            
            reports.append({
                'id': report_tuple[0],
                'name': report_tuple[1],
                'contact': report_tuple[2],
                'description': report_tuple[3],
                'status': report_tuple[4],
                'timestamp': report_tuple[5],
                'resolved': report_tuple[6],
                'secret': report_tuple[7],
                'category': report_tuple[8],
                'matched': report_tuple[9],
                'image': image_base64,
                'status_text': status_text
            })
        
        return jsonify({
            'success': True,
            'reports': reports
        })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset email"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'})
        
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})
        
        # Check if email exists
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Email not found in our system'})
        
        user_id, full_name = user
        
        # Generate verification code
        reset_code = str(random.randint(100000, 999999))
        reset_expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Store reset code
        cursor.execute("UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?", 
                      (reset_code, reset_expires, user_id))
        conn.commit()
        conn.close()
        
        # Send reset email with code
        if EMAIL_CONFIGURED:
            email_body = create_password_reset_code_email(full_name, reset_code)
            
            email_sent = send_email(email, "🔒 Password Reset Code - Item Recovery Portal", email_body, is_html=True)
            
            if email_sent:
                return jsonify({'success': True, 'message': 'Password reset code sent! Check your email.'})
            else:
                return jsonify({'success': False, 'message': 'Failed to send reset code. Please try again.'})
        else:
            return jsonify({'success': False, 'message': 'Email service not configured. Please contact administrator.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """Verify the password reset code"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        
        if not email or not code:
            return jsonify({'success': False, 'message': 'Email and code are required'})
        
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})
        
        # Check if code is valid
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, reset_expires FROM users WHERE email = ? AND reset_token = ?", (email, str(code)))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid verification code. Please check your email and try again.'})
        
        user_id, reset_expires = user
        
        # Check if code is expired
        try:
            expiry_time = datetime.strptime(reset_expires, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry_time:
                conn.close()
                return jsonify({'success': False, 'message': 'Verification code has expired. Please request a new one.'})
        except:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid code format'})
        
        conn.close()
        return jsonify({'success': True, 'message': 'Code verified successfully. You can now reset your password.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Reset password with email and code"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        new_password = data.get('password', '')
        
        if not email or not code or not new_password:
            return jsonify({'success': False, 'message': 'Email, code, and password are required'})
        
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters long'})
        
        # Check code validity
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, reset_expires FROM users WHERE email = ? AND reset_token = ?", (email, str(code)))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid verification code. Please check your email and try again.'})
        
        user_id, reset_expires = user
        
        # Check if code is expired
        try:
            expiry_time = datetime.strptime(reset_expires, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry_time:
                conn.close()
                return jsonify({'success': False, 'message': 'Verification code has expired. Please request a new one.'})
        except:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid code format'})
        
        # Update password
        password_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ?, reset_token = NULL, reset_expires = NULL WHERE id = ?", 
                      (password_hash, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Password reset successfully! You can now login with your new password.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/verify-reset-code')
def verify_reset_code_page():
    """Verify reset code page"""
    return render_template('verify-reset-code.html')

@app.route('/reset-password')
def reset_password_page():
    """Password reset page"""
    return render_template('reset-password.html')

@app.route('/api/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'})
        
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, full_name, is_verified 
            FROM users 
            WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Email not found'})
        
        user_id, full_name, is_verified = user
        
        if is_verified:
            conn.close()
            return jsonify({'success': False, 'message': 'Account is already verified'})
        
        # Generate new verification code
        verification_code = generate_verification_code()
        verification_expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            UPDATE users 
            SET verification_code = ?, verification_expires = ? 
            WHERE id = ?
        """, (verification_code, verification_expires, user_id))
        
        conn.commit()
        conn.close()
        
        # Send verification email
        if EMAIL_CONFIGURED:
            email_body = create_verification_email(full_name, verification_code)
            email_sent = send_email(email, "📧 Verify Your Email - Item Recovery Portal", email_body, is_html=True)
            
            if email_sent:
                return jsonify({'success': True, 'message': 'Verification code sent to your email'})
            else:
                return jsonify({'success': False, 'message': 'Failed to send verification email'})
        else:
            return jsonify({'success': False, 'message': 'Email service not configured'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ------------------- Google OAuth Routes -------------------
@app.route('/api/google-auth/verify', methods=['POST'])
def google_auth_verify():
    """Verify Google ID token and create/login user"""
    try:
        if not GOOGLE_CONFIGURED:
            return jsonify({'success': False, 'message': 'Google authentication is not configured'})
        
        data = request.get_json()
        token = data.get('credential')  # Google ID token
        
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'})
        
        # Verify the token
        try:
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                GOOGLE_CLIENT_ID
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                return jsonify({'success': False, 'message': 'Invalid token issuer'})
            
        except ValueError as e:
            return jsonify({'success': False, 'message': f'Invalid token: {str(e)}'})
        
        # Extract user information
        google_id = idinfo['sub']
        email = idinfo.get('email', '').strip().lower()
        full_name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email not provided by Google'})
        
        # Check if user exists
        conn = sqlite3.connect("lost_found.db")
        cursor = conn.cursor()
        
        # First check by google_id
        cursor.execute("""
            SELECT id, email, full_name, is_verified, is_active, is_admin, auth_provider 
            FROM users 
            WHERE google_id = ?
        """, (google_id,))
        
        user = cursor.fetchone()
        
        if user:
            # User exists with this Google ID
            user_id, user_email, user_name, is_verified, is_active, is_admin, auth_provider = user
            
            if not is_active:
                conn.close()
                return jsonify({'success': False, 'message': 'Account is deactivated. Please contact support.'})
            
            # Update last login and ensure verified (Google accounts are auto-verified)
            cursor.execute("""
                UPDATE users 
                SET last_login = ?, is_verified = 1, email = ?, full_name = ?
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, full_name, user_id))
            conn.commit()
            conn.close()
            
            # Set session
            session['user_logged_in'] = True
            session['user_id'] = user_id
            session['user_email'] = email
            session['user_name'] = full_name
            # Set admin status if user is admin
            if is_admin:
                session['admin_logged_in'] = True
            
            return jsonify({
                'success': True,
                'message': 'Login successful!',
                'user': {
                    'id': user_id,
                    'email': email,
                    'full_name': full_name
                }
            })
        else:
            # Check if user exists with this email (but different auth method)
            cursor.execute("""
                SELECT id, email, full_name, is_verified, is_active, is_admin, auth_provider, password_hash
                FROM users 
                WHERE email = ?
            """, (email,))
            
            existing_user = cursor.fetchone()
            
            if existing_user:
                # User exists with email but not Google ID - link accounts
                user_id, user_email, user_name, is_verified, is_active, is_admin, auth_provider, password_hash = existing_user
                
                if not is_active:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Account is deactivated. Please contact support.'})
                
                # Get admin status before updating
                cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                admin_result = cursor.fetchone()
                is_admin = admin_result and admin_result[0] == 1
                
                # Link Google account to existing email account
                cursor.execute("""
                    UPDATE users 
                    SET google_id = ?, auth_provider = 'both', last_login = ?, is_verified = 1, full_name = ?
                    WHERE id = ?
                """, (google_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), full_name, user_id))
                conn.commit()
                conn.close()
                
                # Set session
                session['user_logged_in'] = True
                session['user_id'] = user_id
                session['user_email'] = email
                session['user_name'] = full_name
                # Set admin status if user is admin
                if is_admin:
                    session['admin_logged_in'] = True
                
                return jsonify({
                    'success': True,
                    'message': 'Google account linked successfully!',
                    'user': {
                        'id': user_id,
                        'email': email,
                        'full_name': full_name
                    }
                })
            else:
                # New user - create account
                # For OAuth users, use a placeholder password_hash (NOT NULL constraint)
                cursor.execute("""
                    INSERT INTO users (email, password_hash, full_name, google_id, auth_provider, is_verified, created_at, last_login, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email,
                    'oauth_user_no_password',  # Placeholder for OAuth users (NOT NULL constraint)
                    full_name,
                    google_id,
                    'google',
                    1,  # Google accounts are auto-verified
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    1
                ))
                
                user_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                # Set session
                session['user_logged_in'] = True
                session['user_id'] = user_id
                session['user_email'] = email
                session['user_name'] = full_name
                
                # Send welcome email
                if EMAIL_CONFIGURED:
                    welcome_body = create_welcome_email(full_name)
                    send_email(email, "🎉 Welcome to Item Recovery Portal!", welcome_body, is_html=True)
                
                return jsonify({
                    'success': True,
                    'message': 'Account created and logged in successfully!',
                    'user': {
                        'id': user_id,
                        'email': email,
                        'full_name': full_name
                    }
                })
                
    except Exception as e:
        import traceback
        print(f"Google OAuth Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Authentication error: {str(e)}'})

@app.route('/api/google-auth/config')
def google_auth_config():
    """Return Google OAuth configuration for frontend"""
    return jsonify({
        'success': True,
        'configured': GOOGLE_CONFIGURED,
        'client_id': GOOGLE_CLIENT_ID if GOOGLE_CONFIGURED else None
    })

@app.route('/api/google-auth/exchange-code', methods=['POST'])
def exchange_google_code():
    """Exchange authorization code for ID token"""
    try:
        if not GOOGLE_CONFIGURED:
            return jsonify({'success': False, 'message': 'Google authentication is not configured'})
        
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'success': False, 'message': 'No authorization code provided'})
        
        # Exchange code for tokens using Google's token endpoint
        import requests
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': '',  # Not needed for public clients
            'redirect_uri': request.host_url.rstrip('/'),
            'grant_type': 'authorization_code'
        }
        
        # Note: For public clients (web apps), we need to use the ID token directly
        # The frontend should handle this, but we can also verify here
        return jsonify({
            'success': False,
            'message': 'Please use ID token flow instead. Use google.accounts.id.prompt() or renderButton().'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    init_db()
    import webbrowser
    import threading
    import time
    
    def open_browser():
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open('http://127.0.0.1:5000')
    
    # Start browser in a separate thread
    threading.Thread(target=open_browser).start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)