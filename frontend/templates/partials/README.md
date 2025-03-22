# Template Partials Structure

This directory contains reusable template components organized by function:

## Directory Structure

- `/common/` - Components used across multiple pages
  - `navigation.html` - Main navigation bar
  - `footer.html` - Site footer
  - `positions_table.html` - Positions table showing current stock and option positions

- `/dashboard/` - Components specific to the dashboard page
  - `account_summary.html` - Account value and summary cards
  - `options_table.html` - Option opportunities table showing available options
  - `pending_orders.html` - Pending orders table showing current orders

- `/portfolio/` - Components specific to the portfolio page

- `/components/` - Smaller, reusable UI components that may be included in multiple partials

## Usage Guidelines

1. Place page-specific components in their respective directories
2. Place shared components in the `/common/` directory
3. Small, reusable UI elements should go in `/components/`
4. Include components using: `{% include "partials/path/to/component.html" %}` 