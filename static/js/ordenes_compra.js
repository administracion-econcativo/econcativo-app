/**
 * ECONCATIVO - Órdenes de Compra Module
 */
// ÓRDENES DE COMPRA LOGIC
let currentOrdenesCompraData = [];
let ordenesFilterDebounceTimer = null;
let lastOrdenesQueryActive = false;

function showOrdenesCompraLoader() {
    const tbody = document.getElementById('tbody-ordenes');
    const counter = document.getElementById('counter-ordenes');
    if (counter) counter.innerText = 'Cargando...';
    if (!tbody) return;
    tbody.innerHTML = `
        <tr>
            <td colspan="8" class="py-24 text-center">
                <div class="flex flex-col items-center justify-center gap-3">
                    <div class="relative w-10 h-10">
                        <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                        <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                    </div>
                    <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                        Cargando órdenes de compra...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

function populateOrdenesCompraMesAnioSelect() {
    // Reemplazado por selector de fecha Desde y Hasta
}

function clearOrdenesCompraDateFilter() {
    resetTablePaginationPage('ordenes');
    const d = document.getElementById('filter-ord-desde');
    const h = document.getElementById('filter-ord-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    filterOrdenesCompraTable(120, true);
}

function resetOrdenesCompraFilters() {
    resetTablePaginationPage('ordenes');
    const s = document.getElementById('search-ordenes');
    const d = document.getElementById('filter-ord-desde');
    const h = document.getElementById('filter-ord-hasta');
    const prov = document.getElementById('filter-ord-proveedor');
    const tipo = document.getElementById('filter-ord-tipo');
    const est = document.getElementById('filter-ord-estado');
    if (s) s.value = '';
    if (d) d.value = '';
    if (h) h.value = '';
    if (prov) {
        prov.value = '';
        if (prov._searchableSelect) prov._searchableSelect.syncValue();
    }
    if (tipo) tipo.value = '';
    if (est) est.value = '';
    lastOrdenesQueryActive = false;
    filterOrdenesCompraTable(120, true);
}

async function loadOrdenesCompraData() {
    populateOrdenesCompraMesAnioSelect();
    showOrdenesCompraLoader();
    try {
        const res = await fetch(`/api/ordenes_compra?_t=${Date.now()}`);
        const json = await res.json();
        if (json.status !== 'success' || !json.data || !json.data.length) {
            const tbody = document.getElementById('tbody-ordenes');
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-400">No hay órdenes de compra registradas.</td></tr>`;
            renderPaginationBar('ordenes', 'pagination-ordenes', { totalItems: 0 });
            return;
        }

        currentOrdenesCompraData = json.data || [];
        updateOrdenesCompraTipoFilter(currentOrdenesCompraData);
        applyOrdenesCompraFilter();
    } catch (err) {
        console.error("Error al cargar órdenes de compra:", err);
    }
}

function updateOrdenesCompraTipoFilter(rows) {
    const sel = document.getElementById('filter-ord-tipo');
    if (!sel) return;
    const currVal = sel.value;
    const typesFromData = (rows || []).map(r => str(r['Tipo insumo'] || r['Tipo de insumo']).trim()).filter(Boolean);
    const masterCats = (window.masterLists && window.masterLists.categorias) || (typeof masterLists !== 'undefined' && masterLists.categorias) || [];
    const allTypes = [...new Set([...masterCats, ...typesFromData])].sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
    
    sel.innerHTML = `<option value="">Todos los Insumos / Rubros</option>` +
        allTypes.map(t => `<option value="${t}">${t}</option>`).join('');
    if (currVal && Array.from(sel.options).some(o => o.value.toLowerCase() === currVal.toLowerCase())) {
        sel.value = currVal;
    }
}

function updateOrdenesCompraKPIs(data) {
    const totalCount = data.length;
    let sumTotal = 0;
    let sumPendiente = 0;
    let sumPagado = 0;

    data.forEach(r => {
        const tot = parseFloat(r['Total'] || 0);
        sumTotal += tot;
        const est = (r['Estado'] || '').toLowerCase();
        if (est === 'pagado') {
            sumPagado += tot;
        } else {
            sumPendiente += tot;
        }
    });

    const elCount = document.getElementById('card-ord-count');
    const elTotal = document.getElementById('card-ord-total');
    const elPend = document.getElementById('card-ord-pendiente');
    const elPag = document.getElementById('card-ord-pagado');
    const elCounter = document.getElementById('counter-ordenes');

    if (elCount) elCount.innerText = totalCount;
    if (elTotal) elTotal.innerText = formatARS(sumTotal);
    if (elPend) elPend.innerText = formatARS(sumPendiente);
    if (elPag) elPag.innerText = formatARS(sumPagado);
    if (elCounter) elCounter.innerText = `${totalCount} orden(es)`;
}

async function toggleMedioPagoOrdenCompra() {
    const formaEl = document.getElementById('o-forma-pago');
    if (!formaEl) return;
    const forma = formaEl.value;
    const container = document.getElementById('o-cheque-container');
    const chequeSel = document.getElementById('o-cheque-id');
    const ctaContainer = document.getElementById('o-cuenta-tesoreria-container');
    const ctaSel = document.getElementById('o-cuenta-tesoreria');
    const ctaLabel = document.getElementById('lbl-o-cuenta-tesoreria');

    const isCheque = forma.toLowerCase().includes('cheque') || forma.toLowerCase().includes('e-cheq');
    const isTransferencia = forma.toLowerCase().includes('transferencia');
    const isEfectivo = forma.toLowerCase().includes('contado') || forma.toLowerCase().includes('efectivo');

    if (isCheque) {
        if (container) container.classList.remove('hidden');
        if (chequeSel) chequeSel.required = true;
        if (ctaContainer) ctaContainer.classList.add('hidden');
        if (ctaSel) {
            ctaSel.required = false;
            ctaSel.value = '';
        }

        if (chequeSel) {
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
                } else {
                    chequeSel.innerHTML = `<option value="">No hay cheques disponibles en cartera</option>`;
                }
            } catch (err) {
                console.error("Error al cargar cheques disponibles:", err);
                chequeSel.innerHTML = `<option value="">Error al cargar cheques</option>`;
            }
        }
    } else if (isTransferencia || isEfectivo) {
        if (container) container.classList.add('hidden');
        if (chequeSel) {
            chequeSel.required = false;
            chequeSel.value = '';
        }
        if (ctaContainer) ctaContainer.classList.remove('hidden');
        if (ctaSel) {
            ctaSel.required = true;
            const allAccs = (window.masterLists && window.masterLists.cuentas_tesoreria && window.masterLists.cuentas_tesoreria.length)
                ? window.masterLists.cuentas_tesoreria
                : ((typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length) ? currentTesoreriaAccounts : []);
            let filteredAccs = allAccs.filter(a => a.tipo !== 'Cheques');
            if (isTransferencia) {
                const bAccs = filteredAccs.filter(a => a.tipo === 'Banco' || a.tipo === 'Billetera');
                if (bAccs.length) filteredAccs = bAccs;
                if (ctaLabel) ctaLabel.innerHTML = `<i class="fa-solid fa-building-columns text-navy mr-1"></i> Seleccionar Cuenta Bancaria de Origen *`;
            } else {
                const cAccs = filteredAccs.filter(a => a.tipo === 'Efectivo');
                if (cAccs.length) filteredAccs = cAccs;
                if (ctaLabel) ctaLabel.innerHTML = `<i class="fa-solid fa-money-bill-wave text-emerald-600 mr-1"></i> Seleccionar Caja / Cuenta de Efectivo de Origen *`;
            }
            const curr = ctaSel.value;
            ctaSel.innerHTML = filteredAccs.map(a => `<option value="${a.nombre}">${a.nombre} (${a.tipo})</option>`).join('');
            if (curr && Array.from(ctaSel.options).some(o => o.value === curr)) ctaSel.value = curr;
        }
    } else {
        if (container) container.classList.add('hidden');
        if (chequeSel) {
            chequeSel.required = false;
            chequeSel.value = '';
        }
        if (ctaContainer) ctaContainer.classList.add('hidden');
        if (ctaSel) {
            ctaSel.required = false;
            ctaSel.value = '';
        }
    }
}

function renderOrdenesCompraTable(data) {
    const tbody = document.getElementById('tbody-ordenes');
    if (!tbody) return;

    const sortedData = sortRecordsMostRecent(data, ['Fecha', 'Fecha emisión'], ['ID orden', 'ID']);

    if (!sortedData.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-400">No hay órdenes de compra registradas.</td></tr>`;
        renderPaginationBar('ordenes', 'pagination-ordenes', { totalItems: 0 });
        return;
    }

    paginateAndRender('ordenes', 'pagination-ordenes', sortedData, (pageRows) => {
        tbody.innerHTML = pageRows.map(item => {
        const oid = item['ID orden'];
        const fecha = item['Fecha'] || '-';
        const proveedor = item['Proveedor'] || '-';
        const cuit = item['CUIT proveedor'] || '-';
        const tipoInsumo = item['Tipo insumo'] || 'Insumo';
        const unidad = item['Unidad'] || 'General';
        const detalle = item['Detalle'] || '-';
        const total = parseFloat(item['Total'] || 0);
        const litros = parseFloat(item['Cantidad/Litros'] || item['litros'] || 0);
        const chqId = item['ID cheque'] || item['id_cheque'] || '';
        const nroChq = item['N° cheque'] || item['nro_cheque'] || '';
        const estado = (item['Estado'] || 'Pendiente').toLowerCase();
        const isPagado = estado === 'pagado';

        const badgeLitros = litros > 0 
            ? `<span class="bg-emerald-50 text-emerald-700 font-bold px-1.5 py-0.5 rounded text-[10px] border border-emerald-200 block mt-0.5"><i class="fa-solid fa-gas-pump text-[9px] mr-1"></i>${litros} Litros</span>`
            : '';

        const badgeCheque = (chqId || nroChq) 
            ? `<span class="bg-purple-50 text-purple-900 border border-purple-200 text-[10px] font-bold px-1.5 py-0.5 rounded block mt-0.5" title="Cheque asignado ${chqId}"><i class="fa-solid fa-money-check-dollar text-[9px] text-purple-600 mr-1"></i>Chq ${nroChq || chqId}</span>`
            : '';

        const badgeEstado = isPagado 
            ? `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full inline-flex items-center gap-1"><i class="fa-solid fa-circle-check text-emerald-600"></i> PAGADO</span>`
            : `<span class="bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold px-2.5 py-1 rounded-full inline-flex items-center gap-1"><i class="fa-solid fa-clock text-amber-600"></i> PENDIENTE</span>`;

        const btnPagar = isPagado
            ? `<span class="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded border border-emerald-200" title="Cobrado/Pagado e ingresado en Egresos"><i class="fa-solid fa-check-double"></i> En Egresos</span>`
            : `<button onclick="confirmarPagoOrdenCompra('${oid}')" class="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1 rounded text-[11px] transition-all cursor-pointer shadow-sm" title="Confirmar pago y registrar en Egresos">
                <i class="fa-solid fa-money-bill-transfer"></i> Pagar & Registrar 💸
               </button>`;

        return `
            <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
                <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${oid}</td>
                <td class="px-4 py-3 whitespace-nowrap text-slate-600">${formatDateAR(fecha)}</td>
                <td class="px-4 py-3 font-bold text-slate-800 whitespace-nowrap">
                    ${proveedor} <span class="text-[10px] text-slate-400 font-normal block">${cuit}</span>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                    <span class="bg-blue-50 text-navy font-bold px-2 py-0.5 rounded text-[10px] border border-blue-200">${tipoInsumo}</span>
                    <span class="text-[10px] text-slate-500 block font-mono mt-0.5">${unidad}</span>
                    ${badgeLitros}
                    ${badgeCheque}
                </td>
                <td class="px-4 py-3 max-w-xs truncate text-slate-600" title="${detalle}">${detalle}</td>
                <td class="px-4 py-3 font-black text-navy text-sm whitespace-nowrap">${formatARS(total)}</td>
                <td class="px-4 py-3 whitespace-nowrap">${badgeEstado}</td>
                <td class="px-4 py-3 text-right whitespace-nowrap">
                    <div class="inline-flex items-center justify-end gap-1.5">
                        <a href="/api/ordenes_compra/${oid}/pdf" target="_blank" class="inline-flex items-center gap-1 bg-amber/10 hover:bg-amber/20 text-amber-dark font-bold px-2.5 py-1 rounded text-[11px] transition-all border border-amber/30 cursor-pointer" title="Descargar PDF Orden de Compra">
                            <i class="fa-solid fa-file-pdf text-amber"></i> PDF
                        </a>
                        ${btnPagar}
                        <button onclick="editOrdenCompra('${oid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[11px] transition-all cursor-pointer" title="Editar orden">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="deleteOrdenCompra('${oid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 transition-all cursor-pointer" title="Eliminar orden">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    }, 10);
}

function filterOrdenesCompraTable(delay = 180, isDropdown = false) {
    resetTablePaginationPage('ordenes');
    const rawSearch = (document.getElementById('search-ordenes')?.value || '').trim();
    const isNowActive = rawSearch.length >= 3;

    if (!isDropdown && !isNowActive && !lastOrdenesQueryActive && rawSearch.length > 0) {
        return;
    }

    if (ordenesFilterDebounceTimer) {
        clearTimeout(ordenesFilterDebounceTimer);
    }

    if (delay > 0) {
        showOrdenesCompraLoader();
    }
    lastOrdenesQueryActive = isNowActive;

    ordenesFilterDebounceTimer = setTimeout(() => {
        applyOrdenesCompraFilter();
    }, delay);
}

function applyOrdenesCompraFilter() {
    const rawSearch = (document.getElementById('search-ordenes')?.value || '').trim();
    const qSearch = rawSearch.length >= 3 ? rawSearch.toLowerCase() : '';
    const fProv = (document.getElementById('filter-ord-proveedor')?.value || '').toLowerCase();
    const fTipo = (document.getElementById('filter-ord-tipo')?.value || '').toLowerCase();
    const fEst = (document.getElementById('filter-ord-estado')?.value || '').toLowerCase();
    const fDesde = document.getElementById('filter-ord-desde')?.value || '';
    const fHasta = document.getElementById('filter-ord-hasta')?.value || '';

    const filtered = (currentOrdenesCompraData || []).filter(item => {
        const full = `${item['ID orden']} ${item['Proveedor']} ${item['CUIT proveedor']} ${item['Detalle']} ${item['Tipo insumo']} ${item['Unidad']}`.toLowerCase();
        const prov = (item['Proveedor'] || '').toLowerCase();
        const tipo = (item['Tipo insumo'] || '').toLowerCase();
        const est = (item['Estado'] || '').toLowerCase();

        const matchSearch = !qSearch || full.includes(qSearch);
        const matchProv = !fProv || prov.includes(fProv);
        const matchTipo = !fTipo || tipo.includes(fTipo);
        const matchEst = !fEst || est === fEst;

        if (!matchSearch || !matchProv || !matchTipo || !matchEst) return false;

        if (fDesde || fHasta) {
            const rawDate = item['Fecha'] || item['Fecha emisión'] || '';
            const dateStr = String(rawDate).split('T')[0].split(' ')[0].trim();
            if (dateStr) {
                if (fDesde && dateStr < fDesde) return false;
                if (fHasta && dateStr > fHasta) return false;
            } else {
                return false;
            }
        }

        return true;
    });

    updateOrdenesCompraKPIs(filtered);
    renderOrdenesCompraTable(filtered);
}

function calcOrdenCompraTotal() {
    let neto = parseFloat(document.getElementById('o-neto')?.value || 0);
    if (isNaN(neto) || neto < 0) {
        neto = 0;
        if (document.getElementById('o-neto')) document.getElementById('o-neto').value = '';
    }
    const ivaPct = parseFloat(document.getElementById('o-iva-pct')?.value || 21);
    const total = Math.max(0, neto + (neto * (ivaPct / 100.0)));

    const totalDiv = document.getElementById('o-total-calc');
    if (totalDiv) {
        totalDiv.innerText = formatARS(total);
    }
}

async function submitOrdenCompra(e) {
    e.preventDefault();
    const editId = document.getElementById('o-id-edit').value;
    const rawNeto = parseFloat(document.getElementById('o-neto')?.value || 0);
    if (isNaN(rawNeto) || rawNeto <= 0) {
        showToast("El Subtotal Neto debe ser un monto positivo mayor a $0.", "warning");
        return;
    }
    const rawLitros = parseFloat(document.getElementById('o-litros')?.value || 0);
    if (rawLitros < 0) {
        showToast("La cantidad de litros no puede ser un valor negativo.", "warning");
        return;
    }
    const neto = rawNeto;
    const ivaPct = parseFloat(document.getElementById('o-iva-pct').value || 21);
    const total = Math.max(0, neto + (neto * (ivaPct / 100.0)));
    const chequeId = document.getElementById('o-cheque-id') ? document.getElementById('o-cheque-id').value : '';

    const payload = {
        id: editId || undefined,
        proveedor: document.getElementById('o-proveedor').value,
        fecha: document.getElementById('o-fecha').value || new Date().toISOString().split('T')[0],
        tipo_insumo: document.getElementById('o-tipo-insumo').value,
        unidad: document.getElementById('o-unidad').value,
        litros: Math.max(0, rawLitros),
        detalle: document.getElementById('o-detalle').value,
        neto: neto,
        iva_pct: ivaPct,
        total: total,
        forma_pago: document.getElementById('o-forma-pago').value,
        cheque_id: chequeId,
        cuenta_tesoreria: document.getElementById('o-cuenta-tesoreria')?.value || '',
        observaciones: document.getElementById('o-observaciones').value
    };

    const url = editId ? '/api/ordenes_compra/update' : '/api/ordenes_compra/add';

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-orden-compra');
            document.getElementById('form-orden-compra').reset();
            document.getElementById('o-id-edit').value = '';
            document.getElementById('o-litros').value = '';
            if (document.getElementById('o-cheque-id')) document.getElementById('o-cheque-id').value = '';
            if (document.getElementById('o-cheque-container')) document.getElementById('o-cheque-container').classList.add('hidden');
            await loadOrdenesCompraData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            showToast(editId ? `Órden ${editId} actualizada con éxito.` : `Órden de Compra ${json.id} generada con éxito.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar la orden de compra.", "error");
    }
}

function toggleVueltoAccountSelector() {
    const radioVuelto = document.querySelector('input[name="vuelto_opcion"][value="vuelto_recibido"]');
    const detailsDiv = document.getElementById('pago-vuelto-details');
    if (detailsDiv && radioVuelto) {
        if (radioVuelto.checked) {
            detailsDiv.classList.remove('hidden');
            toggleVueltoMedioFields();
        } else {
            detailsDiv.classList.add('hidden');
        }
    }
}

function toggleVueltoMedioFields() {
    const radioMedio = document.querySelector('input[name="vuelto_medio"]:checked');
    const medio = radioMedio ? radioMedio.value : 'efectivo';

    const efecContainer = document.getElementById('pago-vuelto-efectivo-container');
    const chqContainer = document.getElementById('pago-vuelto-cheque-container');

    const chqBanco = document.getElementById('pago-vuelto-chq-banco');
    const chqNro = document.getElementById('pago-vuelto-chq-nro');
    const chqEmisor = document.getElementById('pago-vuelto-chq-emisor');
    const chqVenc = document.getElementById('pago-vuelto-chq-vencimiento');

    if (medio === 'cheque') {
        if (efecContainer) efecContainer.classList.add('hidden');
        if (chqContainer) chqContainer.classList.remove('hidden');

        if (chqBanco) chqBanco.required = true;
        if (chqNro) chqNro.required = true;
        if (chqVenc) {
            chqVenc.required = true;
            if (!chqVenc.value) chqVenc.value = new Date().toISOString().split('T')[0];
        }

        const currentProv = document.getElementById('pago-proveedor-lbl')?.innerText || '';
        if (chqEmisor && !chqEmisor.value && currentProv && currentProv !== '-') {
            chqEmisor.value = currentProv;
        }
    } else {
        if (efecContainer) efecContainer.classList.remove('hidden');
        if (chqContainer) chqContainer.classList.add('hidden');

        if (chqBanco) { chqBanco.required = false; chqBanco.value = ''; }
        if (chqNro) { chqNro.required = false; chqNro.value = ''; }
        if (chqEmisor) { chqEmisor.required = false; chqEmisor.value = ''; }
        if (chqVenc) { chqVenc.required = false; chqVenc.value = ''; }
    }
}

async function confirmarPagoOrdenCompra(oid) {
    const item = (currentOrdenesCompraData || []).find(r => (r['ID orden'] || r.id) === oid);
    if (!item) {
        showToast("No se encontró la órden de compra especificada.", "error");
        return;
    }

    const prov = item['Proveedor'] || '-';
    const totalOrden = parseFloat(item['Total'] || item.total || 0);
    const medioPago = item['Forma pago'] || item['Medio de Pago'] || 'Efectivo / Transferencia';
    const chqId = item['ID cheque'] || item['id_cheque'] || '';

    // Populate Modal Labels
    document.getElementById('pago-oid').value = oid;
    document.getElementById('pago-oid-lbl').innerText = `#${oid}`;
    document.getElementById('pago-proveedor-lbl').innerText = prov;
    document.getElementById('pago-monto-orden-lbl').innerText = formatARS(totalOrden);
    document.getElementById('pago-monto-orden-lbl2').innerText = formatARS(totalOrden);
    document.getElementById('pago-medio-lbl').innerText = chqId ? `Cheque ID: ${chqId}` : medioPago;

    // Find CBU / ALIAS of Provider
    const provList = (typeof masterLists !== 'undefined' && masterLists.proveedores) || [];
    const provObj = provList.find(p => getRowProp(p, ['Razón social', 'Razón Social / Nombre', 'Nombre', 'Razón social']).toLowerCase().trim() === prov.toLowerCase().trim());
    const cbuVal = provObj ? getRowProp(provObj, ['CBU / ALIAS', 'CBU/ALIAS', 'CBU', 'ALIAS']) : '';
    const elCbu = document.getElementById('pago-cbu-lbl');
    if (elCbu) {
        elCbu.innerText = cbuVal ? cbuVal : 'Sin CBU / ALIAS registrado';
    }

    // Check assigned cheque details & bank account
    let chequeMonto = 0;
    let chqNum = item['Nro cheque'] || item['nro_cheque'] || '';
    let chqBank = '';

    let chequesList = (typeof globalChequesData !== 'undefined' && globalChequesData.length > 0) ? globalChequesData : (typeof currentChequesData !== 'undefined' ? currentChequesData : []);
    if (!chequesList.length) {
        try {
            const chqRes = await fetch(`/api/cheques?_t=${Date.now()}`);
            const chqJson = await chqRes.json();
            if (chqJson.status === 'success' && chqJson.data) {
                chequesList = chqJson.data;
                globalChequesData = chequesList;
            }
        } catch (e) {}
    }

    if (chqId && chequesList.length > 0) {
        const chqObj = chequesList.find(c => String(c.id || c['ID cheque'] || '').trim().toLowerCase() === String(chqId).trim().toLowerCase());
        if (chqObj) {
            chequeMonto = parseFloat(chqObj.monto || chqObj['Monto ($)'] || 0);
            if (!chqNum) chqNum = chqObj.nro_cheque || chqObj['N° Cheque'] || chqObj.numero || '';
            chqBank = chqObj.banco || chqObj['Banco / Origen'] || chqObj['Banco'] || chqObj.destino || '';
        }
    }

    if (!chqBank && medioPago) {
        chqBank = medioPago;
    }

    // Toggle Treasury Account Selection: Hide when paid via cheque
    const isChequePayment = Boolean(chqId || (medioPago && medioPago.toLowerCase().includes('cheque')));
    const cuentaOrigenContainer = document.getElementById('pago-cuenta-origen-container');
    const cuentaOrigenSelect = document.getElementById('pago-cuenta-origen');
    const cuentaInfoBox = document.getElementById('pago-cuenta-origen-info');
    const cuentaBankNameLbl = document.getElementById('pago-cuenta-origen-bank-name');

    if (cuentaOrigenContainer && cuentaOrigenSelect) {
        if (isChequePayment) {
            cuentaOrigenContainer.classList.add('hidden');
            cuentaOrigenSelect.required = false;
        } else {
            cuentaOrigenContainer.classList.remove('hidden');
            cuentaOrigenSelect.required = true;

            // Ensure options are populated from currentTesoreriaAccounts
            if (typeof currentTesoreriaAccounts === 'undefined' || !currentTesoreriaAccounts || currentTesoreriaAccounts.length === 0) {
                try {
                    const tRes = await fetch(`/api/tesoreria/summary?_t=${Date.now()}`);
                    const tJson = await tRes.json();
                    if (tJson.status === 'success' && tJson.accounts) {
                        currentTesoreriaAccounts = tJson.accounts;
                    }
                } catch (e) {}
            }

            if (typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts && currentTesoreriaAccounts.length > 0) {
                const accs = currentTesoreriaAccounts.filter(a => a.tipo !== 'Cheques');
                cuentaOrigenSelect.innerHTML = accs.map(a => `<option value="${a.nombre}">${a.nombre}</option>`).join('');
            }

            if (chqBank && cuentaOrigenSelect.options.length > 0) {
                const bankLower = chqBank.toLowerCase();
                let matchedOpt = Array.from(cuentaOrigenSelect.options).find(opt => {
                    const optLower = opt.value.toLowerCase();
                    if (bankLower.includes('galicia') && optLower.includes('galicia')) return true;
                    if (bankLower.includes('santander') && optLower.includes('santander')) return true;
                    if (bankLower.includes('efectivo') && optLower.includes('efectivo')) return true;
                    const cleanBank = bankLower.replace(/cta|cte|cuenta|corriente|banco/g, '').trim();
                    return cleanBank.length >= 3 && optLower.includes(cleanBank);
                });

                if (matchedOpt) {
                    cuentaOrigenSelect.value = matchedOpt.value;
                    if (cuentaInfoBox && cuentaBankNameLbl) {
                        cuentaBankNameLbl.innerText = matchedOpt.value;
                        cuentaInfoBox.classList.remove('hidden');
                    }
                } else if (cuentaInfoBox) {
                    cuentaInfoBox.classList.add('hidden');
                }
            } else if (cuentaInfoBox) {
                cuentaInfoBox.classList.add('hidden');
            }
        }
    }

    const overpayBox = document.getElementById('pago-overpay-box');
    const radioSaldoFavor = document.querySelector('input[name="vuelto_opcion"][value="saldo_favor"]');
    if (radioSaldoFavor) radioSaldoFavor.checked = true;
    
    // Reset radio vuelto_medio to efectivo by default
    const radioMedioEfec = document.querySelector('input[name="vuelto_medio"][value="efectivo"]');
    if (radioMedioEfec) radioMedioEfec.checked = true;

    toggleVueltoAccountSelector();

    if (chequeMonto > totalOrden) {
        const dif = chequeMonto - totalOrden;
        document.getElementById('pago-medio-lbl').innerText = `Cheque N° ${chqNum || chqId} (${formatARS(chequeMonto)})`;
        document.getElementById('pago-monto-cheque-lbl').innerText = formatARS(chequeMonto);
        document.getElementById('pago-monto-excedente-lbl').innerText = formatARS(dif);
        document.getElementById('pago-vuelto-monto').value = dif.toFixed(2);
        
        const vCuentaSelect = document.getElementById('pago-vuelto-cuenta');
        if (vCuentaSelect && typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts) {
            const accs = currentTesoreriaAccounts.filter(a => a.tipo !== 'Cheques');
            vCuentaSelect.innerHTML = accs.map(a => `<option value="${a.nombre}">${a.nombre}</option>`).join('');
        }

        overpayBox.classList.remove('hidden');
    } else {
        overpayBox.classList.add('hidden');
    }

    // Check provider credit balance (Saldo a Favor C/C)
    const sfBox = document.getElementById('container-pago-saldo-favor');
    const sfAmtLbl = document.getElementById('pago-disp-saldo-favor-amt');
    const sfMsgLbl = document.getElementById('pago-saldo-favor-detail-msg');

    if (sfBox) {
        sfBox.classList.add('hidden');
        if (prov && prov !== '-') {
            try {
                const provRes = await fetch(`/api/proveedores/saldo/${encodeURIComponent(prov)}`);
                const provJson = await provRes.json();
                if (provJson.status === 'success' && provJson.saldo_favor > 0.01) {
                    const sfVal = provJson.saldo_favor;
                    if (sfAmtLbl) sfAmtLbl.innerText = formatARS(sfVal);
                    if (sfMsgLbl) {
                        if (totalOrden <= sfVal) {
                            sfMsgLbl.innerHTML = `💡 <strong>Tu Saldo a Favor de ${formatARS(sfVal)} cubre el 100% de esta órden (${formatARS(totalOrden)}).</strong> No necesitás desembolsar dinero en efectivo ni transferencia. La cuenta corriente la compensará automáticamente.`;
                        } else {
                            const netDif = totalOrden - sfVal;
                            sfMsgLbl.innerHTML = `💡 <strong>Tu Saldo a Favor de ${formatARS(sfVal)} absorbe parte de esta órden (${formatARS(totalOrden)}).</strong> El saldo neto a abonar hoy es únicamente de <strong>${formatARS(netDif)}</strong>.`;
                        }
                    }
                    sfBox.classList.remove('hidden');
                }
            } catch (e) {
                console.error("Error al verificar saldo a favor del proveedor:", e);
            }
        }
    }

    openModal('modal-confirmar-pago-orden');
}

async function submitConfirmarPagoOrden(e) {
    e.preventDefault();
    const oid = document.getElementById('pago-oid').value;
    if (!oid) return;

    const radioVuelto = document.querySelector('input[name="vuelto_opcion"]:checked');
    const vueltoOpcion = radioVuelto ? radioVuelto.value : 'saldo_favor';
    const vueltoMonto = parseFloat(document.getElementById('pago-vuelto-monto')?.value || 0);
    const vueltoCuenta = document.getElementById('pago-vuelto-cuenta')?.value || 'Caja Chica Efectivo';

    const radioMedio = document.querySelector('input[name="vuelto_medio"]:checked');
    const vueltoMedio = radioMedio ? radioMedio.value : 'efectivo';

    const vueltoChqBanco = document.getElementById('pago-vuelto-chq-banco')?.value || '';
    const vueltoChqNro = document.getElementById('pago-vuelto-chq-nro')?.value || '';
    const vueltoChqEmisor = document.getElementById('pago-vuelto-chq-emisor')?.value || '';
    const vueltoChqVencimiento = document.getElementById('pago-vuelto-chq-vencimiento')?.value || '';

    const cuentaOrigenContainer = document.getElementById('pago-cuenta-origen-container');
    const isOrigenHidden = cuentaOrigenContainer && cuentaOrigenContainer.classList.contains('hidden');
    const cuentaOrigen = isOrigenHidden ? '' : (document.getElementById('pago-cuenta-origen')?.value || '');

    const payload = {
        id: oid,
        vuelto_opcion: vueltoOpcion,
        vuelto_monto: vueltoMonto,
        vuelto_cuenta: vueltoCuenta,
        vuelto_medio: vueltoMedio,
        vuelto_chq_banco: vueltoChqBanco,
        vuelto_chq_nro: vueltoChqNro,
        vuelto_chq_emisor: vueltoChqEmisor,
        vuelto_chq_vencimiento: vueltoChqVencimiento,
        cuenta_origen: cuentaOrigen
    };

    try {
        const res = await fetch('/api/ordenes_compra/confirmar_pago', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-confirmar-pago-orden');
            await loadOrdenesCompraData();
            await loadEgresosData();
            await loadChequesData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            if (typeof loadMaestrosData === 'function') await loadMaestrosData();
            await loadDashboardData();
            showToast(`¡Pago de Órden ${oid} confirmado con éxito!`);
        } else {
            const alertEl = document.getElementById('alert-oc-fondos');
            if (alertEl) {
                alertEl.classList.remove('hidden');
                alertEl.innerHTML = `
                    <div class="flex items-start gap-2.5">
                        <i class="fa-solid fa-circle-exclamation text-rose-600 text-lg shrink-0 mt-0.5 animate-bounce"></i>
                        <div>
                            <div class="font-black text-rose-900 text-xs uppercase tracking-wide">⛔ OPERACIÓN BLOQUEADA / FONDOS INSUFICIENTES</div>
                            <div class="text-[11.5px] font-bold text-rose-900 mt-0.5">${json.message || 'Error al procesar el pago de la órden.'}</div>
                            <div class="text-[10.5px] font-medium text-rose-700 mt-1">
                                💡 Cambia la cuenta de tesorería o repón saldo para poder confirmar este pago.
                            </div>
                        </div>
                    </div>
                `;
            }
            showToast("Error: " + (json.message || ''), "error");
        }
    } catch (err) {
        showToast("Error al procesar el pago de la órden.", "error");
    }
}

function openNuevaOrdenCompraModal() {
    const editId = document.getElementById('o-id-edit');
    if (editId) editId.value = '';
    const form = document.getElementById('form-orden-compra');
    if (form) form.reset();
    const title = document.getElementById('modal-o-title');
    if (title) title.innerHTML = `<i class="fa-solid fa-file-circle-plus text-amber"></i> Nueva Órden de Compra`;
    if (document.getElementById('o-fecha')) document.getElementById('o-fecha').value = new Date().toISOString().split('T')[0];
    if (document.getElementById('o-tipo-insumo')) document.getElementById('o-tipo-insumo').value = 'Combustible';
    if (document.getElementById('o-unidad')) document.getElementById('o-unidad').value = 'General';
    if (document.getElementById('o-forma-pago')) document.getElementById('o-forma-pago').value = 'Cuenta Corriente 30 días';
    if (document.getElementById('o-iva-pct')) document.getElementById('o-iva-pct').value = '21';
    toggleMedioPagoOrdenCompra();
    calcOrdenCompraTotal();
    openModal('modal-orden-compra');
}

async function editOrdenCompra(oid) {
    const item = currentOrdenesCompraData.find(r => r['ID orden'] === oid);
    if (!item) return;

    document.getElementById('o-id-edit').value = oid;
    document.getElementById('modal-o-title').innerHTML = `<i class="fa-solid fa-pen-to-square text-amber"></i> Editar Órden de Compra ${oid}`;
    document.getElementById('o-proveedor').value = item['Proveedor'] || '';
    document.getElementById('o-fecha').value = item['Fecha'] || '';
    document.getElementById('o-tipo-insumo').value = item['Tipo insumo'] || 'Combustible';
    const rawUnidad = item['Unidad'] || 'General';
    const oUnidadEl = document.getElementById('o-unidad');
    if (oUnidadEl) {
        oUnidadEl.value = rawUnidad;
        if (!oUnidadEl.value && rawUnidad) {
            const cleanTarget = String(rawUnidad).trim().toUpperCase();
            for (const opt of oUnidadEl.options) {
                const optVal = String(opt.value || '').trim().toUpperCase();
                const optText = String(opt.text || '').trim().toUpperCase();
                if (optVal === cleanTarget || optText === cleanTarget || (optVal && cleanTarget.includes(optVal))) {
                    oUnidadEl.value = opt.value;
                    break;
                }
            }
        }
    }
    document.getElementById('o-litros').value = item['Cantidad/Litros'] || item['litros'] || '';
    document.getElementById('o-detalle').value = item['Detalle'] || '';
    document.getElementById('o-neto').value = item['Neto'] || '';
    document.getElementById('o-iva-pct').value = item['IVA %'] || '21';
    document.getElementById('o-forma-pago').value = item['Forma pago'] || 'Cuenta Corriente 30 días';
    document.getElementById('o-observaciones').value = item['Observaciones'] || '';

    await toggleMedioPagoOrdenCompra();
    const chqId = item['ID cheque'] || item['id_cheque'] || '';
    if (chqId && document.getElementById('o-cheque-id')) {
        document.getElementById('o-cheque-id').value = chqId;
    }

    calcOrdenCompraTotal();
    openModal('modal-orden-compra');
}

async function deleteOrdenCompra(oid) {
    const confirmed = await showConfirmModal(
        "Eliminar Órden de Compra",
        `¿Eliminar la Órden de Compra <b>${oid}</b>? Se eliminará también el egreso asociado si existiera.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Órden de Compra", `Eliminando ${oid} de la base de datos...`);
    try {
        const res = await fetch('/api/ordenes_compra/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: oid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('o-id-edit') && document.getElementById('o-id-edit').value === oid) {
                document.getElementById('o-id-edit').value = '';
                const form = document.getElementById('form-orden-compra');
                if (form) form.reset();
            }
            await loadOrdenesCompraData();
            await loadEgresosData();
            await loadDashboardData();
            showToast(`Órden de Compra ${oid} eliminada.`);
        } else {
            showToast("Error al eliminar: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar la orden de compra.", "error");
    } finally {
        hideLoading();
    }
}

