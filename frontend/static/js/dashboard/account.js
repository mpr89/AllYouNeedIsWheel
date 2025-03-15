/**
 * Account module for handling portfolio data
 * Manages account summary and positions display
 */
import { fetchAccountData, fetchPositions } from './api.js';
import { showAlert } from '../utils/alerts.js';

// Store account data
let accountData = null;
let positionsData = null;

/**
 * Format currency value for display
 * @param {number} value - The currency value to format
 * @returns {string} Formatted currency string
 */
function formatCurrency(value) {
    if (value === null || value === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', { 
        style: 'currency', 
        currency: 'USD' 
    }).format(value);
}

/**
 * Format percentage for display
 * @param {number} value - The percentage value
 * @returns {string} Formatted percentage string
 */
function formatPercentage(value) {
    if (value === null || value === undefined) return '0.00%';
    return `${value.toFixed(2)}%`;
}

/**
 * Update account summary display
 */
function updateAccountSummary() {
    if (!accountData) return;
    
    // Update account value
    const accountValueElement = document.getElementById('account-value');
    if (accountValueElement) {
        accountValueElement.textContent = formatCurrency(accountData.account_value || 0);
    }
    
    // Update daily change
    const dailyChangeElement = document.getElementById('daily-change');
    if (dailyChangeElement) {
        const changeClass = (accountData.unrealized_pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        dailyChangeElement.className = changeClass;
        dailyChangeElement.textContent = `${formatPercentage(accountData.unrealized_pnl || 0)} today`;
    }
    
    // Update cash balance
    const cashBalanceElement = document.getElementById('cash-balance');
    if (cashBalanceElement) {
        cashBalanceElement.textContent = formatCurrency(accountData.cash_balance || 0);
    }
    
    // Update positions count
    const positionsCountElement = document.getElementById('positions-count');
    if (positionsCountElement) {
        positionsCountElement.textContent = accountData.positions_count || 0;
    }
}

/**
 * Populate positions table
 */
function populatePositionsTable() {
    if (!positionsData) return;
    
    const positionsTableBody = document.getElementById('positions-table-body');
    if (!positionsTableBody) return;
    
    // Clear table
    positionsTableBody.innerHTML = '';
    
    if (positionsData.length === 0) {
        const noDataRow = document.createElement('tr');
        noDataRow.innerHTML = '<td colspan="6" class="text-center">No positions found</td>';
        positionsTableBody.appendChild(noDataRow);
        return;
    }
    
    // Add positions to table
    positionsData.forEach(position => {
        const row = document.createElement('tr');
        
        const marketValue = position.market_value || 0;
        const unrealizedPnL = position.unrealized_pnl || 0;
        const unrealizedPnLPercent = position.unrealized_pnl_percent || 0;
        
        const pnlClass = unrealizedPnL >= 0 ? 'text-success' : 'text-danger';
        
        row.innerHTML = `
            <td>${position.symbol}</td>
            <td>${position.position}</td>
            <td>${formatCurrency(position.average_cost || 0)}</td>
            <td>${formatCurrency(position.market_price || 0)}</td>
            <td>${formatCurrency(marketValue)}</td>
            <td class="${pnlClass}">${formatCurrency(unrealizedPnL)} (${formatPercentage(unrealizedPnLPercent)})</td>
        `;
        
        positionsTableBody.appendChild(row);
    });
}

/**
 * Load portfolio data from API
 */
async function loadPortfolioData() {
    const data = await fetchAccountData();
    if (data) {
        accountData = data;
        updateAccountSummary();
    }
}

/**
 * Load positions data from API
 */
async function loadPositionsTable() {
    const data = await fetchPositions();
    if (data) {
        positionsData = data;
        if (!accountData && document.getElementById('positions-count')) {
            document.getElementById('positions-count').textContent = positionsData.length || 0;
        }
        populatePositionsTable();
    }
}

// Export functions
export {
    loadPortfolioData,
    loadPositionsTable,
    formatCurrency,
    formatPercentage
}; 