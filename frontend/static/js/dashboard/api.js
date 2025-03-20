/**
 * API interaction module for dashboard
 * Handles all data fetching and API calls
 */
import { showAlert } from '../utils/alerts.js';

/**
 * Fetch account and portfolio data
 * @returns {Promise} Promise with account data
 */
async function fetchAccountData() {
    try {
        const response = await fetch('/api/portfolio');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching account data:', error);
        showAlert(`Error fetching account data: ${error.message}`, 'danger');
        return null;
    }
}

/**
 * Fetch positions data
 * @returns {Promise} Promise with positions data
 */
async function fetchPositions() {
    try {
        const response = await fetch('/api/portfolio/positions');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching positions:', error);
        showAlert(`Error fetching positions: ${error.message}`, 'danger');
        return null;
    }
}

/**
 * Fetch weekly option income data
 * @returns {Promise} Promise with weekly income data from short options expiring next Friday
 */
async function fetchWeeklyOptionIncome() {
    try {
        const response = await fetch('/api/portfolio/weekly-income');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching weekly option income:', error);
        showAlert(`Error fetching weekly income data: ${error.message}`, 'danger');
        return {
            positions: [],
            total_income: 0,
            positions_count: 0,
            error: error.message
        };
    }
}

/**
 * Fetch option data for a ticker
 * @param {string} ticker - The stock symbol
 * @param {number} otmPercentage - The OTM percentage value (default: 10)
 * @returns {Promise} Promise with option data
 */
async function fetchOptionData(ticker, otmPercentage = 10) {
    try {
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/options/otm?tickers=${encodeURIComponent(ticker)}&otm=${otmPercentage}&real_time=true&options_only=true&t=${timestamp}`, {
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching options for ${ticker}:`, error);
        showAlert(`Error fetching options for ${ticker}: ${error.message}`, 'danger');
        return null;
    }
}

/**
 * Fetch all tickers
 * @returns {Promise} Promise with tickers data
 */
async function fetchTickers() {
    try {
        const response = await fetch('/api/portfolio/positions');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const positionsData = await response.json();
        
        const tickers = positionsData.map(position => position.symbol);
        
        return { tickers: tickers };
    } catch (error) {
        console.error('Error fetching tickers:', error);
        showAlert(`Error fetching tickers: ${error.message}`, 'danger');
        return { tickers: [] };
    }
}

/**
 * Fetch pending orders
 * @param {boolean} executed - Whether to fetch executed orders (default: false)
 * @returns {Promise} Promise with pending or executed orders data
 */
async function fetchPendingOrders(executed = false) {
    try {
        const url = `/api/options/pending-orders${executed ? '?executed=true' : ''}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching orders:', error);
        showAlert(`Error fetching orders: ${error.message}`, 'danger');
        return null;
    }
}

/**
 * Save an option order
 * @param {Object} orderData - The order data
 * @returns {Promise} Promise with the saved order
 */
async function saveOptionOrder(orderData) {
    try {
        const response = await fetch('/api/options/order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(orderData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error saving order:', error);
        showAlert(`Error saving order: ${error.message}`, 'danger');
        throw error;
    }
}

/**
 * Cancel an order
 * @param {string} orderId - The order ID to cancel
 * @returns {Promise} Promise with the cancelled order
 */
async function cancelOrder(orderId) {
    try {
        // Use the new cancellation endpoint for active orders
        const response = await fetch(`/api/options/cancel/${orderId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to cancel order');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error cancelling order:', error);
        showAlert(`Error cancelling order: ${error.message}`, 'danger');
        throw error;
    }
}

/**
 * Check status of pending/processing orders with TWS
 * @returns {Promise} Promise with updated orders
 */
async function checkOrderStatus() {
    try {
        const response = await fetch('/api/options/check-orders', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to check order status');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error checking order status:', error);
        // Don't show alert for this regular background operation
        throw error;
    }
}

/**
 * Execute an order through TWS
 * @param {string} orderId - The order ID to execute
 * @returns {Promise} Promise with the executed order
 */
async function executeOrder(orderId) {
    try {
        const response = await fetch(`/api/options/execute/${orderId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to execute order');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error executing order:', error);
        showAlert(`Error executing order: ${error.message}`, 'danger');
        throw error;
    }
}

// Export all API functions
export {
    fetchAccountData,
    fetchPositions,
    fetchWeeklyOptionIncome,
    fetchOptionData,
    fetchTickers,
    fetchPendingOrders,
    saveOptionOrder,
    cancelOrder,
    executeOrder,
    checkOrderStatus
}; 