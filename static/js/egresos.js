/**
 * ECONCATIVO - Egresos & Gastos Operativos Module
 */

let egresosFilterDebounceTimer = null;

function showEgresosLoader() {
    const tbody = document.getElementById('tbody-egresos');
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
                        Cargando egresos y gastos...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadEgresosData() {
    const tbody = document.getElementById('tbody-egresos');
    const counter = document.getElementById('counter-egresos');
    if (counter) counter.innerText = 'Cargando...';

    showEgresosLoader();

    try {
        const res = await fetch(`/api/sheet/EGRESOS?_t=${Date.now()}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.rows.length) {
            currentEgresosData = [];
            renderEgresosTable([]);
            return;
        }

        currentEgresosData = json.rows;
        updateEgresosCategoriaFilter(currentEgresosData);
        applyEgresosFilter();
    } catch (err) {
        console.error("Error al cargar egresos:", err);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-rose-500 font-medium">Error al cargar la lista de egresos.</td></tr>`;
        }
        if (counter) counter.innerText = '0 egresos';
    }
}

function getUnifiedCategoriasList(extraCats = []) {
    try { localStorage.removeItem('custom_egreso_categories'); } catch (e) {}

    const mCats = (window.masterLists && window.masterLists.categorias) || (typeof masterLists !== 'undefined' && masterLists.categorias) || [];
    const dataCats = (typeof currentEgresosData !== 'undefined' && Array.isArray(currentEgresosData))
        ? currentEgresosData.map(r => str(getRowProp(r, ['Categoría'])).trim()).filter(Boolean)
        : [];

    const extra = Array.isArray(extraCats) ? extraCats : [extraCats];
    const unified = [...new Set([...mCats, ...dataCats, ...extra])]
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));

    if (window.masterLists) {
        window.masterLists.categorias = unified;
    }
    if (typeof masterLists !== 'undefined' && masterLists) {
        masterLists.categorias = unified;
    }

    return unified;
}

function updateEgresosCategoriaFilter(rows) {
    const catsFromData = (rows || []).map(r => str(getRowProp(r, ['Categoría'])).trim()).filter(Boolean);
    const allCats = getUnifiedCategoriasList(catsFromData);
    
    // 1. Dropdown filtro en pestaña Egresos
    const filterSel = document.getElementById('filter-egresos-categoria');
    if (filterSel) {
        const currVal = filterSel.value;
        filterSel.innerHTML = `<option value="">Todos los Rubros / Categorías</option>` +
            allCats.map(c => `<option value="${c}">${c}</option>`).join('');
        if (currVal && Array.from(filterSel.options).some(o => o.value.toLowerCase() === currVal.toLowerCase())) {
            filterSel.value = currVal;
        }
    }

    // 2. Select en modal de creación de Egreso (e-categoria) - Sincronizado 100%
    const modalSel = document.getElementById('e-categoria');
    if (modalSel) {
        const currModalVal = modalSel.value;
        modalSel.innerHTML = `<option value="">Seleccionar Categoría...</option>` +
            allCats.map(c => `<option value="${c}">${c}</option>`).join('');
        if (currModalVal && Array.from(modalSel.options).some(o => o.value.toLowerCase() === currModalVal.toLowerCase())) {
            modalSel.value = currModalVal;
        }
    }
}

function clearEgresosDateFilter() {
    resetTablePaginationPage('egresos');
    const d = document.getElementById('filter-egresos-desde');
    const h = document.getElementById('filter-egresos-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    filterEgresosTable(180);
}

function resetEgresosFilters() {
    resetTablePaginationPage('egresos');
    const s = document.getElementById('search-egresos');
    const cat = document.getElementById('filter-egresos-categoria');
    const d = document.getElementById('filter-egresos-desde');
    const h = document.getElementById('filter-egresos-hasta');
    const med = document.getElementById('filter-egresos-medio');
    if (s) s.value = '';
    if (cat) cat.value = '';
    if (d) d.value = '';
    if (h) h.value = '';
    if (med) med.value = '';
    filterEgresosTable(180);
}

function filterEgresosTable(delay = 180) {
    resetTablePaginationPage('egresos');
    if (egresosFilterDebounceTimer) {
        clearTimeout(egresosFilterDebounceTimer);
    }

    showEgresosLoader();

    egresosFilterDebounceTimer = setTimeout(() => {
        applyEgresosFilter();
    }, delay);
}

function applyEgresosFilter() {
    const rawSearch = (document.getElementById('search-egresos')?.value || '').trim();
    const qSearch = rawSearch.length >= 3 ? rawSearch.toLowerCase() : '';
    const catVal = document.getElementById('filter-egresos-categoria')?.value || '';
    const fDesde = document.getElementById('filter-egresos-desde')?.value || '';
    const fHasta = document.getElementById('filter-egresos-hasta')?.value || '';
    const medioVal = (document.getElementById('filter-egresos-medio')?.value || '').toLowerCase().trim();

    const filtered = (currentEgresosData || []).filter(r => {
        // 1. General Text Search
        if (qSearch) {
            const rowText = `${getRowProp(r, ['ID egreso', 'ID'])} ${getRowProp(r, ['Categoría'])} ${getRowProp(r, ['Proveedor'])} ${getRowProp(r, ['Unidad'])} ${getRowProp(r, ['Empleado'])} ${getRowProp(r, ['Descripción'])} ${getRowProp(r, ['Observaciones'])} ${getRowProp(r, ['Forma de Pago', 'Medio de Pago', 'Medio Pago', 'Cuenta Tesorería'])}`.toLowerCase();
            if (!rowText.includes(qSearch)) return false;
        }

        // 2. Category / Rubro Filter
        const rowCat = getRowProp(r, ['Categoría']) || '';
        if (catVal && catVal !== '') {
            if (catVal.toLowerCase() === 'otros') {
                const knownCats = ['combustible', 'reparaciones', 'repuestos', 'seguros', 'telepase', 'cadman', 'comisión a centro de camioneros', 'liquidación de sueldos'];
                if (knownCats.some(k => rowCat.toLowerCase().includes(k))) return false;
            } else {
                if (!rowCat.toLowerCase().includes(catVal.toLowerCase())) return false;
            }
        }

        // 3. Payment Method / Treasury Account Filter
        if (medioVal && medioVal !== '') {
            const rowMedio = str(getRowProp(r, ['Forma de Pago', 'Medio de Pago', 'Medio Pago', 'Cuenta Tesorería'])).toLowerCase();
            const rowObs = str(getRowProp(r, ['Observaciones'])).toLowerCase();
            const fullMedioText = `${rowMedio} ${rowObs}`;
            if (medioVal === 'caja chica efectivo' || medioVal === 'efectivo') {
                if (!fullMedioText.includes('efectivo') && !fullMedioText.includes('caja chica')) return false;
            } else if (!fullMedioText.includes(medioVal)) {
                return false;
            }
        }

        // Parse date for Date Range filtering
        const dateStr = getRowProp(r, ['Fecha comprobante', 'Fecha pago', 'Fecha']) || '';
        let day = null, monthStr = null, yearStr = null;

        if (dateStr) {
            const parts = str(dateStr).split(/[-/]/);
            if (parts.length === 3) {
                if (parts[0].length === 4) {
                    // YYYY-MM-DD format
                    yearStr = parts[0];
                    monthStr = parts[1].padStart(2, '0');
                    day = parseInt(parts[2], 10);
                } else if (parts[2].length === 4) {
                    // DD-MM-YYYY format
                    day = parseInt(parts[0], 10);
                    monthStr = parts[1].padStart(2, '0');
                    yearStr = parts[2];
                }
            }
        }

        // 4. Date Range Filter
        if (fDesde || fHasta) {
            let isoDate = '';
            if (yearStr && monthStr && day !== null) {
                isoDate = `${yearStr}-${monthStr}-${String(day).padStart(2, '0')}`;
            } else if (dateStr) {
                isoDate = str(dateStr).split('T')[0].split(' ')[0];
            }
            if (!isoDate) return false;
            if (fDesde && isoDate < fDesde) return false;
            if (fHasta && isoDate > fHasta) return false;
        }

        return true;
    });

    renderEgresosTable(filtered);
}

function renderEgresosTable(rows) {
    const tbody = document.getElementById('tbody-egresos');
    const counter = document.getElementById('counter-egresos');
    const sumTotalEl = document.getElementById('egresos-sum-total');
    const sumPagadoEl = document.getElementById('egresos-sum-pagado');
    const sumSaldoFavorEl = document.getElementById('egresos-sum-saldo-favor');
    const containerSf = document.getElementById('container-egresos-sum-sf');
    const sumLitrosEl = document.getElementById('egresos-sum-litros');

    const totalComprado = rows.reduce((acc, r) => {
        const val = parseFloat(getRowProp(r, ['Total', 'Importe total', 'Importe'])) || 0;
        return acc + (val > 0 ? val : 0);
    }, 0);

    const totalPagadoReal = rows.reduce((acc, r) => {
        const p = parseFloat(getRowProp(r, ['Importe pagado', 'Pagado']));
        const t = parseFloat(getRowProp(r, ['Total']));
        const m = str(getRowProp(r, ['Forma de Pago', 'Medio de Pago'])).toLowerCase();
        if (!isNaN(p) && p > 0 && (!m.includes('saldo a favor') || m.includes('neto'))) return acc + p;
        if (m.includes('saldo a favor') && !m.includes('neto')) return acc;
        return acc + (t > 0 ? t : 0);
    }, 0);

    const totalSaldoFavorImputado = Math.max(0, totalComprado - totalPagadoReal);
    const totalLitros = rows.reduce((acc, r) => {
        const l = parseFloat(getRowProp(r, ['Cantidad/Litros', 'Litros', 'Cantidad'])) || 0;
        return acc + (l > 0 ? l : 0);
    }, 0);

    if (counter) counter.innerText = `${rows.length} egresos`;
    if (sumTotalEl) sumTotalEl.innerText = formatARS(totalComprado);
    if (sumPagadoEl) sumPagadoEl.innerText = formatARS(totalPagadoReal);
    
    if (sumSaldoFavorEl && containerSf) {
        if (totalSaldoFavorImputado > 0) {
            sumSaldoFavorEl.innerText = formatARS(totalSaldoFavorImputado);
            containerSf.classList.remove('hidden');
        } else {
            containerSf.classList.add('hidden');
        }
    }

    if (sumLitrosEl) sumLitrosEl.innerText = `${totalLitros.toLocaleString('es-AR')} L`;

    if (!tbody) return;

    const sortedRows = sortRecordsMostRecent(rows, ['Fecha comprobante', 'Fecha pago', 'Fecha'], ['ID egreso', 'ID']);

    if (!sortedRows.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400 font-medium">No se encontraron egresos con los filtros seleccionados.</td></tr>`;
        renderPaginationBar('egresos', 'pagination-egresos', { totalItems: 0 });
        return;
    }

    paginateAndRender('egresos', 'pagination-egresos', sortedRows, (pageRows) => {
        tbody.innerHTML = pageRows.map(r => {
        const medioPago = getRowProp(r, ['Medio pago', 'Medio de pago', 'Cuenta tesoreria', 'Cuenta']) || '-';
        let medioIcon = 'fa-building-columns text-slate-500';
        if (medioPago.toLowerCase().includes('efectivo') || medioPago.toLowerCase().includes('caja')) {
            medioIcon = 'fa-money-bill-wave text-emerald-600';
        } else if (medioPago.toLowerCase().includes('cheque')) {
            medioIcon = 'fa-money-check-dollar text-amber-600';
        } else if (medioPago.toLowerCase().includes('banco') || medioPago.toLowerCase().includes('cta')) {
            medioIcon = 'fa-building-columns text-sky-600';
        }

        return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 text-xs transition-all">
            <td class="px-4 py-3 font-bold text-rose-600">${getRowProp(r, ['ID egreso', 'ID']) || '-'}</td>
            <td class="px-4 py-3 text-slate-600 whitespace-nowrap">${formatDateAR(getRowProp(r, ['Fecha comprobante', 'Fecha pago', 'Fecha']))}</td>
            <td class="px-4 py-3 font-semibold text-slate-800"><i class="fa-solid fa-tag text-amber mr-1"></i>${getRowProp(r, ['Categoría']) || '-'}</td>
            <td class="px-4 py-3 text-slate-700 font-medium">${getRowProp(r, ['Proveedor']) || '-'}</td>
            <td class="px-4 py-3 text-slate-500">${getRowProp(r, ['Unidad']) || getRowProp(r, ['Empleado']) || '-'}</td>
            <td class="px-4 py-3 font-medium text-slate-700">
                <span class="inline-flex items-center gap-1.5 bg-slate-100/90 text-slate-800 px-2.5 py-1 rounded-lg text-[11px] font-semibold border border-slate-200 shadow-sm">
                    <i class="fa-solid ${medioIcon}"></i> ${medioPago}
                </span>
            </td>
            <td class="px-4 py-3 font-medium text-slate-700">${getRowProp(r, ['Cantidad/Litros']) ? getRowProp(r, ['Cantidad/Litros']) + ' L' : '-'}</td>
            <td class="px-4 py-3 font-bold text-rose-600">${formatARS(getRowProp(r, ['Total', 'Importe pagado']))}</td>
            <td class="px-4 py-3">
                <span class="px-2.5 py-1 rounded-full text-[10px] font-bold ${strStatusClass(getRowProp(r, ['Estado pago']))}">
                    ${getRowProp(r, ['Estado pago']) || 'Pagado'}
                </span>
            </td>
        </tr>
    `}).join('');
    }, 10);
}


// Form Submissions

let currentEgresoSaldoFavorInfo = { saldoFavor: 0, absorvido: 0, neto: 0 };

function onEgresoTotalInput() {
    const totalInput = document.getElementById('e-total');
    if (totalInput && totalInput.value !== '') {
        const val = parseFloat(totalInput.value);
        if (isNaN(val) || val < 0) {
            totalInput.value = '';
        }
    }
    checkEgresoProveedorSaldoFavor();
    checkEgresoOverpayment();
    checkEgresoTreasuryFundsRealtime();
}

async function checkEgresoProveedorSaldoFavor() {
    const provSelect = document.getElementById('e-proveedor');
    const totalInput = document.getElementById('e-total');
    const sfBox = document.getElementById('container-e-saldo-favor');
    const sfAmtLbl = document.getElementById('e-disp-saldo-favor-amt');
    const breakdownBox = document.getElementById('e-saldo-favor-breakdown');
    const lblTotal = document.getElementById('e-sf-lbl-total');
    const lblAbsorvido = document.getElementById('e-sf-lbl-absorvido');
    const lblNeto = document.getElementById('e-sf-lbl-neto');
    const msgGuidance = document.getElementById('e-sf-msg-guidance');
    const labelCuentaTesoreria = document.getElementById('label-e-cuenta-tesoreria');

    if (!provSelect || !sfBox || !sfAmtLbl) return;

    const provName = provSelect.value || '';
    if (!provName || provName === '') {
        sfBox.classList.add('hidden');
        currentEgresoSaldoFavorInfo = { saldoFavor: 0, absorvido: 0, neto: 0 };
        if (labelCuentaTesoreria) labelCuentaTesoreria.innerHTML = `<i class="fa-solid fa-building-columns text-rose-600 mr-1"></i>Cuenta de Tesorería / Medio de Pago *`;
        return;
    }

    try {
        const res = await fetch(`/api/proveedores/saldo/${encodeURIComponent(provName)}`);
        const json = await res.json();
        if (json.status === 'success' && json.saldo_favor > 0.01) {
            const saldoFavor = json.saldo_favor;
            sfAmtLbl.innerText = formatARS(saldoFavor);
            sfBox.classList.remove('hidden');

            const totalEgreso = parseFloat(totalInput?.value || 0);
            if (totalEgreso > 0) {
                const absorvido = Math.min(totalEgreso, saldoFavor);
                const neto = Math.max(0, totalEgreso - absorvido);
                currentEgresoSaldoFavorInfo = { saldoFavor, absorvido, neto };

                lblTotal.innerText = formatARS(totalEgreso);
                lblAbsorvido.innerText = `-${formatARS(absorvido)}`;
                lblNeto.innerText = formatARS(neto);
                breakdownBox.classList.remove('hidden');

                if (neto === 0) {
                    msgGuidance.innerHTML = `🟢 <strong>Tu Saldo a Favor cubre el 100% de este egreso (${formatARS(totalEgreso)}).</strong> No tenés que ingresar nuevo dinero de Tesorería.`;
                    if (labelCuentaTesoreria) labelCuentaTesoreria.innerHTML = `<i class="fa-solid fa-building-columns text-rose-600 mr-1"></i>Cuenta de Tesorería / Medio de Pago (Cubierto con Saldo a Favor) *`;
                    const eCuentaSelect = document.getElementById('e-cuenta-tesoreria');
                    if (eCuentaSelect && (!eCuentaSelect.value || eCuentaSelect.value === 'Efectivo')) {
                        usarSaldoFavorEgresoDirecto();
                    }
                } else {
                    msgGuidance.innerHTML = `💡 <strong>Tu Saldo a Favor absorbe ${formatARS(absorvido)}.</strong> Únicamente debes desembolsar el remanente de <strong>${formatARS(neto)}</strong> hoy.`;
                    if (labelCuentaTesoreria) labelCuentaTesoreria.innerHTML = `<i class="fa-solid fa-building-columns text-rose-600 mr-1"></i>Cuenta de Tesorería / Medio de Pago (para abonar el remanente de ${formatARS(neto)}) *`;
                }
            } else {
                breakdownBox.classList.add('hidden');
                currentEgresoSaldoFavorInfo = { saldoFavor, absorvido: 0, neto: 0 };
                msgGuidance.innerText = 'Podés usar este crédito previo para abonar este egreso sin ingresar dinero de Tesorería.';
                if (labelCuentaTesoreria) labelCuentaTesoreria.innerHTML = `<i class="fa-solid fa-building-columns text-rose-600 mr-1"></i>Cuenta de Tesorería / Medio de Pago *`;
            }
        } else {
            sfBox.classList.add('hidden');
            currentEgresoSaldoFavorInfo = { saldoFavor: 0, absorvido: 0, neto: 0 };
            if (labelCuentaTesoreria) labelCuentaTesoreria.innerHTML = `<i class="fa-solid fa-building-columns text-rose-600 mr-1"></i>Cuenta de Tesorería / Medio de Pago *`;
        }
    } catch (e) {
        console.error("Error al verificar saldo a favor del proveedor en egresos:", e);
        sfBox.classList.add('hidden');
        currentEgresoSaldoFavorInfo = { saldoFavor: 0, absorvido: 0, neto: 0 };
    }
    checkEgresoTreasuryFundsRealtime();
}

function usarSaldoFavorEgresoDirecto() {
    const sel = document.getElementById('e-cuenta-tesoreria');
    if (!sel) return;

    let sfOpt = Array.from(sel.options).find(o => o.value === 'Saldo a Favor C/C');
    if (!sfOpt) {
        sfOpt = document.createElement('option');
        sfOpt.value = 'Saldo a Favor C/C';
        sfOpt.innerText = '🟢 Saldo a Favor C/C (Crédito Proveedor)';
        sel.appendChild(sfOpt);
    }
    sel.value = 'Saldo a Favor C/C';
    toggleMedioPagoEgresoDirecto();
    showToast("¡Medio de pago asignado como Saldo a Favor C/C!");
}

async function toggleMedioPagoEgresoDirecto() {
    const sel = document.getElementById('e-cuenta-tesoreria');
    const container = document.getElementById('e-cheque-container');
    const chequeSel = document.getElementById('e-cheque-id');
    if (!sel || !container || !chequeSel) return;

    const val = sel.value || '';
    const isCheque = val.toLowerCase().includes('cheque');

    if (isCheque) {
        container.classList.remove('hidden');
        chequeSel.required = true;
        chequeSel.innerHTML = `<option value="">Cargando cheques disponibles...</option>`;
        try {
            const res = await fetch(`/api/cheques/disponibles?_t=${Date.now()}`);
            const json = await res.json();
            if (json.status === 'success' && json.data.length > 0) {
                chequeSel.innerHTML = `<option value="">Seleccionar Cheque de Cartera / Propio...</option>` +
                    json.data.map(c => {
                        const chqId = c.id || c['ID cheque'] || c.ID || '';
                        const banco = c.banco || c['Banco'] || '';
                        const nro = c.nro_cheque || c['N° cheque'] || c['Nro cheque'] || c.nro || '';
                        const monto = c.monto !== undefined ? c.monto : (c['Monto'] || 0);
                        const emisor = c.emisor || c['Emisor/Cliente'] || c['Emisor'] || c.cliente || '';
                        return `<option value="${chqId}" data-monto="${monto}">${chqId} | ${banco} N° ${nro} (${formatARS(monto)}) - Emisor: ${emisor}</option>`;
                    }).join('');
            } else {
                chequeSel.innerHTML = `<option value="">No hay cheques disponibles en cartera</option>`;
            }
        } catch (err) {
            console.error("Error al cargar cheques para egreso directo:", err);
            chequeSel.innerHTML = `<option value="">Error al cargar cheques</option>`;
        }
    } else {
        container.classList.add('hidden');
        chequeSel.required = false;
        chequeSel.value = '';
        checkEgresoOverpayment();
    }

    // Re-evaluar en tiempo real la disponibilidad de fondos para la cuenta seleccionada
    checkEgresoTreasuryFundsRealtime();
}

function checkEgresoOverpayment() {
    const chequeSel = document.getElementById('e-cheque-id');
    const totalInput = document.getElementById('e-total');
    const overpayBox = document.getElementById('e-overpay-box');
    if (!chequeSel || !totalInput || !overpayBox) return;

    const opt = chequeSel.options[chequeSel.selectedIndex];
    const chequeMonto = opt ? parseFloat(opt.getAttribute('data-monto') || 0) : 0;
    const totalEgreso = parseFloat(totalInput.value || 0);

    const targetAmount = (currentEgresoSaldoFavorInfo && currentEgresoSaldoFavorInfo.absorvido > 0)
        ? currentEgresoSaldoFavorInfo.neto
        : totalEgreso;

    const radioSaldoFavor = document.querySelector('input[name="e_vuelto_opcion"][value="saldo_favor"]');
    if (radioSaldoFavor && !document.querySelector('input[name="e_vuelto_opcion"]:checked')) {
        radioSaldoFavor.checked = true;
    }

    toggleEgresoVueltoAccountSelector();

    if (chequeMonto > targetAmount && targetAmount >= 0 && chequeMonto > 0) {
        const dif = chequeMonto - targetAmount;
        document.getElementById('e-monto-cheque-lbl').innerText = formatARS(chequeMonto);
        document.getElementById('e-monto-egreso-lbl').innerText = formatARS(targetAmount);
        document.getElementById('e-monto-excedente-lbl').innerText = formatARS(dif);
        document.getElementById('e-vuelto-monto').value = dif.toFixed(2);

        const vCuentaSelect = document.getElementById('e-vuelto-cuenta');
        if (vCuentaSelect && typeof currentTesoreriaAccounts !== 'undefined') {
            const accs = currentTesoreriaAccounts.filter(a => a.tipo !== 'Cheques');
            vCuentaSelect.innerHTML = accs.map(a => `<option value="${a.nombre}">${a.nombre}</option>`).join('');
        }

        overpayBox.classList.remove('hidden');
    } else {
        overpayBox.classList.add('hidden');
    }
}

function toggleEgresoVueltoAccountSelector() {
    const radioVuelto = document.querySelector('input[name="e_vuelto_opcion"]:checked');
    const isVuelto = radioVuelto && radioVuelto.value === 'vuelto_recibido';
    const detailsBox = document.getElementById('e-vuelto-details');
    if (detailsBox) {
        if (isVuelto) detailsBox.classList.remove('hidden');
        else detailsBox.classList.add('hidden');
    }
}

function toggleEgresoVueltoMedioFields() {
    const radioMedio = document.querySelector('input[name="e_vuelto_medio"]:checked');
    const isCheque = radioMedio && radioMedio.value === 'cheque';
    const chqFields = document.getElementById('e-vuelto-cheque-fields');
    const cuentaContainer = document.getElementById('e-vuelto-cuenta-container');

    if (chqFields) {
        if (isCheque) chqFields.classList.remove('hidden');
        else chqFields.classList.add('hidden');
    }
    if (cuentaContainer) {
        if (isCheque) cuentaContainer.classList.add('hidden');
        else cuentaContainer.classList.remove('hidden');
    }
}

function loadCustomEgresoCategorias() {
    try { localStorage.removeItem('custom_egreso_categories'); } catch (e) {}
    const allCats = getUnifiedCategoriasList();
    
    const targetSelectIds = ['e-categoria', 'filter-egresos-categoria', 'o-tipo-insumo', 'filter-ord-tipo', 'mp-rubro'];
    targetSelectIds.forEach(sId => {
        const sel = document.getElementById(sId);
        if (!sel) return;
        const currVal = sel.value;
        const isFilterEgresos = (sId === 'filter-egresos-categoria');
        const isFilterOrd = (sId === 'filter-ord-tipo');
        const isMpRubro = (sId === 'mp-rubro');
        const placeholder = isFilterEgresos ? 'Todos los Rubros / Categorías' :
                           isFilterOrd ? 'Todos los Insumos / Rubros' :
                           isMpRubro ? 'Seleccione Tipo de Proveedor...' :
                           (sId === 'o-tipo-insumo') ? 'Seleccionar Tipo de Insumo / Rubro...' :
                           'Seleccionar Categoría...';
        const defaultVal = '';
        
        sel.innerHTML = `<option value="${defaultVal}">${placeholder}</option>` +
            allCats.map(c => `<option value="${c}">${c}</option>`).join('');
        if (currVal && Array.from(sel.options).some(o => o.value.toLowerCase() === currVal.toLowerCase())) {
            sel.value = currVal;
        }
    });
}

async function promptAgregarCategoriaEgreso() {
    const nuevaCat = await showPromptModal({
        title: "Nueva Categoría de Gasto",
        message: "Crea una categoría personalizada para clasificar los egresos de la empresa.",
        label: "Nombre de la Categoría *",
        placeholder: "Ej: Alquiler Oficina, Impuestos Municipales, Servicios...",
        iconClass: "fa-solid fa-tags text-rose-600 text-xl",
        confirmText: "Agregar Categoría",
        errorMessage: "Por favor, ingresa el nombre de la categoría."
    });

    if (!nuevaCat || !nuevaCat.trim()) return;

    const nombreCat = nuevaCat.trim();

    // Persistir directamente en backend (Base de Datos Supabase y Excel)
    try {
        const res = await fetch('/api/categorias/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ categoria: nombreCat })
        });
        const json = await res.json();
        if (json.status !== 'success') {
            showToast("Advertencia: No se pudo guardar en base de datos: " + (json.message || ''), "warning");
        }
    } catch (err) {
        console.error("Error al persistir categoría en backend:", err);
    }

    // Recargar maestros desde la base de datos para sincronizar todos los selects de inmediato
    if (typeof loadMasterLists === 'function') {
        await loadMasterLists();
    } else {
        const allCats = getUnifiedCategoriasList([nombreCat]);
        const targetSelectIds = ['e-categoria', 'filter-egresos-categoria', 'o-tipo-insumo', 'filter-ord-tipo', 'mp-rubro'];
        targetSelectIds.forEach(sId => {
            const el = document.getElementById(sId);
            if (el) {
                const placeholder = (sId === 'filter-egresos-categoria') ? 'Todos los Rubros / Categorías' :
                                   (sId === 'filter-ord-tipo') ? 'Todos los Insumos / Rubros' :
                                   (sId === 'mp-rubro') ? 'Seleccione Tipo de Proveedor...' :
                                   (sId === 'o-tipo-insumo') ? 'Seleccionar Tipo de Insumo / Rubro...' :
                                   'Seleccionar Categoría...';

                el.innerHTML = `<option value="">${placeholder}</option>` +
                    allCats.map(c => `<option value="${c}">${c}</option>`).join('');
            }
        });
    }

    const sel = document.getElementById('e-categoria');
    if (sel) {
        sel.value = nombreCat;
        if (typeof onEgresoCategoriaChanged === 'function') onEgresoCategoriaChanged();
    }

    showToast(`¡Categoría "${nombreCat}" guardada en la base de datos y disponible en todos los selectores!`);
}

function onEgresoCategoriaChanged() {
    const catEl = document.getElementById('e-categoria');
    if (!catEl) return;
    const cat = catEl.value;

    const titleTextEl = document.getElementById('modal-e-title-text');
    const iconEl = document.getElementById('modal-e-icon');
    const containerLitros = document.getElementById('container-e-litros');
    const litrosInput = document.getElementById('e-litros');
    const unidadSel = document.getElementById('e-unidad');

    if (titleTextEl) {
        titleTextEl.textContent = `Registrar Egreso: ${cat}`;
    }

    if (iconEl) {
        let iconClass = "fa-solid fa-receipt text-rose-600";
        if (cat === "Combustible") iconClass = "fa-solid fa-gas-pump text-rose-600";
        else if (cat === "Reparaciones") iconClass = "fa-solid fa-wrench text-rose-600";
        else if (cat === "Repuestos") iconClass = "fa-solid fa-gears text-rose-600";
        else if (cat === "Seguros") iconClass = "fa-solid fa-shield-halved text-rose-600";
        else if (cat === "Telepase") iconClass = "fa-solid fa-road text-rose-600";
        else if (cat.includes("Luz")) iconClass = "fa-solid fa-bolt text-rose-600";
        else if (cat.includes("Internet") || cat.includes("Telefonía")) iconClass = "fa-solid fa-wifi text-rose-600";
        else if (cat === "CADMAN") iconClass = "fa-solid fa-building-columns text-rose-600";
        else if (cat.includes("Comisión")) iconClass = "fa-solid fa-handshake text-rose-600";
        iconEl.className = iconClass;
    }

    if (containerLitros) {
        if (cat === "Combustible") {
            containerLitros.classList.remove('hidden');
        } else {
            containerLitros.classList.add('hidden');
            if (litrosInput) litrosInput.value = '';
        }
    }

    const vehicleCategories = ['Combustible', 'Reparaciones', 'Repuestos', 'Seguros', 'Telepase'];
    if (unidadSel) {
        let sinUnidadOpt = Array.from(unidadSel.options).find(opt => opt.value === 'Sin Unidad / Oficina General');
        if (!sinUnidadOpt) {
            const opt = document.createElement('option');
            opt.value = 'Sin Unidad / Oficina General';
            opt.textContent = 'Sin Unidad / Oficina General';
            unidadSel.insertBefore(opt, unidadSel.options[1] || null);
        }

        if (!vehicleCategories.includes(cat)) {
            unidadSel.value = 'Sin Unidad / Oficina General';
        }
    }
}

let cachedTreasuryAccounts = [];

async function checkTreasuryDisponibilidadClientSide(cuentaVal, montoVal, alertId, btnId) {
    const alertEl = document.getElementById(alertId);
    if (!alertEl) return true;

    const monto = parseFloat(montoVal) || 0;
    const cuentaStr = String(cuentaVal || '').trim().toLowerCase();

    if (monto <= 0.01 || !cuentaStr || cuentaStr.includes('saldo a favor') || cuentaStr.includes('cheque')) {
        alertEl.classList.add('hidden');
        alertEl.innerHTML = '';
        if (btnId) {
            const btn = document.getElementById(btnId);
            if (btn) btn.disabled = false;
        }
        return true;
    }

    try {
        if (!cachedTreasuryAccounts || cachedTreasuryAccounts.length === 0) {
            const res = await fetch('/api/tesoreria/summary');
            const data = await res.json();
            if (data.status === 'success' && data.accounts) {
                cachedTreasuryAccounts = data.accounts;
            }
        }
    } catch(e) {}

    let matchedAcc = cachedTreasuryAccounts.find(a => 
        (a.nombre || '').toLowerCase() === cuentaStr || (a.id || '').toLowerCase() === cuentaStr
    );

    if (!matchedAcc) {
        matchedAcc = cachedTreasuryAccounts.find(a => {
            const nombL = (a.nombre || '').toLowerCase();
            return nombL.includes(cuentaStr) || cuentaStr.includes(nombL) ||
                ((cuentaStr.includes('efectivo') || cuentaStr.includes('caja')) && (a.tipo === 'Efectivo' || nombL.includes('caja'))) ||
                (cuentaStr.includes('cordoba') && nombL.includes('cordoba')) ||
                (cuentaStr.includes('galicia') && nombL.includes('galicia')) ||
                (cuentaStr.includes('macro') && nombL.includes('macro')) ||
                (cuentaStr.includes('mercado') && nombL.includes('mercado'));
        });
    }

    if (matchedAcc) {
        const saldoDisp = parseFloat(matchedAcc.saldo_calculado || 0);
        if (monto > saldoDisp) {
            const accName = matchedAcc.nombre || cuentaVal;
            alertEl.classList.remove('hidden');
            alertEl.innerHTML = `
                <div class="flex items-start gap-2.5">
                    <i class="fa-solid fa-triangle-exclamation text-rose-600 text-lg shrink-0 mt-0.5 animate-pulse"></i>
                    <div>
                        <div class="font-black text-rose-900 text-xs uppercase tracking-wide">⛔ FONDOS INSUFICIENTES EN ${accName.toUpperCase()}</div>
                        <div class="text-[11.5px] font-semibold text-rose-800 mt-0.5">
                            La cuenta <strong>"${accName}"</strong> dispone únicamente de <strong class="text-rose-950 font-black">${formatARS(saldoDisp)}</strong>.<br>
                            No puedes realizar un pago/desembolso de <strong class="text-rose-950 font-black">${formatARS(monto)}</strong> porque dejaría la caja/cuenta con saldo negativo en la realidad.
                        </div>
                        <div class="text-[10.5px] font-medium text-rose-700 mt-1">
                            💡 <strong>¿Cómo solucionarlo?</strong> Reduce el monto en efectivo, repón fondos en la caja o selecciona otro medio de pago / cuenta de tesorería.
                        </div>
                    </div>
                </div>
            `;
            if (btnId) {
                const btn = document.getElementById(btnId);
                if (btn) btn.disabled = true;
            }
            return false;
        }
    }

    alertEl.classList.add('hidden');
    alertEl.innerHTML = '';
    if (btnId) {
        const btn = document.getElementById(btnId);
        if (btn) btn.disabled = false;
    }
    return true;
}

function checkEgresoTreasuryFundsRealtime() {
    const cuentaVal = document.getElementById('e-cuenta-tesoreria')?.value || '';
    const totalVal = parseFloat(document.getElementById('e-total')?.value || 0);
    const sfAbsorvido = (currentEgresoSaldoFavorInfo && currentEgresoSaldoFavorInfo.absorvido > 0) ? currentEgresoSaldoFavorInfo.absorvido : 0;
    const netoDesembolso = Math.max(0, totalVal - sfAbsorvido);

    checkTreasuryDisponibilidadClientSide(cuentaVal, netoDesembolso, 'alert-e-fondos', 'btn-submit-egreso');
}

function openNuevoEgresoModal() {
    const form = document.getElementById('form-egreso');
    if (form) form.reset();
    if (document.getElementById('e-fecha')) document.getElementById('e-fecha').value = new Date().toISOString().split('T')[0];
    if (document.getElementById('e-ivapct')) document.getElementById('e-ivapct').value = '21';
    
    // Limpiar alertas de fondos previas y re-habilitar botón de envío
    const alertEl = document.getElementById('alert-e-fondos');
    if (alertEl) {
        alertEl.classList.add('hidden');
        alertEl.innerHTML = '';
    }
    const btnSubmit = document.getElementById('btn-submit-egreso');
    if (btnSubmit) btnSubmit.disabled = false;

    currentEgresoSaldoFavorInfo = { saldoFavor: 0, absorvido: 0, neto: 0 };
    loadCustomEgresoCategorias();
    updateEgresosCategoriaFilter(currentEgresosData);
    onEgresoCategoriaChanged();
    checkEgresoProveedorSaldoFavor();
    toggleMedioPagoEgresoDirecto();
    openModal('modal-egreso');
}

async function submitEgreso(e) {
    e.preventDefault();
    const cuentaTesoreria = document.getElementById('e-cuenta-tesoreria')?.value || '';
    const chequeId = document.getElementById('e-cheque-id')?.value || '';

    const radioVuelto = document.querySelector('input[name="e_vuelto_opcion"]:checked');
    const vueltoOpcion = radioVuelto ? radioVuelto.value : 'saldo_favor';
    const vueltoMonto = parseFloat(document.getElementById('e-vuelto-monto')?.value || 0);
    const vueltoCuenta = document.getElementById('e-vuelto-cuenta')?.value || 'Caja Chica Efectivo';

    const radioMedio = document.querySelector('input[name="e_vuelto_medio"]:checked');
    const vueltoMedio = radioMedio ? radioMedio.value : 'efectivo';

    const vueltoChqBanco = document.getElementById('e-vuelto-chq-banco')?.value || '';
    const vueltoChqNro = document.getElementById('e-vuelto-chq-nro')?.value || '';
    const vueltoChqEmisor = document.getElementById('e-vuelto-chq-emisor')?.value || '';
    const vueltoChqVencimiento = document.getElementById('e-vuelto-chq-vencimiento')?.value || '';

    const totalVal = parseFloat(document.getElementById('e-total')?.value) || 0;
    if (totalVal <= 0) {
        showToast('El importe total del egreso debe ser mayor a 0.', 'error');
        return;
    }

    const litrosRaw = document.getElementById('e-litros')?.value;
    if (litrosRaw !== undefined && litrosRaw !== null && litrosRaw !== '') {
        const litrosVal = parseFloat(litrosRaw);
        if (isNaN(litrosVal) || litrosVal < 0) {
            showToast('La cantidad de litros no puede ser un valor negativo.', 'error');
            return;
        }
    }

    const sfAbsorvido = (currentEgresoSaldoFavorInfo && currentEgresoSaldoFavorInfo.absorvido > 0) ? currentEgresoSaldoFavorInfo.absorvido : 0;
    const sfNeto = (currentEgresoSaldoFavorInfo && currentEgresoSaldoFavorInfo.absorvido > 0) ? currentEgresoSaldoFavorInfo.neto : totalVal;

    const payload = {
        categoria: document.getElementById('e-categoria').value,
        proveedor: document.getElementById('e-proveedor').value,
        unidad: document.getElementById('e-unidad').value,
        cantidad_litros: document.getElementById('e-litros').value,
        total: totalVal,
        cuenta_tesoreria: cuentaTesoreria,
        cheque_id: chequeId,
        saldo_favor_aplicado: sfAbsorvido,
        monto_neto_desembolso: sfNeto,
        opcion_sobrepago: vueltoOpcion,
        vuelto_opcion: vueltoOpcion,
        vuelto_monto: vueltoMonto,
        vuelto_cuenta: vueltoCuenta,
        vuelto_medio: vueltoMedio,
        vuelto_chq_banco: vueltoChqBanco,
        vuelto_chq_nro: vueltoChqNro,
        vuelto_chq_emisor: vueltoChqEmisor,
        vuelto_chq_vencimiento: vueltoChqVencimiento
    };

    const btnSubmit = document.getElementById('btn-submit-egreso');
    const origBtnContent = btnSubmit ? btnSubmit.innerHTML : '<i class="fa-solid fa-floppy-disk"></i> Guardar Egreso';

    try {
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = `<i class="fa-solid fa-spinner animate-spin mr-1"></i> Guardando...`;
        }

        const res = await fetch('/api/egresos/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-egreso');
            cachedTreasuryAccounts = [];

            // Limpiar filtros para garantizar que el nuevo egreso sea inmediatamente visible en la datatable
            const searchInput = document.getElementById('search-egresos');
            if (searchInput) searchInput.value = '';
            const catFilter = document.getElementById('filter-egresos-categoria');
            if (catFilter) catFilter.value = '';
            const mesFilter = document.getElementById('filter-egresos-mes');
            if (mesFilter) mesFilter.value = '';
            const qncFilter = document.getElementById('filter-egresos-quincena');
            if (qncFilter) qncFilter.value = '';
            const medioFilter = document.getElementById('filter-egresos-medio');
            if (medioFilter) medioFilter.value = '';

            await Promise.all([
                loadEgresosData(),
                loadChequesData(),
                typeof loadTesoreriaData === 'function' ? loadTesoreriaData() : Promise.resolve(),
                loadDashboardData()
            ]);
            showToast(`Egreso guardado correctamente (${json.id}).`);
        } else {
            const alertEl = document.getElementById('alert-e-fondos');
            if (alertEl) {
                alertEl.classList.remove('hidden');
                alertEl.innerHTML = `
                    <div class="flex items-start gap-2.5">
                        <i class="fa-solid fa-circle-exclamation text-rose-600 text-lg shrink-0 mt-0.5 animate-bounce"></i>
                        <div>
                            <div class="font-black text-rose-900 text-xs uppercase tracking-wide">⛔ OPERACIÓN BLOQUEADA POR FONDOS INSUFICIENTES</div>
                            <div class="text-[11.5px] font-bold text-rose-900 mt-0.5">${json.message || 'Error al guardar el egreso.'}</div>
                            <div class="text-[10.5px] font-medium text-rose-700 mt-1">
                                💡 Cambia el medio de pago o reduce el monto para poder continuar.
                            </div>
                        </div>
                    </div>
                `;
            }
            showToast("Error: " + (json.message || ''), "error");
        }
    } catch (err) {
        showToast("Error al guardar egreso.", "error");
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = origBtnContent;
        }
    }
}

