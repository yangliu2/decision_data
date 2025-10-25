# Cloudflare SSL Configuration Guide

## Problem: Dual Domain SSL Conflict

Your system has **two domains with conflicting SSL requirements**:

1. **www.panzoto.com** (WordPress) - Requires "Full" SSL to avoid redirect loops
2. **api.panzoto.com** (FastAPI) - Works with "Flexible" SSL (no cert on server)

When you change global SSL mode to "Full", the API breaks. When you use "Flexible", WordPress breaks.

**Solution**: Use **Cloudflare Page Rules** to apply different SSL modes per subdomain.

## Step-by-Step Fix

### Step 1: Set Global SSL Mode to "Full" (for WordPress)

1. Login to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select domain: `panzoto.com`
3. Go to **SSL/TLS** → **Overview**
4. Set SSL/TLS encryption mode to **"Full"**
5. Click **Save**

### Step 2: Create Page Rule for API (Exception)

1. Go to **Rules** → **Page Rules** (or **Caching** → **Page Rules**)
2. Click **Create Page Rule**
3. Fill in:
   - **URL**: `api.panzoto.com/*`
   - Click **+ Add a Setting**
   - Select **SSL** → **Flexible**
4. Click **Save and Deploy**

### Step 3: Verify Both Domains Work

```bash
# Test WordPress (Full SSL)
curl -I https://www.panzoto.com

# Test API (Flexible SSL via Page Rule)
curl https://api.panzoto.com/api/health
```

### Expected Results:
- ✅ `https://www.panzoto.com` - Works (Full SSL)
- ✅ `https://api.panzoto.com/api/health` - Works (Flexible SSL via Page Rule)
- ✅ No more ERR_TOO_MANY_REDIRECTS errors

## Why You Need Page Rules

### Domain-Specific SSL Requirements

**WordPress (www.panzoto.com):**
- Running on DigitalOcean App Platform with Let's Encrypt certificate
- **Requires**: Full SSL mode (HTTPS to origin)
- **Reason**: Avoids redirect loops (Flexible mode causes WordPress to redirect HTTP to HTTPS)

**FastAPI API (api.panzoto.com):**
- Running on DigitalOcean Droplet (206.189.185.129:8000) via Nginx reverse proxy
- **Can use**: Flexible SSL mode (HTTP to origin)
- **Reason**: No certificate needed on server (Cloudflare handles HTTPS from browser)

### Solution: Page Rules
Page Rules let you override the global SSL setting **per URL pattern**, so both domains work simultaneously.

## SSL Mode Comparison

| Mode | Browser→Cloudflare | Cloudflare→Server | Certificate Required | Use Case |
|------|-------------------|-------------------|---------------------|----------|
| **Off** | HTTP | HTTP | None | Development only |
| **Flexible** | HTTPS | HTTP | None | **API Server (no cert)** |
| **Full** | HTTPS | HTTPS | Self-signed OK | **WordPress + API** |
| **Full (Strict)** | HTTPS | HTTPS | Valid only | High security |

## Current Server Configuration

**WordPress (App Platform):**
- ✅ HTTPS certificate: Let's Encrypt (auto-renewed)
- ✅ Nginx reverse proxy with HTTPS support
- ✅ Requires "Full" SSL mode in Cloudflare

**FastAPI API (Droplet):**
- ✅ Nginx proxy: Port 80 → 8000 (FastAPI)
- ✅ Direct IP access: `http://206.189.185.129:8000/api/health`
- ❌ No HTTPS certificate on server (can't use "Full" SSL globally)
- ✅ Works with "Flexible" SSL mode via Page Rule

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