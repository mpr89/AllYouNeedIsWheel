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
        portfolioValue: 0,
        projectedAnnualEarnings: 0,
        projectedAnnualReturn: 0,
        weeklyReturn: 0,
        totalPutExerciseCost: 0,
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
    
    // Get portfolio value from portfolioSummary first (most accurate source)
    let totalPortfolioValue = 0;
    
    if (portfolioSummary) {
        // Use the account_value field if available, which should include both stock value and cash
        totalPortfolioValue = portfolioSummary.account_value || 0;
        
        if (totalPortfolioValue === 0) {
            // If account_value is not available, try to calculate from stock value and cash balance
            const stockValue = portfolioSummary.stock_value || 0;
            const cashBalance = portfolioSummary.cash_balance || 0;
            totalPortfolioValue = stockValue + cashBalance;
            
            // Store these values in summary for display
            summary.portfolioValue = stockValue;
            summary.cashBalance = cashBalance;
        } else {
            // If we have account_value, still try to get the breakdown for display purposes
            summary.portfolioValue = portfolioSummary.stock_value || 0;
            summary.cashBalance = portfolioSummary.cash_balance || 0;
        }
    }
    
    // Fallback to window.portfolioData if portfolioSummary didn't provide values
    if (totalPortfolioValue === 0 && window.portfolioData) {
        summary.portfolioValue = window.portfolioData.stockValue || 0;
        summary.cashBalance = window.portfolioData.cashBalance || 0;
        totalPortfolioValue = summary.portfolioValue + summary.cashBalance;
    }
    
    console.log("Portfolio values:", {
        fromSummary: portfolioSummary ? portfolioSummary.account_value : 'N/A',
        calculatedTotal: totalPortfolioValue,
        stockValue: summary.portfolioValue,
        cashBalance: summary.cashBalance
    });
    
    // Calculate weekly return percentage against total portfolio value
    if (totalPortfolioValue > 0) {
        summary.weeklyReturn = (summary.totalWeeklyPremium / totalPortfolioValue) * 100;
        
        // Calculate projected annual earnings (Weekly premium * 52 weeks)
        summary.projectedAnnualEarnings = summary.totalWeeklyPremium * 52;
        
        // Calculate projected annual return as annual income divided by portfolio value
        summary.projectedAnnualReturn = (summary.projectedAnnualEarnings / totalPortfolioValue) * 100;
        
        // Log values for debugging
        console.log("Annual return calculation:", {
            annualEarnings: summary.projectedAnnualEarnings,
            portfolioValue: totalPortfolioValue,
            weeklyReturn: summary.weeklyReturn,
            annualReturn: summary.projectedAnnualReturn
        });
    } else {
        // Calculate projected annual earnings even if portfolio value is zero
        summary.projectedAnnualEarnings = summary.totalWeeklyPremium * 52;
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
    
    // Remember which tab was active before rebuilding the UI
    const putTabWasActive = document.querySelector('#put-options-tab.active') !== null ||
                           document.querySelector('#put-options-section.active') !== null;
    console.log("Put tab was active before update:", putTabWasActive);
    
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
                <button class="nav-link ${putTabWasActive ? '' : 'active'}" id="call-options-tab" data-bs-toggle="tab" data-bs-target="#call-options-section" type="button" role="tab" aria-controls="call-options-section" aria-selected="${putTabWasActive ? 'false' : 'true'}">
                    Covered Calls
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link ${putTabWasActive ? 'active' : ''}" id="put-options-tab" data-bs-toggle="tab" data-bs-target="#put-options-section" type="button" role="tab" aria-controls="put-options-section" aria-selected="${putTabWasActive ? 'true' : 'false'}">
                    Cash-Secured Puts
                </button>
            </li>
        </ul>
        
        <div class="tab-content" id="options-tabs-content">
            <div class="tab-pane fade ${putTabWasActive ? '' : 'show active'}" id="call-options-section" role="tabpanel" aria-labelledby="call-options-tab">
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
            
            <div class="tab-pane fade ${putTabWasActive ? 'show active' : ''}" id="put-options-section" role="tabpanel" aria-labelledby="put-options-tab">
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
                            data-option-type="CALL"
                            min="1" max="50" step="1" 
                            value="${tickerData.callOtmPercentage || 10}">
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
            
            // Store the current quantity in the ticker data for persistence
            if (!tickerData.putQuantity) {
                tickerData.putQuantity = recommendedQty;
            }
            const currentQty = tickerData.putQuantity;
            
            // Calculate premium
            const premiumPerContract = bid * 100; // Premium per contract (100 shares)
            const totalPremium = premiumPerContract * currentQty;
            
            // Calculate cash required
            const cashRequired = strike * 100 * currentQty;
            
            // Calculate return on cash
            const returnOnCash = cashRequired > 0 ? (totalPremium / cashRequired) * 100 : 0;
            
            // Add row to put table
            const putRow = document.createElement('tr');
            // Store row data as dataset attributes for recalculation
            putRow.dataset.ticker = ticker;
            putRow.dataset.premium = premiumPerContract;
            putRow.dataset.strike = strike;
            
            putRow.innerHTML = `
            <td>${ticker}</td>
            <td>${formatCurrency(stockPrice)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <input type="number" class="form-control form-control-sm otm-input" 
                            data-ticker="${ticker}" 
                            data-option-type="PUT"
                            min="1" max="50" step="1" 
                            value="${tickerData.putOtmPercentage || 10}">
                        <button class="btn btn-outline-secondary btn-sm refresh-otm" data-ticker="${ticker}">
                            <i class="bi bi-arrow-repeat"></i>
                        </button>
                </div>
            </td>
                <td>${formatCurrency(strike)}</td>
                <td>${expiration}</td>
                <td>${formatCurrency(bid)}</td>
                <td>${delta.toFixed(2)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <input type="number" class="form-control form-control-sm put-qty-input" 
                            data-ticker="${ticker}"
                            min="1" max="100" step="1" 
                            value="${currentQty}">
                    </div>
                </td>
                <td class="total-premium">${formatCurrency(totalPremium)}</td>
                <td class="return-on-cash">${formatPercentage(returnOnCash)}</td>
                <td class="cash-required">${formatCurrency(cashRequired)}</td>
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
    
    // Add earnings summary table after the options tables
    const earningsSummary = calculateEarningsSummary(tickersData);
    
    // Create a new, more compact earnings summary table
    const earningsSummaryHTML = `
        <div class="card shadow-sm mt-4">
            <div class="card-header d-flex justify-content-between align-items-center bg-light py-2">
                <h6 class="mb-0">Estimated Earnings Summary</h6>
            </div>
            <div class="card-body py-2">
                <table class="table table-sm table-borderless mb-0">
                    <tbody>
                        <tr>
                            <td width="14%" class="fw-bold">Weekly Premium:</td>
                            <td width="14%">Calls: ${formatCurrency(earningsSummary.totalWeeklyCallPremium)}</td>
                            <td width="14%">Puts: ${formatCurrency(earningsSummary.totalWeeklyPutPremium)}</td>
                            <td width="18%" class="fw-bold">Total: ${formatCurrency(earningsSummary.totalWeeklyPremium)}</td>
                            <td width="14%" class="fw-bold">Weekly Return:</td>
                            <td width="12%">${formatPercentage(earningsSummary.weeklyReturn)}</td>
                            <td width="14%" class="fw-bold text-success">Annual: ${formatPercentage(earningsSummary.projectedAnnualReturn)}</td>
                        </tr>
                        <tr>
                            <td class="fw-bold">Portfolio:</td>
                            <td>Stock: ${formatCurrency(earningsSummary.portfolioValue)}</td>
                            <td>Cash: ${formatCurrency(earningsSummary.cashBalance)}</td>
                            <td>CSP Requirement: ${formatCurrency(earningsSummary.totalPutExerciseCost)}</td>
                            <td class="fw-bold">Annual Income:</td>
                            <td colspan="2">${formatCurrency(earningsSummary.projectedAnnualEarnings)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div class="card-footer py-1">
                <small class="text-muted">Projected earnings assume selling the same options weekly for 52 weeks (annualized).</small>
            </div>
        </div>
    `;
    
    // Append the earnings summary to the options table container
    optionsTableContainer.insertAdjacentHTML('beforeend', earningsSummaryHTML);
    
    // Add tab event listeners via the addOptionsTableEventListeners function
    addOptionsTableEventListeners();
    
    // Add input event listeners for OTM% inputs
    addOtmInputEventListeners();
    
    // Add input event listeners for put quantity inputs
    addPutQtyInputEventListeners();
    
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
                        await refreshOptionsForTicker(ticker, true);
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
                        const optionType = otmInput.dataset.optionType || 'CALL'; // Get option type from data attribute
                        
                        // Update ticker's OTM percentage based on option type
                        if (tickersData[ticker]) {
                            if (optionType === 'CALL') {
                                tickersData[ticker].callOtmPercentage = otmPercentage;
                                console.log(`Updated ${ticker} call OTM% to ${otmPercentage}`);
                            } else {
                                tickersData[ticker].putOtmPercentage = otmPercentage;
                                console.log(`Updated ${ticker} put OTM% to ${otmPercentage}`);
                            }
                        }
                        
                        // Refresh options with the new OTM percentage
                        await refreshOptionsForTickerByType(ticker, optionType, true);
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
                            (tickersData[ticker]?.putQuantity || 1),
                        // Include additional data if available
                        bid: button.dataset.bid || 0,
                        ask: button.dataset.ask || 0,
                        last: button.dataset.last || 0,
                        delta: button.dataset.delta || 0,
                        gamma: button.dataset.gamma || 0,
                        theta: button.dataset.theta || 0,
                        vega: button.dataset.vega || 0,
                        implied_volatility: button.dataset.implied_volatility || 0
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
            
            // Handle refresh all options button click using event delegation
            if (event.target.id === 'refresh-all-options' || 
                event.target.closest('#refresh-all-options')) {
                
                const button = event.target.id === 'refresh-all-options' ? 
                               event.target : 
                               event.target.closest('#refresh-all-options');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                console.log('Refresh all options button clicked via delegation');
                button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                button.disabled = true;
                
                try {
                    await refreshAllOptions();
                } catch (error) {
                    console.error('Error refreshing all options:', error);
                } finally {
                    button.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All';
                    button.disabled = false;
                }
            }
            
            // Handle refresh all calls button click using event delegation
            if (event.target.id === 'refresh-all-calls' || 
                event.target.closest('#refresh-all-calls')) {
                
                const button = event.target.id === 'refresh-all-calls' ? 
                               event.target : 
                               event.target.closest('#refresh-all-calls');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                console.log('Refresh all calls button clicked via delegation');
                button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                button.disabled = true;
                
                try {
                    await refreshAllOptions('CALL');
                } catch (error) {
                    console.error('Error refreshing all call options:', error);
                } finally {
                    button.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All Calls';
                    button.disabled = false;
                }
            }
            
            // Handle refresh all puts button click using event delegation
            if (event.target.id === 'refresh-all-puts' || 
                event.target.closest('#refresh-all-puts')) {
                
                const button = event.target.id === 'refresh-all-puts' ? 
                               event.target : 
                               event.target.closest('#refresh-all-puts');
                
                // Prevent duplicate clicks
                if (button.disabled) {
                    console.log('Button already clicked, ignoring');
                    return;
                }
                
                console.log('Refresh all puts button clicked via delegation');
                button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                button.disabled = true;
                
                try {
                    await refreshAllOptions('PUT');
                } catch (error) {
                    console.error('Error refreshing all put options:', error);
                } finally {
                    button.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh All Puts';
                    button.disabled = false;
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
    
    // Refresh all button - REMOVED this button from UI, but keeping code with null check
    // for backward compatibility
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
            const optionType = this.dataset.optionType || 'CALL'; // Get option type from data attribute
            
            // Update ticker's OTM percentage based on option type
            if (tickersData[ticker]) {
                if (optionType === 'CALL') {
                    tickersData[ticker].callOtmPercentage = otmPercentage;
                    console.log(`Updated ${ticker} call OTM% to ${otmPercentage}`);
                } else {
                    tickersData[ticker].putOtmPercentage = otmPercentage;
                    console.log(`Updated ${ticker} put OTM% to ${otmPercentage}`);
                }
            }
        });
    });
}

/**
 * Add event listeners for put quantity inputs - these need to be added each time
 * the table is updated
 */
function addPutQtyInputEventListeners() {
    document.querySelectorAll('.put-qty-input').forEach(input => {
        input.addEventListener('change', function() {
            const ticker = this.dataset.ticker;
            const newQty = parseInt(this.value, 10);
            
            // Update ticker's putQuantity for persistence
            if (tickersData[ticker]) {
                tickersData[ticker].putQuantity = newQty;
                console.log(`Updated ${ticker} put quantity to ${newQty}`);
            }
            
            // Update the rest of the row
            const row = this.closest('tr');
            if (row) {
                const premiumPerContract = parseFloat(row.dataset.premium) || 0;
                const strike = parseFloat(row.dataset.strike) || 0;
                
                // Recalculate values
                const totalPremium = premiumPerContract * newQty;
                const cashRequired = strike * 100 * newQty;
                const returnOnCash = cashRequired > 0 ? (totalPremium / cashRequired) * 100 : 0;
                
                // Update cells
                const totalPremiumCell = row.querySelector('.total-premium');
                const returnOnCashCell = row.querySelector('.return-on-cash');
                const cashRequiredCell = row.querySelector('.cash-required');
                
                if (totalPremiumCell) totalPremiumCell.textContent = formatCurrency(totalPremium);
                if (returnOnCashCell) returnOnCashCell.textContent = formatPercentage(returnOnCash);
                if (cashRequiredCell) cashRequiredCell.textContent = formatCurrency(cashRequired);
                
                // Also update the earnings summary since total premiums changed
                updateEarningsSummary();
            }
        });
    });
}

/**
 * Update the earnings summary without rebuilding the entire table
 */
function updateEarningsSummary() {
    // Calculate earnings summary
    const earningsSummary = calculateEarningsSummary(tickersData);
    
    // Find the earnings summary section
    const summarySection = document.querySelector('.card.shadow-sm.mt-4');
    if (!summarySection) return;
    
    // Update the weekly premium values
    const weeklyCallsPremiumCell = summarySection.querySelector('td:nth-child(2)');
    const weeklyPutsPremiumCell = summarySection.querySelector('td:nth-child(3)');
    const weeklyTotalPremiumCell = summarySection.querySelector('td:nth-child(4)');
    const weeklyReturnCell = summarySection.querySelector('td:nth-child(6)');
    const annualReturnCell = summarySection.querySelector('td:nth-child(7)');
    
    // Update second row cells
    const stockValueCell = summarySection.querySelector('tr:nth-child(2) td:nth-child(2)');
    const cashBalanceCell = summarySection.querySelector('tr:nth-child(2) td:nth-child(3)');
    const cspRequirementCell = summarySection.querySelector('tr:nth-child(2) td:nth-child(4)');
    const annualIncomeCell = summarySection.querySelector('tr:nth-child(2) td:nth-child(6)');
    
    // Update the cells if found
    if (weeklyCallsPremiumCell) weeklyCallsPremiumCell.textContent = `Calls: ${formatCurrency(earningsSummary.totalWeeklyCallPremium)}`;
    if (weeklyPutsPremiumCell) weeklyPutsPremiumCell.textContent = `Puts: ${formatCurrency(earningsSummary.totalWeeklyPutPremium)}`;
    if (weeklyTotalPremiumCell) weeklyTotalPremiumCell.textContent = `Total: ${formatCurrency(earningsSummary.totalWeeklyPremium)}`;
    if (weeklyReturnCell) weeklyReturnCell.textContent = formatPercentage(earningsSummary.weeklyReturn);
    if (annualReturnCell) annualReturnCell.textContent = `Annual: ${formatPercentage(earningsSummary.projectedAnnualReturn)}`;
    
    if (stockValueCell) stockValueCell.textContent = `Stock: ${formatCurrency(earningsSummary.portfolioValue)}`;
    if (cashBalanceCell) cashBalanceCell.textContent = `Cash: ${formatCurrency(earningsSummary.cashBalance)}`;
    if (cspRequirementCell) cspRequirementCell.textContent = `CSP Requirement: ${formatCurrency(earningsSummary.totalPutExerciseCost)}`;
    if (annualIncomeCell) annualIncomeCell.textContent = formatCurrency(earningsSummary.projectedAnnualEarnings);
}

/**
 * Refresh options data for a specific ticker
 * @param {string} ticker - The ticker symbol to refresh options for
 * @param {boolean} [updateUI=false] - Whether to update the UI after refreshing
 */
async function refreshOptionsForTicker(ticker, updateUI = false) {
    try {
        // Remember which tab was active before refreshing
        const putTabWasActive = document.querySelector('#put-options-tab.active') !== null ||
                               document.querySelector('#put-options-section.active') !== null;
        console.log(`Put tab was active before refreshing ${ticker}:`, putTabWasActive);
        
        // Get OTM percentages for calls and puts
        const callOtmPercentage = tickersData[ticker]?.callOtmPercentage || 10;
        const putOtmPercentage = tickersData[ticker]?.putOtmPercentage || 10;
        
        console.log(`Refreshing options for ${ticker} with call OTM ${callOtmPercentage}% and put OTM ${putOtmPercentage}%`);
        
        // Make API call for call options
        const callOptionData = await fetchOptionData(ticker, callOtmPercentage, 'CALL');
        
        // Make API call for put options
        const putOptionData = await fetchOptionData(ticker, putOtmPercentage, 'PUT');
        
        console.log(`Call data for ${ticker}:`, callOptionData);
        console.log(`Put data for ${ticker}:`, putOptionData);
        
        // Make sure tickersData is initialized for this ticker
        if (!tickersData[ticker]) {
            tickersData[ticker] = {
                data: {
                    data: {}
                },
                callOtmPercentage: callOtmPercentage,
                putOtmPercentage: putOtmPercentage,
                putQuantity: 1
            };
            
            // Initialize the ticker data structure
            tickersData[ticker].data.data[ticker] = {
                stock_price: 0,
                position: 0,
                calls: [],
                puts: []
            };
        }
        
        // Merge call and put option data
        if (callOptionData && callOptionData.data && callOptionData.data[ticker]) {
            // Create or update ticker data
            tickersData[ticker].data = tickersData[ticker].data || { data: {} };
            tickersData[ticker].data.data = tickersData[ticker].data.data || {};
            tickersData[ticker].data.data[ticker] = tickersData[ticker].data.data[ticker] || {};
            
            // Update stock price and position
            tickersData[ticker].data.data[ticker].stock_price = callOptionData.data[ticker].stock_price || 0;
            tickersData[ticker].data.data[ticker].position = callOptionData.data[ticker].position || 0;
            
            // Update call options
            tickersData[ticker].data.data[ticker].calls = callOptionData.data[ticker].calls || [];
        }
        
        // Add put options data
        if (putOptionData && putOptionData.data && putOptionData.data[ticker]) {
            // Update put options
            tickersData[ticker].data.data[ticker].puts = putOptionData.data[ticker].puts || [];
        }
        
        console.log(`Updated data for ${ticker}:`, tickersData[ticker]);
        
        // Only update the UI if requested - we'll avoid doing this when refreshing all tickers
        // to prevent the table from being rebuilt multiple times
        if (updateUI) {
            // If the PUT tab was active before, set it back to active
            if (putTabWasActive) {
                const putTab = document.getElementById('put-options-tab');
                const putSection = document.getElementById('put-options-section');
                const callTab = document.getElementById('call-options-tab');
                const callSection = document.getElementById('call-options-section');
                
                // Manually set the PUT tab as active if it exists
                if (putTab && putSection && callTab && callSection) {
                    putTab.classList.add('active');
                    putSection.classList.add('show', 'active');
                    callTab.classList.remove('active');
                    callSection.classList.remove('show', 'active');
                }
            }
            
            // Update the UI
            updateOptionsTable();
            
            // Make sure event listeners are added
            addOptionsTableEventListeners();
        }
        
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
    if (!optionsTableContainer) {
        console.error('Options table container not found');
        return;
    }
    
    try {
        // Remember which tab was active before refreshing
        const putTabWasActive = document.querySelector('#put-options-tab.active') !== null ||
                               document.querySelector('#put-options-section.active') !== null;
        console.log("Put tab was active before refresh:", putTabWasActive);
        
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
        
        // Get the correct table and button based on optionType
        let tableId, buttonId;
        if (optionType === 'CALL') {
            tableId = 'call-options-table';
            buttonId = 'refresh-all-calls';
        } else if (optionType === 'PUT') {
            tableId = 'put-options-table';
            buttonId = 'refresh-all-puts';
        } else {
            tableId = 'call-options-table'; // Default to call table for display purposes
            buttonId = 'refresh-all-options';
        }
        
        // Process each ticker sequentially to provide visual feedback
        for (let i = 0; i < tickers.length; i++) {
            const ticker = tickers[i];
            
            // Update the button text to show progress
            const button = document.getElementById(buttonId);
            if (button) {
                const progressText = `Refreshing ${ticker} (${i+1}/${tickers.length})`;
                button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${progressText}`;
            } else if (buttonId === 'refresh-all-options') {
                // The overall refresh button has been removed from UI, use console for progress
                console.log(`Refreshing ${ticker} (${i+1}/${tickers.length})`);
            }
            
            // Find the row for this ticker to provide visual feedback
            const table = document.getElementById(tableId);
            if (table) {
                const rows = table.querySelectorAll('tbody tr');
                for (const row of rows) {
                    const tickerCell = row.querySelector('td:first-child');
                    if (tickerCell && tickerCell.textContent === ticker) {
                        // Highlight the row being refreshed
                        const originalBg = row.style.backgroundColor;
                        row.style.backgroundColor = '#f0f8ff'; // Light blue background
                        
                        // Refresh this ticker
                        if (optionType) {
                            await refreshOptionsForTickerByType(ticker, optionType);
                        } else {
                            await refreshOptionsForTicker(ticker);
                        }
                        
                        // Reset the background
                        row.style.backgroundColor = originalBg;
                        
                        // Found and processed the row, break the loop
                        break;
                    }
                }
            } else {
                // If we can't find the row, still refresh the ticker
                if (optionType) {
                    await refreshOptionsForTickerByType(ticker, optionType);
                } else {
                    await refreshOptionsForTicker(ticker);
                }
            }
            
            // Short delay to prevent UI freezing
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        
        // If we're refreshing PUT options specifically, set the PUT tab as active before updating
        if (optionType === 'PUT') {
            const putTab = document.getElementById('put-options-tab');
            const putSection = document.getElementById('put-options-section');
            const callTab = document.getElementById('call-options-tab');
            const callSection = document.getElementById('call-options-section');
            
            // Manually set the PUT tab as active if it exists
            if (putTab && putSection && callTab && callSection) {
                putTab.classList.add('active');
                putSection.classList.add('show', 'active');
                callTab.classList.remove('active');
                callSection.classList.remove('show', 'active');
            }
        } else if (putTabWasActive) {
            // If the PUT tab was active before and we're doing a general refresh, set it back to active
            const putTab = document.getElementById('put-options-tab');
            const putSection = document.getElementById('put-options-section');
            const callTab = document.getElementById('call-options-tab');
            const callSection = document.getElementById('call-options-section');
            
            // Manually set the PUT tab as active if it exists
            if (putTab && putSection && callTab && callSection) {
                putTab.classList.add('active');
                putSection.classList.add('show', 'active');
                callTab.classList.remove('active');
                callSection.classList.remove('show', 'active');
            }
        }
        
        // Final UI update after all tickers are refreshed
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
 * @param {boolean} [updateUI=false] - Whether to update the UI after refreshing
 */
async function refreshOptionsForTickerByType(ticker, optionType, updateUI = false) {
    try {
        // Get the appropriate OTM percentage based on option type
        let otmPercentage;
        if (optionType === 'CALL') {
            otmPercentage = tickersData[ticker]?.callOtmPercentage || 10;
        } else {
            otmPercentage = tickersData[ticker]?.putOtmPercentage || 10;
        }
        
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
                callOtmPercentage: optionType === 'CALL' ? otmPercentage : 10,
                putOtmPercentage: optionType === 'PUT' ? otmPercentage : 10,
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
        
        // Only update the UI if requested - we'll avoid doing this when refreshing all tickers
        // to prevent the table from being rebuilt multiple times
        if (updateUI) {
            // If this is a PUT refresh, explicitly set the PUT tab to active before updating
            if (optionType === 'PUT') {
                const putTab = document.getElementById('put-options-tab');
                const putSection = document.getElementById('put-options-section');
                const callTab = document.getElementById('call-options-tab');
                const callSection = document.getElementById('call-options-section');
                
                // Manually set the PUT tab as active if it exists
                if (putTab && putSection && callTab && callSection) {
                    putTab.classList.add('active');
                    putSection.classList.add('show', 'active');
                    callTab.classList.remove('active');
                    callSection.classList.remove('show', 'active');
                }
            }
            
            // Update the UI
            updateOptionsTable();
            
            // Make sure event listeners are added
            addOptionsTableEventListeners();
        }
        
    } catch (error) {
        console.error(`Error refreshing ${optionType} options for ${ticker}:`, error);
        showAlert(`Error refreshing ${optionType} options for ${ticker}: ${error.message}`, 'danger');
    }
}

/**
 * Fetch all tickers and their data
 */
async function loadTickers() {
    // Show a loading message first
    const optionsTableContainer = document.getElementById('options-table-container');
    if (optionsTableContainer) {
        optionsTableContainer.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading options data...</p></div>';
    }
    
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
        console.log(`Fetched ${data.tickers.length} tickers, loading their data...`);
        
        // Initialize ticker data
        data.tickers.forEach(ticker => {
            if (!tickersData[ticker]) {
                tickersData[ticker] = {
                    data: null,
                    callOtmPercentage: 10, // Default OTM percentage for calls
                    putOtmPercentage: 10, // Default OTM percentage for puts
                    putQuantity: 1 // Default put quantity
                };
            }
        });
        
        // First fetch all data for tickers - do NOT update the UI yet
        const totalTickers = data.tickers.length;
        for (let i = 0; i < totalTickers; i++) {
            const ticker = data.tickers[i];
            
            // Update loading message to show progress
            if (optionsTableContainer) {
                optionsTableContainer.innerHTML = `<div class="text-center my-4">
                    <div class="spinner-border text-primary" role="status"></div>
                    <p class="mt-2">Loading data for ${ticker} (${i+1}/${totalTickers})...</p>
                </div>`;
            }
            
            // Fetch data without updating UI
            await refreshOptionsForTicker(ticker, false);
        }
        
        // Now that all data is fetched, update the UI once
        console.log("All ticker data loaded, updating table...");
        updateOptionsTable();
        
        // Add event listeners to the options table
        addOptionsTableEventListeners();
    } else {
        console.error("Failed to fetch tickers data");
        // Show error message in the table container
        if (optionsTableContainer) {
            optionsTableContainer.innerHTML = '<div class="alert alert-danger">Failed to load tickers data. Please try refreshing the page.</div>';
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