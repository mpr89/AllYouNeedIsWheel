/**
 * Orders module for handling pending orders
 */
import { fetchPendingOrders, cancelOrder, executeOrder, checkOrderStatus } from './api.js';
import { showAlert, getBadgeColor } from '../utils/alerts.js';
import { formatCurrency } from './account.js';

// Store orders data
let pendingOrdersData = [];

// Auto-refresh timer
let autoRefreshTimer = null;
const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

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
        pendingOrdersTable.innerHTML = '<tr><td colspan="8" class="text-center">No pending orders found</td></tr>';
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
        
        // IB order information
        const ibOrderId = order.ib_order_id || 'Not sent';
        const ibStatus = order.ib_status || '-';
        
        // Format execution price if available
        const avgFillPrice = order.avg_fill_price ? formatCurrency(order.avg_fill_price) : '-';
        const commission = order.commission ? formatCurrency(order.commission) : '-';
        
        // Status area with IB info
        let statusHtml = `
            <span class="badge bg-${badgeColor}">${order.status}</span>
            <br>
            <small class="text-muted">${createdAt}</small>
        `;
        
        // Add IB info if order has been executed
        if (order.status !== 'pending') {
            statusHtml += `
                <br>
                <small class="text-muted mt-1">
                    <strong>IB ID:</strong> ${ibOrderId}
                </small>
                <br>
                <small class="text-muted">
                    <strong>Status:</strong> ${ibStatus}
                </small>
            `;
            
            // Add fill price and commission if order is executed
            if (order.status === 'executed' && order.avg_fill_price) {
                statusHtml += `
                    <br>
                    <small class="text-muted">
                        <strong>Fill Price:</strong> ${avgFillPrice}
                    </small>
                `;
                
                if (order.commission) {
                    statusHtml += `
                        <br>
                        <small class="text-muted">
                            <strong>Commission:</strong> ${commission}
                        </small>
                    `;
                }
            }
        }
        
        // Create the row HTML
        row.innerHTML = `
            <td>${order.ticker}</td>
            <td>${order.option_type}</td>
            <td>${strike}</td>
            <td>${order.expiration || 'N/A'}</td>
            <td>${premium}</td>
            <td>${statusHtml}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary execute-order" data-order-id="${order.id}" ${order.status !== 'pending' ? 'disabled' : ''}>
                        <i class="bi bi-play-fill"></i> Execute
                    </button>
                    <button class="btn btn-outline-danger cancel-order" data-order-id="${order.id}" ${['executed', 'canceled', 'rejected'].includes(order.status) ? 'disabled' : ''}>
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
        // Execute the order
        const result = await executeOrder(orderId);
        
        // Update the order in pendingOrdersData with the IB information
        const orderIndex = pendingOrdersData.findIndex(order => order.id == orderId);
        if (orderIndex !== -1) {
            // Update the order with execution details
            pendingOrdersData[orderIndex].status = "processing";
            pendingOrdersData[orderIndex].executed = true;
            
            // Add IB details from the response
            if (result.execution_details) {
                pendingOrdersData[orderIndex].ib_order_id = result.execution_details.ib_order_id;
                pendingOrdersData[orderIndex].ib_status = result.execution_details.ib_status;
                pendingOrdersData[orderIndex].filled = result.execution_details.filled;
                pendingOrdersData[orderIndex].remaining = result.execution_details.remaining;
                pendingOrdersData[orderIndex].avg_fill_price = result.execution_details.avg_fill_price;
            } else {
                // Fallback if execution_details is not present
                pendingOrdersData[orderIndex].ib_order_id = result.ib_order_id || 'Unknown';
                pendingOrdersData[orderIndex].ib_status = 'Submitted';
            }
            
            // Update the table immediately
            updatePendingOrdersTable();
        }
        
        // Show success message
        showAlert(`Order sent to TWS (IB Order ID: ${result.ib_order_id})`, 'success');
        
        // Start auto-refresh if not already running to track this order's status
        startAutoRefresh();
    } catch (error) {
        console.error('Error executing order:', error);
        showAlert(`Error executing order: ${error.message}`, 'danger');
    }
}

/**
 * Cancel an order by ID
 * @param {string} orderId - The order ID to cancel
 */
async function cancelOrderById(orderId) {
    try {
        // Use the improved cancel order endpoint
        const result = await cancelOrder(orderId);
        
        // Update the order in pendingOrdersData
        const orderIndex = pendingOrdersData.findIndex(order => order.id == orderId);
        if (orderIndex !== -1) {
            // Update the order status
            pendingOrdersData[orderIndex].status = result.ib_status === 'PendingCancel' ? 'canceling' : 'canceled';
            
            // Add IB details if available
            if (result.ib_status) {
                pendingOrdersData[orderIndex].ib_status = result.ib_status;
            }
            
            // Update the table immediately
            updatePendingOrdersTable();
        }
        
        showAlert('Order cancellation requested', 'success');
        
        // Start auto-refresh if not already running to track this canceled order's status
        startAutoRefresh();
    } catch (error) {
        console.error('Error cancelling order:', error);
        showAlert(`Error cancelling order: ${error.message}`, 'danger');
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

/**
 * Check for order status updates with TWS
 */
async function checkOrdersStatus() {
    try {
        // Only check if we have processing or canceling orders
        const hasProcessingOrders = pendingOrdersData.some(order => 
            ['processing', 'canceling'].includes(order.status));
            
        if (hasProcessingOrders) {
            const result = await checkOrderStatus();
            
            if (result && result.success && result.updated_orders && result.updated_orders.length > 0) {
                // Update the orders that changed
                result.updated_orders.forEach(updatedOrder => {
                    const orderIndex = pendingOrdersData.findIndex(order => order.id == updatedOrder.id);
                    if (orderIndex !== -1) {
                        // Update the order with new status and details
                        pendingOrdersData[orderIndex] = {
                            ...pendingOrdersData[orderIndex],
                            ...updatedOrder
                        };
                    }
                });
                
                // Update the table with the new data
                updatePendingOrdersTable();
                
                // If no more processing orders, stop auto-refresh
                const stillHasProcessingOrders = pendingOrdersData.some(order => 
                    ['processing', 'canceling'].includes(order.status));
                    
                if (!stillHasProcessingOrders) {
                    stopAutoRefresh();
                }
            }
        } else {
            // No processing orders, no need for auto-refresh
            stopAutoRefresh();
        }
    } catch (error) {
        console.error('Error checking order status:', error);
        // Don't show alert for this routine operation
    }
}

/**
 * Start the auto-refresh timer for order status
 */
function startAutoRefresh() {
    // Don't create multiple timers
    if (autoRefreshTimer) {
        return;
    }
    
    // Create a new timer
    autoRefreshTimer = setInterval(checkOrdersStatus, AUTO_REFRESH_INTERVAL);
    console.log('Auto-refresh started');
}

/**
 * Stop the auto-refresh timer
 */
function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
        console.log('Auto-refresh stopped');
    }
}

// Set up event listener for the custom ordersUpdated event
document.addEventListener('ordersUpdated', loadPendingOrders);

// Initial load of pending orders
document.addEventListener('DOMContentLoaded', () => {
    loadPendingOrders();
    
    // Check for any processing orders on initial load and start auto-refresh if needed
    if (pendingOrdersData.some(order => ['processing', 'canceling'].includes(order.status))) {
        startAutoRefresh();
    }
});

// Make sure auto-refresh is stopped when the page is unloaded
window.addEventListener('beforeunload', stopAutoRefresh);

// Export functions
export {
    loadPendingOrders,
    executeOrderById,
    cancelOrderById
}; 