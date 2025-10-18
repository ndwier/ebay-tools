# 🛒 eBay Store Automation

A self-hosted automation tool for managing your eBay store. Automates relisting stale items, sending promotional offers, requesting feedback, and more.

## ✨ Features

- **🔄 Automatic Listing Sync**: Keep your local database in sync with eBay
- **📊 Stale Listing Detection**: Identify and automatically relist items that aren't getting views
- **💰 Smart Offer Management**: Send promotional offers to watchers
- **⭐ Feedback Automation**: Request feedback from buyers at the right time
- **📈 Analytics Dashboard**: Beautiful web interface to monitor your store
- **⏰ Scheduled Tasks**: Run automations at optimal times
- **🐳 Docker Ready**: Easy deployment with Docker on Raspberry Pi or any server

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- eBay Developer Account with API credentials
- Your eBay OAuth token

### Getting Your eBay API Credentials

1. Go to [eBay Developer Program](https://developer.ebay.com/)
2. Create an account or sign in
3. Navigate to "My Account" → "Keys"
4. Create a new keyset (Production)
5. Note your App ID, Dev ID, and Cert ID
6. Generate an OAuth User Token (you'll need to authorize your app)
7. **Important:** Configure the Marketplace Account Deletion endpoint (see [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md))

### Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd ebay-tools
   ```

2. **Create your environment file:**
   ```bash
   cp env_template.txt .env
   ```

3. **Edit the `.env` file with your credentials:**
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

4. **Set up public endpoint for eBay notifications (Required):**
   
   eBay requires a public HTTPS endpoint for account deletion notifications. See [EBAY_NOTIFICATION_SETUP.md](EBAY_NOTIFICATION_SETUP.md) for detailed instructions.
   
   **Quick option:** Use Ngrok for testing:
   ```bash
   ngrok http 5001
   # Copy the HTTPS URL and configure in eBay Developer Portal
   ```

5. **Build and start the container:**
   ```bash
   docker-compose up -d
   ```

6. **Access the dashboard:**
   Open your browser to `http://localhost:5001` (or `http://your-raspberry-pi-ip:5001`)

## 🎛️ Configuration

All settings can be configured in your `.env` file:

### Automation Settings

```bash
# How many days before a listing is considered stale
STALE_LISTING_DAYS=30

# Minimum number of views before sending offers
MIN_VIEWS_FOR_OFFER=5

# Offer discount percentage
OFFER_DISCOUNT_PERCENT=10

# Days after sale to request feedback
FEEDBACK_REQUEST_DAYS=7
```

### Schedule Settings (Cron Format)

```bash
# Check for stale listings daily at 2 AM
STALE_CHECK_SCHEDULE=0 2 * * *

# Check for offer opportunities daily at 10 AM
OFFER_CHECK_SCHEDULE=0 10 * * *

# Check for feedback requests daily at 3 PM
FEEDBACK_CHECK_SCHEDULE=0 15 * * *
```

## 📱 Dashboard Features

### Overview Statistics
- Active listings count
- Stale listings needing attention
- Total views and watchers
- Pending feedback requests
- Daily automation activity

### Manual Actions
- Sync listings on demand
- Trigger stale listing checks
- Check for offer opportunities
- Request feedback immediately

### Scheduled Jobs
- View all scheduled automation tasks
- See next run times
- Monitor job status

### Activity Logs
- Track all automation activities
- Filter by action type
- View success/failure status
- Detailed messages for each action

## 🍓 Raspberry Pi Deployment

This application is optimized for Raspberry Pi and works great alongside other services like Home Assistant.

### Resource Requirements

- **RAM**: ~100-200 MB
- **CPU**: Minimal (runs scheduled tasks, not CPU-intensive)
- **Disk**: ~50 MB for application + space for database
- **Network**: Periodic API calls to eBay

### Running on Raspberry Pi

1. **SSH into your Raspberry Pi:**
   ```bash
   ssh pi@raspberrypi.local
   ```

2. **Install Docker (if not already installed):**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Clone the repository:**
   ```bash
   cd ~
   git clone <your-repo-url> ebay-tools
   cd ebay-tools
   ```

4. **Follow the Quick Start instructions above**

The Docker image will automatically build for ARM architecture on Raspberry Pi.

## 🔧 Maintenance

### View Logs
```bash
docker-compose logs -f
```

### Restart the Service
```bash
docker-compose restart
```

### Update the Application
```bash
docker-compose down
git pull
docker-compose up -d --build
```

### Backup Database
```bash
cp data/ebay_automation.db data/ebay_automation_backup_$(date +%Y%m%d).db
```

## 📊 How It Works

### Automation Flow

1. **Listing Sync** (Every hour)
   - Fetches all active listings from eBay
   - Updates database with current views, watchers, prices
   - Marks listings as inactive if they ended

2. **Stale Listing Check** (Daily at 2 AM)
   - Identifies listings older than configured days with low views
   - Automatically relists items to refresh visibility
   - Logs all relist attempts

3. **Offer Opportunities** (Daily at 10 AM)
   - Finds listings with watchers but no sales
   - Creates promotional offer records
   - Tracks offer history to avoid spamming

4. **Feedback Requests** (Daily at 3 PM)
   - Syncs sold items from eBay
   - Identifies sales ready for feedback request
   - Sends automated feedback requests via eBay API

## 🛠️ Development

### Local Development (without Docker)

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file** (see Quick Start)

4. **Run the application:**
   ```bash
   python app.py
   ```

### Project Structure

```
ebay-tools/
├── app.py                 # Main Flask application
├── ebay_api.py           # eBay API integration
├── automation.py         # Automation rules engine
├── scheduler.py          # Task scheduler
├── models.py             # Database models
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
├── templates/            # HTML templates
│   └── dashboard.html
├── data/                 # SQLite database (auto-created)
└── logs/                 # Application logs (auto-created)
```

## 🔐 Security Notes

- Never commit your `.env` file
- Keep your eBay API credentials secure
- Use OAuth tokens with appropriate scopes
- Run the container on a private network or behind a reverse proxy
- Consider using environment-specific tokens (sandbox vs production)

## 📝 eBay API Limitations

- **Rate Limits**: eBay has daily API call limits. This tool respects those limits with scheduled tasks.
- **Offer Sending**: Some offer features may require eBay's promotional tools or marketing APIs.
- **Feedback**: Feedback requests follow eBay's policies and timing restrictions.

## 🐛 Troubleshooting

### Container won't start
- Check logs: `docker-compose logs`
- Verify `.env` file exists and has valid credentials
- Ensure port 5001 is not already in use

### API errors
- Verify your eBay credentials are correct
- Check if your OAuth token has expired
- Ensure you're using the right environment (production vs sandbox)

### Database errors
- Check file permissions on `data/` directory
- Try removing the database and letting it recreate: `rm data/ebay_automation.db`

### No automations running
- Check the dashboard's "Scheduled Jobs" section
- Verify logs with `docker-compose logs`
- Ensure the scheduler is running (check health endpoint)

## 🚀 Future Enhancements

Possible additions for future versions:
- Email notifications for important events
- More advanced pricing strategies
- Inventory management integration
- Sales analytics and reporting
- Mobile app for monitoring
- Integration with other marketplaces

## 📄 License

This project is for personal use. Be sure to comply with eBay's API Terms of Service.

## 🤝 Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Review eBay API documentation
3. Verify your credentials and permissions

## ⚠️ Disclaimer

This tool automates interactions with your eBay store. Always review eBay's policies and test thoroughly with sandbox credentials before using in production. The author is not responsible for any issues arising from use of this tool.

---

Made with ❤️ for eBay sellers who want to automate the boring stuff!

