# Auto-Trader

A simple automated trading system for options trading on Interactive Brokers (IBKR).

## Overview

Auto-Trader is a lightweight tool that connects to Interactive Brokers to automate basic options trading strategies. It focuses on simplicity and reliability for options sellers.

## Features

### Core Trading System
- **IBKR Integration**: Connection to Interactive Brokers' TWS or IB Gateway
- **Basic Options Strategies**: 
  - Selling put options (cash-secured puts)
  - Selling call options (covered calls)
- **Backtesting**: Test your strategies with historical data before risking real capital
- **Trade Logging**: All trades are logged in SQLite database for performance review

### Technical Stack
- **Language**: Python
- **IBKR Connectivity**: ib_insync for API connection
- **Database**: SQLite for trade logging
- **Automation**: Basic scheduled execution via cron (Linux/macOS)

## Requirements

- Interactive Brokers account
- IBKR Trader Workstation (TWS) or IB Gateway
- API credentials from Interactive Brokers
- Python 3.8+

## Getting Started

Detailed setup and usage instructions coming soon. The project is currently under development.

## Roadmap

### Phase 1: Core Trading System
- Simple put and call selling functionality
- Basic backtesting capabilities
- Trade logging in SQLite

## Disclaimer

Trading options involves significant risk of loss. This software is for educational and research purposes only. Always consult with a financial advisor before implementing any trading strategy.
