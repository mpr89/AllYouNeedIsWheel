/**
 * Orders module for handling pending orders
 */
import { fetchPendingOrders, cancelOrder, executeOrder, checkOrderStatus } from './api.js';
import { showAlert, getBadgeColor } from '../utils/alerts.js';
import { formatCurrency } from './account.js';

// Store orders data
let pendingOrdersData = [];
let filledOrdersData = [];

// Auto-refresh timer
let autoRefreshTimer = null;
const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

/**
 * Format date for display
 * @param {string|number} dateString - The date string or timestamp to format
 * @returns {string} The formatted date
 */
function formatDate(dateString) {
    if (!dateString) return '';
    
    // Handle Unix timestamp (seconds since epoch)
    if (typeof dateString === 'number' || !isNaN(parseInt(dateString))) {
        // Convert to milliseconds if it's in seconds
        const timestamp = parseInt(dateString) * (dateString.toString().length <= 10 ? 1000 : 1);
        
        // Check if this is a Unix epoch date (Jan 1, 1970) or very close to it
        if (timestamp < 86400000) { // Less than 1 day from epoch
            return ''; // Return empty string instead of showing 1970/1/1
        }
        
        return new Date(timestamp).toLocaleString();
    }
    
    // Handle regular date string
    const date = new Date(dateString);
    
    // Check if this is a valid date and not Jan 1, 1970
    if (isNaN(date.getTime()) || date.getFullYear() === 1970) {
        return '';
    }
    
    return date.toLocaleString();
}

/**
 * Check if a date is within the current week
 * @param {Date|string|number} date - The date to check
 * @returns {boolean} True if the date is within the current week
 */
function isWithinCurrentWeek(date) {
    if (!date) return false;
    
    // Convert to Date object if it's not already
    const dateObj = typeof date === 'object' ? date : new Date(date);
    
    // If date is invalid, return false
    if (isNaN(dateObj.getTime())) return false;
    
    const now = new Date();
    
    // Get the first day of the current week (Sunday)
    const firstDayOfWeek = new Date(now);
    firstDayOfWeek.setDate(now.getDate() - now.getDay());
    firstDayOfWeek.setHours(0, 0, 0, 0);
    
    // Get the last day of the current week (Saturday)
    const lastDayOfWeek = new Date(firstDayOfWeek);
    lastDayOfWeek.setDate(firstDayOfWeek.getDate() + 6);
    lastDayOfWeek.setHours(23, 59, 59, 999);
    
    // Check if the date is within the current week
    return dateObj >= firstDayOfWeek && dateObj <= lastDayOfWeek;
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
        `;
        
        // Add date only if it's not empty
        if (createdAt) {
            statusHtml += `
                <br>
                <small class="text-muted">${createdAt}</small>
            `;
        }
        
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
    
    // Also update the filled orders if any order was executed
    updateFilledOrdersTable();
}

/**
 * Update the filled orders table and calculate weekly earnings
 */
function updateFilledOrdersTable() {
    const filledOrdersTable = document.getElementById('filled-orders-table');
    if (!filledOrdersTable) {
        console.error('Could not find filled-orders-table element in the DOM');
        return;
    }
    
    console.log(`Updating filled orders table with ${filledOrdersData.length} orders`);
    
    // Clear the table
    filledOrdersTable.innerHTML = '';
    
    // Note: We're no longer re-filtering from pendingOrdersData here
    // filledOrdersData is already populated with executed orders from the API
    
    if (filledOrdersData.length === 0) {
        console.log('No filled orders to display');
        filledOrdersTable.innerHTML = '<tr><td colspan="8" class="text-center">No filled orders found</td></tr>';
        updateWeeklyEarningsSummary([], 0);
        return;
    }
    
    // Sort filled orders by fill date (newest first)
    filledOrdersData.sort((a, b) => {
        const dateA = new Date(a.filled_at || a.last_updated || a.timestamp || a.created_at);
        const dateB = new Date(b.filled_at || b.last_updated || b.timestamp || b.created_at);
        return dateB - dateA;
    });
    
    // Filter for orders filled this week
    const thisWeekOrders = filledOrdersData.filter(order => {
        const fillDate = new Date(order.filled_at || order.last_updated || order.timestamp || order.created_at);
        return isWithinCurrentWeek(fillDate);
    });
    
    // Calculate total earnings for the week
    let weeklyEarnings = 0;
    
    // Add each filled order to the table
    filledOrdersData.forEach(order => {
        const row = document.createElement('tr');
        
        // Format the strike price
        const strike = order.strike ? `$${order.strike}` : 'N/A';
        
        // Get fill price and commission
        const fillPrice = order.avg_fill_price || 0;
        const commission = order.commission || 0;
        
        // Calculate net premium (fill price - commission)
        const netPremium = fillPrice * 100 - commission; // Multiplied by 100 to get total premium for a contract
        
        // Add to weekly earnings if this order was filled this week
        const fillDate = new Date(order.filled_at || order.last_updated || order.timestamp || order.created_at);
        if (isWithinCurrentWeek(fillDate)) {
            weeklyEarnings += netPremium;
        }
        
        // Format date
        const formattedFillDate = formatDate(order.filled_at || order.last_updated || order.timestamp || order.created_at);
        
        // Determine if this is a recent order (this week)
        const isRecentOrder = isWithinCurrentWeek(fillDate);
        
        // Create the row HTML
        row.innerHTML = `
            <td>${order.ticker}</td>
            <td>${order.option_type}</td>
            <td>${strike}</td>
            <td>${order.expiration || 'N/A'}</td>
            <td>${formatCurrency(fillPrice)}</td>
            <td>${formatCurrency(commission)}</td>
            <td>${formatCurrency(netPremium)}</td>
            <td>${formattedFillDate}</td>
        `;
        
        // Highlight recent orders
        if (isRecentOrder) {
            row.classList.add('table-success');
        }
        
        filledOrdersTable.appendChild(row);
    });
    
    // Update the weekly earnings summary
    updateWeeklyEarningsSummary(thisWeekOrders, weeklyEarnings);
}

/**
 * Update the weekly earnings summary display
 * @param {Array} weeklyOrders - Array of orders filled this week
 * @param {number} totalEarnings - Total earnings for the week
 */
function updateWeeklyEarningsSummary(weeklyOrders, totalEarnings) {
    const orderCount = weeklyOrders.length;
    const averagePremium = orderCount > 0 ? totalEarnings / orderCount : 0;
    
    // Update the display elements
    document.getElementById('weekly-earnings-total').textContent = formatCurrency(totalEarnings);
    document.getElementById('weekly-order-count').textContent = orderCount;
    document.getElementById('weekly-average-premium').textContent = formatCurrency(averagePremium);
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
    
    // Add listener to refresh filled orders button
    const refreshFilledOrdersButton = document.getElementById('refresh-filled-orders');
    if (refreshFilledOrdersButton) {
        refreshFilledOrdersButton.addEventListener('click', loadFilledOrders);
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
        // Fetch pending orders
        const pendingData = await fetchPendingOrders(false);
        if (pendingData && pendingData.orders) {
            pendingOrdersData = pendingData.orders;
            console.log(`Loaded ${pendingOrdersData.length} pending orders`);
            updatePendingOrdersTable();
        }
        
        // Also load filled orders
        await loadFilledOrders();
    } catch (error) {
        console.error('Error loading pending orders:', error);
        showAlert('Error loading pending orders', 'danger');
    }
}

/**
 * Load executed/filled orders from API
 */
async function loadFilledOrders() {
    try {
        // Fetch executed orders
        const executedData = await fetchPendingOrders(true);
        if (executedData && executedData.orders) {
            console.log(`Received ${executedData.orders.length} executed orders from API`);
            
            // Filter for orders that are actually executed (not canceled or rejected)
            filledOrdersData = executedData.orders.filter(order => 
                order.status === 'executed' && 
                order.avg_fill_price
            );
            
            console.log(`Filtered to ${filledOrdersData.length} filled orders with fill price`);
            updateFilledOrdersTable();
        } else {
            console.warn('No executed orders data received from API');
        }
    } catch (error) {
        console.error('Error loading filled orders:', error);
        showAlert('Error loading filled orders', 'danger');
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
                console.log(`Received ${result.updated_orders.length} updated orders from status check`);
                
                // Track if any order's status changed to executed
                let orderWasExecuted = false;
                
                // Update the orders that changed
                result.updated_orders.forEach(updatedOrder => {
                    const orderIndex = pendingOrdersData.findIndex(order => order.id == updatedOrder.id);
                    if (orderIndex !== -1) {
                        // Check if this order is newly executed
                        if (pendingOrdersData[orderIndex].status !== 'executed' && 
                            updatedOrder.status === 'executed') {
                            orderWasExecuted = true;
                        }
                        
                        // Update the order with new status and details
                        pendingOrdersData[orderIndex] = {
                            ...pendingOrdersData[orderIndex],
                            ...updatedOrder
                        };
                    }
                });
                
                // Update the pending orders table
                updatePendingOrdersTable();
                
                // If any order was executed, reload the filled orders
                if (orderWasExecuted) {
                    console.log('An order was executed, refreshing filled orders');
                    await loadFilledOrders();
                }
                
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
    loadFilledOrders,
    executeOrderById,
    cancelOrderById
}; 