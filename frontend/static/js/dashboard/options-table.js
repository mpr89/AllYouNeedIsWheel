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
    
    // First pass: Pre-filter tickers with insufficient shares
    const eligibleTickers = tickers.filter(ticker => {
        const tickerData = tickersData[ticker];
        
        // Skip tickers without data
        if (!tickerData || !tickerData.data || !tickerData.data.data || !tickerData.data.data[ticker]) {
            return true; // Keep to show "No data available" message
        }
        
        // Check shares
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
            row.innerHTML = `
                <td>${ticker}</td>
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
        
        // Get position information (number of shares owned)
        const sharesOwned = optionData.position || 0;
        
        // Double-check shares again (shouldn't be needed due to pre-filtering, but just to be safe)
        if (sharesOwned < 100) {
            console.warn(`Ticker ${ticker} with ${sharesOwned} shares slipped through filtering!`);
            return; // Skip this ticker
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
        
        // Get the current custom put quantity if available, or calculate recommended quantity
        let putQuantity = tickerData.putQuantity || 0;
        let recommendedPutQty = 0;
        
        if (putOption) {
            // Get recommendation if no custom quantity set
            if (!putQuantity) {
                const recommendation = calculateRecommendedPutQuantity(stockPrice, putOption.strike, ticker);
                recommendedPutQty = recommendation.quantity;
                putQuantity = recommendedPutQty;
                tickerData.putQuantity = putQuantity; // Store the recommendation
            }
        } else {
            // No put option available
            putQuantity = 0;
            recommendedPutQty = 0;
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
        
        // Format the premium prices with estimated earnings
        const callPremium = callOption && callOption.ask ? 
            `${formatCurrency(callOption.ask)} x${maxCallContracts} ${formatCurrency(totalCallPremium)}` : 
            'N/A';
        
        const putPremium = putOption && putOption.ask ? 
            `${formatCurrency(putOption.ask)} x${putQuantity} ${formatCurrency(totalPutPremium)}` : 
            'N/A';
        
        // Show share count with a highlight if it's exactly enough for options
        const shareDisplay = sharesOwned === 100 ? 
            `<span class="text-success fw-bold">${sharesOwned} shares</span>` : 
            `${sharesOwned} shares`;
        
        // Create the put quantity input field with recommendation tooltip
        const putQtyInputField = `
            <div class="input-group input-group-sm" style="width: 120px;">
                <button class="btn btn-sm btn-outline-secondary decrement-put-qty" data-ticker="${ticker}">-</button>
                <input type="number" min="0" class="form-control form-control-sm text-center put-qty-input" 
                       value="${putQuantity}" data-ticker="${ticker}" data-recommended="${recommendedPutQty}"
                       ${putOption ? '' : 'disabled'}>
                <button class="btn btn-sm btn-outline-secondary increment-put-qty" data-ticker="${ticker}">+</button>
                ${recommendedPutQty > 0 ? 
                  `<button class="btn btn-sm btn-outline-info ms-1 set-recommended" 
                          data-ticker="${ticker}" data-value="${recommendedPutQty}"
                          title="Set to recommended quantity (${recommendedPutQty})">
                      <i class="bi bi-magic"></i>
                   </button>` : ''}
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
            <td>${ticker}</td>
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
    
    // Add listeners to set recommended quantity buttons
    document.querySelectorAll('.set-recommended').forEach(button => {
        button.addEventListener('click', function() {
            const ticker = this.getAttribute('data-ticker');
            const recommendedValue = parseInt(this.getAttribute('data-value')) || 0;
            const inputElement = document.querySelector(`.put-qty-input[data-ticker="${ticker}"]`);
            
            if (inputElement && recommendedValue > 0) {
                inputElement.value = recommendedValue;
                // Trigger change event
                const event = new Event('change');
                inputElement.dispatchEvent(event);
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
    
    // Get position information (number of shares owned)
    const sharesOwned = optionData.position || 0;
    
    // Calculate max call contracts based on current share position (100 shares per contract)
    const maxCallContracts = Math.floor(sharesOwned / 100);
    
    try {
        // Save the call option order
        if (callOption) {
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
            const putQuantity = tickersData[ticker].putQuantity || 0;
            
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
    
    // Fetch tickers
    const data = await fetchTickers();
    if (data && data.tickers) {
        // Initialize ticker data
        data.tickers.forEach(ticker => {
            if (!tickersData[ticker]) {
                tickersData[ticker] = {
                    data: null,
                    timestamp: 0,
                    otmPercentage: 10, // Default OTM percentage
                    putQuantity: 0 // Default put quantity
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