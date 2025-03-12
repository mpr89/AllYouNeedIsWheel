# Auto-Trader

Auto-Trader is a financial options trading assistant that helps analyze, visualize, and recommend option trading strategies. It connects to Interactive Brokers TWS/IB Gateway, retrieves portfolio data, analyzes options, and presents recommendations through a user-friendly web interface.

## Features

- **Portfolio Dashboard**: View your current portfolio positions, value, and performance metrics
- **Options Analysis**: Analyze option chains for any stock ticker
- **Trading Recommendations**: Get AI-powered option trade recommendations
- **Interactive Web Interface**: Modern, responsive web application with data visualizations
- **API Integration**: Backend API to interact with Interactive Brokers

## Architecture

The application consists of:

1. **Core Libraries** (`autotrader/core/`): Connection to IB TWS, data processing, and analysis
2. **Database Module** (`autotrader/db/`): SQLite database for storing trade data and history
3. **API Backend** (`api/`): Flask-based REST API serving data to the frontend
4. **Web Frontend** (`frontend/`): HTML/CSS/JS browser interface for visualization

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd auto-trader
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make sure Interactive Brokers TWS/IB Gateway is running with API connections enabled.

## Configuration

Create a `.env` file in the root directory with the following settings:

```
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
IB_READONLY=True

LOG_LEVEL=INFO
REPORT_DIR=reports
```

## Usage

### Starting the Web Application

Run the Flask web server:

```
python app.py
```

This will start the application on http://localhost:5000

### API Endpoints

- **Portfolio Data**: GET `/api/portfolio/`
- **Option Chains**: GET `/api/options/<ticker>`
- **Recommendations**: GET `/api/recommendations/`

### Web Interface

The web interface consists of four main pages:

1. **Dashboard**: Overview of your portfolio and key metrics
2. **Portfolio**: Detailed view of all positions
3. **Options**: Option chain analysis for selected tickers
4. **Recommendations**: Trade recommendations based on your strategy

## Development

### Project Structure

```
auto-trader/
├── api/                      # Flask API backend
│   ├── routes/               # API route modules
│   └── services/             # Business logic for API
├── autotrader/               # Core library 
│   ├── core/                 # Trading functionality
│   ├── db/                   # Database operations
│   └── strategies/           # Trading strategies
├── frontend/                 # Frontend web application
│   ├── static/               # Static assets (CSS, JS)
│   └── templates/            # Jinja2 HTML templates
├── app.py                    # Main application entry point
├── requirements.txt          # Python dependencies
└── README.md                 # Documentation
```

## License

[MIT License](LICENSE)

## Acknowledgments

- Interactive Brokers API for Python
- Flask web framework
- Bootstrap CSS framework
