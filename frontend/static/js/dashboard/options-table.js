/**
 * Options Table module for handling options display and interaction
 */
import { fetchOptionData, fetchTickers, saveOptionOrder } from './api.js';
import { showAlert } from '../utils/alerts.js';
import { formatCurrency, formatPercentage } from './account.js';

// Store options data
let tickersData = {};

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
        projectedAnnualReturn: 0
    };
    
    // Process each ticker to get total premium earnings
    Object.values(tickersData).forEach(tickerData => {
        if (!tickerData || !tickerData.data || !tickerData.data.data) return;
        
        // Process each ticker's option data
        Object.values(tickerData.data.data).forEach(optionData => {
            // Add portfolio value from stock positions
            const sharesOwned = optionData.position || 0;
            const stockPrice = optionData.stock_price || 0;
            summary.portfolioValue += sharesOwned * stockPrice;
            
            // Calculate max contracts based on shares owned
            const maxCallContracts = Math.floor(sharesOwned / 100);
            
            // Process call option premiums
            let callOption = null;
            if (optionData.calls && optionData.calls.length > 0) {
                callOption = optionData.calls[0];
            } else if (optionData.call) {
                callOption = optionData.call;
            }
            
            if (callOption && callOption.ask) {
                const callPremiumPerContract = callOption.ask * 100; // Premium per contract (100 shares)
                const totalCallPremium = callPremiumPerContract * maxCallContracts;
                summary.totalWeeklyCallPremium += totalCallPremium;
            }
            
            // Process put option premiums
            let putOption = null;
            if (optionData.puts && optionData.puts.length > 0) {
                putOption = optionData.puts[0];
            } else if (optionData.put) {
                putOption = optionData.put;
            }
            
            if (putOption && putOption.ask) {
                const putPremiumPerContract = putOption.ask * 100;
                const maxPutContracts = Math.floor(sharesOwned / 100);
                const totalPutPremium = putPremiumPerContract * maxPutContracts;
                summary.totalWeeklyPutPremium += totalPutPremium;
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
    
    return summary;
}

/**
 * Update options table with data
 */
function updateOptionsTable() {
    const optionsTable = document.getElementById('options-table');
    if (!optionsTable) return;
    
    // Clear the table
    optionsTable.innerHTML = '';
    
    // Get tickers
    const tickers = Object.keys(tickersData);
    
    if (tickers.length === 0) {
        optionsTable.innerHTML = '<tr><td colspan="10" class="text-center">No tickers available. Please add tickers first.</td></tr>';
        return;
    }
    
    // Process each ticker
    tickers.forEach(ticker => {
        const tickerData = tickersData[ticker];
        
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            // Add row for ticker with refresh button
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${ticker}</td>
                <td colspan="8">No data available</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary refresh-options" data-ticker="${ticker}">
                        <i class="bi bi-arrow-repeat"></i> Refresh
                    </button>
                </td>
            `;
            optionsTable.appendChild(row);
            return;
        }
        
        // We have data for this ticker
        const optionData = tickerData.data.data[ticker];
        
        // Get the stock price from optionData
        const stockPrice = optionData.stock_price || 0;
        
        // Get position information (number of shares owned)
        const sharesOwned = optionData.position || 0;
        
        // Get call option data
        let callOption = null;
        if (optionData.calls && optionData.calls.length > 0) {
            callOption = optionData.calls[0];
        } else if (optionData.call) {
            callOption = optionData.call;
        }
        
        // Get put option data
        let putOption = null;
        if (optionData.puts && optionData.puts.length > 0) {
            putOption = optionData.puts[0];
        } else if (optionData.put) {
            putOption = optionData.put;
        }
        
        // Create the row
        const row = document.createElement('tr');
        
        // Calculate OTM percentage for call
        let callOTMPercent = 0;
        if (callOption) {
            callOTMPercent = calculateOTMPercentage(callOption.strike, stockPrice);
        }
        
        // Calculate OTM percentage for put (for puts, the formula is reversed)
        let putOTMPercent = 0;
        if (putOption) {
            putOTMPercent = calculateOTMPercentage(stockPrice, putOption.strike);
        }
        
        // Format the OTM percentage for display
        const otmDisplayValue = formatPercentage(Math.max(callOTMPercent, putOTMPercent));
        
        // Get delta values for display
        const callDelta = callOption ? callOption.delta || 0 : 0;
        const putDelta = putOption ? putOption.delta || 0 : 0;
        
        // Format delta for display - we'll show both call and put deltas
        const deltaDisplay = `C: ${callDelta.toFixed(2)} / P: ${putDelta.toFixed(2)}`;
        
        // Format the call details
        const callDetails = callOption ? 
            `${callOption.expiration} $${callOption.strike}` : 
            'No call option';
        
        // Format the put details
        const putDetails = putOption ? 
            `${putOption.expiration} $${putOption.strike}` : 
            'No put option';
        
        // Calculate premium earnings based on number of shares owned
        // Each option contract is for 100 shares
        const maxCallContracts = Math.floor(sharesOwned / 100);
        const callAskPrice = callOption && callOption.ask ? callOption.ask : 0;
        const callPremiumPerContract = callAskPrice * 100; // Premium per contract (100 shares)
        const totalCallPremium = callPremiumPerContract * maxCallContracts;
        
        // Calculate put premium (cash secured puts)
        const putAskPrice = putOption && putOption.ask ? putOption.ask : 0;
        const putPremiumPerContract = putAskPrice * 100;
        // Assuming one put contract per 100 shares equivalent of cash
        const maxPutContracts = Math.floor(sharesOwned / 100);
        const totalPutPremium = putPremiumPerContract * maxPutContracts;
        
        // Format the premium prices with estimated earnings
        const callPremium = callOption && callOption.ask ? 
            `${formatCurrency(callOption.ask)} x${maxCallContracts} ${formatCurrency(totalCallPremium)}` : 
            'N/A';
        
        const putPremium = putOption && putOption.ask ? 
            `${formatCurrency(putOption.ask)} x${maxPutContracts} ${formatCurrency(totalPutPremium)}` : 
            'N/A';
        
        // Build the row HTML with OTM slider control
        row.innerHTML = `
            <td>${ticker}</td>
            <td>${formatCurrency(stockPrice)}</td>
            <td>${sharesOwned} shares</td>
            <td>
                <div class="input-group input-group-sm" style="width: 120px;">
                    <input type="range" class="form-range otm-slider" id="otm-${ticker}" 
                           min="5" max="30" step="1" value="${tickerData.otmPercentage || 10}" 
                           data-ticker="${ticker}">
                    <span class="input-group-text" id="otm-value-${ticker}">${tickerData.otmPercentage || 10}%</span>
                </div>
            </td>
            <td>${deltaDisplay}</td>
            <td>${callDetails}</td>
            <td>${callPremium}</td>
            <td>${putDetails}</td>
            <td>${putPremium}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary refresh-options" data-ticker="${ticker}">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>
                    <button class="btn btn-outline-success order-options" data-ticker="${ticker}">
                        <i class="bi bi-plus-circle"></i>
                    </button>
                </div>
            </td>
        `;
        
        // Add the row to the table
        optionsTable.appendChild(row);
    });
    
    // Add earnings summary section after the table
    const summaryData = calculateEarningsSummary(tickersData);
    
    // Create summary row with colspan to take full width
    const summaryRow = document.createElement('tr');
    summaryRow.className = 'table-dark';
    summaryRow.innerHTML = `
        <td colspan="10" class="text-center">
            <div class="d-flex justify-content-around align-items-center py-2">
                <div class="text-center">
                    <h6 class="mb-0">Weekly Premium</h6>
                    <span class="fs-5 fw-bold">${formatCurrency(summaryData.totalWeeklyPremium)}</span>
                    <div class="small text-muted">
                        <span class="text-success">Calls: ${formatCurrency(summaryData.totalWeeklyCallPremium)}</span> | 
                        <span class="text-danger">Puts: ${formatCurrency(summaryData.totalWeeklyPutPremium)}</span>
                    </div>
                </div>
                <div class="text-center">
                    <h6 class="mb-0">Projected Annual Earnings</h6>
                    <span class="fs-5 fw-bold">${formatCurrency(summaryData.projectedAnnualEarnings)}</span>
                    <div class="small text-muted">Based on 52 weeks</div>
                </div>
                <div class="text-center">
                    <h6 class="mb-0">Portfolio Value</h6>
                    <span class="fs-5 fw-bold">${formatCurrency(summaryData.portfolioValue)}</span>
                </div>
                <div class="text-center">
                    <h6 class="mb-0">Projected Annual Return</h6>
                    <span class="fs-5 fw-bold text-${summaryData.projectedAnnualReturn > 15 ? 'success' : 'primary'}">${formatPercentage(summaryData.projectedAnnualReturn)}</span>
                    <div class="small text-muted">Of portfolio value</div>
                </div>
            </div>
        </td>
    `;
    optionsTable.appendChild(summaryRow);
    
    // Add event listeners to buttons and sliders
    addOptionsTableEventListeners();
}

/**
 * Add event listeners to the options table buttons
 */
function addOptionsTableEventListeners() {
    // Add listeners to refresh buttons
    document.querySelectorAll('.refresh-options').forEach(button => {
        button.addEventListener('click', (event) => {
            const ticker = event.currentTarget.dataset.ticker;
            refreshOptionsForTicker(ticker);
        });
    });
    
    // Add listeners to order buttons
    document.querySelectorAll('.order-options').forEach(button => {
        button.addEventListener('click', (event) => {
            const ticker = event.currentTarget.dataset.ticker;
            orderOptionsForTicker(ticker);
        });
    });
    
    // Add listener to refresh all button
    const refreshAllButton = document.getElementById('refresh-all-options');
    if (refreshAllButton) {
        refreshAllButton.addEventListener('click', refreshAllOptions);
    }
    
    // Add listener to order all button
    const orderAllButton = document.getElementById('order-all-options');
    if (orderAllButton) {
        orderAllButton.addEventListener('click', orderAllOptions);
    }
    
    // Add listeners to OTM sliders
    document.querySelectorAll('.otm-slider').forEach(slider => {
        slider.addEventListener('input', function() {
            const ticker = this.getAttribute('data-ticker');
            const value = this.value;
            
            if (ticker && tickersData[ticker]) {
                // Update display and store state
                const valueElement = document.getElementById(`otm-value-${ticker}`);
                if (valueElement) {
                    valueElement.textContent = `${value}%`;
                }
                tickersData[ticker].otmPercentage = parseInt(value);
                console.log(`Updated OTM for ${ticker} to ${value}%`);
            }
        });
    });
}

/**
 * Refresh options data for a specific ticker
 * @param {string} ticker - The ticker symbol
 */
async function refreshOptionsForTicker(ticker) {
    if (!ticker) return;
    
    try {
        // Get the OTM percentage from ticker data or use default
        const otmPercentage = tickersData[ticker]?.otmPercentage || 10;
        
        // Pass the OTM percentage to the fetchOptionData function
        const data = await fetchOptionData(ticker, otmPercentage);
        
        if (data) {
            tickersData[ticker] = {
                data: data,
                timestamp: new Date().getTime(),
                otmPercentage: otmPercentage // Preserve the OTM percentage
            };
            
            updateOptionsTable();
        }
    } catch (error) {
        showAlert(`Error refreshing options for ${ticker}: ${error.message}`, 'danger');
    }
}

/**
 * Refresh all options data
 */
async function refreshAllOptions() {
    const tickers = Object.keys(tickersData);
    if (tickers.length === 0) {
        showAlert('No tickers available to refresh', 'warning');
        return;
    }
    
    showAlert('Refreshing all options data...', 'info');
    
    let successCount = 0;
    let errorCount = 0;
    
    // Process each ticker
    for (const ticker of tickers) {
        try {
            // Get the OTM percentage from ticker data or use default
            const otmPercentage = tickersData[ticker]?.otmPercentage || 10;
            
            // Pass the OTM percentage to the fetchOptionData function
            const data = await fetchOptionData(ticker, otmPercentage);
            
            if (data) {
                tickersData[ticker] = {
                    data: data,
                    timestamp: new Date().getTime(),
                    otmPercentage: otmPercentage // Preserve the OTM percentage
                };
                successCount++;
            }
        } catch (error) {
            console.error(`Error refreshing options for ${ticker}:`, error);
            errorCount++;
        }
    }
    
    updateOptionsTable();
    
    if (errorCount > 0) {
        showAlert(`Refreshed ${successCount} tickers successfully. ${errorCount} failed.`, 'warning');
    } else {
        showAlert(`All ${successCount} tickers refreshed successfully!`, 'success');
    }
}

/**
 * Order options for a specific ticker
 * @param {string} ticker - The ticker symbol
 */
async function orderOptionsForTicker(ticker) {
    if (!ticker || !tickersData[ticker] || !tickersData[ticker].data || !tickersData[ticker].data.data || !tickersData[ticker].data.data[ticker]) {
        showAlert(`No valid option data available for ${ticker}. Please refresh data first.`, 'warning');
        return;
    }
    
    const optionData = tickersData[ticker].data.data[ticker];
    console.log(`Ordering options for ${ticker}:`, optionData);
    
    // Prepare the order data for call option
    let callOption = null;
    if (optionData.calls && optionData.calls.length > 0) {
        callOption = optionData.calls[0];
    } else if (optionData.call) {
        callOption = optionData.call;
    }
    
    // Prepare the order data for put option
    let putOption = null;
    if (optionData.puts && optionData.puts.length > 0) {
        putOption = optionData.puts[0];
    } else if (optionData.put) {
        putOption = optionData.put;
    }
    
    // Check if we have valid options
    if (!callOption && !putOption) {
        showAlert(`No call or put options available for ${ticker}. Please refresh data first.`, 'warning');
        return;
    }
    
    try {
        // Save the call option order
        if (callOption) {
            const callOrderData = {
                ticker: ticker,
                option_type: 'CALL',
                strike: callOption.strike,
                expiration: callOption.expiration,
                premium: callOption.ask || 0,
                details: JSON.stringify(callOption)
            };
            
            // Save the call order
            await saveOptionOrder(callOrderData);
        }
        
        // Save the put option order
        if (putOption) {
            const putOrderData = {
                ticker: ticker,
                option_type: 'PUT',
                strike: putOption.strike,
                expiration: putOption.expiration,
                premium: putOption.ask || 0,
                details: JSON.stringify(putOption)
            };
            
            // Save the put order
            await saveOptionOrder(putOrderData);
        }
        
        showAlert(`Orders for ${ticker} saved successfully`, 'success');
        
        // Custom event to notify that orders were updated
        document.dispatchEvent(new CustomEvent('ordersUpdated'));
    } catch (error) {
        showAlert(`Error saving orders for ${ticker}: ${error.message}`, 'danger');
    }
}

/**
 * Order all available options
 */
async function orderAllOptions() {
    const tickers = Object.keys(tickersData);
    if (tickers.length === 0) {
        showAlert('No option data available. Please refresh data first.', 'warning');
        return;
    }
    
    let orderCount = 0;
    let errorCount = 0;
    
    // Process each ticker
    for (const ticker of tickers) {
        if (tickersData[ticker] && tickersData[ticker].data && tickersData[ticker].data.data && tickersData[ticker].data.data[ticker]) {
            try {
                await orderOptionsForTicker(ticker);
                orderCount++;
            } catch (error) {
                errorCount++;
                console.error(`Error ordering options for ${ticker}:`, error);
            }
        }
    }
    
    if (errorCount > 0) {
        showAlert(`Ordered options for ${orderCount} tickers. ${errorCount} failed.`, 'warning');
    } else {
        showAlert(`Ordered options for ${orderCount} tickers successfully!`, 'success');
    }
    
    // Custom event to notify that orders were updated
    document.dispatchEvent(new CustomEvent('ordersUpdated'));
}

/**
 * Fetch all tickers and their data
 */
async function loadTickers() {
    const data = await fetchTickers();
    if (data && data.tickers) {
        // Initialize ticker data
        data.tickers.forEach(ticker => {
            if (!tickersData[ticker]) {
                tickersData[ticker] = {
                    data: null,
                    timestamp: 0,
                    otmPercentage: 10 // Default OTM percentage
                };
            }
        });
        
        updateOptionsTable();
        
        // Refresh data for each ticker
        for (const ticker of data.tickers) {
            await refreshOptionsForTicker(ticker);
        }
    }
}

// Export functions
export {
    loadTickers,
    refreshOptionsForTicker,
    refreshAllOptions,
    orderOptionsForTicker,
    orderAllOptions
}; 