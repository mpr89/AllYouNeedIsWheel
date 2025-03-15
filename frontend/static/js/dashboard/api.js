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
 * @returns {Promise} Promise with pending orders data
 */
async function fetchPendingOrders() {
    try {
        const response = await fetch('/api/options/pending-orders');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching pending orders:', error);
        showAlert(`Error fetching pending orders: ${error.message}`, 'danger');
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
        const response = await fetch(`/api/options/order/${orderId}`, {
            method: 'DELETE',
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
    fetchOptionData,
    fetchTickers,
    fetchPendingOrders,
    saveOptionOrder,
    cancelOrder,
    executeOrder
}; 