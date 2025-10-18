# 🍓 Raspberry Pi Deployment Guide

Your eBay automation is now on GitHub and ready to deploy!

## 🚀 Quick Deployment (5 Minutes)

### Step 1: SSH into Your Raspberry Pi

From your Mac:

```bash
ssh pi@raspberrypi.local
# Or if that doesn't work, use the IP address:
# ssh pi@192.168.1.XXX
```

Default password is usually `raspberry` (change this if you haven't already!)

### Step 2: Run the Automated Deployment

Once logged into your Pi, run:

```bash
curl -fsSL https://raw.githubusercontent.com/ndwier/ebay-tools/main/deploy-to-pi.sh | bash
```

Or manually:

```bash
cd ~
git clone https://github.com/ndwier/ebay-tools.git
cd ebay-tools
chmod +x deploy-to-pi.sh
./deploy-to-pi.sh
```

### Step 3: Configure Your eBay Credentials

The script will prompt you to edit the `.env` file:

```bash
nano .env
```

Fill in your eBay API credentials:
```
EBAY_APP_ID=your_app_id_here
EBAY_CERT_ID=your_cert_id_here
EBAY_DEV_ID=your_dev_id_here
EBAY_TOKEN=your_oauth_token_here
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

### Step 4: The Script Does the Rest!

The deployment script will:
- ✅ Install Docker (if needed)
- ✅ Clone the repository
- ✅ Build the Docker container
- ✅ Start the application
- ✅ Display your dashboard URL

## 📊 Access Your Dashboard

After deployment, access your dashboard:

**From any device on your network:**
```
http://raspberrypi.local:5001
```

**Or use your Pi's IP address:**
```
http://192.168.1.XXX:5001
```

To find your Pi's IP:
```bash
hostname -I
```

## 🔍 Verify Everything is Running

### Check Container Status

```bash
cd ~/ebay-tools
docker compose ps
```

Should show:
```
NAME                COMMAND             STATUS
ebay-automation    "python app.py"     Up X minutes
```

### View Logs

```bash
docker compose logs -f
```

Press `Ctrl+C` to exit log view.

### Test the Dashboard

1. Open http://raspberrypi.local:5001
2. Click "Sync Listings"
3. Watch the activity log populate
4. Check stats update

## 🌐 Connect Ngrok from Your Pi

Since the app is now running on the Pi, you need ngrok running there too:

### Option A: Move Ngrok to Pi (Recommended)

**On your Pi:**

```bash
# Install ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz
tar xvzf ngrok-v3-stable-linux-arm.tgz
sudo mv ngrok /usr/local/bin/
rm ngrok-v3-stable-linux-arm.tgz

# Authenticate (use your same token)
ngrok config add-authtoken 34DknjkfUV7AuF3CX8JFFMdZYsL_6RQ68RXJzTkWfFxekzXMj

# Start tunnel
ngrok http 5001
```

**Note:** You can now stop ngrok on your Mac (it's not needed there anymore).

### Option B: SSH Tunnel (Advanced)

Keep ngrok on your Mac and tunnel through SSH:

```bash
# On your Mac
ssh -R 5001:localhost:5001 pi@raspberrypi.local
```

Then ngrok on your Mac will tunnel to the Pi.

## 🔄 Common Commands

### View Logs
```bash
cd ~/ebay-tools
docker compose logs -f
```

### Restart Application
```bash
cd ~/ebay-tools
docker compose restart
```

### Stop Application
```bash
cd ~/ebay-tools
docker compose down
```

### Start Application
```bash
cd ~/ebay-tools
docker compose up -d
```

### Update from GitHub
```bash
cd ~/ebay-tools
git pull
docker compose up -d --build
```

### View Resource Usage
```bash
docker stats ebay-automation
```

## 📱 Make it Auto-Start on Boot

To ensure your eBay automation starts when the Pi boots:

```bash
# Create systemd service
sudo nano /etc/systemd/system/ebay-automation.service
```

Add this content:

```ini
[Unit]
Description=eBay Store Automation
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/ebay-tools
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable ebay-automation
sudo systemctl start ebay-automation
```

## 🔧 Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker compose logs

# Verify .env file exists and has credentials
cat .env | grep EBAY_APP_ID

# Rebuild container
docker compose down
docker compose up -d --build
```

### Can't Access Dashboard

```bash
# Check container is running
docker compose ps

# Check firewall (shouldn't be an issue on default Pi setup)
sudo ufw status

# Test locally on Pi
curl http://localhost:5001/health
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a

# Remove old images
docker image prune -a
```

### Permission Errors

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then test
docker ps
```

## 🎯 What's Running

Your Raspberry Pi is now running:
- ✅ **Flask web server** on port 5001
- ✅ **Background scheduler** for automated tasks
- ✅ **SQLite database** in `~/ebay-tools/data/`
- ✅ **Activity logs** in `~/ebay-tools/logs/`

## 📊 Monitor Performance

### Check Resource Usage

```bash
# Overall Pi stats
htop

# Docker container stats
docker stats ebay-automation

# Disk usage
du -sh ~/ebay-tools/data
du -sh ~/ebay-tools/logs
```

Typical resource usage:
- **RAM:** ~150 MB
- **CPU:** <5% average
- **Disk:** ~50 MB + database growth

## 🔐 Security Recommendations

1. **Change default Pi password:**
   ```bash
   passwd
   ```

2. **Update Pi regularly:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Secure SSH:**
   ```bash
   # Edit SSH config
   sudo nano /etc/ssh/sshd_config
   
   # Disable password auth, use keys only
   PasswordAuthentication no
   
   # Restart SSH
   sudo systemctl restart ssh
   ```

4. **Firewall (optional):**
   ```bash
   sudo ufw allow 5001/tcp
   sudo ufw enable
   ```

## 📚 Next Steps

1. ✅ Verify dashboard is accessible
2. ✅ Configure ngrok endpoint in eBay portal
3. ✅ Test "Sync Listings" button
4. ✅ Let automations run for 24 hours
5. ✅ Review activity logs
6. ✅ Adjust settings as needed

## 🆘 Need Help?

**Check logs first:**
```bash
cd ~/ebay-tools
docker compose logs -f
```

**Common issues:**
- Missing .env file → Run: `cp env_template.txt .env && nano .env`
- Invalid credentials → Double-check your eBay API keys
- Port conflict → Change `FLASK_PORT=5001` in .env to another port
- Out of memory → Restart Pi: `sudo reboot`

## 🎉 Success!

Your eBay store automation is now running 24/7 on your Raspberry Pi!

**Dashboard:** http://raspberrypi.local:5001  
**Logs:** `docker compose logs -f`  
**Location:** `~/ebay-tools/`

Enjoy your automated eBay store! 🛒🤖

