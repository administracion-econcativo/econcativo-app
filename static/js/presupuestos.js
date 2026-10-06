/**
 * ECONCATIVO - Presupuestos & Cotizaciones Module
 */
// PRESUPUESTOS MODULE
let presupuestosFilterDebounceTimer = null;

function showPresupuestosLoader() {
    const tbody = document.getElementById('tbody-presupuestos');
    const counter = document.getElementById('counter-presupuestos');
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
                        Cargando cotizaciones y presupuestos...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadPresupuestosData() {
    showPresupuestosLoader();
    try {
        const res = await fetch(`/api/presupuestos?_t=${Date.now()}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.rows.length) {
            const tbody = document.getElementById('tbody-presupuestos');
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No hay presupuestos registrados. ¡Haz clic en "Nuevo Presupuesto" para crear el primero!</td></tr>`;
            const counter = document.getElementById('counter-presupuestos');
            if (counter) counter.innerText = '0 presupuestos';
            currentPresupuestos = [];
            return;
        }

        currentPresupuestos = json.rows;
        updatePresupuestosTipoFilter(currentPresupuestos);
        applyPresupuestosFilter();

    } catch (err) {
        console.error("Error al cargar presupuestos:", err);
        const tbody = document.getElementById('tbody-presupuestos');
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-500 font-medium">Error al cargar presupuestos.</td></tr>`;
    }
}

function updatePresupuestosTipoFilter(rows) {
    const sel = document.getElementById('filter-p-tipo');
    if (!sel) return;
    const currVal = sel.value;
    const typesFromData = (rows || []).map(r => str(getRowProp(r, ['Tipo servicio'])).trim()).filter(Boolean);
    const masterAct = (window.masterLists && window.masterLists.actividades) || (typeof masterLists !== 'undefined' && masterLists.actividades) || [];
    const baseTypes = ['Viaje / Transporte', 'Servicio de Maquinaria', 'Flete Especial'];
    const allTypes = [...new Set([...baseTypes, ...masterAct, ...typesFromData])].sort();

    sel.innerHTML = `<option value="">Todos los Servicios</option>` +
        allTypes.map(t => `<option value="${t}">${t}</option>`).join('');
    if (currVal && Array.from(sel.options).some(o => o.value.toLowerCase() === currVal.toLowerCase())) {
        sel.value = currVal;
    }
}

function renderPresupuestosTable(rows) {
    const tbody = document.getElementById('tbody-presupuestos');
    const counter = document.getElementById('counter-presupuestos');

    counter.innerText = `${rows.length} presupuestos`;

    const sortedRows = sortRecordsMostRecent(rows, ['Fecha'], ['ID presupuesto', 'ID']);

    if (!sortedRows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No se encontraron presupuestos con los filtros seleccionados.</td></tr>`;
        renderPaginationBar('presupuestos', 'pagination-presupuestos', { totalItems: 0 });
        return;
    }

    paginateAndRender('presupuestos', 'pagination-presupuestos', sortedRows, (pageRows) => {
        tbody.innerHTML = pageRows.map(r => {
            const pid = getRowProp(r, ['ID presupuesto', 'ID']);
            const st = str(getRowProp(r, ['Estado']) || 'Pendiente');
            const isApproved = st.toLowerCase() === 'aprobado';
            const isRejected = st.toLowerCase() === 'rechazado';
            const assocViaje = getRowProp(r, ['ID viaje asociado']);

            let badgeClass = 'bg-amber-100 text-amber-800 border-amber-200';
            let badgeIcon = '';
            if (isApproved) {
                badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200 font-bold';
                badgeIcon = '<i class="fa-solid fa-lock mr-1"></i>';
            } else if (isRejected) {
                badgeClass = 'bg-rose-100 text-rose-800 border-rose-200 font-bold';
                badgeIcon = '<i class="fa-solid fa-xmark mr-1"></i>';
            }

            const combModText = str(getRowProp(r, ['Modalidad combustible', 'modalidad_combustible', 'Observaciones']) || '');
            const isSinComb = combModText.toLowerCase().includes('sin combustible');
            const combBadge = isSinComb 
                ? `<span class="bg-amber-100 text-amber-900 border border-amber-300 font-bold px-1.5 py-0.5 rounded text-[10px] inline-block mt-0.5" title="Sin Combustible - A liquidar post-servicio">⛽ Sin Combustible</span>`
                : `<span class="bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold px-1.5 py-0.5 rounded text-[10px] inline-block mt-0.5">🟢 Con Combustible</span>`;

            return `
                <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all">
                    <td class="px-3 py-2.5 font-bold text-navy whitespace-nowrap">${pid}</td>
                    <td class="px-3 py-2.5 text-slate-600 whitespace-nowrap">${formatDateAR(getRowProp(r, ['Fecha']))}</td>
                    <td class="px-3 py-2.5 font-semibold text-slate-800">${getRowProp(r, ['Cliente']) || '-'}</td>
                    <td class="px-3 py-2.5 text-slate-700 font-medium text-[11px]">
                        <div>${getRowProp(r, ['Tipo servicio']) || '-'}</div>
                        ${combBadge}
                    </td>
                    <td class="px-3 py-2.5 text-slate-600 font-medium max-w-xs truncate" title="${getRowProp(r, ['Detalle/Concepto'])}">${getRowProp(r, ['Detalle/Concepto']) || '-'}</td>
                    <td class="px-3 py-2.5 font-bold text-navy whitespace-nowrap">${formatARS(getRowProp(r, ['Total']))}</td>
                    <td class="px-3 py-2.5 whitespace-nowrap">
                        <span class="px-2.5 py-1 rounded-full text-[10px] border ${badgeClass}">
                            ${badgeIcon}${st}
                        </span>
                    </td>
                    <td class="px-3 py-2.5 text-right whitespace-nowrap">
                        <div class="inline-flex items-center justify-end gap-1.5">
                            <a href="/api/presupuestos/${pid}/pdf" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2 py-1 rounded text-[11px] border border-red-200 transition-all" title="Ver / Descargar PDF">
                                <i class="fa-solid fa-file-pdf"></i> PDF
                            </a>

                            ${(!isApproved && !isRejected) ? `
                                <button onclick="editPresupuesto('${pid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[11px] transition-all cursor-pointer" title="Editar Presupuesto">
                                    <i class="fa-solid fa-pen"></i> Editar
                                </button>
                                <button onclick="aprobarPresupuesto('${pid}', this)" class="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1 rounded text-[11px] shadow-sm transition-all cursor-pointer" title="Aprobar y Convertir a Servicio">
                                    <i class="fa-solid fa-check"></i> Aprobar
                                </button>
                                <button onclick="rechazarPresupuesto('${pid}')" class="inline-flex items-center gap-1 bg-rose-500 hover:bg-rose-600 text-white font-bold px-2 py-1 rounded text-[11px] shadow-sm transition-all cursor-pointer" title="Marcar como Rechazado">
                                    <i class="fa-solid fa-xmark"></i> Rechazar
                                </button>
                            ` : (isApproved ? `
                                <span class="inline-flex items-center gap-1 bg-slate-100 text-slate-400 font-bold px-2 py-1 rounded text-[11px] border border-slate-200" title="Presupuesto Aprobado (Edición bloqueada)">
                                    <i class="fa-solid fa-lock"></i> Bloqueado
                                </span>
                                <span class="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded" title="Convertido a ${assocViaje || ''}">
                                    <i class="fa-solid fa-circle-check"></i> ${assocViaje || 'OK'}
                                </span>
                            ` : `
                                <span class="inline-flex items-center gap-1 text-[10px] font-bold text-rose-600 bg-rose-50 border border-rose-200 px-2 py-1 rounded">
                                    <i class="fa-solid fa-xmark"></i> Rechazado
                                </span>
                            `)}

                            <button onclick="deletePresupuesto('${pid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 transition-all cursor-pointer" title="Eliminar Presupuesto y su operación asociada">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }, 10);
}

let lastPresupuestosQueryActive = false;

function filterPresupuestosTable(delay = 180, isDropdown = false) {
    const rawQuery = (document.getElementById('search-presupuestos')?.value || '').trim();
    const isNowActive = rawQuery.length >= 3;

    // Si el usuario escribe y tiene menos de 3 caracteres (y antes tampoco había búsqueda activa), no hacemos nada
    if (!isDropdown && !isNowActive && !lastPresupuestosQueryActive) {
        return;
    }

    resetTablePaginationPage('presupuestos');

    if (presupuestosFilterDebounceTimer) {
        clearTimeout(presupuestosFilterDebounceTimer);
    }

    showPresupuestosLoader();
    lastPresupuestosQueryActive = isNowActive;

    presupuestosFilterDebounceTimer = setTimeout(() => {
        applyPresupuestosFilter();
    }, delay);
}

function applyPresupuestosFilter() {
    const fCliente = (document.getElementById('filter-p-cliente')?.value || '').toLowerCase();
    const fEstado = (document.getElementById('filter-p-estado')?.value || '').toLowerCase();
    const fTipo = (document.getElementById('filter-p-tipo')?.value || '').toLowerCase();
    const fFecha = (document.getElementById('filter-p-fecha')?.value || '').toLowerCase();
    const rawQuery = (document.getElementById('search-presupuestos')?.value || '').trim();
    const fQuery = rawQuery.length >= 3 ? rawQuery.toLowerCase() : '';

    const filtered = (currentPresupuestos || []).filter(r => {
        const cliente = str(getRowProp(r, ['Cliente'])).toLowerCase();
        const estado = str(getRowProp(r, ['Estado'])).toLowerCase();
        const tipo = str(getRowProp(r, ['Tipo servicio'])).toLowerCase();
        const fecha = str(getRowProp(r, ['Fecha'])).toLowerCase();
        const fullText = (str(getRowProp(r, ['ID presupuesto', 'ID'])) + " " + cliente + " " + str(getRowProp(r, ['Detalle/Concepto']))).toLowerCase();

        if (fCliente && cliente !== fCliente) return false;
        if (fEstado && estado !== fEstado) return false;
        if (fTipo && !tipo.includes(fTipo)) return false;
        if (fFecha && !fecha.includes(fFecha)) return false;
        if (fQuery && !fullText.includes(fQuery)) return false;

        return true;
    });

    renderPresupuestosTable(filtered);
}

function resetPresupuestosFilters() {
    const c = document.getElementById('filter-p-cliente');
    const e = document.getElementById('filter-p-estado');
    const t = document.getElementById('filter-p-tipo');
    const f = document.getElementById('filter-p-fecha');
    const s = document.getElementById('search-presupuestos');
    if (c) {
        c.value = '';
        if (c._searchableSelect) c._searchableSelect.syncValue();
    }
    if (e) e.value = '';
    if (t) t.value = '';
    if (f) f.value = '';
    if (s) s.value = '';
    lastPresupuestosQueryActive = false;
    filterPresupuestosTable(120, true);
}

async function rechazarPresupuesto(pid) {
    try {
        const res = await fetch('/api/presupuestos/rechazar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: pid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadPresupuestosData();
            showToast(`Presupuesto ${pid} marcado como RECHAZADO.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al rechazar presupuesto.", "error");
    }
}

function openNuevoPresupuestoModal() {
    const editId = document.getElementById('p-id-edit');
    if (editId) editId.value = '';
    const form = document.getElementById('form-presupuesto');
    if (form) form.reset();
    const title = document.getElementById('modal-p-title');
    if (title) title.innerHTML = `<i class="fa-solid fa-file-pdf text-amber"></i> Generar Nuevo Presupuesto Comercial`;
    if (document.getElementById('p-validez')) document.getElementById('p-validez').value = '15 días';
    const ivaInput = document.getElementById('p-iva-pct');
    if (ivaInput) ivaInput.value = '21';
    resetPresupuestoItems('Viaje');
    openModal('modal-presupuesto');
}

function editPresupuesto(pid) {
    const target = currentPresupuestos.find(r => str(getRowProp(r, ['ID presupuesto', 'ID'])) === str(pid));
    if (!target) return;

    if (str(getRowProp(target, ['Estado'])).toLowerCase() === 'aprobado') {
        showToast(`El Presupuesto ${pid} está APROBADO y bloqueado para ediciones.`, "error");
        return;
    }

    document.getElementById('modal-p-title').innerHTML = `<i class="fa-solid fa-pen text-amber"></i> Editar Presupuesto ${pid}`;
    document.getElementById('p-id-edit').value = pid;
    document.getElementById('p-cliente').value = getRowProp(target, ['Cliente']);
    document.getElementById('p-cuit').value = getRowProp(target, ['CUIT']);
    document.getElementById('p-validez').value = getRowProp(target, ['Validez']) || '15 días';
    const rawIvaVal = getRowProp(target, ['IVA %', 'IVA', 'iva_pct']);
    const parsedIvaVal = parseFloat(rawIvaVal);
    document.getElementById('p-iva-pct').value = !isNaN(parsedIvaVal) ? parsedIvaVal : 21;
    document.getElementById('p-observaciones').value = getRowProp(target, ['Observaciones']);

    let itemsStr = getRowProp(target, ['Items JSON', 'items_json', 'ID viaje asociado / Items JSON', 'ID viaje asociado']);
    let items = [];
    if (itemsStr && str(itemsStr).trim().startsWith('[')) {
        try {
            items = JSON.parse(str(itemsStr).trim());
        } catch (e) {
            console.error("Error al parsear Items JSON:", e);
        }
    }

    if (items && items.length) {
        nextItemId = 1;
        items.forEach(it => it.id = nextItemId++);
        presupuestoItems = items;
    } else {
        nextItemId = 1;
        const tipoOp = str(getRowProp(target, ['Tipo servicio'])).includes('Servicio') ? 'Servicio' : 'Viaje';
        presupuestoItems = [{
            id: nextItemId++,
            tipo: tipoOp,
            actividad: getRowProp(target, ['Tipo servicio']) || (tipoOp === 'Viaje' ? TRANSPORT_ACTIVITIES[0] : SERVICE_ACTIVITIES[0]),
            subtipo_granel: 'General',
            toneladas: '',
            km: '',
            origen: '',
            destino: '',
            descripcion: getRowProp(target, ['Detalle/Concepto']),
            detalle_trabajo: getRowProp(target, ['Detalle/Concepto']),
            ubicacion: '',
            horas: '',
            neto: Math.max(0, parseFloat(getRowProp(target, ['Total']) || 0))
        }];
    }

    renderPresupuestoItems();
    openModal('modal-presupuesto');
}

async function aprobarPresupuesto(pid, btnElement) {
    if (btnElement) {
        btnElement.disabled = true;
        btnElement.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Aprobando...`;
    }
    try {
        const res = await fetch('/api/presupuestos/aprobar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: pid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadPresupuestosData();
            await loadViajesData();
            showToast(`¡Presupuesto ${pid} Aprobado! Se generó la Operación ${json.viaje_id}.`);
        } else {
            showToast("Error: " + json.message, "error");
            if (btnElement) {
                btnElement.disabled = false;
                btnElement.innerHTML = `<i class="fa-solid fa-check"></i> Aprobar`;
            }
        }
    } catch (err) {
        showToast("Error al aprobar presupuesto.", "error");
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = `<i class="fa-solid fa-check"></i> Aprobar`;
        }
    }
}

async function deletePresupuesto(pid) {
    const confirmed = await showConfirmModal(
        "Eliminar Presupuesto",
        `¿Estás seguro de eliminar el presupuesto <b>${pid}</b>? Si tenía un viaje asociado también será eliminado.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    showLoading("Eliminando Presupuesto", `Eliminando ${pid} de la base de datos...`);
    try {
        const res = await fetch('/api/presupuestos/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: pid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('p-id-edit') && document.getElementById('p-id-edit').value === pid) {
                document.getElementById('p-id-edit').value = '';
                const form = document.getElementById('form-presupuesto');
                if (form) form.reset();
            }
            await loadPresupuestosData();
            await loadViajesData();
            showToast(`Presupuesto ${pid} eliminado correctamente.`);
        } else {
            showToast("Error al eliminar: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar presupuesto.", "error");
    } finally {
        hideLoading();
    }
}

function setPresupuestoTipoOperacion(tipo) {
    const hiddenInput = document.getElementById('p-tipo-operacion');
    if (hiddenInput) {
        hiddenInput.value = tipo;
    }

    const btnViaje = document.getElementById('btn-p-tipo-viaje');
    const btnServicio = document.getElementById('btn-p-tipo-servicio');
    if (btnViaje && btnServicio) {
        if (tipo === 'Viaje') {
            btnViaje.classList.add('active', 'btn-primary');
            btnViaje.classList.remove('btn-outline-secondary');
            btnServicio.classList.remove('active', 'btn-primary');
            btnServicio.classList.add('btn-outline-secondary');
        } else {
            btnServicio.classList.add('active', 'btn-primary');
            btnServicio.classList.remove('btn-outline-secondary');
            btnViaje.classList.remove('active', 'btn-primary');
            btnViaje.classList.add('btn-outline-secondary');
        }
    }
    if (typeof resetPresupuestoItems === 'function') {
        resetPresupuestoItems(tipo);
    }
}

// PRESUPUESTOS MULTI-ITEM & ACTIVITY FILTERING
const TRANSPORT_ACTIVITIES = [
    "492229 - TRANSPORTE AUTOMOTOR DE MERCADERÍAS A GRANEL N.C.P.",
    "492290 - SERVICIO DE TRANSPORTE AUTOMOTOR DE CARGAS N.C.P.",
    "521010 - SERVICIOS DE MANIPULACIÓN DE CARGA EN EL ÁMBITO TERRESTRE"
];

const SERVICE_ACTIVITIES = [
    "452990 - MANTENIMIENTO Y REPARACIÓN DEL MOTOR N.C.P., MECÁNICA INTEGRAL",
    "466940 - VENTA AL POR MAYOR DE PRODUCTOS INTERMEDIOS N.C.P.",
    "771190 - ALQUILER DE VEHÍCULOS AUTOMOTORES N.C.P., SIN CONDUCTOR NI OPERARIOS",
    "960990 - SERVICIOS PERSONALES N.C.P."
];

let presupuestoItems = [];
let nextItemId = 1;

function resetPresupuestoItems(initialTipo = 'Viaje') {
    nextItemId = 1;
    presupuestoItems = [createDefaultPresupuestoItem(initialTipo)];
    renderPresupuestoItems();
}

function createDefaultPresupuestoItem(tipo = 'Viaje') {
    const isViaje = tipo === 'Viaje';
    const defaultAct = isViaje ? TRANSPORT_ACTIVITIES[0] : SERVICE_ACTIVITIES[0];
    return {
        id: nextItemId++,
        tipo: tipo,
        actividad: defaultAct,
        subtipo_granel: 'Cereales',
        toneladas: '',
        km: '',
        origen: '',
        destino: '',
        descripcion: '',
        detalle_trabajo: '',
        ubicacion: '',
        horas: '',
        neto: 0
    };
}

function addPresupuestoItem(tipo = 'Viaje') {
    saveCurrentPresupuestoItemValues();
    presupuestoItems.push(createDefaultPresupuestoItem(tipo));
    renderPresupuestoItems();
}

function removePresupuestoItem(id) {
    if (presupuestoItems.length <= 1) {
        showToast("El presupuesto debe tener al menos una actividad.", "error");
        return;
    }
    saveCurrentPresupuestoItemValues();
    presupuestoItems = presupuestoItems.filter(item => item.id !== id);
    renderPresupuestoItems();
}

function saveCurrentPresupuestoItemValues() {
    presupuestoItems.forEach(item => {
        const id = item.id;
        const actEl = document.getElementById(`p-item-actividad-${id}`);
        if (actEl) item.actividad = actEl.value;

        const isViaje = item.tipo === 'Viaje';
        if (isViaje) {
            const isGranel = (item.actividad || '').includes('492229');
            if (isGranel) {
                const subEl = document.getElementById(`p-item-subtipo-${id}`);
                if (subEl) item.subtipo_granel = subEl.value;
                const tonEl = document.getElementById(`p-item-toneladas-${id}`);
                if (tonEl) item.toneladas = tonEl.value;
            } else {
                item.toneladas = '';
                item.subtipo_granel = 'General';
            }
            const kmEl = document.getElementById(`p-item-km-${id}`);
            if (kmEl) item.km = kmEl.value;
            const oriEl = document.getElementById(`p-item-origen-${id}`);
            if (oriEl) item.origen = oriEl.value;
            const desEl = document.getElementById(`p-item-destino-${id}`);
            if (desEl) item.destino = desEl.value;
            const descEl = document.getElementById(`p-item-descripcion-${id}`);
            if (descEl) item.descripcion = descEl.value;
        } else {
            const trabEl = document.getElementById(`p-item-trabajo-${id}`);
            if (trabEl) item.detalle_trabajo = trabEl.value;
            const ubiEl = document.getElementById(`p-item-ubicacion-${id}`);
            if (ubiEl) item.ubicacion = ubiEl.value;
            const horEl = document.getElementById(`p-item-horas-${id}`);
            if (horEl) item.horas = horEl.value;
        }

        const netEl = document.getElementById(`p-item-neto-${id}`);
        if (netEl) item.neto = parseFloat(netEl.value) || 0;
    });
}

function onPresupuestoItemActivityChange(id, newAct) {
    saveCurrentPresupuestoItemValues();
    const item = presupuestoItems.find(it => it.id === id);
    if (item) {
        item.actividad = newAct;
        renderPresupuestoItems();
    }
}

function onPresupuestoItemTipoChange(id, newTipo) {
    saveCurrentPresupuestoItemValues();
    const item = presupuestoItems.find(it => it.id === id);
    if (item) {
        item.tipo = newTipo;
        item.actividad = newTipo === 'Viaje' ? TRANSPORT_ACTIVITIES[0] : SERVICE_ACTIVITIES[0];
        renderPresupuestoItems();
    }
}

function renderPresupuestoItems() {
    const container = document.getElementById('p-items-container');
    if (!container) return;

    container.innerHTML = presupuestoItems.map((item, index) => {
        const isViaje = item.tipo === 'Viaje';
        const isGranel = isViaje && (item.actividad || '').includes('492229');
        const activitiesList = isViaje ? TRANSPORT_ACTIVITIES : SERVICE_ACTIVITIES;
        const totalItems = presupuestoItems.length;

        return `
            <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-3 relative transition-all hover:border-amber-300 shadow-sm">
                <div class="flex items-center justify-between border-b border-slate-100 pb-2">
                    <div class="flex items-center gap-2">
                        <span class="bg-navy text-white font-black px-2.5 py-0.5 rounded text-[11px]">Actividad #${index + 1}</span>
                        <div class="inline-flex bg-slate-100 p-0.5 rounded-lg text-[11px] font-bold">
                            <button type="button" onclick="onPresupuestoItemTipoChange(${item.id}, 'Viaje')" class="px-2.5 py-1 rounded-md transition-all cursor-pointer ${isViaje ? 'bg-navy text-white shadow' : 'text-slate-600 hover:text-navy'}">
                                <i class="fa-solid fa-truck mr-1"></i> Viaje / Transporte
                            </button>
                            <button type="button" onclick="onPresupuestoItemTipoChange(${item.id}, 'Servicio')" class="px-2.5 py-1 rounded-md transition-all cursor-pointer ${!isViaje ? 'bg-navy text-white shadow' : 'text-slate-600 hover:text-navy'}">
                                <i class="fa-solid fa-trowel-bricks mr-1"></i> Servicio Maquinaria
                            </button>
                        </div>
                    </div>
                    ${totalItems > 1 ? `
                        <button type="button" onclick="removePresupuestoItem(${item.id})" class="text-rose-500 hover:text-rose-700 font-bold px-2 py-1 bg-rose-50 hover:bg-rose-100 rounded border border-rose-200 transition-all text-xs flex items-center gap-1 cursor-pointer" title="Eliminar este ítem">
                            <i class="fa-solid fa-trash-can"></i> Eliminar
                        </button>
                    ` : ''}
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div class="sm:col-span-2">
                        <label class="font-semibold text-slate-700">Actividad de la Empresa *</label>
                        <select id="p-item-actividad-${item.id}" required onchange="onPresupuestoItemActivityChange(${item.id}, this.value)" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                            ${activitiesList.map(act => `<option value="${act}" ${act === item.actividad ? 'selected' : ''}>${act}</option>`).join('')}
                        </select>
                    </div>

                    ${isViaje ? `
                        ${isGranel ? `
                            <div>
                                <label class="font-semibold text-slate-700">Material / Sub-tipo Granel</label>
                                <select id="p-item-subtipo-${item.id}" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                                    <option value="Cereales" ${item.subtipo_granel === 'Cereales' ? 'selected' : ''}>🌾 Cereales (Comisión Chofer)</option>
                                    <option value="Bodoque" ${item.subtipo_granel === 'Bodoque' ? 'selected' : ''}>🧱 Bodoque</option>
                                    <option value="Basura" ${item.subtipo_granel === 'Basura' ? 'selected' : ''}>🗑️ Basura</option>
                                    <option value="Otros" ${item.subtipo_granel === 'Otros' ? 'selected' : ''}>📦 Otros / General</option>
                                </select>
                            </div>

                            <div>
                                <label class="font-semibold text-slate-700">Toneladas Estimadas (Peso)</label>
                                <input type="number" step="0.1" min="0" onkeydown="if(event.key==='-')event.preventDefault();" oninput="if(this.value<0)this.value=0;" id="p-item-toneladas-${item.id}" value="${item.toneladas || ''}" placeholder="Ej: 30 Tn" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                            </div>
                        ` : ''}

                        <div>
                            <label class="font-semibold text-slate-700">Distancia Estimada (km) *</label>
                            <input type="number" step="1" min="0" onkeydown="if(event.key==='-')event.preventDefault();" oninput="if(this.value<0)this.value=0;" id="p-item-km-${item.id}" value="${item.km || ''}" placeholder="Ej: 350 km" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>

                        <div>
                            <label class="font-semibold text-slate-700">Origen / Planta Salida</label>
                            <input type="text" id="p-item-origen-${item.id}" value="${item.origen || ''}" placeholder="Ej: Oncativo" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>

                        <div>
                            <label class="font-semibold text-slate-700">Destino / Puerto Entrega</label>
                            <input type="text" id="p-item-destino-${item.id}" value="${item.destino || ''}" placeholder="Ej: Puerto Rosario" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>

                        <div class="sm:col-span-2">
                            <label class="font-semibold text-slate-700">Descripción / Detalles de la Carga</label>
                            <input type="text" id="p-item-descripcion-${item.id}" value="${item.descripcion || ''}" placeholder="Ej: Carga general en chasis y acoplado..." class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>
                    ` : `
                        <div class="sm:col-span-2">
                            <label class="font-semibold text-slate-700">Trabajo / Servicio a Realizar *</label>
                            <input type="text" id="p-item-trabajo-${item.id}" value="${item.detalle_trabajo || ''}" placeholder="Ej: Nivelación y compactación de suelo..." class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>

                        <div>
                            <label class="font-semibold text-slate-700">Ubicación / Lugar de la Obra</label>
                            <input type="text" id="p-item-ubicacion-${item.id}" value="${item.ubicacion || ''}" placeholder="Ej: Obra Calle San Martín" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>

                        <div>
                            <label class="font-semibold text-slate-700">Horas / Cantidad Estimada</label>
                            <input type="number" step="0.5" min="0" onkeydown="if(event.key==='-')event.preventDefault();" oninput="if(this.value<0)this.value=0;" id="p-item-horas-${item.id}" value="${item.horas || ''}" placeholder="Ej: 12 hs" class="w-full mt-1 p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium outline-none focus:ring-2 focus:ring-navy">
                        </div>
                    `}

                    <div class="sm:col-span-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                        <label class="font-bold text-slate-800">Importe Neto Cotizado ($) para esta actividad *</label>
                        <input type="number" step="0.01" min="0" onkeydown="if(event.key==='-')event.preventDefault();" oninput="if(this.value<0)this.value=0; calcPresupuestoTotals();" id="p-item-neto-${item.id}" value="${item.neto || ''}" placeholder="0.00" required class="w-40 p-2 bg-white border border-slate-300 rounded-lg font-black text-navy text-right outline-none focus:ring-2 focus:ring-navy">
                    </div>
                </div>
            </div>
        `;
    }).join('');

    calcPresupuestoTotals();
}

function calcPresupuestoTotals() {
    let subtotalNeto = 0;
    presupuestoItems.forEach(item => {
        const netEl = document.getElementById(`p-item-neto-${item.id}`);
        if (netEl) {
            let val = parseFloat(netEl.value) || 0;
            if (val < 0) {
                val = 0;
                netEl.value = '0';
            }
            item.neto = val;
        }
        subtotalNeto += (item.neto || 0);
    });

    const ivaValRaw = document.getElementById('p-iva-pct') ? document.getElementById('p-iva-pct').value : '21';
    const ivaParsed = parseFloat(ivaValRaw);
    const ivaPct = !isNaN(ivaParsed) ? ivaParsed : 21;
    const ivaMonto = subtotalNeto * (ivaPct / 100);
    const totalFinal = subtotalNeto + ivaMonto;

    const subEl = document.getElementById('p-calc-subtotal');
    if (subEl) subEl.innerText = formatARS(subtotalNeto);
    const ivaEl = document.getElementById('p-calc-iva');
    if (ivaEl) ivaEl.innerText = formatARS(ivaMonto);
    const totEl = document.getElementById('p-calc-total');
    if (totEl) totEl.innerText = formatARS(totalFinal);
}

async function submitPresupuesto(e) {
    e.preventDefault();
    saveCurrentPresupuestoItemValues();
    const p_id = document.getElementById('p-id-edit').value;

    if (!presupuestoItems.length) {
        showToast("Debes agregar al menos una actividad cotizada.", "error");
        return;
    }

    let subtotal = 0;
    for (let i = 0; i < presupuestoItems.length; i++) {
        const it = presupuestoItems[i];
        const n = parseFloat(it.neto) || 0;
        if (n < 0) {
            showToast(`El importe neto en la Actividad #${i + 1} no puede ser negativo.`, "error");
            return;
        }
        if (n === 0) {
            showToast(`La Actividad #${i + 1} debe tener un importe cotizado mayor a cero ($0.00).`, "error");
            return;
        }
        if (parseFloat(it.km) < 0 || parseFloat(it.toneladas) < 0 || parseFloat(it.horas) < 0) {
            showToast(`Las distancias, toneladas u horas en la Actividad #${i + 1} no pueden ser negativas.`, "error");
            return;
        }
        subtotal += n;
    }

    if (subtotal <= 0) {
        showToast("El monto total del presupuesto debe ser mayor a cero ($0.00).", "error");
        return;
    }

    const ivaValRawSubmit = document.getElementById('p-iva-pct') ? document.getElementById('p-iva-pct').value : '21';
    const ivaParsedSubmit = parseFloat(ivaValRawSubmit);
    const ivaPctSubmit = !isNaN(ivaParsedSubmit) ? ivaParsedSubmit : 21;

    const payload = {
        cliente: document.getElementById('p-cliente').value,
        cuit: document.getElementById('p-cuit').value,
        validez: document.getElementById('p-validez').value,
        iva_pct: ivaPctSubmit,
        modalidad_combustible: document.getElementById('p-combustible-modalidad') ? document.getElementById('p-combustible-modalidad').value : 'Con Combustible Incluido',
        observaciones: document.getElementById('p-observaciones').value,
        items: presupuestoItems
    };

    if (p_id) payload.id = p_id;

    const endpoint = p_id ? '/api/presupuestos/update' : '/api/presupuestos/add';

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-presupuesto');
            await loadPresupuestosData();
            showToast(`Presupuesto ${json.id || p_id} guardado con éxito.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar presupuesto.", "error");
    }
}

// Deprecated old toggle
function setTipoOperacion(tipo) {
    // Left for backwards compatibility if needed
}
