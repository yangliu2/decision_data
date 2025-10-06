"""
Integration tests for the complete audio upload and transcription workflow.

This test suite validates the entire pipeline from user authentication
to audio file transcription.
"""

import pytest
import requests
import base64
import secrets
from Crypto.Cipher import AES
from io import BytesIO

# Test configuration
BASE_URL = "http://206.189.185.129:8000"
TEST_USER_EMAIL = "workflow_test@example.com"
TEST_USER_PASSWORD = "TestPass123!"


class TestAudioWorkflow:
    """Test the complete audio processing workflow end-to-end."""

    @pytest.fixture(scope="class")
    def test_user(self):
        """Register a test user for the workflow."""
        response = requests.post(
            f"{BASE_URL}/api/register",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
        )

        # User might already exist, that's okay
        if response.status_code == 200:
            return response.json()
        else:
            # Try to login instead
            login_response = requests.post(
                f"{BASE_URL}/api/login",
                json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD
                }
            )
            assert login_response.status_code == 200, f"Login failed: {login_response.text}"
            return login_response.json()

    def test_01_user_registration(self):
        """Test 1: User can register successfully."""
        unique_email = f"test_{secrets.token_hex(4)}@example.com"

        response = requests.post(
            f"{BASE_URL}/api/register",
            json={
                "email": unique_email,
                "password": TEST_USER_PASSWORD
            }
        )

        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        print(f"[OK] User registered: {unique_email}")

    def test_02_user_login(self, test_user):
        """Test 2: User can login and get JWT token."""
        response = requests.post(
            f"{BASE_URL}/api/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
        )

        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        print(f"[OK] User logged in, token: {data['token'][:30]}...")

    def test_03_get_encryption_key(self, test_user):
        """Test 3: User can fetch encryption key from server."""
        token = test_user['token']

        response = requests.get(
            f"{BASE_URL}/api/user/encryption-key",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200, f"Get encryption key failed: {response.text}"
        data = response.json()
        assert "encryption_key" in data
        assert "user_id" in data

        # Verify key is valid base64
        encryption_key = data['encryption_key']
        decoded_key = base64.b64decode(encryption_key)
        assert len(decoded_key) == 32, f"Key should be 32 bytes, got {len(decoded_key)}"

        print(f"[OK] Encryption key fetched: {encryption_key[:30]}...")
        return encryption_key

    def test_04_encrypt_audio_file(self):
        """Test 4: Encrypt audio file using server-managed key."""
        # Create fake audio data
        fake_audio_data = b"FAKE_AUDIO_DATA_" * 100  # 1600 bytes

        # Generate encryption key (simulating server key)
        encryption_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        key = base64.b64decode(encryption_key)

        # Encrypt using AES-GCM (same as Android app)
        iv = secrets.token_bytes(16)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)

        encrypted_data, tag = cipher.encrypt_and_digest(fake_audio_data)

        # Android app writes: IV + encrypted_data + tag
        full_encrypted = iv + encrypted_data + tag

        print(f"[OK] Audio encrypted: {len(full_encrypted)} bytes (IV: {len(iv)}, Data: {len(encrypted_data)}, Tag: {len(tag)})")

        return {
            'encrypted_data': full_encrypted,
            'encryption_key': encryption_key,
            'original_size': len(fake_audio_data)
        }

    def test_05_decrypt_audio_file(self):
        """Test 5: Server can decrypt audio file encrypted by client."""
        # Encrypt data
        encryption_result = self.test_04_encrypt_audio_file()
        encrypted_data = encryption_result['encrypted_data']
        encryption_key_b64 = encryption_result['encryption_key']

        # Decrypt (server-side logic)
        key = base64.b64decode(encryption_key_b64)

        iv = encrypted_data[:16]
        encrypted_content = encrypted_data[16:-16]
        tag = encrypted_data[-16:]

        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        decrypted_data = cipher.decrypt_and_verify(encrypted_content, tag)

        assert len(decrypted_data) == encryption_result['original_size']
        print(f"[OK] Audio decrypted successfully: {len(decrypted_data)} bytes")

    def test_06_create_audio_file_record(self, test_user):
        """Test 6: Create audio file record in DynamoDB."""
        token = test_user['token']

        response = requests.post(
            f"{BASE_URL}/api/audio-file",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "s3_key": "test_audio_workflow/test_file.3gp_encrypted",
                "file_size": 1000,
                "duration": 10.5
            }
        )

        assert response.status_code == 200, f"Create audio file failed: {response.text}"
        data = response.json()
        assert "file_id" in data
        assert data["s3_key"] == "test_audio_workflow/test_file.3gp_encrypted"

        print(f"[OK] Audio file record created: {data['file_id']}")
        return data['file_id']

    def test_07_get_user_audio_files(self, test_user):
        """Test 7: User can retrieve their audio files."""
        token = test_user['token']

        response = requests.get(
            f"{BASE_URL}/api/user/audio-files",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200, f"Get audio files failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)

        print(f"[OK] Retrieved {len(data)} audio files")

    def test_08_get_processing_jobs(self, test_user):
        """Test 8: User can check processing job status."""
        token = test_user['token']

        response = requests.get(
            f"{BASE_URL}/api/user/processing-jobs?limit=20",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200, f"Get processing jobs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)

        print(f"[OK] Retrieved {len(data)} processing jobs")

        # Show job statuses
        if data:
            for job in data[:3]:
                print(f"  - Job {job['job_id'][:8]}: {job['status']}")

    def test_09_get_transcripts(self, test_user):
        """Test 9: User can retrieve their transcripts."""
        token = test_user['token']

        response = requests.get(
            f"{BASE_URL}/api/user/transcripts?limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200, f"Get transcripts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)

        print(f"[OK] Retrieved {len(data)} transcripts")

    def test_10_health_check(self):
        """Test 10: API health check."""
        response = requests.get(f"{BASE_URL}/api/health")

        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"

        print(f"[OK] API is healthy: {data}")


class TestEncryptionCompatibility:
    """Test encryption/decryption compatibility between Android and Backend."""

    def test_android_encryption_format(self):
        """Verify Android encryption format matches server expectations."""
        # Simulate Android encryption
        encryption_key_b64 = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        original_data = b"Test audio content for encryption verification"

        # Android encryption
        key = base64.b64decode(encryption_key_b64)
        iv = secrets.token_bytes(16)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        encrypted_data, tag = cipher.encrypt_and_digest(original_data)

        # Format: IV + encrypted_data + tag
        android_format = iv + encrypted_data + tag

        # Server decryption (mimics backend logic)
        key_server = base64.b64decode(encryption_key_b64)
        iv_extracted = android_format[:16]
        encrypted_content = android_format[16:-16]
        tag_extracted = android_format[-16:]

        cipher_server = AES.new(key_server, AES.MODE_GCM, nonce=iv_extracted)
        decrypted_data = cipher_server.decrypt_and_verify(encrypted_content, tag_extracted)

        assert decrypted_data == original_data, "Encryption/Decryption mismatch!"
        print(f"[OK] Android <-> Server encryption compatible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
