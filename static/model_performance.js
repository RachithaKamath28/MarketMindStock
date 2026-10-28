// =========================================================
// MODEL PERFORMANCE & ACCURACY MODULE
// Independent module: reads only from /api/model-performance/* endpoints.
// Does not read from or write to any state used by other pages/modules.
// =========================================================

let mpInitialized = false;
let mpSymbolRanges = {};
let mpActualPredictedChartInstance = null;
let mpResidualChartInstance = null;
let mpErrorDistChartInstance = null;

function mpCssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function initModelPerformancePage() {
    if (mpInitialized) return;
    mpInitialized = true;

    fetch('/api/model-performance/symbols')
        .then(res => res.json())
        .then(data => {
            mpSymbolRanges = data.sectors || {};
            const select = document.getElementById('mpSymbolSelect');
            select.innerHTML = '';
            Object.keys(mpSymbolRanges).forEach(sector => {
                const group = document.createElement('optgroup');
                group.label = sector;
                mpSymbolRanges[sector].forEach(entry => {
                    const opt = document.createElement('option');
                    opt.value = entry.symbol;
                    opt.textContent = entry.symbol;
                    opt.dataset.start = entry.data_start;
                    opt.dataset.end = entry.data_end;
                    group.appendChild(opt);
                });
                select.appendChild(group);
            });

            select.addEventListener('change', mpApplyDefaultDateRange);
            if (select.options.length) {
                select.selectedIndex = 0;
                mpApplyDefaultDateRange();
                loadModelPerformance();
            }
        })
        .catch(() => {
            document.getElementById('mpSymbolSelect').innerHTML = '<option value="">Failed to load stocks</option>';
        });
}

function mpApplyDefaultDateRange() {
    const select = document.getElementById('mpSymbolSelect');
    const opt = select.options[select.selectedIndex];
    if (!opt) return;
    const start = opt.dataset.start;
    const end = opt.dataset.end;
    document.getElementById('mpStartDate').value = start || '';
    document.getElementById('mpEndDate').value = end || '';
    const hint = document.getElementById('mpRangeHint');
    if (hint) hint.textContent = start && end ? `Data available from ${start} to ${end}.` : '';
}

async function loadModelPerformance() {
    const symbol = document.getElementById('mpSymbolSelect').value;
    if (!symbol) return;
    const startDate = document.getElementById('mpStartDate').value || null;
    const endDate = document.getElementById('mpEndDate').value || null;

    const emptyState = document.getElementById('mpEmptyState');
    const errorState = document.getElementById('mpErrorState');
    const results = document.getElementById('mpResults');

    emptyState.style.display = 'none';
    errorState.style.display = 'none';
    results.style.display = 'none';
    emptyState.textContent = 'Running walk-forward backtest…';
    emptyState.style.display = 'block';

    try {
        const res = await fetch('/api/model-performance/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, start_date: startDate, end_date: endDate })
        });
        const data = await res.json();

        if (!res.ok || data.error) {
            emptyState.style.display = 'none';
            errorState.style.display = 'block';
            errorState.textContent = data.error || 'Evaluation failed.';
            return;
        }

        emptyState.style.display = 'none';
        results.style.display = 'block';
        mpRenderResults(data);
    } catch (e) {
        emptyState.style.display = 'none';
        errorState.style.display = 'block';
        errorState.textContent = 'Could not reach the evaluation service. Please try again.';
    }
}

function mpRenderResults(data) {
    mpAnimateKpis(data.metrics);
    document.getElementById('mpPointsBadge').textContent = `${data.evaluation_points} test months`;

    mpRenderActualPredictedChart(data.actual_vs_predicted);
    mpRenderResidualChart(data.residuals);
    mpRenderErrorDistChart(data.error_distribution);
    mpRenderConfusionMatrix(data.confusion_matrix);
    mpRenderGauge(data.performance_score);

    document.getElementById('mpInterpretationText').textContent = data.interpretation;
}

// ---------------------------------------------------------
// KPI cards — animated count-up
// ---------------------------------------------------------
function mpAnimateKpis(metrics) {
    mpAnimateValue('mpMAE', metrics.mae, v => `₹${v.toFixed(2)}`);
    mpAnimateValue('mpMSE', metrics.mse, v => v.toFixed(1));
    mpAnimateValue('mpRMSE', metrics.rmse, v => `₹${v.toFixed(2)}`);
    mpAnimateValue('mpMAPE', metrics.mape, v => `${v.toFixed(2)}%`);
    mpAnimateValue('mpR2', metrics.r2, v => v.toFixed(3));
}

function mpAnimateValue(elId, target, formatter, durationMs = 700) {
    const el = document.getElementById(elId);
    if (!el) return;
    const start = 0;
    const startTime = performance.now();

    function tick(now) {
        const progress = Math.min(1, (now - startTime) / durationMs);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = start + (target - start) * eased;
        el.textContent = formatter(current);
        if (progress < 1) requestAnimationFrame(tick);
        else el.textContent = formatter(target);
    }
    requestAnimationFrame(tick);
}

// ---------------------------------------------------------
// Actual vs Predicted line chart
// ---------------------------------------------------------
function mpRenderActualPredictedChart(series) {
    const ctx = document.getElementById('mpActualPredictedChart').getContext('2d');
    if (mpActualPredictedChartInstance) mpActualPredictedChartInstance.destroy();

    const textColor = mpCssVar('--text-dim') || '#7c8798';
    const gridColor = mpCssVar('--border') || '#1d2530';
    const posColor = mpCssVar('--pos') || '#24d17a';
    const infoColor = mpCssVar('--info') || '#33b1e8';

    mpActualPredictedChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: series.dates,
            datasets: [
                {
                    label: 'Actual Price',
                    data: series.actual,
                    borderColor: posColor,
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    borderWidth: 2.5,
                    pointRadius: 2.5,
                    pointBackgroundColor: posColor
                },
                {
                    label: 'Predicted Price',
                    data: series.predicted,
                    borderColor: infoColor,
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    borderWidth: 2.5,
                    borderDash: [6, 4],
                    pointRadius: 2.5,
                    pointBackgroundColor: infoColor
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { color: textColor } },
                tooltip: {
                    callbacks: {
                        label: (c) => `${c.dataset.label}: ₹${c.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: { ticks: { color: textColor, maxTicksLimit: 10, autoSkip: true }, grid: { color: gridColor } },
                y: { ticks: { color: textColor, callback: (v) => `₹${v}` }, grid: { color: gridColor } }
            }
        }
    });
}

// ---------------------------------------------------------
// Residual plot (scatter: predicted price vs residual)
// ---------------------------------------------------------
function mpRenderResidualChart(residuals) {
    const ctx = document.getElementById('mpResidualChart').getContext('2d');
    if (mpResidualChartInstance) mpResidualChartInstance.destroy();

    const textColor = mpCssVar('--text-dim') || '#7c8798';
    const gridColor = mpCssVar('--border') || '#1d2530';
    const amber = mpCssVar('--amber') || '#ff9f0a';

    const points = residuals.predicted.map((p, i) => ({ x: p, y: residuals.residual[i] }));

    mpResidualChartInstance = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Residual (Actual − Predicted)',
                    data: points,
                    backgroundColor: amber,
                    pointRadius: 4
                },
                {
                    label: 'Zero Error',
                    data: points.length ? [
                        { x: Math.min(...points.map(p => p.x)), y: 0 },
                        { x: Math.max(...points.map(p => p.x)), y: 0 }
                    ] : [],
                    type: 'line',
                    borderColor: mpCssVar('--text-faint') || '#4d5866',
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (c) => `Predicted ₹${c.parsed.x.toFixed(2)} → residual ₹${c.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Predicted Price (₹)', color: textColor }, ticks: { color: textColor }, grid: { color: gridColor } },
                y: { title: { display: true, text: 'Residual (₹)', color: textColor }, ticks: { color: textColor }, grid: { color: gridColor } }
            }
        }
    });
}

// ---------------------------------------------------------
// Prediction error distribution (histogram)
// ---------------------------------------------------------
function mpRenderErrorDistChart(dist) {
    const ctx = document.getElementById('mpErrorDistChart').getContext('2d');
    if (mpErrorDistChartInstance) mpErrorDistChartInstance.destroy();

    const textColor = mpCssVar('--text-dim') || '#7c8798';
    const gridColor = mpCssVar('--border') || '#1d2530';
    const violet = mpCssVar('--violet') || '#a78bfa';

    mpErrorDistChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dist.labels,
            datasets: [{
                label: 'Occurrences',
                data: dist.counts,
                backgroundColor: violet,
                borderRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            plugins: { legend: { display: false } },
            scales: {
                x: { title: { display: true, text: 'Error Range (₹)', color: textColor }, ticks: { color: textColor, maxRotation: 45, minRotation: 45 }, grid: { display: false } },
                y: { title: { display: true, text: 'Number of Forecasts', color: textColor }, ticks: { color: textColor, precision: 0 }, grid: { color: gridColor } }
            }
        }
    });
}

// ---------------------------------------------------------
// Trend direction confusion matrix
// ---------------------------------------------------------
function mpRenderConfusionMatrix(cm) {
    document.getElementById('mpCmTP').textContent = cm.tp;
    document.getElementById('mpCmFP').textContent = cm.fp;
    document.getElementById('mpCmFN').textContent = cm.fn;
    document.getElementById('mpCmTN').textContent = cm.tn;

    document.getElementById('mpCmAccuracy').textContent = `${cm.accuracy.toFixed(1)}%`;
    document.getElementById('mpCmPrecision').textContent = `${cm.precision.toFixed(1)}%`;
    document.getElementById('mpCmRecall').textContent = `${cm.recall.toFixed(1)}%`;
    document.getElementById('mpCmF1').textContent = `${cm.f1.toFixed(1)}%`;
}

// ---------------------------------------------------------
// Circular gauge for the composite Model Performance Score
// ---------------------------------------------------------
function mpRenderGauge(scoreInfo) {
    const fillPath = document.getElementById('mpGaugeFill');
    const scoreEl = document.getElementById('mpGaugeScore');
    const categoryEl = document.getElementById('mpGaugeCategory');

    const categoryClass = {
        'Excellent': 'excellent',
        'Good': 'good',
        'Average': 'average',
        'Poor': 'poor'
    }[scoreInfo.category] || 'average';

    // The arc path length is ~282.7 (semicircle radius 90). Offset animates
    // from "empty" to the score's proportion of the 0-100 scale.
    const arcLength = 282.7;
    const targetOffset = arcLength * (1 - scoreInfo.score / 100);

    fillPath.classList.remove('poor', 'average', 'good', 'excellent');
    fillPath.classList.add(categoryClass);
    fillPath.style.strokeDasharray = `${arcLength}`;
    fillPath.style.strokeDashoffset = `${arcLength}`;
    // Force reflow so the transition animates from full-offset to target.
    fillPath.getBoundingClientRect();
    fillPath.style.strokeDashoffset = `${targetOffset}`;

    categoryEl.textContent = scoreInfo.category;
    categoryEl.className = `mp-gauge-category ${categoryClass}`;
    mpAnimateValue('mpGaugeScore', scoreInfo.score, v => v.toFixed(1));
}
