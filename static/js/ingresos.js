/**
 * ECONCATIVO - Ingresos, Cobranzas & Comprobantes Module
 */


// INGRESOS TAB DATA & AUDIT TRAIL
function populateIngresosMesAnioSelect() {
    // Reemplazado por selector de fecha Desde y Hasta
}

let ingresosFilterDebounceTimer = null;
let lastIngresosQueryActive = false;

function showIngresosLoader() {
    const tbody = document.getElementById('tbody-ingresos');
    const counter = document.getElementById('counter-ingresos');
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
                        Cargando cobranzas e ingresos...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadIngresosData() {
    populateIngresosMesAnioSelect();
    showIngresosLoader();
    try {
        const res = await fetch(`/api/sheet/INGRESOS?_t=${Date.now()}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.rows.length) {
            document.getElementById('tbody-ingresos').innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No hay cobros registrados en Ingresos.</td></tr>`;
            document.getElementById('counter-ingresos').innerText = '0 registros';
            renderPaginationBar('ingresos', 'pagination-ingresos', { totalItems: 0 });
            currentIngresos = [];
            return;
        }

        const ingresosRows = json.rows.filter(r => {
            const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();
            return st === 'COBRADO' || st === 'PENDIENTE MEDIO DE PAGO' || st.includes('PARCIAL');
        });

        currentIngresos = ingresosRows;
        applyIngresosFilter();

    } catch (err) {
        console.error("Error al cargar ingresos:", err);
    }
}

function renderIngresosTable(rows) {
    const tbody = document.getElementById('tbody-ingresos');
    const counter = document.getElementById('counter-ingresos');
    const sumTotalEl = document.getElementById('ingresos-sum-total');

    if (counter) counter.innerText = `${rows.length} registros`;

    let totalIngresado = 0;
    rows.forEach(r => {
        const total = parseFloat(getRowProp(r, ['Total']) || 0);
        const cobradoAmt = parseFloat(getRowProp(r, ['Importe cobrado']) || total);
        const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();
        if (st === 'COBRADO' || st.includes('PARCIAL')) {
            totalIngresado += cobradoAmt;
        }
    });

    if (sumTotalEl) {
        sumTotalEl.innerText = formatARS(totalIngresado);
    }

    const sortedRows = sortRecordsMostRecent(rows, ['Fecha cobro', 'Fecha emisión', 'Fecha'], ['ID ingreso', 'ID']);

    if (!sortedRows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No hay cobros registrados en Ingresos. Transfiere una factura desde Facturación al tocar 'Cobrado 💰'.</td></tr>`;
        renderPaginationBar('ingresos', 'pagination-ingresos', { totalItems: 0 });
        return;
    }

    paginateAndRender('ingresos', 'pagination-ingresos', sortedRows, (pageRows) => {
        tbody.innerHTML = pageRows.map(r => {
        const iid = str(getRowProp(r, ['ID ingreso', 'ID'])).trim();
        const reciboId = str(getRowProp(r, ['ID acuerdo', 'ID recibo', 'Recibo'])).trim();

        const fechaCobro = getRowProp(r, ['Fecha cobro', 'Fecha emisión', 'Fecha']) || '-';
        const nroFactura = str(getRowProp(r, ['N° factura ARCA', 'Factura'])).trim();
        const cliente = getRowProp(r, ['Cliente']) || '-';
        const medioCobro = getRowProp(r, ['Medio cobro', 'Medio de cobro']) || 'Por registrar';
        
        const total = parseFloat(getRowProp(r, ['Total']) || 0);
        const cobradoAmt = parseFloat(getRowProp(r, ['Importe cobrado']) || total);
        const saldoRem = parseFloat(getRowProp(r, ['Saldo', 'Saldo pendiente']) || (total - cobradoAmt));
        const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();

        const isCobrado = st === 'COBRADO';
        const isParcial = st.includes('PARCIAL');

        let rowBgClass = '';
        let statusBadge = '';
        let actionBtn = '';

        if (isParcial) {
            rowBgClass = 'bg-sky-50/90 border-sky-200 font-semibold';
            const recBadge = reciboId && reciboId.startsWith('REC-') ? ` <span class="bg-sky-700 text-white px-1.5 py-0.5 rounded text-[9px] font-black">${reciboId}</span>` : '';
            statusBadge = `<span class="bg-sky-100 text-sky-800 border border-sky-300 text-[10px] font-bold px-2.5 py-1 rounded-full inline-flex items-center gap-1"><i class="fa-solid fa-hourglass-half text-sky-600"></i> COBRADO PARCIAL (Saldo: ${formatARS(saldoRem)}) ${recBadge}</span>`;
            actionBtn = `
                <button onclick="marcarComoCobrado('${iid}')" class="inline-flex items-center gap-1 bg-sky-600 hover:bg-sky-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs shadow transition-all cursor-pointer" title="Ingresar cobro del saldo restante (${formatARS(saldoRem)})">
                    <i class="fa-solid fa-hand-holding-dollar"></i> 💰 Cobrar Saldo
                </button>
            `;
        } else if (!isCobrado) {
            rowBgClass = 'bg-amber-50/90 border-amber-200 font-semibold';
            statusBadge = `<span class="bg-amber-500 text-white text-[10px] font-bold px-2.5 py-1 rounded shadow-sm inline-flex items-center gap-1 uppercase"><i class="fa-solid fa-clock"></i> Pendiente Medio de Pago</span>`;
            actionBtn = `
                <button onclick="marcarComoCobrado('${iid}')" class="inline-flex items-center gap-1 bg-amber hover:bg-amber-dark text-white font-bold px-3 py-1.5 rounded-lg text-xs shadow transition-all cursor-pointer" title="Ingresar importes y combinación de medios de pago">
                    <i class="fa-solid fa-pen-to-square"></i> ✍️ Cargar Medios de Pago
                </button>
            `;
        } else {
            rowBgClass = 'bg-emerald-50/60 border-emerald-200';
            
            const recBadge = reciboId && reciboId.startsWith('REC-') ? ` <span class="bg-emerald-700 text-white px-1.5 py-0.5 rounded text-[9px] font-black">${reciboId}</span>` : '';
            statusBadge = `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full inline-flex items-center gap-1"><i class="fa-solid fa-circle-check text-emerald-600"></i> COBRADO 🟢${recBadge}</span>`;
            
            actionBtn = `
                <a href="/api/ingresos/${iid}/recibo_pdf" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-3 py-1.5 rounded-lg text-xs border border-red-200 shadow-sm transition-all" title="Ver / Descargar Recibo Oficial de Cobro (PDF)">
                    <i class="fa-solid fa-file-pdf"></i> PDF Recibo 📄
                </a>
            `;
        }

        return `
            <tr class="${rowBgClass} border-b transition-all text-xs">
                <td class="px-3 py-2.5 font-bold text-navy whitespace-nowrap">${iid}</td>
                <td class="px-3 py-2.5 whitespace-nowrap text-slate-600">${(isCobrado || isParcial) ? formatDateAR(fechaCobro) : '-'}</td>
                <td class="px-3 py-2.5 font-bold text-slate-800 whitespace-nowrap">${nroFactura}</td>
                <td class="px-3 py-2.5 font-semibold text-slate-800">${cliente}</td>
                <td class="px-3 py-2.5 text-slate-600 text-[11px] font-medium max-w-xs truncate" title="${medioCobro}">${medioCobro}</td>
                <td class="px-3 py-2.5 font-bold text-emerald-700 whitespace-nowrap">${formatARS(cobradoAmt)}</td>
                <td class="px-3 py-2.5 whitespace-nowrap">${statusBadge}</td>
                <td class="px-3 py-2.5 text-right whitespace-nowrap">${actionBtn}</td>
            </tr>
        `;
    }).join('');
    }, 10);
}

function clearIngresosDateFilter() {
    resetTablePaginationPage('ingresos');
    const d = document.getElementById('filter-i-desde');
    const h = document.getElementById('filter-i-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    filterIngresosTable();
}

function resetIngresosFilters() {
    resetTablePaginationPage('ingresos');
    const s = document.getElementById('search-ingresos');
    const d = document.getElementById('filter-i-desde');
    const h = document.getElementById('filter-i-hasta');
    const est = document.getElementById('filter-i-estado');
    const med = document.getElementById('filter-i-medio');
    if (s) s.value = '';
    if (d) d.value = '';
    if (h) h.value = '';
    if (est) est.value = '';
    if (med) med.value = '';
    lastIngresosQueryActive = false;
    filterIngresosTable(120, true);
}

function filterIngresosTable(delay = 180, isDropdown = false) {
    resetTablePaginationPage('ingresos');
    const rawQuery = (document.getElementById('search-ingresos')?.value || '').trim();
    const isNowActive = rawQuery.length >= 3;

    if (!isDropdown && !isNowActive && !lastIngresosQueryActive && rawQuery.length > 0) {
        return;
    }

    if (ingresosFilterDebounceTimer) {
        clearTimeout(ingresosFilterDebounceTimer);
    }

    if (delay > 0) {
        showIngresosLoader();
    }
    lastIngresosQueryActive = isNowActive;

    ingresosFilterDebounceTimer = setTimeout(() => {
        applyIngresosFilter();
    }, delay);
}

function applyIngresosFilter() {
    const rawQuery = (document.getElementById('search-ingresos')?.value || '').trim();
    const fQuery = rawQuery.length >= 3 ? rawQuery.toLowerCase() : '';
    const fEstado = document.getElementById('filter-i-estado')?.value || '';
    const fMedio = (document.getElementById('filter-i-medio')?.value || '').toLowerCase().trim();
    const fDesde = document.getElementById('filter-i-desde')?.value || '';
    const fHasta = document.getElementById('filter-i-hasta')?.value || '';

    const filtered = currentIngresos.filter(r => {
        const iid = str(getRowProp(r, ['ID ingreso', 'ID'])).toLowerCase();
        const cliente = str(getRowProp(r, ['Cliente'])).toLowerCase();
        const nroFactura = str(getRowProp(r, ['N° factura ARCA', 'Factura'])).toLowerCase();
        const medio = str(getRowProp(r, ['Medio cobro', 'Forma de Pago', 'Medio de Pago', 'Medio'])).toLowerCase();
        const obs = str(getRowProp(r, ['Observaciones'])).toLowerCase();
        const st = str(getRowProp(r, ['Estado cobro'])).trim().toUpperCase();

        const fullText = `${iid} ${cliente} ${nroFactura} ${medio} ${obs}`;
        if (fQuery && !fullText.includes(fQuery)) return false;

        const isCobrado = st === 'COBRADO';
        const isParcial = st.includes('PARCIAL');

        if (fEstado === 'pendiente_medio' && (isCobrado || isParcial)) return false;
        if (fEstado === 'cobrado' && (!isCobrado && !isParcial)) return false;

        if (fMedio && fMedio !== '') {
            if (fMedio === 'caja chica efectivo' || fMedio === 'efectivo') {
                if (!fullText.includes('efectivo') && !fullText.includes('caja chica')) return false;
            } else if (!fullText.includes(fMedio)) {
                return false;
            }
        }

        if (fDesde || fHasta) {
            const rawDate = getRowProp(r, ['Fecha cobro', 'Fecha emisión', 'Fecha']) || '';
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

    renderIngresosTable(filtered);
}

function onTipoComprobanteIngresoChanged() {
    const tipo = document.getElementById('i-tipo').value;
    const nroInput = document.getElementById('i-nro');
    const ivapctSel = document.getElementById('i-ivapct');

    if (tipo === 'Comprobante Interno (No Fiscal)' || tipo.includes('No Fiscal')) {
        nroInput.value = 'COMPROBANTE-INTERNO';
        nroInput.readOnly = true;
        nroInput.removeAttribute('required');
        nroInput.classList.add('bg-slate-100', 'cursor-not-allowed');
        ivapctSel.value = '0';
    } else {
        if (nroInput.value === 'COMPROBANTE-INTERNO') {
            nroInput.value = '';
        }
        nroInput.readOnly = false;
        nroInput.setAttribute('required', 'required');
        nroInput.classList.remove('bg-slate-100', 'cursor-not-allowed');
    }
    calcIngresoTotal();
}

function openNuevoIngresoModal() {
    const editId = document.getElementById('i-id-edit');
    if (editId) editId.value = '';
    const form = document.getElementById('form-ingreso');
    if (form) form.reset();
    const title = document.getElementById('modal-i-title');
    if (title) title.innerHTML = `<i class="fa-solid fa-file-invoice-dollar text-amber"></i> Registrar Ingreso Manual / Factura`;

    const clienteSel = document.getElementById('i-cliente');
    if (clienteSel) {
        clienteSel.disabled = false;
        clienteSel.classList.remove('bg-slate-100', 'cursor-not-allowed');
        clienteSel.classList.add('bg-slate-50');
        if (window.masterLists && window.masterLists.clientes && typeof populateSelect === 'function') {
            populateSelect('i-cliente', window.masterLists.clientes, 'Seleccionar Cliente...');
        }
        clienteSel.value = '';
    }
    const tag = document.getElementById('label-i-cliente-tag');
    if (tag) tag.classList.add('hidden');
    const btnNewCli = document.getElementById('btn-nuevo-cliente-ingreso');
    if (btnNewCli) btnNewCli.classList.remove('hidden');

    if (document.getElementById('i-fecha')) document.getElementById('i-fecha').value = new Date().toISOString().split('T')[0];
    if (document.getElementById('i-tipo')) document.getElementById('i-tipo').value = 'Factura A';
    if (document.getElementById('i-ivapct')) document.getElementById('i-ivapct').value = '21';
    if (document.getElementById('i-neto')) document.getElementById('i-neto').value = '';
    onTipoComprobanteIngresoChanged();
    calcIngresoTotal();
    openModal('modal-ingreso');
}

function completarFacturacionData(iid) {
    const target = currentFacturacion.find(r => str(getRowProp(r, ['ID ingreso', 'ID'])).trim() === str(iid).trim());
    if (!target) return;

    document.getElementById('modal-i-title').innerHTML = `<i class="fa-solid fa-file-invoice-dollar text-amber"></i> Datos de Facturación / Modalidad (${iid})`;
    document.getElementById('i-id-edit').value = iid;
    
    const clienteVal = getRowProp(target, ['Cliente']) || 'Cliente';
    const clienteSel = document.getElementById('i-cliente');
    if (clienteSel) {
        if (!Array.from(clienteSel.options).some(o => o.value === clienteVal)) {
            clienteSel.appendChild(new Option(clienteVal, clienteVal));
        }
        clienteSel.value = clienteVal;
        clienteSel.disabled = true;
        clienteSel.classList.remove('bg-slate-50');
        clienteSel.classList.add('bg-slate-100', 'cursor-not-allowed');
    }
    const tag = document.getElementById('label-i-cliente-tag');
    if (tag) tag.classList.remove('hidden');
    const btnNewCli = document.getElementById('btn-nuevo-cliente-ingreso');
    if (btnNewCli) btnNewCli.classList.add('hidden');

    const nroVal = getRowProp(target, ['N° factura ARCA', 'Factura']);
    document.getElementById('i-nro').value = (nroVal && !nroVal.includes('PENDIENTE')) ? nroVal : '';
    
    const fechaVal = getRowProp(target, ['Fecha emisión', 'Fecha']);
    document.getElementById('i-fecha').value = fechaVal || new Date().toISOString().split('T')[0];
    document.getElementById('i-tipo').value = getRowProp(target, ['Tipo comprobante']) || 'Factura A';

    document.getElementById('i-neto').value = getRowProp(target, ['Neto']) || 0;
    
    const rawIvaIngreso = getRowProp(target, ['IVA %', 'IVA', 'iva_pct']);
    const parsedIvaIngreso = parseFloat(rawIvaIngreso);
    document.getElementById('i-ivapct').value = !isNaN(parsedIvaIngreso) ? String(parsedIvaIngreso) : '21';
    
    onTipoComprobanteIngresoChanged();
    calcIngresoTotal();
    openModal('modal-ingreso');
}

function calcCobroTotal() {
    const transf = parseFloat(document.getElementById('ic-monto-transferencia')?.value) || 0;
    const echeq = parseFloat(document.getElementById('ic-monto-echeq')?.value) || 0;
    const cheque = parseFloat(document.getElementById('ic-monto-cheque')?.value) || 0;
    const efectivo = parseFloat(document.getElementById('ic-monto-efectivo')?.value) || 0;
    const tarjeta = parseFloat(document.getElementById('ic-monto-tarjeta')?.value) || 0;

    const sfCheck = document.getElementById('ic-check-saldo-favor');
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    const saldoFavor = (sfCheck && sfCheck.checked && sfInput) ? (parseFloat(sfInput.value) || 0) : 0;

    const totalSum = transf + echeq + cheque + efectivo + tarjeta + saldoFavor;
    const sumEl = document.getElementById('ic-sum-calc');
    if (sumEl) sumEl.innerText = formatARS(totalSum);

    const targetAmt = parseFloat(sfInput?.dataset?.targetAmt || 0);
    const feedbackEl = document.getElementById('ic-feedback-calc');
    if (feedbackEl && targetAmt > 0) {
        const diff = Math.round((totalSum - targetAmt) * 100) / 100;
        if (diff > 0.01) {
            feedbackEl.className = "text-[11px] text-rose-700 font-bold mt-1 flex items-center gap-1";
            feedbackEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-rose-600"></i> Atención: La suma ingresada (${formatARS(totalSum)}) supera el saldo a cobrar (${formatARS(targetAmt)}) por ${formatARS(diff)}.`;
        } else if (diff < -0.01) {
            feedbackEl.className = "text-[11px] text-amber-800 font-semibold mt-1 flex items-center gap-1";
            feedbackEl.innerHTML = `<i class="fa-solid fa-circle-info text-amber-600"></i> Cobro parcial: Quedará un saldo pendiente de ${formatARS(Math.abs(diff))}.`;
        } else {
            feedbackEl.className = "text-[11px] text-emerald-800 font-semibold mt-1 flex items-center gap-1";
            feedbackEl.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-600"></i> Monto exacto a cobrar (${formatARS(totalSum)}).`;
        }
    } else if (feedbackEl) {
        feedbackEl.innerHTML = '';
    }

    const chqDetails = document.getElementById('container-ic-cheque-detalles');
    if (chqDetails) {
        if (cheque > 0) {
            chqDetails.classList.remove('hidden');
            const vtoEl = document.getElementById('ic-cheque-vencimiento');
            if (vtoEl && !vtoEl.value) {
                vtoEl.value = document.getElementById('ic-fecha')?.value || new Date().toISOString().split('T')[0];
            }
        } else {
            chqDetails.classList.add('hidden');
        }
    }

    const echqDetails = document.getElementById('container-ic-echeq-detalles');
    if (echqDetails) {
        if (echeq > 0) {
            echqDetails.classList.remove('hidden');
            const vtoEl = document.getElementById('ic-echeq-vencimiento');
            if (vtoEl && !vtoEl.value) {
                vtoEl.value = document.getElementById('ic-fecha')?.value || new Date().toISOString().split('T')[0];
            }
        } else {
            echqDetails.classList.add('hidden');
        }
    }
}

function toggleSaldoFavor(isChecked) {
    const sfWrapper = document.getElementById('wrapper-ic-saldo-favor-input');
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    if (!sfInput) return;

    const maxSaldo = parseFloat(sfInput.dataset.maxSaldo || 0);
    const targetAmt = parseFloat(sfInput.dataset.targetAmt || 0);

    if (isChecked) {
        if (sfWrapper) sfWrapper.classList.remove('hidden');
        const sugerido = Math.min(maxSaldo, targetAmt > 0 ? targetAmt : maxSaldo);
        sfInput.value = sugerido > 0 ? sugerido : '';

        // Si transferencia tenía todo el saldo, sugerir el remanente
        const remanente = Math.max(0, targetAmt - sugerido);
        const curTransf = parseFloat(document.getElementById('ic-monto-transferencia').value) || 0;
        if (curTransf === targetAmt || curTransf === 0) {
            document.getElementById('ic-monto-transferencia').value = remanente > 0 ? remanente : '';
        }
    } else {
        if (sfWrapper) sfWrapper.classList.add('hidden');
        sfInput.value = '';
        // Restaurar saldo completo en transferencia si tenía el remanente
        const curTransf = parseFloat(document.getElementById('ic-monto-transferencia').value) || 0;
        if (curTransf < targetAmt) {
            document.getElementById('ic-monto-transferencia').value = targetAmt > 0 ? targetAmt : '';
        }
    }
    calcCobroTotal();
}

function onMontoSaldoFavorInput() {
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    if (!sfInput) return;
    const maxSaldo = parseFloat(sfInput.dataset.maxSaldo || 0);
    const targetAmt = parseFloat(sfInput.dataset.targetAmt || 0);
    let val = parseFloat(sfInput.value) || 0;

    if (val < 0) {
        sfInput.value = 0;
    } else if (maxSaldo > 0 && val > maxSaldo) {
        sfInput.value = maxSaldo;
    } else if (targetAmt > 0 && val > targetAmt) {
        sfInput.value = targetAmt;
    }
    calcCobroTotal();
}

function usarMaximoSaldoFavor() {
    const sfCheck = document.getElementById('ic-check-saldo-favor');
    if (sfCheck && !sfCheck.checked) {
        sfCheck.checked = true;
        toggleSaldoFavor(true);
        return;
    }
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    if (!sfInput) return;
    const maxSaldo = parseFloat(sfInput.dataset.maxSaldo || 0);
    const targetAmt = parseFloat(sfInput.dataset.targetAmt || 0);
    const aAplicar = Math.min(maxSaldo, targetAmt > 0 ? targetAmt : maxSaldo);

    sfInput.value = aAplicar > 0 ? aAplicar : '';

    const remanente = Math.max(0, targetAmt - aAplicar);
    document.getElementById('ic-monto-transferencia').value = remanente > 0 ? remanente : '';

    calcCobroTotal();
}

function parseCurrencyStr(strVal) {
    if (!strVal) return 0;
    let s = String(strVal).replace(/[$ ]/g, '').trim();
    if (!s) return 0;
    if (s.includes(',') && s.includes('.')) {
        if (s.lastIndexOf('.') > s.lastIndexOf(',')) {
            s = s.replace(/,/g, '');
        } else {
            s = s.replace(/\./g, '').replace(',', '.');
        }
    } else if (s.includes(',')) {
        s = s.replace(',', '.');
    } else if (s.includes('.')) {
        const parts = s.split('.');
        if (parts.length > 2 || (parts.length === 2 && parts[1].length === 3)) {
            s = s.replace(/\./g, '');
        }
    }
    const val = parseFloat(s);
    return !isNaN(val) ? val : 0;
}

async function marcarComoCobrado(iid) {
    let target = currentIngresos.find(r => str(getRowProp(r, ['ID ingreso', 'ID'])).trim() === str(iid).trim());
    if (!target) {
        target = currentFacturacion.find(r => str(getRowProp(r, ['ID ingreso', 'ID'])).trim() === str(iid).trim());
    }
    if (!target) return;

    const obs = str(getRowProp(target, ['Observaciones']) || '');
    let assocViajeId = '';
    if (obs.includes('Operación origen:')) {
        assocViajeId = obs.split('Operación origen:')[1].trim().split(' ')[0];
    }

    const totalVal = parseFloat(getRowProp(target, ['Total']) || 0);
    let totAdelantos = 0;

    if (obs.includes('Señas/Adelantos cobrados previamente:')) {
        const match = obs.match(/Señas\/Adelantos cobrados previamente:\s*\$?([\d\.,]+)/i);
        if (match) {
            totAdelantos = parseCurrencyStr(match[1]);
        }
    }

    if (assocViajeId && !totAdelantos) {
        try {
            const res = await fetch(`/api/viajes/${assocViajeId}/facturacion_summary`);
            const sjson = await res.json();
            if (sjson.status === 'success' && sjson.summary) {
                totAdelantos = parseFloat(sjson.summary.tot_adelantos || 0);
            }
        } catch (e) {}
    }

    const rawSaldo = parseFloat(getRowProp(target, ['Saldo']));
    let saldoACobrar = !isNaN(rawSaldo) && rawSaldo > 0 ? rawSaldo : Math.max(0, totalVal - totAdelantos);
    if (totAdelantos > 0 && (isNaN(rawSaldo) || rawSaldo === totalVal)) {
        saldoACobrar = Math.max(0, totalVal - totAdelantos);
    }

    document.getElementById('modal-ic-title').innerHTML = `<i class="fa-solid fa-money-bill-wave text-emerald-600"></i> Registrar Medios de Pago (${getRowProp(target, ['N° factura ARCA']) || iid})`;
    document.getElementById('ic-id-edit').value = iid;
    const clienteName = getRowProp(target, ['Cliente']) || '-';
    document.getElementById('ic-disp-cliente').innerText = clienteName;
    if (document.getElementById('ic-cliente-hidden')) document.getElementById('ic-cliente-hidden').value = clienteName;
    if (document.getElementById('ic-cuit-hidden')) document.getElementById('ic-cuit-hidden').value = getRowProp(target, ['CUIT/CUIL', 'CUIT']) || '';

    // Reset Saldo a Favor C/C Container
    const sfContainer = document.getElementById('container-ic-saldo-favor');
    const sfCheck = document.getElementById('ic-check-saldo-favor');
    const sfWrapper = document.getElementById('wrapper-ic-saldo-favor-input');
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    if (sfContainer) sfContainer.classList.add('hidden');
    if (sfWrapper) sfWrapper.classList.add('hidden');
    if (sfCheck) sfCheck.checked = false;
    if (sfInput) {
        sfInput.value = '';
        sfInput.dataset.maxSaldo = '0';
        sfInput.dataset.targetAmt = saldoACobrar;
    }

    // Check client credit balance (Saldo a Favor) in C/C
    let creditAvail = 0;
    if (clienteName && clienteName !== '-') {
        try {
            const ccRes = await fetch(`/api/cuentas_corrientes/${encodeURIComponent(clienteName)}`);
            const ccJson = await ccRes.json();
            if (ccJson.status === 'success') {
                const sFinal = parseFloat(ccJson.saldo_final) || 0;
                // En cuenta corriente, saldo negativo = saldo acreedor (a favor del cliente)
                if (sFinal < -0.01) {
                    creditAvail = Math.abs(sFinal);
                } else {
                    creditAvail = 0;
                }

                if (creditAvail > 0.01 && sfContainer && sfInput) {
                    sfContainer.classList.remove('hidden');
                    document.getElementById('ic-disp-saldo-favor-amt').innerText = formatARS(creditAvail);
                    sfInput.dataset.maxSaldo = creditAvail;
                }
            }
        } catch (e) {
            console.error("Error al verificar saldo a favor de cliente:", e);
            creditAvail = 0;
        }
    }
    
    let dispFacturaHtml = `${getRowProp(target, ['N° factura ARCA']) || iid} (${getRowProp(target, ['Tipo comprobante']) || 'Comprobante'})`;
    if (totAdelantos > 0) {
        dispFacturaHtml += ` <span class="bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold px-2 py-0.5 rounded ml-2"><i class="fa-solid fa-hand-holding-dollar"></i> ${formatARS(totAdelantos)} en Adelantos Previos</span>`;
    }
    document.getElementById('ic-disp-factura').innerHTML = dispFacturaHtml;

    let dispTotalHtml = `
        <div class="text-right">
            <div class="text-xs text-slate-500">Total Factura ARCA: <span class="font-bold text-slate-700">${formatARS(totalVal)}</span></div>
            ${totAdelantos > 0 ? `<div class="text-xs text-amber-700 font-semibold">(-) Adelantos Cobrados: <span class="font-bold">-${formatARS(totAdelantos)}</span></div>` : ''}
            <div class="text-sm font-black text-emerald-700">Saldo a Cobrar Hoy: ${formatARS(saldoACobrar)}</div>
        </div>
    `;
    document.getElementById('ic-disp-total').innerHTML = dispTotalHtml;
    
    // Auto fill cash/transfer with remaining balance to collect
    document.getElementById('ic-monto-transferencia').value = saldoACobrar > 0 ? saldoACobrar : '';
    document.getElementById('ic-monto-echeq').value = '';
    document.getElementById('ic-monto-cheque').value = '';
    document.getElementById('ic-monto-efectivo').value = '';
    document.getElementById('ic-monto-tarjeta').value = '';
    if (document.getElementById('ic-cheque-nro')) document.getElementById('ic-cheque-nro').value = '';
    if (document.getElementById('ic-cheque-banco')) document.getElementById('ic-cheque-banco').value = '';
    if (document.getElementById('ic-cheque-vencimiento')) document.getElementById('ic-cheque-vencimiento').value = '';
    if (document.getElementById('ic-echeq-nro')) document.getElementById('ic-echeq-nro').value = '';
    if (document.getElementById('ic-echeq-banco')) document.getElementById('ic-echeq-banco').value = '';
    if (document.getElementById('ic-echeq-vencimiento')) document.getElementById('ic-echeq-vencimiento').value = '';
    calcCobroTotal();

    document.getElementById('ic-fecha').value = new Date().toISOString().split('T')[0];
    let defaultObs = '';
    if (totAdelantos > 0) {
        defaultObs = `Cobro de saldo restante (Descontado adelanto previo de ${formatARS(totAdelantos)})`;
    }
    document.getElementById('ic-observaciones').value = defaultObs;

    openModal('modal-cobro');
}

async function submitIngreso(e) {
    e.preventDefault();
    const i_id = document.getElementById('i-id-edit').value;
    const clienteVal = (document.getElementById('i-cliente')?.value || '').trim();
    if (!clienteVal || clienteVal.toLowerCase().includes('seleccionar')) {
        showToast("Por favor selecciona un cliente para la factura.", "error");
        return;
    }
    const tipoVal = document.getElementById('i-tipo').value;
    let nroVal = document.getElementById('i-nro').value;
    if (tipoVal.includes('No Fiscal') || tipoVal.includes('Sin Factura')) {
        nroVal = 'COMPROBANTE-INTERNO';
    }

    const payload = {
        cliente: clienteVal,
        tipo_comprobante: tipoVal,
        nro_factura: nroVal,
        fecha_emision: document.getElementById('i-fecha').value,
        neto: document.getElementById('i-neto').value,
        iva_pct: document.getElementById('i-ivapct').value
    };

    if (i_id) payload.id = i_id;

    try {
        const res = await fetch('/api/ingresos/factura/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-ingreso');
            await loadFacturacionData();
            if (typeof loadIngresosData === 'function') await loadIngresosData();
            await loadDashboardData();
            const msgToast = i_id 
                ? (nroVal === 'COMPROBANTE-INTERNO' ? `Guardado como Comprobante Interno (No Fiscal). Listo para registrar el cobro.` : `Factura ARCA guardada. Estado actualizado a 'Factura Emitida'.`)
                : `Factura guardada con éxito (${json.id || 'ARCA'}).`;
            showToast(msgToast);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar la factura.", "error");
    }
}

async function submitCobro(e) {
    e.preventDefault();
    const i_id = document.getElementById('ic-id-edit').value;
    const sfCheck = document.getElementById('ic-check-saldo-favor');
    const sfInput = document.getElementById('ic-monto-saldo-favor');
    const sfVal = (sfCheck && sfCheck.checked && sfInput) ? (parseFloat(sfInput.value) || 0) : 0;

    const transf = parseFloat(document.getElementById('ic-monto-transferencia').value) || 0;
    const echeq = parseFloat(document.getElementById('ic-monto-echeq').value) || 0;
    const cheque = parseFloat(document.getElementById('ic-monto-cheque').value) || 0;
    const efectivo = parseFloat(document.getElementById('ic-monto-efectivo').value) || 0;
    const tarjeta = parseFloat(document.getElementById('ic-monto-tarjeta').value) || 0;

    const totalCobro = transf + echeq + cheque + efectivo + tarjeta + sfVal;
    if (totalCobro <= 0) {
        showToast("Debes ingresar un importe mayor a 0 en al menos un medio de pago.", "error");
        return;
    }

    const targetAmt = parseFloat(sfInput?.dataset?.targetAmt || 0);
    if (targetAmt > 0 && totalCobro > (targetAmt + 0.05)) {
        showToast(`La suma de medios (${formatARS(totalCobro)}) supera el saldo a cobrar (${formatARS(targetAmt)}). Ajustá los importes antes de continuar.`, "error");
        return;
    }

    const payload = {
        id: i_id,
        cliente: document.getElementById('ic-cliente-hidden')?.value?.trim() || '',
        cuit: document.getElementById('ic-cuit-hidden')?.value?.trim() || '',
        fecha_cobro: document.getElementById('ic-fecha').value,
        monto_transferencia: transf,
        monto_echeq: echeq,
        monto_cheque: cheque,
        monto_efectivo: efectivo,
        monto_tarjeta: tarjeta,
        monto_saldo_favor: sfVal,
        cuenta_destino: document.getElementById('ic-cuenta-destino')?.value || '',
        observaciones: document.getElementById('ic-observaciones').value
    };

    if (cheque > 0) {
        payload.nro_cheque = document.getElementById('ic-cheque-nro')?.value?.trim() || '';
        payload.banco_cheque = document.getElementById('ic-cheque-banco')?.value?.trim() || '';
        payload.fecha_venc_cheque = document.getElementById('ic-cheque-vencimiento')?.value || payload.fecha_cobro;
        if (!payload.nro_cheque) {
            showToast("Por favor ingresá el Nº del cheque físico para registrarlo en Cartera de Cheques.", "error");
            return;
        }
    }

    if (echeq > 0) {
        payload.nro_echeq = document.getElementById('ic-echeq-nro')?.value?.trim() || '';
        payload.banco_echeq = document.getElementById('ic-echeq-banco')?.value?.trim() || '';
        payload.fecha_venc_echeq = document.getElementById('ic-echeq-vencimiento')?.value || payload.fecha_cobro;
        if (!payload.nro_echeq) {
            showToast("Por favor ingresá el Nº del E-Cheq para registrarlo en Cartera de Cheques.", "error");
            return;
        }
    }

    try {
        const res = await fetch('/api/ingresos/cobro/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cobro');
            await loadFacturacionData();
            await loadIngresosData();
            await loadDashboardData();
            await loadChequesData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            showToast(`¡Cobro registrado definitivamente (${json.recibo_id || i_id})! Se habilitó la descarga del PDF Recibo.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al registrar el cobro.", "error");
    }
}

// EMAIL FACTURACION & SMTP CONFIGURATION HANDLERS
async function openSendFacturaEmailModal(iid) {
    const target = (currentFacturacion || []).find(r => str(getRowProp(r, ['ID ingreso', 'ID'])).trim() === str(iid).trim());
    if (!target) {
        showToast("No se encontró el registro de facturación seleccionado.", "error");
        return;
    }

    const nroFactura = str(getRowProp(target, ['N° factura ARCA', 'Factura'])).trim();
    const clienteNombre = str(getRowProp(target, ['Cliente'])).trim();

    if (document.getElementById('mfe-id')) document.getElementById('mfe-id').value = iid;
    if (document.getElementById('mfe-subject')) document.getElementById('mfe-subject').value = `Factura de Venta / Comprobante - ECONCATIVO S.A.S. (${nroFactura || iid})`;
    if (document.getElementById('mfe-pdf')) document.getElementById('mfe-pdf').value = '';

    const statusEl = document.getElementById('mfe-email-status');
    const emailEl = document.getElementById('mfe-email');
    if (statusEl) {
        statusEl.classList.add('hidden');
        statusEl.innerHTML = '';
    }

    // Fetch dynamic preview with client email lookup from backend
    try {
        const res = await fetch(`/api/facturacion/${iid}/email_preview`);
        const json = await res.json();
        if (json.status === 'success') {
            if (json.subject) {
                if (document.getElementById('mfe-subject')) document.getElementById('mfe-subject').value = json.subject;
            }
            if (json.message) {
                if (document.getElementById('mfe-message')) document.getElementById('mfe-message').value = json.message;
            }

            if (json.to_email) {
                if (emailEl) emailEl.value = json.to_email;
                if (statusEl) {
                    statusEl.classList.remove('hidden');
                    statusEl.innerHTML = `<span class="text-emerald-700 font-semibold"><i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i> Correo obtenido automáticamente del maestro de clientes (${json.to_email}).</span>`;
                }
            } else {
                if (emailEl) emailEl.value = '';
                if (statusEl) {
                    statusEl.classList.remove('hidden');
                    statusEl.innerHTML = `<span class="text-amber-800 bg-amber-50 border border-amber-200 px-2 py-1 rounded inline-block font-semibold"><i class="fa-solid fa-triangle-exclamation text-amber-600 mr-1"></i> El cliente "${clienteNombre || 'seleccionado'}" no tiene un correo registrado en Maestros. Podés ingresarlo manualmente a continuación.</span>`;
                }
            }
        }
    } catch (e) {
        console.error("Error al cargar vista previa del email:", e);
    }

    openModal('modal-send-factura-email');
}

async function submitSendFacturaEmail(e) {
    e.preventDefault();
    const btnSubmit = document.getElementById('mfe-btn-submit');
    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Enviando Correo...`;
    }

    try {
        const formData = new FormData();
        formData.append('ingreso_id', document.getElementById('mfe-id') ? document.getElementById('mfe-id').value : '');
        formData.append('to_email', document.getElementById('mfe-email').value);
        formData.append('subject', document.getElementById('mfe-subject').value);
        formData.append('message', document.getElementById('mfe-message').value);

        const pdfFileInput = document.getElementById('mfe-pdf');
        if (pdfFileInput && pdfFileInput.files && pdfFileInput.files[0]) {
            formData.append('pdf_file', pdfFileInput.files[0]);
        }

        const res = await fetch('/api/facturacion/send_email', {
            method: 'POST',
            body: formData
        });

        const json = await res.json();
        if (json.status === 'success') {
            showToast(json.message || "¡Email enviado exitosamente!", "success");
            closeModal('modal-send-factura-email');
        } else {
            showToast(json.message || "Error al enviar el email.", "error");
        }
    } catch (err) {
        console.error("Error al enviar el email:", err);
        showToast("Error de conexión al intentar enviar el email.", "error");
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane mr-1"></i> Enviar Factura por Email`;
        }
    }
}

async function openConfigSMTPModal() {
    try {
        const res = await fetch('/api/config/smtp');
        const json = await res.json();
        if (json.status === 'success' && json.data) {
            if (document.getElementById('cfg-smtp-email')) document.getElementById('cfg-smtp-email').value = json.data.smtp_email || '';
            if (document.getElementById('cfg-smtp-password')) document.getElementById('cfg-smtp-password').value = json.data.smtp_password || '';
            if (document.getElementById('cfg-admin-phone')) document.getElementById('cfg-admin-phone').value = json.data.telefono_administracion || '';
        }
    } catch (e) {
        console.error("Error al cargar configuración SMTP:", e);
    }
    openModal('modal-config-smtp');
}

async function submitConfigSMTP(e) {
    e.preventDefault();
    try {
        const payload = {
            smtp_email: document.getElementById('cfg-smtp-email').value,
            smtp_password: document.getElementById('cfg-smtp-password').value,
            telefono_administracion: document.getElementById('cfg-admin-phone').value
        };

        const res = await fetch('/api/config/smtp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const json = await res.json();
        if (json.status === 'success') {
            showToast("Configuración de correo guardada exitosamente.", "success");
            closeModal('modal-config-smtp');
        } else {
            showToast(json.message || "Error al guardar la configuración.", "error");
        }
    } catch (err) {
        console.error("Error al guardar la configuración SMTP:", err);
        showToast("Error de conexión al guardar la configuración.", "error");
    }
}


function calcIngresoTotal() {
    const neto = parseFloat(document.getElementById('i-neto').value) || 0;
    const pctVal = document.getElementById('i-ivapct') ? document.getElementById('i-ivapct').value : '21';
    const pctParsed = parseFloat(pctVal);
    const pct = !isNaN(pctParsed) ? pctParsed : 21;
    const total = neto + (neto * (pct / 100));
    document.getElementById('i-total-calc').innerText = formatARS(total);
}

