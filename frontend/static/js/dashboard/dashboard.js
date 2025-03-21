/**
 * Main dashboard module
 * Coordinates all dashboard components and initializes the dashboard
 */
import { loadPortfolioData, loadPositionsTable } from './account.js';
import { loadTickers } from './options-table.js';
import { loadPendingOrders } from './orders.js';
import { showAlert } from '../utils/alerts.js';
import { fetchWeeklyOptionIncome } from './api.js';
import { formatCurrency } from './account.js';

// Store weekly income data
let weeklyIncomeData = null;

/**
 * Update the weekly earnings summary card
 */
async function updateWeeklyEarningsSummary() {
    try {
        const data = await fetchWeeklyOptionIncome();
        weeklyIncomeData = data;
        
        // Update the weekly income summary card
        const weeklyIncomeSummary = document.getElementById('weekly-income-summary');
        if (weeklyIncomeSummary) {
            weeklyIncomeSummary.textContent = formatCurrency(data.total_income || 0);
        }
        
        // Update the count of positions expiring this Friday
        const weeklyPositionsCount = document.getElementById('weekly-positions-count');
        if (weeklyPositionsCount) {
            weeklyPositionsCount.textContent = data.positions_count || 0;
        }
        
        // Update the Friday date if available
        const fridayDate = document.getElementById('friday-date');
        if (fridayDate && data.this_friday) {
            fridayDate.textContent = data.this_friday;
        }
    } catch (error) {
        console.error('Error updating weekly earnings summary:', error);
    }
}

/**
 * Initialize the dashboard
 */
async function initializeDashboard() {
    try {
        console.log('Initializing dashboard...');
        
        // Create a container for alerts if it doesn't exist
        if (!document.querySelector('.content-container')) {
            const mainContainer = document.querySelector('main .container') || document.querySelector('main');
            if (mainContainer) {
                const contentContainer = document.createElement('div');
                contentContainer.className = 'content-container';
                mainContainer.prepend(contentContainer);
            }
        }
        
        // Add event listener for the refresh positions button
        const refreshPositionsButton = document.getElementById('refresh-positions');
        if (refreshPositionsButton) {
            refreshPositionsButton.addEventListener('click', async () => {
                await Promise.all([
                    loadPortfolioData(),
                    loadPositionsTable()
                ]);
                showAlert('Positions refreshed successfully', 'success');
            });
        }
        
        // Load all dashboard components in parallel
        await Promise.all([
            loadPortfolioData(),
            loadPositionsTable(),
            loadTickers(),
            loadPendingOrders(),
            updateWeeklyEarningsSummary()
        ]);
        
        console.log('Dashboard initialization complete');
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showAlert(`Error initializing dashboard: ${error.message}`, 'danger');
    }
}

// Initialize the dashboard when the DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDashboard); 