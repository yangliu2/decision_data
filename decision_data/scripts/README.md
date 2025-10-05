# Utility Scripts

This directory contains one-off utility and maintenance scripts for the decision_data project.

## 📋 Script Inventory

### Database Maintenance

**`cleanup_processing_jobs.py`**
- **Purpose**: Clean up all processing jobs from DynamoDB
- **Use Case**: Fresh start after major migrations (e.g., encryption system changes)
- **Usage**: `python decision_data/scripts/cleanup_processing_jobs.py --auto`
- **Tables**: `panzoto-processing-jobs`, `panzoto-transcripts` (optional)
- **Added**: October 5, 2025 (Server-side encryption migration)

**`create_new_tables.py`**
- **Purpose**: Create new DynamoDB tables for the project
- **Use Case**: Initial setup or adding new tables
- **Tables Created**: Various project tables
- **Usage**: `python decision_data/scripts/create_new_tables.py`

### Debugging & Diagnostics

**`check_audio_files.py`**
- **Purpose**: Inspect audio files stored in S3 and DynamoDB
- **Use Case**: Verify file uploads and metadata consistency
- **Usage**: `python decision_data/scripts/check_audio_files.py`

**`check_dynamodb_jobs.py`**
- **Purpose**: Query and display processing jobs from DynamoDB
- **Use Case**: Debug stuck jobs, view job status distribution
- **Usage**: `python decision_data/scripts/check_dynamodb_jobs.py`

**`check_jobs.py`**
- **Purpose**: General job status checker
- **Use Case**: Monitor background processing pipeline
- **Usage**: `python decision_data/scripts/check_jobs.py`

### Data Repair

**`create_missing_transcription_jobs.py`**
- **Purpose**: Create transcription jobs for audio files that don't have them
- **Use Case**: Recover from processing failures or missed jobs
- **Usage**: `python decision_data/scripts/create_missing_transcription_jobs.py`
- **Warning**: Ensure encryption keys are available before running

### Deprecated Scripts

**`start_api_server.sh`** ⚠️ DEPRECATED
- **Purpose**: Manually start the API server
- **Status**: No longer needed - deployment is automated via GitHub Actions
- **Replaced By**: `.github/workflows/deploy.yml` handles automatic deployment
- **Keep**: Retained for local development reference only

---

## 🔧 Running Scripts

All scripts should be run from the **project root directory** with the proper conda environment:

```bash
# Activate environment
source ~/anaconda3/etc/profile.d/conda.sh
conda activate decision_data

# Run script (example)
python decision_data/scripts/cleanup_processing_jobs.py --auto
```

---

## 📝 Adding New Scripts

When creating new utility scripts:

1. **Location**: Place in `decision_data/scripts/`
2. **Documentation**: Add entry to this README
3. **Structure**:
   - Clear docstring at the top
   - Command-line arguments for non-interactive use
   - Environment variable loading (use `.env`)
   - Proper error handling and logging

4. **Template**:
```python
"""
Script description here.

Usage:
    python decision_data/scripts/your_script.py [--options]
"""

import boto3
from dotenv import load_dotenv
import os

load_dotenv()

def main():
    # Your script logic here
    pass

if __name__ == "__main__":
    main()
```

---

## ⚠️ Important Notes

- **Environment**: Always use the `decision_data` conda environment
- **Credentials**: Scripts use AWS credentials from `.env` file
- **Production**: Be careful running scripts against production databases
- **Backups**: DynamoDB data should be backed up before destructive operations
- **Testing**: Test scripts with `--dry-run` flags when available

---

## 📚 Related Documentation

- **Project Overview**: `../CLAUDE.md`
- **API Documentation**: `../docs/api_endpoints.md`
- **Deployment Guide**: `../docs/deployment_guide.md`
- **Security Architecture**: `../docs/security.md`
