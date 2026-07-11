# HR Automate

Recruitment automation workspace: source candidates, map LinkedIn profiles, score matches, and run controlled outreach.

## Components

| Path | Purpose | Stack |
| --- | --- | --- |
| `sourcer/` | Full recruitment pipeline: jobs, multi-source ingestion, AI scoring, outreach, reply handling | FastAPI, Celery, Redis, Supabase, Next.js |
| `linkedin-sales-nav-parser/` | Sales Navigator search-result parser with resumable CSV export | TypeScript, Playwright |
| `linkedin-profile-mapper/` | Detailed single-profile mapper; saves section HTML and normalized JSON | Python, Playwright, BeautifulSoup |

## Start Sourcer

```bash
cd sourcer
cp .env.example .env
# Set required credentials in .env
bash launch.sh
```

Frontend: `http://localhost:3000`
API docs: `http://localhost:8000/docs`

See [Sourcer README](sourcer/README.md) for setup, architecture, and operations.

## Run Sales Navigator parser

```bash
cd linkedin-sales-nav-parser
npm install
npm run build
npm start -- --url "YOUR_SALES_NAV_URL" --test
```

See [parser README](linkedin-sales-nav-parser/README.md) for options.

## Run profile mapper

```bash
cd linkedin-profile-mapper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py "https://www.linkedin.com/in/PROFILE_SLUG/"
```

## Repository hygiene

Credentials, browser sessions, scraped profiles, logs, debug captures, caches, and financial-model exports are local-only. Copy environment template before running; never commit populated `.env` files.

Automated LinkedIn actions can trigger account restrictions and must comply with LinkedIn terms, applicable law, and candidate-consent requirements.
