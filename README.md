# Addis Laptop

Find the best laptop deals from Telegram channels.

A Telegram bot that scrapes laptop listings from tech channels, extracts specs using LLM, and provides intelligent search and AI-powered recommendations.

## Features

- **Browse** - View latest laptop listings with pagination
- **Search** - Filter by brand, price, RAM, screen size
- **AI Recommendations** - Get personalized suggestions based on use case and budget
- **Natural Language** - Just type what you're looking for: 
  - "Dell laptop under 100k"
  - "HP laptop 16GB RAM"
  - "ለቢሮ ሥራ የሚሆኑ ላፕቶፖች፣ ከ50ሺ በታች"
- **Voice Search** - Send a short voice message in _English_ or _አማርኛ_

## Architecture

<a href="https://github.com/balewgize/addis-laptop/blob/main/screenshots/architecture.png">View architecture diagram</a>

## Live Demo

- Telegram Bot: [@AddisLaptopBot](https://t.me/AddisLaptopBot)
- Web App: [https://laptops.balewgize.app/](https://laptops.balewgize.app/)

## Video

https://github.com/user-attachments/assets/7d06cf95-c7d7-4792-986c-a3d1bade1ffa

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram API credentials ([my.telegram.org](https://my.telegram.org))
- Telegram Bot token ([@BotFather](https://t.me/BotFather))
- OpenRouter API key ([openrouter.ai](https://openrouter.ai))
- Docker

### Installation

```bash
git clone https://github.com/balewgize/addis-laptop.git
cd addis-laptop
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

```bash
# .env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
OPENROUTER_API_KEY=your_openrouter_key

# Optional (for voice search)
ELEVENLABS_API_KEY=your_elevenlabs_key
```

### Data Extraction

```bash
# Option 1: From Telegram exports (recommended)
# Scrape manually from exported JSON (to avoid account ban)
# Export messages from Telegram Desktop (JSON format)
# Place the JSON file in the data/exports directory
# Filename must be channel username without @ symbol
# e.g. data/exports/username.json
python -m scripts.sync_json

# Option 2: Using Telethong Sync channels (scrape laptop listings)
# Note: It will require you to login to your Telegram account
# WARNING: This may get your account banned if used frequently
python -m scripts.sync_channels
```

### Run with Docker (local)

```bash
docker compose -f docker-compose-local.yml up --build
```

### Run with Docker (prod)

```bash
docker compose up -d --build
```

### Run each service alone (optional)

```bash
# Start the bot
# python -m bot.core

# # Run Streamlit user app
# streamlit run web/user.py

# # Run Streamlit admin app
# streamlit run web/admin.py
```

### Accessing 

- Telegram Bot: [@your_bot_user_name](https://t.me/your_bot_user_name)
- Web User: [http://localhost:8501/](http://localhost:8501/)
- Web Admin: [http://localhost:8502/](http://localhost:8502/)


## Project Structure

```
├── bot/                  # Telegram bot
│   ├── core.py          # Bot entry point
│   ├── handlers/        # Command & message handlers
│   ├── parser.py        # NL query parser
│   └── utils/           # Formatting, keyboards, pagination
├── core/                 # Core modules
│   ├── database.py      # SQLite operations
│   ├── extractor.py     # LLM spec extraction
│   ├── recommender.py   # AI recommendations
│   ├── schemas.py       # Data models
│   └── telegram.py      # Channel scraper
├── scripts/             # CLI utilities
│   └── sync_channels.py # Scrape channels
└── data/
    └── laptops.db       # SQLite database
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/browse` | Browse latest laptops |
| `/search` | Guided search with filters |
| `/recommend` | AI-powered recommendations |
| `/cancel` | Cancel current operation |
| `/help` | Show help |

Or just type naturally: *"Gaming laptop with 16GB RAM under 150k"*

## Tech Stack

- **Bot Framework**: python-telegram-bot
- **Scraping**: Telethon
- **Database**: SQLite + SQLModel
- **LLM**: Claude via OpenRouter
- **Validation**: Pydantic

## License

MIT
