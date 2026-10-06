/**
 * ECONCATIVO - Liquidaciones de Personal & Novedades Module
 */

// LIQUIDACIONES TAB LOGIC, HISTORY & PDF INTEGRATION
function populateLiquidacionesMesAnioSelect() {
    // Reemplazado por selector de rango de fechas Desde y Hasta
}

function initLiquidacionesDateFilters() {
    const dDesde = document.getElementById('filter-tab-liq-desde');
    const dHasta = document.getElementById('filter-tab-liq-hasta');
    const qSel = document.getElementById('filter-tab-liq-quincena');
    if (!dDesde || !dHasta) return;
    if (dDesde.value && dHasta.value) return;

    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const day = now.getDate();

    if (day <= 15) {
        if (qSel) qSel.value = 'q1';
        dDesde.value = `${y}-${m}-01`;
        dHasta.value = `${y}-${m}-15`;
    } else {
        if (qSel) qSel.value = 'q2';
        const lastDay = new Date(y, now.getMonth() + 1, 0).getDate();
        dDesde.value = `${y}-${m}-16`;
        dHasta.value = `${y}-${m}-${lastDay}`;
    }
}

function getLiquidacionesDateRangeParams() {
    const dDesde = document.getElementById('filter-tab-liq-desde')?.value || '';
    const dHasta = document.getElementById('filter-tab-liq-hasta')?.value || '';
    let params = '';
    if (dDesde) params += `&fecha_desde=${encodeURIComponent(dDesde)}&desde=${encodeURIComponent(dDesde)}`;
    if (dHasta) params += `&fecha_hasta=${encodeURIComponent(dHasta)}&hasta=${encodeURIComponent(dHasta)}`;

    if (dDesde) {
        const parts = dDesde.split('-');
        if (parts.length >= 2) {
            params += `&mes=${parseInt(parts[1], 10)}&anio=${parts[0]}`;
        }
    }
    return params;
}

function onLiquidacionesQuincenaChange() {
    const qSel = document.getElementById('filter-tab-liq-quincena');
    const dDesde = document.getElementById('filter-tab-liq-desde');
    const dHasta = document.getElementById('filter-tab-liq-hasta');
    if (!qSel || !dDesde || !dHasta) return;

    const qVal = qSel.value;
    if (qVal === 'custom') {
        loadLiquidacionesTab();
        return;
    }

    let baseDate = new Date();
    if (dDesde.value) {
        const p = dDesde.value.split('-');
        if (p.length === 3) {
            baseDate = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, 1);
        }
    }

    const y = baseDate.getFullYear();
    const m = String(baseDate.getMonth() + 1).padStart(2, '0');
    const lastDay = new Date(y, baseDate.getMonth() + 1, 0).getDate();

    if (qVal === 'q1') {
        dDesde.value = `${y}-${m}-01`;
        dHasta.value = `${y}-${m}-15`;
    } else if (qVal === 'q2') {
        dDesde.value = `${y}-${m}-16`;
        dHasta.value = `${y}-${m}-${lastDay}`;
    } else if (qVal === 'todas') {
        dDesde.value = `${y}-${m}-01`;
        dHasta.value = `${y}-${m}-${lastDay}`;
    }

    loadLiquidacionesTab();
}

function onLiquidacionesFechaChange() {
    const qSel = document.getElementById('filter-tab-liq-quincena');
    if (qSel) {
        qSel.value = 'custom';
    }
    loadLiquidacionesTab();
}

function clearLiquidacionesDateFilter() {
    const dDesde = document.getElementById('filter-tab-liq-desde');
    const dHasta = document.getElementById('filter-tab-liq-hasta');
    const qSel = document.getElementById('filter-tab-liq-quincena');
    if (dDesde) dDesde.value = '';
    if (dHasta) dHasta.value = '';
    if (qSel) qSel.value = 'todas';
    initLiquidacionesDateFilters();
    loadLiquidacionesTab();
}

function resetLiquidacionesFilters() {
    const dDesde = document.getElementById('filter-tab-liq-desde');
    const dHasta = document.getElementById('filter-tab-liq-hasta');
    const qSel = document.getElementById('filter-tab-liq-quincena');
    const emp = document.getElementById('filter-tab-liq-empleado');
    if (dDesde) dDesde.value = '';
    if (dHasta) dHasta.value = '';
    if (qSel) qSel.value = 'todas';
    if (emp) emp.value = '';
    initLiquidacionesDateFilters();
    loadLiquidacionesTab();
}

function showLiquidacionesTabLoader() {
    const tbody = document.getElementById('tbody-tab-liquidaciones');
    const totalCount = document.getElementById('tab-liq-total-count');
    if (totalCount) totalCount.innerText = 'Cargando...';
    if (!tbody) return;
    tbody.innerHTML = `
        <tr>
            <td colspan="12" class="py-24 text-center">
                <div class="flex flex-col items-center justify-center gap-3">
                    <div class="relative w-10 h-10">
                        <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                        <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                    </div>
                    <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                        Calculando liquidaciones del período...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadLiquidacionesTab() {
    initLiquidacionesDateFilters();
    showLiquidacionesTabLoader();

    const qSel = document.getElementById('filter-tab-liq-quincena');
    const qVal = qSel ? qSel.value : 'q1';
    const extraParams = getLiquidacionesDateRangeParams();

    const pdfBtn = document.getElementById('btn-pdf-planilla-resumen');
    if (pdfBtn) {
        pdfBtn.href = `/api/liquidaciones/planilla_pdf?quincena=${qVal}${extraParams}`;
    }

    try {
        // Cargar historial de liquidaciones y cheques disponibles PRIMERO para tener estados reales en memoria
        await Promise.all([
            loadHistorialLiquidaciones(),
            (async () => {
                try {
                    const chqRes = await fetch(`/api/cheques/disponibles?_t=${Date.now()}`);
                    const chqJson = await chqRes.json();
                    if (chqJson.status === 'success') {
                        window.currentAvailableCheques = chqJson.data || [];
                    }
                } catch (e) {
                    window.currentAvailableCheques = [];
                }
            })()
        ]);

        const res = await fetch(`/api/maestros/empleado/liquidaciones?quincena=${qVal}${extraParams}&_t=${Date.now()}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.data.length) {
            document.getElementById('tbody-tab-liquidaciones').innerHTML = `<tr><td colspan="12" class="p-6 text-center text-slate-400">Sin datos de liquidación para el período seleccionado.</td></tr>`;
            document.getElementById('tab-liq-total-sum').innerText = formatARS(0);
            document.getElementById('tab-liq-total-count').innerText = '0 choferes';
            currentTabLiquidacionesData = [];
        } else {
            currentTabLiquidacionesData = json.data;

            // Populate employee filter dropdown
            const empSelect = document.getElementById('filter-tab-liq-empleado');
            if (empSelect) {
                const currEmp = empSelect.value;
                empSelect.innerHTML = `<option value="">Todos los Empleados</option>` +
                    json.data.map(d => `<option value="${d.id_empleado}">${d.nombre} (${d.id_empleado})</option>`).join('');
                if (currEmp) empSelect.value = currEmp;
            }

            renderLiquidacionesTabTable(currentTabLiquidacionesData);
        }

    } catch (err) {
        console.error("Error al cargar la pestaña de liquidaciones:", err);
    }
}

function filterLiquidacionesTabTable() {
    const empVal = document.getElementById('filter-tab-liq-empleado').value;
    if (!empVal) {
        renderLiquidacionesTabTable(currentTabLiquidacionesData);
    } else {
        const filtered = currentTabLiquidacionesData.filter(d => d.id_empleado === empVal);
        renderLiquidacionesTabTable(filtered);
    }
}

function getLiquidacionConfirmadaEnPeriodo(item) {
    if (!currentHistorialLiquidacionesData || !currentHistorialLiquidacionesData.length) return null;
    const itemEid = String(item.id_empleado || '').trim().toLowerCase();
    const itemPeriodo = (item.periodo_label || '').toLowerCase();
    
    const isQ1_item = itemPeriodo.includes('1ª') || itemPeriodo.includes('1a') || itemPeriodo.includes('1°') || itemPeriodo.includes('1º') || itemPeriodo.includes('1');
    const isQ2_item = itemPeriodo.includes('2ª') || itemPeriodo.includes('2a') || itemPeriodo.includes('2°') || itemPeriodo.includes('2º') || itemPeriodo.includes('2');
    
    const dDesde = document.getElementById('filter-tab-liq-desde')?.value || '';
    const filterMonthYear = dDesde ? dDesde.substring(0, 7) : '';

    return currentHistorialLiquidacionesData.find(h => {
        const hEid = String(h.id_empleado || '').trim().toLowerCase();
        if (hEid !== itemEid) return false;
        
        const hPeriodo = (h.periodo_label || '').toLowerCase();
        const isQ1_h = hPeriodo.includes('1ª') || hPeriodo.includes('1a') || hPeriodo.includes('1°') || hPeriodo.includes('1º') || hPeriodo.includes('1');
        const isQ2_h = hPeriodo.includes('2ª') || hPeriodo.includes('2a') || hPeriodo.includes('2°') || hPeriodo.includes('2º') || hPeriodo.includes('2');
        
        const periodMatches = (isQ1_item && isQ1_h) || (isQ2_item && isQ2_h) || (hPeriodo === itemPeriodo);
        if (!periodMatches) return false;

        if (filterMonthYear && h.fecha_confirmacion) {
            const confMonthYear = String(h.fecha_confirmacion).substring(0, 7);
            if (filterMonthYear !== confMonthYear) return false;
        }
        
        return true;
    }) || null;
}

function isEmpleadoLiquidadoEnPeriodo(item) {
    return !!getLiquidacionConfirmadaEnPeriodo(item);
}

function mostrarErrorEmpleadoYaLiquidado(nombre, periodo, liqId = '') {
    const idMsg = liqId ? ` (${liqId})` : '';
    showToast(`El sueldo de ${nombre} ya fue liquidado para '${periodo}'${idMsg}. Si necesitás volver a liquidarlo por nuevos viajes o adelantos, podés hacer clic en 'Re-liquidar'.`, "warning", 6000);
}

function renderLiquidacionesTabTable(data) {
    const tbody = document.getElementById('tbody-tab-liquidaciones');
    const totalSumEl = document.getElementById('tab-liq-total-sum');
    const totalCountEl = document.getElementById('tab-liq-total-count');
    const qVal = document.getElementById('filter-tab-liq-quincena') ? document.getElementById('filter-tab-liq-quincena').value : 'q1';
    const extraParams = getLiquidacionesDateRangeParams();

    const totalSum = data.reduce((acc, item) => acc + item.sueldo_final, 0);
    totalSumEl.innerText = formatARS(totalSum);
    totalCountEl.innerText = `${data.length} choferes`;

    if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="12" class="p-6 text-center text-slate-400">Sin datos para el filtro seleccionado.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(item => {
        const comisionBadge = item.comision_pct > 0 
            ? `<span class="bg-emerald-100 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] border border-emerald-200">${item.comision_pct}%</span>` 
            : `<span class="text-slate-400 font-medium">0%</span>`;

        const totReint = item.tot_reintegros || 0;
        const totDed = item.tot_deducciones || 0;

        const reintDisp = totReint > 0 
            ? `<span class="font-bold text-emerald-700">+${formatARS(totReint)}</span>` 
            : `<span class="text-slate-400">$0.00</span>`;

        const dedDisp = totDed > 0 
            ? `<span class="font-bold text-red-600">-${formatARS(totDed)}</span>` 
            : `<span class="text-slate-400">$0.00</span>`;

        const liqExistente = getLiquidacionConfirmadaEnPeriodo(item);
        const yaLiquidado = !!liqExistente;

        const estadoBadge = yaLiquidado
            ? `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold px-2.5 py-1 rounded-full text-[11px] inline-flex items-center gap-1 shadow-sm"><i class="fa-solid fa-lock text-emerald-600"></i> Liquidado</span>`
            : `<span class="bg-amber-50 text-amber-800 border border-amber-300 font-bold px-2.5 py-1 rounded-full text-[11px] inline-flex items-center gap-1"><i class="fa-solid fa-clock text-amber-600"></i> Pendiente</span>`;

        const accionesHtml = yaLiquidado
            ? `
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="verDesgloseLiquidacion('${item.id_empleado}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2.5 py-1.5 rounded-lg text-xs transition-all cursor-pointer" title="Ver desglose detallado">
                        <i class="fa-solid fa-list-check"></i> Desglose
                    </button>
                    <a href="/api/liquidaciones/${item.id_empleado}/pdf?quincena=${qVal}${extraParams}" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2.5 py-1.5 rounded-lg text-xs border border-red-200 shadow-sm transition-all" title="Descargar Recibo PDF">
                        <i class="fa-solid fa-file-pdf"></i> Recibo
                    </a>
                    <span class="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 font-bold px-3 py-1.5 rounded-lg text-xs border border-emerald-200 shadow-sm" title="Liquidación ya confirmada para este período">
                        <i class="fa-solid fa-circle-check text-emerald-500"></i> Liquidado
                    </span>
                </div>
            `
            : `
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="verDesgloseLiquidacion('${item.id_empleado}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2.5 py-1.5 rounded-lg text-xs transition-all cursor-pointer" title="Ver desglose detallado">
                        <i class="fa-solid fa-list-check"></i> Desglose
                    </button>
                    <button onclick="abrirModalLiquidarEmpleado('${item.id_empleado}')" class="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-3.5 py-1.5 rounded-lg text-xs shadow-sm hover:shadow transition-all cursor-pointer" title="Liquidar sueldo de este empleado">
                        <i class="fa-solid fa-hand-holding-dollar"></i> Liquidar Sueldo
                    </button>
                </div>
            `;

        return `
            <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
                <td class="px-4 py-3 whitespace-nowrap">
                    <div class="font-bold text-navy text-sm">${item.nombre}</div>
                    <div class="text-[10px] text-slate-400 font-mono">${item.id_empleado}</div>
                </td>
                <td class="px-4 py-3 font-medium text-slate-700 whitespace-nowrap">${item.puesto}</td>
                <td class="px-4 py-3 whitespace-nowrap">
                    <span class="bg-amber-100 text-amber-900 font-bold px-2 py-0.5 rounded text-[10px] border border-amber-200">${item.periodo_label}</span>
                </td>
                <td class="px-4 py-3 font-semibold text-slate-800 whitespace-nowrap">
                    ${formatARS(item.sueldo_fijo_base)} 
                    <span class="text-[10px] text-slate-400 font-normal block">(Mes: ${formatARS(item.sueldo_fijo_mensual)})</span>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">${comisionBadge}</td>
                <td class="px-4 py-3 font-bold text-slate-800 whitespace-nowrap">${item.cant_viajes} op.</td>
                <td class="px-4 py-3 font-bold text-emerald-600 whitespace-nowrap">${formatARS(item.total_comisiones)}</td>
                <td class="px-4 py-3 whitespace-nowrap">${reintDisp}</td>
                <td class="px-4 py-3 whitespace-nowrap">${dedDisp}</td>
                <td class="px-4 py-3 font-black text-emerald-950 text-sm bg-emerald-50/60 whitespace-nowrap">${formatARS(item.sueldo_final)}</td>
                <td class="px-4 py-3 text-center whitespace-nowrap">${estadoBadge}</td>
                <td class="px-4 py-3 text-right whitespace-nowrap">${accionesHtml}</td>
            </tr>
        `;
    }).join('');
}

// HISTORIAL DE LIQUIDACIONES LOGIC
let historialLiqFilterDebounceTimer = null;
let lastHistorialLiqQueryActive = false;

function showHistorialLiquidacionesLoader() {
    const tbody = document.getElementById('tbody-historial-liquidaciones');
    const counter = document.getElementById('counter-historial-liq');
    if (counter) counter.innerText = 'Cargando...';
    if (!tbody) return;
    tbody.innerHTML = `
        <tr>
            <td colspan="9" class="py-24 text-center">
                <div class="flex flex-col items-center justify-center gap-3">
                    <div class="relative w-10 h-10">
                        <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                        <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                    </div>
                    <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                        Cargando historial de liquidaciones confirmadas...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadHistorialLiquidaciones() {
    showHistorialLiquidacionesLoader();
    try {
        const extraParams = getLiquidacionesDateRangeParams();
        const res = await fetch(`/api/liquidaciones/historial?_t=${Date.now()}${extraParams}`);
        const json = await res.json();
        const counter = document.getElementById('counter-historial-liq');
        
        if (json.status !== 'success' || !json.data.length) {
            document.getElementById('tbody-historial-liquidaciones').innerHTML = `<tr><td colspan="9" class="p-6 text-center text-slate-400">No hay liquidaciones confirmadas en el historial. ¡Toca "Confirmar & Registrar Liquidación 🔒" arriba para guardar una quincena!</td></tr>`;
            if (counter) counter.innerText = '0 registros';
            renderPaginationBar('historial_liq', 'pagination-historial-liq', { totalItems: 0 });
            currentHistorialLiquidacionesData = [];
            return;
        }

        currentHistorialLiquidacionesData = json.data;
        if (counter) counter.innerText = `${json.data.length} registros`;
        renderHistorialLiquidacionesTable(currentHistorialLiquidacionesData);

        // Mantener tabla activa sincronizada
        if (typeof currentTabLiquidacionesData !== 'undefined' && currentTabLiquidacionesData && currentTabLiquidacionesData.length) {
            renderLiquidacionesTabTable(currentTabLiquidacionesData);
        }

    } catch (err) {
        console.error("Error al cargar historial de liquidaciones:", err);
    }
}

function renderHistorialLiquidacionesTable(data) {
    const tbody = document.getElementById('tbody-historial-liquidaciones');

    const sortedData = sortRecordsMostRecent(data, ['fecha_confirmacion', 'fecha'], ['id_liquidacion', 'id']);

    if (!sortedData.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="p-6 text-center text-slate-400">Sin registros en el historial con los filtros aplicados.</td></tr>`;
        renderPaginationBar('historial_liq', 'pagination-historial-liq', { totalItems: 0 });
        return;
    }

    paginateAndRender('historial_liq', 'pagination-historial-liq', sortedData, (pageRows) => {
        tbody.innerHTML = pageRows.map(item => {
        const lid = item.id_liquidacion;
        const qVal = (item.periodo_label || '').includes('1ª') ? 'q1' : ((item.periodo_label || '').includes('2ª') ? 'q2' : 'todas');

        return `
            <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
                <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${lid}</td>
                <td class="px-4 py-3 whitespace-nowrap text-slate-600">${formatDateAR(item.fecha_confirmacion)}</td>
                <td class="px-4 py-3 whitespace-nowrap">
                    <span class="bg-amber-100 text-amber-900 font-bold px-2 py-0.5 rounded text-[10px] border border-amber-200">${item.periodo_label}</span>
                </td>
                <td class="px-4 py-3 font-bold text-slate-800 whitespace-nowrap">
                    ${item.nombre} <span class="text-[10px] text-slate-400 font-mono block">${item.id_empleado}</span>
                </td>
                <td class="px-4 py-3 font-semibold text-slate-800 whitespace-nowrap">${formatARS(item.sueldo_fijo_base)}</td>
                <td class="px-4 py-3 font-bold text-emerald-600 whitespace-nowrap">${formatARS(item.total_comisiones)}</td>
                <td class="px-4 py-3 font-black text-emerald-950 text-sm bg-emerald-50/60 whitespace-nowrap">${formatARS(item.sueldo_final)}</td>
                <td class="px-4 py-3 whitespace-nowrap">
                    <span class="bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full inline-flex items-center gap-1">
                        <i class="fa-solid fa-lock text-emerald-600"></i> CONFIRMADO
                    </span>
                </td>
                <td class="px-4 py-3 text-right whitespace-nowrap">
                    <div class="inline-flex items-center justify-end gap-1.5">
                        <button onclick="verDesgloseLiquidacion('${item.id_empleado}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[11px] transition-all cursor-pointer" title="Ver viajes de esta liquidación histórica">
                            <i class="fa-solid fa-list-check"></i> Desglose
                        </button>
                        <a href="/api/liquidaciones/${item.id_empleado}/pdf?quincena=${qVal}" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2 py-1 rounded text-[11px] border border-red-200 transition-all" title="Descargar PDF Individual para el chofer">
                            <i class="fa-solid fa-file-pdf"></i> PDF Chofer
                        </a>
                        <button onclick="deleteHistorialLiquidacion('${lid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 transition-all cursor-pointer" title="Eliminar registro del historial">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    }, 10);
}

function filterHistorialLiquidacionesTable(delay = 180, isDropdown = false) {
    resetTablePaginationPage('historial_liq');
    const rawQuery = (document.getElementById('search-historial-liq')?.value || '').trim();
    const isNowActive = rawQuery.length >= 3;

    if (!isDropdown && !isNowActive && !lastHistorialLiqQueryActive && rawQuery.length > 0) {
        return;
    }

    if (historialLiqFilterDebounceTimer) {
        clearTimeout(historialLiqFilterDebounceTimer);
    }

    if (delay > 0) {
        showHistorialLiquidacionesLoader();
    }
    lastHistorialLiqQueryActive = isNowActive;

    historialLiqFilterDebounceTimer = setTimeout(() => {
        applyHistorialLiquidacionesFilter();
    }, delay);
}

function applyHistorialLiquidacionesFilter() {
    const rawQuery = (document.getElementById('search-historial-liq')?.value || '').trim();
    const fQuery = rawQuery.length >= 3 ? rawQuery.toLowerCase() : '';
    const filtered = (currentHistorialLiquidacionesData || []).filter(r => {
        if (!fQuery) return true;
        const full = `${r.id_liquidacion} ${r.nombre} ${r.id_empleado} ${r.periodo_label} ${r.fecha_confirmacion}`.toLowerCase();
        return full.includes(fQuery);
    });
    renderHistorialLiquidacionesTable(filtered);
}

// INDIVIDUAL LIQUIDATION MODAL & MULTI-PAYMENT LOGIC
function getDefaultLiquidacionAccount() {
    if (typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length) {
        const bank = currentTesoreriaAccounts.find(a => a.tipo === 'Banco');
        if (bank) return bank.nombre;
        return currentTesoreriaAccounts[0].nombre;
    }
    return 'Banco Galicia Cta Cte';
}

function abrirModalLiquidarEmpleado(empId) {
    const item = (currentTabLiquidacionesData || []).find(d => String(d.id_empleado).trim().toLowerCase() === String(empId).trim().toLowerCase());
    if (!item) {
        showToast("No se encontraron los datos del empleado seleccionado.", "error");
        return;
    }

    if (isEmpleadoLiquidadoEnPeriodo(item)) {
        mostrarErrorEmpleadoYaLiquidado(item.nombre, item.periodo_label);
        return;
    }

    window.activeLiquidandoItem = item;

    // Populate employee details
    const nomEl = document.getElementById('liq-modal-emp-nombre');
    const idEl = document.getElementById('liq-modal-emp-id');
    const perEl = document.getElementById('liq-modal-periodo');
    const bancoEl = document.getElementById('liq-modal-banco');
    const cbuEl = document.getElementById('liq-modal-cbu');
    const baseEl = document.getElementById('liq-modal-base');
    const comEl = document.getElementById('liq-modal-comisiones');
    const reintEl = document.getElementById('liq-modal-reintegros');
    const dedEl = document.getElementById('liq-modal-deducciones');
    const netoEl = document.getElementById('liq-modal-sueldo-neto');

    if (nomEl) nomEl.innerText = item.nombre;
    if (idEl) idEl.innerText = item.id_empleado;
    if (perEl) perEl.innerText = item.periodo_label;
    if (bancoEl) bancoEl.innerText = item.banco || 'No especificado';
    if (cbuEl) cbuEl.innerText = item.alias_cbu || item.cbu || 'Sin CBU / Alias';

    if (baseEl) baseEl.innerText = formatARS(item.sueldo_fijo_base);
    if (comEl) comEl.innerText = `${formatARS(item.total_comisiones)} (${item.cant_viajes} viajes)`;
    if (reintEl) reintEl.innerText = formatARS(item.tot_reintegros || 0);
    if (dedEl) dedEl.innerText = formatARS(item.tot_deducciones || 0);
    if (netoEl) netoEl.innerText = formatARS(item.sueldo_final);

    // Initial default payment row
    const defaultAcc = getDefaultLiquidacionAccount();
    window.liquidandoPagos = [
        {
            metodo: 'Transferencia Bancaria',
            cuenta: defaultAcc,
            cheque_id: '',
            nro_cheque_propio: '',
            monto: item.sueldo_final
        }
    ];

    renderPagosLiquidacionRows();
    calcPagosLiquidacionTotales();

    openModal('modal-liquidar-empleado');
}

function renderPagosLiquidacionRows() {
    const container = document.getElementById('liq-pagos-container');
    if (!container) return;

    const availableCheques = (typeof window.currentAvailableCheques !== 'undefined' && window.currentAvailableCheques) ? window.currentAvailableCheques : [];
    
    const bankAccounts = (typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length)
        ? currentTesoreriaAccounts.filter(a => a.tipo === 'Banco')
        : [{ nombre: 'Banco Galicia Cta Cte' }];
        
    const cashAccounts = (typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length)
        ? currentTesoreriaAccounts.filter(a => a.tipo === 'Efectivo')
        : [{ nombre: 'Caja Chica Efectivo' }];

    container.innerHTML = (window.liquidandoPagos || []).map((pago, idx) => {
        const canDelete = window.liquidandoPagos.length > 1;

        let subSelectorHtml = '';
        if (pago.metodo === 'Transferencia Bancaria') {
            const accOpts = bankAccounts.map(a => `<option value="${a.nombre}" ${a.nombre === pago.cuenta ? 'selected' : ''}>${a.nombre}</option>`).join('');
            subSelectorHtml = `
                <div class="flex-1 min-w-[200px]">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Cuenta Bancaria de Origen *</label>
                    <select onchange="onCuentaPagoLiqChange(${idx}, this.value)" class="liq-pago-cuenta w-full p-2 bg-white border border-slate-200 rounded-xl font-bold text-navy text-xs outline-none focus:ring-2 focus:ring-navy shadow-sm">
                        ${accOpts}
                    </select>
                </div>
            `;
        } else if (pago.metodo === 'Efectivo') {
            const cashOpts = cashAccounts.map(a => `<option value="${a.nombre}" ${a.nombre === pago.cuenta ? 'selected' : ''}>${a.nombre}</option>`).join('');
            subSelectorHtml = `
                <div class="flex-1 min-w-[200px]">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Caja de Efectivo *</label>
                    <select onchange="onCuentaPagoLiqChange(${idx}, this.value)" class="liq-pago-cuenta w-full p-2 bg-white border border-slate-200 rounded-xl font-bold text-navy text-xs outline-none focus:ring-2 focus:ring-navy shadow-sm">
                        ${cashOpts}
                    </select>
                </div>
            `;
        } else if (pago.metodo === 'Cheque de Terceros') {
            let chqOpts = `<option value="">Seleccionar Cheque de Cartera...</option>`;
            if (availableCheques.length > 0) {
                chqOpts += availableCheques.map(c => {
                    const chqId = c.id || c['ID cheque'] || c.ID || '';
                    const banco = c.banco || c['Banco'] || '';
                    const nro = c.nro_cheque || c['N° cheque'] || c['Nro cheque'] || c.nro || '';
                    const monto = c.monto !== undefined ? c.monto : (c['Monto'] || 0);
                    const emisor = c.emisor || c['Emisor/Cliente'] || c['Emisor'] || c.cliente || 'Terceros';
                    const isSel = String(pago.cheque_id) === String(chqId) ? 'selected' : '';
                    return `<option value="${chqId}" data-monto="${monto}" data-banco="${banco}" data-nro="${nro}" ${isSel}>${chqId} | ${banco} N° ${nro} (${formatARS(monto)}) - ${emisor}</option>`;
                }).join('');
            } else {
                chqOpts = `<option value="">No hay cheques disponibles en cartera</option>`;
            }

            subSelectorHtml = `
                <div class="flex-1 min-w-[240px]">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Cheque de Cartera Disponible *</label>
                    <select onchange="onChequeLiqChange(${idx}, this)" class="liq-pago-cheque w-full p-2 bg-amber-50 border border-amber-300 rounded-xl font-medium text-amber-950 text-xs outline-none focus:ring-2 focus:ring-amber-500 shadow-sm">
                        ${chqOpts}
                    </select>
                </div>
            `;
        } else if (pago.metodo === 'Cheque Propio') {
            const bankOpts = bankAccounts.map(a => `<option value="${a.nombre}" ${a.nombre === pago.cuenta ? 'selected' : ''}>${a.nombre}</option>`).join('');
            subSelectorHtml = `
                <div class="flex-1 min-w-[150px]">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Banco Chequera *</label>
                    <select onchange="onCuentaPagoLiqChange(${idx}, this.value)" class="liq-pago-cuenta w-full p-2 bg-white border border-slate-200 rounded-xl font-bold text-navy text-xs outline-none focus:ring-2 focus:ring-navy shadow-sm">
                        ${bankOpts}
                    </select>
                </div>
                <div class="w-28">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">N° Cheque *</label>
                    <input type="text" placeholder="Ej: 10492" value="${pago.nro_cheque_propio || ''}" oninput="onNroChequePropioChange(${idx}, this.value)" class="liq-pago-nro-chq w-full p-2 bg-white border border-slate-200 rounded-xl font-mono text-xs outline-none focus:ring-2 focus:ring-navy shadow-sm">
                </div>
            `;
        }

        return `
            <div class="liq-pago-row bg-slate-50/80 p-3 rounded-xl border border-slate-200 flex flex-wrap items-end gap-2.5 transition-all shadow-xs">
                <div class="w-full flex items-center justify-between pb-1 border-b border-slate-200/60 text-[11px]">
                    <span class="font-bold text-slate-600 flex items-center gap-1">
                        <i class="fa-solid fa-receipt text-slate-400"></i> Desembolso #${idx + 1}
                    </span>
                    ${canDelete ? `
                        <button type="button" onclick="removePagoLiquidacionRow(${idx})" class="text-rose-500 hover:text-rose-700 font-bold transition-all cursor-pointer text-xs" title="Quitar este medio de pago">
                            <i class="fa-solid fa-trash-can"></i> Quitar
                        </button>
                    ` : ''}
                </div>

                <div class="w-44">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Tipo de Pago *</label>
                    <select onchange="onMetodoPagoLiqChange(${idx}, this.value)" class="liq-pago-metodo w-full p-2 bg-white border border-slate-200 rounded-xl font-semibold text-slate-800 text-xs outline-none focus:ring-2 focus:ring-navy shadow-sm">
                        <option value="Transferencia Bancaria" ${pago.metodo === 'Transferencia Bancaria' ? 'selected' : ''}>🏦 Transferencia</option>
                        <option value="Efectivo" ${pago.metodo === 'Efectivo' ? 'selected' : ''}>💵 Efectivo</option>
                        <option value="Cheque de Terceros" ${pago.metodo === 'Cheque de Terceros' ? 'selected' : ''}>💳 Cheque Cartera</option>
                        <option value="Cheque Propio" ${pago.metodo === 'Cheque Propio' ? 'selected' : ''}>✍️ Cheque Propio</option>
                    </select>
                </div>

                ${subSelectorHtml}

                <div class="w-32">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase mb-1">Monto ($) *</label>
                    <input type="number" step="0.01" min="0" value="${pago.monto || 0}" oninput="onMontoPagoLiqChange(${idx}, this.value)" class="liq-pago-monto w-full p-2 bg-white border border-slate-200 rounded-xl font-black text-navy text-xs outline-none focus:ring-2 focus:ring-navy text-right shadow-sm">
                </div>
            </div>
        `;
    }).join('');
}

function onMetodoPagoLiqChange(idx, newMetodo) {
    if (!window.liquidandoPagos || !window.liquidandoPagos[idx]) return;
    window.liquidandoPagos[idx].metodo = newMetodo;
    window.liquidandoPagos[idx].cheque_id = '';
    window.liquidandoPagos[idx].nro_cheque_propio = '';
    
    if (newMetodo === 'Transferencia Bancaria') {
        const banks = (typeof currentTesoreriaAccounts !== 'undefined') ? currentTesoreriaAccounts.filter(a => a.tipo === 'Banco') : [];
        window.liquidandoPagos[idx].cuenta = banks.length ? banks[0].nombre : 'Banco Galicia Cta Cte';
    } else if (newMetodo === 'Efectivo') {
        const cash = (typeof currentTesoreriaAccounts !== 'undefined') ? currentTesoreriaAccounts.filter(a => a.tipo === 'Efectivo') : [];
        window.liquidandoPagos[idx].cuenta = cash.length ? cash[0].nombre : 'Caja Chica Efectivo';
    } else if (newMetodo === 'Cheque Propio') {
        const banks = (typeof currentTesoreriaAccounts !== 'undefined') ? currentTesoreriaAccounts.filter(a => a.tipo === 'Banco') : [];
        window.liquidandoPagos[idx].cuenta = banks.length ? banks[0].nombre : 'Banco Galicia Cta Cte';
    }

    renderPagosLiquidacionRows();
    calcPagosLiquidacionTotales();
}

function onCuentaPagoLiqChange(idx, val) {
    if (!window.liquidandoPagos || !window.liquidandoPagos[idx]) return;
    window.liquidandoPagos[idx].cuenta = val;
}

function onNroChequePropioChange(idx, val) {
    if (!window.liquidandoPagos || !window.liquidandoPagos[idx]) return;
    window.liquidandoPagos[idx].nro_cheque_propio = val;
}

function onChequeLiqChange(idx, selectEl) {
    if (!window.liquidandoPagos || !window.liquidandoPagos[idx]) return;
    const chqId = selectEl.value;
    window.liquidandoPagos[idx].cheque_id = chqId;

    const opt = selectEl.selectedOptions[0];
    if (opt && opt.dataset.monto) {
        const chqMonto = parseFloat(opt.dataset.monto);
        window.liquidandoPagos[idx].monto = chqMonto;
        const banco = opt.dataset.banco || 'Banco';
        const nro = opt.dataset.nro || '';
        window.liquidandoPagos[idx].cuenta = `Cheque N° ${nro} (${banco})`;
    }

    renderPagosLiquidacionRows();
    calcPagosLiquidacionTotales();
}

function onMontoPagoLiqChange(idx, val) {
    if (!window.liquidandoPagos || !window.liquidandoPagos[idx]) return;
    window.liquidandoPagos[idx].monto = parseFloat(val) || 0;
    calcPagosLiquidacionTotales();
}

function addPagoLiquidacionRow() {
    if (!window.liquidandoPagos) window.liquidandoPagos = [];
    const item = window.activeLiquidandoItem;
    const currentTotal = window.liquidandoPagos.reduce((acc, p) => acc + (parseFloat(p.monto) || 0), 0);
    const pendingAmount = item ? Math.max(0, roundDecimals(item.sueldo_final - currentTotal)) : 0;

    window.liquidandoPagos.push({
        metodo: 'Transferencia Bancaria',
        cuenta: getDefaultLiquidacionAccount(),
        cheque_id: '',
        nro_cheque_propio: '',
        monto: pendingAmount
    });

    renderPagosLiquidacionRows();
    calcPagosLiquidacionTotales();
}

function removePagoLiquidacionRow(idx) {
    if (!window.liquidandoPagos || window.liquidandoPagos.length <= 1) return;
    window.liquidandoPagos.splice(idx, 1);
    renderPagosLiquidacionRows();
    calcPagosLiquidacionTotales();
}

function roundDecimals(val) {
    return Math.round((val + Number.EPSILON) * 100) / 100;
}

function calcPagosLiquidacionTotales() {
    const item = window.activeLiquidandoItem;
    if (!item) return;

    const sueldoNeto = item.sueldo_final;
    const totalPagos = (window.liquidandoPagos || []).reduce((acc, p) => acc + (parseFloat(p.monto) || 0), 0);
    const diff = roundDecimals(totalPagos - sueldoNeto);

    const totPagarEl = document.getElementById('liq-calc-total-pagar');
    const totAsignEl = document.getElementById('liq-calc-total-asignado');
    const diffEl = document.getElementById('liq-calc-diferencia');
    const bannerEl = document.getElementById('liq-excedente-banner');

    if (totPagarEl) totPagarEl.innerText = formatARS(sueldoNeto);
    if (totAsignEl) totAsignEl.innerText = formatARS(totalPagos);

    if (diffEl) {
        if (diff < -0.01) {
            diffEl.className = 'font-black text-xs text-rose-600';
            diffEl.innerText = `Falta asignar: ${formatARS(Math.abs(diff))}`;
            if (bannerEl) bannerEl.classList.add('hidden');
        } else if (Math.abs(diff) <= 0.01) {
            diffEl.className = 'font-black text-xs text-emerald-600';
            diffEl.innerText = `✓ Total cubierto exactamente (${formatARS(totalPagos)})`;
            if (bannerEl) bannerEl.classList.add('hidden');
        } else {
            diffEl.className = 'font-black text-xs text-emerald-700';
            diffEl.innerText = `+ Excedente: ${formatARS(diff)}`;
            if (bannerEl) {
                bannerEl.classList.remove('hidden');
                const bTotPagos = document.getElementById('liq-banner-total-pagos');
                const bNeto = document.getElementById('liq-banner-sueldo-neto');
                const bExc = document.getElementById('liq-banner-excedente');
                if (bTotPagos) bTotPagos.innerText = formatARS(totalPagos);
                if (bNeto) bNeto.innerText = formatARS(sueldoNeto);
                if (bExc) bExc.innerText = formatARS(diff);
            }
        }
    }
}

async function submitLiquidacionIndividual(e) {
    e.preventDefault();
    const item = window.activeLiquidandoItem;
    if (!item) {
        showToast("No hay datos de empleado activos para liquidar.", "error");
        return;
    }

    if (!window.liquidandoPagos || !window.liquidandoPagos.length) {
        showToast("Debe agregar al menos un medio de pago.", "error");
        return;
    }

    for (let i = 0; i < window.liquidandoPagos.length; i++) {
        const p = window.liquidandoPagos[i];
        if (!p.monto || p.monto <= 0) {
            showToast(`El desembolso #${i + 1} debe tener un importe mayor a 0.`, "error");
            return;
        }
        if (p.metodo === 'Cheque de Terceros' && !p.cheque_id) {
            showToast(`Debe seleccionar un cheque disponible en cartera para el desembolso #${i + 1}.`, "error");
            return;
        }
    }

    const chqIds = window.liquidandoPagos.map(p => p.cheque_id).filter(Boolean);
    if (new Set(chqIds).size !== chqIds.length) {
        showToast("No podés seleccionar el mismo cheque en más de una línea de pago.", "error");
        return;
    }

    const totalPagos = window.liquidandoPagos.reduce((acc, p) => acc + (parseFloat(p.monto) || 0), 0);
    const sueldoNeto = item.sueldo_final;

    if (totalPagos < sueldoNeto - 0.01) {
        showToast(`El monto asignado (${formatARS(totalPagos)}) es menor al sueldo neto a cobrar (${formatARS(sueldoNeto)}). Debe cubrir la totalidad del sueldo.`, "error");
        return;
    }

    const excedente = roundDecimals(totalPagos - sueldoNeto);

    if (excedente > 0) {
        const confirmed = await showConfirmModal(
            "Confirmar Liquidación con Excedente",
            `El monto asignado (<b>${formatARS(totalPagos)}</b>) supera el sueldo neto a cobrar (<b>${formatARS(sueldoNeto)}</b>).<br><br>El excedente de <b>${formatARS(excedente)}</b> se registrará automáticamente como un <b>Adelanto de Sueldo (Deducción)</b> para la <b>siguiente quincena</b> de <b>${item.nombre}</b>.<br><br>¿Deseas confirmar y registrar la liquidación?`,
            {
                iconClass: "fa-solid fa-hand-holding-dollar text-emerald-600 text-3xl",
                confirmText: "Sí, Confirmar y Registrar"
            }
        );
        if (!confirmed) return;
    } else {
        const confirmed = await showConfirmModal(
            "Confirmar Liquidación de Sueldo",
            `¿Confirmar y liquidar el sueldo de <b>${item.nombre}</b> por un total de <b>${formatARS(sueldoNeto)}</b> para el período <b>${item.periodo_label}</b>?`,
            {
                iconClass: "fa-solid fa-circle-check text-emerald-600 text-3xl",
                confirmText: "Sí, Confirmar Sueldo"
            }
        );
        if (!confirmed) return;
    }

    const btn = document.getElementById('btn-confirmar-liq-individual');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Registrando...`;
    }

    try {
        const res = await fetch('/api/liquidaciones/confirmar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quincena: item.quincena || 'q1',
                id_empleado: item.id_empleado,
                item: item,
                pagos: window.liquidandoPagos.map(p => ({
                    metodo: p.metodo,
                    cuenta_tesoreria: p.cuenta,
                    cheque_id: p.cheque_id || null,
                    nro_cheque_propio: p.nro_cheque_propio || '',
                    monto: p.monto
                }))
            })
        });

        const json = await res.json();

        if (json.status === 'success') {
            showToast(json.message || `¡Sueldo de ${item.nombre} liquidado con éxito!`);
            closeModal('modal-liquidar-empleado');
            await loadLiquidacionesTab();
            try { await loadEgresosData(); } catch(e) {}
            try { await loadChequesData(); } catch(e) {}
            try { if (typeof loadTesoreriaData === 'function') await loadTesoreriaData(); } catch(e) {}
            try { await loadDashboardData(); } catch(e) {}
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al registrar liquidación individual:", err);
        showToast("Error al conectar con el servidor para registrar la liquidación.", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-lock text-sm"></i> Confirmar & Registrar Liquidación`;
        }
    }
}

async function confirmarLiquidacionActual(btnElement) {
    showToast("La liquidación ahora es individual por chofer. Hacé clic en 'Liquidar Sueldo' en el chofer correspondiente.", "info");
}

async function deleteHistorialLiquidacion(lid) {
    const confirmed = await showConfirmModal(
        "Eliminar Liquidación Histórica",
        `¿Estás seguro de eliminar la liquidación <b>${lid}</b>? Se revertirá también su egreso asociado.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    showLoading("Eliminando Liquidación", `Eliminando ${lid} del historial y de la base de datos...`);
    try {
        const res = await fetch('/api/liquidaciones/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: lid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadLiquidacionesTab();
            await loadEgresosData();
            await loadDashboardData();
            showToast(`Registro ${lid} eliminado del historial y de Egresos.`);
        } else {
            showToast("Error al eliminar: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar el registro del historial.", "error");
    } finally {
        hideLoading();
    }
}


// NOVEDADES DE PERSONAL JS HANDLERS
async function openModalNovedadPersonal() {
    if (!masterLists.empleados || masterLists.empleados.length === 0) {
        await loadMasterLists();
    }
    populateSelect('nov-empleado', masterLists.empleados, 'Seleccionar Empleado / Chofer...');

    if (typeof currentTesoreriaAccounts === 'undefined' || !currentTesoreriaAccounts || currentTesoreriaAccounts.length === 0) {
        try {
            const res = await fetch(`/api/tesoreria/summary?_t=${Date.now()}`);
            const data = await res.json();
            if (data && data.accounts) {
                currentTesoreriaAccounts = data.accounts;
            }
        } catch(e) {
            console.error("Error loading tesoreria accounts:", e);
        }
    }

    const fechaEl = document.getElementById('nov-fecha');
    if (fechaEl) fechaEl.value = new Date().toISOString().split('T')[0];

    document.getElementById('nov-monto').value = '';
    document.getElementById('nov-concepto').value = '';
    document.getElementById('nov-observaciones').value = '';
    document.getElementById('nov-tipo').value = 'Deducción';
    document.getElementById('nov-medio-pago').value = 'Transferencia Bancaria';

    await toggleMedioPagoNovedad();
    openModal('modal-novedad-personal');
}

async function toggleMedioPagoNovedad() {
    const medioEl = document.getElementById('nov-medio-pago');
    if (!medioEl) return;
    const medio = medioEl.value;
    const cuentaContainer = document.getElementById('nov-cuenta-container');
    const cuentaLabel = document.getElementById('nov-cuenta-label');
    const cuentaSel = document.getElementById('nov-cuenta-id');
    const chequeContainer = document.getElementById('nov-cheque-container');
    const chequeSel = document.getElementById('nov-cheque-id');

    if (typeof currentTesoreriaAccounts === 'undefined' || !currentTesoreriaAccounts || currentTesoreriaAccounts.length === 0) {
        try {
            const res = await fetch(`/api/tesoreria/summary?_t=${Date.now()}`);
            const data = await res.json();
            if (data && data.accounts) {
                currentTesoreriaAccounts = data.accounts;
            }
        } catch(e) {}
    }

    const allAccounts = currentTesoreriaAccounts || [];

    if (medio === 'Transferencia Bancaria') {
        if (chequeContainer) chequeContainer.classList.add('hidden');
        if (chequeSel) { chequeSel.required = false; chequeSel.value = ''; }

        if (cuentaContainer) {
            cuentaContainer.classList.remove('hidden');
            if (cuentaLabel) {
                cuentaLabel.innerHTML = `<i class="fa-solid fa-building-columns text-blue-600"></i> Cuenta Bancaria de Origen *`;
            }
            const bankAccounts = allAccounts.filter(a => a.tipo === 'Banco' || a.tipo === 'Billetera');
            const targetAccounts = bankAccounts.length ? bankAccounts : allAccounts.filter(a => a.tipo !== 'Cheques');
            if (cuentaSel) {
                cuentaSel.required = true;
                cuentaSel.innerHTML = targetAccounts.map(a => `<option value="${a.nombre}">${a.nombre} (Saldo: ${formatARS(a.saldo_calculado || 0)})</option>`).join('');
                if (!targetAccounts.length) {
                    cuentaSel.innerHTML = `<option value="Banco Cordoba">Banco Cordoba</option>`;
                }
            }
        }
    } else if (medio === 'Efectivo' || medio === 'Caja Chica') {
        if (chequeContainer) chequeContainer.classList.add('hidden');
        if (chequeSel) { chequeSel.required = false; chequeSel.value = ''; }

        if (cuentaContainer) {
            cuentaContainer.classList.remove('hidden');
            if (cuentaLabel) {
                cuentaLabel.innerHTML = `<i class="fa-solid fa-money-bill-wave text-emerald-600"></i> Caja / Cuenta de Efectivo de Origen *`;
            }
            const cashAccounts = allAccounts.filter(a => a.tipo === 'Efectivo');
            const targetAccounts = cashAccounts.length ? cashAccounts : allAccounts.filter(a => a.tipo !== 'Cheques');
            if (cuentaSel) {
                cuentaSel.required = true;
                cuentaSel.innerHTML = targetAccounts.map(a => `<option value="${a.nombre}">${a.nombre} (Saldo: ${formatARS(a.saldo_calculado || 0)})</option>`).join('');
                if (!targetAccounts.length) {
                    cuentaSel.innerHTML = `<option value="Caja Chica Efectivo">Caja Chica Efectivo</option>`;
                }
            }
        }
    } else if (medio === 'Cheque de Terceros') {
        if (cuentaContainer) {
            cuentaContainer.classList.add('hidden');
            if (cuentaSel) { cuentaSel.required = false; }
        }
        if (chequeContainer) {
            chequeContainer.classList.remove('hidden');
            if (chequeSel) {
                chequeSel.required = true;
                chequeSel.innerHTML = `<option value="">Cargando cheques disponibles...</option>`;

                try {
                    const res = await fetch(`/api/cheques/disponibles?_t=${Date.now()}`);
                    const json = await res.json();

                    if (json.status === 'success' && json.data.length > 0) {
                        chequeSel.innerHTML = `<option value="">Seleccionar Cheque de Cartera...</option>` +
                            json.data.map(c => {
                                const chqId = c.id || c['ID cheque'] || c.ID || '';
                                const banco = c.banco || c['Banco'] || '';
                                const nro = c.nro_cheque || c['N° cheque'] || c['Nro cheque'] || c.nro || '';
                                const monto = c.monto !== undefined ? c.monto : (c['Monto'] || 0);
                                const emisor = c.emisor || c['Emisor/Cliente'] || c['Emisor'] || c.cliente || '';
                                const labelText = `${chqId} | ${banco} N° ${nro} (${formatARS(monto)}) - Emisor: ${emisor}`;
                                return `<option value="${chqId}" data-monto="${monto}">${labelText}</option>`;
                            }).join('');

                        chequeSel.onchange = function() {
                            const selectedOpt = chequeSel.options[chequeSel.selectedIndex];
                            const monto = selectedOpt ? selectedOpt.getAttribute('data-monto') : null;
                            if (monto) {
                                document.getElementById('nov-monto').value = parseFloat(monto);
                            }
                        };
                    } else {
                        chequeSel.innerHTML = `<option value="">No hay cheques disponibles en cartera</option>`;
                    }
                } catch (err) {
                    console.error("Error al cargar cheques disponibles:", err);
                    chequeSel.innerHTML = `<option value="">Error al cargar cheques</option>`;
                }
            }
        }
    } else {
        if (cuentaContainer) cuentaContainer.classList.add('hidden');
        if (chequeContainer) chequeContainer.classList.add('hidden');
    }
}

async function submitNovedadPersonal(e) {
    e.preventDefault();
    const empleado = document.getElementById('nov-empleado').value;
    const tipo = document.getElementById('nov-tipo').value;
    const monto = parseFloat(document.getElementById('nov-monto').value || 0);
    const fecha = document.getElementById('nov-fecha').value;
    const medioPago = document.getElementById('nov-medio-pago').value;
    const cuentaOrigen = document.getElementById('nov-cuenta-id') ? document.getElementById('nov-cuenta-id').value : '';
    const chequeId = document.getElementById('nov-cheque-id') ? document.getElementById('nov-cheque-id').value : '';
    const concepto = document.getElementById('nov-concepto').value;
    const observaciones = document.getElementById('nov-observaciones').value;

    if (!empleado || !fecha || !concepto || monto <= 0) {
        showToast("Por favor complete todos los campos obligatorios y un monto mayor a 0.", "error");
        return;
    }

    if (medioPago === 'Cheque de Terceros' && !chequeId) {
        showToast("Debe seleccionar un cheque disponible en cartera.", "error");
        return;
    }

    if ((medioPago === 'Transferencia Bancaria' || medioPago === 'Efectivo' || medioPago === 'Caja Chica') && !cuentaOrigen) {
        showToast("Debe seleccionar la cuenta u origen de los fondos.", "error");
        return;
    }

    try {
        const res = await fetch('/api/liquidaciones/novedades/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                empleado: empleado,
                tipo: tipo,
                monto: monto,
                fecha: fecha,
                medio_pago: medioPago,
                cuenta_origen: cuentaOrigen,
                cheque_id: chequeId,
                concepto: concepto,
                observaciones: observaciones
            })
        });

        const json = await res.json();
        if (json.status === 'success') {
            showToast(`¡Novedad registrada con éxito! (${tipo}: ${formatARS(monto)})`);
            closeModal('modal-novedad-personal');
            await loadLiquidacionesTab();
            try { 
                if (typeof loadTesoreriaSummary === 'function') await loadTesoreriaSummary();
                if (typeof loadChequesData === 'function') await loadChequesData();
                if (typeof loadEgresosTable === 'function') await loadEgresosTable();
            } catch(err) {}
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al registrar novedad de personal:", err);
        showToast("Error de conexión al guardar novedad.", "error");
    }
}

// LISTADO Y GESTIÓN DE TODAS LAS NOVEDADES
let currentAllNovedadesData = [];

async function openModalListadoNovedades() {
    openModal('modal-listado-novedades');
    const tbody = document.getElementById('tbody-listado-novedades');
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="p-6 text-center text-slate-400">Cargando movimientos...</td></tr>`;
    
    try {
        const res = await fetch(`/api/liquidaciones/novedades?quincena=todas&_t=${Date.now()}`);
        const json = await res.json();
        if (json.status === 'success') {
            currentAllNovedadesData = json.data || [];
            
            const fEmp = document.getElementById('filtro-nov-empleado');
            if (fEmp) {
                const emps = [...new Set(currentAllNovedadesData.map(n => n.empleado).filter(Boolean))].sort();
                const currVal = fEmp.value;
                fEmp.innerHTML = `<option value="">Todos los Empleados (${emps.length})</option>` +
                    emps.map(e => `<option value="${e}">${e}</option>`).join('');
                if (currVal) fEmp.value = currVal;
            }
            renderListadoNovedadesTable();
        }
    } catch(err) {
        console.error("Error al cargar novedades:", err);
    }
}

function renderListadoNovedadesTable() {
    const tbody = document.getElementById('tbody-listado-novedades');
    const fEmp = document.getElementById('filtro-nov-empleado')?.value || '';
    const counterEl = document.getElementById('nov-listado-contador');
    if (!tbody) return;

    let list = currentAllNovedadesData || [];
    if (fEmp) {
        list = list.filter(n => (n.empleado || '').toLowerCase() === fEmp.toLowerCase());
    }

    if (counterEl) {
        const totalMonto = list.reduce((sum, n) => sum + (parseFloat(n.monto) || 0), 0);
        counterEl.innerHTML = `Total registros: <strong>${list.length}</strong> | Suma: <strong>${formatARS(totalMonto)}</strong>`;
    }

    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="p-6 text-center text-slate-400">No se encontraron movimientos registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = list.map(n => {
        const isDed = (n.tipo || '').toLowerCase().includes('deduc') || (n.tipo || '').toLowerCase().includes('adelant');
        const badgeTipo = isDed
            ? `<span class="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded text-[10px] border border-rose-200">🔻 Deducción</span>`
            : `<span class="bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded text-[10px] border border-emerald-200">🔺 Reintegro</span>`;

        const montoClass = isDed ? 'text-rose-600 font-bold' : 'text-emerald-700 font-bold';
        const montoSign = isDed ? '-' : '+';
        const isLiq = (n.estado || '').toLowerCase() === 'liquidado';

        const badgeEstado = isLiq
            ? `<span class="bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold px-2 py-0.5 rounded-full text-[10px] inline-flex items-center gap-1"><i class="fa-solid fa-lock"></i> Liquidado</span>`
            : `<span class="bg-amber-50 text-amber-700 border border-amber-200 font-bold px-2 py-0.5 rounded-full text-[10px] inline-flex items-center gap-1"><i class="fa-solid fa-clock"></i> Pendiente</span>`;

        const btnAction = isLiq
            ? `<span class="text-slate-400 text-[11px] font-medium" title="Ya liquidado">-</span>`
            : `<button onclick="confirmarEliminarNovedad('${n.id}', '${n.empleado}', ${n.monto})" class="bg-rose-50 hover:bg-rose-100 text-rose-700 hover:text-rose-900 border border-rose-200 font-bold px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer inline-flex items-center gap-1" title="Eliminar novedad y devolver fondos a cuenta bancaria/caja">
                <i class="fa-solid fa-trash-can text-rose-600"></i> Eliminar
               </button>`;

        return `
            <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
                <td class="px-3 py-2 font-bold text-navy font-mono">${n.id}</td>
                <td class="px-3 py-2 text-slate-600 whitespace-nowrap">${formatDateAR(n.fecha)}</td>
                <td class="px-3 py-2 font-bold text-slate-800">${n.empleado}</td>
                <td class="px-3 py-2">${badgeTipo}</td>
                <td class="px-3 py-2 text-slate-700 font-medium">${n.concepto}</td>
                <td class="px-3 py-2 text-slate-600 font-medium">${n.medio_pago || '-'}</td>
                <td class="px-3 py-2 text-right ${montoClass}">${montoSign}${formatARS(n.monto)}</td>
                <td class="px-3 py-2 text-center">${badgeEstado}</td>
                <td class="px-3 py-2 text-center">${btnAction}</td>
            </tr>
        `;
    }).join('');
}

async function confirmarEliminarNovedad(novId, emp, monto) {
    if (!confirm(`¿Estás seguro de eliminar el movimiento ${novId} de ${emp} por ${formatARS(monto)}?\n\nSi era una deducción/adelanto, se eliminará el egreso correspondiente y se reintegrará el dinero a la cuenta bancaria o caja.`)) {
        return;
    }

    try {
        const res = await fetch('/api/liquidaciones/novedades/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: novId })
        });
        const json = await res.json();
        if (json.status === 'success') {
            showToast(`¡Movimiento ${novId} eliminado con éxito!`);
            await openModalListadoNovedades();
            await loadLiquidacionesTab();
            try { 
                if (typeof loadTesoreriaSummary === 'function') await loadTesoreriaSummary();
                if (typeof loadChequesData === 'function') await loadChequesData();
                if (typeof loadEgresosTable === 'function') await loadEgresosTable();
            } catch(e) {}
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch(err) {
        console.error("Error al eliminar novedad:", err);
        showToast("Error de conexión al eliminar novedad.", "error");
    }
}


