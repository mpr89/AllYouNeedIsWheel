/**
 * Options Table module for handling options display and interaction
 */
import { fetchOptionData, fetchTickers, saveOptionOrder, fetchAccountData } from './api.js';
import { showAlert } from '../utils/alerts.js';
import { formatCurrency, formatPercentage } from './account.js';

// Store options data
let tickersData = {};
// Store portfolio summary data
let portfolioSummary = null;
// Flag to track if event listeners have been initialized
let eventListenersInitialized = false;
// Flag to track if container event listeners have been initialized
let containerEventListenersInitialized = false;

// Reference to loadPendingOrders function from orders.js
let loadPendingOrdersFunc = null;

/**
 * Try to get the loadPendingOrders function from window or import it dynamically
 * @returns {Function|null} The loadPendingOrders function or null if not available
 */
async function getLoadPendingOrdersFunction() {
    // First check if it's available on window (global)
    if (typeof window.loadPendingOrders === 'function') {
        return window.loadPendingOrders;
    }
    
    // If not, try to get it from a custom event
    if (!loadPendingOrdersFunc) {
        try {
            // Create and dispatch a custom event to request the function
            const requestEvent = new CustomEvent('requestPendingOrdersRefresh', {
                detail: { source: 'options-table' }
            });
            document.dispatchEvent(requestEvent);
            console.log('Dispatched event requesting pending orders refresh');
        } catch (error) {
            console.error('Error trying to request pending orders refresh:', error);
        }
    }
    
    return null;
}

/**
 * Refresh the pending orders table
 */
async function refreshPendingOrders() {
    try {
        // Try multiple methods to refresh the pending orders table
        
        // Method 1: Use the global loadPendingOrders function if available
        if (typeof window.loadPendingOrders === 'function') {
            console.log('Refreshing pending orders using window.loadPendingOrders');
            await window.loadPendingOrders();
            return;
        }
        
        // Method 2: Dispatch a custom event that orders.js is listening for
        console.log('Dispatching ordersUpdated event to trigger refresh');
        const event = new CustomEvent('ordersUpdated');
        document.dispatchEvent(event);
        
        // Method 3: Try to find and click the refresh button in the DOM
        const refreshButton = document.getElementById('refresh-pending-orders');
        if (refreshButton) {
            console.log('Clicking the refresh-pending-orders button');
            refreshButton.click();
            return;
        }
        
        console.log('All pending orders refresh methods attempted');
    } catch (error) {
        console.error('Error refreshing pending orders:', error);
    }
}

/**
 * Calculate the Out of The Money percentage
 * @param {number} strikePrice - The option strike price
 * @param {number} currentPrice - The current stock price
 * @returns {number} The OTM percentage
 */
function calculateOTMPercentage(strikePrice, currentPrice) {
    if (!strikePrice || !currentPrice) return 0;
    
    const diff = strikePrice - currentPrice;
    return (diff / currentPrice) * 100;
}

/**
 * Calculate recommended put options quantity based on portfolio data
 * @param {number} stockPrice - Current stock price
 * @param {number} putStrike - Put option strike price
 * @param {string} ticker - The ticker symbol
 * @returns {Object} Recommended quantity and explanation
 */
function calculateRecommendedPutQuantity(stockPrice, putStrike, ticker) {
    // Default recommendation if we can't calculate
    const defaultRecommendation = {
        quantity: 1,
        explanation: "Default recommendation"
    };
    
    // If we don't have portfolio data, return default
    if (!portfolioSummary || !stockPrice || !putStrike) {
        return defaultRecommendation;
    }
    
    try {
        // Get cash balance and total portfolio value
        const cashBalance = portfolioSummary.cash_balance || 0;
        const totalPortfolioValue = portfolioSummary.account_value || 0;
        
        // Get number of unique tickers (for diversification)
        const totalStocks = Object.keys(tickersData).length || 1;
        
        // Calculate maximum allocation per stock (200% of cash balance / number of stocks)
        const maxAllocationPerStock = (2.0 * cashBalance) / totalStocks;
        
        // Calculate how many contracts that would allow (each contract = 100 shares)
        const potentialContracts = Math.floor(maxAllocationPerStock / (putStrike * 100));
        
        // Limit to a reasonable number based on portfolio size
        const maxContracts = Math.min(potentialContracts, 10);
        const recommendedQuantity = Math.max(1, maxContracts);
        
        return {
            quantity: recommendedQuantity,
            explanation: `Based on cash: ${formatCurrency(cashBalance)}, diversification across ${totalStocks} stocks`
        };
    } catch (error) {
        console.error("Error calculating recommended put quantity:", error);
        return defaultRecommendation;
    }
}

/**
 * Calculate earnings summary for all options
 * @param {Object} tickersData - The data for all tickers
 * @returns {Object} Summary of earnings
 */
function calculateEarningsSummary(tickersData) {
    const summary = {
        totalWeeklyCallPremium: 0,
        totalWeeklyPutPremium: 0,
        totalWeeklyPremium: 0,
        portfolioValue: 0, // Will be calculated from position value
        projectedAnnualEarnings: 0,
        projectedAnnualReturn: 0,
        totalPutExerciseCost: 0, // NEW: Total cost if all puts are exercised
        cashBalance: portfolioSummary ? portfolioSummary.cash_balance || 0 : 0
    };
    
    // Process each ticker to get total premium earnings
    Object.values(tickersData).forEach(tickerData => {
        if (!tickerData || !tickerData.data || !tickerData.data.data) {
            console.log("Skipping ticker with invalid data structure", tickerData);
            return;
        }
        
        // Process each ticker's option data
        Object.values(tickerData.data.data).forEach(optionData => {
            // Get position information (number of shares owned)
            const sharesOwned = optionData.position || 0;
            
            // Skip positions with less than 100 shares (minimum for 1 option contract)
            if (sharesOwned < 100) {
                console.log(`Skipping position with ${sharesOwned} shares (less than 100)`);
                return; // Skip this position in earnings calculation
            }
            
            // Add portfolio value from stock positions
            const stockPrice = optionData.stock_price || 0;
            summary.portfolioValue += sharesOwned * stockPrice;
            
            // Calculate max contracts based on shares owned
            const maxCallContracts = Math.floor(sharesOwned / 100);
            
            // Process call options
            if (optionData.calls && optionData.calls.length > 0) {
                const callOption = optionData.calls[0];
            if (callOption && callOption.ask) {
                const callPremiumPerContract = callOption.ask * 100; // Premium per contract (100 shares)
                const totalCallPremium = callPremiumPerContract * maxCallContracts;
                summary.totalWeeklyCallPremium += totalCallPremium;
            }
            }
            
            // Process put options
            if (optionData.puts && optionData.puts.length > 0) {
                const putOption = optionData.puts[0];
            if (putOption && putOption.ask) {
                const putPremiumPerContract = putOption.ask * 100;
                // Use custom put quantity if available
                const ticker = optionData.symbol || Object.keys(tickerData.data.data)[0];
                const customPutQuantity = tickerData.putQuantity || Math.floor(sharesOwned / 100);
                const totalPutPremium = putPremiumPerContract * customPutQuantity;
                summary.totalWeeklyPutPremium += totalPutPremium;
                
                // Calculate total exercise cost
                const putExerciseCost = putOption.strike * customPutQuantity * 100;
                summary.totalPutExerciseCost += putExerciseCost;
                }
            }
        });
    });
    
    // Calculate total weekly premium
    summary.totalWeeklyPremium = summary.totalWeeklyCallPremium + summary.totalWeeklyPutPremium;
    
    // Calculate projected annual earnings (assuming the same premium every week for 52 weeks)
    summary.projectedAnnualEarnings = summary.totalWeeklyPremium * 52;
    
    // Calculate projected annual return as percentage of portfolio value
    if (summary.portfolioValue > 0) {
        summary.projectedAnnualReturn = (summary.projectedAnnualEarnings / summary.portfolioValue) * 100;
    }
    
    console.log("Earnings summary:", summary);
    
    return summary;
}

/**
 * Update options table with data from stock positions
 */
function updateOptionsTable() {
    console.log("Updating options table with data:", tickersData);
    
    const optionsTableContainer = document.getElementById('options-table-container');
    if (!optionsTableContainer) {
        console.error("Options table container not found in the DOM");
        return;
    }
    
    // Clear existing tables
    optionsTableContainer.innerHTML = '';
    
    // Get tickers
    const tickers = Object.keys(tickersData);
    
    if (tickers.length === 0) {
        console.log("No tickers found");
        optionsTableContainer.innerHTML = '<div class="alert alert-info">No stock positions available. Please add stock positions first.</div>';
        return;
    }
    
    console.log("Found ticker data for:", tickers.join(", "));
    
    // Keep track of tickers with sufficient shares
    let sufficientSharesCount = 0;
    let insufficientSharesCount = 0;
    let filteredTickers = [];
    let visibleTickers = [];
    
    // First pass: Pre-filter tickers with insufficient shares
    const eligibleTickers = tickers.filter(ticker => {
        const tickerData = tickersData[ticker];
        
        // Skip tickers without data
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            console.log(`Ticker ${ticker} has no data or invalid data structure:`, tickerData);
            return true; // Keep to show "No data available" message
        }
        
        // Check shares
        const optionData = tickerData.data.data[ticker];
        const sharesOwned = optionData.position || 0;
        
        console.log(`Ticker ${ticker} has ${sharesOwned} shares`);
        
        // Filter out tickers with less than 100 shares (can't sell covered calls)
        if (sharesOwned < 100) {
            console.log(`${ticker} has ${sharesOwned} shares, less than required for selling options`);
            insufficientSharesCount++;
            return false;
        }
        
        sufficientSharesCount++;
        return true;
    });
    
    // Create tabs for call and put options
    const tabsHTML = `
        <ul class="nav nav-tabs mb-3" id="options-tabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="call-options-tab" data-bs-toggle="tab" data-bs-target="#call-options-section" type="button" role="tab" aria-controls="call-options-section" aria-selected="true">
                    Covered Calls
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="put-options-tab" data-bs-toggle="tab" data-bs-target="#put-options-section" type="button" role="tab" aria-controls="put-options-section" aria-selected="false">
                    Cash-Secured Puts
                </button>
            </li>
        </ul>
        
        <div class="tab-content" id="options-tabs-content">
            <div class="tab-pane fade show active" id="call-options-section" role="tabpanel" aria-labelledby="call-options-tab">
                <div class="d-flex justify-content-end mb-2">
                    <button class="btn btn-sm btn-outline-success me-2" id="sell-all-calls">
                        <i class="bi bi-check2-all"></i> Sell All
                    </button>
                    <button class="btn btn-sm btn-outline-primary" id="refresh-all-calls">
                        <i class="bi bi-arrow-repeat"></i> Refresh All Calls
                    </button>
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-sm" id="call-options-table">
                        <thead>
                            <tr>
                                <th>Ticker</th>
                                <th>Shares</th>
                                <th>Stock Price</th>
                                <th>OTM %</th>
                                <th>Strike</th>
                                <th>Expiration</th>
                                <th>Premium</th>
                                <th>Delta</th>
                                <th>Qty</th>
                                <th>Total Premium</th>
                                <th>% Return</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
            
            <div class="tab-pane fade" id="put-options-section" role="tabpanel" aria-labelledby="put-options-tab">
                <div class="d-flex justify-content-end mb-2">
                    <button class="btn btn-sm btn-outline-success me-2" id="sell-all-puts">
                        <i class="bi bi-check2-all"></i> Sell All
                    </button>
                    <button class="btn btn-sm btn-outline-primary" id="refresh-all-puts">
                        <i class="bi bi-arrow-repeat"></i> Refresh All Puts
                    </button>
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-sm" id="put-options-table">
                        <thead>
                            <tr>
                                <th>Ticker</th>
                                <th>Stock Price</th>
                                <th>OTM %</th>
                                <th>Strike</th>
                                <th>Expiration</th>
                                <th>Premium</th>
                                <th>Delta</th>
                                <th>Qty</th>
                                <th>Total Premium</th>
                                <th>% Return</th>
                                <th>Cash Required</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    
    // Add the tabs and tables to the container
    optionsTableContainer.innerHTML = tabsHTML;
    
    // Get table references
    const callTableBody = document.querySelector('#call-options-table tbody');
    const putTableBody = document.querySelector('#put-options-table tbody');
    
    // Add debug information about the tables
    console.log('Call table body element:', callTableBody);
    console.log('Put table body element:', putTableBody);
    
    // Ensure put table has a tbody and correct structure
    const putTable = document.querySelector('#put-options-table');
    if (putTable && !putTableBody) {
        console.log('Put table has no tbody, adding it now');
        const tbody = document.createElement('tbody');
        putTable.appendChild(tbody);
    }
    
    // Requery putTableBody if it was just created
    const updatedPutTableBody = putTableBody || document.querySelector('#put-options-table tbody');
    
    // If no eligible tickers, show message in both tables
    if (eligibleTickers.length === 0) {
        const noDataMessage = '<tr><td colspan="12" class="text-center">No eligible stock positions found. You need at least 100 shares to sell covered calls.</td></tr>';
        callTableBody.innerHTML = noDataMessage;
        updatedPutTableBody.innerHTML = noDataMessage;
        return;
    }
    
    // Process each eligible ticker and add to the appropriate table
    let callCount = 0;
    let putCount = 0;
    
    for (const ticker of eligibleTickers) {
        const tickerData = tickersData[ticker];
        
        // Skip tickers without data
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            continue;
        }
        
        const optionData = tickerData.data.data[ticker];
        const stockPrice = optionData.stock_price || 0;
        const sharesOwned = optionData.position || 0;
        
        // Process call options
        let callOptions = [];
        if (optionData.calls && optionData.calls.length > 0) {
            console.log(`Found ${optionData.calls.length} call options for ${ticker}`);
            callOptions = optionData.calls;
        } else if (optionData.call) {
            console.log(`Found single call option for ${ticker}`);
            callOptions = [optionData.call];
        } else {
            console.log(`No call options found for ${ticker}`);
        }
        
        // Process put options
        let putOptions = [];
        if (optionData.puts && optionData.puts.length > 0) {
            console.log(`Found ${optionData.puts.length} put options for ${ticker}`);
            putOptions = optionData.puts;
        } else if (optionData.put) {
            console.log(`Found single put option for ${ticker}`);
            putOptions = [optionData.put];
        } else {
            console.log(`No put options found for ${ticker}`);
        }
        
        // Add call options to call table
        for (const call of callOptions) {
            if (!call) {
                console.log(`Skipping undefined call option for ${ticker}`);
                continue;
            }
            console.log(`Processing call option:`, call);
            
            const strike = call.strike || 0;
            const bid = call.bid || 0;
            const ask = call.ask || 0;
            const mid = (bid + ask) / 2;
            const delta = call.delta || 0;
            const expiration = call.expiration || '';
            
            // Calculate OTM percentage
            const otmPercent = calculateOTMPercentage(strike, stockPrice);
            
            // Calculate contracts based on shares owned
            const maxContracts = Math.floor(sharesOwned / 100);
            
            // Calculate premium
            const premiumPerContract = bid * 100; // Premium per contract (100 shares)
            const totalPremium = premiumPerContract * maxContracts;
            
            // Calculate return on capital
            const returnOnCapital = strike > 0 ? (totalPremium / (strike * 100 * maxContracts)) * 100 : 0;
            
            // Add row to call table
            const callRow = document.createElement('tr');
            callRow.innerHTML = `
                <td>${ticker}</td>
                <td>${sharesOwned}</td>
                <td>${formatCurrency(stockPrice)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <input type="number" class="form-control form-control-sm otm-input" 
                            data-ticker="${ticker}" 
                            min="1" max="50" step="1" 
                            value="${tickerData.otmPercentage || 10}">
                        <button class="btn btn-outline-secondary btn-sm refresh-otm" data-ticker="${ticker}">
                            <i class="bi bi-arrow-repeat"></i>
                        </button>
                    </div>
                </td>
                <td>${formatCurrency(strike)}</td>
                <td>${expiration}</td>
                <td>${formatCurrency(bid)}</td>
                <td>${delta.toFixed(2)}</td>
                <td>${maxContracts}</td>
                <td>${formatCurrency(totalPremium)}</td>
                <td>${formatPercentage(returnOnCapital)}</td>
                <td>
                    <button class="btn btn-sm btn-primary sell-option" data-ticker="${ticker}" data-option-type="CALL" data-strike="${strike}" data-expiration="${expiration}">
                        Sell
                    </button>
                </td>
            `;
            callTableBody.appendChild(callRow);
            callCount++;
        }
        
        // Add put options to put table
        for (const put of putOptions) {
            if (!put) {
                console.log(`Skipping undefined put option for ${ticker}`);
                continue;
            }
            console.log(`Processing put option:`, put);
            
            const strike = put.strike || 0;
            const bid = put.bid || 0;
            const ask = put.ask || 0;
            const mid = (bid + ask) / 2;
            const delta = put.delta || 0;
            const expiration = put.expiration || '';
            
            // Calculate OTM percentage (negative for puts because they're OTM below the stock price)
            const otmPercent = -calculateOTMPercentage(strike, stockPrice);
            
            // Calculate recommended quantity
            const recommendation = calculateRecommendedPutQuantity(stockPrice, strike, ticker);
            const recommendedQty = recommendation.quantity;
            
            // Calculate premium
            const premiumPerContract = bid * 100; // Premium per contract (100 shares)
            const totalPremium = premiumPerContract * recommendedQty;
            
            // Calculate cash required
            const cashRequired = strike * 100 * recommendedQty;
            
            // Calculate return on cash
            const returnOnCash = cashRequired > 0 ? (totalPremium / cashRequired) * 100 : 0;
            
            // Add row to put table
            const putRow = document.createElement('tr');
            putRow.innerHTML = `
            <td>${ticker}</td>
            <td>${formatCurrency(stockPrice)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <input type="number" class="form-control form-control-sm otm-input" 
                            data-ticker="${ticker}" 
                            min="1" max="50" step="1" 
                            value="${tickerData.otmPercentage || 10}">
                        <button class="btn btn-outline-secondary btn-sm refresh-otm" data-ticker="${ticker}">
                            <i class="bi bi-arrow-repeat"></i>
                        </button>
                </div>
            </td>
                <td>${formatCurrency(strike)}</td>
                <td>${expiration}</td>
                <td>${formatCurrency(bid)}</td>
                <td>${delta.toFixed(2)}</td>
                <td>${recommendedQty}</td>
                <td>${formatCurrency(totalPremium)}</td>
                <td>${formatPercentage(returnOnCash)}</td>
                <td>${formatCurrency(cashRequired)}</td>
                <td>
                    <button class="btn btn-sm btn-primary sell-option" data-ticker="${ticker}" data-option-type="PUT" data-strike="${strike}" data-expiration="${expiration}">
                        Sell
                    </button>
            </td>
        `;
            updatedPutTableBody.appendChild(putRow);
            putCount++;
        }
    }
    
    // If no call options found, show message
    if (callCount === 0) {
        callTableBody.innerHTML = '<tr><td colspan="12" class="text-center">No call options available for your stock positions.</td></tr>';
    }
    
    // If no put options found, show message
    if (putCount === 0) {
        updatedPutTableBody.innerHTML = '<tr><td colspan="12" class="text-center">No put options available.</td></tr>';
    }
    
    // Add tab event listeners via the addOptionsTableEventListeners function
    addOptionsTableEventListeners();
    
    // Add input event listeners for OTM% inputs
    addOtmInputEventListeners();
    
    console.log('Options table update complete. Call count:', callCount, 'Put count:', putCount);
}

/**
 * Add event listeners to the options table
 */
function addOptionsTableEventListeners() {
    // Get the container
    const container = document.getElementById('options-table-container');
    if (!container) return;
    
    // Initialize Bootstrap tabs if Bootstrap JS is available
    if (typeof bootstrap !== 'undefined') {
        const tabEls = document.querySelectorAll('#options-tabs button[data-bs-toggle="tab"]');
        tabEls.forEach(tabEl => {
            const tab = new bootstrap.Tab(tabEl);
            
            tabEl.addEventListener('click', event => {
                event.preventDefault();
                tab.show();
                console.log(`Tab ${tabEl.id} activated via Bootstrap Tab`);
            });
        });
    
        console.log('Bootstrap tabs initialized');
    } else {
        console.log('Bootstrap JS not available, using fallback tab switching');
        
        // Fallback tab switching (manual)
        const callTab = document.getElementById('call-options-tab');
        const putTab = document.getElementById('put-options-tab');
        const callSection = document.getElementById('call-options-section');
        const putSection = document.getElementById('put-options-section');
        
        if (callTab && putTab && callSection && putSection) {
            callTab.addEventListener('click', (e) => {
                e.preventDefault();
                callTab.classList.add('active');
                putTab.classList.remove('active');
                callSection.classList.add('show', 'active');
                putSection.classList.remove('show', 'active');
                console.log('Switched to call options tab (fallback)');
            });
            
            putTab.addEventListener('click', (e) => {
                e.preventDefault();
                callTab.classList.remove('active');
                putTab.classList.add('active');
                callSection.classList.remove('show', 'active');
                putSection.classList.add('show', 'active');
                console.log('Switched to put options tab (fallback)');
            });
        }
    }
    
    // Set up container event delegation if not already set up
    if (!containerEventListenersInitialized) {
        console.log('Initializing container event delegation');
        
        // Add event delegation for all buttons in the container
        container.addEventListener('click', async (event) => {
            // Handle refresh button click
            if (event.target.classList.contains('refresh-options') || 
                event.target.closest('.refresh-options')) {
                
                const button = event.target.classList.contains('refresh-options') ? 
                               event.target : 
                               event.target.closest('.refresh-options');
                
                const ticker = button.dataset.ticker;
                if (ticker) {
                    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                    button.disabled = true;
                    
                    try {
                        await refreshOptionsForTicker(ticker);
                        button.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh';
                    } catch (error) {
                        console.error('Error refreshing ticker:', error);
                    } finally {
                        button.disabled = false;
                    }
                }
            }
            
            // Handle OTM% refresh button click
            if (event.target.classList.contains('refresh-otm') || 
                event.target.closest('.refresh-otm')) {
                
                const button = event.target.classList.contains('refresh-otm') ? 
                               event.target : 
                               event.target.closest('.refresh-otm');
                
                const ticker = button.dataset.ticker;
                if (ticker) {
                    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
                    button.disabled = true;
                    
                    try {
                        // Find the related input element
                        const inputGroup = button.closest('.input-group');
                        const otmInput = inputGroup.querySelector('.otm-input');
                        const otmPercentage = parseInt(otmInput.value, 10);
                        
                        // Update ticker's OTM percentage
                        if (tickersData[ticker]) {
                            tickersData[ticker].otmPercentage = otmPercentage;
                        }
                        
                        // Refresh options with the new OTM percentage
                        await refreshOptionsForTicker(ticker);
                    } catch (error) {
                        console.error(`Error refreshing ${ticker} with new OTM%:`, error);
                    } finally {
                        button.innerHTML = '<i class="bi bi-arrow-repeat"></i>';
                        button.disabled = false;
                    }
                }
            }
            
            // Handle sell option button click
            if (event.target.classList.contains('sell-option') || 
                event.target.closest('.sell-option')) {
                
                const button = event.target.classList.contains('sell-option') ? 
                               event.target : 
                               event.target.closest('.sell-option');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                const ticker = button.dataset.ticker;
                const optionType = button.dataset.optionType;
                const strike = button.dataset.strike;
                const expiration = button.dataset.expiration;
                
                if (ticker && optionType && strike && expiration) {
                    // Create order data
                    const orderData = {
                        ticker: ticker,
                        option_type: optionType,
                        strike: parseFloat(strike),
                        expiration: expiration,
                        action: 'SELL',
                        quantity: optionType === 'CALL' ? 
                            Math.floor(tickersData[ticker]?.data?.data?.[ticker]?.position / 100) || 1 :
                            (tickersData[ticker]?.putQuantity || 1)
                    };
                    
                    try {
                        // Proceed directly without confirmation dialog
                        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
                        button.disabled = true;
                        
                        // Save the order
                        const result = await saveOptionOrder(orderData);
                        
                        if (result && result.order_id) {
                            console.log(`Order saved successfully! Order ID: ${result.order_id}`);
                            // Trigger refresh of the pending orders table
                            await refreshPendingOrders();
                        } else {
                            console.error('Failed to save order');
                        }
                    } catch (error) {
                        console.error('Error saving order:', error);
                    } finally {
                        button.innerHTML = 'Sell';
                        button.disabled = false;
                    }
                }
            }
            
            // Handle sell all calls button click using event delegation
            if (event.target.id === 'sell-all-calls' || 
                event.target.closest('#sell-all-calls')) {
                
                const button = event.target.id === 'sell-all-calls' ? 
                               event.target : 
                               event.target.closest('#sell-all-calls');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                console.log('Sell all calls button clicked via delegation');
                try {
                    await sellAllOptions('CALL');
                    // Note: Button state and alerts are handled inside sellAllOptions
                } catch (error) {
                    console.error('Error in sell all calls handler:', error);
                }
            }
            
            // Handle sell all puts button click using event delegation
            if (event.target.id === 'sell-all-puts' || 
                event.target.closest('#sell-all-puts')) {
                
                const button = event.target.id === 'sell-all-puts' ? 
                               event.target : 
                               event.target.closest('#sell-all-puts');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                console.log('Sell all puts button clicked via delegation');
                try {
                    await sellAllOptions('PUT');
                    // Note: Button state and alerts are handled inside sellAllOptions
                } catch (error) {
                    console.error('Error in sell all puts handler:', error);
                }
            }
        });
        
        // Mark container event listeners as initialized
        containerEventListenersInitialized = true;
        console.log('Container event delegation initialized');
    }
    
    // Check if individual button event listeners are already initialized
    if (eventListenersInitialized) {
        console.log('Button event listeners already initialized, skipping');
        return;
    }
    
    console.log('Initializing individual button event listeners');
    
    // Register dedicated listeners for the various buttons
    
    // Refresh all button
    const refreshAllButton = document.getElementById('refresh-all-options');
    if (refreshAllButton) {
        refreshAllButton.addEventListener('click', async () => {
            refreshAllButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
            refreshAllButton.disabled = true;
            
            try {
                await refreshAllOptions();
            } catch (error) {
                console.error('Error refreshing all options:', error);
            } finally {
                refreshAllButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All';
                refreshAllButton.disabled = false;
            }
        });
    }

    // Refresh all calls button
    const refreshAllCallsButton = document.getElementById('refresh-all-calls');
    if (refreshAllCallsButton) {
        refreshAllCallsButton.addEventListener('click', async () => {
            refreshAllCallsButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
            refreshAllCallsButton.disabled = true;
            
            try {
                await refreshAllOptions('CALL');
            } catch (error) {
                console.error('Error refreshing all call options:', error);
            } finally {
                refreshAllCallsButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All Calls';
                refreshAllCallsButton.disabled = false;
            }
        });
    }

    // Refresh all puts button
    const refreshAllPutsButton = document.getElementById('refresh-all-puts');
    if (refreshAllPutsButton) {
        refreshAllPutsButton.addEventListener('click', async () => {
            refreshAllPutsButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
            refreshAllPutsButton.disabled = true;
            
            try {
                await refreshAllOptions('PUT');
            } catch (error) {
                console.error('Error refreshing all put options:', error);
            } finally {
                refreshAllPutsButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All Puts';
                refreshAllPutsButton.disabled = false;
            }
        });
    }
    
    // Note: We're removing direct event listeners for sell-all buttons
    // and using event delegation instead (defined above in the container click handler)
    
    // Mark the event listeners as initialized
    eventListenersInitialized = true;
    console.log('Individual button event listeners initialization complete');
    
    // Add input event listeners for OTM% inputs - these need to be added each time
    addOtmInputEventListeners();
}

/**
 * Add event listeners for OTM% inputs - these need to be added each time
 * the table is updated
 */
function addOtmInputEventListeners() {
    document.querySelectorAll('.otm-input').forEach(input => {
        input.addEventListener('change', function() {
            const ticker = this.dataset.ticker;
            const otmPercentage = parseInt(this.value, 10);
            
            // Update ticker's OTM percentage
            if (tickersData[ticker]) {
                tickersData[ticker].otmPercentage = otmPercentage;
                console.log(`Updated ${ticker} OTM% to ${otmPercentage}`);
            }
        });
    });
}

/**
 * Refresh options data for a specific ticker
 * @param {string} ticker - The ticker symbol to refresh options for
 */
async function refreshOptionsForTicker(ticker) {
    try {
        // Get OTM percentage from ticker data or use default
        const otmPercentage = tickersData[ticker]?.otmPercentage || 10;
        
        console.log(`Refreshing options for ${ticker} with OTM ${otmPercentage}%`);
        
        // Make two separate API calls for call and put options
        const callData = await fetchOptionData(ticker, otmPercentage, 'CALL');
        const putData = await fetchOptionData(ticker, otmPercentage, 'PUT');
        
        console.log('CALL data:', callData);
        console.log('PUT data:', putData);
        
        // Merge the data before updating tickersData
        const mergedData = {
            data: {
                data: {}
            }
        };
        
        // Initialize the ticker data with empty arrays for calls and puts
        mergedData.data.data[ticker] = {
            stock_price: 0,
            position: 0,
            calls: [],
            puts: []
        };
        
        // Copy call data if available
        if (callData && callData.data && callData.data[ticker]) {
            console.log(`Processing call data for ${ticker}`);
            mergedData.data.data[ticker].stock_price = callData.data[ticker].stock_price || 0;
            mergedData.data.data[ticker].position = callData.data[ticker].position || 0;
            mergedData.data.data[ticker].calls = callData.data[ticker].calls || [];
        }
        
        // Copy put data if available
        if (putData && putData.data && putData.data[ticker]) {
            console.log(`Processing put data for ${ticker}`);
            // If we didn't get stock price and position from call data, use put data
            if (!mergedData.data.data[ticker].stock_price) {
                mergedData.data.data[ticker].stock_price = putData.data[ticker].stock_price || 0;
            }
            if (!mergedData.data.data[ticker].position) {
                mergedData.data.data[ticker].position = putData.data[ticker].position || 0;
            }
            mergedData.data.data[ticker].puts = putData.data[ticker].puts || [];
        }
        
        console.log('Merged data:', mergedData);
        
        // Update the ticker data
        tickersData[ticker] = {
            data: mergedData.data,
            otmPercentage: otmPercentage,
            putQuantity: tickersData[ticker]?.putQuantity || 1  // Default to 1 for put quantity
        };
        
        console.log(`Updated tickersData for ${ticker}:`, tickersData[ticker]);
        
        // Update the UI
        updateOptionsTable();
        
        // Make sure event listeners are added
        addOptionsTableEventListeners();
        
    } catch (error) {
        console.error(`Error refreshing options for ${ticker}:`, error);
        showAlert(`Error refreshing options for ${ticker}: ${error.message}`, 'danger');
    }
}

/**
 * Refresh options data for all tickers
 * @param {string} [optionType] - Optional option type ('CALL' or 'PUT') to refresh only that type
 */
async function refreshAllOptions(optionType) {
    // Show a loading message
    const optionsTableContainer = document.getElementById('options-table-container');
    if (optionsTableContainer) {
        // If refreshing a specific option type, only update that section
        if (optionType) {
            const tableId = optionType === 'CALL' ? 'call-options-table' : 'put-options-table';
            const tableBody = document.querySelector(`#${tableId} tbody`);
            if (tableBody) {
                tableBody.innerHTML = '<tr><td colspan="12" class="text-center"><div class="spinner-border spinner-border-sm text-primary" role="status"></div> Loading options data...</td></tr>';
            }
        } else {
            // Otherwise, show loading for the whole container
            optionsTableContainer.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading options data...</p></div>';
        }
    }
    
    try {
        // Get list of tickers to refresh
    const tickers = Object.keys(tickersData);
    if (tickers.length === 0) {
            const tickersResult = await fetchTickers();
            if (tickersResult && tickersResult.tickers) {
                tickers.push(...tickersResult.tickers);
            }
        }
        
        // Fetch account data for proper recommendations
        const accountData = await fetchAccountData();
        if (accountData) {
            portfolioSummary = accountData;
        }
        
        console.log(`Refreshing options for ${tickers.length} tickers${optionType ? ` (${optionType} options only)` : ''}`);
    
    // Process each ticker
        const promises = [];
    for (const ticker of tickers) {
            if (optionType) {
                // If specific option type, only refresh that type
                promises.push(refreshOptionsForTickerByType(ticker, optionType));
            } else {
                // Otherwise refresh all options
                promises.push(refreshOptionsForTicker(ticker));
            }
        }
        
        // Wait for all promises to resolve
        await Promise.all(promises);
        
        // Final UI update
        updateOptionsTable();
        
        // Make sure event listeners are added
        addOptionsTableEventListeners();
        
            } catch (error) {
        console.error(`Error refreshing ${optionType || 'all'} options:`, error);
        showAlert(`Error refreshing options: ${error.message}`, 'danger');
        
        // Reset to empty UI in case of error
        updateOptionsTable();
    }
}

/**
 * Refresh options data for a specific ticker and option type
 * @param {string} ticker - The ticker symbol to refresh options for
 * @param {string} optionType - The option type to refresh ('CALL' or 'PUT')
 */
async function refreshOptionsForTickerByType(ticker, optionType) {
    try {
        // Get OTM percentage from ticker data or use default
        const otmPercentage = tickersData[ticker]?.otmPercentage || 10;
        
        console.log(`Refreshing ${optionType} options for ${ticker} with OTM ${otmPercentage}%`);
        
        // Make API call for specific option type
        const optionData = await fetchOptionData(ticker, otmPercentage, optionType);
        
        console.log(`${optionType} data for ${ticker}:`, optionData);
        
        // Make sure tickersData is initialized for this ticker
        if (!tickersData[ticker]) {
            tickersData[ticker] = {
                data: {
                    data: {}
                },
                otmPercentage: otmPercentage,
                putQuantity: optionType === 'PUT' ? 1 : 0
            };
            
            // Initialize the ticker data structure
            tickersData[ticker].data.data[ticker] = {
                stock_price: 0,
                position: 0,
                calls: [],
                puts: []
            };
        }
        
        // Update only the specific option type data
        if (optionData && optionData.data && optionData.data[ticker]) {
            // Update stock price and position if available
            if (optionData.data[ticker].stock_price) {
                tickersData[ticker].data.data[ticker].stock_price = optionData.data[ticker].stock_price;
            }
            if (optionData.data[ticker].position) {
                tickersData[ticker].data.data[ticker].position = optionData.data[ticker].position;
            }
            
            // Update the specific option type data
            if (optionType === 'CALL') {
                tickersData[ticker].data.data[ticker].calls = optionData.data[ticker].calls || [];
            } else {
                tickersData[ticker].data.data[ticker].puts = optionData.data[ticker].puts || [];
            }
        }
        
        console.log(`Updated ${optionType} data for ${ticker}:`, tickersData[ticker]);
        
    } catch (error) {
        console.error(`Error refreshing ${optionType} options for ${ticker}:`, error);
        showAlert(`Error refreshing ${optionType} options for ${ticker}: ${error.message}`, 'danger');
    }
}

/**
 * Fetch all tickers and their data
 */
async function loadTickers() {
    // Fetch portfolio data first to get latest cash balance
    try {
        portfolioSummary = await fetchAccountData();
        console.log("Portfolio summary:", portfolioSummary);
    } catch (error) {
        console.error('Error fetching portfolio data:', error);
    }
    
    // Fetch tickers
    const data = await fetchTickers();
    if (data && data.tickers) {
        // Initialize ticker data
        data.tickers.forEach(ticker => {
            if (!tickersData[ticker]) {
                tickersData[ticker] = {
                    data: null,
                    otmPercentage: 10, // Default OTM percentage
                    putQuantity: 1 // Default put quantity (updated from 0 to 1)
                };
            }
        });
        
        // Update the UI
        updateOptionsTable();
        
        // Add event listeners to the options table
        addOptionsTableEventListeners();
        
        // Refresh data for each ticker
        for (const ticker of data.tickers) {
            await refreshOptionsForTicker(ticker);
        }
    }
}

/**
 * Sell all available options of a specific type
 * @param {string} optionType - The option type ('CALL' or 'PUT')
 * @returns {Promise<number>} - Number of successfully created orders
 */
async function sellAllOptions(optionType) {
    console.log(`Starting sellAllOptions for ${optionType} options`);
    
    const successOrders = [];
    const failedOrders = [];
    
    // Process each ticker
    const tickers = Object.keys(tickersData);
    console.log(`Processing ${tickers.length} tickers for ${optionType} options`);
    
    // Show progress in the button
    const buttonId = optionType === 'CALL' ? 'sell-all-calls' : 'sell-all-puts';
    const button = document.getElementById(buttonId);
    if (button) {
        button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...`;
        button.disabled = true;
    }
    
    try {
        for (const ticker of tickers) {
            const tickerData = tickersData[ticker];
            
            // Skip tickers without data
            if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
                console.log(`Skipping ticker ${ticker} - missing or invalid data`);
                continue;
            }
            
            const optionData = tickerData.data.data[ticker];
            
            // For CALL options, skip positions with less than 100 shares (can't sell covered calls)
            const sharesOwned = optionData.position || 0;
            if (optionType === 'CALL' && sharesOwned < 100) {
                console.log(`Skipping ticker ${ticker} - insufficient shares for calls: ${sharesOwned}`);
                continue;
            }
            
            // Get the options based on type
            let options = [];
            if (optionType === 'CALL' && optionData.calls && optionData.calls.length > 0) {
                options = optionData.calls;
                console.log(`Found ${options.length} CALL options for ${ticker}`);
            } else if (optionType === 'PUT' && optionData.puts && optionData.puts.length > 0) {
                options = optionData.puts;
                console.log(`Found ${options.length} PUT options for ${ticker}`);
            } else {
                console.log(`No ${optionType} options found for ${ticker}`);
                continue;
            }
            
            // Skip if no options available
            if (options.length === 0) {
                console.log(`No ${optionType} options available for ${ticker}`);
                continue;
            }
            
            // Use the first option (best match)
            const option = options[0];
            if (!option) {
                console.log(`Invalid option data for ${ticker}`);
                continue;
            }
            
            // Update UI with current ticker
            if (button) {
                button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing ${ticker}...`;
            }
            
            console.log(`Processing order for ${ticker} ${optionType} option: ${option.strike} ${option.expiration}`);
            
            // Create order data
            const orderData = {
                ticker: ticker,
                option_type: optionType,
                strike: parseFloat(option.strike),
                expiration: option.expiration,
                action: 'SELL',
                quantity: optionType === 'CALL' ? 
                    Math.floor(sharesOwned / 100) : 
                    (tickerData.putQuantity || 1),
                // Include additional data if available
                bid: option.bid || 0,
                ask: option.ask || 0,
                last: option.last || 0,
                delta: option.delta || 0,
                gamma: option.gamma || 0,
                theta: option.theta || 0,
                vega: option.vega || 0,
                implied_volatility: option.implied_volatility || 0
            };
            
            console.log(`Order data:`, orderData);
            
            try {
                // Save the order
                const result = await saveOptionOrder(orderData);
                
                if (result && result.order_id) {
                    console.log(`Order saved successfully for ${ticker} ${optionType} ${option.strike} ${option.expiration}! Order ID: ${result.order_id}`);
                    successOrders.push(`${ticker} ${optionType} ${option.strike} ${option.expiration}`);
                } else {
                    console.error(`Failed to save order for ${ticker} ${optionType} ${option.strike} ${option.expiration}`);
                    failedOrders.push(`${ticker} ${optionType} ${option.strike} ${option.expiration}`);
                }
            } catch (error) {
                console.error(`Error saving order for ${ticker}:`, error);
                failedOrders.push(`${ticker} ${optionType} ${option.strike} ${option.expiration}`);
            }
            
            // Small delay to prevent overwhelming the server
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // Log results
        console.log(`Sell all ${optionType} orders results:`, {
            successful: successOrders.length,
            failed: failedOrders.length,
            successDetails: successOrders,
            failDetails: failedOrders
        });
        
        if (failedOrders.length > 0) {
            console.error(`${failedOrders.length} orders failed to be created`);
        }
        
        // Reset the button state
        if (button) {
            button.innerHTML = `<i class="bi bi-check2-all"></i> Sell All`;
            button.disabled = false;
        }
        
        // Show a summary alert
        if (successOrders.length > 0) {
            showAlert(`Successfully created ${successOrders.length} ${optionType.toLowerCase()} option orders`, 'success');
            
            // Ensure the pending orders table is refreshed after successful orders
            console.log('Refreshing pending orders table after successful sell all operation');
            
            // Make multiple attempts to refresh pending orders to ensure it works
            // First immediate refresh
            await refreshPendingOrders();
            
            // Second delayed refresh (after a short delay)
            setTimeout(async () => {
                console.log('Executing delayed refresh of pending orders');
                await refreshPendingOrders();
            }, 500);
            
            // Third refresh with a longer delay (to catch any async operations)
            setTimeout(async () => {
                console.log('Executing final refresh of pending orders');
                await refreshPendingOrders();
            }, 1500);
        } else {
            showAlert(`No ${optionType.toLowerCase()} option orders were created`, 'warning');
        }
        
        return successOrders.length;
    } catch (error) {
        console.error(`Error in sellAllOptions for ${optionType}:`, error);
        
        // Reset the button state
        if (button) {
            button.innerHTML = `<i class="bi bi-check2-all"></i> Sell All`;
            button.disabled = false;
        }
        
        // Show error alert
        showAlert(`Error selling ${optionType.toLowerCase()} options: ${error.message}`, 'danger');
        
        return 0;
    }
}

// Export functions
export {
    loadTickers,
    refreshOptionsForTicker,
    refreshOptionsForTickerByType,
    refreshAllOptions,
    sellAllOptions
}; 