/**
 * ECONCATIVO - Facturación Tab Module
 */
// FACTURACIÓN TAB DATA & AUDIT TRAIL
function populateFacturacionMesAnioSelect() {
    // Reemplazado por selector de fecha Desde y Hasta
}

let facturacionFilterDebounceTimer = null;
let lastFacturacionQueryActive = false;

function showFacturacionLoader() {
    const tbody = document.getElementById('tbody-facturacion');
    const counter = document.getElementById('counter-facturacion');
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
                        Cargando facturas y comprobantes ARCA...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadFacturacionData() {
    populateFacturacionMesAnioSelect();
    showFacturacionLoader();
    try {
        const res = await fetch(`/api/sheet/INGRESOS?_t=${Date.now()}`);
        const json = await res.json();

        const facturacionRows = (json.rows || []).filter(r => {
            const tipoComp = str(getRowProp(r, ['Tipo comprobante'])).trim().toLowerCase();
            const isVuelto = tipoComp.includes('vuelto');
            const isEntregaCC = tipoComp.includes('entrega cc') || tipoComp.includes('cuenta corriente');
            const isAdelantoSena = tipoComp.includes('adelanto') || tipoComp.includes('seña') || tipoComp.includes('sena');
            return !isVuelto && !isEntregaCC && !isAdelantoSena;
        });

        if (json.status !== 'success' || !facturacionRows.length) {
            document.getElementById('tbody-facturacion').innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400">No hay facturas registradas en el historial de Facturación.</td></tr>`;
            document.getElementById('counter-facturacion').innerText = '0 registros';
            renderPaginationBar('facturacion', 'pagination-facturacion', { totalItems: 0 });
            currentFacturacion = [];
            return;
        }

        currentFacturacion = facturacionRows;
        applyFacturacionFilter();

    } catch (err) {
        console.error("Error al cargar facturación:", err);
    }
}

function renderFacturacionTable(rows) {
    const tbody = document.getElementById('tbody-facturacion');
    const counter = document.getElementById('counter-facturacion');

    counter.innerText = `${rows.length} registros`;

    const sortedRows = sortRecordsMostRecent(rows, ['Fecha emisión', 'Fecha'], ['ID ingreso', 'ID']);

    if (!sortedRows.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400">No se encontraron registros con los filtros seleccionados.</td></tr>`;
        renderPaginationBar('facturacion', 'pagination-facturacion', { totalItems: 0 });
        return;
    }

    paginateAndRender('facturacion', 'pagination-facturacion', sortedRows, (pageRows) => {
        tbody.innerHTML = pageRows.map(r => {
        const iid = str(getRowProp(r, ['ID ingreso', 'ID'])).trim();
        const fecha = getRowProp(r, ['Fecha emisión', 'Fecha']) || '-';
        const nroFactura = str(getRowProp(r, ['N° factura ARCA', 'Factura'])).trim();
        const cliente = getRowProp(r, ['Cliente']) || '-';
        
        const chofer = getRowProp(r, ['Chofer']) || '';
        const unidad = getRowProp(r, ['Unidad']) || '';
        let choferUnidad = '-';
        if (chofer && unidad) choferUnidad = `${chofer} / ${unidad}`;
        else if (chofer) choferUnidad = chofer;
        else if (unidad) choferUnidad = unidad;

        const neto = parseFloat(getRowProp(r, ['Neto']) || 0);
        const total = parseFloat(getRowProp(r, ['Total']) || 0);
        const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();

        const obs = str(getRowProp(r, ['Observaciones']) || '');
        let assocViajeId = '';
        if (obs.includes('Operación origen:')) {
            assocViajeId = obs.split('Operación origen:')[1].trim().split(' ')[0];
        }

        const tipoComp = str(getRowProp(r, ['Tipo comprobante'])).trim();
        const isNoFiscal = nroFactura.toUpperCase().includes('COMPROBANTE-INTERNO') || tipoComp.includes('No Fiscal') || st.includes('NO FISCAL');

        const isPendingBilling = !isNoFiscal && (!nroFactura || 
                                 nroFactura.toUpperCase().includes('PENDIENTE') || 
                                 st.includes('PENDIENTE DE FACTURA') || 
                                 st.includes('PENDIENTE FACTURA'));

        const isTransferredToIngresos = st === 'PENDIENTE MEDIO DE PAGO' || st === 'COBRADO' || st.includes('COBRADO') || st.includes('PARCIAL');

        let rowBgClass = 'hover:bg-slate-50 border-slate-100';
        let nroDisplay = '';
        let statusBadge = '';
        let actionBtn = '';

        let pdfResumenBtn = '';
        if (assocViajeId.startsWith('VIA-')) {
            pdfResumenBtn = `<a href="/api/viajes/${assocViajeId}/resumen_pdf" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2 py-1 rounded text-[11px] border border-red-200 shadow-sm transition-all" title="Descargar PDF Resumen de Liquidación del Viaje (Base + Extras - Señas)"><i class="fa-solid fa-file-pdf"></i> PDF Resumen 📄</a>`;
        } else {
            pdfResumenBtn = `<a href="/api/ingresos/${iid}/recibo_pdf" target="_blank" class="inline-flex items-center gap-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold px-2 py-1 rounded text-[11px] border border-slate-200 shadow-sm transition-all" title="Descargar Comprobante / Recibo de Ingreso"><i class="fa-solid fa-file-invoice"></i> Recibo 📄</a>`;
        }

        const emailBtn = `<button onclick="openSendFacturaEmailModal('${iid}')" class="inline-flex items-center gap-1 bg-sky-600 hover:bg-sky-700 text-white font-bold px-2 py-1 rounded text-[11px] shadow-sm transition-all cursor-pointer" title="Enviar mail al cliente adjuntando la factura ARCA PDF desde tu computadora"><i class="fa-solid fa-envelope"></i> Email ✉️</button>`;

        if (isNoFiscal && isTransferredToIngresos) {
            rowBgClass = 'bg-purple-50/60 hover:bg-purple-100/50 border-purple-200 opacity-90';
            nroDisplay = `<span class="bg-purple-100 text-purple-900 text-[10px] font-bold px-2 py-0.5 rounded border border-purple-200 uppercase"><i class="fa-solid fa-file-shield mr-1"></i>COMPROBANTE INTERNO</span>`;
            statusBadge = `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full"><i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i>No Fiscal (En Ingresos)</span>`;
            actionBtn = `
                ${pdfResumenBtn}
                ${emailBtn}
                <span class="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded" title="Transferido a la pestaña Ingresos">
                    <i class="fa-solid fa-hand-holding-dollar"></i> En Ingresos
                </span>
            `;
        } else if (isNoFiscal) {
            rowBgClass = 'bg-purple-50/60 hover:bg-purple-100/50 border-purple-200';
            nroDisplay = `<span class="bg-purple-100 text-purple-900 text-[10px] font-bold px-2 py-0.5 rounded border border-purple-200 uppercase"><i class="fa-solid fa-file-shield mr-1"></i>COMPROBANTE INTERNO</span>`;
            statusBadge = `<span class="bg-purple-600 text-white text-[9px] px-2 py-0.5 rounded font-bold uppercase shadow-sm"><i class="fa-solid fa-circle-check mr-1"></i>No Fiscal (Cobro Pendiente)</span>`;
            actionBtn = `
                ${pdfResumenBtn}
                ${emailBtn}
                <button onclick="marcarComoCobrado('${iid}')" class="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1 rounded text-[11px] shadow-sm transition-all cursor-pointer" title="Registrar Medios de Pago (Efectivo, Transferencia, Cheques)">
                    <i class="fa-solid fa-money-bill-wave"></i> Cobrado 💰
                </button>
            `;
        } else if (isPendingBilling) {
            rowBgClass = 'bg-amber-100/90 text-amber-900 border-amber-300 font-semibold';
            nroDisplay = `<span class="bg-amber-200 text-amber-950 text-[10px] font-bold px-2 py-0.5 rounded border border-amber-300 uppercase"><i class="fa-solid fa-clock mr-1"></i>PENDIENTE ARCA</span>`;
            statusBadge = `<span class="bg-amber-500 text-white text-[9px] px-2 py-0.5 rounded font-bold uppercase shadow-sm"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Pendiente ARCA</span>`;
            actionBtn = `
                ${pdfResumenBtn}
                ${emailBtn}
                <button onclick="completarFacturacionData('${iid}')" class="inline-flex items-center gap-1 bg-amber hover:bg-amber-dark text-white font-bold px-2.5 py-1 rounded text-[11px] shadow transition-all cursor-pointer" title="Cargar Número de Factura ARCA y fecha de emisión">
                    <i class="fa-solid fa-file-invoice-dollar"></i> Completar ARCA ✍️
                </button>
            `;
        } else if (isTransferredToIngresos) {
            rowBgClass = 'hover:bg-slate-50 border-slate-100 opacity-90';
            nroDisplay = `<span class="font-bold text-slate-800">${nroFactura}</span>`;
            statusBadge = `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full"><i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i>Facturado & Transferido</span>`;
            actionBtn = `
                ${pdfResumenBtn}
                ${emailBtn}
                <span class="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded" title="Transferido a la pestaña Ingresos">
                    <i class="fa-solid fa-hand-holding-dollar"></i> En Ingresos
                </span>
            `;
        } else {
            rowBgClass = 'hover:bg-slate-50 border-slate-100';
            nroDisplay = `<span class="font-bold text-slate-800">${nroFactura}</span>`;
            statusBadge = `<span class="bg-amber-100 text-amber-800 border border-amber-300 text-[10px] font-bold px-2.5 py-1 rounded-full"><i class="fa-solid fa-clock mr-1"></i>Factura Emitida</span>`;
            actionBtn = `
                ${pdfResumenBtn}
                ${emailBtn}
                <button onclick="transferirAIngresos('${iid}')" class="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1 rounded text-[11px] shadow-sm transition-all cursor-pointer" title="Transferir a la pestaña Ingresos para registrar los medios de pago">
                    <i class="fa-solid fa-money-bill-wave"></i> Cobrado 💰
                </button>
            `;
        }

        return `
            <tr class="${rowBgClass} border-b transition-all text-xs">
                <td class="px-3 py-2.5 font-bold ${isPendingBilling ? 'text-amber-950' : 'text-navy'} whitespace-nowrap">${iid}</td>
                <td class="px-3 py-2.5 whitespace-nowrap text-slate-600">${formatDateAR(fecha)}</td>
                <td class="px-3 py-2.5 whitespace-nowrap">${nroDisplay}</td>
                <td class="px-3 py-2.5 font-semibold text-slate-800">${cliente}</td>
                <td class="px-3 py-2.5 text-slate-500 text-[11px]">${choferUnidad}</td>
                <td class="px-3 py-2.5 font-medium text-slate-700">${formatARS(neto)}</td>
                <td class="px-3 py-2.5 font-bold text-navy whitespace-nowrap">${formatARS(total)}</td>
                <td class="px-3 py-2.5 whitespace-nowrap">${statusBadge}</td>
                <td class="px-3 py-2.5 text-right whitespace-nowrap">${actionBtn}</td>
            </tr>
        `;
    }).join('');
    }, 10);
}

function clearFacturacionDateFilter() {
    resetTablePaginationPage('facturacion');
    const d = document.getElementById('filter-f-desde');
    const h = document.getElementById('filter-f-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    filterFacturacionTable();
}

function resetFacturacionFilters() {
    resetTablePaginationPage('facturacion');
    const s = document.getElementById('search-facturacion');
    const d = document.getElementById('filter-f-desde');
    const h = document.getElementById('filter-f-hasta');
    const e = document.getElementById('filter-f-estado');
    if (s) s.value = '';
    if (d) d.value = '';
    if (h) h.value = '';
    if (e) e.value = '';
    lastFacturacionQueryActive = false;
    filterFacturacionTable(120, true);
}

function filterFacturacionTable(delay = 180, isDropdown = false) {
    resetTablePaginationPage('facturacion');
    const rawQuery = (document.getElementById('search-facturacion')?.value || '').trim();
    const isNowActive = rawQuery.length >= 3;

    if (!isDropdown && !isNowActive && !lastFacturacionQueryActive && rawQuery.length > 0) {
        return;
    }

    if (facturacionFilterDebounceTimer) {
        clearTimeout(facturacionFilterDebounceTimer);
    }

    if (delay > 0) {
        showFacturacionLoader();
    }
    lastFacturacionQueryActive = isNowActive;

    facturacionFilterDebounceTimer = setTimeout(() => {
        applyFacturacionFilter();
    }, delay);
}

function applyFacturacionFilter() {
    const rawQuery = (document.getElementById('search-facturacion')?.value || '').trim();
    const fQuery = rawQuery.length >= 3 ? rawQuery.toLowerCase() : '';
    const fEstado = document.getElementById('filter-f-estado')?.value || '';
    const fDesde = document.getElementById('filter-f-desde')?.value || '';
    const fHasta = document.getElementById('filter-f-hasta')?.value || '';

    const filtered = (currentFacturacion || []).filter(r => {
        const iid = str(getRowProp(r, ['ID ingreso', 'ID'])).toLowerCase();
        const cliente = str(getRowProp(r, ['Cliente'])).toLowerCase();
        const nroFactura = str(getRowProp(r, ['N° factura ARCA', 'Factura'])).toLowerCase();
        const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();

        const fullText = `${iid} ${cliente} ${nroFactura}`;
        if (fQuery && !fullText.includes(fQuery)) return false;

        const isPendingBilling = !nroFactura || nroFactura.includes('pendiente') || st.includes('PENDIENTE DE FACTURA');
        const isTransferred = st === 'PENDIENTE MEDIO DE PAGO' || st === 'COBRADO';
        const isBilled = !isPendingBilling && !isTransferred;

        if (fEstado === 'pendiente_arca' && !isPendingBilling) return false;
        if (fEstado === 'factura_emitida' && !isBilled) return false;
        if (fEstado === 'enviado_ingresos' && !isTransferred) return false;

        if (fDesde || fHasta) {
            const rawDate = getRowProp(r, ['Fecha emisión', 'Fecha cobro', 'Fecha']) || '';
            const dateStr = str(rawDate).split('T')[0].split(' ')[0];
            if (dateStr) {
                if (fDesde && dateStr < fDesde) return false;
                if (fHasta && dateStr > fHasta) return false;
            } else {
                return false;
            }
        }

        return true;
    });

    renderFacturacionTable(filtered);
}

// Transfer item from Facturación tab to Ingresos tab
async function transferirAIngresos(iid) {
    try {
        const res = await fetch('/api/ingresos/pasar_a_ingresos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: iid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadFacturacionData();
            await loadIngresosData();
            showToast(`Operación ${iid} transferida a la pestaña INGRESOS (Pendiente de Medio de Pago).`);
            switchTab('ingresos');
            marcarComoCobrado(iid);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al transferir a Ingresos.", "error");
    }
}
