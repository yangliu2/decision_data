# Install ffmpeg on Server

Run these commands on the server to install ffmpeg for 3gp audio conversion:

```bash
# SSH into server
ssh root@206.189.185.129

# Fix any interrupted dpkg operations
dpkg --configure -a

# Install ffmpeg
apt-get update
apt-get install -y ffmpeg

# Verify installation
ffmpeg -version

# Restart API server
pkill -9 -f 'uvicorn.*decision_data'
cd /root/decision_data
/root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn decision_data.api.backend.api:app --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &

# Check server is running
sleep 5
curl http://localhost:8000/api/health
```

After this, the server will automatically convert 3gp audio files to mp3 before sending to OpenAI Whisper API.
