# Panzoto Encryption Backend

This document contains complete instructions for creating a separate backend service to handle user authentication and audio file decryption for the Panzoto Android app.

## Project Overview

The backend provides:
- User registration and authentication with password-derived encryption keys
- Audio file decryption service for transcription
- RESTful API endpoints for the Android app
- PostgreSQL database for user management

## Database Connection Details

**From Android Project Setup:**
- **Host**: `panzoto-dev.cjqb9dlo18fh.us-east-1.rds.amazonaws.com`
- **Username**: `panzoto`
- **Password**: `Rmger49Rmger49`
- **Database**: `postgres`
- **Port**: `5432`

**Tables already created:**
```sql
-- Users table with encryption key salts
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- Argon2 hash for login
    key_salt BYTEA NOT NULL,                -- For deriving encryption key
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audio files metadata
CREATE TABLE audio_files (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    s3_key VARCHAR(500) NOT NULL,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Backend Project Setup

### 1. Create New Project Directory
```bash
mkdir panzoto-backend
cd panzoto-backend
```

### 2. Project Structure
```
panzoto-backend/
├── app.py              # Flask main application
├── models.py           # Database models
├── auth.py             # Authentication logic
├── crypto_utils.py     # Encryption/decryption helpers
├── config.py           # Configuration
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
└── README.md          # Project documentation
```

### 3. Dependencies (requirements.txt)
```txt
flask==2.3.2
flask-sqlalchemy==3.0.5
flask-migrate==4.0.4
flask-cors==4.0.0
psycopg2-binary==2.9.6
argon2-cffi==21.3.0
cryptography==41.0.1
boto3==1.26.137
python-dotenv==1.0.0
PyJWT==2.8.0
```

### 4. Environment Configuration (.env)
```env
# Database
DATABASE_URL=postgresql://panzoto:Rmger49Rmger49@panzoto-dev.cjqb9dlo18fh.us-east-1.rds.amazonaws.com/postgres

# Flask
SECRET_KEY=your-secret-key-change-this-in-production
FLASK_ENV=development

# AWS (for S3 access)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET=panzoto-audio-dev
```

### 5. Configuration (config.py)
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'panzoto-audio-dev')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
```

### 6. Database Models (models.py)
```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    key_salt = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    audio_files = db.relationship('AudioFile', backref='user', lazy=True)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class AudioFile(db.Model):
    __tablename__ = 'audio_files'

    file_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    s3_key = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'file_id': self.file_id,
            'user_id': self.user_id,
            's3_key': self.s3_key,
            'file_size': self.file_size,
            'uploaded_at': self.uploaded_at.isoformat()
        }
```

### 7. Authentication (auth.py)
```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password for database storage using Argon2"""
    return ph.hash(password)

def verify_password(password: str, hash: str) -> bool:
    """Verify password against stored Argon2 hash"""
    try:
        ph.verify(hash, password)
        return True
    except VerifyMismatchError:
        return False

def generate_key_salt() -> bytes:
    """Generate random salt for key derivation (32 bytes)"""
    return secrets.token_bytes(32)

def generate_jwt_token(user_id: str) -> str:
    """Generate JWT token for user authentication"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=30),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_jwt_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to require JWT token for API endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401

        request.current_user_id = payload['user_id']
        return f(*args, **kwargs)

    return decorated
```

### 8. Encryption Utilities (crypto_utils.py)
```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import tempfile

class AudioDecryptor:
    """Handles decryption of audio files encrypted by Panzoto Android app"""

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2 (matches Android implementation)

        Args:
            password: User's password
            salt: 32-byte salt from database

        Returns:
            32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=100000,  # Must match Android PBKDF2_ITERATIONS
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    @staticmethod
    def decrypt_audio_file(encrypted_file_path: str, output_file_path: str,
                          password: str, salt: bytes) -> bool:
        """
        Decrypt audio file encrypted by Panzoto Android app

        Args:
            encrypted_file_path: Path to encrypted file
            output_file_path: Path where decrypted file will be saved
            password: User's password
            salt: Key derivation salt from database

        Returns:
            True if decryption successful, False otherwise
        """
        try:
            # Derive the same key used by Android app
            key = AudioDecryptor.derive_key_from_password(password, salt)

            with open(encrypted_file_path, 'rb') as encrypted_file:
                # Read the first 12 bytes as IV (matches Android implementation)
                iv = encrypted_file.read(12)
                if len(iv) != 12:
                    raise ValueError("Invalid file format: IV should be 12 bytes")

                # Read the rest as encrypted data + auth tag
                encrypted_data = encrypted_file.read()

            # Create AES-GCM cipher (matches Android "AES/GCM/NoPadding")
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Decrypt the data
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

            # Write decrypted data to output file
            with open(output_file_path, 'wb') as output_file:
                output_file.write(decrypted_data)

            return True

        except Exception as e:
            print(f"Decryption failed: {str(e)}")
            return False

    @staticmethod
    def decrypt_to_temp_file(encrypted_file_path: str, password: str, salt: bytes) -> str:
        """
        Decrypt audio file to a temporary file for transcription processing

        Returns:
            Path to temporary decrypted file (caller must clean up)
        """
        temp_file = tempfile.NamedTemporaryFile(suffix='.3gp', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        if AudioDecryptor.decrypt_audio_file(encrypted_file_path, temp_path, password, salt):
            return temp_path
        else:
            os.unlink(temp_path)
            return None
```

### 9. Main Application (app.py)
```python
from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, User, AudioFile
from auth import hash_password, verify_password, generate_key_salt, generate_jwt_token, token_required
from crypto_utils import AudioDecryptor
from config import config
import os

def create_app(config_name=None):
    app = Flask(__name__)

    # Load configuration
    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])

    # Enable CORS for frontend integration
    CORS(app)

    # Initialize database
    db.init_app(app)

    # Routes
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({'status': 'healthy', 'service': 'panzoto-backend'})

    @app.route('/api/register', methods=['POST'])
    def register():
        """Register new user with email and password"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')

            # Validation
            if not email or not password:
                return jsonify({'error': 'Email and password are required'}), 400

            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400

            # Check if user already exists
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'User already exists'}), 409

            # Create new user
            password_hash = hash_password(password)
            key_salt = generate_key_salt()

            user = User(
                email=email,
                password_hash=password_hash,
                key_salt=key_salt
            )

            db.session.add(user)
            db.session.commit()

            # Generate JWT token
            token = generate_jwt_token(user.user_id)

            return jsonify({
                'token': token,
                'user_id': user.user_id,
                'key_salt': user.key_salt.hex(),  # Send salt for key derivation
                'user': user.to_dict()
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': 'Registration failed'}), 500

    @app.route('/api/login', methods=['POST'])
    def login():
        """Authenticate user with email and password"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')

            if not email or not password:
                return jsonify({'error': 'Email and password are required'}), 400

            # Find user
            user = User.query.filter_by(email=email).first()

            if not user or not verify_password(password, user.password_hash):
                return jsonify({'error': 'Invalid email or password'}), 401

            # Generate JWT token
            token = generate_jwt_token(user.user_id)

            return jsonify({
                'token': token,
                'user_id': user.user_id,
                'key_salt': user.key_salt.hex(),
                'user': user.to_dict()
            })

        except Exception as e:
            return jsonify({'error': 'Login failed'}), 500

    @app.route('/api/decrypt-audio', methods=['POST'])
    @token_required
    def decrypt_audio():
        """
        Decrypt user's audio file for transcription
        Requires: JWT token, password, file_id or s3_key
        """
        try:
            data = request.get_json()
            password = data.get('password')
            file_id = data.get('file_id')
            s3_key = data.get('s3_key')

            if not password:
                return jsonify({'error': 'Password required for decryption'}), 400

            if not file_id and not s3_key:
                return jsonify({'error': 'file_id or s3_key required'}), 400

            # Get user
            user = User.query.get(request.current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Verify password
            if not verify_password(password, user.password_hash):
                return jsonify({'error': 'Invalid password'}), 401

            # Get audio file record
            if file_id:
                audio_file = AudioFile.query.filter_by(
                    file_id=file_id,
                    user_id=user.user_id
                ).first()
            else:
                audio_file = AudioFile.query.filter_by(
                    s3_key=s3_key,
                    user_id=user.user_id
                ).first()

            if not audio_file:
                return jsonify({'error': 'Audio file not found'}), 404

            # TODO: Download from S3, decrypt, and return download URL
            # For now, return success with file info
            return jsonify({
                'status': 'ready_for_transcription',
                'file_info': audio_file.to_dict(),
                'message': 'File decryption would happen here'
            })

        except Exception as e:
            return jsonify({'error': 'Decryption failed'}), 500

    @app.route('/api/user/audio-files', methods=['GET'])
    @token_required
    def get_user_audio_files():
        """Get list of user's audio files"""
        try:
            audio_files = AudioFile.query.filter_by(
                user_id=request.current_user_id
            ).order_by(AudioFile.uploaded_at.desc()).all()

            return jsonify({
                'audio_files': [file.to_dict() for file in audio_files]
            })

        except Exception as e:
            return jsonify({'error': 'Failed to retrieve audio files'}), 500

    return app

# Application factory
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist (they should already exist from Android setup)
        db.create_all()

    app.run(debug=True, host='0.0.0.0', port=5000)
```

### 10. Installation and Setup
```bash
# Clone or create the backend project
cd panzoto-backend

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your actual values

# Run the application
python app.py
```

### 11. API Usage Examples

#### Register User:
```bash
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

#### Login:
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

#### Access Protected Endpoint:
```bash
curl -X GET http://localhost:5000/api/user/audio-files \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Android App Integration

### Update Android App API Base URL
```kotlin
// In your Android app
private const val API_BASE_URL = "http://your-backend-server:5000/api"
```

### Authentication Flow
1. User registers/logs in through Android app
2. App sends request to backend `/api/register` or `/api/login`
3. Backend returns JWT token and key salt
4. App derives encryption key from password + salt
5. App uses JWT token for authenticated requests

## Deployment Options

### Development
- Run locally: `python app.py`
- Access at: `http://localhost:5000`

### Production Options
- **AWS Lambda + API Gateway**: Serverless deployment
- **AWS ECS**: Containerized deployment
- **Heroku**: Simple platform deployment
- **DigitalOcean App Platform**: Managed deployment

## Security Notes

1. **Environment Variables**: Never commit `.env` file to version control
2. **HTTPS**: Use HTTPS in production (never HTTP)
3. **CORS**: Configure CORS properly for your frontend domain
4. **Rate Limiting**: Add rate limiting for API endpoints
5. **Input Validation**: Validate all input data
6. **SQL Injection**: SQLAlchemy ORM provides protection
7. **Password Storage**: Argon2 is currently the best practice

## Next Steps for Android Integration

1. Create this backend project separately
2. Deploy it to a server (local or cloud)
3. Update Android app to call these API endpoints
4. Test user registration and authentication
5. Implement audio file upload tracking
6. Add transcription service integration

This backend provides the foundation for secure, per-user encryption keys while maintaining compatibility with your existing Android app architecture.