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
- **Jira Project**: Audio Recording (Android) (CCS) - https://panzoto.atlassian.net/browse/CCS
- **Confluence Space**: Panzoto - https://panzoto.atlassian.net/wiki/spaces/PANZOTO
- **Atlassian API Guide**: `docs/atlassian_api_guide.md` - Complete reference for Jira/Confluence integration
- Current deployment story: [CCS-37](https://panzoto.atlassian.net/browse/CCS-37)

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

### Known Issues
- DateTime objects have inconsistent saving to MongoDB, causing filtering issues

### Deployment & Hosting
- **Production Environment**: DigitalOcean Droplet (ubuntu-s-1vcpu-512mb-10gb-nyc1-01)
- **Automated Deployment**: GitHub Actions on push to main branch
- **Monthly Cost**: ~$4-6 (80% savings vs App Platform)
- **Deployment Documentation**: `docs/deployment_guide.md`

### Project Management & Documentation
- **Jira Integration**: REST API v3 with Atlassian Document Format (ADF)
- **Confluence Integration**: Storage Format (XHTML-based) for page content
- **Atlassian API Reference**: `docs/atlassian_api_guide.md`
- **Authentication**: API tokens with Base64 encoding for REST API calls

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
- **Confluence Space**: **Panzoto** - All project documentation and architecture
- **Jira Project**: **Audio Recording (Android)** (CCS) - Epic and story tracking
- **Related Android Project**: `/Users/fangfanglai/AndroidStudioProjects/Panzoto/claude.md`

**Note**: This backend serves as the authentication and user management system for the Panzoto Android audio recording app. The Android project contains the security implementation roadmap that this backend fulfills (Phase 1.2 - Database Setup and 1.3 - Backend API Setup).