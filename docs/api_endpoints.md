# API Endpoints Documentation

## Base URL
```
http://localhost:8000
```

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

Tokens are obtained from login/register endpoints and expire after 30 days.

## User Management Endpoints

### Health Check
```http
GET /api/health
```
**Description**: Service health check
**Authentication**: Not required

**Response**:
```json
{
  "status": "healthy",
  "service": "decision-data-backend",
  "database": "dynamodb"
}
```

### User Registration
```http
POST /api/register
```
**Description**: Create a new user account
**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Validation**:
- Password must be at least 8 characters
- Email must be valid format
- Email must be unique

**Response** (201 Created):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user_id": "uuid-string",
  "key_salt": "hex-encoded-salt",
  "user": {
    "user_id": "uuid-string",
    "email": "user@example.com",
    "created_at": "2025-09-25T01:04:39"
  }
}
```

**Error Responses**:
- `400`: Password too short
- `409`: User already exists
- `500`: Registration failed

### User Login
```http
POST /api/login
```
**Description**: Authenticate user and get access token
**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response** (200 OK):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user_id": "uuid-string",
  "key_salt": "hex-encoded-salt",
  "user": {
    "user_id": "uuid-string",
    "email": "user@example.com",
    "created_at": "2025-09-25T01:04:39"
  }
}
```

**Error Responses**:
- `401`: Invalid email or password
- `500`: Login failed

## Audio File Management Endpoints

### List User's Audio Files
```http
GET /api/user/audio-files?limit=50
```
**Description**: Get list of current user's audio files
**Authentication**: Required

**Query Parameters**:
- `limit` (optional): Number of files to return (1-100, default: 50)

**Response** (200 OK):
```json
[
  {
    "file_id": "uuid-string",
    "user_id": "uuid-string",
    "s3_key": "users/user-id/audio-123.m4a",
    "file_size": 2048,
    "uploaded_at": "2025-09-25T01:06:21"
  }
]
```

**Error Responses**:
- `401`: Not authenticated / Invalid token
- `500`: Failed to retrieve audio files

### Create Audio File Record
```http
POST /api/audio-file
```
**Description**: Create a new audio file record
**Authentication**: Required

**Request Body**:
```json
{
  "s3_key": "users/user-id/audio-123.m4a",
  "file_size": 2048
}
```

**Response** (201 Created):
```json
{
  "file_id": "uuid-string",
  "user_id": "uuid-string",
  "s3_key": "users/user-id/audio-123.m4a",
  "file_size": 2048,
  "uploaded_at": "2025-09-25T01:06:21"
}
```

**Error Responses**:
- `400`: Invalid request data
- `401`: Not authenticated / Invalid token
- `500`: Failed to create audio file

### Get Specific Audio File
```http
GET /api/audio-file/{file_id}
```
**Description**: Get details of a specific audio file (only if owned by current user)
**Authentication**: Required

**Path Parameters**:
- `file_id`: UUID of the audio file

**Response** (200 OK):
```json
{
  "file_id": "uuid-string",
  "user_id": "uuid-string",
  "s3_key": "users/user-id/audio-123.m4a",
  "file_size": 2048,
  "uploaded_at": "2025-09-25T01:06:21"
}
```

**Error Responses**:
- `401`: Not authenticated / Invalid token
- `403`: Access denied (file belongs to another user)
- `404`: Audio file not found
- `500`: Failed to retrieve audio file

### Delete Audio File Record
```http
DELETE /api/audio-file/{file_id}
```
**Description**: Delete an audio file record (only if owned by current user)
**Authentication**: Required

**Path Parameters**:
- `file_id`: UUID of the audio file

**Response** (200 OK):
```json
{
  "message": "Audio file deleted successfully"
}
```

**Error Responses**:
- `401`: Not authenticated / Invalid token
- `404`: Audio file not found or access denied
- `500`: Failed to delete audio file

## Existing Story Endpoints (Unchanged)

### Get Stories
```http
GET /api/stories?source=reddit&limit=10&subreddit=decision
```
**Description**: Retrieve stories from Reddit
**Authentication**: Not required

**Query Parameters**:
- `source`: Data source ("reddit", default: "reddit")
- `limit`: Number of stories (1-1000, default: 10)
- `subreddit`: Subreddit name (default: "decision")

### Save Stories
```http
POST /api/save_stories?num_posts=10
```
**Description**: Trigger background task to save Reddit stories
**Authentication**: Not required

**Query Parameters**:
- `num_posts`: Number of posts to save (1-1000, default: 10)

## Error Handling

All endpoints return consistent error responses:

### Authentication Errors
```json
{
  "detail": "Not authenticated"
}
```

### Validation Errors
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required"
    }
  ]
}
```

### Application Errors
```json
{
  "detail": "Error description"
}
```

## Rate Limiting

Currently no rate limiting is implemented. Consider adding rate limiting for production deployment.

## CORS Configuration

CORS is enabled for all origins in development:
```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

## Example Usage

### Complete User Flow
```bash
# 1. Register user
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'

# 2. Login (get token from response)
TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}' | \
  python -c "import sys, json; print(json.load(sys.stdin)['token'])")

# 3. Create audio file record
curl -X POST http://localhost:8000/api/audio-file \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"s3_key": "users/test/audio.m4a", "file_size": 1024}'

# 4. List user's audio files
curl -X GET http://localhost:8000/api/user/audio-files \
  -H "Authorization: Bearer $TOKEN"
```

## Development Notes

- Server runs on `http://0.0.0.0:8000` in development mode
- Auto-reload enabled for development
- Uses conda environment `decision_data`
- FastAPI automatic documentation available at `/docs` and `/redoc`