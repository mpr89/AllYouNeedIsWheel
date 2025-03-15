/**
 * Orders module for handling pending orders
 */
import { fetchPendingOrders, cancelOrder, executeOrder } from './api.js';
import { showAlert, getBadgeColor } from '../utils/alerts.js';
import { formatCurrency } from './account.js';

// Store orders data
let pendingOrdersData = [];

/**
 * Format date for display
 * @param {string|number} dateString - The date string or timestamp to format
 * @returns {string} The formatted date
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    // Handle Unix timestamp (seconds since epoch)
    if (typeof dateString === 'number' || !isNaN(parseInt(dateString))) {
        // Convert to milliseconds if it's in seconds
        const timestamp = parseInt(dateString) * (dateString.toString().length <= 10 ? 1000 : 1);
        return new Date(timestamp).toLocaleString();
    }
    
    // Handle regular date string
    return new Date(dateString).toLocaleString();
}

/**
 * Update the pending orders table with data
 */
function updatePendingOrdersTable() {
    const pendingOrdersTable = document.getElementById('pending-orders-table');
    if (!pendingOrdersTable) return;
    
    // Clear the table
    pendingOrdersTable.innerHTML = '';
    
    if (pendingOrdersData.length === 0) {
        pendingOrdersTable.innerHTML = '<tr><td colspan="7" class="text-center">No pending orders found</td></tr>';
        return;
    }
    
    // Sort orders by timestamp (newest first)
    pendingOrdersData.sort((a, b) => {
        // Handle different timestamp formats
        const timestampA = a.timestamp || a.created_at;
        const timestampB = b.timestamp || b.created_at;
        
        if (typeof timestampA === 'number' && typeof timestampB === 'number') {
            return timestampB - timestampA;
        } else {
            return new Date(timestampB) - new Date(timestampA);
        }
    });
    
    // Add each order to the table
    pendingOrdersData.forEach(order => {
        const row = document.createElement('tr');
        
        // Format the strike price
        const strike = order.strike ? `$${order.strike}` : 'N/A';
        
        // Format the premium
        const premium = order.premium ? formatCurrency(order.premium) : 'N/A';
        
        // Format the created date
        const createdAt = formatDate(order.timestamp || order.created_at);
        
        // Get the badge color for status
        const badgeColor = getBadgeColor(order.status);
        
        // Create the row HTML
        row.innerHTML = `
            <td>${order.ticker}</td>
            <td>${order.option_type}</td>
            <td>${strike}</td>
            <td>${order.expiration || 'N/A'}</td>
            <td>${premium}</td>
            <td>
                <span class="badge bg-${badgeColor}">${order.status}</span>
                <br>
                <small class="text-muted">${createdAt}</small>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary execute-order" data-order-id="${order.id}" ${order.status !== 'pending' ? 'disabled' : ''}>
                        <i class="bi bi-play-fill"></i> Execute
                    </button>
                    <button class="btn btn-outline-danger cancel-order" data-order-id="${order.id}" ${order.status !== 'pending' ? 'disabled' : ''}>
                        <i class="bi bi-x-circle"></i> Cancel
                    </button>
                </div>
            </td>
        `;
        
        pendingOrdersTable.appendChild(row);
    });
    
    // Add event listeners
    addOrdersTableEventListeners();
}

/**
 * Add event listeners to the orders table buttons
 */
function addOrdersTableEventListeners() {
    // Add listeners to execute buttons
    document.querySelectorAll('.execute-order').forEach(button => {
        button.addEventListener('click', async (event) => {
            const orderId = event.currentTarget.dataset.orderId;
            // Remove confirmation dialog and execute directly
            await executeOrderById(orderId);
        });
    });
    
    // Add listeners to cancel buttons
    document.querySelectorAll('.cancel-order').forEach(button => {
        button.addEventListener('click', async (event) => {
            const orderId = event.currentTarget.dataset.orderId;
            // Remove confirmation dialog and cancel directly
            await cancelOrderById(orderId);
        });
    });
    
    // Add listener to refresh pending orders button
    const refreshPendingOrdersButton = document.getElementById('refresh-pending-orders');
    if (refreshPendingOrdersButton) {
        refreshPendingOrdersButton.addEventListener('click', loadPendingOrders);
    }
}

/**
 * Execute an order by ID
 * @param {string} orderId - The order ID to execute
 */
async function executeOrderById(orderId) {
    try {
        const result = await executeOrder(orderId);
        showAlert(`Order sent to TWS for execution (IB Order ID: ${result.ib_order_id})`, 'success');
        await loadPendingOrders(); // Refresh the orders list
    } catch (error) {
        console.error('Error executing order:', error);
    }
}

/**
 * Cancel an order by ID
 * @param {string} orderId - The order ID to cancel
 */
async function cancelOrderById(orderId) {
    try {
        await cancelOrder(orderId);
        showAlert('Order cancelled successfully', 'success');
        await loadPendingOrders(); // Refresh the orders list
    } catch (error) {
        console.error('Error cancelling order:', error);
    }
}

/**
 * Load pending orders from API
 */
async function loadPendingOrders() {
    try {
        const data = await fetchPendingOrders();
        if (data && data.orders) {
            pendingOrdersData = data.orders;
            updatePendingOrdersTable();
        }
    } catch (error) {
        console.error('Error loading pending orders:', error);
        showAlert('Error loading pending orders', 'danger');
    }
}

// Set up event listener for the custom ordersUpdated event
document.addEventListener('ordersUpdated', loadPendingOrders);

// Export functions
export {
    loadPendingOrders,
    executeOrderById,
    cancelOrderById
}; 