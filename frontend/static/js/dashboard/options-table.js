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

// Local storage key for custom tickers
const CUSTOM_TICKERS_STORAGE_KEY = 'customTickers';

/**
 * Function to get custom tickers from localStorage
 * @returns {Array} Array of custom ticker symbols
 */
function getCustomTickers() {
    const stored = localStorage.getItem(CUSTOM_TICKERS_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
}

/**
 * Function to save custom tickers to localStorage
 * @param {Array} tickers - Array of ticker symbols to save
 */
function saveCustomTickers(tickers) {
    localStorage.setItem(CUSTOM_TICKERS_STORAGE_KEY, JSON.stringify(tickers));
}

/**
 * Add a custom ticker for put options
 * @param {string} ticker - The ticker symbol to add
 */
function addCustomTicker(ticker) {
    if (!ticker) {
        showAlert('Please enter a valid ticker symbol', 'warning');
        return;
    }
    
    // Get current custom tickers
    const customTickers = getCustomTickers();
    
    // Check if ticker already exists
    if (customTickers.includes(ticker)) {
        showAlert(`${ticker} is already in your custom tickers list`, 'info');
        return;
    }
    
    // Add to custom tickers
    customTickers.push(ticker);
    saveCustomTickers(customTickers);
    
    // Add to tickersData if not already there
    if (!tickersData[ticker]) {
        tickersData[ticker] = {
            data: null,
            timestamp: 0,
            otmPercentage: 10,
            putQuantity: 1,
            isCustom: true,
            callsDisabled: true
        };
    } else {
        // Mark as custom if already exists
        tickersData[ticker].isCustom = true;
    }
    
    // Refresh the ticker data
    refreshOptionsForTicker(ticker);
    
    // Update UI
    renderCustomTickers();
    
    showAlert(`Added ${ticker} to custom tickers`, 'success');
}

/**
 * Remove a custom ticker
 * @param {string} ticker - The ticker symbol to remove
 */
function removeCustomTicker(ticker) {
    // Get current custom tickers
    const customTickers = getCustomTickers();
    
    // Remove the ticker
    const updatedTickers = customTickers.filter(t => t !== ticker);
    saveCustomTickers(updatedTickers);
    
    // Remove isCustom flag from tickersData if it exists
    if (tickersData[ticker]) {
        // Check if it exists in the portfolio before fully removing
        if (tickersData[ticker].isPortfolioTicker) {
            // Just remove the custom flag if it's also in portfolio
            tickersData[ticker].isCustom = false;
            tickersData[ticker].callsDisabled = false;
        } else {
            // Remove from tickersData if not in portfolio
            delete tickersData[ticker];
        }
    }
    
    // Update UI
    renderCustomTickers();
    updateOptionsTable();
    
    showAlert(`Removed ${ticker} from custom tickers`, 'success');
}

/**
 * Render the list of custom tickers
 */
function renderCustomTickers() {
    const customTickersList = document.getElementById('custom-tickers-list');
    if (!customTickersList) return;
    
    // Get current custom tickers
    const customTickers = getCustomTickers();
    
    // Clear current list
    customTickersList.innerHTML = '';
    
    // Add badges for each custom ticker
    customTickers.forEach(ticker => {
        const badge = document.createElement('span');
        badge.className = 'badge bg-light text-dark border d-flex align-items-center';
        badge.innerHTML = `
            ${ticker}
            <button class="btn-close ms-2" style="font-size: 0.5rem;" data-ticker="${ticker}"></button>
        `;
        customTickersList.appendChild(badge);
        
        // Add event listener to remove button
        const removeButton = badge.querySelector('.btn-close');
        removeButton.addEventListener('click', () => {
            removeCustomTicker(ticker);
        });
    });
    
    // Show a message if no custom tickers
    if (customTickers.length === 0) {
        customTickersList.innerHTML = '<span class="text-muted">No custom tickers added</span>';
    }
}

/**
 * Initialize custom ticker UI
 */
function initCustomTickerUI() {
    const addButton = document.getElementById('add-custom-ticker');
    const tickerInput = document.getElementById('custom-ticker-input');
    
    if (addButton) {
        addButton.addEventListener('click', () => {
            addCustomTicker();
        });
    }
    
    if (tickerInput) {
        tickerInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addCustomTicker();
            }
        });
    }
    
    // Initial render of custom tickers
    renderCustomTickers();
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
        if (!tickerData || !tickerData.data || !tickerData.data.data) return;
        
        // Process each ticker's option data
        Object.values(tickerData.data.data).forEach(optionData => {
            // Get position information (number of shares owned)
            const sharesOwned = optionData.position || 0;
            
            // Skip positions with less than 100 shares (minimum for 1 option contract)
            if (sharesOwned < 100) {
                return; // Skip this position in earnings calculation
            }
            
            // Add portfolio value from stock positions
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
                // Use custom put quantity if available
                const ticker = optionData.symbol || Object.keys(tickerData.data.data)[0];
                const customPutQuantity = tickerData.putQuantity || Math.floor(sharesOwned / 100);
                const totalPutPremium = putPremiumPerContract * customPutQuantity;
                summary.totalWeeklyPutPremium += totalPutPremium;
                
                // Calculate total exercise cost
                const putExerciseCost = putOption.strike * customPutQuantity * 100;
                summary.totalPutExerciseCost += putExerciseCost;
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
 * Update options table with data from stock positions
 */
function updateOptionsTable() {
    const optionsTable = document.getElementById('options-table');
    if (!optionsTable) return;
    
    // Clear the table
    optionsTable.innerHTML = '';
    
    // Get tickers
    const tickers = Object.keys(tickersData);
    
    if (tickers.length === 0) {
        optionsTable.innerHTML = '<tr><td colspan="13" class="text-center">No stock positions available. Please add stock positions first.</td></tr>';
        return;
    }
    
    console.log("Found ticker data for:", tickers.join(", "));
    
    // Keep track of tickers with sufficient shares
    let sufficientSharesCount = 0;
    let insufficientSharesCount = 0;
    let filteredTickers = [];
    let visibleTickers = [];
    let customTickersCount = 0;
    
    // First pass: Pre-filter tickers with insufficient shares (portfolio tickers only)
    const eligibleTickers = tickers.filter(ticker => {
        const tickerData = tickersData[ticker];
        
        // Skip tickers without data
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            return true; // Keep to show "No data available" message
        }
        
        // If it's a custom ticker, always include it
        if (tickerData.isCustom) {
            customTickersCount++;
            visibleTickers.push(ticker);
            return true;
        }
        
        // For portfolio tickers, check shares
        const optionData = tickerData.data.data[ticker];
        const sharesOwned = optionData.position || 0;
        
        console.log(`Ticker ${ticker} has ${sharesOwned} shares`);
        
        // Filter out positions with less than 100 shares
        if (sharesOwned < 100) {
            filteredTickers.push(ticker);
            insufficientSharesCount++;
            return false; // Remove this ticker
        }
        
        visibleTickers.push(ticker);
        sufficientSharesCount++;
        return true; // Keep this ticker
    });
    
    console.log("Filtered out tickers:", filteredTickers.join(", "));
    console.log("Visible tickers:", visibleTickers.join(", "));
    
    // If we have no positions with sufficient shares after filtering
    if (visibleTickers.length === 0) {
        optionsTable.innerHTML = '<tr><td colspan="13" class="text-center">No stock positions with at least 100 shares found. You need at least 100 shares to sell a covered call.</td></tr>';
        return;
    }
    
    // Process each eligible ticker
    eligibleTickers.forEach(ticker => {
        const tickerData = tickersData[ticker];
        
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            // Add row for ticker with refresh button
            const row = document.createElement('tr');
            
            // Use different styling for custom tickers
            if (tickerData && tickerData.isCustom) {
                row.className = 'table-info'; // Light blue background for custom tickers
            }
            
            row.innerHTML = `
                <td>${ticker}${tickerData && tickerData.isCustom ? ' <span class="badge bg-info text-white">Custom</span>' : ''}</td>
                <td colspan="11">No data available</td>
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
        
        // Handle share count differently for custom vs portfolio tickers
        let sharesOwned = 0;
        let shareDisplay = '';
        
        if (tickerData.isCustom && !tickerData.isPortfolioTicker) {
            // For custom tickers not in portfolio, show special text
            sharesOwned = 0;
            shareDisplay = '<span class="text-info">Custom (Put Only)</span>';
        } else {
            // For portfolio tickers, show actual share count
            sharesOwned = optionData.position || 0;
            
            // Double-check shares again for portfolio tickers
            if (sharesOwned < 100 && !tickerData.isCustom) {
                console.warn(`Ticker ${ticker} with ${sharesOwned} shares slipped through filtering!`);
                return; // Skip this ticker
            }
            
            shareDisplay = `${sharesOwned} shares`;
        }
        
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
        
        // Use different styling for custom tickers
        if (tickerData.isCustom && !tickerData.isPortfolioTicker) {
            row.className = 'table-info'; // Light blue background for custom tickers
        }
        
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
        
        // Handle call details differently for custom tickers
        let callDetails = 'N/A';
        let callPremium = 'N/A';
        
        if (!tickerData.callsDisabled && callOption) {
            // Format the call details for portfolio tickers
            callDetails = `${callOption.expiration} $${callOption.strike}`;
            
            // Calculate premium earnings based on number of shares owned
            // Each option contract is for 100 shares
            const maxCallContracts = Math.floor(sharesOwned / 100);
            const callAskPrice = callOption.ask || 0;
            const callPremiumPerContract = callAskPrice * 100; // Premium per contract (100 shares)
            const totalCallPremium = callPremiumPerContract * maxCallContracts;
            
            // Format the premium
            callPremium = callOption.ask ? 
                `${formatCurrency(callOption.ask)} x${maxCallContracts} ${formatCurrency(totalCallPremium)}` : 
                'N/A';
        }
        
        // Format the put details
        const putDetails = putOption ? 
            `${putOption.expiration} $${putOption.strike}` : 
            'No put option';
        
        // Calculate put premium (cash secured puts)
        const putAskPrice = putOption && putOption.ask ? putOption.ask : 0;
        const putPremiumPerContract = putAskPrice * 100;
        
        // Get the current custom put quantity if available, or set default
        let putQuantity = tickerData.putQuantity || 0;
        
        if (putOption && putQuantity === 0) {
            // For custom tickers, default to 1 if not set
            if (tickerData.isCustom) {
                putQuantity = 1;
            } else {
                // For portfolio tickers, use share count
                putQuantity = Math.floor(sharesOwned / 100);
            }
            
            // Store the value
            tickerData.putQuantity = putQuantity;
        }
        
        // Calculate total premium based on put quantity
        const totalPutPremium = putPremiumPerContract * putQuantity;
        
        // Calculate exercise cost and portfolio impact for put options
        let exerciseCost = 0;
        let portfolioImpact = 0;
        
        if (putOption && putQuantity > 0) {
            exerciseCost = putOption.strike * putQuantity * 100;
            
            // Calculate portfolio impact
            if (portfolioSummary && portfolioSummary.account_value > 0) {
                portfolioImpact = (exerciseCost / portfolioSummary.account_value) * 100;
            }
        }
        
        // Format the premium prices for puts
        const putPremium = putOption && putOption.ask ? 
            `${formatCurrency(putOption.ask)} x${putQuantity} ${formatCurrency(totalPutPremium)}` : 
            'N/A';
        
        // Create the put quantity input field without the recommendation tooltip
        const putQtyInputField = `
            <div class="input-group input-group-sm" style="width: 120px;">
                <button class="btn btn-sm btn-outline-secondary decrement-put-qty" data-ticker="${ticker}">-</button>
                <input type="number" min="0" class="form-control form-control-sm text-center put-qty-input" 
                       value="${putQuantity}" data-ticker="${ticker}"
                       ${putOption ? '' : 'disabled'}>
                <button class="btn btn-sm btn-outline-secondary increment-put-qty" data-ticker="${ticker}">+</button>
            </div>
        `;
        
        // Format exercise cost and portfolio impact display
        const exerciseCostDisplay = exerciseCost > 0 ? 
            formatCurrency(exerciseCost) : 
            'N/A';
        
        const portfolioImpactDisplay = portfolioImpact > 0 ? 
            `<span class="${portfolioImpact > 50 ? 'text-danger' : portfolioImpact > 25 ? 'text-warning' : 'text-success'}">${formatPercentage(portfolioImpact)}</span>` : 
            'N/A';
        
        // Build the row HTML with OTM slider control
        row.innerHTML = `
            <td>${ticker}${tickerData.isCustom ? ' <span class="badge bg-info text-white">Custom</span>' : ''}</td>
            <td>${formatCurrency(stockPrice)}</td>
            <td>${shareDisplay}</td>
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
            <td>${putQtyInputField}</td>
            <td>${putPremium}</td>
            <td>${exerciseCostDisplay}</td>
            <td>${portfolioImpactDisplay}</td>
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
    
    // Add a message about filtered positions if any were filtered out
    if (insufficientSharesCount > 0) {
        const noticeRow = document.createElement('tr');
        noticeRow.className = 'table-warning';
        noticeRow.innerHTML = `
            <td colspan="13" class="text-center">
                <small><i class="bi bi-info-circle"></i> ${insufficientSharesCount} position(s) with fewer than 100 shares have been hidden (${filteredTickers.join(', ')}), as they cannot be used for covered calls.</small>
            </td>
        `;
        // Insert at the top of the table
        optionsTable.insertBefore(noticeRow, optionsTable.firstChild);
    }
    
    // Add custom ticker notice if any custom tickers are present
    if (customTickersCount > 0) {
        const customRow = document.createElement('tr');
        customRow.className = 'table-info';
        customRow.innerHTML = `
            <td colspan="13" class="text-center">
                <small><i class="bi bi-info-circle"></i> Custom tickers (highlighted in blue) are for put options only and don't require owning the underlying stock.</small>
            </td>
        `;
        // Insert at the top of the table
        optionsTable.insertBefore(customRow, optionsTable.firstChild);
    }
    
    // Add earnings summary section after the table
    const summaryData = calculateEarningsSummary(tickersData);
    
    // Create summary row with colspan to take full width
    const summaryRow = document.createElement('tr');
    summaryRow.className = 'table-dark';
    summaryRow.innerHTML = `
        <td colspan="13" class="text-center">
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
                <div class="text-center">
                    <h6 class="mb-0">Total Put Exercise Cost</h6>
                    <span class="fs-5 fw-bold text-${summaryData.totalPutExerciseCost > summaryData.cashBalance ? 'danger' : 'success'}">${formatCurrency(summaryData.totalPutExerciseCost)}</span>
                    <div class="small text-muted">
                        ${formatPercentage((summaryData.totalPutExerciseCost / summaryData.cashBalance) * 100)} of cash
                    </div>
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
    
    // Add listeners to put quantity increment buttons
    document.querySelectorAll('.increment-put-qty').forEach(button => {
        button.addEventListener('click', function() {
            const ticker = this.getAttribute('data-ticker');
            const inputElement = document.querySelector(`.put-qty-input[data-ticker="${ticker}"]`);
            
            if (inputElement) {
                const currentValue = parseInt(inputElement.value) || 0;
                inputElement.value = currentValue + 1;
                // Trigger change event
                const event = new Event('change');
                inputElement.dispatchEvent(event);
            }
        });
    });
    
    // Add listeners to put quantity decrement buttons
    document.querySelectorAll('.decrement-put-qty').forEach(button => {
        button.addEventListener('click', function() {
            const ticker = this.getAttribute('data-ticker');
            const inputElement = document.querySelector(`.put-qty-input[data-ticker="${ticker}"]`);
            
            if (inputElement) {
                const currentValue = parseInt(inputElement.value) || 0;
                if (currentValue > 0) {
                    inputElement.value = currentValue - 1;
                    // Trigger change event
                    const event = new Event('change');
                    inputElement.dispatchEvent(event);
                }
            }
        });
    });
    
    // Add listeners to put quantity input fields
    document.querySelectorAll('.put-qty-input').forEach(input => {
        input.addEventListener('change', function() {
            const ticker = this.getAttribute('data-ticker');
            const value = parseInt(this.value) || 0;
            
            if (ticker && tickersData[ticker]) {
                tickersData[ticker].putQuantity = value;
                console.log(`Updated put quantity for ${ticker} to ${value}`);
                
                // Recalculate earnings and update table
                updateOptionsTable();
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
                otmPercentage: otmPercentage, // Preserve the OTM percentage
                putQuantity: tickersData[ticker]?.putQuantity || 0 // Preserve put quantity
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
    
    // Fetch portfolio data first to get latest cash balance
    try {
        portfolioSummary = await fetchAccountData();
    } catch (error) {
        console.error('Error fetching portfolio data:', error);
    }
    
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
                    otmPercentage: otmPercentage, // Preserve the OTM percentage
                    putQuantity: tickersData[ticker]?.putQuantity || 0 // Preserve put quantity
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
    
    const tickerData = tickersData[ticker];
    const optionData = tickerData.data.data[ticker];
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
        // Different handling for custom tickers vs portfolio tickers
        if (tickerData.isCustom && !tickerData.isPortfolioTicker) {
            // For custom tickers, only allow put options
            if (putOption) {
                // Get the put quantity
                const putQuantity = tickerData.putQuantity || 0;
                
                // Only create an order if the quantity is greater than 0
                if (putQuantity > 0) {
                    const putOrderData = {
                        ticker: ticker,
                        option_type: 'PUT',
                        strike: putOption.strike,
                        expiration: putOption.expiration,
                        premium: putOption.ask || 0,
                        quantity: putQuantity,
                        action: 'SELL', // Default to selling puts
                        details: JSON.stringify(putOption)
                    };
                    
                    // Save the put order
                    await saveOptionOrder(putOrderData);
                    showAlert(`Put order for ${ticker} saved successfully`, 'success');
                } else {
                    showAlert(`Please set a quantity greater than 0 for ${ticker} put options`, 'warning');
                }
            } else {
                showAlert(`No valid put option data available for ${ticker}`, 'warning');
            }
        } else {
            // Regular portfolio ticker logic
            // Get position information (number of shares owned)
            const sharesOwned = optionData.position || 0;
            
            // Calculate max call contracts based on current share position (100 shares per contract)
            const maxCallContracts = Math.floor(sharesOwned / 100);
            
            // Save the call option order
            if (callOption && !tickerData.callsDisabled) {
                // Set quantity to match current position for call options
                const callQuantity = maxCallContracts || 1; // Default to 1 if no position
                
                const callOrderData = {
                    ticker: ticker,
                    option_type: 'CALL',
                    strike: callOption.strike,
                    expiration: callOption.expiration,
                    premium: callOption.ask || 0,
                    quantity: callQuantity,
                    action: 'SELL', // Default to selling calls
                    details: JSON.stringify(callOption)
                };
                
                // Save the call order
                await saveOptionOrder(callOrderData);
            }
            
            // Save the put option order
            if (putOption) {
                // For put options, use the custom quantity we've set
                const putQuantity = tickerData.putQuantity || 0;
                
                // Only create an order if the quantity is greater than 0
                if (putQuantity > 0) {
                    const putOrderData = {
                        ticker: ticker,
                        option_type: 'PUT',
                        strike: putOption.strike,
                        expiration: putOption.expiration,
                        premium: putOption.ask || 0,
                        quantity: putQuantity,
                        action: 'SELL', // Default to selling puts
                        details: JSON.stringify(putOption)
                    };
                    
                    // Save the put order
                    await saveOptionOrder(putOrderData);
                }
            }
            
            showAlert(`Orders for ${ticker} saved successfully`, 'success');
        }
        
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
    // Fetch portfolio data first to get latest cash balance
    try {
        portfolioSummary = await fetchAccountData();
        console.log("Portfolio summary:", portfolioSummary);
    } catch (error) {
        console.error('Error fetching portfolio data:', error);
    }
    
    // Get custom tickers from localStorage
    const customTickers = getCustomTickers();
    
    // Fetch portfolio tickers
    let portfolioTickers = [];
    try {
        const data = await fetchTickers();
        if (data && data.tickers) {
            portfolioTickers = data.tickers;
        }
    } catch (error) {
        console.error('Error fetching portfolio tickers:', error);
    }
    
    // Combine portfolio and custom tickers (removing duplicates)
    const allTickers = [...new Set([...portfolioTickers, ...customTickers])];
    
    // Initialize ticker data for all tickers
    allTickers.forEach(ticker => {
        const isPortfolioTicker = portfolioTickers.includes(ticker);
        const isCustomTicker = customTickers.includes(ticker);
        
        if (!tickersData[ticker]) {
            tickersData[ticker] = {
                data: null,
                timestamp: 0,
                otmPercentage: 10, // Default OTM percentage
                putQuantity: 0, // Default put quantity
                isPortfolioTicker: isPortfolioTicker,
                isCustom: isCustomTicker,
                callsDisabled: isCustomTicker && !isPortfolioTicker
            };
        } else {
            // Update flags for existing tickers
            tickersData[ticker].isPortfolioTicker = isPortfolioTicker;
            tickersData[ticker].isCustom = isCustomTicker;
            tickersData[ticker].callsDisabled = isCustomTicker && !isPortfolioTicker;
        }
    });
    
    // Update UI
    updateOptionsTable();
    
    // Refresh data for each ticker
    for (const ticker of allTickers) {
        await refreshOptionsForTicker(ticker);
    }
}

/**
 * Initialize the custom tickers UI
 */
function initCustomTickersUI() {
    // Display existing custom tickers
    displayCustomTickers();
    
    // Modal open button
    const openModalBtn = document.getElementById('openAddTickerModalBtn');
    if (openModalBtn) {
        openModalBtn.addEventListener('click', () => {
            // Get Bootstrap modal instance
            const modal = new bootstrap.Modal(document.getElementById('addCustomTickerModal'));
            modal.show();
        });
    }
    
    // Add ticker form submission
    const addTickerForm = document.getElementById('addCustomTickerForm');
    if (addTickerForm) {
        addTickerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const tickerInput = document.getElementById('customTickerSymbol');
            const qtyInput = document.getElementById('customTickerInitialQty');
            
            const ticker = tickerInput.value.trim().toUpperCase();
            const quantity = parseInt(qtyInput.value, 10) || 1;
            
            if (ticker) {
                // Close the modal
                bootstrap.Modal.getInstance(document.getElementById('addCustomTickerModal')).hide();
                
                // Add the ticker and set initial quantity
                addCustomTicker(ticker);
                
                // Fetch options data for the new ticker
                showToast(`Fetching data for ${ticker}...`, {
                    autoHide: true,
                    delay: 3000,
                    className: 'bg-info'
                });
                
                getOptionsData([ticker])
                    .then(() => {
                        // Set the initial put quantity
                        if (tickersData[ticker]) {
                            tickersData[ticker].putQuantity = quantity;
                        }
                        
                        // Update the table with the new ticker
                        updateOptionsTable();
                        displayCustomTickers();
                        
                        showToast(`${ticker} added successfully!`, {
                            autoHide: true,
                            delay: 3000,
                            className: 'bg-success'
                        });
                    })
                    .catch(error => {
                        showAlert(`Error fetching data for ${ticker}: ${error.message}`, 'warning');
                    });
                
                // Reset the form
                tickerInput.value = '';
                qtyInput.value = '1';
            }
        });
    }
}

/**
 * Display custom tickers in the UI
 */
function displayCustomTickers() {
    const customTickersList = document.getElementById('customTickersList');
    const customTickers = getCustomTickers();
    
    // Clear the list first
    customTickersList.innerHTML = '';
    
    // Add each custom ticker as a badge with a remove button
    customTickers.forEach(ticker => {
        const tickerBadge = document.createElement('div');
        tickerBadge.className = 'badge bg-light text-dark p-2 d-flex align-items-center';
        tickerBadge.style.border = '1px solid #ddd';
        
        tickerBadge.innerHTML = `
            <span>${ticker}</span>
            <button class="btn btn-sm btn-close ms-2" style="font-size: 0.65rem;" data-ticker="${ticker}"></button>
        `;
        
        // Add click event to the remove button
        const removeBtn = tickerBadge.querySelector('.btn-close');
        removeBtn.addEventListener('click', () => {
            removeCustomTicker(ticker);
            tickerBadge.remove();
            
            // Update the options table to remove the ticker
            updateOptionsTable();
        });
        
        customTickersList.appendChild(tickerBadge);
    });
    
    // Show a message if no custom tickers
    if (customTickers.length === 0) {
        const message = document.createElement('span');
        message.className = 'text-muted fst-italic small';
        message.textContent = 'No custom tickers added yet';
        customTickersList.appendChild(message);
    }
}

/**
 * Initialize the options table functionality
 */
function initOptionsTable() {
    // Initialize the UI for custom tickers
    initCustomTickersUI();
    
    // Load tickers and options data
    loadTickers()
        .then(() => {
            updateOptionsTable();
        })
        .catch(error => {
            console.error('Error initializing options table:', error);
            showAlert('Error loading ticker data', 'danger');
        });
    
    // Event listeners for the buttons
    document.getElementById('refreshOptionsBtn').addEventListener('click', refreshOptionsData);
    document.getElementById('saveAllOptionsBtn').addEventListener('click', saveAllOptions);
    
    // Global event listener for put quantity changes
    document.body.addEventListener('putQuantityChanged', (event) => {
        const { ticker, quantity } = event.detail;
        if (ticker && tickersData[ticker]) {
            tickersData[ticker].putQuantity = quantity;
        }
    });
}

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', initOptionsTable);

// Export functions
export {
    loadTickers,
    refreshOptionsForTicker,
    refreshAllOptions,
    orderOptionsForTicker,
    orderAllOptions
};

/**
 * Save option orders for all tickers
 */
async function saveAllOptions() {
    try {
        // Get all tickers from the tickersData object
        const tickers = Object.keys(tickersData);
        
        if (tickers.length === 0) {
            showAlert('No options data available to save', 'warning');
            return;
        }
        
        // Track successful and failed orders
        let successCount = 0;
        let failedCount = 0;
        let skippedCount = 0;
        
        // Create a loading indicator
        const loadingToast = showToast('Saving option orders...', {
            autoHide: false,
            className: 'bg-info'
        });
        
        // Process each ticker
        for (const ticker of tickers) {
            try {
                const tickerData = tickersData[ticker];
                
                // Skip tickers with no data
                if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
                    skippedCount++;
                    continue;
                }
                
                // Get the options data for this ticker
                const optionData = tickerData.data.data[ticker];
                
                // Prepare call option data
                let callOption = null;
                if (optionData.calls && optionData.calls.length > 0) {
                    callOption = optionData.calls[0];
                } else if (optionData.call) {
                    callOption = optionData.call;
                }
                
                // Prepare put option data
                let putOption = null;
                if (optionData.puts && optionData.puts.length > 0) {
                    putOption = optionData.puts[0];
                } else if (optionData.put) {
                    putOption = optionData.put;
                }
                
                // Different handling for custom tickers vs portfolio tickers
                if (tickerData.isCustom && !tickerData.isPortfolioTicker) {
                    // For custom tickers, only handle put options
                    if (putOption) {
                        const putQuantity = tickerData.putQuantity || 0;
                        
                        // Only create an order if the quantity is greater than 0
                        if (putQuantity > 0) {
                            const putOrderData = {
                                ticker: ticker,
                                option_type: 'PUT',
                                strike: putOption.strike,
                                expiration: putOption.expiration,
                                premium: putOption.ask || 0,
                                quantity: putQuantity,
                                action: 'SELL',
                                details: JSON.stringify(putOption)
                            };
                            
                            // Save the put order
                            await saveOptionOrder(putOrderData);
                            successCount++;
                        } else {
                            skippedCount++;
                        }
                    } else {
                        skippedCount++;
                    }
                } else {
                    // Regular portfolio ticker logic
                    const sharesOwned = optionData.position || 0;
                    
                    // Calculate max call contracts based on current share position (100 shares per contract)
                    const maxCallContracts = Math.floor(sharesOwned / 100);
                    
                    // Process call option if not disabled and we have data
                    if (callOption && !tickerData.callsDisabled && maxCallContracts > 0) {
                        // Set quantity to match current position for call options
                        const callQuantity = maxCallContracts;
                        
                        const callOrderData = {
                            ticker: ticker,
                            option_type: 'CALL',
                            strike: callOption.strike,
                            expiration: callOption.expiration,
                            premium: callOption.ask || 0,
                            quantity: callQuantity,
                            action: 'SELL',
                            details: JSON.stringify(callOption)
                        };
                        
                        // Save the call order
                        await saveOptionOrder(callOrderData);
                        successCount++;
                    }
                    
                    // Process put option
                    if (putOption) {
                        const putQuantity = tickerData.putQuantity || 0;
                        
                        // Only create an order if the quantity is greater than 0
                        if (putQuantity > 0) {
                            const putOrderData = {
                                ticker: ticker,
                                option_type: 'PUT',
                                strike: putOption.strike,
                                expiration: putOption.expiration,
                                premium: putOption.ask || 0,
                                quantity: putQuantity,
                                action: 'SELL',
                                details: JSON.stringify(putOption)
                            };
                            
                            // Save the put order
                            await saveOptionOrder(putOrderData);
                            successCount++;
                        } else {
                            skippedCount++;
                        }
                    } else {
                        skippedCount++;
                    }
                }
            } catch (error) {
                console.error(`Error saving orders for ${ticker}:`, error);
                failedCount++;
            }
        }
        
        // Hide the loading toast
        if (loadingToast) {
            loadingToast.hide();
        }
        
        // Show summary
        let message = `Orders saved: ${successCount}`;
        if (skippedCount > 0) message += `, skipped: ${skippedCount}`;
        if (failedCount > 0) message += `, failed: ${failedCount}`;
        
        const alertType = failedCount > 0 ? 'warning' : 'success';
        showAlert(message, alertType);
        
        // Notify that orders were updated
        document.dispatchEvent(new CustomEvent('ordersUpdated'));
    } catch (error) {
        console.error('Error saving all orders:', error);
        showAlert(`Error saving all orders: ${error.message}`, 'danger');
    }
}

/**
 * Handle WebSocket messages for price updates
 * @param {Object} message - The WebSocket message data
 */
function handle_ws_message(message) {
    if (!message || !message.data) return;
    
    try {
        const data = JSON.parse(message.data);
        
        // Check if it's a market data message with ticker information
        if (data.type === 'marketData' && data.ticker) {
            const ticker = data.ticker;
            
            // Update the ticker data if we're tracking it
            if (tickersData[ticker]) {
                // Update the last price
                if (data.last) {
                    tickersData[ticker].last_price = parseFloat(data.last);
                }
                
                // Update the current data in the table
                updateTickerRow(ticker);
            }
        }
        
        // Check if it's a portfolio update or position update
        if (data.type === 'portfolioUpdate' || data.type === 'positionUpdate') {
            // Reload tickers to get the updated portfolio data
            loadTickers()
                .then(() => {
                    updateOptionsTable();
                })
                .catch(error => {
                    console.error('Error reloading ticker data after portfolio update:', error);
                });
        }
    } catch (error) {
        console.error('Error processing WebSocket message:', error);
    }
}

/**
 * Update a single ticker row in the options table
 * @param {string} ticker - The ticker symbol to update
 */
function updateTickerRow(ticker) {
    if (!tickersData[ticker]) return;
    
    const tickerRow = document.querySelector(`#optionsTable tr[data-ticker="${ticker}"]`);
    if (!tickerRow) return;
    
    const tickerData = tickersData[ticker];
    const optionData = tickerData.data?.data?.[ticker];
    if (!optionData) return;
    
    // Update the price cell
    const priceCell = tickerRow.querySelector('td:nth-child(2)');
    if (priceCell && tickerData.last_price) {
        priceCell.textContent = `$${tickerData.last_price.toFixed(2)}`;
    }
    
    // Update call premium calculation if we have call data
    const callOption = optionData.call || (optionData.calls && optionData.calls.length > 0 ? optionData.calls[0] : null);
    if (callOption) {
        const premiumCell = tickerRow.querySelector('td:nth-child(6)');
        const exercisePriceCell = tickerRow.querySelector('td:nth-child(7)');
        
        // Recalculate premium if share price changed
        const sharesOwned = optionData.position || 0;
        const maxCallContracts = Math.floor(sharesOwned / 100);
        const premium = (callOption.ask || 0) * 100 * maxCallContracts;
        
        if (premiumCell) {
            premiumCell.textContent = maxCallContracts > 0 ? `$${premium.toFixed(2)}` : 'N/A';
        }
        
        if (exercisePriceCell) {
            const exercisePrice = callOption.strike * 100 * maxCallContracts;
            exercisePriceCell.textContent = maxCallContracts > 0 ? `$${exercisePrice.toFixed(2)}` : 'N/A';
        }
    }
    
    // Update put premium calculation if we have put data
    const putOption = optionData.put || (optionData.puts && optionData.puts.length > 0 ? optionData.puts[0] : null);
    if (putOption) {
        const putQuantity = tickerData.putQuantity || 0;
        const putPremiumCell = tickerRow.querySelector('td:nth-child(11)');
        const exerciseCostCell = tickerRow.querySelector('td:nth-child(12)');
        
        if (putPremiumCell && putQuantity > 0) {
            const putPremium = (putOption.ask || 0) * 100 * putQuantity;
            putPremiumCell.textContent = `$${putPremium.toFixed(2)}`;
        }
        
        if (exerciseCostCell && putQuantity > 0) {
            const exerciseCost = putOption.strike * 100 * putQuantity;
            exerciseCostCell.textContent = `$${exerciseCost.toFixed(2)}`;
        }
    }
} 