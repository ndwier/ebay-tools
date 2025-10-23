# ✅ eBay Automation Setup Checklist

Follow this checklist to get your eBay store automation running!

## 📋 Pre-Setup (Do First)

### eBay Developer Account Setup

- [ ] Sign up at https://developer.ebay.com/
- [ ] Create a Production keyset in "My Account" → "Keys"
- [ ] Save your credentials:
  - [ ] App ID (Client ID)
  - [ ] Dev ID
  - [ ] Cert ID (Client Secret)
- [ ] Generate OAuth User Token
- [ ] Save token securely

## 🔧 Application Setup

### On Your Raspberry Pi (or any server)

- [ ] Docker installed (`docker --version`)
- [ ] Docker Compose installed (`docker-compose --version`)
- [ ] Navigate to ebay-tools directory
- [ ] Copy environment file: `cp env_template.txt .env`
- [ ] Edit `.env` with your eBay credentials
- [ ] Start application: `docker-compose up -d`
- [ ] Verify running: `docker-compose ps`
- [ ] Test locally: http://localhost:5001

## 🌐 Public Endpoint Setup (REQUIRED)

eBay requires a public HTTPS endpoint. Choose one option:

### Option A: Ngrok (Quickest - 5 minutes)

- [ ] Install Ngrok
- [ ] Sign up for free account at https://ngrok.com
- [ ] Authenticate: `ngrok config add-authtoken YOUR_TOKEN`
- [ ] Start tunnel: `ngrok http 5001`
- [ ] Copy the HTTPS URL (like `https://abc123.ngrok.io`)
- [ ] Keep terminal open (or run in background)

**See [NGROK_QUICK_START.md](NGROK_QUICK_START.md) for detailed steps**

### Option B: Cloudflare Tunnel (Best for long-term)

- [ ] Install cloudflared
- [ ] Authenticate: `cloudflared tunnel login`
- [ ] Create tunnel
- [ ] Configure DNS
- [ ] Run tunnel service

**See [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md) for detailed steps**

### Option C: Port Forwarding + Dynamic DNS

- [ ] Configure router port forwarding (443 → Pi:5001)
- [ ] Set up Dynamic DNS service
- [ ] Get SSL certificate with Let's Encrypt
- [ ] Configure Nginx reverse proxy

**See [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md) for detailed steps**

## 🔗 eBay Developer Portal Configuration

### Configure Notification Endpoint

- [ ] Go to https://developer.ebay.com/
- [ ] Navigate to "My Account" → "Application Keys"
- [ ] Click your application name
- [ ] Scroll to "Event Notification Delivery Method"
- [ ] Select "Platform Notifications (push)"
- [ ] Configure "Marketplace Account Deletion":
  - [ ] Enter your email for notifications
  - [ ] Enter endpoint URL:
    ```
    https://your-ngrok-url.ngrok.io/webhook/marketplace-account-deletion
    ```
  - [ ] Leave verification token blank
  - [ ] Click "Save"
- [ ] Wait for eBay to verify endpoint (automatic)
- [ ] Check logs for verification: `docker-compose logs -f`
- [ ] Look for: `Received eBay verification challenge`
- [ ] Confirm eBay portal shows ✅ "Verified"

## 🧪 Testing & Verification

### Test Your Setup

- [ ] Access dashboard: http://localhost:5001 (or your Pi's IP)
- [ ] Click "Sync Listings" button
- [ ] Wait for sync to complete
- [ ] Verify listings appear in dashboard
- [ ] Check "Recent Activity" for sync logs
- [ ] View "Scheduled Jobs" section
- [ ] Confirm 5 jobs are scheduled

### Test Notifications (Optional)

- [ ] Test challenge response:
  ```bash
  curl "http://localhost:5001/webhook/marketplace-account-deletion?challenge_code=test"
  ```
- [ ] Should return: `{"challengeResponse": "test"}`

## 📊 Dashboard Verification

### Verify Everything Works

- [ ] **Stats showing:**
  - [ ] Active listings count
  - [ ] Total views
  - [ ] Total watchers
- [ ] **Manual actions work:**
  - [ ] Click "Sync Listings" - works
  - [ ] Check logs - activity recorded
- [ ] **Scheduled jobs visible:**
  - [ ] Listing sync (hourly)
  - [ ] Stale check (2 AM)
  - [ ] Offer check (10 AM)
  - [ ] Sold items sync (2 hours)
  - [ ] Feedback check (3 PM)

## ⚙️ Configuration (Optional)

### Customize Settings in `.env`

Default settings work great, but you can adjust:

- [ ] Review automation thresholds:
  - `STALE_LISTING_DAYS=30`
  - `MIN_VIEWS_FOR_OFFER=5`
  - `OFFER_DISCOUNT_PERCENT=10`
  - `FEEDBACK_REQUEST_DAYS=7`
- [ ] Adjust schedules (cron format):
  - `STALE_CHECK_SCHEDULE=0 2 * * *`
  - `OFFER_CHECK_SCHEDULE=0 10 * * *`
  - `FEEDBACK_CHECK_SCHEDULE=0 15 * * *`
- [ ] Restart if changed: `docker-compose restart`

## 🎯 First 24 Hours

### Monitor Initial Operation

- [ ] Check dashboard once after 1 hour
- [ ] Verify sync happened (check "Recent Activity")
- [ ] Review any errors in logs
- [ ] Wait for first automated tasks overnight
- [ ] Check dashboard next morning
- [ ] Review "Relists Today" count
- [ ] Check activity log for overnight actions

## 📱 Mobile Access (Optional)

### Access from Phone/Tablet

- [ ] Find your Pi's IP: `hostname -I`
- [ ] Access from mobile browser: `http://pi-ip:5001`
- [ ] Bookmark for easy access
- [ ] Works great for monitoring on the go!

## 🔒 Security Hardening (Optional but Recommended)

### Additional Security Steps

- [ ] Change Flask secret key in `.env`
- [ ] Set up Nginx with authentication
- [ ] Enable firewall on Pi
- [ ] Use VPN for remote access
- [ ] Regular database backups:
  ```bash
  cp data/ebay_automation.db data/backup_$(date +%Y%m%d).db
  ```

## 🆘 Troubleshooting

### Common Issues

**Container won't start:**
- [ ] Check logs: `docker-compose logs`
- [ ] Verify `.env` exists
- [ ] Check port 5001 not in use

**Can't access dashboard:**
- [ ] Verify container running: `docker-compose ps`
- [ ] Check firewall settings
- [ ] Try Pi's IP instead of localhost

**eBay endpoint won't verify:**
- [ ] Confirm using HTTPS (not HTTP)
- [ ] Test endpoint externally
- [ ] Check Ngrok is running
- [ ] Verify full path included

**No listings syncing:**
- [ ] Check eBay credentials in `.env`
- [ ] Verify OAuth token hasn't expired
- [ ] Check logs for API errors
- [ ] Test with manual "Sync Listings"

## 📚 Documentation Reference

Quick links to detailed guides:

- **Setup:** [README.md](README.md) - Main documentation
- **Quick Start:** [QUICK_START.md](QUICK_START.md) - 5-minute guide
- **Ngrok:** [NGROK_QUICK_START.md](NGROK_QUICK_START.md) - Ngrok setup
- **Notifications:** [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md) - Endpoint details
- **Technical:** [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Full project details

## ✅ Success Criteria

You're fully set up when:

- ✅ Docker container running
- ✅ Dashboard accessible
- ✅ Listings synced and visible
- ✅ Scheduled jobs configured
- ✅ eBay endpoint verified
- ✅ Activity log showing actions
- ✅ No errors in logs

## 🎉 You're Done!

Congratulations! Your eBay store is now automated. The system will:

- ✅ Sync listings hourly
- ✅ Relist stale items daily
- ✅ Identify offer opportunities
- ✅ Request feedback automatically
- ✅ Track everything in the dashboard

**Sit back and let it work!** 🚀

## 📞 Need Help?

1. Check logs: `docker-compose logs -f`
2. Review documentation in the `/docs` folder
3. Test endpoints manually with curl
4. Verify eBay credentials are correct

---

**Time Estimate:** 15-30 minutes total setup time
**Difficulty:** Easy (if following steps)
**Maintenance:** < 5 minutes per week


