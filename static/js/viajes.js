/**
 * ECONCATIVO - Viajes & Operaciones Module
 */


// VIAJES & SERVICIOS OPERATIONAL LIFECYCLE
function populateViajesMesAnioSelect() {
    // Reemplazado por selector de fecha Desde y Hasta
}

let viajesFilterDebounceTimer = null;
let lastViajesQueryActive = false;

function showViajesLoader() {
    const tbody = document.getElementById('tbody-viajes');
    const counter = document.getElementById('counter-viajes');
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
                        Cargando viajes y servicios operativos...
                    </div>
                </div>
            </td>
        </tr>
    `;
}

async function loadViajesData() {
    populateViajesMesAnioSelect();
    showViajesLoader();
    try {
        const res = await fetch(`/api/sheet/VIAJES?_t=${Date.now()}`);
        const json = await res.json();
        const tbody = document.getElementById('tbody-viajes');
        const counter = document.getElementById('counter-viajes');
        
        if (json.status !== 'success' || !json.rows.length) {
            if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400">No hay registros de viajes o servicios.</td></tr>`;
            if (counter) counter.innerText = '0 registros';
            currentViajes = [];
            currentViajesData = [];
            return;
        }

        currentViajes = json.rows;
        currentViajesData = json.rows;
        applyViajesFilter();

    } catch (err) {
        console.error("Error al cargar viajes:", err);
        const tbody = document.getElementById('tbody-viajes');
        if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-rose-500 font-medium">Error al cargar viajes.</td></tr>`;
    }
}

function renderViajesTable(rows) {
    const tbody = document.getElementById('tbody-viajes');
    const counter = document.getElementById('counter-viajes');
    if (!tbody || !counter) return;

    counter.innerText = `${rows.length} registros`;

    const sortedRows = sortRecordsMostRecent(rows, ['Fecha salida', 'Fecha'], ['ID viaje', 'ID']);

    if (!sortedRows.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400">Sin viajes o servicios con los filtros aplicados.</td></tr>`;
        renderPaginationBar('viajes', 'pagination-viajes', { totalItems: 0 });
        return;
    }

    paginateAndRender('viajes', 'pagination-viajes', sortedRows, (pageRows) => {
        tbody.innerHTML = pageRows.map(r => {
        const vid = str(getRowProp(r, ['ID viaje', 'ID', 'id_viaje'])).trim();
        const actividad = str(getRowProp(r, ['Actividad', 'Tipo servicio', 'actividad'])).toLowerCase();
        const isSrv = str(vid).startsWith('SRV') || actividad.includes('servicio') || actividad.includes('maquinaria') || actividad.includes('grúa');
        
        const icon = isSrv ? '<i class="fa-solid fa-trowel-bricks text-amber mr-1"></i>' : '<i class="fa-solid fa-truck text-navy mr-1"></i>';
        const rawKmHs = str(getRowProp(r, ['Km final', 'Km recorridos', 'Km inicial', 'km_recorridos', 'km_hs'])).trim();
        
        const choferVal = str(getRowProp(r, ['Chofer', 'chofer'])).trim();
        const unidadVal = str(getRowProp(r, ['Unidad', 'unidad'])).trim();

        const estFact = str(getRowProp(r, ['Estado facturación', 'Estado facturacion', 'estado_facturacion'])).toLowerCase();
        const idIngreso = str(getRowProp(r, ['ID ingreso/factura', 'ID ingreso', 'id_ingreso_factura'])).trim();

        const isFinalizado = rawKmHs.includes('FINALIZADO') || estFact.includes('factura') || idIngreso.startsWith('ING-');
        const isPendingData = !isFinalizado && (!choferVal || choferVal === '-' || choferVal.includes('POR ASIGNAR') || !unidadVal || unidadVal === '-' || unidadVal.includes('POR ASIGNAR'));
        
        let rowBgClass = 'hover:bg-slate-50 border-slate-100';
        let pendingBadge = '';

        if (isFinalizado) {
            rowBgClass = 'bg-emerald-50/50 text-emerald-950 border-emerald-200';
            pendingBadge = `<span class="bg-emerald-600 text-white text-[9px] px-2 py-0.5 rounded font-bold ml-1.5 shadow-sm uppercase"><i class="fa-solid fa-circle-check mr-1"></i>En Facturación</span>`;
        } else if (isPendingData) {
            rowBgClass = 'bg-amber-100/90 text-amber-900 border-amber-300 font-semibold';
            pendingBadge = `<span class="bg-amber-500 text-white text-[9px] px-2 py-0.5 rounded font-bold ml-1.5 shadow-sm uppercase"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Completar datos</span>`;
        } else {
            rowBgClass = 'hover:bg-slate-50 border-slate-100';
            pendingBadge = `<span class="bg-blue-600 text-white text-[9px] px-2 py-0.5 rounded font-bold ml-1.5 shadow-sm uppercase"><i class="fa-solid fa-truck-moving mr-1"></i>Asignado</span>`;
        }

        const cleanKmHs = rawKmHs.replace(/\(FINALIZADO\)/gi, '').replace(/PENDIENTE DE DATOS/gi, '').trim();
        let kmOrHsDisplay = cleanKmHs;
        if (isFinalizado) {
            kmOrHsDisplay = cleanKmHs ? `${cleanKmHs} (FINALIZADO)` : 'FINALIZADO';
        } else if (isPendingData) {
            kmOrHsDisplay = 'PENDIENTE DE DATOS';
        } else if (!cleanKmHs || cleanKmHs === '0') {
            kmOrHsDisplay = 'ASIGNADO';
        } else if (!isNaN(cleanKmHs) && !cleanKmHs.endsWith('km') && !cleanKmHs.endsWith('hs')) {
            kmOrHsDisplay = `${cleanKmHs} km`;
        }
        const clienteDisp = getRowProp(r, ['Cliente', 'cliente']) || '-';
        const cargaDisp = getRowProp(r, ['Carga', 'carga', 'Detalle/Concepto', 'Actividad']) || '-';

        return `
            <tr class="${rowBgClass} border-b transition-all text-xs">
                <td class="px-3 py-2.5 font-bold ${isPendingData ? 'text-amber-950' : 'text-navy'} whitespace-nowrap">${icon}${vid || '-'}${pendingBadge}</td>
                <td class="px-3 py-2.5 whitespace-nowrap text-slate-600">${formatDateAR(getRowProp(r, ['Fecha salida', 'Fecha', 'fecha_salida']))}</td>
                <td class="px-3 py-2.5 font-semibold text-slate-800">${choferVal || '-'}</td>
                <td class="px-3 py-2.5 font-medium text-slate-700">${unidadVal || '-'}</td>
                <td class="px-3 py-2.5 font-medium text-slate-800">${clienteDisp}</td>
                <td class="px-3 py-2.5 text-slate-600 font-medium">${formatLocation(getRowProp(r, ['Origen', 'origen']), getRowProp(r, ['Destino', 'destino']))}</td>
                <td class="px-3 py-2.5 font-medium text-slate-700 text-[11px] max-w-xs truncate" title="${cargaDisp}">${cargaDisp}</td>
                <td class="px-3 py-2.5 font-bold whitespace-nowrap">${kmOrHsDisplay}</td>
                <td class="px-3 py-2.5 text-right whitespace-nowrap">
                    <div class="inline-flex items-center justify-end gap-1 flex-wrap">
                        ${isFinalizado ? `
                            <a href="/api/viajes/${vid}/resumen_pdf" target="_blank" class="inline-flex items-center gap-1 bg-amber-50 hover:bg-amber-100 text-amber-900 font-bold px-2 py-1 rounded text-[10px] border border-amber-300 transition-all whitespace-nowrap" title="Ver / Descargar Resumen de Facturación (Base + Extras)">
                                <i class="fa-solid fa-file-invoice-dollar text-amber-700"></i> Resumen 📑
                            </a>
                            <a href="/api/viajes/${vid}/pdf" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2 py-1 rounded text-[10px] border border-red-200 transition-all whitespace-nowrap" title="Descargar Orden de Trabajo / Hoja de Ruta PDF">
                                <i class="fa-solid fa-file-pdf"></i> Hoja Ruta 📄
                            </a>
                            <span class="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 font-bold px-2 py-1 rounded text-[10px] border border-emerald-200 whitespace-nowrap" title="Enviado a Facturación">
                                <i class="fa-solid fa-receipt"></i> En Facturación
                            </span>
                        ` : (isPendingData ? `
                            <button onclick="completarViajeData('${vid}')" class="inline-flex items-center gap-1 bg-amber hover:bg-amber-dark text-white font-bold px-2 py-1 rounded text-[10px] shadow transition-all cursor-pointer whitespace-nowrap" title="Completar Chofer, Unidad, Remito según tarea">
                                <i class="fa-solid fa-pen-to-square"></i> Completar ✍️
                            </button>
                        ` : `
                            <button onclick="completarViajeData('${vid}')" class="inline-flex items-center gap-1 bg-blue-50 hover:bg-blue-100 text-blue-800 font-bold px-1.5 py-1 rounded text-[10px] border border-blue-300 transition-all cursor-pointer whitespace-nowrap" title="Modificar Asignación, Chofer, Unidad o Ruta">
                                <i class="fa-solid fa-pen-to-square"></i> Editar
                            </button>
                            <button onclick="openModalAdelantoViaje('${vid}', '${clienteDisp.replace(/'/g, "\\'")}')" class="inline-flex items-center gap-0.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold px-1.5 py-1 rounded text-[10px] border border-emerald-300 transition-all cursor-pointer whitespace-nowrap" title="Registrar Seña / Adelanto de Dinero">
                                <i class="fa-solid fa-hand-holding-dollar text-emerald-600"></i> + Seña
                            </button>
                            <button onclick="openModalAdicionalViaje('${vid}')" class="inline-flex items-center gap-0.5 bg-amber-50 hover:bg-amber-100 text-amber-900 font-bold px-1.5 py-1 rounded text-[10px] border border-amber-300 transition-all cursor-pointer whitespace-nowrap" title="Agregar Adicional / Hora Extra al Viaje">
                                <i class="fa-solid fa-plus-circle text-amber-700"></i> + Extra
                            </button>
                            <a href="/api/viajes/${vid}/pdf" target="_blank" class="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold px-2 py-1 rounded text-[10px] border border-red-200 transition-all whitespace-nowrap" title="Descargar Orden de Trabajo / Hoja de Ruta PDF">
                                <i class="fa-solid fa-file-pdf"></i> Hoja Ruta 📄
                            </a>
                            <button onclick="finalizarViaje('${vid}')" class="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2 py-1 rounded text-[10px] shadow transition-all cursor-pointer whitespace-nowrap" title="Finalizar viaje y transferir a la Pestaña Facturación">
                                <i class="fa-solid fa-flag-checkered"></i> Finalizar 🏁
                            </button>
                        `)}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    }, 10);
}

function clearViajesDateFilter() {
    const d = document.getElementById('filter-viajes-desde');
    const h = document.getElementById('filter-viajes-hasta');
    if (d) d.value = '';
    if (h) h.value = '';
    resetTablePaginationPage('viajes');
    filterViajesTable(120, true);
}

function resetViajesFilters() {
    const s = document.getElementById('search-viajes');
    const d = document.getElementById('filter-viajes-desde');
    const h = document.getElementById('filter-viajes-hasta');
    if (s) s.value = '';
    if (d) d.value = '';
    if (h) h.value = '';
    lastViajesQueryActive = false;
    resetTablePaginationPage('viajes');
    filterViajesTable(120, true);
}

function filterViajesTable(delay = 180, isDropdown = false) {
    const rawQuery = (document.getElementById('search-viajes')?.value || '').trim();
    const isNowActive = rawQuery.length >= 3;

    if (!isDropdown && !isNowActive && !lastViajesQueryActive) {
        return;
    }

    resetTablePaginationPage('viajes');

    if (viajesFilterDebounceTimer) {
        clearTimeout(viajesFilterDebounceTimer);
    }

    showViajesLoader();
    lastViajesQueryActive = isNowActive;

    viajesFilterDebounceTimer = setTimeout(() => {
        applyViajesFilter();
    }, delay);
}

function applyViajesFilter() {
    const rawQuery = (document.getElementById('search-viajes')?.value || '').trim();
    const fQuery = rawQuery.length >= 3 ? rawQuery.toLowerCase() : '';
    const fDesde = document.getElementById('filter-viajes-desde')?.value || '';
    const fHasta = document.getElementById('filter-viajes-hasta')?.value || '';

    const filtered = (currentViajes || []).filter(r => {
        const vid = str(getRowProp(r, ['ID viaje', 'ID'])).toLowerCase();
        const chofer = str(getRowProp(r, ['Chofer'])).toLowerCase();
        const cliente = str(getRowProp(r, ['Cliente'])).toLowerCase();
        const unidad = str(getRowProp(r, ['Unidad'])).toLowerCase();
        const remito = str(getRowProp(r, ['N° remito / remesa', 'Remito', 'Comprobante'])).toLowerCase();
        const origen = str(getRowProp(r, ['Origen'])).toLowerCase();
        const destino = str(getRowProp(r, ['Destino'])).toLowerCase();
        const carga = str(getRowProp(r, ['Carga', 'Detalle/Concepto', 'Actividad'])).toLowerCase();

        const fullText = `${vid} ${chofer} ${cliente} ${unidad} ${remito} ${origen} ${destino} ${carga}`;
        if (fQuery && !fullText.includes(fQuery)) return false;

        if (fDesde || fHasta) {
            const rawDate = getRowProp(r, ['Fecha salida', 'Fecha', 'Fecha emisión']) || '';
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

    renderViajesTable(filtered);
}

let viajeChoferes = [''];
let viajeUnidades = [''];

function resetViajeAssignments() {
    viajeChoferes = [''];
    viajeUnidades = [''];
    renderViajeChoferesRows();
    renderViajeUnidadesRows();
}

function saveCurrentViajeAssignmentsFromDOM() {
    const choferEls = document.querySelectorAll('.v-chofer-select');
    if (choferEls.length > 0) {
        viajeChoferes = Array.from(choferEls).map(el => el.value);
    } else if (viajeChoferes.length === 0) {
        viajeChoferes = [''];
    }

    const unidadEls = document.querySelectorAll('.v-unidad-select');
    if (unidadEls.length > 0) {
        viajeUnidades = Array.from(unidadEls).map(el => el.value);
    } else if (viajeUnidades.length === 0) {
        viajeUnidades = [''];
    }
}

function addViajeChoferRow(val = '') {
    saveCurrentViajeAssignmentsFromDOM();
    viajeChoferes.push(val);
    renderViajeChoferesRows();
}

function removeViajeChoferRow(idx) {
    saveCurrentViajeAssignmentsFromDOM();
    if (viajeChoferes.length <= 1) {
        viajeChoferes = [''];
    } else {
        viajeChoferes.splice(idx, 1);
    }
    renderViajeChoferesRows();
}

function renderViajeChoferesRows() {
    const container = document.getElementById('v-choferes-container');
    if (!container) return;

    const emps = (masterLists.empleados && masterLists.empleados.length) ? masterLists.empleados : [];

    container.innerHTML = viajeChoferes.map((val, idx) => {
        const optionsList = [...emps];
        if (val && !optionsList.includes(val) && !val.includes('POR ASIGNAR')) {
            optionsList.push(val);
        }
        return `
        <div class="flex items-center gap-2">
            <select class="v-chofer-select w-full p-2 bg-white border border-slate-200 rounded-lg font-medium text-xs outline-none focus:ring-2 focus:ring-navy">
                <option value="">-- Seleccionar Chofer / Operador --</option>
                ${optionsList.map(e => `<option value="${e}" ${e === val ? 'selected' : ''}>${e}</option>`).join('')}
            </select>
            ${viajeChoferes.length > 1 ? `
                <button type="button" onclick="removeViajeChoferRow(${idx})" class="text-rose-500 hover:text-rose-700 font-bold px-2 py-1.5 bg-rose-50 hover:bg-rose-100 rounded-lg border border-rose-200 text-xs cursor-pointer transition-all" title="Quitar Chofer">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            ` : ''}
        </div>
        `;
    }).join('');
}

function addViajeUnidadRow(val = '') {
    saveCurrentViajeAssignmentsFromDOM();
    viajeUnidades.push(val);
    renderViajeUnidadesRows();
}

function removeViajeUnidadRow(idx) {
    saveCurrentViajeAssignmentsFromDOM();
    if (viajeUnidades.length <= 1) {
        viajeUnidades = [''];
    } else {
        viajeUnidades.splice(idx, 1);
    }
    renderViajeUnidadesRows();
}

function renderViajeUnidadesRows() {
    const container = document.getElementById('v-unidades-container');
    if (!container) return;

    const unids = masterLists.unidades || [];

    container.innerHTML = viajeUnidades.map((val, idx) => `
        <div class="flex items-center gap-2">
            <select class="v-unidad-select w-full p-2 bg-white border border-slate-200 rounded-lg font-medium text-xs outline-none focus:ring-2 focus:ring-navy">
                <option value="">-- Seleccionar Unidad / Maquinaria --</option>
                ${unids.map(u => {
                    const uVal = typeof u === 'object' && u !== null ? (u.value ?? u.patente ?? '') : u;
                    const uLabel = typeof u === 'object' && u !== null ? (u.label ?? u.text ?? uVal) : u;
                    const cleanTarget = String(val || '').trim().toUpperCase();
                    const cleanVal = String(uVal || '').trim().toUpperCase();
                    const cleanLabel = String(uLabel || '').trim().toUpperCase();
                    const isSelected = cleanVal && cleanTarget && (
                        cleanVal === cleanTarget || 
                        cleanLabel === cleanTarget || 
                        cleanTarget.startsWith(cleanVal) || 
                        cleanTarget.includes(cleanVal)
                    );
                    return `<option value="${uVal}" ${isSelected ? 'selected' : ''}>${uLabel}</option>`;
                }).join('')}
            </select>
            ${viajeUnidades.length > 1 ? `
                <button type="button" onclick="removeViajeUnidadRow(${idx})" class="text-rose-500 hover:text-rose-700 font-bold px-2 py-1.5 bg-rose-50 hover:bg-rose-100 rounded-lg border border-rose-200 text-xs cursor-pointer transition-all" title="Quitar Unidad">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            ` : ''}
        </div>
    `).join('');
}

function completarViajeData(vid) {
    try {
        const list = (typeof currentViajes !== 'undefined' && currentViajes && currentViajes.length) ? currentViajes : ((typeof currentViajesData !== 'undefined' && currentViajesData) ? currentViajesData : []);
        const target = list.find(v => str(getRowProp(v, ['ID viaje', 'ID viaje / operación', 'ID', 'id_viaje'])).trim() === str(vid).trim());
        
        const cleanVid = str(vid).trim() || (target ? str(getRowProp(target, ['ID viaje', 'ID viaje / operación', 'ID', 'id_viaje'])).trim() : 'VIA-000000');
        const isSrv = cleanVid.toUpperCase().startsWith('SRV');

        const clienteVal = target ? str(getRowProp(target, ['Cliente', 'cliente'])).trim() : '';
        const cargaVal = target ? str(getRowProp(target, ['Carga', 'carga', 'Detalle/Concepto', 'Actividad'])).replace(/\[PRESUPUESTO APROBADO [^\]]+\]/gi, '').trim() : '';

        const rawChofer = target ? str(getRowProp(target, ['Chofer', 'chofer'])).trim() : '';
        const isAlreadyAssigned = rawChofer && !rawChofer.includes('POR ASIGNAR');

        const titleEl = document.getElementById('modal-v-title');
        if (titleEl) {
            titleEl.innerHTML = `<i class="fa-solid fa-pen-to-square text-amber"></i> ${isAlreadyAssigned ? 'Modificar Asignación' : 'Asignación'}: ${isSrv ? 'Servicio de Maquinaria' : 'Viaje / Transporte'} (${cleanVid})`;
        }
        const saveBtn = document.getElementById('btn-save-viaje');
        if (saveBtn) {
            saveBtn.innerText = isAlreadyAssigned ? 'Guardar Cambios' : 'Guardar Asignación';
        }

        document.getElementById('v-id-edit').value = cleanVid;

        if (document.getElementById('v-summary-id')) document.getElementById('v-summary-id').innerText = cleanVid;
        if (document.getElementById('v-summary-tipo')) document.getElementById('v-summary-tipo').innerText = isSrv ? 'Servicio Maquinaria' : 'Transporte de Cargas';
        if (document.getElementById('v-summary-cliente')) document.getElementById('v-summary-cliente').innerText = 'Cliente: ' + (clienteVal || '-');
        if (document.getElementById('v-summary-detalle')) document.getElementById('v-summary-detalle').innerText = cargaVal || 'Detalle registrado en presupuesto';
        
        if (rawChofer && !rawChofer.includes('POR ASIGNAR')) {
            const list = rawChofer.split(/\/\/|,/).map(c => c.trim()).filter(Boolean);
            viajeChoferes = list.length ? list : [''];
        } else {
            viajeChoferes = [''];
        }
        renderViajeChoferesRows();

        const rawUnidad = target ? str(getRowProp(target, ['Unidad', 'unidad'])).trim() : '';
        if (rawUnidad && !rawUnidad.includes('POR ASIGNAR')) {
            const list = rawUnidad.split(/\/\/|,/).map(u => u.trim()).filter(Boolean);
            viajeUnidades = list.length ? list : [''];
        } else {
            viajeUnidades = [''];
        }
        renderViajeUnidadesRows();

        if (!masterLists.empleados || masterLists.empleados.length === 0 || !masterLists.unidades || masterLists.unidades.length === 0) {
            loadMasterLists().then(() => {
                renderViajeChoferesRows();
                renderViajeUnidadesRows();
            });
        }

        const fechaSal = target ? str(getRowProp(target, ['Fecha salida', 'Fecha', 'fecha_salida'])).trim() : '';
        if (document.getElementById('v-fecha-salida')) {
            document.getElementById('v-fecha-salida').value = (fechaSal && fechaSal.length >= 10) ? fechaSal.substring(0, 10) : new Date().toISOString().split('T')[0];
        }

        const remitoVal = target ? str(getRowProp(target, ['N° remito', 'Remito', 'nro_remito'])).trim() : '';
        if (document.getElementById('v-remito')) {
            document.getElementById('v-remito').value = (remitoVal && remitoVal !== 'PENDIENTE') ? remitoVal : '';
        }

        const oriVal = target ? str(getRowProp(target, ['Origen', 'origen'])).trim() : '';
        if (document.getElementById('v-origen')) {
            document.getElementById('v-origen').value = (oriVal && oriVal !== 'POR DEFINIR') ? oriVal : '';
        }

        const desVal = target ? str(getRowProp(target, ['Destino', 'destino'])).trim() : '';
        if (document.getElementById('v-destino')) {
            document.getElementById('v-destino').value = (desVal && desVal !== 'POR DEFINIR') ? desVal : '';
        }

        if (document.getElementById('v-observaciones')) {
            document.getElementById('v-observaciones').value = target ? str(getRowProp(target, ['Observaciones', 'observaciones'])).trim() : '';
        }

        openModal('modal-viaje');
    } catch (err) {
        console.error("Error en completarViajeData:", err);
        document.getElementById('v-id-edit').value = str(vid).trim();
        if (document.getElementById('v-summary-id')) document.getElementById('v-summary-id').innerText = str(vid).trim();
        openModal('modal-viaje');
    }
}

async function submitViaje(e) {
    e.preventDefault();
    const vid = document.getElementById('v-id-edit').value;

    saveCurrentViajeAssignmentsFromDOM();
    const selectedChoferes = viajeChoferes.filter(c => c && !c.includes('POR ASIGNAR'));
    const selectedUnidades = viajeUnidades.filter(u => u && !u.includes('POR ASIGNAR'));

    if (selectedChoferes.length === 0) {
        showToast("Selecciona al menos un chofer u operador válido.", "error");
        return;
    }

    if (selectedUnidades.length === 0) {
        showToast("Selecciona al menos una unidad o maquinaria válida.", "error");
        return;
    }

    const payload = {
        id: vid,
        chofer: selectedChoferes.join(', '),
        unidad: selectedUnidades.join(', '),
        origen: document.getElementById('v-origen') ? document.getElementById('v-origen').value.trim() : '',
        destino: document.getElementById('v-destino') ? document.getElementById('v-destino').value.trim() : '',
        fecha_salida: document.getElementById('v-fecha-salida').value,
        remito: document.getElementById('v-remito').value,
        observaciones: document.getElementById('v-observaciones') ? document.getElementById('v-observaciones').value : ''
    };

    try {
        const res = await fetch('/api/viajes/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-viaje');
            await loadViajesData();
            showToast(`¡Operación ${vid} actualizada correctamente!`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar la asignación.", "error");
    }
}

async function finalizarViaje(vid) {
    const confirmed = await showConfirmModal(
        "Finalizar Operación / Viaje",
        `¿Confirmas finalizar el viaje <b>${vid}</b> y transferir el servicio a la Pestaña de Facturación?`,
        {
            iconClass: "fa-solid fa-flag-checkered text-emerald-600 text-3xl",
            confirmText: "Sí, Finalizar y Facturar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/viajes/finalizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: vid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadViajesData();
            await loadFacturacionData();
            await loadDashboardData();
            showToast(`¡Operación ${vid} Finalizada! Se transfirió a la pestaña 'Facturación' (${json.ingreso_id}).`);
        } else {
            showToast("Error: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error al finalizar la operación.", "error");
    }
}

function marcarViajeFinalizado(vid) {
    return finalizarViaje(vid);
}


// VIAJE ADELANTOS & ADICIONALES JS HANDLERS
function openModalAdelantoViaje(vid, cliente = '') {
    document.getElementById('va-viaje-id').value = vid;
    if (document.getElementById('va-disp-viaje')) {
        document.getElementById('va-disp-viaje').innerText = `${vid} ${cliente ? '(' + cliente + ')' : ''}`;
    }
    document.getElementById('va-monto').value = '';
    document.getElementById('va-fecha').value = new Date().toISOString().split('T')[0];
    document.getElementById('va-comprobante').value = '';
    document.getElementById('va-observaciones').value = '';
    
    if (typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length > 0) {
        const liquidAccs = currentTesoreriaAccounts.filter(a => a.tipo !== 'Cheques');
        const liquidOptions = liquidAccs.map(a => `<option value="${a.nombre}">${a.nombre} (${a.tipo})</option>`).join('');
        const vaCuentaSelect = document.getElementById('va-cuenta-tesoreria');
        if (vaCuentaSelect) vaCuentaSelect.innerHTML = liquidOptions;
    }

    openModal('modal-adelanto');
}

async function submitAdelantoViaje(e) {
    e.preventDefault();
    const vid = document.getElementById('va-viaje-id').value;
    const vaCuenta = document.getElementById('va-cuenta-tesoreria');
    const payload = {
        viaje_id: vid,
        monto: document.getElementById('va-monto').value,
        fecha: document.getElementById('va-fecha').value,
        medio_pago: document.getElementById('va-medio-pago').value,
        cuenta_tesoreria: vaCuenta ? vaCuenta.value : '',
        comprobante: document.getElementById('va-comprobante').value,
        observaciones: document.getElementById('va-observaciones').value
    };

    try {
        const res = await fetch('/api/viajes/add_adelanto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-adelanto');
            await loadViajesData();
            await loadIngresosData();
            try { await loadChequesData(); } catch(e) {}
            await loadDashboardData();
            showToast(`Seña/Adelanto de $${payload.monto} registrado con éxito en ${vid} e Ingresos.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al registrar seña/adelanto.", "error");
    }
}

function openModalAdicionalViaje(vid) {
    document.getElementById('vad-viaje-id').value = vid;
    if (document.getElementById('vad-disp-viaje')) {
        document.getElementById('vad-disp-viaje').innerText = vid;
    }
    selectExtraPreset('combustible');
    openModal('modal-adicional');
}

function selectExtraPreset(type) {
    if (document.getElementById('vad-preset-type')) {
        document.getElementById('vad-preset-type').value = type;
    }

    const buttons = ['combustible', 'horas', 'km', 'otro'];
    buttons.forEach(b => {
        const btn = document.getElementById(`preset-btn-${b}`);
        if (btn) {
            if (b === type) {
                btn.className = "preset-btn bg-amber-500 text-white font-bold p-2 rounded-lg border border-amber-600 text-[11px] text-left flex items-center gap-1.5 transition-all shadow-sm";
            } else {
                btn.className = "preset-btn bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold p-2 rounded-lg border border-slate-200 text-[11px] text-left flex items-center gap-1.5 transition-all";
            }
        }
    });

    const calcContainer = document.getElementById('extra-calc-container');
    const lblCant = document.getElementById('lbl-calc-cant');
    const lblPrecio = document.getElementById('lbl-calc-precio');
    const inputCant = document.getElementById('vad-calc-cant');
    const inputPrecio = document.getElementById('vad-calc-precio');

    if (inputCant) inputCant.value = '';
    if (inputPrecio) inputPrecio.value = '';
    if (document.getElementById('vad-monto')) document.getElementById('vad-monto').value = '';

    if (type === 'combustible') {
        if (calcContainer) calcContainer.classList.remove('hidden');
        if (lblCant) lblCant.innerText = "Litros Consumidos";
        if (lblPrecio) lblPrecio.innerText = "Precio / Litro ($)";
        if (document.getElementById('vad-concepto')) document.getElementById('vad-concepto').value = "Consumo de combustible post-uso";
    } else if (type === 'horas') {
        if (calcContainer) calcContainer.classList.remove('hidden');
        if (lblCant) lblCant.innerText = "Horas Extras Trab.";
        if (lblPrecio) lblPrecio.innerText = "Valor por Hora ($)";
        if (document.getElementById('vad-concepto')) document.getElementById('vad-concepto').value = "Horas extra de máquina / trabajo en obra";
    } else if (type === 'km') {
        if (calcContainer) calcContainer.classList.add('hidden');
        if (document.getElementById('vad-concepto')) document.getElementById('vad-concepto').value = "Adicional por Km / Peajes";
    } else {
        if (calcContainer) calcContainer.classList.add('hidden');
        if (document.getElementById('vad-concepto')) document.getElementById('vad-concepto').value = "";
    }
}

function calcExtraMontoFromUnits() {
    const type = document.getElementById('vad-preset-type')?.value || 'combustible';
    const cant = parseFloat(document.getElementById('vad-calc-cant')?.value) || 0;
    const precio = parseFloat(document.getElementById('vad-calc-precio')?.value) || 0;
    const total = cant * precio;

    if (total > 0 && document.getElementById('vad-monto')) {
        document.getElementById('vad-monto').value = total.toFixed(2);
    }

    if (type === 'combustible' && cant > 0 && document.getElementById('vad-concepto')) {
        document.getElementById('vad-concepto').value = `Consumo de combustible post-uso (${cant} Litros${precio > 0 ? ' @ $' + precio + '/L' : ''})`;
    } else if (type === 'horas' && cant > 0 && document.getElementById('vad-concepto')) {
        document.getElementById('vad-concepto').value = `${cant} Horas extra de máquina en obra${precio > 0 ? ' @ $' + precio + '/hs' : ''}`;
    }
}

async function submitAdicionalViaje(e) {
    e.preventDefault();
    const vid = document.getElementById('vad-viaje-id').value;
    const payload = {
        viaje_id: vid,
        concepto: document.getElementById('vad-concepto').value,
        monto: document.getElementById('vad-monto').value
    };

    try {
        const res = await fetch('/api/viajes/add_adicional', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-adicional');
            await loadViajesData();
            showToast(`Adicional '${payload.concepto}' de $${payload.monto} agregado a ${vid}.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al agregar adicional.", "error");
    }
}

