# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

```bash
# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install
```

## Running the Application

```bash
# Start the FastAPI server
uv run run.py
```

The application runs at http://localhost:8000 with automatic reload enabled.

## API Documentation

Access interactive API documentation at http://localhost:8000/docs (Swagger UI).

## Architecture Overview

This is a Band social network monitoring application built with:

- **FastAPI**: Web framework for the REST API
- **Playwright**: Browser automation for web scraping
- **aiosqlite**: Async SQLite database operations
- **Pydantic**: Data validation and serialization

### Core Components

**Main Application** (`src/band_monitor/main.py`):
- FastAPI application with lifecycle management
- REST endpoints for account management and monitoring control
- Global instances of Database and BrowserManager

**Database Layer** (`src/band_monitor/database.py`):
- Async SQLite operations for account persistence
- Account status and friend count tracking
- Database initialization and schema management

**Browser Management** (`src/band_monitor/browser_manager.py`):
- Playwright-based browser automation
- Per-account persistent browser sessions stored in `browser_sessions/`
- Friend count monitoring with 10-second intervals
- Currently has login functionality commented out for development

**Data Models** (`src/band_monitor/models.py`):
- Pydantic models for request/response validation
- MonitorStatus enum (running/paused/stopped)
- Account and API response schemas

### Key Workflows

1. **Account Registration**: Add Band account credentials via POST /accounts
2. **Start Monitoring**: Launch browser session and begin friend count tracking
3. **Pause/Resume**: Control monitoring without losing browser session
4. **Status Tracking**: Monitor account states and friend count changes

The application maintains separate browser sessions for each account in the `browser_sessions/` directory to preserve login state and avoid re-authentication.