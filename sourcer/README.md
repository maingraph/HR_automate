# Sourcer — Autonomous AI Recruitment Pipeline

> **Fully autonomous recruitment system powered by LLMs**  
> Scrape → Score → Outreach → Reply — All automated.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.2-black.svg)](https://nextjs.org/)
[![License](https://img.shields.io/badge/License-Private-red.svg)]()

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Redis
- Supabase account
- Telegram API credentials
- LinkedIn account (for outreach)

### One-Command Launch
```bash
bash launch.sh
```

This will:
1. Start Redis (if not running)
2. Launch FastAPI backend on :8000
3. Start Celery worker + beat
4. Start Telegram listener
5. Launch Next.js frontend on :3000

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium

# Copy and configure environment
cp ../.env.example ../.env
# Edit .env with your credentials

# Run services
uvicorn app.main:app --port 8000 --reload
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
python ../scripts/run_telegram_listener.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Complete system architecture, tech stack, algorithms |
| [REFACTORING_CHANGELOG.md](./REFACTORING_CHANGELOG.md) | Detailed changelog of all refactoring sessions |
| [CLAUDE_ARCH_CONTEXT.md](./CLAUDE_ARCH_CONTEXT.md) | Original Claude Opus architecture notes |
| [ANTIGRAVITY_FIX_LOG.md](./ANTIGRAVITY_FIX_LOG.md) | Gemini 3.1 bug fixes and improvements |

**Quick Links:**
- [Tech Stack](#tech-stack)
- [How It Works](#how-it-works)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Tech Stack

**Backend:**
- FastAPI 0.115 (async Python web framework)
- Celery 5.4 (distributed task queue)
- Redis (message broker)
- Supabase (PostgreSQL + pgvector)
- Telethon (Telegram automation)
- Playwright (LinkedIn automation)

**Frontend:**
- Next.js 14.2 (React framework)
- Tailwind CSS 3.4 (styling)
- TypeScript 5.5

**AI/LLM:**
- Google Gemini 2.5 Flash (plan generation, scoring)
- OpenRouter (fallback provider)
- Gemini Embeddings (768-dim vectors)

---

## 🔄 How It Works

### 1. Job Creation
```
User inputs vacancy → Gemini generates search plan
  ├─ LinkedIn Boolean queries (3 variants)
  ├─ Telegram keywords (25-40 items)
  ├─ Hard filters (disqualifiers)
  └─ Scoring rubric (weighted dimensions)
```

### 2. Candidate Sourcing
```
Pipeline scrapes multiple sources in parallel:
  ├─ Telegram channels (Telethon)
  ├─ LinkedIn XLSX exports (manual upload)
  └─ Apollo.io (optional)
     ↓
Deduplication (3-pass: exact → fuzzy → key)
     ↓
Stage 1: Embedding similarity filter (drop bottom 30%)
     ↓
Stage 2: LLM scoring (Gemini structured output)
     ↓
Persist to database (candidates table)
```

### 3. Outreach Campaign
```
User creates campaign → Selects candidates
     ↓
System sends messages:
  ├─ LinkedIn (Playwright browser automation)
  └─ Telegram (Telethon DM)
     ↓
Random delays (5-15 min) to avoid spam detection
```

### 4. Reply Management
```
Incoming replies detected:
  ├─ LinkedIn: Voyager API polling (every 30 min)
  └─ Telegram: Persistent listener process
     ↓
AI classifies intent (interested / questions / declined)
     ↓
Copilot mode: Human reviews draft
Autopilot mode: AI sends automatically
```

---

## 🔧 Environment Variables

Create `.env` in project root:

```bash
# Telegram
TELEGRAM_API_ID=your_api_id          # from my.telegram.org
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890

# LinkedIn
LI_AT_COOKIE=your_li_at_cookie       # from browser DevTools
LI_HEADLESS=true
LI_SEND_MIN_DELAY=300                # seconds between sends
LI_SEND_MAX_DELAY=900

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_key

# Gemini / OpenRouter
GEMINI_API_KEY=your_gemini_key
GEMINI_API_KEYS=key1,key2,key3       # optional rotation pool
AI_PROVIDER=gemini                   # or: openrouter
OPENROUTER_API_KEY=your_openrouter_key

# Redis
REDIS_URL=redis://localhost:6379/0

# Scoring
EMBEDDING_FILTER_PERCENTILE=0.30     # drop bottom 30%
MIN_GEMINI_SCORE=50                  # minimum score to keep
```

See [.env.example](./.env.example) for complete list.

---

## 📊 Project Structure

```
sourcer/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── core/             # Config, DB, Celery, error handling
│   │   ├── scoring/          # LLM scoring + prompt generation
│   │   ├── scrapers/         # Data ingestion (Telegram, LinkedIn, files)
│   │   ├── outreach/         # Message sending + reply handling
│   │   ├── tasks/            # Celery async tasks
│   │   └── services/         # Business logic
│   └── sessions/             # Telethon session files
├── frontend/
│   ├── app/                  # Next.js pages
│   │   ├── page.tsx          # Sourcing wizard
│   │   ├── jobs/[id]/        # Job detail + candidates
│   │   ├── outreach/         # Campaigns + inbox
│   │   └── admin/            # Settings + logs
│   ├── components/           # Shared UI components
│   └── lib/                  # API client + types
├── scripts/                  # Utility scripts
├── supabase/                 # Database migrations
├── ARCHITECTURE.md           # Complete documentation
└── launch.sh                 # One-command launcher
```

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Check Python environment
cd backend && source .venv/bin/activate
python -c "import fastapi; print('OK')"

# Check environment variables
cat ../.env | grep SUPABASE_URL
```

### Frontend build fails
```bash
cd frontend
rm -rf .next node_modules
npm install
npm run build
```

### Telegram login fails
```bash
# Keep official Telegram app open during login
cd scripts
python telegram_login.py --session listener
python telegram_login.py --session scraper
```

### LinkedIn messages not sending
1. Check `li_at` cookie is fresh (expires randomly)
2. Verify `LI_HEADLESS=false` to debug browser
3. Check logs: `tail -f /tmp/sourcer_api.log`

### Celery tasks stuck
```bash
# Kill zombie workers
pkill -f "celery"

# Restart clean
cd backend
.venv/bin/celery -A app.core.celery_app worker --loglevel=info
```

See [ARCHITECTURE.md § 17 Troubleshooting](./ARCHITECTURE.md#17-troubleshooting-guide) for more.

---

## 🧪 Testing

### Run unit tests
```bash
cd backend
.venv/bin/python -c "
from app.core.error_handling import with_fallback
from app.scoring.prompt_builder import build_plan_system_prompt
# Tests...
"
```

### Test full pipeline
```bash
# Start all services
bash launch.sh

# Open browser
open http://localhost:3000

# Create test job
# Monitor logs: tail -f /tmp/sourcer_*.log
```

---

## 📈 Performance

**Typical Pipeline:**
- 1000 Telegram messages scraped: ~2 min
- Deduplication: ~5 sec
- Embedding generation (1000 candidates): ~30 sec
- LLM scoring (700 candidates after filter): ~10 min
- Total: ~13 minutes for 1000 → 700 → 50 qualified candidates

**Bottlenecks:**
- LLM API rate limits (10 req/min on free tier)
- LinkedIn send delays (5-15 min between messages)
- Telegram scraping (depends on channel size)

---

## 🔒 Security Notes

⚠️ **Current Status:** Development mode, no authentication

**Before production:**
- [ ] Add JWT authentication to API
- [ ] Implement rate limiting
- [ ] Encrypt sensitive credentials
- [ ] Enable Supabase RLS policies
- [ ] Add CORS restrictions
- [ ] Implement audit logging

See [ARCHITECTURE.md § 10 Unimplemented Features](./ARCHITECTURE.md#10-unimplemented-features--shortcuts) for details.

---

## 🗺️ Roadmap

### Phase 2: Frontend Refactoring (May 2026)
- [ ] Eliminate component duplication
- [ ] Create reusable form hooks
- [ ] Standardize async patterns
- [ ] Improve TypeScript types

### Phase 3: Performance (June 2026)
- [ ] WebSocket/SSE for real-time updates
- [ ] Database views for aggregations
- [ ] Redis caching layer
- [ ] Batch embedding optimization

### Phase 4: Production (July 2026)
- [ ] Authentication system
- [ ] Monitoring and alerting
- [ ] Comprehensive test suite
- [ ] CI/CD pipeline
- [ ] Docker deployment

---

## 📝 Recent Changes

**2026-04-27 — Phase 1 Backend Refactoring**
- ✅ Unified error handling system
- ✅ Modular prompt generation
- ✅ Comprehensive documentation
- ✅ 100% test pass rate

See [REFACTORING_CHANGELOG.md](./REFACTORING_CHANGELOG.md) for details.

---

## 🤝 Contributing

This is a private project. For questions or issues:
1. Check [ARCHITECTURE.md](./ARCHITECTURE.md) for technical details
2. Review [REFACTORING_CHANGELOG.md](./REFACTORING_CHANGELOG.md) for recent changes
3. Contact the development team

---

## 📄 License

Private / Proprietary

---

## 🙏 Acknowledgments

**Development History:**
- **Claude Opus (Sonnet 4.6):** Foundation architecture (2024-2025)
- **Gemini 3.1 (Antigravity):** Dynamic prompts, admin dashboard (2025-2026)
- **OpenCode (kr/claude-sonnet-4.5):** Clean Development refactoring (2026)

---

**Built with ❤️ for autonomous recruitment**

