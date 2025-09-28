# Cloudflare SSL Configuration Guide

## Current Status: 522 Connection Timeout Error

**Issue**: Cloudflare is trying to connect to your server via HTTPS, but nginx is only configured for HTTP.

**Solution**: Configure Cloudflare SSL mode to match your server setup.

## Quick Fix: Flexible SSL Mode

### Step 1: Configure Cloudflare
1. Login to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain: `panzoto.com`
3. Go to **SSL/TLS** → **Overview**
4. Change SSL mode from "Full" to **"Flexible"**
5. Save changes

### Step 2: Verify Setup
After changing to Flexible mode, test:

```bash
# This should work after the change:
curl https://api.panzoto.com/api/health
```

## SSL Mode Comparison

| Mode | Browser→Cloudflare | Cloudflare→Server | Certificate Required |
|------|-------------------|-------------------|---------------------|
| **Off** | HTTP | HTTP | None |
| **Flexible** | HTTPS | HTTP | None |
| **Full** | HTTPS | HTTPS | Self-signed OK |
| **Full (Strict)** | HTTPS | HTTPS | Valid certificate required |

## Current Server Configuration

✅ **Working**:
- Nginx proxy: Port 80 → 8000 (FastAPI)
- Direct IP access: `http://206.189.185.129:8000/api/health`
- Local connectivity: All services running

❌ **Issue**:
- Server only has HTTP (port 80), no HTTPS (port 443)
- Cloudflare trying to connect via HTTPS gets 522 timeout

## Security Assessment

### Flexible Mode Security
- ✅ **Browser traffic**: Encrypted (HTTPS)
- ⚠️ **Cloudflare-to-server**: Unencrypted (HTTP)
- ✅ **For personal data**: Acceptable since Cloudflare is trusted CDN

### Future Enhancement: Full (Strict) Mode
For maximum security, we can upgrade to Full (Strict) by:

1. **Installing Let's Encrypt certificate**:
```bash
# After fixing DNS resolution:
certbot --nginx -d api.panzoto.com --agree-tos --email support@panzoto.com
```

2. **Configuring nginx for HTTPS**:
```nginx
server {
    listen 443 ssl http2;
    server_name api.panzoto.com;

    ssl_certificate /etc/letsencrypt/live/api.panzoto.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.panzoto.com/privkey.pem;

    # ... rest of configuration
}
```

## DNS Configuration Status

✅ **Current DNS**: `api.panzoto.com` → Cloudflare IPs
- `104.21.77.147`
- `172.67.209.12`

## Troubleshooting Commands

### Test Direct Server Access
```bash
# Should work (bypasses Cloudflare):
curl http://206.189.185.129:8000/api/health

# Should timeout (firewall blocks external port 80):
curl http://206.189.185.129/api/health
```

### Test Domain Access
```bash
# Before fix - 522 error:
curl https://api.panzoto.com/api/health

# After Flexible mode - should work:
curl https://api.panzoto.com/api/health
```

### Check Server Status
```bash
ssh -i ~/.ssh/digitalocean_deploy root@206.189.185.129 "
systemctl status nginx
systemctl status uvicorn  # or check running processes
curl http://127.0.0.1/api/health
"
```

## Production Security Checklist

- [x] **Firewall**: UFW configured (ports 22, 80, 443)
- [x] **Reverse Proxy**: Nginx → FastAPI
- [x] **DNS**: Cloudflare proxy enabled
- [ ] **SSL Mode**: Configure Flexible (immediate)
- [ ] **Let's Encrypt**: Install certificate (future)
- [ ] **Rate Limiting**: API protection
- [ ] **Security Headers**: Enhanced protection

## Expected Results After Fix

### API Endpoints
- ✅ `https://api.panzoto.com/api/health`
- ✅ `https://api.panzoto.com/api/register`
- ✅ `https://api.panzoto.com/api/login`
- ✅ `https://api.panzoto.com/docs` (FastAPI documentation)

### Security Features
- ✅ HTTPS for all client connections
- ✅ Cloudflare DDoS protection
- ✅ Firewall protection on server
- ✅ Security headers via nginx

## Next Steps After SSL Fix

1. **Test API Functionality**: Verify all endpoints work
2. **Rate Limiting**: Implement API rate limits
3. **Security Headers**: Add comprehensive headers
4. **Monitoring**: Set up uptime monitoring
5. **Backup Strategy**: Database and configuration backups

---

**Configuration Date**: September 28, 2025
**Status**: Pending Cloudflare SSL mode change
**Contact**: Update this doc when configuration is complete