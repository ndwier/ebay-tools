# Quick Start Guide

## 🎯 Goal
Get your eBay Store Automation running on your Raspberry Pi (or any server) in under 10 minutes.

## 📋 Prerequisites Checklist

Before starting, make sure you have:
- [ ] Docker installed on your system
- [ ] eBay Developer Account
- [ ] eBay API credentials (App ID, Dev ID, Cert ID)
- [ ] eBay OAuth User Token

## 🚀 5-Minute Setup

### Step 1: Get Your eBay Credentials (if you don't have them)

1. Go to https://developer.ebay.com/
2. Sign in with your eBay account
3. Go to "My Account" → "Keys"
4. Create a Production keyset
5. Save your:
   - App ID (Client ID)
   - Dev ID
   - Cert ID (Client Secret)
6. Generate an OAuth User Token (click "Get OAuth Application Token")

### Step 2: Configure the Application

```bash
# Navigate to the ebay-tools directory
cd ebay-tools

# Copy the environment template
cp env_template.txt .env

# Edit the .env file with your credentials
nano .env
```

**Minimum required settings:**
```bash
EBAY_APP_ID=your_app_id_here
EBAY_CERT_ID=your_cert_id_here
EBAY_DEV_ID=your_dev_id_here
EBAY_TOKEN=your_oauth_token_here
```

Save and exit (Ctrl+X, then Y, then Enter in nano).

### Step 3: Start the Application

```bash
# Build and start
docker-compose up -d

# Check if it's running
docker-compose ps
```

You should see the container running on port 5001.

### Step 4: Access Your Dashboard

Open your browser to:
- **Local:** http://localhost:5001
- **Raspberry Pi:** http://your-pi-ip-address:5001

You should see your eBay Store Automation dashboard!

## ✅ Verify It's Working

1. **Check the dashboard loads** - You should see the stats page
2. **Click "Sync Listings"** - This will fetch your eBay listings
3. **Check the logs** - You should see activity in the "Recent Activity" section
4. **View scheduled jobs** - Should show 5 scheduled automation tasks

## 🎛️ Next Steps

### Customize Automation Settings

Edit your `.env` file to adjust:

```bash
# How many days before relisting
STALE_LISTING_DAYS=30

# When to send offers
MIN_VIEWS_FOR_OFFER=5
OFFER_DISCOUNT_PERCENT=10

# When to request feedback
FEEDBACK_REQUEST_DAYS=7
```

After changing settings:
```bash
docker-compose restart
```

### Monitor Your Automations

The dashboard will show:
- **Active Listings** - Total number of items for sale
- **Stale Listings** - Items that need relisting
- **Pending Feedback** - Sales awaiting feedback request
- **Today's Activity** - Relists and offers sent today

### Set Your Schedule

By default, automations run:
- **2:00 AM** - Check and relist stale listings
- **10:00 AM** - Check for offer opportunities
- **3:00 PM** - Request feedback from buyers
- **Every hour** - Sync listings from eBay
- **Every 2 hours** - Sync sold items

Edit these in your `.env` file using cron format:
```bash
STALE_CHECK_SCHEDULE=0 2 * * *
OFFER_CHECK_SCHEDULE=0 10 * * *
FEEDBACK_CHECK_SCHEDULE=0 15 * * *
```

## 🔧 Common Commands

```bash
# View live logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Stop the service
docker-compose down

# Update and restart
git pull
docker-compose up -d --build

# Backup your database
cp data/ebay_automation.db data/backup_$(date +%Y%m%d).db
```

## 🆘 Troubleshooting

### Container won't start
```bash
# Check logs for errors
docker-compose logs

# Common issues:
# - Missing .env file -> Copy from env_template.txt
# - Invalid credentials -> Double-check your eBay API keys
# - Port 5001 in use -> Change FLASK_PORT in .env
```

### Can't access dashboard
- Check firewall settings on your Pi
- Verify the container is running: `docker-compose ps`
- Try accessing via IP instead of hostname

### API errors in logs
- Verify your OAuth token hasn't expired
- Check you're using production credentials (not sandbox)
- Ensure your eBay account has API access enabled

## 💡 Pro Tips

1. **Test First**: Use eBay's sandbox environment first by setting `EBAY_ENV=sandbox` in your `.env`

2. **Start Conservative**: Begin with high values (e.g., `STALE_LISTING_DAYS=60`) and adjust down

3. **Monitor Initially**: Check the dashboard daily for the first week to ensure automations work as expected

4. **Backup Regularly**: Your database contains all automation history
   ```bash
   # Add to crontab for weekly backups
   0 0 * * 0 cp /path/to/ebay-tools/data/ebay_automation.db /path/to/backups/ebay_$(date +\%Y\%m\%d).db
   ```

5. **Mobile Access**: Access your dashboard from your phone using your Pi's IP address

## 🎉 You're Done!

Your eBay store is now running on autopilot. The system will:
- ✅ Keep your listings fresh by relisting stale items
- ✅ Track views and watchers
- ✅ Identify offer opportunities
- ✅ Request feedback at the right time
- ✅ Log all activities for your review

Sit back and let the automation work for you! 🚀


