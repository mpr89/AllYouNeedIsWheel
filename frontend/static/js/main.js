/**
 * Auto-Trader Frontend
 * Main JavaScript file
 */

// Global utility functions

/**
 * Format a number as currency
 * @param {number|string} value - The value to format
 * @returns {string} - Formatted currency string
 */
function formatCurrency(value) {
    if (value === undefined || value === null) {
        return '$0.00';
    }
    return '$' + parseFloat(value).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

/**
 * Format a number as percentage
 * @param {number|string} value - The value to format
 * @returns {string} - Formatted percentage string
 */
function formatPercentage(value) {
    if (value === undefined || value === null) {
        return '0.00%';
    }
    const numValue = parseFloat(value);
    return (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
}

/**
 * Format a date string
 * @param {string} dateString - Date string in any valid format
 * @param {string} format - Format option ('short', 'medium', 'long')
 * @returns {string} - Formatted date string
 */
function formatDate(dateString, format = 'medium') {
    if (!dateString) return 'N/A';
    
    try {
        const date = new Date(dateString);
        
        // Check if date is valid
        if (isNaN(date.getTime())) {
            return dateString;
        }
        
        let options;
        switch (format) {
            case 'short':
                options = { month: 'numeric', day: 'numeric', year: '2-digit' };
                break;
            case 'long':
                options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
                break;
            case 'medium':
            default:
                options = { year: 'numeric', month: 'short', day: 'numeric' };
                break;
        }
        
        return date.toLocaleDateString('en-US', options);
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateString;
    }
}

/**
 * Add class to element based on value
 * @param {Element} element - DOM element to modify
 * @param {number} value - Value to evaluate
 * @param {string} positiveClass - Class to add for positive values
 * @param {string} negativeClass - Class to add for negative values
 */
function addValueClass(element, value, positiveClass = 'text-success', negativeClass = 'text-danger') {
    if (value > 0) {
        element.classList.add(positiveClass);
        element.classList.remove(negativeClass);
    } else if (value < 0) {
        element.classList.add(negativeClass);
        element.classList.remove(positiveClass);
    } else {
        element.classList.remove(positiveClass);
        element.classList.remove(negativeClass);
    }
}

/**
 * Show loading spinner
 * @param {string} targetId - ID of element to show spinner in
 * @param {string} message - Optional loading message
 */
function showLoading(targetId, message = 'Loading...') {
    const targetElement = document.getElementById(targetId);
    if (targetElement) {
        targetElement.innerHTML = `
            <div class="text-center p-3">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">${message}</p>
            </div>
        `;
    }
}

/**
 * Show error message
 * @param {string} targetId - ID of element to show error in
 * @param {string} message - Error message
 */
function showError(targetId, message = 'An error occurred. Please try again.') {
    const targetElement = document.getElementById(targetId);
    if (targetElement) {
        targetElement.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                ${message}
            </div>
        `;
    }
}

// Initialize tooltips and popovers when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Set the current year in the footer
document.addEventListener('DOMContentLoaded', function() {
    const currentYearElement = document.getElementById('current-year');
    if (currentYearElement) {
        currentYearElement.textContent = new Date().getFullYear();
    }
    
    // Add a content container for alerts if it doesn't exist
    const mainContainer = document.querySelector('main');
    if (mainContainer && !document.querySelector('.content-container')) {
        const contentContainer = document.createElement('div');
        contentContainer.className = 'content-container';
        mainContainer.prepend(contentContainer);
    }
});

// Add CustomEvent polyfill for older browsers
(function() {
    if (typeof window.CustomEvent === 'function') return false;
    
    function CustomEvent(event, params) {
        params = params || { bubbles: false, cancelable: false, detail: null };
        const evt = document.createEvent('CustomEvent');
        evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
        return evt;
    }
    
    window.CustomEvent = CustomEvent;
})();

// Add Array.from polyfill for older browsers
if (!Array.from) {
    Array.from = function(arrayLike) {
        return [].slice.call(arrayLike);
    };
}

// Add Promise polyfill for older browsers (minimal implementation)
if (!window.Promise) {
    window.Promise = function(executor) {
        this.then = function(onFulfilled) {
            this.onFulfilled = onFulfilled;
            return this;
        };
        this.catch = function(onRejected) {
            this.onRejected = onRejected;
            return this;
        };
        
        const resolve = (value) => {
            setTimeout(() => {
                if (this.onFulfilled) this.onFulfilled(value);
            }, 0);
        };
        
        const reject = (reason) => {
            setTimeout(() => {
                if (this.onRejected) this.onRejected(reason);
            }, 0);
        };
        
        executor(resolve, reject);
    };
    
    window.Promise.all = function(promises) {
        return new Promise((resolve, reject) => {
            let results = [];
            let completedCount = 0;
            
            promises.forEach((promise, index) => {
                promise.then(value => {
                    results[index] = value;
                    completedCount++;
                    
                    if (completedCount === promises.length) {
                        resolve(results);
                    }
                }).catch(reject);
            });
        });
    };
}

// Add fetch polyfill (minimal implementation, for modern browsers that don't support fetch)
if (!window.fetch) {
    console.warn('Fetch API not available. Using XMLHttpRequest polyfill. Consider updating your browser.');
    
    window.fetch = function(url, options) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open(options?.method || 'GET', url);
            
            if (options?.headers) {
                Object.keys(options.headers).forEach(key => {
                    xhr.setRequestHeader(key, options.headers[key]);
                });
            }
            
            xhr.onload = function() {
                const response = {
                    ok: xhr.status >= 200 && xhr.status < 300,
                    status: xhr.status,
                    json: function() {
                        return Promise.resolve(JSON.parse(xhr.responseText));
                    },
                    text: function() {
                        return Promise.resolve(xhr.responseText);
                    }
                };
                resolve(response);
            };
            
            xhr.onerror = function() {
                reject(new Error('Network error'));
            };
            
            xhr.send(options?.body || null);
        });
    };
} 