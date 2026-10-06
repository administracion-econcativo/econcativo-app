/**
 * ECONCATIVO - Dashboard & Charts Module
 */
// Dynamically populate Dashboard Year Select (No hardcoding)
function populateDashboardYearSelect() {
    const select = document.getElementById('filter-year');
    if (!select) return;
    if (select.children.length > 0 && select.dataset.populated) return;

    const currentYear = new Date().getFullYear();
    const prevVal = select.value;
    let html = '';
    
    // Año base del sistema: 2026. No muestra años anteriores a este.
    // Muestra dinámicamente desde el año actual + 1 hasta 2026 cada vez que pasemos de año.
    const baseYear = Math.min(2026, currentYear);
    const maxYear = Math.max(currentYear + 1, baseYear + 1);

    for (let y = maxYear; y >= baseYear; y--) {
        const isSelected = (!prevVal && y === currentYear) || (prevVal === String(y));
        html += `<option value="${y}" ${isSelected ? 'selected' : ''}>Año ${y}</option>`;
    }
    html += `<option value="todos" ${prevVal === 'todos' ? 'selected' : ''}>Todos los Años (Histórico)</option>`;
    
    select.innerHTML = html;
    select.dataset.populated = 'true';
}

function showDashboardLoader() {
    const loader = document.getElementById('dashboard-loader');
    if (loader) {
        loader.classList.remove('hidden');
        loader.classList.add('flex');
    }
}

function hideDashboardLoader() {
    const loader = document.getElementById('dashboard-loader');
    if (loader) {
        loader.classList.add('hidden');
        loader.classList.remove('flex');
    }
}

// Dashboard Data
async function loadDashboardData() {
    populateDashboardYearSelect();
    showDashboardLoader();

    try {
        const anio = document.getElementById('filter-year')?.value || new Date().getFullYear();
        
        // Transición suave con loader (mínimo 200ms para feedback visual fluido al cambiar filtro)
        const fetchPromise = fetch(`/api/dashboard?anio=${anio}&_t=${Date.now()}`).then(res => res.json());
        const minTimerPromise = new Promise(resolve => setTimeout(resolve, 200));

        const [json] = await Promise.all([fetchPromise, minTimerPromise]);

        if (json.status !== 'success') return;

        const { kpis, monthly, egresos_por_categoria, medios_pago, actividades } = json.data;

        document.getElementById('kpi-facturado').innerText = formatARS(kpis.facturado_neto);
        const facturasCount = kpis.total_facturas !== undefined ? kpis.total_facturas : (kpis.facturas_count || 0);
        document.getElementById('kpi-facturas-count').innerText = facturasCount;
        if (document.getElementById('kpi-iva-facturado')) {
            document.getElementById('kpi-iva-facturado').innerText = formatARS(kpis.iva_facturado || 0);
        }
        if (document.getElementById('kpi-facturado-bruto')) {
            document.getElementById('kpi-facturado-bruto').innerText = formatARS(kpis.facturado_bruto || (kpis.facturado_neto + (kpis.iva_facturado || 0)));
        }
        document.getElementById('kpi-cobrado').innerText = formatARS(kpis.cobrado);
        document.getElementById('kpi-egresos').innerText = formatARS(kpis.egresos_pagados);
        if (kpis.saldo_favor_compensado > 0) {
            const subtextEl = document.getElementById('kpi-egresos-subtext');
            const compLbl = document.getElementById('kpi-total-comprado-lbl');
            if (subtextEl && compLbl) {
                compLbl.innerText = `${formatARS(kpis.total_gastos_comprados)} (${formatARS(kpis.saldo_favor_compensado)} Saldo a Favor C/C)`;
                subtextEl.classList.remove('hidden');
            }
        }
        document.getElementById('kpi-resultado').innerText = formatARS(kpis.resultado_caja);

        const elSaldo = document.getElementById('kpi-saldo-cobrar');
        if (elSaldo) elSaldo.innerText = formatARS(kpis.saldo_por_cobrar);
        const elRemu = document.getElementById('kpi-remuneracion');
        if (elRemu) elRemu.innerText = formatARS(kpis.remuneracion_generada);
        const elViajes = document.getElementById('kpi-total-viajes');
        if (elViajes) elViajes.innerText = `${kpis.total_viajes} registros`;

        renderMonthlyChart(monthly);
        renderExpensesChart(egresos_por_categoria);
        renderPaymentsChart(medios_pago);
        renderActivitiesChart(actividades);
        renderTopClientsChart(json.data.top_clientes);
        renderUnitFuelChart(json.data.consumo_unidades);
        renderChequesStatusChart(json.data.estado_cheques);

    } catch (err) {
        console.error("Error al cargar el dashboard:", err);
    } finally {
        hideDashboardLoader();
    }
}

function renderMonthlyChart(monthlyData) {
    const ctxElement = document.getElementById('chart-monthly');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const mData = monthlyData || {};
    const facturadoNeto = months.map(m => mData[m] ? (mData[m].facturado_neto !== undefined ? mData[m].facturado_neto : (mData[m].facturado || 0)) : 0);
    const ivaFacturado = months.map(m => mData[m] ? (mData[m].iva || 0) : 0);
    const cobrado = months.map(m => mData[m] ? (mData[m].cobrado || 0) : 0);
    const egresos = months.map(m => mData[m] ? (mData[m].egresos || 0) : 0);

    if (chartMonthly) chartMonthly.destroy();

    chartMonthly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: months,
            datasets: [
                { 
                    label: 'Facturado Neto', 
                    data: facturadoNeto, 
                    backgroundColor: '#002B5C', 
                    stack: 'facturado',
                    borderRadius: { topLeft: 0, topRight: 0, bottomLeft: 4, bottomRight: 4 }
                },
                { 
                    label: 'IVA Facturado', 
                    data: ivaFacturado, 
                    backgroundColor: '#EAA225', 
                    stack: 'facturado',
                    borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 }
                },
                { 
                    label: 'Cobrado Real', 
                    data: cobrado, 
                    backgroundColor: '#10B981', 
                    stack: 'cobrado',
                    borderRadius: 4 
                },
                { 
                    label: 'Egresos Pagados', 
                    data: egresos, 
                    backgroundColor: '#EF4444', 
                    stack: 'egresos',
                    borderRadius: 4 
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                label += formatARS(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: { 
                x: { stacked: false },
                y: { 
                    beginAtZero: true, 
                    ticks: { callback: v => '$' + v.toLocaleString('es-AR') } 
                } 
            }
        }
    });
}

function renderDoughnutLegend(containerId, items, unit = '$') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items || items.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-400 text-center py-2 font-medium">Sin datos registrados</p>';
        return;
    }

    const total = items.reduce((sum, item) => sum + (Number(item.value) || 0), 0);
    if (total <= 0) {
        container.innerHTML = '<p class="text-xs text-slate-400 text-center py-2 font-medium">Sin operaciones en este período</p>';
        return;
    }

    let html = '<div class="space-y-1.5">';
    items.forEach(item => {
        const val = Number(item.value) || 0;
        const pct = ((val / total) * 100).toFixed(1);
        let valFormatted = '';
        if (unit === '$') {
            valFormatted = formatARS(val);
        } else if (unit === 'viajes') {
            valFormatted = `${val.toLocaleString('es-AR')} ${val === 1 ? 'viaje' : 'viajes'}`;
        } else {
            valFormatted = `${val.toLocaleString('es-AR')} ${unit}`;
        }

        html += `
            <div class="flex items-center justify-between text-xs py-1.5 px-2 rounded-lg bg-slate-50/80 hover:bg-slate-100/90 transition-colors">
                <div class="flex items-center gap-2 min-w-0 pr-2">
                    <span class="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm" style="background-color: ${item.color};"></span>
                    <span class="text-slate-700 font-medium truncate" title="${item.label}">${item.label}</span>
                </div>
                <div class="flex items-center gap-1.5 flex-shrink-0 text-right">
                    <span class="font-bold text-navy text-[11px] font-mono">${valFormatted}</span>
                    <span class="text-[10px] font-semibold text-slate-400 min-w-[40px] text-right">(${pct}%)</span>
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

function renderExpensesChart(catData) {
    const ctxElement = document.getElementById('chart-expenses');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    
    const entries = Object.entries(catData || {}).filter(([_, v]) => Number(v) > 0);
    entries.sort((a, b) => b[1] - a[1]);

    const labels = entries.map(e => e[0]);
    const values = entries.map(e => e[1]);
    const palette = ['#D48806', '#002B5C', '#10B981', '#3B82F6', '#8B5CF6', '#EC4899', '#F97316', '#64748B'];
    const colors = labels.map((_, i) => palette[i % palette.length]);

    if (chartExpenses) chartExpenses.destroy();

    const hasData = values.length > 0 && values.some(v => v > 0);

    chartExpenses = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: hasData ? labels : ['Sin datos'],
            datasets: [{
                data: hasData ? values : [1],
                backgroundColor: hasData ? colors : ['#E2E8F0'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: hasData,
                    callbacks: {
                        label: function(context) {
                            return ` ${context.label}: ${formatARS(context.raw)}`;
                        }
                    }
                }
            }
        }
    });

    const legendItems = labels.map((label, idx) => ({
        label,
        value: values[idx],
        color: colors[idx]
    }));
    renderDoughnutLegend('legend-expenses', legendItems, '$');
}

function renderPaymentsChart(mediosData) {
    const ctxElement = document.getElementById('chart-payments');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    
    const entries = Object.entries(mediosData || {}).filter(([_, v]) => Number(v) > 0);
    entries.sort((a, b) => b[1] - a[1]);

    const labels = entries.map(e => e[0]);
    const values = entries.map(e => e[1]);
    const palette = ['#10B981', '#3B82F6', '#D48806', '#F59E0B', '#8B5CF6', '#64748B'];
    const colors = labels.map((_, i) => palette[i % palette.length]);

    if (chartPayments) chartPayments.destroy();

    const hasData = values.length > 0 && values.some(v => v > 0);

    chartPayments = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: hasData ? labels : ['Sin datos'],
            datasets: [{
                data: hasData ? values : [1],
                backgroundColor: hasData ? colors : ['#E2E8F0'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: hasData,
                    callbacks: {
                        label: function(context) {
                            return ` ${context.label}: ${formatARS(context.raw)}`;
                        }
                    }
                }
            }
        }
    });

    const legendItems = labels.map((label, idx) => ({
        label,
        value: values[idx],
        color: colors[idx]
    }));
    renderDoughnutLegend('legend-payments', legendItems, '$');
}

function renderActivitiesChart(actividadesData) {
    const ctxElement = document.getElementById('chart-activities');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    
    const entries = Object.entries(actividadesData || {});
    const positiveEntries = entries.filter(([_, v]) => Number(v) > 0);
    const activeEntries = positiveEntries.length > 0 ? positiveEntries : entries;

    const labels = activeEntries.map(e => e[0]);
    const values = activeEntries.map(e => e[1]);
    const palette = ['#002B5C', '#D48806', '#10B981', '#3B82F6'];
    const colors = labels.map((_, i) => palette[i % palette.length]);

    if (chartActivities) chartActivities.destroy();

    const hasData = values.length > 0 && values.some(v => v > 0);

    chartActivities = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: hasData ? labels : ['Sin datos'],
            datasets: [{
                data: hasData ? values : [1],
                backgroundColor: hasData ? colors : ['#E2E8F0'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: hasData,
                    callbacks: {
                        label: function(context) {
                            const val = context.raw;
                            return ` ${context.label}: ${val} ${val === 1 ? 'viaje / operación' : 'viajes / operaciones'}`;
                        }
                    }
                }
            }
        }
    });

    const legendItems = labels.map((label, idx) => ({
        label,
        value: values[idx],
        color: colors[idx]
    }));
    renderDoughnutLegend('legend-activities', legendItems, 'viajes');
}

function renderTopClientsChart(topClientsData) {
    const ctxElement = document.getElementById('chart-top-clients');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    const labels = Object.keys(topClientsData || {});
    const values = Object.values(topClientsData || {});

    if (chartTopClients) chartTopClients.destroy();

    chartTopClients = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length ? labels : ['Sin datos'],
            datasets: [{
                label: 'Facturado Neto ($)',
                data: values.length ? values : [0],
                backgroundColor: '#002B5C',
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Facturado: ${formatARS(ctx.parsed.x)}`
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { callback: v => '$' + (v >= 1000000 ? (v/1000000).toFixed(1) + 'M' : v.toLocaleString('es-AR')) }
                }
            }
        }
    });
}

function renderUnitFuelChart(fuelData) {
    const ctxElement = document.getElementById('chart-unit-fuel');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    const labels = Object.keys(fuelData || {});
    const values = Object.values(fuelData || {});

    if (chartUnitFuel) chartUnitFuel.destroy();

    chartUnitFuel = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length ? labels : ['Sin datos'],
            datasets: [{
                label: 'Combustible (Litros)',
                data: values.length ? values : [0],
                backgroundColor: '#E11D48',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Consumo: ${ctx.parsed.y.toLocaleString('es-AR')} Litros`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: v => v.toLocaleString('es-AR') + ' L' }
                }
            }
        }
    });
}

function renderChequesStatusChart(chequesData) {
    const ctxElement = document.getElementById('chart-cheques-status');
    if (!ctxElement) return;
    const ctx = ctxElement.getContext('2d');
    
    const entries = Object.entries(chequesData || {}).filter(([_, v]) => Number(v) > 0);
    entries.sort((a, b) => b[1] - a[1]);

    const labels = entries.map(e => e[0]);
    const values = entries.map(e => e[1]);

    const statusColorMap = {
        'Disponibles': '#10B981',
        'Cobrados / Regularizados': '#002B5C',
        'Entregados / Endosados': '#3B82F6',
        'En Re-presentación / Rechazados': '#EF4444'
    };
    const defaultPalette = ['#10B981', '#3B82F6', '#EF4444', '#002B5C', '#64748B'];
    const colors = labels.map((l, i) => statusColorMap[l] || defaultPalette[i % defaultPalette.length]);

    if (chartChequesStatus) chartChequesStatus.destroy();

    const hasData = values.length > 0 && values.some(v => v > 0);

    chartChequesStatus = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: hasData ? labels : ['Sin datos'],
            datasets: [{
                data: hasData ? values : [1],
                backgroundColor: hasData ? colors : ['#E2E8F0'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: hasData,
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${formatARS(ctx.parsed)}`
                    }
                }
            }
        }
    });

    const legendItems = labels.map((label, idx) => ({
        label,
        value: values[idx],
        color: colors[idx]
    }));
    renderDoughnutLegend('legend-cheques-status', legendItems, '$');
}

