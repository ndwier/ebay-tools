# eBay Marketplace Account Deletion Endpoint Setup

## Why This is Required

eBay requires all applications to implement a **Marketplace Account Deletion notification endpoint** for GDPR/privacy compliance. This endpoint allows eBay to notify you when a user deletes their marketplace account, so you can delete their data from your system.

**You cannot use certain eBay API features until this endpoint is configured.**

## 📍 Your Endpoint URL

Your notification endpoint is:
```
https://your-domain.com/webhook/marketplace-account-deletion
```

If running locally or on Raspberry Pi without a public domain:
```
https://your-public-ip:5001/webhook/marketplace-account-deletion
```

⚠️ **Important:** eBay requires an **HTTPS** endpoint (not HTTP). You'll need SSL/TLS configured.

## 🔧 Setup Steps in eBay Developer Portal

### Step 1: Access Your Application Settings

1. Go to https://developer.ebay.com/
2. Sign in with your eBay account
3. Click "My Account" → "Application Keys"
4. Click on your application name

### Step 2: Configure Event Notifications

1. Scroll down to **"Event Notification Delivery Method"**
2. Select **"Platform Notifications (push)"**

### Step 3: Marketplace Account Deletion Settings

In the **"Marketplace Account Deletion"** section:

1. **Email to notify if endpoint is down:**
   ```
   your-email@example.com
   ```
   
2. **Marketplace account deletion notification endpoint:**
   ```
   https://your-domain.com/webhook/marketplace-account-deletion
   ```
   Replace with your actual domain or public IP
   
3. **Verification token:** (Optional)
   ```
   leave blank for now
   ```
   Our endpoint doesn't require a verification token, but you can add one if needed

4. Click **"Save"**

### Step 4: Endpoint Verification

After saving, eBay will send a verification request to your endpoint:

1. eBay sends a GET request with a `challenge_code` parameter
2. Your endpoint responds with `{"challengeResponse": "the_code"}`
3. If successful, eBay marks your endpoint as verified ✅

You can monitor the verification in your logs:
```bash
docker-compose logs -f
```

Look for:
```
Received eBay verification challenge: [challenge_code]
```

## 🌐 Making Your Endpoint Publicly Accessible

Since you're running on a Raspberry Pi, you have several options:

### Option 1: Ngrok (Quick & Easy for Testing)

**Best for:** Testing and development

```bash
# Install ngrok
# Visit https://ngrok.com/ and create a free account

# Run ngrok to expose your local port
ngrok http 5001
```

Ngrok will give you a public HTTPS URL like:
```
https://abc123.ngrok.io
```

Use this in eBay's settings:
```
https://abc123.ngrok.io/webhook/marketplace-account-deletion
```

⚠️ **Note:** Free ngrok URLs change every time you restart. For production, use a paid plan or another solution.

### Option 2: Cloudflare Tunnel (Free & Permanent)

**Best for:** Long-term production use

1. **Install Cloudflared on your Raspberry Pi:**
   ```bash
   # Download cloudflared
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm
   sudo mv cloudflared-linux-arm /usr/local/bin/cloudflared
   sudo chmod +x /usr/local/bin/cloudflared
   
   # Authenticate
   cloudflared tunnel login
   ```

2. **Create a tunnel:**
   ```bash
   cloudflared tunnel create ebay-automation
   ```

3. **Configure the tunnel:**
   Create `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: ebay-automation
   credentials-file: /home/pi/.cloudflared/[tunnel-id].json
   
   ingress:
     - hostname: ebay.your-domain.com
       service: http://localhost:5001
     - service: http_status:404
   ```

4. **Add DNS record in Cloudflare dashboard**

5. **Run the tunnel:**
   ```bash
   cloudflared tunnel run ebay-automation
   ```

Your endpoint will be:
```
https://ebay.your-domain.com/webhook/marketplace-account-deletion
```

### Option 3: Port Forwarding + Dynamic DNS

**Best for:** If you own a domain and can configure your router

1. **Configure port forwarding on your router:**
   - Forward port 443 → Your Pi's IP:5001
   - Or use a reverse proxy like Nginx

2. **Set up Dynamic DNS:**
   - Use a service like DuckDNS, No-IP, or Dynu
   - Get a free subdomain: `your-name.duckdns.org`

3. **Set up SSL certificate:**
   ```bash
   # Install certbot
   sudo apt install certbot
   
   # Get SSL certificate
   sudo certbot certonly --standalone -d your-name.duckdns.org
   ```

4. **Configure Nginx as reverse proxy:**
   ```nginx
   server {
       listen 443 ssl;
       server_name your-name.duckdns.org;
       
       ssl_certificate /etc/letsencrypt/live/your-name.duckdns.org/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-name.duckdns.org/privkey.pem;
       
       location / {
           proxy_pass http://localhost:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

Your endpoint will be:
```
https://your-name.duckdns.org/webhook/marketplace-account-deletion
```

### Option 4: VPS/Cloud Proxy (Most Reliable)

**Best for:** Production, if you want guaranteed uptime

1. Set up a small VPS (DigitalOcean, AWS, etc.)
2. Install Nginx as a reverse proxy
3. Point it to your home Pi via VPN (WireGuard or Tailscale)
4. Use the VPS's IP/domain for eBay

## 🧪 Testing Your Endpoint

### Test Locally First

```bash
# Test the challenge response
curl "http://localhost:5001/webhook/marketplace-account-deletion?challenge_code=test123"

# Should return:
# {"challengeResponse": "test123"}
```

### Test eBay's Verification

After configuring in eBay's portal:

1. Save your endpoint URL
2. eBay automatically sends a verification request
3. Check your logs:
   ```bash
   docker-compose logs -f | grep "verification challenge"
   ```
4. If successful, eBay's portal shows ✅ "Verified"

### Test Account Deletion (Manual)

You can simulate an account deletion notification:

```bash
curl -X POST http://localhost:5001/webhook/marketplace-account-deletion \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "notificationId": "test123",
      "topic": "MARKETPLACE_ACCOUNT_DELETION"
    },
    "notification": {
      "data": {
        "userId": "testuser123",
        "marketplaceId": "EBAY_US"
      }
    }
  }'
```

Check logs to confirm it processed:
```bash
docker-compose logs | grep "account_deletion"
```

## 🔍 What the Endpoint Does

1. **Verification (GET request):**
   - eBay sends: `?challenge_code=abc123`
   - Endpoint returns: `{"challengeResponse": "abc123"}`
   - eBay marks as verified ✅

2. **Account Deletion Notification (POST request):**
   - eBay sends user deletion data
   - Endpoint deletes buyer data from `sold_items` table
   - Logs the deletion in `automation_logs`
   - Returns success confirmation to eBay

## 📊 Monitoring Notifications

View account deletion notifications in your dashboard:

1. Go to http://your-pi-ip:5001
2. Click "Recent Activity" section
3. Filter by "account_deletion" type
4. See all processed deletions

Or check logs directly:
```bash
docker-compose logs | grep "Account deletion notification"
```

## ⚠️ Troubleshooting

### "Endpoint verification failed"

- ✅ Check endpoint is publicly accessible via HTTPS
- ✅ Test with curl from external network
- ✅ Check firewall allows incoming connections
- ✅ Verify container is running: `docker-compose ps`
- ✅ Check logs for errors: `docker-compose logs -f`

### "SSL certificate error"

- eBay requires valid SSL certificates
- Self-signed certificates won't work
- Use Let's Encrypt (free) or Cloudflare (free)

### "Endpoint not responding"

- ✅ Verify Docker container is running
- ✅ Check port 5001 is accessible
- ✅ Test locally first, then externally
- ✅ Check reverse proxy configuration (if using)

### "Still can't unlock API"

- Some eBay API features require additional verification
- Ensure your developer account is approved
- Contact eBay Developer Support if issues persist

## 🎯 Recommended Setup

**For most users (running on Raspberry Pi at home):**

1. **Short term / Testing:** Use **Ngrok** (5 min setup)
2. **Long term / Production:** Use **Cloudflare Tunnel** (free, reliable, permanent URL)

Both provide HTTPS automatically and work behind NAT/firewall.

## 📧 Support

If you continue to have issues with endpoint verification:

1. Check logs: `docker-compose logs -f`
2. Test endpoint externally: `curl https://your-url/webhook/marketplace-account-deletion?challenge_code=test`
3. Verify SSL certificate is valid: `openssl s_client -connect your-domain.com:443`
4. Contact eBay Developer Support with your application details

## 📝 Summary

✅ **Endpoint added:** `/webhook/marketplace-account-deletion`  
✅ **Handles:** GET (verification) and POST (notifications)  
✅ **Compliant:** GDPR/privacy requirements met  
✅ **Logged:** All activity tracked in database  

Just set up public access (Ngrok/Cloudflare recommended) and configure in eBay's developer portal!


