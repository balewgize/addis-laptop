# Telegram Laptop Scraper

Extract structured laptop specifications from Ethiopian Telegram e-commerce channels using LLMs.

## Features

- 🔍 Scrapes laptop listings from Telegram channels
- 🤖 Uses LLMs (via OpenRouter) to extract structured data
- 💾 Stores data in SQLite for easy querying
- 🎯 Simple recommendation engine based on your needs
- 🌐 Streamlit web UI (deployable online)

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
git clone https://github.com/balewgize/telegram-laptop-scraper.git
cd telegram-laptop-scraper
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Option A: Install with pinned versions (recommended)
pip install -r requirements.txt

# Option B: Install latest compatible versions
pip install -e ".[dev]"
```

### 2. Get API credentials

**Telegram API:**
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create an application (any name/short name works)
5. Copy `api_id` and `api_hash`

**OpenRouter API:**
1. Go to https://openrouter.ai
2. Create an account
3. Go to Keys → Create Key
4. Copy the API key

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 4. First run (Telegram auth)

The first time you run the app, Telegram will ask for authentication:

```bash
streamlit run streamlit_app.py
```

1. Enter your phone number (with country code, e.g., +251...)
2. Enter the verification code sent to your Telegram
3. This creates a session file - you won't need to auth again

### 5. Deploy online (Streamlit Cloud)

1. Push your code to GitHub
2. Go to https://share.streamlit.io
3. Connect your repo
4. Add secrets in Streamlit Cloud dashboard:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `OPENROUTER_API_KEY`

**Note:** For Streamlit Cloud, you'll need to handle Telegram session differently. See [Deployment section](#deployment).

## Usage

### Running locally

```bash
streamlit run streamlit_app.py
```

Open http://localhost:8501

### Syncing channels

1. Enter a Telegram channel URL (e.g., `https://t.me/Linktechcomputers`)
2. Click "Sync Channel"
3. Wait for extraction to complete
4. Browse and filter the results

### Finding recommendations

1. Go to "Recommend" tab
2. Set your budget and requirements
3. Get matched laptops

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_extractor.py

# Run specific test
pytest tests/test_extractor.py::TestLaptopExtractor::test_extract_dell_laptop

# Run tests with print output visible
pytest -s

# Run only fast tests (skip API calls)
pytest -m "not slow"
```

**Note:** Some tests require `OPENROUTER_API_KEY` to be set. They'll be skipped if the key is missing.

## Project Structure

```
telegram-laptop-scraper/
├── telegram_laptop_scraper/
│   ├── config.py         # Settings management
│   ├── schemas.py        # Data models
│   ├── telegram.py       # Telegram client
│   ├── extractor.py      # LLM extraction
│   ├── database.py       # SQLite operations
│   └── recommender.py    # Filtering logic
├── streamlit_app.py      # Web UI (standalone)
├── tests/                # Test suite
├── data/                 # SQLite database
├── requirements.txt      # Pinned dependencies
└── .env                  # Your configuration
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_API_ID` | Yes | - | Telegram API ID |
| `TELEGRAM_API_HASH` | Yes | - | Telegram API hash |
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key |
| `LLM_MODEL` | No | `anthropic/claude-sonnet-4` | Model for extraction |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `DATABASE_PATH` | No | `data/laptops.db` | SQLite path |

## Supported LLM Models

Via [OpenRouter](https://openrouter.ai/models):

| Model | Cost | Quality | Speed |
|-------|------|---------|-------|
| `anthropic/claude-sonnet-4` | $$ | Best | Medium |
| `openai/gpt-4o-mini` | $ | Good | Fast |
| `meta-llama/llama-3.1-70b-instruct` | $ | Good | Medium |
| `google/gemini-flash-1.5` | $ | Good | Fast |

## Deployment

### Streamlit Cloud

For cloud deployment, Telegram session handling needs special care:

1. **Option A:** Run locally first to create session, then upload `laptop_scraper_session.session` file
2. **Option B:** Use Telegram Bot API instead (TODO: future feature)

### Environment variables on Streamlit Cloud

Add these in your app settings → Secrets:

```toml
TELEGRAM_API_ID = "your_id"
TELEGRAM_API_HASH = "your_hash"
OPENROUTER_API_KEY = "your_key"
```

## Development

```bash
# Format code
ruff format .

# Lint
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

## License

MIT

## TODO

- [ ] Telegram Bot interface
- [ ] Price history tracking
- [ ] More product types (phones, etc.)
- [ ] LLM-powered natural language search
```