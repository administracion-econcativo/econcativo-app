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
        const deleteBtn = `<button onclick="confirmarEliminarFactura('${iid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 shadow-sm transition-all cursor-pointer ml-1" title="Eliminar factura y revertir movimientos"><i class="fa-solid fa-trash-can"></i></button>`;

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
                ${deleteBtn}
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
                ${deleteBtn}
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
                ${deleteBtn}
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
                ${deleteBtn}
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
                ${deleteBtn}
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

// Delete invoice and reverse all associated financial/operational movements
async function confirmarEliminarFactura(iid) {
    if (!iid) return;
    const messageHtml = `
        <div class="space-y-3 text-left">
            <p class="text-sm text-slate-700">¿Estás seguro de que deseas eliminar la factura <b>${iid}</b>?</p>
            <div class="text-xs bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-lg space-y-1.5">
                <div class="flex items-start gap-1.5"><i class="fa-solid fa-circle-info text-amber-600 mt-0.5"></i> <span>Se revertirán automáticamente los cobros y movimientos en tesorería / bancos.</span></div>
                <div class="flex items-start gap-1.5"><i class="fa-solid fa-money-check text-amber-600 mt-0.5"></i> <span>Se eliminarán de cartera los cheques generados por esta factura.</span></div>
                <div class="flex items-start gap-1.5"><i class="fa-solid fa-rotate-left text-amber-600 mt-0.5"></i> <span>Por defecto, el viaje asociado volverá a <b>Pendiente de Facturar</b> para poder corregirlo y re-facturarlo.</span></div>
            </div>
            <label class="flex items-start gap-2.5 p-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-slate-800 cursor-pointer transition text-xs select-none">
                <input type="checkbox" id="del-viaje-cascade-chk" class="w-4 h-4 text-rose-600 rounded border-slate-300 mt-0.5">
                <span><b>Eliminar también el Viaje y Presupuesto asociado</b></span>
            </label>
        </div>
    `;

    const confirmed = await showConfirmModal(
        "Eliminar Factura",
        messageHtml,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar Factura",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    const deleteCascade = !!document.getElementById('del-viaje-cascade-chk')?.checked;

    showLoading("Eliminando Factura", `Eliminando ${iid} y revirtiendo movimientos...`);
    try {
        const res = await fetch('/api/ingresos/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: iid, delete_viaje_cascade: deleteCascade })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (typeof loadFacturacionData === 'function') await loadFacturacionData();
            if (typeof loadIngresosData === 'function') await loadIngresosData();
            if (typeof loadViajesData === 'function') await loadViajesData();
            if (typeof loadPresupuestosData === 'function') await loadPresupuestosData();
            if (typeof loadChequesData === 'function') await loadChequesData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            if (typeof loadCuentasCorrientesData === 'function') await loadCuentasCorrientesData();
            showToast(json.message || `Factura ${iid} eliminada correctamente.`);
        } else {
            showToast("Error al eliminar factura: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error de conexión al eliminar la factura.", "error");
    } finally {
        hideLoading();
    }
}

// ==================== CARGAR FACTURA DIRECTA / HISTÓRICA ====================
function openNuevaFacturaDirectaModal() {
    const form = document.getElementById('form-factura-directa');
    if (form) form.reset();

    const todayStr = new Date().toISOString().split('T')[0];
    const fFecha = document.getElementById('fd-fecha');
    if (fFecha) fFecha.value = todayStr;

    const fCobro = document.getElementById('fd-fecha-cobro');
    if (fCobro) fCobro.value = todayStr;

    const fTipo = document.getElementById('fd-tipo');
    if (fTipo) fTipo.value = 'Factura A';

    const fIvaPct = document.getElementById('fd-iva-pct');
    if (fIvaPct) fIvaPct.value = '21';

    const fEstadoCobro = document.getElementById('fd-estado-cobro');
    if (fEstadoCobro) fEstadoCobro.value = 'PENDIENTE';

    const fPreSaldo = document.getElementById('fd-pre-saldo-chk');
    if (fPreSaldo) fPreSaldo.checked = true; // Por defecto protegido para no alterar saldo inicial

    const fCrearViaje = document.getElementById('fd-crear-viaje');
    if (fCrearViaje) fCrearViaje.checked = false;

    // Toggle sections visibility
    toggleFacturaDirectaViajeSection();
    toggleFacturaDirectaCobroSection();

    // Populate dropdowns from masterLists
    if (window.masterLists && typeof populateSelect === 'function') {
        if (window.masterLists.clientes) populateSelect('fd-cliente', window.masterLists.clientes, 'Seleccionar Cliente...');
        if (window.masterLists.empleados) populateSelect('fd-chofer', window.masterLists.empleados, 'Seleccionar Chofer (Opcional)...');
        if (window.masterLists.unidades) {
            populateSelect('fd-unidad', window.masterLists.unidades, 'Seleccionar Unidad (Opcional)...');
            const uSelect = document.getElementById('fd-unidad');
            if (uSelect && !uSelect.querySelector('option[value="Sin Unidad"]')) {
                const optSin = document.createElement('option');
                optSin.value = 'Sin Unidad';
                optSin.textContent = '🚫 Sin Unidad / Solo Operario';
                uSelect.insertBefore(optSin, uSelect.children[1] || null);
            }
        }
        
        const ctaSel = document.getElementById('fd-cuenta-cobro');
        if (ctaSel && window.masterLists.cuentas_tesoreria) {
            const liquidAccs = window.masterLists.cuentas_tesoreria.filter(a => a.tipo !== 'Cheques');
            ctaSel.innerHTML = liquidAccs.map(a => `<option value="${a.nombre}">${a.nombre} (${a.tipo})</option>`).join('');
        }
    }

    calcFacturaDirectaTotal();
    openModal('modal-factura-directa');
}

function calcFacturaDirectaTotal() {
    const neto = parseFloat(document.getElementById('fd-neto')?.value) || 0.0;
    const pct = parseFloat(document.getElementById('fd-iva-pct')?.value) || 0.0;
    const ivaAmt = Math.round(neto * (pct / 100.0) * 100) / 100;
    const total = Math.round((neto + ivaAmt) * 100) / 100;

    const ivaEl = document.getElementById('fd-iva-calc');
    const totEl = document.getElementById('fd-total-calc');

    if (ivaEl) ivaEl.innerText = typeof formatARS === 'function' ? formatARS(ivaAmt) : `$${ivaAmt.toFixed(2)}`;
    if (totEl) totEl.innerText = typeof formatARS === 'function' ? formatARS(total) : `$${total.toFixed(2)}`;
}

function toggleFacturaDirectaViajeSection() {
    const chk = document.getElementById('fd-crear-viaje');
    const sec = document.getElementById('fd-viaje-section');
    if (!sec) return;
    if (chk && chk.checked) {
        sec.classList.remove('hidden');
    } else {
        sec.classList.add('hidden');
    }
}

function toggleFacturaDirectaCobroSection() {
    const est = document.getElementById('fd-estado-cobro')?.value;
    const sec = document.getElementById('fd-cobro-section');
    if (!sec) return;
    if (est === 'COBRADO') {
        sec.classList.remove('hidden');
    } else {
        sec.classList.add('hidden');
    }
}

async function submitNuevaFacturaDirecta(e) {
    e.preventDefault();

    const cliente = (document.getElementById('fd-cliente')?.value || '').trim();
    const tipo = (document.getElementById('fd-tipo')?.value || 'Factura A').trim();
    const nro = (document.getElementById('fd-nro')?.value || '').trim().toUpperCase();
    const fecha = document.getElementById('fd-fecha')?.value || '';
    const actividad = (document.getElementById('fd-actividad')?.value || '').trim() || 'Facturación Directa';
    const neto = parseFloat(document.getElementById('fd-neto')?.value) || 0.0;
    const iva_pct = parseFloat(document.getElementById('fd-iva-pct')?.value) || 0.0;
    const obs = (document.getElementById('fd-obs')?.value || '').trim();

    if (!cliente) {
        showToast("Por favor seleccione un cliente.", "error");
        return;
    }
    if (!nro) {
        showToast("Por favor ingrese el N° de factura ARCA.", "error");
        return;
    }
    if (!fecha) {
        showToast("Por favor ingrese la fecha de emisión.", "error");
        return;
    }
    if (neto <= 0) {
        showToast("El importe neto debe ser mayor a 0.", "error");
        return;
    }

    const crearViaje = !!document.getElementById('fd-crear-viaje')?.checked;
    const chofer = (document.getElementById('fd-chofer')?.value || '').trim();
    const unidad = (document.getElementById('fd-unidad')?.value || '').trim();
    const origen = (document.getElementById('fd-origen')?.value || '').trim();
    const destino = (document.getElementById('fd-destino')?.value || '').trim();
    const remito = (document.getElementById('fd-remito')?.value || '').trim();
    const km = (document.getElementById('fd-km')?.value || '').trim();

    const yaCobrado = document.getElementById('fd-estado-cobro')?.value === 'COBRADO';
    const fechaCobro = document.getElementById('fd-fecha-cobro')?.value || fecha;
    const medioCobro = document.getElementById('fd-cuenta-cobro')?.value || 'Banco Córdoba';
    // Si pre-saldo está marcado, impacta_tesoreria = false (protección de tesorería activada)
    const preSaldoChecked = !!document.getElementById('fd-pre-saldo-chk')?.checked;
    const impactaTesoreria = yaCobrado ? !preSaldoChecked : false;

    const payload = {
        cliente: cliente,
        tipo_comprobante: tipo,
        nro_factura: nro,
        fecha_emision: fecha,
        actividad: actividad,
        neto: neto,
        iva_pct: iva_pct,
        observaciones: obs,
        crear_viaje: crearViaje,
        chofer: chofer,
        unidad: (unidad && unidad.toUpperCase() !== 'SIN UNIDAD') ? unidad : (chofer ? 'Sin Unidad' : 'POR ASIGNAR'),
        origen: origen,
        destino: destino,
        remito: remito,
        km_hs: km,
        ya_cobrado: yaCobrado,
        estado_cobro: yaCobrado ? 'COBRADO' : 'Pendiente de Cobro',
        fecha_cobro: yaCobrado ? fechaCobro : '',
        medio_cobro: yaCobrado ? medioCobro : '',
        impacta_tesoreria: impactaTesoreria
    };

    showLoading("Guardando Factura", "Registrando comprobante y sincronizando datos...");
    try {
        const res = await fetch('/api/ingresos/factura/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-factura-directa');
            if (typeof loadFacturacionData === 'function') await loadFacturacionData();
            if (typeof loadIngresosData === 'function') await loadIngresosData();
            if (crearViaje && typeof loadViajesData === 'function') await loadViajesData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            showToast(json.message || `Factura ${nro} registrada exitosamente.`);
        } else {
            showToast("Error al guardar factura: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error de conexión al guardar la factura.", "error");
    } finally {
        hideLoading();
    }
}


