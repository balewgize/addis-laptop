# Laptop Addis

Extract structured laptop specifications from Ethiopian Telegram e-commerce channels using LLMs.

## Features

- 🔍 Scrapes laptop listings from multiple Telegram channels
- 🤖 Uses LLMs (via OpenRouter) to extract structured data
- 💡 AI-powered recommendations with pros/cons analysis
- 📊 Admin dashboard for channel management
- 🤖 Telegram bot interface
- 📈 Analytics (views, clicks) for monetization

## Quick Start

### 1. Install

```bash
git clone https://github.com/balewgize/telegram-laptop-scraper.git
cd telegram-laptop-scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Get API Credentials

**Telegram API:** https://my.telegram.org
**Telegram Bot:** https://t.me/BotFather
**OpenRouter:** https://openrouter.ai

### 4. Run

```bash
# Public website (view only)
streamlit run app/user_app.py

# Admin dashboard
streamlit run app/admin_app.py

# Telegram bot
python -m core.bot

# Scheduled sync
python scripts/sync_channels.py
```

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Skip slow tests (API calls)
pytest -m "not slow"

# Run specific test
pytest tests/test_database.py -v
```

## Project Structure

```
telegram-laptop-scraper/
├── core/  # Core package
│   ├── config.py            # Settings
│   ├── schemas.py           # Data models
│   ├── telegram.py          # Telegram client
│   ├── extractor.py         # LLM extraction
│   ├── database.py          # SQLite operations
│   ├── recommender.py       # AI recommendations
│   └── bot.py               # Telegram bot
├── app/
│   ├── user_app.py          # Public Streamlit
│   └── admin_app.py         # Admin dashboard
├── scripts/
│   └── sync_channels.py     # Scheduled sync
└── tests/                   # Test suite
```

## License

MIT
