# Personalization Sitemap Generator

A Python/Flask web app for Salesforce sales engineers. It detects homepage hero content from a live customer site, extracts CSS styles, and generates a Salesforce Personalization sitemap using Einstein LLM via a Salesforce Connected App.

## Stack

- Python / Flask backend
- Vanilla HTML/CSS/JS frontend
- BeautifulSoup4 for HTML parsing
- cssutils for CSS parsing
- LangChain wrapper calling Salesforce Einstein LLM (GPT-4-32k)
- No Anthropic or OpenAI API key required

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `EINSTEIN_CLIENT_SECRET` | **Yes** | Client secret for the Salesforce Connected App. Never commit this value. |
| `PORT` | On Heroku | HTTP port. Heroku sets this automatically; locally defaults to `3000`. |

Copy `.env.example` to `.env` for local development:

```bash
cp .env.example .env
```

Then set `EINSTEIN_CLIENT_SECRET` to the real secret from your Salesforce Connected App.

## Run locally

```bash
pip install -r requirements.txt
python main.py
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy to Heroku

1. Push this app to GitHub.
2. In Heroku, create a new app and connect the GitHub repo under **Deploy**.
3. Under **Settings** > **Config Vars**, add `EINSTEIN_CLIENT_SECRET`.
4. Deploy the `main` branch (or enable automatic deploys).

The `Procfile` runs `web: gunicorn main:app`. Heroku's Python buildpack auto-detects `requirements.txt`.

If this app lives inside a larger monorepo, either deploy this folder as its own repo or use a subdirectory buildpack with `PROJECT_PATH=sitemap-generator`.

## API

- `POST /detect` — Fetch page HTML, detect hero element, return `{ selector, outerHtml }`
- `POST /extract-styles` — Parse inline, embedded, and external CSS for the hero element, return `{ extractedStyles }`
- `POST /generate` — Build prompt with extracted values, call Einstein LLM, return `{ sitemap }`
