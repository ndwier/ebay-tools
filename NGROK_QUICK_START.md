# 🚀 Quick Setup with Ngrok (5 Minutes)

This is the fastest way to get your eBay notification endpoint working.

## What is Ngrok?

Ngrok creates a secure public URL that tunnels to your local application. Perfect for:
- ✅ Testing eBay webhooks
- ✅ Running from home without port forwarding
- ✅ Getting started quickly

## Step-by-Step Setup

### 1. Install Ngrok

**On Mac:**
```bash
brew install ngrok
```

**On Raspberry Pi:**
```bash
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz
tar xvzf ngrok-v3-stable-linux-arm.tgz
sudo mv ngrok /usr/local/bin/
```

**On Linux:**
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

### 2. Sign Up for Ngrok (Free)

1. Go to https://dashboard.ngrok.com/signup
2. Create a free account
3. Copy your authtoken from the dashboard

### 3. Authenticate Ngrok

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

### 4. Start Your eBay Automation App

```bash
cd ebay-tools
docker-compose up -d
```

### 5. Start Ngrok Tunnel

```bash
ngrok http 5001
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123xyz.ngrok.io -> http://localhost:5001
```

**Copy the `https://` URL!** This is your public endpoint.

### 6. Configure in eBay Developer Portal

1. Go to https://developer.ebay.com/
2. Navigate to "My Account" → "Application Keys"
3. Click your application name
4. Scroll to "Event Notification Delivery Method"
5. Select "Platform Notifications (push)"
6. In "Marketplace account deletion notification endpoint", paste:
   ```
   https://abc123xyz.ngrok.io/webhook/marketplace-account-deletion
   ```
   (Replace with your actual Ngrok URL)
7. Enter your email for notifications
8. Click "Save"

### 7. Verify It Works

eBay will automatically verify your endpoint. Check your app logs:

```bash
docker-compose logs -f
```

Look for:
```
Received eBay verification challenge: [some code]
```

If you see this, you're all set! ✅

### 8. Access Your Dashboard

You can now access your dashboard via:
- **Local:** http://localhost:5001
- **Public (via Ngrok):** https://abc123xyz.ngrok.io

## 📱 Bonus: View Ngrok Inspector

Ngrok provides a web interface to inspect all requests:

Open http://127.0.0.1:4040 in your browser to see:
- All incoming requests
- Request/response details
- Timing information
- Perfect for debugging!

## ⚠️ Important Notes

### Free Plan Limitations

- ✅ HTTPS included (perfect for eBay)
- ✅ Unlimited use
- ⚠️ URL changes every time you restart Ngrok
- ⚠️ Session expires after 8 hours (reconnects automatically)

**For Production:** If the URL changes, you'll need to update it in eBay's developer portal again.

### Keeping Ngrok Running

To run Ngrok in the background on Raspberry Pi:

```bash
# Run in background
nohup ngrok http 5001 > ngrok.log 2>&1 &

# View the URL
curl http://localhost:4040/api/tunnels | grep -o 'https://[^"]*'
```

Or create a systemd service:

```bash
sudo nano /etc/systemd/system/ngrok.service
```

```ini
[Unit]
Description=Ngrok Tunnel
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/local/bin/ngrok http 5001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ngrok
sudo systemctl start ngrok
```

## 🔄 When You Restart

If your Ngrok URL changes:

1. Get the new URL:
   ```bash
   curl http://localhost:4040/api/tunnels | grep -o 'https://[^"]*'
   ```

2. Update in eBay Developer Portal

3. Save and eBay will re-verify automatically

## 💡 Pro Tips

1. **Bookmark the Ngrok dashboard:** http://127.0.0.1:4040
2. **Add Ngrok to your startup script** if running on Pi
3. **For production use:** Consider upgrading to Ngrok's paid plan for:
   - Static URLs (don't change)
   - Custom domains (like `ebay.yourdomain.com`)
   - Better reliability

## 🎯 Next Steps

Once you've verified your endpoint works:

1. ✅ Test sync listings in the dashboard
2. ✅ Verify automations are running
3. ✅ Check the activity logs

For **long-term production** use, consider:
- **Ngrok paid plan** ($8/month) - Static URLs
- **Cloudflare Tunnel** (Free) - See [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md)
- **VPS/Cloud hosting** - Most reliable

## 🆘 Troubleshooting

### "Connection refused"

```bash
# Make sure your app is running
docker-compose ps

# Should show container as "Up"
```

### "Invalid host header"

Ngrok passes the ngrok domain to your app. This is expected and works fine.

### "Can't access Ngrok URL"

- Ngrok should show "Session Status: online"
- Test locally first: `curl http://localhost:5001/health`
- Check firewall isn't blocking Ngrok

### "eBay can't verify endpoint"

- Make sure you used the **https://** URL (not http://)
- Check you included the full path: `/webhook/marketplace-account-deletion`
- Look for errors in: `docker-compose logs -f`

## ✅ Success Checklist

- [ ] Ngrok installed and authenticated
- [ ] eBay app running (`docker-compose ps`)
- [ ] Ngrok tunnel active (showing HTTPS URL)
- [ ] Endpoint configured in eBay Developer Portal
- [ ] eBay verification successful (check logs)
- [ ] Dashboard accessible

You're ready to automate your eBay store! 🎉

