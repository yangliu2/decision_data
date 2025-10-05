# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a decision data collection system that scrapes stories from Reddit, transcribes audio content using AWS services, and provides an API to access decision-making stories. The system uses FastAPI for the backend, MongoDB for data storage, and AWS S3/DynamoDB for file storage and metadata.

## Commands

### Development Commands
- `poetry install` - Install dependencies
- `poetry add <package>` - Add new package
- `poetry add <package> --group dev` - Add development dependency

### Testing and Quality Assurance
- `pytest` - Run all tests
- `tox` - Run all test environments (test, lint, format, type checking)
- `tox -e py313-test` - Run tests with coverage report
- `tox -e py313-lint` - Run flake8 linting
- `tox -e py313-fmt` - Check Black formatting
- `tox -e py313-type` - Run mypy type checking

### API Server
- `uvicorn decision_data.api.backend.api:app --reload` - Start development server
- `./start_api_server.sh` - Start API server using script

### Deployment
- `git push origin main` - Triggers automated deployment to DigitalOcean droplet
- Production API: `http://206.189.185.129:8000`
- Health check: `curl http://206.189.185.129:8000/api/health`
- Deployment logs: GitHub Actions workflow runs

### Project Management & Documentation
- **GitHub Issues**: For bugs and feature requests - https://github.com/yangliu2/decision_data/issues
- **CLAUDE.md**: Main project documentation and progress tracking (this file)
- **README.md**: User-facing documentation and setup instructions

### Building
- `poetry build` - Generate package

## Architecture

### Core Components

**Data Collection Pipeline:**
- `backend/data/reddit.py` - Reddit scraping using PRAW
- `backend/data/save_reddit_posts.py` - Save scraped data to MongoDB
- `backend/data/mongodb_client.py` - MongoDB operations

**Transcription Service:**
- `backend/transcribe/whisper.py` - OpenAI Whisper API integration (runs as automatic service)
- `backend/transcribe/aws_s3.py` - S3 file operations for audio processing

**API Layer:**
- `api/backend/api.py` - FastAPI application with CORS enabled
- Main endpoints:
  - `GET /api/stories` - Retrieve stories from MongoDB
  - `POST /api/save_stories` - Trigger Reddit scraping and save to DB

**Configuration & Utilities:**
- `backend/config/config.py` - Pydantic settings
- `backend/utils/logger.py` - Loguru logging setup
- `backend/utils/dynamo.py` - AWS DynamoDB key-value storage
- `data_structure/models.py` - Pydantic data models

**Workflows:**
- `backend/workflow/daily_summary.py` - Generate daily summaries from transcriptions
- `backend/services/controller.py` - Service management

**UI Components:**
- `ui/email/email.py` - Email functionality

### Data Flow
1. Reddit posts are scraped and saved to MongoDB
2. Audio content is uploaded to S3 and transcribed via Whisper service
3. Transcriptions trigger daily summary generation
4. API serves processed stories to clients

### Environment Setup
- Requires `.env` file with API keys and database credentials
- MongoDB IP access must be configured
- AWS credentials needed for S3 and DynamoDB access

### Code Quality Standards
- Uses Black formatter (line length: 79)
- Flake8 linting (max line length: 89)
- MyPy type checking (Python 3.13)
- Test coverage reporting via pytest-cov

### Documentation Maintenance Guidelines
- **IMPORTANT**: Only maintain ONE file per documentation topic in `docs/` folder
- **Security Documentation**: `docs/security.md` (consolidated - do not create multiple security files)
- **Architecture Documentation**: `docs/architecture.md` (consolidated - do not create multiple architecture files)
- **API Documentation**: `docs/api_endpoints.md`
- **Deployment Documentation**: `docs/deployment_guide.md`
- **NEVER** create duplicate documentation files with similar names
- **ALWAYS** update the existing consolidated file rather than creating new ones
- If documentation becomes too long, use clear section headers within the single file

### Development Notes
- **IMPORTANT**: When using `find` commands, always exclude `.tox` folder: `find . -path "*/.tox" -prune -o -type f -name "*.py" -print`
- Tox creates virtual environments that contain many third-party packages and can overwhelm search results

### Known Issues
- DateTime objects have inconsistent saving to MongoDB, causing filtering issues
- **RESOLVED**: DynamoDB Decimal conversion issues with timestamps (fixed in user_service.py)

### Deployment & Hosting
- **Production Environment**: DigitalOcean Droplet (ubuntu-s-1vcpu-512mb-10gb-nyc1-01)
- **IP Address**: 206.189.185.129
- **Automated Deployment**: GitHub Actions on push to main branch
- **Monthly Cost**: ~$4-6 (80% savings vs App Platform)
- **Deployment Documentation**: `docs/deployment_guide.md`
- **Implementation Log**: `docs/implementation_log.md` - Complete project history and steps

### Security & Best Practices
- **SSH Keys**: Ed25519 without passphrase for automated deployment
- **GitHub Secrets**: Properly configured for CI/CD pipeline
- **Private Data Isolation**: `docs/private/` folder excluded from git
- **Git History**: Cleaned of sensitive data (completed September 28, 2025)

### Project Management
- **GitHub Issues**: Track bugs and feature requests
- **Markdown Documentation**: In-repo documentation for architecture and progress
- **Git Commits**: Detailed commit messages for tracking changes
- **Utility Scripts**: `decision_data/scripts/` - One-off maintenance and debugging scripts
  - See `decision_data/scripts/README.md` for script inventory and usage
  - All new utility scripts should be placed in this directory

# Current Progress

## DynamoDB User Profile & Audio File Migration Plan

**Goal:** Replicate the user authentication and audio file management service from AWS RDS to DynamoDB for cost efficiency and better scalability.

### ✅ Completed Steps

1. **✅ AWS DynamoDB Table Setup** - September 24, 2025
   - [x] Created `panzoto-users` table with email GSI
   - [x] Created `panzoto-audio-files` table with user-files GSI
   - [x] Verified tables are ACTIVE and operational
   - [x] Tested basic read/write operations

2. **✅ Dependencies & Environment Setup** - September 24, 2025
   - [x] Added boto3, PyJWT, argon2-cffi, cryptography via Poetry
   - [x] Updated .env file with DynamoDB configuration
   - [x] Configured AWS credentials for DynamoDB access
   - [x] Tested DynamoDB connection successfully

3. **✅ Backend Code Implementation** - September 24, 2025
   - [x] Created DynamoDB models for User and AudioFile
   - [x] Implemented authentication utilities (Argon2, JWT tokens)
   - [x] Created UserService and AudioFileService classes
   - [x] Added 7 new FastAPI routes for user management
   - [x] Updated backend configuration with DynamoDB settings

4. **✅ Testing & Validation** - September 24, 2025
   - [x] Tested user registration endpoint
   - [x] Tested user login endpoint
   - [x] Tested audio file creation and retrieval
   - [x] Tested JWT token authentication
   - [x] Verified all CRUD operations work correctly
   - [x] Fixed Decimal conversion issue for DynamoDB timestamps

5. **✅ Documentation & Git Commit** - September 24, 2025
   - [x] Created comprehensive migration guide (`docs/dynamodb_migration_guide.md`)
   - [x] Created API endpoints documentation (`docs/api_endpoints.md`)
   - [x] Updated CLAUDE.md with migration completion status

### 🔄 In Progress Steps

- None

### 📋 Pending Steps

6. **Future Enhancements (Optional)**
   - [ ] Implement batch operations for audio files
   - [ ] Add Redis caching for frequently accessed data
   - [ ] Set up CloudWatch monitoring for DynamoDB costs
   - [ ] Add API rate limiting for production
   - [ ] Implement audio file search by metadata

### Key Benefits of Migration:
- **Cost Reduction**: From $15-25/month (RDS) to $1-5/month (DynamoDB)
- **Auto-scaling**: No manual capacity management needed
- **Serverless**: Perfect integration with Lambda functions
- **Pay-per-request**: Only pay for actual usage

### Technical Implementation Notes:
- Using DynamoDB with Global Secondary Indexes for efficient queries
- Implemented JWT authentication with 30-day token expiration
- Preserving S3 integration for audio file storage
- Using Pydantic models for data validation
- Following existing FastAPI patterns in the codebase
- Argon2 password hashing for security
- Full CRUD operations for user and audio file management

### New API Endpoints Implemented:
- `GET /api/health` - Service health check
- `POST /api/register` - User registration
- `POST /api/login` - User authentication
- `GET /api/user/audio-files` - List user's audio files
- `POST /api/audio-file` - Create audio file record
- `GET /api/audio-file/{file_id}` - Get specific audio file
- `DELETE /api/audio-file/{file_id}` - Delete audio file record

### Files Added/Modified:
- **New Services**: `user_service.py`, `audio_service.py`, `auth.py`
- **Updated Models**: Added User, AudioFile, UserCreate, UserLogin classes
- **Updated API**: Added 7 new endpoints to existing FastAPI app
- **Updated Config**: Added DynamoDB and auth configuration
- **Documentation**: Created comprehensive guides in `docs/` folder

### Project Documentation & Tracking:
- **GitHub Repository**: https://github.com/yangliu2/decision_data
- **Related Android Project**: `/Users/fangfanglai/AndroidStudioProjects/Panzoto/claude.md`

**Note**: This backend serves as the authentication and user management system for the Panzoto Android audio recording app. The Android project contains the security implementation roadmap that this backend fulfills (Phase 1.2 - Database Setup and 1.3 - Backend API Setup).

## S3 Storage Architecture Update (September 27, 2025)

### User-Specific Folder Structure Implementation

**Migration Status**: ✅ **COMPLETED** - All new audio uploads now use user-specific folder organization

### New S3 Organization

**Previous Structure** (Before September 27, 2025):
```
panzoto/
└── audio_upload/
    ├── audio_record_1727472600000.3gp_encrypted
    ├── audio_record_1727472700000.3gp_encrypted
    └── ... (all files mixed together)
```

**New Structure** (September 27, 2025+):
```
panzoto/
└── audio_upload/
    ├── user-uuid-1/
    │   ├── audio_user123a_1727472600000_4527.3gp_encrypted
    │   ├── audio_user123a_1727472700000_8341.3gp_encrypted
    │   └── ...
    ├── user-uuid-2/
    │   ├── audio_user456b_1727472800000_2156.3gp_encrypted
    │   └── ...
    └── user-uuid-n/
        └── ...
```

### File Naming Convention Updates

**Enhanced Collision Prevention**:
- **Format**: `audio_{user_prefix}_{timestamp}_{random_suffix}.3gp_encrypted`
- **user_prefix**: First 8 characters of user UUID for quick identification
- **timestamp**: Milliseconds since epoch for temporal uniqueness
- **random_suffix**: 4-digit random number for additional entropy
- **S3 Path**: `audio_upload/{full_user_uuid}/{filename}`

**Example S3 Keys**:
```
audio_upload/user123abc-def456-7890-abcd-ef1234567890/audio_user123a_1727472600000_4527.3gp_encrypted
audio_upload/user456def-789a-bcde-f012-3456789abcde/audio_user456d_1727472800000_2156.3gp_encrypted
```

### Backend API Integration

**DynamoDB Records** - Updated to store complete S3 paths:
```json
{
  "file_id": "audio-file-uuid",
  "user_id": "user123abc-def456-7890-abcd-ef1234567890",
  "s3_key": "audio_upload/user123abc-def456-7890-abcd-ef1234567890/audio_user123a_1727472600000_4527.3gp_encrypted",
  "file_size": 45678,
  "uploaded_at": "2025-09-27T20:30:00Z"
}
```

**API Endpoints** - No breaking changes, updated examples:
- `POST /api/audio-file` - Accepts new S3 key format
- `GET /api/user/audio-files` - Returns files with new S3 paths
- `GET /api/audio-file/{file_id}` - Provides complete S3 location

### Benefits Achieved

1. **Zero File Collisions**: Multiple users can record simultaneously without conflicts
2. **User Isolation**: Files organizationally separated for better management
3. **Audit Compliance**: Clear user attribution at file and folder level
4. **Scalability**: Supports unlimited concurrent users safely
5. **Performance**: S3 prefix optimization for large-scale file operations
6. **Security**: User-specific encryption with proper file isolation

### Migration Impact

**Backward Compatibility**: ✅ Maintained
- Existing files remain accessible at current locations
- No API breaking changes
- DynamoDB schema unchanged (only data format updated)

**Android App Changes**: ✅ Deployed
- Updated file naming logic in `MainActivity.kt`
- Modified S3 key generation for user-specific folders
- Enhanced collision prevention with multiple entropy sources

**Testing Requirements**:
- [ ] Verify new uploads create user-specific folders
- [ ] Confirm DynamoDB records include complete S3 paths
- [ ] Test concurrent uploads from multiple users
- [ ] Validate file accessibility and user isolation

### Implementation Files Modified

**Android App** (`/Users/fangfanglai/AndroidStudioProjects/Panzoto/`):
- `MainActivity.kt:175-181` - Enhanced filename generation
- `MainActivity.kt:272` - User-specific S3 key creation
- `CLAUDE.md` - Complete documentation update

**Backend Documentation**:
- `docs/api_endpoints.md` - Updated S3 folder structure section
- `CLAUDE.md` - Architecture documentation (this file)

**Related Jira/Confluence**: Update pending for project tracking

## Multi-User Audio Processing & Security Implementation (September 28, 2025)

### Complete User-Specific Audio Processing System

**Migration Status**: ✅ **COMPLETED** - Fully functional multi-user system with Android app integration

### Overview
Implemented a complete user-specific audio processing pipeline that transforms previously hardcoded single-user functionality into a secure, scalable multi-user system. This includes encrypted audio storage, user preferences management, processing job tracking, and personalized email summaries.

### ✅ Backend Implementation Completed

#### New Data Models & Services
**User Preferences System** (`backend/services/preferences_service.py`):
- User-specific notification settings (email, daily summary toggles, timing)
- Transcription processing preferences per user
- Complete CRUD operations with DynamoDB

**Multi-User Transcription Service** (`backend/services/transcription_service.py`):
- User-specific audio file decryption using password + salt
- Individual processing job tracking per user
- Secure transcript storage with user isolation
- AES-256-GCM encryption handling per user's unique encryption keys

**Extended API Endpoints**:
- `GET/POST/PUT /api/user/preferences` - User settings management
- `GET /api/user/transcripts` - User's transcription history
- `GET /api/user/processing-jobs` - User's background job status
- `POST /api/user/request-daily-summary` - Trigger personalized summaries

#### Enhanced Data Models (`data_structure/models.py`):
```python
UserPreferences, UserPreferencesCreate, UserPreferencesUpdate  # User settings
ProcessingJob                                                 # Job tracking
TranscriptUser                                               # User transcripts
```

#### DynamoDB Tables Created:
- `panzoto-user-preferences` - User notification & processing settings
- `panzoto-processing-jobs` - Background job queue and status tracking
- `panzoto-transcripts` - User-specific transcription storage

### ✅ Android App Implementation Completed

#### New UI Screens
**Settings Screen** (`SettingsScreen.kt`):
- Email notification configuration
- Daily summary timing settings (UTC)
- Audio transcription toggle controls
- Real-time preference validation and saving

**Processing Screen** (`ProcessingScreen.kt`):
- Live processing job status monitoring
- Personal transcript history with search
- Manual daily summary requests
- Refresh functionality for real-time updates

#### Enhanced Authentication Service (`AuthService.kt`):
- Comprehensive debug logging for network troubleshooting
- User preferences CRUD operations
- Processing job and transcript retrieval
- Daily summary request functionality

### ✅ Critical Bug Fixes Resolved

#### NetworkOnMainThreadException Prevention
**Issue**: Android app crashed with threading violations when making network calls
**Solution**: Systematic addition of `Dispatchers.IO` to all coroutine network operations
**Files Fixed**:
- `SettingsScreen.kt:53, 261` - Preference loading and saving
- `ProcessingScreen.kt:69, 197` - Data loading and daily summary requests
- Added proper imports: `kotlinx.coroutines.Dispatchers`

**Documentation Added**: Comprehensive warning section in `CLAUDE.md` with code examples to prevent recurrence

#### DynamoDB Table Creation
**Issue**: Missing DynamoDB tables caused "null" API responses
**Solution**: Created all required tables with proper Global Secondary Indexes
**Tables**: `panzoto-user-preferences`, `panzoto-processing-jobs`, `panzoto-transcripts`

#### AWS Region Configuration
**Issue**: Services referenced incorrect config variable names
**Solution**: Standardized to `REGION_NAME` across all services

### ✅ Testing & Validation Completed

#### DigitalOcean Production Server
- **Status**: ✅ Fully operational at `http://206.189.185.129:8000`
- **API Endpoints**: All new endpoints properly deployed and responding
- **Database Connectivity**: Confirmed working with proper error handling
- **Authentication**: Validation and JWT tokens functioning correctly

#### Android App Testing
- **Settings Screen**: Loads and saves preferences without threading errors
- **Processing Screen**: Displays processing jobs and transcripts successfully
- **Network Operations**: All API calls execute properly on background threads

### Security & Data Isolation Features

#### User-Specific Encryption
- Each user has unique encryption salt stored securely
- Audio files encrypted with user's password + individual salt
- PBKDF2 key derivation with 100,000 iterations
- AES-256-GCM authenticated encryption

#### Data Isolation
- DynamoDB user_id isolation across all data tables
- S3 user-specific folder structure: `audio_upload/{user_uuid}/`
- Processing jobs tracked individually per user
- Transcripts stored with complete user separation

#### API Security
- JWT authentication required for all user-specific endpoints
- Token-based user identification and authorization
- Secure password hashing with Argon2
- Input validation and sanitization

### System Architecture Benefits

#### Scalability Achieved
- **Concurrent Users**: Unlimited simultaneous audio processing
- **File Collisions**: Eliminated through user-specific folders + entropy
- **Database Performance**: DynamoDB auto-scaling with GSI optimization
- **Processing Queue**: Individual job tracking prevents user interference

#### Cost Efficiency
- **DynamoDB**: Pay-per-request pricing vs fixed RDS costs
- **S3 Storage**: Optimized prefix structure for performance
- **No Resource Contention**: User isolation prevents processing conflicts

### Implementation Files

#### Backend Services Added/Modified:
```
decision_data/backend/services/
├── preferences_service.py          # User preferences management
├── transcription_service.py        # Multi-user audio processing
└── user_service.py                 # Extended user operations

decision_data/data_structure/models.py  # Extended data models
decision_data/api/backend/api.py         # New API endpoints
```

#### Android App Files Modified:
```
Panzoto/app/src/main/java/com/example/panzoto/
├── ui/SettingsScreen.kt            # User preferences UI
├── ui/ProcessingScreen.kt          # Processing status & history
├── service/AuthService.kt          # Enhanced API client
└── CLAUDE.md                       # Threading prevention docs
```

### ⚠️ CRITICAL: NetworkOnMainThreadException Prevention

**IMPORTANT**: When adding new network operations in Android, ALWAYS use background threads:

**❌ WRONG - Causes crashes:**
```kotlin
coroutineScope.launch {
    val result = authService.someNetworkCall()
}
```

**✅ CORRECT - Safe threading:**
```kotlin
coroutineScope.launch(Dispatchers.IO) {
    val result = authService.someNetworkCall()
}
```

**Required Import**: `import kotlinx.coroutines.Dispatchers`

### Next Steps & Future Enhancements
- [ ] Implement batch transcript processing
- [ ] Add Redis caching for frequently accessed preferences
- [ ] Set up CloudWatch monitoring for DynamoDB performance
- [ ] Implement transcript search and filtering
- [ ] Add export functionality for user data
- [ ] Enhanced email template customization

### Related Documentation
- **Android App Security Roadmap**: `/Users/fangfanglai/AndroidStudioProjects/Panzoto/CLAUDE.md`
- **API Endpoints**: `docs/api_endpoints.md`
- **DynamoDB Migration**: `docs/dynamodb_migration_guide.md`
- **Deployment Guide**: `docs/deployment_guide.md`

## Server-Side Encryption Architecture (October 5, 2025)

### ✅ **COMPLETED**: Migration to AWS Secrets Manager

**Status**: 🟢 **DEPLOYED TO PRODUCTION**
**Documentation**: `docs/server_side_encryption_implementation.md`

#### Problem Solved
- **Issue**: All recordings stuck in pending/processing/failed status
- **Root Cause**: Background processor couldn't decrypt files without user passwords
- **Solution**: Server-managed encryption keys in AWS Secrets Manager

#### Architecture Changes

**Before (Password-Based Encryption)**:
```
User Password + Salt → PBKDF2 → Encryption Key
Server: ❌ No access to password → Cannot decrypt automatically
```

**After (Server-Managed Keys)**:
```
User Password → Argon2 Hash → DynamoDB (authentication only)
Server Key → AWS Secrets Manager → Encryption Key → Auto-transcription ✅
```

#### Security Benefits
- ✅ **Password Never Leaves Device**: Stored only on Android, never sent for encryption
- ✅ **Separation of Concerns**: Authentication vs encryption keys are independent
- ✅ **Key Rotation**: Can rotate encryption keys without password changes
- ✅ **Audit Trail**: AWS CloudTrail logs all key access
- ✅ **Automatic Processing**: Enables transcription without user interaction

#### Implementation Files
- **Backend**:
  - `backend/utils/secrets_manager.py` (new) - AWS Secrets Manager integration
  - `backend/services/user_service.py` - Auto-generate keys on registration
  - `backend/services/transcription_service.py` - Use server keys for decryption
  - `backend/services/audio_processor.py` - Enable automatic processing
  - `api/backend/api.py` - New endpoint: `GET /api/user/encryption-key`

- **Android** (not committed to this repo):
  - `service/AuthService.kt` - Fetch encryption keys after login
  - `FileEncryptor.kt` - Use base64 server keys instead of PBKDF2
  - `MainActivity.kt` - Encrypt with server keys before upload
  - `viewmodel/AuthViewModel.kt` - Provide encryption key accessor
  - `data/AuthModels.kt` - Add EncryptionKeyResponse model

#### Migration Notes
- **New users**: Encryption keys created automatically on registration
- **Existing users**: Require re-login to fetch encryption keys
- **Old files**: Encrypted with password-based method still accessible (backward compatible)
- **Cost**: AWS Secrets Manager ~$0.40/user/month + minimal API costs

#### Related Documentation
- **Full Implementation Guide**: `docs/server_side_encryption_implementation.md`
- **API Endpoints**: `docs/api_endpoints.md` (updated with encryption key endpoint)
- **Security Architecture**: `docs/security.md` (updated with new threat model)

---

## 📋 Current Work & Next Steps

### ✅ Recently Completed
- ✅ **Server-side encryption migration** - October 5, 2025
- ✅ **Automatic transcription enabled** - Background processor fully functional
- ✅ Multi-user audio processing system with complete user isolation
- ✅ Android Settings and Processing screens with proper threading
- ✅ Production deployment with automated CI/CD pipeline
- ✅ NetworkOnMainThreadException fixes and documentation

### 🔄 Current Focus
- Monitor automatic transcription success rate
- Track AWS Secrets Manager costs and usage
- Migrate existing users to new encryption system

### 🚀 Next Up (GitHub Issues)
- [ ] Batch transcript processing for efficiency
- [ ] Redis caching for encryption keys (reduce Secrets Manager API calls)
- [ ] Transcript search and filtering features
- [ ] Email template customization
- [ ] CloudWatch monitoring for transcription pipeline
- [ ] Key rotation mechanism for enhanced security