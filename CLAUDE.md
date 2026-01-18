# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RedInk (红墨) is an AI-powered image and text generator for creating Xiaohongshu (Little Red Book) style content. It generates complete visual posts including cover images and content pages from a single text prompt.

## Tech Stack

- **Backend**: Python 3.11+ with Flask, using `uv` as package manager
- **Frontend**: Vue 3 + TypeScript with Vite, using `pnpm` as package manager
- **AI Integration**: Google Gemini and OpenAI-compatible APIs

## Development Commands

### Backend

```bash
# Install dependencies
uv sync

# Run backend server (port 12398)
uv run python -m backend.app

# Run tests
uv run pytest
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev      # Development server (port 5173)
pnpm build    # Production build
```

### Quick Start

- Windows: `start.bat`
- macOS/Linux: `start.sh` or `scripts/start-macos.command`

### Docker

```bash
docker-compose up -d
# Or: docker run -d -p 12398:12398 -v ./history:/app/history -v ./output:/app/output histonemax/redink:latest
```

## Architecture

```
backend/
├── app.py              # Flask application entry point
├── config.py           # Configuration management
├── generators/         # AI generation implementations (factory pattern)
│   ├── base.py         # Base generator class
│   ├── factory.py      # Generator factory
│   ├── google_genai.py # Google Gemini integration
│   └── openai_compatible.py  # OpenAI-compatible API
├── prompts/            # AI prompt templates
├── routes/             # API route blueprints (config, content, history, image, outline)
├── services/           # Business logic (content, history, image, outline)
└── utils/              # Utility functions

frontend/src/
├── api/                # API client modules
├── components/         # Reusable Vue components
├── composables/        # Vue composables
├── stores/             # Pinia state management
└── views/              # Page components
```

## Key Configuration Files

- `text_providers.yaml` - Text generation API configuration (OpenAI/Gemini)
- `image_providers.yaml` - Image generation API configuration
- `frontend/vite.config.ts` - Vite config with API proxy to backend

## API Proxy

Frontend dev server proxies `/api` requests to `http://127.0.0.1:12398` (backend).
