# Profood SaleScrap - Food Delivery Intelligence

SaleScrap is a competitive intelligence tool designed for the BizDev department. It automates the scraping, monitoring, and analysis of food delivery promotions across major aggregators in Uzbekistan (Uzum Tezkor, Yandex Eda).

## Features

*   **Asynchronous Scraping:** High-performance data ingestion using `asyncio` and `httpx`.
*   **Retail Filtering:** Built-in blacklists to filter out data pollution (e.g., supermarkets, pharmacies, pet stores).
*   **Time-Series Tracking:** Preserves historical parsing data to track promotion dynamics over time.
*   **Interactive Dashboard (Streamlit):**
    *   **Price vs Trust Index:** Analyzes the relationship between discount magnitude and restaurant rating.
    *   **True Cost Analysis:** Calculates the real cost for the customer by factoring in delivery fees, service fees, and discounts.
    *   **Visibility Gap (Funnel):** Tracks exactly where the restaurant appears in the aggregator's feed.
*   **Telegram Notifications:** Automated alerts for aggressive competitor discounts and parsing stats summaries.

## Tech Stack

*   **Language:** Python 3.12+
*   **Package Manager:** `uv`
*   **Database:** SQLite via SQLAlchemy 2.0 (Async)
*   **Dashboard:** Streamlit & Plotly Express
*   **Linting & Formatting:** Ruff

## Setup & Installation

This project strictly uses `uv` for dependency management.

1.  **Sync Dependencies:**
    ```bash
    uv sync
    ```

2.  **Run the Scraper Pipeline:**
    Run the full ingestion cycle (Uzum + Yandex) to populate the database:
    ```bash
    uv run python main.py --scrape
    ```

3.  **Launch the Analytics Dashboard:**
    ```bash
    uv run python main.py --dashboard
    ```

## Project Structure

*   `main.py` - Application entry point.
*   `app.py` - Streamlit analytics dashboard.
*   `scraper/` - Async web scrapers for Yandex and Uzum.
*   `database/` - SQLAlchemy models (flat architecture) and connection configuration.
*   `analytics/` - Mapping logic, anomaly detection, and data processing.
*   `notifications/` - Telegram bot polling and alert mechanisms.
*   `data/` - Static JSON exports for reporting (`export.json`).

## Testing & Linting

*   **Lint & Format:** `uv run ruff check . && uv run ruff format .`
*   **Type Check:** `uv run mypy .`

## Contributing

Please adhere to Conventional Commits and ensure all CI checks pass before merging.
