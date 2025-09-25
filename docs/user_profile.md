# User Profile Management with DynamoDB

This document provides complete setup instructions for migrating from RDS PostgreSQL to DynamoDB for user authentication and audio file management in the Panzoto backend.

## Why DynamoDB?

### Cost Benefits:
- **Pay-per-request**: Only pay for actual database operations
- **No always-running instances**: Unlike RDS, no base monthly cost
- **Automatic scaling**: Scales to zero when not in use
- **Serverless-friendly**: Perfect for Lambda functions

### Estimated Costs:
- **Development**: $1-5/month (vs $15-25/month for RDS db.t3.micro)
- **Light production**: $5-20/month
- **Heavy usage**: Still typically much cheaper than RDS

## Table Design

### User Profile Table: `panzoto-users`

```json
{
  "TableName": "panzoto-users",
  "AttributeDefinitions": [
    {
      "AttributeName": "user_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "email",
      "AttributeType": "S"
    }
  ],
  "KeySchema": [
    {
      "AttributeName": "user_id",
      "KeyType": "HASH"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "email-index",
      "KeySchema": [
        {
          "AttributeName": "email",
          "KeyType": "HASH"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

### Audio Files Table: `panzoto-audio-files`

```json
{
  "TableName": "panzoto-audio-files",
  "AttributeDefinitions": [
    {
      "AttributeName": "file_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "user_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "uploaded_at",
      "AttributeType": "N"
    }
  ],
  "KeySchema": [
    {
      "AttributeName": "file_id",
      "KeyType": "HASH"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "user-files-index",
      "KeySchema": [
        {
          "AttributeName": "user_id",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "uploaded_at",
          "KeyType": "RANGE"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

## Setup Steps

### 1. AWS Account Setup (10 minutes)

#### Create DynamoDB Tables:

```bash
# Create Users table
aws dynamodb create-table \
    --table-name panzoto-users \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=email,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
    --global-secondary-indexes \
        IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL} \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Create Audio Files table
aws dynamodb create-table \
    --table-name panzoto-audio-files \
    --attribute-definitions \
        AttributeName=file_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=uploaded_at,AttributeType=N \
    --key-schema \
        AttributeName=file_id,KeyType=HASH \
    --global-secondary-indexes \
        IndexName=user-files-index,KeySchema=[{AttributeName=user_id,KeyType=HASH},{AttributeName=uploaded_at,KeyType=RANGE}],Projection={ProjectionType=ALL} \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

#### Verify Tables Created:
```bash
aws dynamodb list-tables --region us-east-1
aws dynamodb describe-table --table-name panzoto-users --region us-east-1
aws dynamodb describe-table --table-name panzoto-audio-files --region us-east-1
```

### 2. Backend Dependencies Update

#### Update `requirements.txt`:
```txt
flask==2.3.2
flask-cors==4.0.0
boto3==1.28.57
argon2-cffi==21.3.0
cryptography==41.0.1
python-dotenv==1.0.0
PyJWT==2.8.0
uuid==1.30
```

#### Environment Configuration (`.env`):
```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# DynamoDB Tables
USERS_TABLE=panzoto-users
AUDIO_FILES_TABLE=panzoto-audio-files

# Flask
SECRET_KEY=your-secret-key-change-this-in-production
FLASK_ENV=development

# S3 (if still using for audio storage)
S3_BUCKET=panzoto-audio-dev
```

### 3. Database Models (`models.py`)

```python
import boto3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from botocore.exceptions import ClientError
import os

class DynamoDBConnection:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        self.users_table = self.dynamodb.Table(os.getenv('USERS_TABLE', 'panzoto-users'))
        self.audio_files_table = self.dynamodb.Table(os.getenv('AUDIO_FILES_TABLE', 'panzoto-audio-files'))

db = DynamoDBConnection()

class User:
    def __init__(self, user_id: str = None, email: str = None, password_hash: str = None,
                 key_salt: bytes = None, created_at: datetime = None):
        self.user_id = user_id or str(uuid.uuid4())
        self.email = email
        self.password_hash = password_hash
        self.key_salt = key_salt
        self.created_at = created_at or datetime.utcnow()

    def save(self) -> bool:
        """Save user to DynamoDB"""
        try:
            # Convert bytes to base64 string for DynamoDB storage
            import base64
            key_salt_b64 = base64.b64encode(self.key_salt).decode('utf-8') if self.key_salt else None

            db.users_table.put_item(
                Item={
                    'user_id': self.user_id,
                    'email': self.email,
                    'password_hash': self.password_hash,
                    'key_salt': key_salt_b64,
                    'created_at': int(self.created_at.timestamp()),
                    'created_at_iso': self.created_at.isoformat()
                }
            )
            return True
        except ClientError as e:
            print(f"Error saving user: {e}")
            return False

    @classmethod
    def get_by_id(cls, user_id: str) -> Optional['User']:
        """Get user by ID"""
        try:
            response = db.users_table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                return cls._from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            print(f"Error getting user by ID: {e}")
            return None

    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email using GSI"""
        try:
            response = db.users_table.query(
                IndexName='email-index',
                KeyConditionExpression='email = :email',
                ExpressionAttributeValues={':email': email}
            )
            if response['Items']:
                return cls._from_dynamodb_item(response['Items'][0])
            return None
        except ClientError as e:
            print(f"Error getting user by email: {e}")
            return None

    @classmethod
    def _from_dynamodb_item(cls, item: Dict[str, Any]) -> 'User':
        """Convert DynamoDB item to User object"""
        import base64

        # Convert base64 string back to bytes
        key_salt = base64.b64decode(item['key_salt']) if item.get('key_salt') else None
        created_at = datetime.fromtimestamp(item.get('created_at', 0))

        user = cls()
        user.user_id = item['user_id']
        user.email = item['email']
        user.password_hash = item['password_hash']
        user.key_salt = key_salt
        user.created_at = created_at
        return user

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for API responses"""
        return {
            'user_id': self.user_id,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class AudioFile:
    def __init__(self, file_id: str = None, user_id: str = None, s3_key: str = None,
                 file_size: int = None, uploaded_at: datetime = None):
        self.file_id = file_id or str(uuid.uuid4())
        self.user_id = user_id
        self.s3_key = s3_key
        self.file_size = file_size
        self.uploaded_at = uploaded_at or datetime.utcnow()

    def save(self) -> bool:
        """Save audio file record to DynamoDB"""
        try:
            db.audio_files_table.put_item(
                Item={
                    'file_id': self.file_id,
                    'user_id': self.user_id,
                    's3_key': self.s3_key,
                    'file_size': self.file_size,
                    'uploaded_at': int(self.uploaded_at.timestamp()),
                    'uploaded_at_iso': self.uploaded_at.isoformat()
                }
            )
            return True
        except ClientError as e:
            print(f"Error saving audio file: {e}")
            return False

    @classmethod
    def get_by_id(cls, file_id: str) -> Optional['AudioFile']:
        """Get audio file by ID"""
        try:
            response = db.audio_files_table.get_item(Key={'file_id': file_id})
            if 'Item' in response:
                return cls._from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            print(f"Error getting audio file by ID: {e}")
            return None

    @classmethod
    def get_by_user_id(cls, user_id: str, limit: int = 50) -> List['AudioFile']:
        """Get audio files for a user, ordered by upload time (newest first)"""
        try:
            response = db.audio_files_table.query(
                IndexName='user-files-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=limit
            )
            return [cls._from_dynamodb_item(item) for item in response['Items']]
        except ClientError as e:
            print(f"Error getting audio files for user: {e}")
            return []

    @classmethod
    def get_by_s3_key(cls, s3_key: str, user_id: str) -> Optional['AudioFile']:
        """Get audio file by S3 key and user ID"""
        try:
            # Since we can't query by s3_key directly, we need to scan (expensive for large datasets)
            # In production, consider adding another GSI if this query is frequent
            response = db.audio_files_table.scan(
                FilterExpression='s3_key = :s3_key AND user_id = :user_id',
                ExpressionAttributeValues={
                    ':s3_key': s3_key,
                    ':user_id': user_id
                },
                Limit=1
            )
            if response['Items']:
                return cls._from_dynamodb_item(response['Items'][0])
            return None
        except ClientError as e:
            print(f"Error getting audio file by S3 key: {e}")
            return None

    @classmethod
    def _from_dynamodb_item(cls, item: Dict[str, Any]) -> 'AudioFile':
        """Convert DynamoDB item to AudioFile object"""
        uploaded_at = datetime.fromtimestamp(item.get('uploaded_at', 0))

        audio_file = cls()
        audio_file.file_id = item['file_id']
        audio_file.user_id = item['user_id']
        audio_file.s3_key = item['s3_key']
        audio_file.file_size = item.get('file_size')
        audio_file.uploaded_at = uploaded_at
        return audio_file

    def to_dict(self) -> Dict[str, Any]:
        """Convert audio file to dictionary for API responses"""
        return {
            'file_id': self.file_id,
            'user_id': self.user_id,
            's3_key': self.s3_key,
            'file_size': self.file_size,
            'uploaded_at': self.uploaded_at.isoformat()
        }
```

### 4. Updated Application (`app.py`)

```python
from flask import Flask, request, jsonify
from flask_cors import CORS
from models import User, AudioFile
from auth import hash_password, verify_password, generate_key_salt, generate_jwt_token, token_required
from crypto_utils import AudioDecryptor
import os

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Enable CORS for frontend integration
    CORS(app)

    # Routes
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({'status': 'healthy', 'service': 'panzoto-backend', 'database': 'dynamodb'})

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
            existing_user = User.get_by_email(email)
            if existing_user:
                return jsonify({'error': 'User already exists'}), 409

            # Create new user
            password_hash = hash_password(password)
            key_salt = generate_key_salt()

            user = User(
                email=email,
                password_hash=password_hash,
                key_salt=key_salt
            )

            if not user.save():
                return jsonify({'error': 'Failed to create user'}), 500

            # Generate JWT token
            token = generate_jwt_token(user.user_id)

            return jsonify({
                'token': token,
                'user_id': user.user_id,
                'key_salt': user.key_salt.hex(),  # Send salt for key derivation
                'user': user.to_dict()
            }), 201

        except Exception as e:
            print(f"Registration error: {e}")
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
            user = User.get_by_email(email)

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
            print(f"Login error: {e}")
            return jsonify({'error': 'Login failed'}), 500

    @app.route('/api/user/audio-files', methods=['GET'])
    @token_required
    def get_user_audio_files():
        """Get list of user's audio files"""
        try:
            limit = int(request.args.get('limit', 50))
            audio_files = AudioFile.get_by_user_id(request.current_user_id, limit=limit)

            return jsonify({
                'audio_files': [file.to_dict() for file in audio_files]
            })

        except Exception as e:
            print(f"Error retrieving audio files: {e}")
            return jsonify({'error': 'Failed to retrieve audio files'}), 500

    @app.route('/api/audio-file', methods=['POST'])
    @token_required
    def create_audio_file():
        """Create new audio file record"""
        try:
            data = request.get_json()
            s3_key = data.get('s3_key')
            file_size = data.get('file_size')

            if not s3_key:
                return jsonify({'error': 's3_key is required'}), 400

            audio_file = AudioFile(
                user_id=request.current_user_id,
                s3_key=s3_key,
                file_size=file_size
            )

            if not audio_file.save():
                return jsonify({'error': 'Failed to create audio file record'}), 500

            return jsonify({
                'audio_file': audio_file.to_dict()
            }), 201

        except Exception as e:
            print(f"Error creating audio file: {e}")
            return jsonify({'error': 'Failed to create audio file'}), 500

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
            user = User.get_by_id(request.current_user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Verify password
            if not verify_password(password, user.password_hash):
                return jsonify({'error': 'Invalid password'}), 401

            # Get audio file record
            if file_id:
                audio_file = AudioFile.get_by_id(file_id)
                if not audio_file or audio_file.user_id != user.user_id:
                    return jsonify({'error': 'Audio file not found'}), 404
            else:
                audio_file = AudioFile.get_by_s3_key(s3_key, user.user_id)
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
            print(f"Decryption error: {e}")
            return jsonify({'error': 'Decryption failed'}), 500

    return app

# Application factory
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### 5. Authentication (auth.py)

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

## Testing DynamoDB Setup

### 1. Test Table Creation:
```bash
# List tables to verify they exist
aws dynamodb list-tables --region us-east-1

# Check table structure
aws dynamodb describe-table --table-name panzoto-users --region us-east-1
aws dynamodb describe-table --table-name panzoto-audio-files --region us-east-1
```

### 2. Test User Registration:
```bash
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

### 3. Test User Login:
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

### 4. Test Audio File Creation:
```bash
# Use token from login response
curl -X POST http://localhost:5000/api/audio-file \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "s3_key": "users/test-user/audio-123.3gp",
    "file_size": 1024
  }'
```

### 5. Test Get User Files:
```bash
curl -X GET http://localhost:5000/api/user/audio-files \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## DynamoDB vs RDS Comparison

| Feature | RDS PostgreSQL | DynamoDB |
|---------|----------------|----------|
| **Base Cost** | ~$15-25/month | $0 (pay-per-request) |
| **Scaling** | Manual | Automatic |
| **Maintenance** | Required | Managed |
| **Query Flexibility** | SQL (full featured) | Limited (NoSQL) |
| **ACID Transactions** | Full support | Limited support |
| **Best For** | Complex queries, reporting | High-scale, simple queries |

## Migration Considerations

### Data Migration (if needed):
```python
# Script to migrate existing RDS data to DynamoDB
import psycopg2
import boto3
from models import User, AudioFile

def migrate_from_rds():
    # Connect to old RDS database
    conn = psycopg2.connect(
        host="your-rds-endpoint",
        database="postgres",
        user="panzoto",
        password="your-password"
    )

    cur = conn.cursor()

    # Migrate users
    cur.execute("SELECT user_id, email, password_hash, key_salt, created_at FROM users")
    for row in cur.fetchall():
        user = User(
            user_id=row[0],
            email=row[1],
            password_hash=row[2],
            key_salt=row[3],
            created_at=row[4]
        )
        user.save()

    # Migrate audio files
    cur.execute("SELECT file_id, user_id, s3_key, file_size, uploaded_at FROM audio_files")
    for row in cur.fetchall():
        audio_file = AudioFile(
            file_id=row[0],
            user_id=row[1],
            s3_key=row[2],
            file_size=row[3],
            uploaded_at=row[4]
        )
        audio_file.save()

    conn.close()

if __name__ == "__main__":
    migrate_from_rds()
```

### Performance Optimization Tips:

1. **Use GSIs effectively**: Design Global Secondary Indexes for your query patterns
2. **Batch operations**: Use `batch_get_item` and `batch_write_item` for multiple items
3. **Avoid scans**: Always prefer queries over scans when possible
4. **Monitor costs**: Use AWS CloudWatch to track read/write capacity units

### Security Best Practices:

1. **IAM Roles**: Use IAM roles instead of access keys when possible
2. **Least privilege**: Grant minimum required permissions
3. **Encryption**: Enable encryption at rest and in transit
4. **VPC endpoints**: Use VPC endpoints for private connectivity

## Next Steps

1. **Create the DynamoDB tables** using the AWS CLI commands above
2. **Set up your new backend project** with the provided code
3. **Test all endpoints** to ensure functionality
4. **Update your Android app** to use the new backend URL
5. **Monitor costs** in AWS Console to verify savings

This setup provides the same functionality as RDS but with significant cost savings and better scalability for a mobile app workload.