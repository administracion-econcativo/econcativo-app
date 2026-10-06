/**
 * ECONCATIVO - Cuentas Corrientes Clientes Module
 */
// CUENTAS CORRIENTES CLIENTES MODULE
let currentCCData = null;

async function loadCuentaCorrienteTab() {
    await loadMasterLists();
    const sel = document.getElementById('select-cc-cliente');
    if (sel && sel.options.length > 1 && !sel.value) {
        sel.selectedIndex = 1;
        if (sel._searchableSelect) sel._searchableSelect.syncValue();
    }
    await loadCuentaCorrienteCliente();
}

function resetCuentaCorrienteFilters() {
    const d = document.getElementById('cc-fecha-desde');
    const h = document.getElementById('cc-fecha-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    loadCuentaCorrienteCliente();
}

async function loadCuentaCorrienteCliente() {
    const cliente = document.getElementById('select-cc-cliente')?.value;
    const fDesde = document.getElementById('cc-fecha-desde')?.value || '';
    const fHasta = document.getElementById('cc-fecha-hasta')?.value || '';

    const tbody = document.getElementById('tbody-cc-movements');
    const badgeCount = document.getElementById('badge-cc-count');

    if (!cliente) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400 font-medium">Selecciona un cliente para visualizar su cuenta corriente.</td></tr>`;
        document.getElementById('card-cc-saldo-monto').innerText = '$0.00';
        document.getElementById('card-cc-debe-monto').innerText = '$0.00';
        document.getElementById('card-cc-haber-monto').innerText = '$0.00';
        if (badgeCount) badgeCount.innerText = '0 movimientos';
        currentCCData = null;
        return;
    }

    // Loader centrado en el medio de la tabla para transición suave (idéntico a Tablas Maestras)
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="py-20 text-center">
                    <div class="flex flex-col items-center justify-center gap-3">
                        <div class="relative w-10 h-10">
                            <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                            <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                        </div>
                        <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                            Cargando cuenta corriente...
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }
    if (badgeCount) badgeCount.innerText = 'Cargando...';

    try {
        const query = `fecha_desde=${fDesde}&fecha_hasta=${fHasta}&_t=${Date.now()}`;
        const [res] = await Promise.all([
            fetch(`/api/cuentas_corrientes/${encodeURIComponent(cliente)}?${query}`),
            new Promise(r => setTimeout(r, 200))
        ]);
        const json = await res.json();
        if (json.status === 'success') {
            currentCCData = json;
            renderCuentaCorrienteTable();
        } else {
            if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-rose-500 font-medium">Error: ${json.message || 'Error al cargar'}</td></tr>`;
            showToast("Error al cargar cuenta corriente: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al cargar cuenta corriente:", err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-rose-500 font-medium">Error de conexión al cargar cuenta corriente.</td></tr>`;
        showToast("Error al conectar con el servidor.", "error");
    }
}

function renderCuentaCorrienteTable() {
    if (!currentCCData) return;

    const movs = currentCCData.movimientos || [];
    const saldoFinal = currentCCData.saldo_final || 0;
    const totDebe = currentCCData.total_debe || 0;
    const totHaber = currentCCData.total_haber || 0;
    const saldoAnterior = currentCCData.saldo_anterior || 0;

    // Update KPI Cards
    const cardSaldo = document.getElementById('card-cc-saldo-monto');
    const cardLabel = document.getElementById('card-cc-saldo-label');
    const cardBadge = document.getElementById('card-cc-saldo-badge');

    if (cardSaldo) cardSaldo.innerText = formatARS(Math.abs(saldoFinal));
    
    if (saldoFinal > 0.01) {
        if (cardLabel) cardLabel.innerText = "SALDO EN CONTRA ACTUAL";
        if (cardBadge) {
            cardBadge.innerText = "🔴 SALDO EN CONTRA (DEUDA PENDIENTE)";
            cardBadge.className = "block text-[11px] font-bold text-rose-600 mt-1";
        }
        if (cardSaldo) cardSaldo.className = "text-2xl font-black text-rose-600";
    } else if (saldoFinal < -0.01) {
        if (cardLabel) cardLabel.innerText = "SALDO A FAVOR ACTUAL";
        if (cardBadge) {
            cardBadge.innerText = "🟢 SALDO A FAVOR (CRÉDITO DISPONIBLE)";
            cardBadge.className = "block text-[11px] font-bold text-emerald-600 mt-1";
        }
        if (cardSaldo) cardSaldo.className = "text-2xl font-black text-emerald-600";
    } else {
        if (cardLabel) cardLabel.innerText = "SALDO EN CUENTA";
        if (cardBadge) {
            cardBadge.innerText = "✓ AL DÍA (SALDO $0.00)";
            cardBadge.className = "block text-[11px] font-bold text-emerald-600 mt-1";
        }
        if (cardSaldo) cardSaldo.className = "text-2xl font-black text-slate-700";
    }

    if (document.getElementById('card-cc-debe-monto')) document.getElementById('card-cc-debe-monto').innerText = formatARS(totDebe);
    if (document.getElementById('card-cc-haber-monto')) document.getElementById('card-cc-haber-monto').innerText = formatARS(totHaber);
    if (document.getElementById('badge-cc-count')) document.getElementById('badge-cc-count').innerText = `${movs.length} movimientos`;

    const tbody = document.getElementById('tbody-cc-movements');
    if (!tbody) return;

    // Ordenar movimientos para que el más reciente aparezca arriba de todo
    const indexedMovs = movs.map((m, idx) => ({ ...m, _idx: idx }));
    const sortedMovs = indexedMovs.slice().sort((a, b) => {
        const valDateA = a.fecha || a.vencimiento || '';
        const valDateB = b.fecha || b.vencimiento || '';
        const tsA = parseDateForSort(valDateA);
        const tsB = parseDateForSort(valDateB);
        if (tsB !== tsA) {
            return tsB - tsA;
        }
        return b._idx - a._idx;
    });

    let html = ``;

    if (!sortedMovs.length) {
        html += `<tr><td colspan="5" class="p-6 text-center text-slate-400 font-medium">No se registraron movimientos en el período seleccionado.</td></tr>`;
    } else {
        html += sortedMovs.map(m => {
            const dVal = parseFloat(m.debe) || 0;
            const hVal = parseFloat(m.haber) || 0;
            const sVal = parseFloat(m.saldo_acumulado) || 0;

            const isEntrega = hVal > 0;

            return `
                <tr class="hover:bg-slate-50 transition-all border-b border-slate-100 ${isEntrega ? 'bg-emerald-50/20' : ''}">
                    <td class="px-4 py-3 whitespace-nowrap font-medium text-slate-600">${formatDateAR(m.vencimiento || m.fecha)}</td>
                    <td class="px-4 py-3">
                        <span class="font-bold text-slate-800 block">${m.concepto || m.tipo}</span>
                        <span class="text-[11px] text-slate-400">${m.tipo}${m.ref_id ? ' (Ref: ' + m.ref_id + ')' : ''}</span>
                    </td>
                    <td class="px-4 py-3 text-right font-bold text-navy whitespace-nowrap">${dVal > 0 ? formatARS(dVal) : '-'}</td>
                    <td class="px-4 py-3 text-right font-bold text-emerald-700 whitespace-nowrap">${hVal > 0 ? formatARS(hVal) : '-'}</td>
                    <td class="px-4 py-3 text-right font-black ${sVal > 0 ? 'text-rose-700' : 'text-slate-800'} whitespace-nowrap">${formatARS(sVal)}</td>
                </tr>
            `;
        }).join('');
    }

    // Saldo Anterior de la cuenta (al inicio del período, al pie del historial)
    html += `
        <tr class="bg-slate-100/70 border-t-2 border-slate-200 font-semibold text-slate-600">
            <td class="px-4 py-3 whitespace-nowrap text-slate-500">${formatDateAR(currentCCData.fecha_desde) || 'Inicio'}</td>
            <td class="px-4 py-3 font-bold text-slate-700" colspan="3"><i class="fa-solid fa-clock-rotate-left text-slate-400 mr-1.5"></i>SALDO ANTERIOR DE LA CUENTA</td>
            <td class="px-4 py-3 text-right font-black text-navy whitespace-nowrap">${formatARS(saldoAnterior)}</td>
        </tr>
    `;

    tbody.innerHTML = html;
}

async function openModalPagoCC() {
    await loadMasterLists();
    const currCli = document.getElementById('select-cc-cliente')?.value;
    const pagoSel = document.getElementById('pago-cc-cliente');
    if (pagoSel && currCli) pagoSel.value = currCli;

    const fechaEl = document.getElementById('pago-cc-fecha');
    if (fechaEl) fechaEl.value = new Date().toISOString().split('T')[0];

    const montoEl = document.getElementById('pago-cc-monto');
    if (montoEl) montoEl.value = '';

    const conceptoEl = document.getElementById('pago-cc-concepto');
    if (conceptoEl) conceptoEl.value = 'Entrega a cuenta de viajes / servicios';

    const obsEl = document.getElementById('pago-cc-obs');
    if (obsEl) obsEl.value = '';

    const metodoEl = document.getElementById('pago-cc-metodo');
    if (metodoEl) metodoEl.value = 'transferencia';

    togglePagoCCChequesFields();
    await onClientePagoCCChanged();

    openModal('modal-cc-pago');
}

async function onClientePagoCCChanged() {
    const cliente = document.getElementById('pago-cc-cliente')?.value;
    const impSel = document.getElementById('pago-cc-imputacion');
    if (!impSel) return;

    if (!cliente) {
        impSel.innerHTML = `
            <option value="auto_fifo">⚡ Auto-Saldar por fecha más antigua (FIFO)</option>
            <option value="">💵 Entrega Libre a Cuenta (Generar Saldo a Favor)</option>
        `;
        return;
    }

    try {
        const res = await fetch(`/api/cuentas_corrientes/${encodeURIComponent(cliente)}/unpaid_invoices`);
        const json = await res.json();
        let html = `
            <option value="auto_fifo">⚡ Auto-Saldar por fecha más antigua (FIFO)</option>
            <option value="">💵 Entrega Libre a Cuenta (Generar Saldo a Favor)</option>
        `;
        if (json.status === 'success' && json.data && json.data.length > 0) {
            html += json.data.map(inv => `
                <option value="${inv.id}">📌 Factura ${inv.nro_factura} (${inv.concepto}) - Pendiente: $${inv.saldo_pendiente.toLocaleString('es-AR')}</option>
            `).join('');
        }
        impSel.innerHTML = html;
    } catch (e) {
        console.error("Error al cargar comprobantes pendientes:", e);
    }
}

function togglePagoCCChequesFields() {
    const metodo = document.getElementById('pago-cc-metodo')?.value;
    const container = document.getElementById('pago-cc-cheque-container');
    if (container) {
        if (metodo === 'cheque_fisico' || metodo === 'e_cheq') {
            container.classList.remove('hidden');
        } else {
            container.classList.add('hidden');
        }
    }
}

async function submitPagoCC(e) {
    e.preventDefault();
    const payload = {
        cliente: document.getElementById('pago-cc-cliente').value,
        imputar_a_ingreso_id: document.getElementById('pago-cc-imputacion')?.value || '',
        metodo: document.getElementById('pago-cc-metodo').value,
        cuenta_tesoreria: document.getElementById('pago-cc-cuenta-tesoreria')?.value || '',
        fecha: document.getElementById('pago-cc-fecha').value,
        monto: parseFloat(document.getElementById('pago-cc-monto').value) || 0,
        concepto: document.getElementById('pago-cc-concepto').value,
        banco: document.getElementById('pago-cc-banco')?.value || '',
        nro_cheque: document.getElementById('pago-cc-nro-cheque')?.value || '',
        vencimiento: document.getElementById('pago-cc-vencimiento')?.value || '',
        observaciones: document.getElementById('pago-cc-obs')?.value || ''
    };

    try {
        const res = await fetch('/api/cuentas_corrientes/pago', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cc-pago');
            await loadCuentaCorrienteCliente();
            await loadFacturacionData();
            await loadIngresosData();
            await loadChequesData();
            await loadViajesData();
            if (typeof loadTesoreriaData === 'function') await loadTesoreriaData();
            await loadDashboardData();
            showToast(`Entrega de $${payload.monto} registrada en la cuenta corriente de ${payload.cliente} e Ingresos.`);
        } else {
            showToast("Error al registrar entrega: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al registrar entrega:", err);
        showToast("Error de conexión al guardar entrega.", "error");
    }
}

function downloadPdfCuentaCorriente() {
    const cliente = document.getElementById('select-cc-cliente')?.value;
    if (!cliente) {
        showToast("Selecciona un cliente para descargar su Resumen de Cuenta Corriente.", "error");
        return;
    }
    const fDesde = document.getElementById('cc-fecha-desde')?.value || '';
    const fHasta = document.getElementById('cc-fecha-hasta')?.value || '';

    const url = `/api/cuentas_corrientes/${encodeURIComponent(cliente)}/pdf?fecha_desde=${fDesde}&fecha_hasta=${fHasta}`;
    window.open(url, '_blank');
}

