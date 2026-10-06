/**
 * ECONCATIVO - Tesorería & Conciliación Bancaria Module
 */
// ==================== TESORERIA & CONCILIACION MODULE ====================

let currentTesoreriaAccounts = [];

function showTesoreriaLoader() {
    const tbody = document.getElementById('tbody-tesoreria');
    if (!tbody) return;
    tbody.innerHTML = `
        <tr>
            <td colspan="11" class="py-24 text-center">
                <div class="flex flex-col items-center justify-center gap-3">
                    <div class="relative w-10 h-10">
                        <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                        <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                    </div>
                    <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                        Cargando tesorería y conciliación bancaria...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadTesoreriaData() {
    showTesoreriaLoader();
    try {
        const res = await fetch(`/api/tesoreria/summary?_t=${Date.now()}`);
        const json = await res.json();
        
        if (json.status !== 'success') {
            console.error("Error al cargar Tesorería:", json.message);
            showToast("Error al cargar resumen de Tesorería: " + json.message, "error");
            return;
        }

        currentTesoreriaAccounts = json.accounts || [];

        // Update KPI Cards
        const totals = json.totals || {};
        const totDispEl = document.getElementById('tes-total-disponible');
        const totBancEl = document.getElementById('tes-total-bancos');
        const totEfecEl = document.getElementById('tes-total-efectivo');
        const totBillEl = document.getElementById('tes-total-billeteras');
        const totCheqEl = document.getElementById('tes-total-cheques');

        if (totDispEl) totDispEl.innerText = formatARS(totals.total_disponible || 0);
        if (totBancEl) totBancEl.innerText = formatARS(totals.total_bancos || 0);
        if (totEfecEl) totEfecEl.innerText = formatARS(totals.total_efectivo || 0);
        if (totBillEl) totBillEl.innerText = formatARS(totals.total_billeteras || 0);
        if (totCheqEl) totCheqEl.innerText = formatARS(totals.total_cheques || 0);

        renderSaldosInicialesModal();
        updateTesoreriaSelectDropdowns();
        renderTesoreriaTable(currentTesoreriaAccounts);
    } catch (err) {
        console.error("Error al obtener resumen de Tesorería:", err);
    }
}

function renderSaldosInicialesModal() {
    const container = document.getElementById('init-saldos-container');
    if (!container) return;

    container.innerHTML = currentTesoreriaAccounts.map(acc => {
        const isSystemCheque = acc.id === 'CTA-005' || acc.tipo === 'Cheques';
        return `
            <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 flex items-center justify-between gap-3">
                <div class="flex-grow">
                    <label class="font-bold text-slate-800 text-xs block">${acc.nombre} (${acc.tipo})</label>
                    ${acc.cbu ? `<span class="text-[10px] text-slate-400 block">${acc.cbu}</span>` : ''}
                    <input type="number" step="0.01" id="init-${acc.id}" value="${isSystemCheque ? (acc.saldo_calculado || 0) : (acc.saldo_inicial || 0)}" ${isSystemCheque ? 'readonly' : ''} placeholder="0.00" class="w-full mt-1 p-2 bg-white border border-slate-200 rounded-lg font-bold ${isSystemCheque ? 'text-slate-400 bg-slate-100' : 'text-slate-900'} outline-none focus:ring-2 focus:ring-navy">
                </div>
                ${!isSystemCheque ? `
                    <button type="button" onclick="deleteCuentaTesoreria('${acc.id}', '${acc.nombre}')" class="text-rose-500 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 p-2 rounded-lg border border-rose-200 text-xs transition-all cursor-pointer mt-4" title="Eliminar / Dar de baja esta cuenta">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                ` : ''}
            </div>
        `;
    }).join('');
}

function updateTesoreriaSelectDropdowns() {
    if (typeof populateTreasurySelectsFromMaster === 'function') {
        populateTreasurySelectsFromMaster(currentTesoreriaAccounts);
    }
}

function renderTesoreriaTable(accounts) {
    const tbody = document.getElementById('tbody-tesoreria');
    if (!tbody) return;

    if (!accounts || accounts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" class="p-6 text-center text-slate-400">Sin datos de cuentas registradas.</td></tr>`;
        return;
    }

    tbody.innerHTML = accounts.map(acc => {
        let estadoBadge = '';
        if (acc.estado_conciliacion === 'CONCILIADO') {
            estadoBadge = `<span class="bg-emerald-100 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] border border-emerald-300 inline-flex items-center gap-1"><i class="fa-solid fa-circle-check text-emerald-600"></i> Conciliado</span>`;
        } else if (acc.estado_conciliacion === 'PENDIENTE_AJUSTE') {
            estadoBadge = `<span class="bg-rose-100 text-rose-800 font-bold px-2.5 py-1 rounded-full text-[11px] border border-rose-300 inline-flex items-center gap-1"><i class="fa-solid fa-triangle-exclamation text-rose-600"></i> Ajuste Pendiente</span>`;
        } else {
            estadoBadge = `<span class="bg-slate-100 text-slate-600 font-semibold px-2.5 py-1 rounded-full text-[11px] border border-slate-200 inline-flex items-center gap-1"><i class="fa-solid fa-clock text-slate-400"></i> Sin Cotejar</span>`;
        }

        let fechaCotejoHtml = '';
        const rawFecha = acc.fecha_cotejo ? String(acc.fecha_cotejo).trim() : '';
        const hasCotejo = acc.estado_conciliacion !== 'SIN_COTEJO' && rawFecha && !['-', 'NONE', 'NULL', 'UNDEFINED'].includes(rawFecha.toUpperCase());

        if (hasCotejo) {
            const fAr = typeof formatDateAR === 'function' ? formatDateAR(rawFecha) : rawFecha;
            if (fAr && fAr !== '-') {
                fechaCotejoHtml = `
                    <span class="block text-[10px] text-slate-500 font-medium mt-1 leading-tight inline-flex items-center gap-1" title="Fecha del último cotejo">
                        <i class="fa-regular fa-calendar-check text-slate-400"></i> ${fAr}
                    </span>
                `;
            }
        }

        const difColorClass = acc.diferencia === 0 
            ? 'text-slate-600 font-semibold' 
            : (acc.diferencia > 0 ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold');

        const isReadOnlyCheque = acc.tipo === 'Cheques';

        return `
            <tr class="hover:bg-slate-50 transition-all border-b border-slate-100">
                <td class="p-3.5 font-bold text-navy text-xs">
                    <div class="flex items-center gap-2">
                        <i class="${acc.tipo === 'Banco' ? 'fa-solid fa-building-columns text-indigo-600' : (acc.tipo === 'Efectivo' ? 'fa-solid fa-money-bill-wave text-emerald-600' : (acc.tipo === 'Billetera' ? 'fa-solid fa-wallet text-sky-600' : 'fa-solid fa-money-check-dollar text-teal-600'))}"></i>
                        <div>
                            <span>${acc.nombre}</span>
                            ${acc.cbu ? `<span class="block text-[10px] text-slate-400 font-normal">CBU: ${acc.cbu}</span>` : ''}
                        </div>
                    </div>
                </td>
                <td class="p-3.5 text-slate-600 font-medium">${acc.tipo}</td>
                <td class="p-3.5 text-right font-semibold text-slate-600">${formatARS(acc.saldo_inicial)}</td>
                <td class="p-3.5 text-right text-emerald-600 font-semibold">+${formatARS(acc.total_ingresos)}</td>
                <td class="p-3.5 text-right text-rose-600 font-semibold">-${formatARS(acc.total_egresos)}</td>
                <td class="p-3.5 text-right text-slate-600 font-medium">${formatARS(acc.transferencias_entrantes - acc.transferencias_salientes)}</td>
                <td class="p-3.5 text-right font-black text-navy text-sm">${formatARS(acc.saldo_calculado)}</td>
                <td class="p-3.5 text-right font-bold text-slate-800 text-sm">${acc.saldo_real > 0 ? formatARS(acc.saldo_real) : '<span class="text-slate-400 font-normal text-xs">-</span>'}</td>
                <td class="p-3.5 text-right ${difColorClass}">${acc.saldo_real > 0 ? (acc.diferencia >= 0 ? '+' + formatARS(acc.diferencia) : formatARS(acc.diferencia)) : '-'}</td>
                <td class="p-3.5 text-center">
                    <div class="inline-flex flex-col items-center justify-center">
                        ${estadoBadge}
                        ${fechaCotejoHtml}
                    </div>
                </td>
                <td class="p-3.5 text-center">
                    <div class="flex items-center justify-center gap-1.5">
                        ${isReadOnlyCheque ? '<span class="text-slate-400 text-[11px]">Auto-Sync</span>' : `
                            <button onclick="openConciliarModal('${acc.id}', '${acc.nombre}', ${acc.saldo_calculado}, '${acc.fecha_cotejo || ''}')" class="bg-navy hover:bg-navy-dark text-white font-bold px-2.5 py-1.5 rounded-lg text-xs shadow transition-all cursor-pointer inline-flex items-center gap-1" title="Cotejar saldo con Home Banking o Arqueo">
                                <i class="fa-solid fa-check-double"></i> Cotejar
                            </button>
                            <button onclick="deleteCuentaTesoreria('${acc.id}', '${acc.nombre}')" class="text-rose-500 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 p-1.5 rounded-lg border border-rose-200 text-xs transition-all cursor-pointer" title="Eliminar / Dar de baja cuenta">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        `}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

async function submitSaldosIniciales(e) {
    e.preventDefault();
    const payload = {};
    currentTesoreriaAccounts.forEach(acc => {
        if (acc.id !== 'CTA-005') {
            const inputEl = document.getElementById(`init-${acc.id}`);
            if (inputEl) {
                payload[acc.id] = parseFloat(inputEl.value) || 0;
            }
        }
    });

    try {
        const res = await fetch('/api/tesoreria/saldos_iniciales', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-saldos-iniciales');
            await loadTesoreriaData();
            showToast("Saldos iniciales actualizados correctamente.");
        } else {
            showToast("Error al guardar saldos iniciales: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al actualizar saldos iniciales:", err);
        showToast("Error de conexión al guardar saldos.", "error");
    }
}

async function promptAgregarNuevoBanco(targetSelectId = null) {
    const nuevoBanco = await showPromptModal({
        title: "Nuevo Banco / Cuenta de Tesorería",
        message: "Ingresá el nombre del banco o cuenta corriente para darlo de alta en el sistema.",
        label: "Nombre del Banco / Cuenta *",
        placeholder: "Ej: Banco Santander, Banco BBVA, Banco Nación...",
        iconClass: "fa-solid fa-building-columns text-emerald-600 text-xl",
        confirmText: "Crear Banco",
        confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-xs flex items-center gap-1.5",
        errorMessage: "Por favor, ingresá el nombre del banco."
    });

    if (!nuevoBanco || !nuevoBanco.trim()) return;
    const nombreBanco = nuevoBanco.trim();

    try {
        const res = await fetch('/api/tesoreria/account/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre: nombreBanco,
                banco: nombreBanco,
                tipo: 'Banco',
                saldo_inicial: 0
            })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadTesoreriaData();
            if (typeof loadMasterLists === 'function') await loadMasterLists();

            // Auto-select in the target select if specified
            if (targetSelectId) {
                const targetEl = document.getElementById(targetSelectId);
                if (targetEl) {
                    targetEl.value = nombreBanco;
                    if (targetSelectId === 'e-cuenta-tesoreria' && typeof toggleMedioPagoEgresoDirecto === 'function') {
                        toggleMedioPagoEgresoDirecto();
                    }
                }
            } else {
                ['chqp-banco', 'e-cuenta-tesoreria', 'o-cuenta-tesoreria', 'pago-cc-cuenta-tesoreria'].forEach(sId => {
                    const el = document.getElementById(sId);
                    if (el && Array.from(el.options).some(o => o.value === nombreBanco)) el.value = nombreBanco;
                });
            }
            showToast(`¡Banco "${nombreBanco}" registrado y seleccionado con éxito!`);
        } else {
            showToast("Error al crear banco: " + (json.message || ''), "error");
        }
    } catch (err) {
        console.error("Error al crear banco:", err);
        showToast("Error de conexión al registrar el banco.", "error");
    }
}

async function submitNuevaCuentaTesoreria(e) {
    e.preventDefault();
    const nombreVal = (document.getElementById('nc-nombre')?.value || '').trim();
    const bancoVal = (document.getElementById('nc-banco')?.value || '').trim();
    const finalNombre = nombreVal || bancoVal;
    if (!finalNombre) {
        showToast("El nombre o denominación del banco es requerido.", "warning");
        return;
    }

    const payload = {
        nombre: finalNombre,
        banco: bancoVal || finalNombre,
        tipo: document.getElementById('nc-tipo')?.value || 'Banco',
        nro_cuenta: document.getElementById('nc-nro-cuenta')?.value || '',
        cbu_num: document.getElementById('nc-cbu-val')?.value || '',
        alias: document.getElementById('nc-alias')?.value || '',
        titular: document.getElementById('nc-titular')?.value || '',
        cuit: document.getElementById('nc-cuit')?.value || '',
        saldo_inicial: parseFloat(document.getElementById('nc-saldo-inicial')?.value) || 0,
        observaciones: document.getElementById('nc-observaciones')?.value || ''
    };

    try {
        const res = await fetch('/api/tesoreria/account/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-nueva-cuenta-tesoreria');
            document.getElementById('form-nueva-cuenta-tesoreria')?.reset();
            await loadTesoreriaData();
            if (typeof loadMasterLists === 'function') await loadMasterLists();

            // Auto-select in any active modal
            ['chqp-banco', 'e-cuenta-tesoreria', 'o-cuenta-tesoreria', 'pago-cc-cuenta-tesoreria'].forEach(sId => {
                const el = document.getElementById(sId);
                if (el && Array.from(el.options).some(o => o.value === finalNombre)) el.value = finalNombre;
            });

            showToast(`Cuenta "${finalNombre}" creada exitosamente.`);
        } else {
            showToast("Error al crear la cuenta: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al crear nueva cuenta:", err);
        showToast("Error de conexión al crear la cuenta.", "error");
    }
}

async function deleteCuentaTesoreria(accountId, accountName) {
    const confirmed = await showConfirmModal(
        "Eliminar Cuenta de Tesorería",
        `¿Está seguro de eliminar la cuenta <b>"${accountName}"</b>? Esta acción no se puede deshacer.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    showLoading("Eliminando Cuenta", `Eliminando "${accountName}" de Tesorería...`);
    try {
        const res = await fetch('/api/tesoreria/account/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_id: accountId })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadTesoreriaData();
            if (typeof loadMasterLists === 'function') await loadMasterLists();
            showToast(`Cuenta "${accountName}" eliminada correctamente.`);
        } else {
            showToast("Error al eliminar la cuenta: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al eliminar cuenta:", err);
        showToast("Error de conexión al eliminar la cuenta.", "error");
    } finally {
        hideLoading();
    }
}

async function submitGastosBancarios(e) {
    e.preventDefault();
    const payload = {
        cuenta_nombre: document.getElementById('gb-cuenta').value,
        monto: parseFloat(document.getElementById('gb-monto').value) || 0,
        fecha: document.getElementById('gb-fecha').value,
        concepto: document.getElementById('gb-concepto').value,
        observaciones: document.getElementById('gb-observaciones').value
    };

    try {
        const res = await fetch('/api/tesoreria/gastos_bancarios', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-gastos-bancarios');
            await loadTesoreriaData();
            await loadEgresosData();
            await loadDashboardData();
            showToast(`Gasto bancario de $${payload.monto} registrado exitosamente en Egresos.`);
        } else {
            showToast("Error al registrar gasto bancario: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al registrar gasto bancario:", err);
        showToast("Error de conexión al guardar gasto bancario.", "error");
    }
}

async function submitTransferenciaTesoreria(e) {
    e.preventDefault();
    const orig = document.getElementById('trf-origen').value;
    const dest = document.getElementById('trf-destino').value;
    if (orig === dest) {
        showToast("La cuenta de origen y destino no pueden ser la misma.", "error");
        return;
    }

    const payload = {
        origen: orig,
        destino: dest,
        monto: parseFloat(document.getElementById('trf-monto').value) || 0,
        fecha: document.getElementById('trf-fecha').value,
        concepto: document.getElementById('trf-concepto').value,
        observaciones: document.getElementById('trf-observaciones').value
    };

    try {
        const res = await fetch('/api/tesoreria/transferencia', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-transferencia-tesoreria');
            await loadTesoreriaData();
            showToast(`Transferencia de $${payload.monto} entre ${orig} y ${dest} registrada.`);
        } else {
            const alertEl = document.getElementById('alert-trf-fondos');
            if (alertEl) {
                alertEl.classList.remove('hidden');
                alertEl.innerHTML = `
                    <div class="flex items-start gap-2.5">
                        <i class="fa-solid fa-circle-exclamation text-rose-600 text-lg shrink-0 mt-0.5 animate-bounce"></i>
                        <div>
                            <div class="font-black text-rose-900 text-xs uppercase tracking-wide">⛔ OPERACIÓN BLOQUEADA / FONDOS INSUFICIENTES</div>
                            <div class="text-[11.5px] font-bold text-rose-900 mt-0.5">${json.message || 'Error al registrar transferencia.'}</div>
                            <div class="text-[10.5px] font-medium text-rose-700 mt-1">
                                💡 Cambia la cuenta de origen o reduce el monto a transferir.
                            </div>
                        </div>
                    </div>
                `;
            }
            showToast("Error: " + (json.message || ''), "error");
        }
    } catch (err) {
        console.error("Error al registrar transferencia:", err);
        showToast("Error de conexión al guardar transferencia.", "error");
    }
}

function openConciliarModal(accId, accTitle, saldoCalc, fechaCotejo = '') {
    document.getElementById('concil-account-id').value = accId;
    document.getElementById('concil-account-title').innerText = accTitle;
    let calcText = `Saldo Calculado por Sistema: <b>${formatARS(saldoCalc)}</b>`;
    if (fechaCotejo && !['-', 'none', 'null', ''].includes(String(fechaCotejo).toLowerCase().trim())) {
        const fAr = typeof formatDateAR === 'function' ? formatDateAR(fechaCotejo) : fechaCotejo;
        if (fAr && fAr !== '-') {
            calcText += `<span class="block text-[11px] text-slate-500 mt-1"><i class="fa-regular fa-calendar-check text-emerald-600 mr-1"></i>Último cotejo registrado: <b>${fAr}</b></span>`;
        }
    }
    document.getElementById('concil-account-calc').innerHTML = calcText;
    document.getElementById('concil-saldo-real').value = '';
    document.getElementById('concil-fecha').value = new Date().toISOString().split('T')[0];
    openModal('modal-conciliar-cuenta');
}

async function submitConciliarCuenta(e) {
    e.preventDefault();
    const payload = {
        account_id: document.getElementById('concil-account-id').value,
        saldo_real: parseFloat(document.getElementById('concil-saldo-real').value) || 0,
        fecha_cotejo: document.getElementById('concil-fecha').value
    };

    try {
        const res = await fetch('/api/tesoreria/conciliar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-conciliar-cuenta');
            await loadTesoreriaData();
            showToast("Cotejo administrativo de saldo guardado correctamente.");
        } else {
            showToast("Error al cotejar cuenta: " + json.message, "error");
        }
    } catch (err) {
        console.error("Error al cotejar cuenta:", err);
        showToast("Error de conexión al guardar cotejo.", "error");
    }
}




