// =========================================================
// GLOBAL INVESTMENT BUDGET (optional)
// Single source of truth: the Budget field inside the Investment
// Advisor's own card. Setting it there also sizes Portfolio
// Optimization's allocations (which reads it on demand via
// getGlobalBudget()). Leave it empty and the whole app behaves
// exactly as before.
// =========================================================
const BUDGET_STORAGE_KEY = 'marketmind_global_budget';

function getGlobalBudget() {
    const stored = localStorage.getItem(BUDGET_STORAGE_KEY);
    if (!stored) return null;
    const value = Number(stored);
    return Number.isFinite(value) && value > 0 ? value : null;
}

function formatCurrency(value) {
    return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function refreshBudgetUI() {
    const budget = getGlobalBudget();
    const indicator = document.getElementById('budgetModeIndicator');
    const advisorHint = document.getElementById('advisorBudgetSyncHint');
    const advisorBudgetField = document.getElementById('advisorBudget');

    if (budget) {
        if (indicator) {
            indicator.textContent = `BUDGET MODE · ${formatCurrency(budget)}`;
            indicator.style.display = 'inline-flex';
        }
        if (advisorHint) advisorHint.textContent = `Also used to size allocations in Portfolio Optimization (${formatCurrency(budget)}).`;
        if (advisorBudgetField && !advisorBudgetField.value) advisorBudgetField.value = budget;
    } else {
        if (indicator) indicator.style.display = 'none';
        if (advisorHint) advisorHint.textContent = 'Also used to size allocations in Portfolio Optimization.';
    }
}

// Persists the Investment Advisor's budget field as the app-wide budget.
// An empty/invalid value clears it, so simply clearing the field is how
// a user resets budget-aware sizing everywhere it's used.
function setGlobalBudget(value) {
    const numericValue = Number(value);
    if (!value || !Number.isFinite(numericValue) || numericValue <= 0) {
        localStorage.removeItem(BUDGET_STORAGE_KEY);
    } else {
        localStorage.setItem(BUDGET_STORAGE_KEY, String(numericValue));
    }
    refreshBudgetUI();
}

document.addEventListener('DOMContentLoaded', refreshBudgetUI);

// Page navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');

    document.querySelectorAll('.sidebar li').forEach(li => li.classList.remove('active'));
    if (typeof event !== 'undefined' && event && event.target && event.target.closest('li')) {
        event.target.closest('li').classList.add('active');
    }
    
    if (pageId === 'dashboard') {
        loadDashboard();
    } else if (pageId === 'portfolio') {
        loadPortfolioOptimization();
    } else if (pageId === 'futurePrediction') {
        const sectorSelect = document.getElementById('futureSectorSelect');
        const sector = sectorSelect ? sectorSelect.value : 'All';
        loadFuturePrediction(sector);
    } else if (pageId === 'multiStock') {
        initMultiStockPage();
    } else if (pageId === 'aiAdvisor') {
        initAIAdvisorPage();
    } else if (pageId === 'modelPerformance') {
        initModelPerformancePage();
    }
}

// Dashboard loading
let dashboardTrendChartInstance = null;
let dashboardComparisonChartInstance = null;

async function loadDashboard() {
    try {
        const response = await fetch('/api/dashboard');
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        document.getElementById('dashTotalStocks').textContent = data.total_stocks;
        document.getElementById('dashAverageReturn').textContent = `${Number(data.average_return).toFixed(2)}%`;
        document.getElementById('dashTopStock').textContent = data.top_stock.symbol;
        document.getElementById('dashTopStockReturn').textContent = `${data.top_stock.sector} | ${Number(data.top_stock.return_pct).toFixed(2)}%`;

        const trendCtx = document.getElementById('dashboardTrendChart').getContext('2d');
        if (dashboardTrendChartInstance) {
            dashboardTrendChartInstance.destroy();
        }
        const sectors = Array.isArray(data.sectors) && data.sectors.length ? data.sectors : ['IT', 'Banking', 'Pharma', 'FMCG'];
        const sectorPalette = {
            IT: { line: '#36a2eb', fill: 'rgba(54, 162, 235, 0.15)' },
            Banking: { line: '#ff9f40', fill: 'rgba(255, 159, 64, 0.15)' },
            Pharma: { line: '#4bc0c0', fill: 'rgba(75, 192, 192, 0.15)' },
            FMCG: { line: '#9966ff', fill: 'rgba(153, 102, 255, 0.15)' }
        };

        dashboardTrendChartInstance = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: data.trend_labels,
                datasets: sectors.map(sector => ({
                    label: sector,
                    data: (data.sector_trends && data.sector_trends[sector]) || [],
                    borderColor: sectorPalette[sector]?.line || '#667eea',
                    backgroundColor: sectorPalette[sector]?.fill || 'rgba(102, 126, 234, 0.15)',
                    fill: false,
                    tension: 0.35
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } }
            }
        });

        const comparisonCtx = document.getElementById('dashboardComparisonChart').getContext('2d');
        if (dashboardComparisonChartInstance) {
            dashboardComparisonChartInstance.destroy();
        }
        dashboardComparisonChartInstance = new Chart(comparisonCtx, {
            type: 'bar',
            data: {
                labels: sectors,
                datasets: [{
                    label: 'Average Return (%)',
                    data: sectors.map(sector => (data.sector_performance && data.sector_performance[sector]) || 0),
                    backgroundColor: sectors.map(sector => {
                        const color = sectorPalette[sector]?.line || '#667eea';
                        if (color === '#36a2eb') return 'rgba(54, 162, 235, 0.65)';
                        if (color === '#ff9f40') return 'rgba(255, 159, 64, 0.65)';
                        if (color === '#4bc0c0') return 'rgba(75, 192, 192, 0.65)';
                        if (color === '#9966ff') return 'rgba(153, 102, 255, 0.65)';
                        return 'rgba(102, 126, 234, 0.65)';
                    }),
                    borderColor: sectors.map(sector => sectorPalette[sector]?.line || '#667eea'),
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });

        loadInvestmentRecommendations();
    } catch (error) {
        console.error('Error loading dashboard:', error);
        alert('Error loading dashboard data');
    }
}

async function loadInvestmentRecommendations() {
    const chartContainer = document.getElementById('recommendationChart');
    const summaryContainer = document.getElementById('recommendationSummary');
    const listContainer = document.getElementById('recommendationList');

    if (!chartContainer || !summaryContainer || !listContainer) {
        return;
    }

    const budgetInput = document.getElementById('recommendationBudget');
    const sectorSelect = document.getElementById('recommendationSectors');
    const riskSelect = document.getElementById('recommendationRisk');

    // If the widget's own budget field is empty, fall back to the global
    // budget set in the sidebar. Leaving both empty keeps normal behavior.
    if (budgetInput && !budgetInput.value) {
        const globalBudget = getGlobalBudget();
        if (globalBudget) {
            budgetInput.value = globalBudget;
        }
    }

    const selectedSectors = Array.from(sectorSelect.selectedOptions || []).map(option => option.value);
    const payload = {
        budget: budgetInput.value ? Number(budgetInput.value) : null,
        sectors: selectedSectors,
        riskPreference: riskSelect.value
    };

    try {
        const response = await fetch('/api/investment-recommendations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.error) {
            summaryContainer.innerHTML = `<div class="recommendation-empty">${data.error}</div>`;
            listContainer.innerHTML = '';
            return;
        }

        const budgetLabel = data.budget !== null && data.budget !== undefined
            ? `${Number(data.budget).toLocaleString()}`
            : 'No budget provided';
        const topPick = data.portfolio_summary?.top_pick;
        const summaryHtml = `
            <div class="recommendation-summary-card">
                <strong>Portfolio outlook</strong>
                <p>Budget: ${budgetLabel}</p>
                <p>Expected return: ${Number(data.portfolio_summary?.expected_return_pct || 0).toFixed(2)}%</p>
                <p>Estimated volatility: ${Number(data.portfolio_summary?.volatility_pct || 0).toFixed(2)}%</p>
                <p>Top pick: ${topPick ? `${topPick.symbol} (${topPick.expected_return_pct}%)` : 'No candidates found'}</p>
            </div>
        `;
        summaryContainer.innerHTML = summaryHtml;

        const labels = data.recommendations.map(item => item.symbol);
        const returns = data.recommendations.map(item => item.expected_return_pct);
        const volatilities = data.recommendations.map(item => item.volatility_pct);

        Plotly.newPlot(chartContainer, [
            {
                type: 'bar',
                x: labels,
                y: returns,
                name: 'Expected return (%)',
                marker: { color: '#3b82f6' }
            },
            {
                type: 'bar',
                x: labels,
                y: volatilities,
                name: 'Volatility (%)',
                yaxis: 'y2',
                marker: { color: '#f59e0b' }
            }
        ], {
            barmode: 'group',
            margin: { t: 20, r: 40, b: 40, l: 40 },
            yaxis: { title: 'Expected return (%)' },
            yaxis2: { title: 'Volatility (%)', overlaying: 'y', side: 'right' }
        });

        listContainer.innerHTML = data.recommendations.map(item => `
            <div class="recommendation-item">
                <div class="recommendation-item-header">
                    <strong>${item.symbol}</strong>
                    <span>${item.sector}</span>
                </div>
                <p>Expected return: ${item.expected_return_pct}% | Volatility: ${item.volatility_pct}%</p>
                <p>VaR (95%): ${item.var_95_pct}% | Sharpe: ${item.sharpe_ratio}</p>
                <p>Risk: ${item.risk_level} | Confidence: ${item.confidence}</p>
                <p>${item.recommended_amount !== null ? `Suggested allocation: ₹${Number(item.recommended_amount).toLocaleString()} (${item.allocation_pct}%)` : 'Budget not provided; allocation shown as a score-based shortlist.'}</p>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading investment recommendations:', error);
        summaryContainer.innerHTML = '<div class="recommendation-empty">Unable to generate recommendations right now.</div>';
        listContainer.innerHTML = '';
    }
}

function parseDateInput(value) {
    const dateValue = value.trim();
    const slashMatch = dateValue.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    const dashMatch = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})$/);

    if (slashMatch) {
        const month = slashMatch[1].padStart(2, '0');
        const day = slashMatch[2].padStart(2, '0');
        const year = slashMatch[3];
        return `${year}-${month}-${day}`;
    }

    if (dashMatch) {
        return dateValue;
    }

    return null;
}

function formatStartDate(dateValue) {
    const dashMatch = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!dashMatch) {
        return dateValue;
    }

    const year = dashMatch[1];
    const month = dashMatch[2];
    const day = dashMatch[3];
    return `${month}/${day}/${year}`;
}

// Data update
async function updateData() {
    const rawDate = document.getElementById('startDate').value;
    const startDate = parseDateInput(rawDate);
    if (!startDate) {
        alert('Please enter start date in MM/DD/YYYY format');
        return;
    }
    
    try {
        const response = await fetch('/update_data', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({start_date: startDate})
        });
        const data = await response.json();
        alert(data.message || data.error);
    } catch (error) {
        console.error('Error updating data:', error);
        alert('Error updating data');
    }
}

// Sector analysis
let sectorChartInstance = null;
let monthlyReturnsChartInstance = null;

async function loadSectorAnalysis() {
    const sector = document.getElementById('sectorSelect').value;
    if (!sector) {
        alert('Please select a sector');
        return;
    }

    try {
        const response = await fetch('/analyze_sector', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sector: sector})
        });

        const text = await response.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch (parseError) {
            console.error('Sector response parse error:', parseError, text);
            alert('Error parsing sector response. See console for details.');
            return;
        }

        if (!response.ok) {
            const message = data.error || `Server error ${response.status}`;
            alert(`Sector analysis failed: ${message}`);
            return;
        }

        if (data.error) {
            alert(data.error);
            return;
        }

        const stocks = Object.keys(data.stocks || {});
        if (stocks.length === 0) {
            alert('No stock data available for this sector.');
            return;
        }

        const performances = stocks.map(stock => data.stocks[stock].performance);
        const avgPrices = stocks.map(stock => data.stocks[stock].current_price);
        const volatilities = stocks.map(stock => {
            const returns = data.stocks[stock].volatility || 0;
            return returns;
        });

        // Update summary cards
        const bestStock = stocks.reduce((a, b) => data.stocks[a].performance > data.stocks[b].performance ? a : b, stocks[0]);
        document.getElementById('bestSectorStock').textContent = `${bestStock} (${data.stocks[bestStock].performance.toFixed(2)}%)`;
        document.getElementById('sectorAvgReturn').textContent = `${data.avg_performance.toFixed(2)}%`;
        document.getElementById('sectorRiskLevel').textContent = data.risk_level || 'Unknown';
        document.getElementById('sectorAvgVolatility').textContent = (data.avg_volatility || 0).toFixed(4);

        // Create performance chart
        const ctx = document.getElementById('sectorChart').getContext('2d');
        if (sectorChartInstance) {
            sectorChartInstance.destroy();
        }

        sectorChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: stocks,
                datasets: [{
                    label: 'Return (%)',
                    data: performances,
                    backgroundColor: performances.map(p => p >= 0 ? 'rgba(75, 192, 192, 0.6)' : 'rgba(255, 99, 132, 0.6)'),
                    borderColor: performances.map(p => p >= 0 ? 'rgb(75, 192, 192)' : 'rgb(255, 99, 132)'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Return (%)'
                        }
                    }
                }
            }
        });

        // Load and create monthly returns chart
        await loadMonthlyReturnsChart(sector);

        // Populate metrics table
        const tbody = document.getElementById('sectorMetricsBody');
        tbody.innerHTML = '';
        stocks.forEach(stock => {
            const row = document.createElement('tr');
            const stockData = data.stocks[stock];
            row.innerHTML = `
                <td><strong>${stock}</strong></td>
                <td>${stockData.performance.toFixed(2)}%</td>
                <td>₹${stockData.current_price.toFixed(2)}</td>
                <td>${(stockData.volatility || 0).toFixed(4)}</td>
                <td>₹${stockData.current_price.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });

        // Update insight
        document.getElementById('sectorInsight').textContent = data.ai_insight || `${sector} sector analysis based on selected stocks.`;

        // Show results
        document.getElementById('sectorContent').style.display = 'block';
    } catch (error) {
        console.error('Error analyzing sector:', error);
        alert(`Error analyzing sector: ${error.message || error}`);
    }
}

// Load Monthly Returns Chart for specific sector
async function loadMonthlyReturnsChart(sector) {
    try {
        const response = await fetch('/get_sector_monthly_returns');
        const data = await response.json();
        
        if (!data[sector]) {
            console.error(`No data available for sector: ${sector}`);
            return;
        }

        const sectorData = data[sector];
        
        // Define colors for each sector
        const sectorColors = {
            'IT': { border: 'rgb(75, 192, 192)', bg: 'rgba(75, 192, 192, 0.2)', fill: 'rgba(75, 192, 192, 0.1)' },
            'Banking': { border: 'rgb(255, 99, 132)', bg: 'rgba(255, 99, 132, 0.2)', fill: 'rgba(255, 99, 132, 0.1)' },
            'Pharma': { border: 'rgb(54, 162, 235)', bg: 'rgba(54, 162, 235, 0.2)', fill: 'rgba(54, 162, 235, 0.1)' },
            'FMCG': { border: 'rgb(255, 206, 86)', bg: 'rgba(255, 206, 86, 0.2)', fill: 'rgba(255, 206, 86, 0.1)' }
        };
        
        const colors = sectorColors[sector] || sectorColors['IT'];
        
        // Destroy existing chart if present
        if (monthlyReturnsChartInstance) {
            monthlyReturnsChartInstance.destroy();
        }
        
        // Create new monthly returns chart
        const ctx = document.getElementById('monthlyReturnsChart').getContext('2d');
        monthlyReturnsChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: sectorData.months,
                datasets: [{
                    label: `${sector} Monthly Return (%)`,
                    data: sectorData.monthly_returns,
                    borderColor: colors.border,
                    backgroundColor: colors.bg,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: colors.border,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Return: ${context.parsed.y.toFixed(2)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.05)',
                            borderDash: [5, 5]
                        },
                        ticks: {
                            font: {
                                size: 11
                            }
                        }
                    },
                    y: {
                        grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.05)',
                            borderDash: [5, 5]
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            callback: function(value) {
                                return value.toFixed(1) + '%';
                            }
                        }
                    }
                }
            }
        });
        
    } catch (error) {
        console.error('Error loading monthly returns chart:', error);
    }
}

// Risk analysis
async function analyzeRisk() {
    const riskLevel = document.querySelector('input[name="riskLevel"]:checked').value;
    
    try {
        const response = await fetch('/risk_analysis', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({risk_level: riskLevel})
        });
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }
        
        const tbody = document.getElementById('riskTableBody');
        tbody.innerHTML = '';
        
        data.stocks.forEach(stock => {
            const row = document.createElement('tr');
            row.className = stock.risk_level.toLowerCase();
            row.innerHTML = `
                <td>${stock.stock}</td>
                <td>${stock.risk_level}</td>
                <td>${stock.expected_return}%</td>
            `;
            tbody.appendChild(row);
        });
        
        document.getElementById('riskResults').style.display = 'block';
    } catch (error) {
        console.error('Error analyzing risk:', error);
        alert('Error analyzing risk');
    }
}

// Portfolio optimization
let portfolioAllocationChartInstance = null;
let portfolioRiskReturnChartInstance = null;

async function loadPortfolioOptimization() {
    const runBtn = document.getElementById('runPortfolioBtn');
    const runStatus = document.getElementById('portfolioRunStatus');

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = 'Running...';
    }
    if (runStatus) {
        runStatus.textContent = 'Refreshing portfolio metrics...';
    }

    try {
        const globalBudget = getGlobalBudget();
        const url = globalBudget ? `/api/portfolio?budget=${encodeURIComponent(globalBudget)}` : '/api/portfolio';
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        document.getElementById('portfolioBestStock').textContent = data.best_stock.symbol;
        document.getElementById('portfolioBestAllocation').textContent = `${Number(data.best_stock.allocation_pct).toFixed(2)}%`;
        document.getElementById('portfolioBestReturn').textContent = `${Number(data.best_stock.return_pct).toFixed(2)}%`;

        document.getElementById('portfolioSafestStock').textContent = data.safest_stock.symbol;
        document.getElementById('portfolioSafestVolatility').textContent = `${Number(data.safest_stock.volatility_pct).toFixed(2)}%`;
        document.getElementById('portfolioSafestRisk').textContent = data.safest_stock.risk_category;

        const allocationCtx = document.getElementById('portfolioAllocationChart').getContext('2d');
        if (portfolioAllocationChartInstance) {
            portfolioAllocationChartInstance.destroy();
        }
        portfolioAllocationChartInstance = new Chart(allocationCtx, {
            type: 'pie',
            data: {
                labels: data.allocations.map(item => item.symbol),
                datasets: [{
                    data: data.allocations.map(item => item.allocation_pct),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.6)',
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 205, 86, 0.6)',
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(153, 102, 255, 0.6)',
                        'rgba(255, 159, 64, 0.6)',
                        'rgba(102, 187, 106, 0.6)',
                        'rgba(171, 71, 188, 0.6)',
                        'rgba(38, 198, 218, 0.6)',
                        'rgba(255, 138, 101, 0.6)',
                        'rgba(124, 179, 66, 0.6)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });

        const riskReturnCtx = document.getElementById('portfolioRiskReturnChart').getContext('2d');
        if (portfolioRiskReturnChartInstance) {
            portfolioRiskReturnChartInstance.destroy();
        }
        const riskDatasets = ['Low', 'Medium', 'High'].map(category => {
            const filtered = data.risk_return_metrics.filter(item => item.risk_category === category);
            return {
                label: `${category} Risk`,
                data: filtered.map(item => ({
                    x: item.volatility_pct,
                    y: item.return_pct
                })),
                backgroundColor: category === 'Low' ? 'rgba(40, 167, 69, 0.65)' :
                               category === 'Medium' ? 'rgba(255, 193, 7, 0.65)' :
                               'rgba(220, 53, 69, 0.65)',
                borderColor: category === 'Low' ? '#28a745' :
                             category === 'Medium' ? '#ffc107' :
                             '#dc3545',
                pointRadius: 6
            };
        });

        portfolioRiskReturnChartInstance = new Chart(riskReturnCtx, {
            type: 'scatter',
            data: { datasets: riskDatasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'Volatility (%)' } },
                    y: { title: { display: true, text: 'Return (%)' } }
                }
            }
        });

        const sharesHeader = document.getElementById('portfolioSharesHeader');
        const investedHeader = document.getElementById('portfolioInvestedHeader');
        const budgetSummaryEl = document.getElementById('portfolioBudgetSummary');
        const hasBudget = Boolean(data.budget_summary);

        if (sharesHeader) sharesHeader.style.display = hasBudget ? '' : 'none';
        if (investedHeader) investedHeader.style.display = hasBudget ? '' : 'none';

        if (budgetSummaryEl) {
            if (hasBudget) {
                budgetSummaryEl.textContent =
                    `${formatCurrency(data.budget_summary.budget)} budget → ${formatCurrency(data.budget_summary.total_deployed)} deployed, ${formatCurrency(data.budget_summary.cash_remaining)} cash left (odd lots after whole shares)`;
                budgetSummaryEl.style.display = 'inline-block';
            } else {
                budgetSummaryEl.style.display = 'none';
            }
        }

        const tableBody = document.getElementById('portfolioAllocationBody');
        tableBody.innerHTML = '';
        data.allocations.forEach(item => {
            const tr = document.createElement('tr');
            const sharesCell = hasBudget ? `<td>${item.shares ?? '-'}</td>` : '';
            const investedCell = hasBudget ? `<td>${item.invested_amount !== null && item.invested_amount !== undefined ? formatCurrency(item.invested_amount) : '-'}</td>` : '';
            tr.innerHTML = `
                <td><strong>${item.symbol}</strong></td>
                <td>${item.sector}</td>
                <td>${item.risk_category}</td>
                <td>${Number(item.return_pct).toFixed(2)}%</td>
                <td>${Number(item.volatility_pct).toFixed(2)}%</td>
                <td>${Number(item.allocation_pct).toFixed(2)}%</td>
                ${sharesCell}
                ${investedCell}
            `;
            tableBody.appendChild(tr);
        });

        document.getElementById('portfolioResults').style.display = 'block';

        if (runStatus) {
            const now = new Date();
            runStatus.textContent = `Updated at ${now.toLocaleTimeString()}`;
        }
    } catch (error) {
        console.error('Error loading portfolio optimization:', error);
        alert('Error loading portfolio data');
        if (runStatus) {
            runStatus.textContent = 'Update failed. Please try again.';
        }
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = 'Run Optimization';
        }
    }
}

// Launch Streamlit Risk Analysis Dashboard
function launchStreamlitDashboard() {
    // Open Streamlit app in a new tab/window
    // Note: Streamlit typically runs on http://localhost:8501
    window.open('http://localhost:8501', '_blank');
}

// Load Advanced Risk Analysis
let currentRiskChartData = [];
let currentRiskVizType = 'scatter';

function toFiniteNumber(value, fallback = 0) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
}

function formatPercentValue(value, decimals = 2) {
    return `${toFiniteNumber(value, 0).toFixed(decimals)}%`;
}

function formatIntegerValue(value, fallback = 0) {
    return String(Math.round(toFiniteNumber(value, fallback)));
}

function updateSectorPerformanceCard(avgReturnValue, totalStocksValue) {
    const avgReturnText = formatPercentValue(avgReturnValue, 2);
    const totalStocksText = formatIntegerValue(totalStocksValue, 0);

    const avgReturnEl = document.getElementById('avgReturn');
    const totalStocksEl = document.getElementById('totalStocks');

    if (avgReturnEl) {
        avgReturnEl.textContent = avgReturnText;
    }
    if (totalStocksEl) {
        totalStocksEl.textContent = totalStocksText;
    }

    // Fallback: if IDs are missing due stale/cached markup, render directly into card content.
    if (!avgReturnEl || !totalStocksEl) {
        const performanceCardContent = document.querySelector('.highlight-card.performance-enhanced .highlight-content');
        if (performanceCardContent) {
            performanceCardContent.innerHTML = `
                <div class="performance-metric">
                    <span class="metric-label">Avg Return:</span>
                    <span class="metric-value">${avgReturnText}</span>
                </div>
                <div class="performance-metric">
                    <span class="metric-label">Total Stocks:</span>
                    <span class="metric-value">${totalStocksText}</span>
                </div>
            `;
        }
    }
}

async function loadRiskAnalysis() {
    const sectorSelect = document.getElementById('riskSectorSelect');
    const selectedSector = sectorSelect.value;

    if (!selectedSector) {
        alert('Please select a sector first.');
        return;
    }

    try {
        const response = await fetch('/advanced_risk_analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ sector: selectedSector })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Update Enhanced KPI Cards
        document.getElementById('lowRiskCount').textContent = data.risk_counts.Low;
        document.getElementById('mediumRiskCount').textContent = data.risk_counts.Medium;
        document.getElementById('highRiskCount').textContent = data.risk_counts.High;
        document.getElementById('avgVolatility').textContent = formatPercentValue(toFiniteNumber(data.avg_volatility, 0) * 100, 1);

        // Update Sector Intelligence
        const sectorInsight = data.sector_insight;
        document.getElementById('riskProfile').textContent = sectorInsight.risk_profile.charAt(0).toUpperCase() + sectorInsight.risk_profile.slice(1);
        document.getElementById('marketOutlook').textContent = sectorInsight.outlook.charAt(0).toUpperCase() + sectorInsight.outlook.slice(1);
        document.getElementById('insightDescription').textContent = sectorInsight.insight_text;
        
        // Update sentiment indicator
        const sentimentIndicator = document.getElementById('sentimentIndicator');
        const sentimentText = document.getElementById('sentimentText');
        sentimentText.textContent = sectorInsight.sentiment.charAt(0).toUpperCase() + sectorInsight.sentiment.slice(1);
        
        if (sectorInsight.sentiment === 'bullish') {
            sentimentIndicator.style.background = '#28a745';
        } else if (sectorInsight.sentiment === 'bearish') {
            sentimentIndicator.style.background = '#dc3545';
        } else {
            sentimentIndicator.style.background = '#ffc107';
        }

        // Update Enhanced Highlights
        const safestStock = data.stock_analyses.find(s => s.symbol === data.safest_stock);
        const riskiestStock = data.stock_analyses.find(s => s.symbol === data.riskiest_stock);
        
        // Safest Stock Display
        document.getElementById('safestStock').textContent = data.safest_stock;
        if (safestStock) {
            document.getElementById('safestVolatility').textContent = (safestStock.volatility * 100).toFixed(2) + '%';
            document.getElementById('safestReturn').textContent = safestStock.total_return.toFixed(2) + '%';
        }
        
        // Riskiest Stock Display
        document.getElementById('riskiestStock').textContent = data.riskiest_stock;
        if (riskiestStock) {
            document.getElementById('riskiestVolatility').textContent = (riskiestStock.volatility * 100).toFixed(2) + '%';
            document.getElementById('riskiestReturn').textContent = riskiestStock.total_return.toFixed(2) + '%';
        }
        
        // Sector Performance Display
        updateSectorPerformanceCard(data.avg_return, data.total_stocks);

        // Update Enhanced Risk Metrics Table
        updateEnhancedRiskTable(data.table_data);

        // Create advanced 3D risk vs return chart
        currentRiskChartData = Array.isArray(data.chart_data) ? data.chart_data : [];
        createAdvancedRiskChart(currentRiskChartData, currentRiskVizType);

        // Update Predictive Insights Panel
        updatePredictiveInsights(data.stock_analyses);

        // Show the content
        document.getElementById('riskContent').style.display = 'block';

    } catch (error) {
        console.error('Error loading risk analysis:', error);
        alert('Error loading risk analysis. Please try again.');
    }
}

// Update Enhanced Risk Metrics Table with conditional formatting
function updateEnhancedRiskTable(tableData) {
    const tableBody = document.getElementById('enhancedRiskTableBody');
    tableBody.innerHTML = '';
    
    tableData.forEach(row => {
        const tr = document.createElement('tr');
        
        // Apply conditional formatting based on risk category
        const riskClass = `risk-${row.risk_category.toLowerCase()}`;
        tr.className = riskClass;
        
        // Format trend with emoji
        let trendEmoji = '';
        if (row.predictive_trend === 'bullish') trendEmoji = '📈';
        else if (row.predictive_trend === 'bearish') trendEmoji = '📉';
        else trendEmoji = '➡️';
        
        // Ensure proper risk category display
        const riskCategory = row.risk_category || 'Unknown';
        const riskClassBadge = riskCategory.toLowerCase();
        
        tr.innerHTML = `
            <td><strong>${row.stock}</strong></td>
            <td><span class="risk-badge ${riskClassBadge}">${riskCategory.toUpperCase()}</span></td>
            <td>${(row.volatility * 100).toFixed(2)}%</td>
            <td>${row.return_pct.toFixed(2)}%</td>
            <td>${row.sharpe_ratio.toFixed(3)}</td>
            <td>${row.max_drawdown.toFixed(2)}%</td>
            <td>${row.var_5.toFixed(2)}%</td>
            <td>${trendEmoji} ${row.predictive_trend.charAt(0).toUpperCase() + row.predictive_trend.slice(1)}</td>
            <td><span class="confidence-badge ${row.confidence.toLowerCase()}">${row.confidence}</span></td>
        `;
        tableBody.appendChild(tr);
    });
}

// Create Advanced 3D-style Risk vs Return Chart
function createAdvancedRiskChart(chartData, vizType = 'scatter') {
    const ctx = document.getElementById('riskReturnChart3D').getContext('2d');
    
    // Destroy existing chart if present
    if (window.advancedRiskChart) {
        window.advancedRiskChart.destroy();
    }
    
    // Group data by risk category
    const categories = ['Low', 'Medium', 'High'];
    const chartType = vizType === 'heatmap' ? 'scatter' : vizType;
    const datasets = categories.map(category => {
        const categoryData = chartData.filter(item => item.risk_category === category);
        const isHeatmap = vizType === 'heatmap';
        const isScatter = vizType === 'scatter';

        return {
            label: `${category} Risk`,
            data: categoryData.map(item => ({
                x: item.volatility,
                y: item.return_pct,
                r: isScatter ? 6 : Math.max(4, Math.sqrt(toFiniteNumber(item.avg_price, 1)) / 2),
                stock: item.stock
            })),
            backgroundColor: category === 'Low' ? 'rgba(40, 167, 69, 0.6)' : 
                           category === 'Medium' ? 'rgba(255, 193, 7, 0.6)' : 
                           'rgba(220, 53, 69, 0.6)',
            borderColor: category === 'Low' ? 'rgb(40, 167, 69)' : 
                         category === 'Medium' ? 'rgb(255, 193, 7)' : 
                         'rgb(220, 53, 69)',
            borderWidth: isHeatmap ? 0 : 2,
            hoverRadius: 8,
            hoverBorderWidth: 3,
            pointRadius: isScatter ? 6 : undefined,
            pointHoverRadius: isScatter ? 8 : undefined
        };
    });
    
    window.advancedRiskChart = new Chart(ctx, {
        type: chartType,
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const data = context.raw;
                            return [
                                `${data.stock}`,
                                `Volatility: ${(data.x * 100).toFixed(2)}%`,
                                `Return: ${data.y.toFixed(2)}%`,
                                `Bubble Size: ${data.r.toFixed(2)}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Volatility (Annualized)',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                        borderDash: [5, 5]
                    },
                    ticks: {
                        callback: function(value) {
                            return (value * 100).toFixed(1) + '%';
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Total Return (%)',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                        borderDash: [5, 5]
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '%';
                        }
                    }
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeInOutQuart'
            }
        }
    });
}

// Update Predictive Insights Panel
function updatePredictiveInsights(stockAnalyses) {
    const insightsGrid = document.getElementById('insightsGrid');
    insightsGrid.innerHTML = '';
    
    let highConfCount = 0, mediumConfCount = 0, lowConfCount = 0;
    
    stockAnalyses.forEach(analysis => {
        const insight = analysis.predictive_insight;
        const insightCard = document.createElement('div');
        insightCard.className = `insight-card ${insight.trend}`;
        
        let trendIcon = '';
        if (insight.trend === 'bullish') trendIcon = '📈';
        else if (insight.trend === 'bearish') trendIcon = '📉';
        else trendIcon = '➡️';
        
        insightCard.innerHTML = `
            <div class="insight-stock">${trendIcon} ${analysis.symbol}</div>
            <div class="insight-text">${insight.insight}</div>
            <div class="insight-confidence">Confidence: ${insight.confidence} | Predicted Move: ${insight.predicted_move.toFixed(2)}%</div>
        `;
        
        insightsGrid.appendChild(insightCard);
        
        // Count confidence levels
        if (insight.confidence === 'High') highConfCount++;
        else if (insight.confidence === 'Medium') mediumConfCount++;
        else lowConfCount++;
    });
    
    // Update confidence summary
    document.getElementById('highConfCount').textContent = highConfCount;
    document.getElementById('mediumConfCount').textContent = mediumConfCount;
    document.getElementById('lowConfCount').textContent = lowConfCount;
}

let predictionPriceChartInstance = null;
let predictionSectorChartInstance = null;
let isLoadingFuturePrediction = false;

async function loadFuturePrediction(sector) {
    if (!sector) {
        sector = 'All';
    }

    if (isLoadingFuturePrediction) {
        return; // Prevent multiple simultaneous loads
    }

    isLoadingFuturePrediction = true;

    try {
        const response = await fetch('/predict', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sector: sector})
        });
        const result = await response.json();

        if (!response.ok || result.error) {
            console.error('Prediction API error:', result.error || response.status);
            return;
        }

        const best = result.top_growth_stock || {};
        const stable = result.most_stable_stock || {};
        const sectorGrowthValue = sector === 'All'
            ? Object.values(result.sector_future_growth).reduce((sum, v) => sum + v, 0) / Math.max(Object.values(result.sector_future_growth).length, 1)
            : result.sector_future_growth[sector];

        document.getElementById('futureGrowthPct').textContent = `${sectorGrowthValue !== undefined ? sectorGrowthValue.toFixed(2) : 0.00}%`;
        document.getElementById('futureReturnPct').textContent = `${best.projected_return_pct !== undefined ? best.projected_return_pct.toFixed(2) : 0.00}%`;
        document.getElementById('futureRiskLevel').textContent = best.projected_risk_level || 'N/A';
        document.getElementById('topGrowthStock').textContent = best.symbol || '-';
        document.getElementById('topGrowthMetric').textContent = best.projected_return_pct !== undefined ? `${best.projected_return_pct.toFixed(2)}% growth` : '-';
        document.getElementById('mostStableStock').textContent = stable.symbol || '-';
        document.getElementById('stableRiskMetric').textContent = stable.predicted_volatility_pct !== undefined ? `${stable.predicted_volatility_pct.toFixed(2)}% vol` : '-';

        const predictionSection = document.getElementById('futurePredictionSection');
        if (predictionSection) {
            predictionSection.style.display = 'block';
        }

        const isAllSector = sector === 'All';
        const plotSeries = result.sector_plot || (result.predictions && result.predictions.length ? result.predictions.sort((a, b) => b.expected_growth_pct - a.expected_growth_pct)[0] : null);
        if (plotSeries) {
            createPredictionPriceChart(plotSeries, !!result.sector_plot, sector);
        }

        const sectorCard = document.getElementById('predictionSectorCard');
        if (sectorCard) {
            sectorCard.style.display = isAllSector ? 'block' : 'none';
        }

        if (isAllSector) {
            createPredictionSectorChart(result.sector_future_growth);
        } else if (predictionSectorChartInstance) {
            predictionSectorChartInstance.destroy();
            predictionSectorChartInstance = null;
        }
    } catch (error) {
        console.error('Error loading future prediction:', error);
    } finally {
        isLoadingFuturePrediction = false;
    }
}

function createPredictionPriceChart(stockPrediction, isSectorPlot = false, sector = 'All') {
    const ctx = document.getElementById('predictionPriceChart').getContext('2d');
    if (predictionPriceChartInstance) {
        predictionPriceChartInstance.destroy();
    }

    if (!stockPrediction || !stockPrediction.history || !stockPrediction.predicted || 
        stockPrediction.history.length === 0 || stockPrediction.predicted.length === 0) {
        console.warn('Invalid prediction data for chart');
        return;
    }

    const historyLabels = stockPrediction.history.map(item => item.date);
    const historyData = stockPrediction.history.map(item => item.close);
    const predictedLabels = stockPrediction.predicted.map(item => item.date);
    const predictedData = stockPrediction.predicted.map(item => item.close);

    const titlePrefix = isSectorPlot ? `${sector} Sector` : stockPrediction.symbol;
    const minPrice = Math.min(...historyData, ...predictedData);
    const maxPrice = Math.max(...historyData, ...predictedData);
    const padding = (maxPrice - minPrice) * 0.08;

    predictionPriceChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [...historyLabels, ...predictedLabels],
            datasets: [
                {
                    label: `${titlePrefix} Historical`,
                    data: [...historyData, ...Array(predictedData.length).fill(null)],
                    borderColor: '#6c5ce7',
                    backgroundColor: 'rgba(108, 92, 231, 0.25)',
                    fill: false,
                    tension: 0.35,
                    spanGaps: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#6c5ce7',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1,
                    borderWidth: 3
                },
                {
                    label: `${titlePrefix} Predicted`,
                    data: [...Array(historyData.length).fill(null), ...predictedData],
                    borderColor: '#00b894',
                    backgroundColor: 'rgba(0, 184, 148, 0.16)',
                    fill: false,
                    tension: 0.35,
                    spanGaps: true,
                    borderDash: [8, 4],
                    pointRadius: 4,
                    pointBackgroundColor: '#00b894',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1,
                    borderWidth: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 0
            },
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₹${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    title: { display: true, text: 'Date' },
                    ticks: {
                        maxTicksLimit: 10,
                        autoSkip: true,
                        sampleSize: 8
                    }
                },
                y: {
                    display: true,
                    title: { display: true, text: 'Price (₹)' },
                    min: minPrice - padding,
                    max: maxPrice + padding
                }
            }
        }
    });
}

function createPredictionSectorChart(sectorGrowth) {
    const ctx = document.getElementById('predictionSectorChart').getContext('2d');
    if (predictionSectorChartInstance) {
        predictionSectorChartInstance.destroy();
    }

    const sectors = Object.keys(sectorGrowth);
    const values = sectors.map(sec => sectorGrowth[sec]);

    predictionSectorChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sectors,
            datasets: [{
                label: 'Predicted Growth (%)',
                data: values,
                backgroundColor: sectors.map(sec => {
                    if (sec === 'IT') return 'rgba(54, 162, 235, 0.75)';
                    if (sec === 'Banking') return 'rgba(255, 159, 64, 0.75)';
                    if (sec === 'Pharma') return 'rgba(75, 192, 192, 0.75)';
                    return 'rgba(153, 102, 255, 0.75)';
                }),
                borderColor: sectors.map(sec => {
                    if (sec === 'IT') return '#36a2eb';
                    if (sec === 'Banking') return '#ff9f40';
                    if (sec === 'Pharma') return '#4bc0c0';
                    return '#9966ff';
                }),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 0
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Growth (%)' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// Additional utility functions for the enhanced dashboard
function switchRiskVisualization(type, btnElement) {
    // Update button states
    document.querySelectorAll('.viz-btn').forEach(btn => btn.classList.remove('active'));
    if (btnElement) {
        btnElement.classList.add('active');
    }

    currentRiskVizType = type;

    if (!currentRiskChartData.length) {
        return;
    }

    createAdvancedRiskChart(currentRiskChartData, type);
}

function sortTable(columnIndex) {
    const table = document.getElementById('enhancedRiskTable');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        // Handle numeric sorting
        if (columnIndex === 2 || columnIndex === 3 || columnIndex === 5 || columnIndex === 6) {
            return parseFloat(aValue) - parseFloat(bValue);
        }
        
        return aValue.localeCompare(bValue);
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

function exportRiskData() {
    // Implement export functionality
    alert('Export functionality will be implemented soon!');
}

function toggleSort() {
    // Toggle sort direction
    console.log('Toggle sort');
}

// Create Risk vs Return Scatter Chart
function createRiskReturnChart(chartData) {
    const ctx = document.getElementById('riskReturnChart').getContext('2d');

    // Group data by risk category
    const categories = ['Low', 'Medium', 'High'];
    const datasets = categories.map(category => {
        const categoryData = chartData.filter(item => item.risk_category === category);
        return {
            label: `${category} Risk`,
            data: categoryData.map(item => ({
                x: item.volatility,
                y: item.return_pct
            })),
            backgroundColor: category === 'Low' ? '#28a745' : category === 'Medium' ? '#ffc107' : '#dc3545',
            borderColor: category === 'Low' ? '#1e7e34' : category === 'Medium' ? '#e0a800' : '#bd2130',
            borderWidth: 1,
            pointRadius: categoryData.map(item => Math.sqrt(item.avg_price) / 10), // Size based on price
            pointHoverRadius: 8
        };
    });

    new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const data = chartData[context.dataIndex];
                            return `${data.stock}: Volatility ${data.volatility.toFixed(4)}, Return ${data.return_pct.toFixed(2)}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Daily Volatility'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Total Return (%)'
                    }
                }
            }
        }
    });
}

// Handle iframe loading for risk analysis page
function handleIframeLoad() {
    const iframe = document.querySelector('.streamlit-container iframe');
    const fallback = document.querySelector('.iframe-fallback');

    if (iframe && fallback) {
        iframe.addEventListener('load', function() {
            // If iframe loads successfully, hide fallback
            fallback.style.display = 'none';
        });

        iframe.addEventListener('error', function() {
            // If iframe fails to load, show fallback
            fallback.style.display = 'block';
        });

        // Check if iframe is accessible after a short delay
        setTimeout(function() {
            try {
                // Try to access iframe content to check if it's loaded
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (iframeDoc) {
                    fallback.style.display = 'none';
                }
            } catch (e) {
                // Cross-origin error, but iframe might still be loading
                // We'll assume it's working unless error event fires
            }
        }, 3000);
    }
}


// ========== STOCK PREDICTION FUNCTIONS ==========
let stockPredictionChartInstance = null;
let isLoadingStockPrediction = false;

async function loadStockPrediction() {
    const symbol = document.getElementById('stockPredictSelect').value;
    const periodDays = parseInt(document.getElementById('stockPredictPeriod').value) || 365;

    if (!symbol) {
        alert('Please select a stock');
        return;
    }

    if (isLoadingStockPrediction) {
        return;
    }

    isLoadingStockPrediction = true;
    const contentDiv = document.getElementById('stockPredictionContent');
    
    try {
        const response = await fetch('/stock-predict', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol: symbol, period_days: periodDays})
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            alert(`Error: ${data.error || 'Failed to generate prediction'}`);
            return;
        }

        // Update KPI Cards
        const growthPercent = data.projected_return_pct || 0;
        const growthLabel = growthPercent > 0 ? 'Positive outlook' : growthPercent < 0 ? 'Negative outlook' : 'Neutral';
        
        document.getElementById('stockPredGrowth').textContent = `${growthPercent.toFixed(2)}%`;
        document.getElementById('stockPredGrowthLabel').textContent = growthLabel;

        const trendText = data.trend === 'bullish' ? '📈 Bullish'
            : data.trend === 'sideways' ? '➡️ Sideways'
            : '📉 Bearish';
        const trendLabel = data.trend === 'bullish' ? 'Upward trend'
            : data.trend === 'sideways' ? 'Stable / range-bound'
            : 'Downward trend';
        
        document.getElementById('stockPredTrend').textContent = trendText;
        document.getElementById('stockPredTrendLabel').textContent = trendLabel;

        const confidenceColor = data.confidence === 'High' ? '#28a745' : 
                              data.confidence === 'Medium' ? '#ffc107' : '#dc3545';
        
        document.getElementById('stockPredConfidence').textContent = data.confidence;
        document.querySelector('.confidence-card').style.borderTopColor = confidenceColor;

        document.getElementById('stockPredTarget').textContent = `₹${data.projected_price.toFixed(2)}`;
        document.getElementById('stockPredTargetLabel').textContent = `from ₹${data.latest_price.toFixed(2)}`;

        // Update Detail Cards
        document.getElementById('stockCurrentPrice').textContent = `₹${data.latest_price.toFixed(2)}`;
        document.getElementById('stockVolatility').textContent = `${data.predicted_volatility_pct.toFixed(2)}%`;
        document.getElementById('stockRiskLevel').textContent = data.projected_risk_level;
        
        document.getElementById('stockProjectedPrice').textContent = `₹${data.projected_price.toFixed(2)}`;
        document.getElementById('stockExpectedReturn').textContent = `${data.expected_growth_pct.toFixed(2)}%`;
        document.getElementById('stockModelR2').textContent = data.model_fit.r_squared.toFixed(4);

        // Create prediction chart
        createStockPredictionChart(data);

        // Show content
        contentDiv.style.display = 'block';

    } catch (error) {
        console.error('Error loading stock prediction:', error);
        alert(`Error: ${error.message}`);
    } finally {
        isLoadingStockPrediction = false;
    }
}

function createStockPredictionChart(data) {
    const ctx = document.getElementById('stockPredictionChart').getContext('2d');
    
    if (stockPredictionChartInstance) {
        stockPredictionChartInstance.destroy();
    }

    const historyLabels = data.history.map(item => item.date);
    const historyData = data.history.map(item => item.close);
    const predictedLabels = data.predicted.map(item => item.date);
    const predictedData = data.predicted.map(item => item.close);

    const minPrice = Math.min(...historyData, ...predictedData);
    const maxPrice = Math.max(...historyData, ...predictedData);
    const padding = (maxPrice - minPrice) * 0.1;

    stockPredictionChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [...historyLabels, ...predictedLabels],
            datasets: [
                {
                    label: `${data.symbol} - Historical Price`,
                    data: [...historyData, ...Array(predictedData.length).fill(null)],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: false,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    borderWidth: 3,
                    spanGaps: true
                },
                {
                    label: `${data.symbol} - Predicted Price`,
                    data: [...Array(historyData.length).fill(null), ...predictedData],
                    borderColor: '#00b894',
                    backgroundColor: 'rgba(0, 184, 148, 0.1)',
                    fill: false,
                    tension: 0.4,
                    borderDash: [8, 4],
                    pointRadius: 5,
                    pointBackgroundColor: '#00b894',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    borderWidth: 3,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₹${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date',
                        font: { size: 12, weight: 'bold' }
                    },
                    ticks: {
                        maxTicksLimit: 8,
                        autoSkip: true
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Price (₹)',
                        font: { size: 12, weight: 'bold' }
                    },
                    min: minPrice - padding,
                    max: maxPrice + padding,
                    ticks: {
                        callback: function(value) {
                            return '₹' + value.toFixed(0);
                        }
                    }
                }
            },
            animation: {
                duration: 800,
                easing: 'easeInOutQuart'
            }
        }
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadDashboard();
    handleIframeLoad();
});

// =============================================================================
// MULTI-STOCK ANALYSIS MODULE (independent from Sector Analysis)
// Self-contained: does not read/write any Sector Analysis DOM elements or state.
// =============================================================================

let multiStockInitialized = false;
let multiStockData = [];
let multiStockChartType = 'line';   // 'line' | 'pie'
let multiStockMetric = 'market_value'; // current metric for the pie view
let multiStockLastCharts = null;         // cached OHLC/series payload from last successful fetch
let multiStockLastComparisonTable = null; // cached comparison-table rows from last successful fetch

const MULTI_STOCK_COLORS = [
    '#ff9f0a', '#33b1e8', '#24d17a', '#ff4d5e', '#c792ea',
    '#f5d76e', '#7ee787', '#ff8fab', '#89ddff', '#ffb86c',
    '#a78bfa', '#4dd0e1', '#ffd54f', '#ef9a9a', '#80cbc4'
];

// Pie Chart metric definitions -- proportional comparison across the selected
// stocks. All values are derived from the same comparison_table rows; nothing
// here alters backend calculations, it only reshapes already-computed figures
// into a share-of-whole view.
const MULTI_STOCK_PIE_METRICS = {
    market_value: {
        label: 'Portfolio Allocation (Market Value)',
        getValue: r => (r.latest_close || 0) * (r.avg_volume || 0)
    },
    return_contribution: {
        label: 'Return Contribution',
        getValue: r => Math.abs(r.return_pct || 0),
        note: 'Shown as share of total absolute return magnitude (negative returns cannot be sliced on a pie chart).'
    },
    volume_share: {
        label: 'Trading Volume Share',
        getValue: r => r.avg_volume || 0
    },
    volatility_share: {
        label: 'Volatility Share',
        getValue: r => r.volatility_pct || 0
    }
};

const MULTI_STOCK_SECTION_TITLES = {
    line: 'Historical &amp; Predicted Price Trend',
    pie: 'Proportional Stock Comparison'
};

function initMultiStockPage() {
    if (multiStockInitialized) {
        loadMultiStockList();
        return;
    }
    multiStockInitialized = true;

    const today = new Date();
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(today.getMonth() - 6);
    document.getElementById('multiStockEndDate').value = today.toISOString().split('T')[0];
    document.getElementById('multiStockStartDate').value = sixMonthsAgo.toISOString().split('T')[0];

    document.getElementById('multiStockStartDate').addEventListener('change', onMultiStockSelectionChange);
    document.getElementById('multiStockEndDate').addEventListener('change', onMultiStockSelectionChange);

    document.getElementById('multiStockSelectAll').addEventListener('click', () => {
        document.querySelectorAll('.multi-stock-checkbox').forEach(cb => { cb.checked = true; });
        onMultiStockSelectionChange();
    });
    document.getElementById('multiStockClearAll').addEventListener('click', () => {
        document.querySelectorAll('.multi-stock-checkbox').forEach(cb => { cb.checked = false; });
        onMultiStockSelectionChange();
    });

    // Chart selector: Line Graph / Pie Chart
    document.querySelectorAll('#multiStockVizToggle button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#multiStockVizToggle button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            multiStockChartType = btn.dataset.vizType;
            onMultiStockChartTypeChange();
        });
    });

    document.getElementById('multiStockMetricSelect').addEventListener('change', (e) => {
        multiStockMetric = e.target.value;
        renderMultiStockVisualization();
    });

    loadMultiStockList();
}

function onMultiStockChartTypeChange() {
    const metricRow = document.getElementById('multiStockMetricRow');
    const metricSelect = document.getElementById('multiStockMetricSelect');
    const titleEl = document.getElementById('multiStockChartSectionTitle');
    titleEl.innerHTML = MULTI_STOCK_SECTION_TITLES[multiStockChartType];

    if (multiStockChartType === 'line') {
        metricRow.style.display = 'none';
    } else {
        const defaultMetric = 'market_value';
        metricSelect.innerHTML = Object.keys(MULTI_STOCK_PIE_METRICS)
            .map(key => `<option value="${key}">${MULTI_STOCK_PIE_METRICS[key].label}</option>`).join('');
        multiStockMetric = defaultMetric;
        metricSelect.value = defaultMetric;
        metricRow.style.display = 'flex';
    }

    renderMultiStockVisualization();
}

function loadMultiStockList() {
    const tbody = document.getElementById('multiStockTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="multi-stock-loading">Loading live quotes…</td></tr>';

    fetch('/api/multi-stock/list')
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                tbody.innerHTML = `<tr><td colspan="5">Error: ${data.error}</td></tr>`;
                return;
            }
            multiStockData = data.stocks || [];
            renderMultiStockTable();
        })
        .catch(() => {
            tbody.innerHTML = '<tr><td colspan="5">Failed to load stock list. Check your connection and try again.</td></tr>';
        });
}

function renderMultiStockTable() {
    const tbody = document.getElementById('multiStockTableBody');
    const previouslySelected = getSelectedMultiStockSymbols();

    // All 15 stocks (IT + Banking + Pharma + FMCG) are always shown on a single page;
    // there is no sector filter or symbol search to narrow this list.
    const rows = multiStockData;

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No stock data available.</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(s => {
        const checked = previouslySelected.includes(s.full_symbol) ? 'checked' : '';
        const changeClass = (s.change_pct == null) ? '' : (s.change_pct >= 0 ? 'positive' : 'negative');
        const priceDisplay = s.price != null ? `₹${s.price.toFixed(2)}` : '—';
        const changeDisplay = s.change_pct != null ? `${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(2)}%` : '—';
        return `
            <tr>
                <td><input type="checkbox" class="multi-stock-checkbox" value="${s.full_symbol}" ${checked} onchange="onMultiStockSelectionChange()"></td>
                <td>${s.symbol}</td>
                <td><span class="multi-stock-sector-tag">${s.sector}</span></td>
                <td>${priceDisplay}</td>
                <td class="${changeClass}">${changeDisplay}</td>
            </tr>`;
    }).join('');
}

function getSelectedMultiStockSymbols() {
    return Array.from(document.querySelectorAll('.multi-stock-checkbox:checked')).map(cb => cb.value);
}

function onMultiStockSelectionChange() {
    const selected = getSelectedMultiStockSymbols();
    const resultsEl = document.getElementById('multiStockResults');
    const emptyStateEl = document.getElementById('multiStockEmptyState');

    if (selected.length < 2) {
        resultsEl.style.display = 'none';
        emptyStateEl.style.display = 'block';
        emptyStateEl.textContent = selected.length === 0
            ? 'Select two or more stocks above (any sector combination) to view comparison charts and the metrics table.'
            : 'Select at least one more stock to run a comparison.';
        return;
    }
    emptyStateEl.style.display = 'none';
    resultsEl.style.display = 'block';
    loadMultiStockComparison(selected);
}

function loadMultiStockComparison(selectedSymbols) {
    const selected = selectedSymbols || getSelectedMultiStockSymbols();
    if (selected.length === 0) return;

    const startDate = document.getElementById('multiStockStartDate').value;
    const endDate = document.getElementById('multiStockEndDate').value;

    document.getElementById('multiStockChart').innerHTML = '<div class="multi-stock-loading">Loading chart…</div>';
    document.getElementById('multiStockComparisonTable').innerHTML = '<div class="multi-stock-loading">Crunching metrics…</div>';

    fetch('/api/multi-stock/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbols: selected,
            start_date: startDate,
            end_date: endDate,
            // Backend always returns the full series + metrics regardless of this
            // value (candlestick/bar options have been removed from the UI), so
            // 'line' is used as the request shape for both the Line and Pie views.
            chart_type: 'line'
        })
    })
        .then(res => res.json())
        .then(data => {
            if (data.error && !data.comparison_table) {
                document.getElementById('multiStockChart').innerHTML = `<div class="multi-stock-error">${data.error}</div>`;
                document.getElementById('multiStockComparisonTable').innerHTML = '';
                multiStockLastCharts = null;
                multiStockLastComparisonTable = null;
                return;
            }
            multiStockLastCharts = data.charts;
            multiStockLastComparisonTable = data.comparison_table;
            renderMultiStockVisualization();
            renderMultiStockComparisonTable(data.comparison_table, data.unavailable);
        })
        .catch(() => {
            document.getElementById('multiStockChart').innerHTML = '<div class="multi-stock-error">Failed to load comparison data.</div>';
        });
}

// Single dispatcher for the chart selector: renders whichever of the three
// visualization types (Line Graph, Pie Chart) is currently active,
// using the most recently fetched charts/comparison-table data. This lets the
// metric dropdown and the chart-type buttons both re-render instantly without
// re-fetching from the backend.
function renderMultiStockVisualization() {
    const container = document.getElementById('multiStockChart');
    if (!multiStockLastCharts || !multiStockLastComparisonTable) {
        return;
    }

    if (multiStockChartType === 'line') {
        renderMultiStockLineChart(multiStockLastCharts, multiStockLastComparisonTable);
    } else if (multiStockChartType === 'pie') {
        renderMultiStockPieChart(multiStockLastComparisonTable, multiStockMetric);
    }
}

const MULTI_STOCK_LAYOUT_BASE = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#cdd6e0' },
    margin: { t: 30, r: 20, l: 50, b: 40 },
    legend: { orientation: 'h', y: -0.2 },
    xaxis: { gridcolor: '#1d2530' },
    yaxis: { gridcolor: '#1d2530' }
};

// Line Graph: historical closing price plus a dashed forecast segment per
// stock when a trend-based predicted price is available for it.
function renderMultiStockLineChart(charts, comparisonTable) {
    if (!charts || charts.length === 0) {
        document.getElementById('multiStockChart').innerHTML = '<div class="multi-stock-error">No chart data available.</div>';
        return;
    }

    const predictionBySymbol = {};
    (comparisonTable || []).forEach(r => { predictionBySymbol[r.symbol] = r.prediction; });

    const traces = [];
    charts.forEach((c, i) => {
        const color = MULTI_STOCK_COLORS[i % MULTI_STOCK_COLORS.length];
        traces.push({
            type: 'scatter',
            mode: 'lines',
            name: c.symbol,
            x: c.dates,
            y: c.close,
            line: { color, width: 2 }
        });

        const prediction = predictionBySymbol[c.symbol];
        if (prediction && c.dates.length > 0) {
            const lastDate = new Date(c.dates[c.dates.length - 1]);
            const forecastDate = new Date(lastDate);
            forecastDate.setDate(forecastDate.getDate() + prediction.horizon_days);
            traces.push({
                type: 'scatter',
                mode: 'lines',
                name: `${c.symbol} (forecast)`,
                x: [c.dates[c.dates.length - 1], forecastDate.toISOString().split('T')[0]],
                y: [c.close[c.close.length - 1], prediction.predicted_price],
                line: { color, width: 2, dash: 'dot' },
                showlegend: false,
                hovertemplate: `Predicted: ₹%{y:.2f}<extra>${c.symbol} forecast</extra>`
            });
        }
    });

    Plotly.newPlot('multiStockChart', traces, {
        ...MULTI_STOCK_LAYOUT_BASE,
        height: 440,
        yaxis: { ...MULTI_STOCK_LAYOUT_BASE.yaxis, title: 'Close Price (₹)' }
    }, { responsive: true, displayModeBar: false });
}

// Pie Chart: proportional comparison of the selected stocks based on a
// chosen metric (portfolio allocation / market value, return contribution,
// trading volume share, or volatility share).
function renderMultiStockPieChart(rows, metricKey) {
    if (!rows || rows.length === 0) {
        document.getElementById('multiStockChart').innerHTML = '<div class="multi-stock-error">No comparison data available.</div>';
        return;
    }

    const metric = MULTI_STOCK_PIE_METRICS[metricKey] || MULTI_STOCK_PIE_METRICS.market_value;
    const labels = rows.map(r => r.symbol);
    const values = rows.map(r => Math.max(0, metric.getValue(r) || 0));
    const total = values.reduce((sum, v) => sum + v, 0);

    if (total <= 0) {
        document.getElementById('multiStockChart').innerHTML =
            '<div class="multi-stock-error">Selected metric has no positive values to plot for these stocks.</div>';
        return;
    }

    const trace = {
        type: 'pie',
        labels,
        values,
        marker: { colors: rows.map((_, i) => MULTI_STOCK_COLORS[i % MULTI_STOCK_COLORS.length]) },
        textinfo: 'label+percent',
        hovertemplate: '%{label}: %{value:,.2f} (%{percent})<extra></extra>',
        hole: 0.35
    };

    Plotly.newPlot('multiStockChart', [trace], {
        ...MULTI_STOCK_LAYOUT_BASE,
        height: 440,
        showlegend: true,
        legend: { orientation: 'h', y: -0.15 }
    }, { responsive: true, displayModeBar: false });
}

function renderMultiStockComparisonTable(rows, unavailable) {
    const el = document.getElementById('multiStockComparisonTable');
    if (!rows || rows.length === 0) {
        el.innerHTML = '<div class="multi-stock-error">No comparison data.</div>';
        return;
    }

    const warningHtml = (unavailable && unavailable.length)
        ? `<div class="multi-stock-warning">No data available for: ${unavailable.join(', ')}</div>`
        : '';

    const body = rows.map(r => {
        const returnClass = r.return_pct >= 0 ? 'positive' : 'negative';
        const growthClass = (r.growth_pct == null) ? '' : (r.growth_pct >= 0 ? 'positive' : 'negative');
        const growthDisplay = r.growth_pct != null ? `${r.growth_pct > 0 ? '+' : ''}${r.growth_pct.toFixed(2)}%` : '—';
        const betaDisplay = r.beta != null ? r.beta.toFixed(2) : '—';
        const sharpeDisplay = r.sharpe_ratio != null ? r.sharpe_ratio.toFixed(2) : '—';
        const predClass = (r.prediction && r.prediction.predicted_change_pct >= 0) ? 'positive' : 'negative';
        const predDisplay = r.prediction
            ? `₹${r.prediction.predicted_price.toFixed(2)} <span class="multi-stock-pred-delta ${predClass}">(${r.prediction.predicted_change_pct > 0 ? '+' : ''}${r.prediction.predicted_change_pct.toFixed(2)}%)</span>`
            : '—';
        // Day Change (%): close on the selected "To" date vs. the previous
        // trading day within the filtered range (see day_change_pct in the
        // backend payload). Distinct from "Return", which is the total
        // return across the whole selected period.
        const dayChangeClass = (r.day_change_pct == null) ? '' : (r.day_change_pct >= 0 ? 'positive' : 'negative');
        const dayChangeDisplay = r.day_change_pct != null
            ? `${r.day_change_pct > 0 ? '+' : ''}${r.day_change_pct.toFixed(2)}%`
            : '—';
        const badgeHtml = (r.badges || [])
            .map(b => `<span class="multi-stock-badge badge-${b.replace(/\s+/g, '-').toLowerCase()}">${b}</span>`)
            .join(' ');
        return `
            <tr>
                <td>${r.symbol}</td>
                <td>${r.sector}</td>
                <td>₹${r.latest_close.toFixed(2)}</td>
                <td class="${dayChangeClass}">${dayChangeDisplay}</td>
                <td class="${returnClass}">${r.return_pct > 0 ? '+' : ''}${r.return_pct.toFixed(2)}%</td>
                <td class="${growthClass}">${growthDisplay}</td>
                <td>${r.volatility_pct.toFixed(2)}%</td>
                <td>${r.risk_category}</td>
                <td>${betaDisplay}</td>
                <td>${sharpeDisplay}</td>
                <td>${Math.round(r.avg_volume).toLocaleString()}</td>
                <td>${predDisplay}</td>
                <td>${r.score.toFixed(1)}</td>
                <td>${badgeHtml || '—'}</td>
            </tr>`;
    }).join('');

    el.innerHTML = `
        ${warningHtml}
        <div class="multi-stock-table-scroll">
        <table class="multi-stock-table">
            <thead>
                <tr>
                    <th>Symbol</th><th>Sector</th><th>Price</th><th>Day Change (%)</th><th>Return</th>
                    <th>Growth (CAGR)</th><th>Volatility</th><th>Risk</th><th>Beta</th>
                    <th>Sharpe</th><th>Avg Volume</th><th>Predicted Price</th><th>Score</th><th>Badges</th>
                </tr>
            </thead>
            <tbody>${body}</tbody>
        </table>
        </div>`;
}

// =========================================================
// AI INVESTMENT ADVISOR
// The single, cohesive Investment Advisor card: Sector Selection +
// Investment Budget + risk/date filters + recommendations, all in one
// place. The Budget field here is also the app's one global budget
// input (see setGlobalBudget/getGlobalBudget above) -- Portfolio
// Optimization reads whatever was last set here.
// =========================================================

let advisorTrendChartInstance = null;
let advisorSectorChartInstance = null;
let aiAdvisorPageInitialized = false;

function initAIAdvisorPage() {
    const budgetField = document.getElementById('advisorBudget');
    const globalBudget = getGlobalBudget();
    if (budgetField && !budgetField.value && globalBudget) {
        budgetField.value = globalBudget;
    }
    if (!aiAdvisorPageInitialized) {
        aiAdvisorPageInitialized = true;
        wireAIAdvisorDynamicInputs();
        updateAdvisorRiskHelp();
        // Do not run analysis automatically: the user should set preferences
        // first and press the clearly labelled Generate Recommendation button.
    }
}

// Beginner-friendly flow: enter preferences first, then explicitly generate.
// This avoids unexpected requests while users are still filling the form.
function wireAIAdvisorDynamicInputs() {
    const sectorSelect = document.getElementById('advisorSectorSelect');
    const budgetInput = document.getElementById('advisorBudget');
    const riskSelect = document.getElementById('advisorRisk');
    const startDateInput = document.getElementById('advisorStartDate');
    const endDateInput = document.getElementById('advisorEndDate');

    // Keep the form predictable for beginners: changing an input does not
    // launch analysis in the background. The user starts it with the button.
    if (riskSelect) riskSelect.addEventListener('change', updateAdvisorRiskHelp);

    if (budgetInput) {
        let debounceTimer = null;
        budgetInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            // Keep the shared budget in sync after typing pauses, without
            // running an analysis until the user presses Generate.
            debounceTimer = setTimeout(() => {
                setGlobalBudget(budgetInput.value ? Number(budgetInput.value) : null);
            }, 600);
        });
    }
}


function updateAdvisorRiskHelp() {
    const riskSelect = document.getElementById('advisorRisk');
    const help = document.getElementById('advisorRiskHelp');
    if (!riskSelect || !help) return;
    const messages = {
        Low: 'Low Risk: prefers comparatively lower historical price fluctuations. Loss is still possible.',
        Medium: 'Balanced: weighs expected return against price fluctuations.',
        High: 'High Growth: favors growth indicators and may accept higher price fluctuations.'
    };
    help.textContent = messages[riskSelect.value] || messages.Medium;
}

function formatSignedCurrency(value) {
    const num = Number(value);
    const sign = num > 0 ? '+' : '';
    return `${sign}${formatCurrency(Math.round(num))}`;
}

async function loadAIAdvisor() {
    const emptyState = document.getElementById('advisorEmptyState');
    const results = document.getElementById('advisorResults');

    const sectorSelect = document.getElementById('advisorSectorSelect');
    const budgetInput = document.getElementById('advisorBudget');
    const riskSelect = document.getElementById('advisorRisk');
    const startDateInput = document.getElementById('advisorStartDate');
    const endDateInput = document.getElementById('advisorEndDate');

    // If the field is empty, fall back to the previously set global budget
    // (e.g. from an earlier session) so it doesn't have to be re-entered.
    if (budgetInput && !budgetInput.value) {
        const globalBudget = getGlobalBudget();
        if (globalBudget) budgetInput.value = globalBudget;
    }

    if (budgetInput && budgetInput.value && (!Number.isFinite(Number(budgetInput.value)) || Number(budgetInput.value) <= 0)) {
        if (emptyState) {
            emptyState.textContent = 'Please enter a budget greater than ₹0, or leave the budget empty to analyze stocks without share estimates.';
            emptyState.style.display = 'block';
        }
        if (results) results.style.display = 'none';
        return;
    }

    const payload = {
        sector: sectorSelect ? sectorSelect.value : '',
        budget: budgetInput && budgetInput.value ? Number(budgetInput.value) : null,
        riskPreference: riskSelect ? riskSelect.value : 'Medium',
        start_date: startDateInput && startDateInput.value ? startDateInput.value : null,
        end_date: endDateInput && endDateInput.value ? endDateInput.value : null
    };

    if (emptyState) emptyState.textContent = 'Analyzing available stock data. This may take a few seconds…';
    if (emptyState) emptyState.style.display = 'block';
    if (results) results.style.display = 'none';

    try {
        const generateButton = document.getElementById('advisorGenerateButton');
        if (generateButton) { generateButton.disabled = true; generateButton.textContent = 'Analyzing…'; }
        const response = await fetch('/api/ai-advisor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload)
        });
        let data;
        try { data = await response.json(); }
        catch (_) { throw new Error(response.redirected ? 'Your session may have expired. Please log in again and retry.' : `The advisor returned an unexpected response (HTTP ${response.status}).`); }

        if (!response.ok || data.error) {
            if (emptyState) {
                emptyState.textContent = data.error || `Could not generate a recommendation (HTTP ${response.status}).`;
                emptyState.style.display = 'block';
            }
            if (results) results.style.display = 'none';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';
        if (results) results.style.display = 'block';

        renderAdvisorSectorCard(data);
        renderAdvisorStockGrid(data.recommendations || []);
        renderAdvisorTrendChart(data.top_pick);
        renderAdvisorSectorChart(data.sector_comparison || [], data.best_sector);

        const sectorChartTitleEl = document.getElementById('advisorSectorChartTitle');
        if (sectorChartTitleEl) {
            sectorChartTitleEl.textContent = data.sector_locked
                ? `📊 ${data.best_sector} Model Score`
                : '📊 Sector Comparison (Model Score)';
        }

        const assumptionsEl = document.getElementById('advisorAssumptions');
        if (assumptionsEl) {
            assumptionsEl.textContent = 'Assumptions: ' + (data.assumptions || []).join(' ');
        }
    } catch (error) {
        console.error('Error loading AI advisor recommendation:', error);
        if (emptyState) {
            emptyState.textContent = error.message || 'Unable to generate a recommendation. Check the Flask terminal for details and try again.';
            emptyState.style.display = 'block';
        }
        if (results) results.style.display = 'none';
    } finally {
        const generateButton = document.getElementById('advisorGenerateButton');
        if (generateButton) { generateButton.disabled = false; generateButton.textContent = 'Generate Recommendation'; }
    }
}

function renderAdvisorSectorCard(data) {
    const sectorEl = document.getElementById('advisorBestSector');
    const reasonEl = document.getElementById('advisorSectorReason');
    const kpiWrap = document.getElementById('advisorPortfolioKpis');
    const badgeEl = document.getElementById('advisorSectorBadge');
    const gridTitleEl = document.getElementById('advisorStockGridTitle');

    if (sectorEl) sectorEl.textContent = data.best_sector || '-';
    if (reasonEl) reasonEl.textContent = data.sector_reason || '';
    if (badgeEl) badgeEl.textContent = data.sector_locked ? 'Selected Sector' : 'Recommended Sector';
    if (gridTitleEl) {
        gridTitleEl.textContent = data.sector_locked
            ? `Top Stocks in ${data.best_sector}`
            : 'Top 3 Stocks in this Sector';
    }

    const summary = data.portfolio_summary || {};
    const hasBudget = summary.invested_amount !== null && summary.invested_amount !== undefined;

    if (kpiWrap) {
        kpiWrap.style.display = hasBudget ? 'flex' : 'none';
        if (hasBudget) {
            document.getElementById('advisorInvested').textContent = formatCurrency(summary.invested_amount);
            document.getElementById('advisorPredictedValue').textContent = formatCurrency(summary.predicted_value);
            const profitEl = document.getElementById('advisorProfit');
            profitEl.textContent = formatSignedCurrency(summary.expected_profit);
            profitEl.className = 'metric-value ' + (summary.expected_profit >= 0 ? 'positive' : 'negative');
        }
    }
}

function renderAdvisorStockGrid(recommendations) {
    const grid = document.getElementById('advisorStockGrid');
    if (!grid) return;

    if (!recommendations.length) {
        grid.innerHTML = '<div class="ai-advisor-empty-state">No stocks could be scored for this sector/date range.</div>';
        return;
    }

    grid.innerHTML = recommendations.map(item => {
        const riskClass = `risk-${(item.risk_level || 'medium').toLowerCase()}`;
        const hasShares = item.shares !== null && item.shares !== undefined;
        const profitClass = item.expected_profit >= 0 ? 'positive' : 'negative';

        const sharesRow = hasShares
            ? `<div class="metric-item"><span class="metric-label">Shares you can buy:</span><span class="metric-value">${item.shares}</span></div>
               <div class="metric-item"><span class="metric-label">Invested:</span><span class="metric-value">${formatCurrency(item.invested_amount)}</span></div>
               <div class="metric-item"><span class="metric-label">Predicted Value:</span><span class="metric-value">${formatCurrency(item.predicted_value)}</span></div>
               <div class="metric-item"><span class="metric-label">Expected Profit:</span><span class="metric-value ${profitClass}">${formatSignedCurrency(item.expected_profit)}</span></div>`
            : `<div class="metric-item"><span class="metric-label">Allocation:</span><span class="metric-value">Provide a budget to see shares</span></div>`;

        const noteHtml = item.note
            ? `<div class="ai-advisor-substitution-note">${item.is_substitution ? '🔁 Substituted: ' : '⚠️ '}${item.note}</div>`
            : '';

        return `
            <div class="ai-advisor-stock-card ${riskClass}">
                <div class="ai-advisor-stock-card-header">
                    <span class="ai-advisor-stock-symbol">${item.symbol}</span>
                    <span class="ai-advisor-stock-sector">${item.sector}</span>
                </div>
                <div class="ai-advisor-stock-metrics">
                    <div class="metric-item"><span class="metric-label">Current Price:</span><span class="metric-value">₹${Number(item.current_price).toFixed(2)}</span></div>
                    <div class="metric-item"><span class="metric-label">Predicted Price (12mo):</span><span class="metric-value">₹${Number(item.predicted_price).toFixed(2)}</span></div>
                    <div class="metric-item"><span class="metric-label">Expected Return:</span><span class="metric-value ${item.expected_return_pct >= 0 ? 'positive' : 'negative'}">${item.expected_return_pct}%</span></div>
                    <div class="metric-item"><span class="metric-label">Risk Level:</span><span class="metric-value">${item.risk_level}</span></div>
                    <div class="metric-item"><span class="metric-label">Confidence:</span><span class="metric-value">${item.confidence}</span></div>
                    ${sharesRow}
                </div>
                ${noteHtml}
            </div>`;
    }).join('');
}

function renderAdvisorTrendChart(topPick) {
    const canvas = document.getElementById('advisorTrendChart');
    const label = document.getElementById('advisorTrendStockLabel');
    if (!canvas) return;

    if (advisorTrendChartInstance) {
        advisorTrendChartInstance.destroy();
        advisorTrendChartInstance = null;
    }

    if (!topPick || !topPick.history || !topPick.predicted) return;
    if (label) label.textContent = `${topPick.symbol} (${topPick.sector})`;

    const historyLabels = topPick.history.map(item => item.date);
    const historyData = topPick.history.map(item => item.close);
    const predictedLabels = topPick.predicted.map(item => item.date);
    const predictedData = topPick.predicted.map(item => item.close);

    const ctx = canvas.getContext('2d');
    advisorTrendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [...historyLabels, ...predictedLabels],
            datasets: [
                {
                    label: `${topPick.symbol} Historical`,
                    data: [...historyData, ...Array(predictedData.length).fill(null)],
                    borderColor: '#6c5ce7',
                    backgroundColor: 'rgba(108, 92, 231, 0.25)',
                    fill: false,
                    tension: 0.35,
                    spanGaps: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#6c5ce7',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1,
                    borderWidth: 3
                },
                {
                    label: `${topPick.symbol} Predicted`,
                    data: [...Array(historyData.length).fill(null), ...predictedData],
                    borderColor: '#00b894',
                    backgroundColor: 'rgba(0, 184, 148, 0.16)',
                    fill: false,
                    tension: 0.35,
                    spanGaps: true,
                    borderDash: [8, 4],
                    pointRadius: 4,
                    pointBackgroundColor: '#00b894',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1,
                    borderWidth: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₹${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: { display: true, title: { display: true, text: 'Date' }, ticks: { maxTicksLimit: 10, autoSkip: true } },
                y: { display: true, title: { display: true, text: 'Price (₹)' } }
            }
        }
    });
}

function renderAdvisorSectorChart(sectorComparison, bestSector) {
    const canvas = document.getElementById('advisorSectorChart');
    if (!canvas) return;

    if (advisorSectorChartInstance) {
        advisorSectorChartInstance.destroy();
        advisorSectorChartInstance = null;
    }
    if (!sectorComparison.length) return;

    const labels = sectorComparison.map(s => s.sector);
    const scores = sectorComparison.map(s => s.avg_score);
    const colors = sectorComparison.map(s => s.sector === bestSector ? '#ff9f0a' : 'rgba(51, 177, 232, 0.55)');
    const borders = sectorComparison.map(s => s.sector === bestSector ? '#ff9f0a' : '#33b1e8');

    const ctx = canvas.getContext('2d');
    advisorSectorChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Avg. Model Score',
                data: scores,
                backgroundColor: colors,
                borderColor: borders,
                borderWidth: 2,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const sector = sectorComparison[context.dataIndex];
                            return [
                                `Score: ${sector.avg_score}`,
                                `Avg. Expected Return: ${sector.avg_expected_return_pct}%`,
                                `Avg. Volatility: ${sector.avg_volatility_pct}%`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Sector' } },
                y: { title: { display: true, text: 'Avg. Model Score' } }
            }
        }
    });
}
