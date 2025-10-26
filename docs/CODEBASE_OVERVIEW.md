# Panzoto Codebase Architecture Overview

## Project Overview
**Panzoto** is a comprehensive audio transcription and decision-making data collection system with:
- **Android Mobile App** - Records and encrypts audio
- **FastAPI Backend** - Handles auth, encryption, transcription management
- **AWS Infrastructure** - S3 storage, DynamoDB database, Secrets Manager
- **OpenAI Whisper Integration** - Automatic speech-to-text

---

## Backend Architecture

### Directory Structure
```
decision_data/
├── api/backend/
│   └── api.py                    # FastAPI app with all endpoints
├── backend/
│   ├── config/
│   │   └── config.py            # Pydantic settings (env vars)
│   ├── services/                # Core business logic
│   │   ├── user_service.py      # User auth & encryption key management
│   │   ├── audio_service.py     # Audio file CRUD (DynamoDB)
│   │   ├── transcription_service.py  # Decryption, transcription jobs
│   │   ├── audio_processor.py   # Background transcription processor (30s interval)
│   │   ├── preferences_service.py   # User settings management
│   │   ├── daily_summary_scheduler.py  # Scheduled summary generation
│   │   └── summary_retrieval_service.py # Retrieve & decrypt summaries
│   ├── transcribe/
│   │   ├── whisper.py           # OpenAI Whisper API integration, 3gp→mp3 conversion
│   │   └── aws_s3.py            # S3 helper functions
│   ├── utils/
│   │   ├── auth.py              # JWT token generation/validation
│   │   ├── secrets_manager.py   # AWS Secrets Manager integration
│   │   ├── aes_encryption.py    # AES-256-GCM encryption utilities
│   │   ├── dynamo.py            # DynamoDB helpers
│   │   └── logger.py            # Logging configuration
│   ├── workflow/
│   │   └── daily_summary.py     # Daily summary generation logic
│   └── data/
│       └── reddit.py            # Reddit scraper (stories feature)
├── data_structure/
│   └── models.py                # Pydantic models for all data structures
└── scripts/                     # Utility scripts for data migration, testing
```

### API Endpoints Organization

**Authentication** (in `/api/register`, `/api/login`)
- `POST /api/register` - User registration (auto-creates preferences)
- `POST /api/login` - User login (JWT token)
- `GET /api/user/encryption-key` - Get server-managed encryption key

**Audio Management** (in `audio_service.py`)
- `POST /api/audio-file` - Upload audio metadata (auto-creates transcription job)
- `GET /api/user/audio-files` - List user's audio files
- `GET /api/audio-file/{file_id}` - Get specific audio file
- `DELETE /api/audio-file/{file_id}` - Delete audio file

**Transcription & Jobs** (in `transcription_service.py`)
- `POST /api/transcribe/audio-file/{file_id}` - Manually trigger transcription
- `GET /api/user/transcripts` - Get user's transcripts
- `GET /api/user/processing-jobs` - Get user's processing jobs

**User Preferences** (in `preferences_service.py`)
- `GET /api/user/preferences` - Get settings
- `POST /api/user/preferences` - Create preferences
- `PUT /api/user/preferences` - Update preferences
- `DELETE /api/user/preferences` - Delete preferences

**Daily Summaries** (in `summary_retrieval_service.py`)
- `GET /api/user/summaries` - List all summaries
- `GET /api/user/summaries/{date}` - Get summary by date (YYYY-MM-DD)
- `DELETE /api/user/summaries/{id}` - Delete summary
- `GET /api/user/summaries/export/download` - Export (JSON/CSV)
- `POST /api/user/request-daily-summary` - Manually trigger summary

**Health Check**
- `GET /api/health` - Server status

### Data Models (Pydantic - in `models.py`)

**User**
```python
- user_id: str (UUID)
- email: str
- password_hash: str (Argon2)
- key_salt: str (hex for legacy compatibility)
- created_at: datetime
```

**AudioFile**
```python
- file_id: str
- user_id: str
- s3_key: str
- file_size: int (bytes)
- uploaded_at: datetime
- recorded_at: datetime (from Android app)
```

**UserPreferences**
```python
- user_id: str
- notification_email: str
- enable_daily_summary: bool (default: false)
- enable_transcription: bool (default: true) ← AUTO MODE ENABLED
- summary_time_local: str (HH:MM format)
- timezone_offset_hours: int
- recording_max_duration_minutes: int
- created_at: datetime
- updated_at: datetime
```

**ProcessingJob**
```python
- job_id: str
- user_id: str
- job_type: str ("transcription" or "daily_summary")
- audio_file_id: str (optional)
- status: str ("pending", "processing", "completed", "failed")
- created_at: datetime
- completed_at: datetime (optional)
- error_message: str (optional)
- retry_count: int (default: 0)
- last_attempt_at: datetime (optional)
```

**TranscriptUser**
```python
- transcript_id: str
- user_id: str
- audio_file_id: str
- transcript: str
- length_in_seconds: float
- s3_key: str
- created_at: datetime
```

**DailySummaryResponse**
```python
- summary_id: str
- summary_date: str
- family_info: List[str]
- business_info: List[str]
- misc_info: List[str]
- created_at: datetime
```

### DynamoDB Tables

| Table | Partition Key | GSI | Purpose |
|-------|---|---|---|
| `panzoto-users` | `user_id` | `email-index` (email) | User accounts & auth |
| `panzoto-audio-files` | `file_id` | `user-files-index` (user_id) | Audio metadata |
| `panzoto-processing-jobs` | `job_id` | `user-jobs-index` (user_id) | Transcription/summary jobs |
| `panzoto-transcripts` | `transcript_id` | `user-transcripts-index` (user_id) | Transcribed text |
| `panzoto-user-preferences` | `user_id` | None | User settings |

### Key Services

**UserService**
- User registration & authentication (Argon2 hashing)
- Encryption key management (AWS Secrets Manager)
- User retrieval

**AudioFileService**
- Create/read/delete audio file records in DynamoDB
- Query user's audio files (with GSI)
- No direct file storage (files go to S3)

**UserTranscriptionService**
- Download encrypted audio from S3
- Decrypt with user's encryption key
- Send to OpenAI Whisper API
- Store transcript in DynamoDB
- Create/update processing jobs
- Retrieve user's transcripts

**UserPreferencesService**
- CRUD operations for user preferences
- Query users with daily_summary enabled

**AudioProcessor** (Background Service)
- Runs every 30 seconds (configurable)
- Processes pending transcription jobs
- Safety checks:
  - File size < 5MB
  - Retry count < 3
  - Job age < 24 hours
  - User has `enable_transcription=true`
- Prevents cost overruns

**SummaryRetrievalService**
- Generate daily summaries from transcripts
- Decrypt summaries (stored encrypted)
- Export functionality (JSON/CSV)

### Configuration (config.py)

**Transcription Safety Limits** (Cost-Control)
```python
TRANSCRIPTION_MAX_FILE_SIZE_MB = 5.0
TRANSCRIPTION_MAX_RETRIES = 3
TRANSCRIPTION_TIMEOUT_MINUTES = 5
TRANSCRIPTION_RATE_LIMIT_PER_MINUTE = 5
TRANSCRIPTION_CHECK_INTERVAL_SECONDS = 30
TRANSCRIPTION_MAX_DURATION_SECONDS = 300 (5 min)
TRANSCRIPTION_MIN_DURATION_SECONDS = 3
```

**AWS Configuration**
```python
AWS_S3_BUCKET_NAME = "panzoto"
AWS_S3_AUDIO_FOLDER = "audio_upload"
AWS_S3_TRANSCRIPT_FOLDER = "transcripts"
```

**Daily Summary Scheduling**
```python
DAILY_SUMMARY_HOUR = 17
TIME_OFFSET_FROM_UTC = -6
DAILY_RESET_HOUR = 2
TRANSCRIBER_INTERVAL = 60 seconds
```

---

## Android App Architecture

### Directory Structure
```
Panzoto/app/src/main/java/com/example/panzoto/
├── MainActivity.kt              # App entry point, navigation
├── FileEncryptor.kt             # AES-256-GCM encryption (16-byte IV)
├── config/
│   └── AppConfig.kt            # Centralized configuration
├── service/
│   ├── AuthService.kt          # API client, authentication
│   ├── RecordingService.kt     # Audio recording background service
│   └── RecordingNotificationManager.kt  # Notification handling
├── viewmodel/
│   ├── AuthViewModel.kt        # State management (login/register/session)
│   └── RecordingViewModel.kt   # Recording state management
├── ui/
│   ├── CostScreen.kt           # Cost transparency (PLACEHOLDER - "Coming Soon")
│   ├── HomeScreen.kt           # Main home/dashboard
│   ├── LoginScreen.kt          # User login
│   ├── RegisterScreen.kt       # User registration
│   ├── PreferencesScreen.kt    # User settings (enable transcription, daily summary, etc.)
│   ├── JobsScreen.kt           # View processing jobs
│   ├── TranscriptsScreen.kt    # View transcripts
│   ├── DecisionsScreen.kt      # View stories (Reddit decisions)
│   ├── ProcessingComponents.kt # Reusable UI components
│   └── theme/
│       └── Theme.kt            # Material Design 3 theme configuration
└── data/
    └── AuthModels.kt           # Data models
```

### UI Screens & Navigation

**Navigation Structure** (in `MainActivity.kt`)
- **HomeScreen** - Main dashboard with recording button
  - Shows recent transcripts/jobs
  - Quick stats
  - Navigation to other screens
  
- **LoginScreen** - Email + password authentication
  - Fetches encryption key on successful login
  - Caches token in DataStore
  
- **RegisterScreen** - New user registration
  - Password validation (8+ chars)
  - Creates user account
  - Auto-creates preferences with transcription ON
  
- **JobsScreen** - Processing job monitoring
  - Shows pending/processing/completed jobs
  - Status updates
  - Retry capability
  
- **TranscriptsScreen** - View transcribed audio
  - Lists all user's transcripts
  - Shows transcript text
  - Audio duration metadata
  
- **CostScreen** - PLACEHOLDER (Not Yet Implemented)
  - Currently shows "Coming Soon"
  - Lists planned features:
    - OpenAI Whisper API costs
    - AWS S3 storage costs
    - DynamoDB database costs
    - Total monthly expenses
    - Cost per recording
    - User contribution to total costs
  
- **PreferencesScreen** - User settings
  - Enable/disable daily summaries
  - Enable/disable transcription
  - Set summary time (local timezone)
  - Email address for notifications
  - Maximum recording duration
  
- **DecisionsScreen** - Stories feature
  - Fetches stories from Reddit
  - Displays decision-making scenarios
  
- **Theme** - Material Design 3
  - Light/dark mode support
  - Primary, secondary, tertiary colors
  - Consistent typography

### Key Components

**AuthService**
- HTTP client (OkHttp3) for API calls
- User registration & login
- JWT token management
- Encryption key fetching and caching
- Error handling & retry logic

**FileEncryptor**
- AES-256-GCM encryption
- 16-byte random IV per file
- Base64 encoding for transport
- Format: `[16-byte IV][encrypted data][16-byte GCM tag]`

**AppConfig**
- **Api**: Backend URL management (strings.xml override)
- **Audio**: Recording settings (silence thresholds, max duration)
- **Auth**: Authentication config (token expiry: 30 days, min password: 8 chars)
- **Encryption**: IV length (16 bytes), key length (256 bits)
- **Network**: Timeouts (30s connection, 60s read/write)
- **UI**: Spacing, padding, icon sizes

**RecordingViewModel**
- Recording state management
- Audio duration tracking
- Error handling

**AuthViewModel**
- User session state
- Login/register logic
- Token management

### Jetpack Compose Libraries Used
- `androidx.compose.material3` - Material Design 3 components
- `androidx.compose.material:material-icons-extended` - Extended icon set
- `androidx.activity.compose` - Compose integration
- `androidx.lifecycle:lifecycle-viewmodel-compose` - ViewModel integration
- `androidx.navigation:navigation-compose` - Navigation system
- `androidx.datastore:datastore-preferences` - Local data storage

**No Chart Libraries Detected** - No dedicated chart/graph libraries in build.gradle.kts

---

## Data Flow

### User Registration & Login
1. User enters email + password in **RegisterScreen**
2. POST `/api/register` creates account, returns JWT token + key_salt
3. Backend auto-creates **UserPreferences** with:
   - `enable_transcription = true` (automatic mode)
   - `enable_daily_summary = false` (opt-in)
4. Android stores token in **DataStore** (encrypted local storage)
5. On login, app fetches encryption key from `/api/user/encryption-key`

### Audio Recording & Upload
1. User taps record button in **HomeScreen**
2. Android records audio as `.3gp` file
3. App encrypts file locally:
   - Fetch encryption key from DataStore
   - Generate 16-byte random IV
   - AES-256-GCM encrypt the audio
   - Format: `[IV(16)][encrypted(variable)][tag(16)]`
4. Get presigned S3 URL from `/api/presigned-url?key=...`
5. Upload encrypted file directly to S3: `audio_upload/{user_uuid}/{filename}.3gp_encrypted`
6. POST `/api/audio-file` with metadata
   - Backend auto-creates **ProcessingJob** (status: pending)

### Automatic Background Transcription
1. **AudioProcessor** runs every 30 seconds
2. Finds pending jobs matching criteria:
   - File size < 5MB
   - Retry count < 3
   - Job age < 24 hours
   - User `enable_transcription = true`
3. Downloads encrypted file from S3
4. Fetches user's encryption key from **AWS Secrets Manager**
5. Decrypts using AES-256-GCM
6. Converts `.3gp` → `.mp3` using ffmpeg
7. Sends to **OpenAI Whisper API**
8. Stores transcript in **panzoto-transcripts** table
9. Updates job status to "completed"
10. User sees transcript in **TranscriptsScreen** (no action needed!)

### Manual Transcription (If Needed)
1. User taps "Transcribe" button in **TranscriptsScreen**
2. Rate limit: 5 per minute per user
3. Same process as automatic, but triggered on-demand
4. Job status updates: pending → processing → completed/failed

---

## Security & Encryption

### Encryption Model
- **Type**: AES-256-GCM (authenticated encryption)
- **Key Storage**: AWS Secrets Manager (server-managed)
- **Key Path**: `panzoto/encryption-keys/{user_uuid}`
- **IV Length**: 16 bytes (fixed, critical!)
- **Tag Length**: 128 bits
- **Format**: `[16-byte IV][encrypted audio][16-byte GCM tag]`

### Key Features
- Unique 256-bit key per user
- Keys never sent over network (cached after login)
- Independent of password changes
- GCM provides both confidentiality and authenticity

### Data Isolation
- **S3**: User-specific folders (`audio_upload/{user_uuid}/`)
- **DynamoDB**: Row-level access via `user_id` field
- **JWT**: 30-day tokens with user_id claim
- **Secrets Manager**: Separate key per user

---

## Cost Tracking Integration Points

### Current Status
- **Backend**: No cost tracking service exists yet
- **Android**: `CostScreen.kt` shows "Coming Soon" placeholder
- **Data Model**: No `UsageMetrics` or `CostTracker` table

### Integration Points Identified

#### Backend Integration
1. **New Model** (in `models.py`):
   ```python
   class UsageMetrics(BaseModel):
       metrics_id: str
       user_id: str
       date: str (YYYY-MM-DD)
       
       # Whisper API costs
       total_audio_minutes: float
       whisper_api_cost: float (calculated: minutes * $0.006)
       
       # S3 costs
       storage_bytes: int
       monthly_storage_cost: float
       
       # DynamoDB costs
       read_units: int
       write_units: int
       
       # Aggregates
       total_daily_cost: float
       created_at: datetime
   ```

2. **New Service** (in `services/usage_tracking_service.py`):
   - Track audio duration per transcription
   - Calculate Whisper API costs
   - Monitor S3 storage per user
   - Track DynamoDB operations
   - Aggregate daily metrics
   - Calculate user's contribution to total costs

3. **New DynamoDB Table** (`panzoto-usage-metrics`):
   - Partition Key: `user_id`
   - Sort Key: `date`
   - Tracks daily usage per user

4. **New API Endpoints** (in `api.py`):
   - `GET /api/user/usage-metrics` - Daily metrics
   - `GET /api/user/usage-metrics/{date}` - Specific date
   - `GET /api/user/usage-summary` - Monthly aggregate
   - `GET /api/admin/system-costs` - System-wide costs (admin only)

#### Android Integration
1. **CostScreen.kt Enhancement**:
   - Fetch `/api/user/usage-metrics` on load
   - Display daily/monthly costs
   - Show cost breakdown (Whisper vs. S3 vs. DynamoDB)
   - Chart/graph visualization (need to add library)

2. **Charts Library Options**:
   - `com.patrykandpatrick:vico` (Compose chart library)
   - `io.github.aachartmodel:aaChartCore-kotlin` (AAChart)
   - `com.github.PhilJay:MPAndroidChart` (MPAndroidChart)

3. **New ViewModel** (in `viewmodel/`):
   - `CostViewModel.kt` - Manage cost metrics state
   - Fetch data from API
   - Format for display

4. **New Composable Components**:
   - `CostBreakdownCard` - Show cost by service
   - `MonthlyTrendChart` - Graph of costs over time
   - `ContributionSummary` - User's % of total system costs

#### Transcription Service Integration
- **In `transcription_service.py`**:
  - When transcription completes, record:
    - Audio duration (seconds)
    - Whisper API cost: `duration_seconds / 60 * 0.006`
    - Completion timestamp
  - Store in DynamoDB via `UsageMetricsService`

#### Audio Processor Integration
- **In `audio_processor.py`**:
  - When processing jobs, track:
    - Total audio minutes processed that day
    - S3 storage size for all user files
    - DynamoDB operations

---

## Current Limitations & Design Considerations

### CostScreen Status
- Currently a placeholder with static "Coming Soon" text
- Uses Material3 theme correctly
- Uses AppConfig for styling
- No API calls implemented
- No data visualization

### Missing Infrastructure for Cost Tracking
1. No usage metrics table in DynamoDB
2. No tracking service in backend
3. No API endpoints for cost data
4. No chart/graph library in Android dependencies
5. No ViewModel for cost state management

### Architecture Strengths
- Clean separation of concerns (services, viewmodels, UI)
- Centralized configuration (AppConfig)
- Strong type safety (Pydantic models)
- Good error handling patterns
- Background processing isolated from API
- Security-first design (server-managed encryption)

### Recommended Chart Library (for Android)
- **Vico** (`com.patrykandpatrick:vico`)
  - Native Compose support
  - Modern, lightweight
  - Easy integration with state management
  - Good theming support

---

## Key Files Summary

### Backend
| File | Purpose |
|------|---------|
| `api.py` | All 20+ endpoints, startup/shutdown |
| `models.py` | 10+ Pydantic models |
| `user_service.py` | Auth, encryption key management |
| `audio_service.py` | Audio file CRUD |
| `transcription_service.py` | Decryption, transcription, jobs |
| `audio_processor.py` | Background processor (30s interval) |
| `preferences_service.py` | User settings |
| `summary_retrieval_service.py` | Summary retrieval & export |
| `whisper.py` | OpenAI integration + ffmpeg |
| `config.py` | All configuration (env vars) |

### Android
| File | Purpose |
|------|---------|
| `MainActivity.kt` | App entry point, navigation |
| `CostScreen.kt` | Cost transparency UI (PLACEHOLDER) |
| `AppConfig.kt` | Centralized configuration |
| `AuthService.kt` | API client |
| `FileEncryptor.kt` | AES-256-GCM encryption |
| `PreferencesScreen.kt` | User settings UI |
| `TranscriptsScreen.kt` | Transcript listing |

---

## Deployment & Infrastructure

### Backend Server
- **Platform**: DigitalOcean Droplet
- **IP**: 206.189.185.129
- **Software**: Ubuntu + Uvicorn (FastAPI)
- **Cost**: ~$6/month
- **Auto-deploy**: GitHub Actions on `main` branch

### AWS Services
- **S3**: Audio storage (user-specific folders)
- **DynamoDB**: Tables for users, audio, jobs, transcripts, preferences
- **Secrets Manager**: Encryption keys
- **Free tier**: Covers small-scale usage

### Monthly Cost Estimate
- **S3 Storage**: ~$0.50 (1000 files × 20KB)
- **DynamoDB**: Free tier (25GB storage, 25 RCU, 25 WCU)
- **Secrets Manager**: ~$10 (25 users)
- **OpenAI Whisper**: ~$0.30 (50 min audio)
- **DigitalOcean**: $6.00

**Total**: ~$17-20/month for 25 users, 1000 files

---

## Next Steps for Cost Tracking Feature

### Phase 1: Backend Infrastructure
1. Create `UsageMetrics` model
2. Create `panzoto-usage-metrics` DynamoDB table
3. Create `UsageTrackingService`
4. Integrate tracking into `TranscriptionService`
5. Add API endpoints for cost retrieval

### Phase 2: Cost Calculation
1. Calculate Whisper API costs (duration × $0.006/min)
2. Calculate S3 costs (storage size × $0.023/GB)
3. Calculate DynamoDB costs (estimated)
4. Implement cost aggregation (daily/monthly)

### Phase 3: Android UI
1. Add chart library to build.gradle.kts
2. Create `CostViewModel`
3. Enhance `CostScreen.kt` with real data
4. Create cost breakdown components
5. Add trend charts

### Phase 4: Transparency Features
1. System-wide cost dashboard (admin)
2. User contribution percentage
3. Cost breakdown by service
4. Historical cost trends
5. Projection/forecast

---

*Document Generated: October 25, 2025*
*System Status: Production Ready (without cost tracking)*
