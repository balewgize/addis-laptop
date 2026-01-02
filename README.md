# Telegram Laptop Scraper

Extract structured laptop specifications from Ethiopian Telegram e-commerce channels using LLMs.

## Features

- 🔍 Scrapes laptop listings from Telegram channels
- 🤖 Uses LLMs (via OpenRouter) to extract structured data
- 💾 Stores data in SQLite for easy querying
- 🎯 Simple recommendation engine based on your needs
- 🌐 FastAPI backend + Streamlit UI

## Sample Input

```
✅✅New arrival 2024!!
DELL INSPIRON 
✅ 14th generation  
✅ Intel core Ultra 7 150U
✅Storage : 1TB Nvme SSD
✅Ram : 16gb DDR4
Price : 128,500Birr
📞0932823071
```

## Sample Output

```json
{
  "brand": "Dell",
  "model": "Inspiron 16 5640",
  "cpu": "Intel Core Ultra 7 150U",
  "ram_gb": 16,
  "storage_gb": 1000,
  "price_etb": 128500,
  "condition": "new",
  "contact": "0932823071"
}
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourusername/telegram-laptop-scraper.git
cd telegram-laptop-scraper
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Get API credentials

**Telegram API:**
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Create an application
4. Copy `api_id` and `api_hash`

**OpenRouter API:**
1. Go to https://openrouter.ai
2. Create an account
3. Generate an API key

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 4. First run (Telegram auth)

```bash
python -c "from telegram_laptop_scraper.telegram import TelegramClient; import asyncio; asyncio.run(TelegramClient().connect())"
```

This will prompt for your phone number and verification code (one-time setup).

### 5. Run the app

**Option A: Streamlit UI**
```bash
streamlit run streamlit_app.py
```

**Option B: API server**
```bash
uvicorn telegram_laptop_scraper.api:app --reload
```

Then open http://localhost:8000/docs for API documentation.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sync` | Fetch new messages from channels |
| `GET` | `/laptops` | List all laptops |
| `GET` | `/laptops/{id}` | Get single laptop |
| `GET` | `/laptops/search` | Filter by specs |
| `POST` | `/recommend` | Get recommendations |

## Project Structure

```
telegram-laptop-scraper/
├── telegram_laptop_scraper/
│   ├── config.py         # Settings management
│   ├── schemas.py        # Data models
│   ├── telegram.py       # Telegram client
│   ├── extractor.py      # LLM extraction
│   ├── database.py       # SQLite operations
│   ├── recommender.py    # Filtering logic
│   └── api.py            # FastAPI app
├── streamlit_app.py      # Web UI
├── tests/
└── data/                 # SQLite database
```

## Configuration

All settings via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_API_ID` | Yes | - | Telegram API ID |
| `TELEGRAM_API_HASH` | Yes | - | Telegram API hash |
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key |
| `LLM_MODEL` | No | `anthropic/claude-sonnet-4` | Model to use |
| `TELEGRAM_CHANNELS` | No | - | Comma-separated channel URLs |
| `DATABASE_PATH` | No | `data/laptops.db` | SQLite database path |

## Supported LLM Models (via OpenRouter)

- `anthropic/claude-sonnet-4` (recommended)
- `openai/gpt-4o-mini` (budget)
- `meta-llama/llama-3.1-70b-instruct` (open source)
- Any model on [OpenRouter](https://openrouter.ai/models)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
ruff format .
```

## License

MIT