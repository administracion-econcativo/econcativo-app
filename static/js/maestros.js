/**
 * ECONCATIVO - Maestros (Clientes, Unidades, Empleados, Proveedores)
 */

// Master Lists & Dropdowns
async function loadMasterLists() {
    try {
        const res = await fetch(`/api/masters?_t=${Date.now()}`);
        const json = await res.json();
        if (json.status !== 'success') return;

        masterLists = json.data || {};
        window.masterLists = masterLists;

        // Clientes
        populateSelect('p-cliente', masterLists.clientes, 'Seleccionar Cliente...');
        populateSelect('filter-p-cliente', masterLists.clientes, 'Todos los Clientes');
        populateSelect('v-cliente', masterLists.clientes, 'Seleccionar Cliente...');
        populateSelect('i-cliente', masterLists.clientes, 'Seleccionar Cliente...');
        populateSelect('select-cc-cliente', masterLists.clientes, 'Seleccionar Cliente...');
        populateSelect('pago-cc-cliente', masterLists.clientes, 'Seleccionar Cliente...');

        // Proveedores
        populateSelect('e-proveedor', masterLists.proveedores, 'Seleccionar Proveedor...');
        populateSelect('o-proveedor', masterLists.proveedores, 'Seleccionar Proveedor...');
        populateSelect('filter-ord-proveedor', masterLists.proveedores, 'Todos los Proveedores');
        populateSelect('usar-chq-proveedor', masterLists.proveedores, 'Seleccionar Proveedor...');

        // Unidades
        populateSelect('v-unidad', masterLists.unidades, 'Seleccionar Unidad / Maquinaria...');
        populateSelect('e-unidad', masterLists.unidades, 'Seleccionar Unidad (Opcional)...');
        populateSelect('o-unidad', masterLists.unidades, 'General / Taller Central', 'General');

        // Empleados y Choferes
        populateSelect('v-chofer', masterLists.empleados, 'Seleccionar Chofer / Operador...');
        populateSelect('nov-empleado', masterLists.empleados, 'Seleccionar Empleado / Chofer...');
        populateSelect('filtro-nov-empleado', masterLists.empleados, 'Todos los Empleados');
        populateSelect('filter-tab-liq-empleado', masterLists.empleados, 'Todos los Empleados');

        // Categorías / Rubros (Egresos, Órdenes de Compra, Proveedores)
        if (masterLists.categorias && masterLists.categorias.length > 0) {
            populateSelect('e-categoria', masterLists.categorias, 'Seleccionar Categoría...');
            populateSelect('filter-egresos-categoria', masterLists.categorias, 'Todos los Rubros / Categorías');
            populateSelect('o-tipo-insumo', masterLists.categorias, 'Seleccionar Tipo de Insumo / Rubro...');
            populateSelect('filter-ord-tipo', masterLists.categorias, 'Todos los Insumos / Rubros');
            populateSelect('mp-rubro', masterLists.categorias, 'Seleccione Tipo de Proveedor...');
        }

        if (typeof loadCustomEgresoCategorias === 'function') {
            loadCustomEgresoCategorias();
        }

        // Cuentas de Tesorería en todos los selects y filtros
        if (masterLists.cuentas_tesoreria && masterLists.cuentas_tesoreria.length > 0) {
            populateTreasurySelectsFromMaster(masterLists.cuentas_tesoreria);
        }

        // Años para filtros
        if (masterLists.anios && masterLists.anios.length > 0) {
            populateYearSelectsFromMaster(masterLists.anios);
        }

        if (typeof initAllSearchableSelects === 'function') {
            initAllSearchableSelects();
        }

    } catch (err) {
        console.error("Error al cargar maestros:", err);
    }
}

function populateSelect(selectId, items, placeholder, defaultVal = '') {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const currVal = sel.value;
    const defVal = (selectId === 'o-unidad') ? 'General' : defaultVal;
    sel.innerHTML = `<option value="${defVal}">${placeholder}</option>` + 
        (items || []).map(item => {
            const val = typeof item === 'object' && item !== null ? (item.value ?? item.patente ?? item.id ?? '') : item;
            const label = typeof item === 'object' && item !== null ? (item.label ?? item.text ?? val) : item;
            return `<option value="${val}">${label}</option>`;
        }).join('');
    if (currVal) {
        sel.value = currVal;
        if (!sel.value) {
            const cleanTarget = String(currVal).trim().toUpperCase();
            for (const opt of sel.options) {
                const optVal = String(opt.value || '').trim().toUpperCase();
                const optText = String(opt.text || '').trim().toUpperCase();
                if (optVal === cleanTarget || optText === cleanTarget || (optVal && cleanTarget.includes(optVal))) {
                    sel.value = opt.value;
                    break;
                }
            }
        }
    }
    if (sel._searchableSelect && typeof sel._searchableSelect.syncOptions === 'function') {
        sel._searchableSelect.syncOptions();
    }
}

function populateTreasurySelectsFromMaster(accounts) {
    if (!accounts || !accounts.length) return;
    const liquidAccs = accounts.filter(a => a.tipo !== 'Cheques');
    const bankAccs = accounts.filter(a => a.tipo === 'Banco' || a.tipo === 'Billetera');
    
    // gb-cuenta (Gastos Bancarios)
    const gbSelect = document.getElementById('gb-cuenta');
    if (gbSelect) {
        const curr = gbSelect.value;
        const opts = (bankAccs.length ? bankAccs : liquidAccs).map(a => `<option value="${a.nombre}">${a.nombre} (${a.tipo})</option>`).join('');
        gbSelect.innerHTML = opts;
        if (curr && Array.from(gbSelect.options).some(o => o.value === curr)) gbSelect.value = curr;
    }

    // trf-origen & trf-destino (Transferencias Internas)
    const trfOrig = document.getElementById('trf-origen');
    const trfDest = document.getElementById('trf-destino');
    const liquidOptsHtml = liquidAccs.map(a => `<option value="${a.nombre}">${a.nombre} (${a.tipo})</option>`).join('');
    if (trfOrig) {
        const curr = trfOrig.value;
        trfOrig.innerHTML = liquidOptsHtml;
        if (curr && Array.from(trfOrig.options).some(o => o.value === curr)) trfOrig.value = curr;
    }
    if (trfDest) {
        const curr = trfDest.value;
        trfDest.innerHTML = liquidOptsHtml;
        if (curr && Array.from(trfDest.options).some(o => o.value === curr)) trfDest.value = curr;
    }

    // Form accounts
    ['o-cuenta-tesoreria', 'pago-cuenta-origen', 'pago-vuelto-cuenta', 'ic-cuenta-destino', 'pago-cc-cuenta-tesoreria', 'va-cuenta-tesoreria', 'nov-cuenta-id', 'e-vuelto-cuenta'].forEach(sId => {
        const el = document.getElementById(sId);
        if (el) {
            const curr = el.value;
            el.innerHTML = liquidOptsHtml;
            if (curr && Array.from(el.options).some(o => o.value === curr)) el.value = curr;
        }
    });

    // chqp-banco (Banco Emisor para Cheques Propios)
    const chqpBanco = document.getElementById('chqp-banco');
    if (chqpBanco) {
        const curr = chqpBanco.value;
        const bOpts = (bankAccs.length ? bankAccs : liquidAccs).map(a => `<option value="${a.nombre}">${a.nombre}</option>`).join('');
        chqpBanco.innerHTML = bOpts;
        if (curr && Array.from(chqpBanco.options).some(o => o.value === curr)) chqpBanco.value = curr;
    }

    const eCuenta = document.getElementById('e-cuenta-tesoreria');
    if (eCuenta) {
        const curr = eCuenta.value;
        eCuenta.innerHTML = liquidOptsHtml + `<option value="Cheque (Cartera / Propio)">💳 Cheque (Cartera / Propio)</option><option value="Saldo a Favor C/C">🟢 Saldo a Favor C/C (Crédito Proveedor)</option>`;
        if (curr && Array.from(eCuenta.options).some(o => o.value === curr)) eCuenta.value = curr;
    }

    // Filters (Egresos & Ingresos)
    const fIMedio = document.getElementById('filter-i-medio');
    const fEMedio = document.getElementById('filter-egresos-medio');
    const filterAccOpts = `
        <option value="">Todos los Medios / Cuentas</option>
        ${liquidAccs.map(a => {
            let icon = '🏦';
            if (a.tipo === 'Efectivo') icon = '💵';
            else if (a.tipo === 'Billetera') icon = '📱';
            let searchVal = a.nombre.toLowerCase().replace('cta cte', '').trim();
            return `<option value="${searchVal}">${icon} ${a.nombre}</option>`;
        }).join('')}
        <option value="cheque">💳 Cheques (Propio / Cartera / E-Cheq)</option>
        <option value="saldo a favor">🟢 Saldo a Favor C/C</option>
    `;
    if (fIMedio) {
        const curr = fIMedio.value;
        fIMedio.innerHTML = filterAccOpts;
        if (curr) fIMedio.value = curr;
    }
    if (fEMedio) {
        const curr = fEMedio.value;
        fEMedio.innerHTML = filterAccOpts;
        if (curr) fEMedio.value = curr;
    }
}

function populateYearSelectsFromMaster(anios) {
    if (!anios || !anios.length) return;
    const currentYear = new Date().getFullYear();
    
    // filter-year (Dashboard)
    const fYear = document.getElementById('filter-year');
    if (fYear) {
        const curr = fYear.value;
        let html = '';
        anios.forEach(y => {
            const isSel = (!curr && y === currentYear) || (curr === String(y));
            html += `<option value="${y}" ${isSel ? 'selected' : ''}>Año ${y}</option>`;
        });
        html += `<option value="todos" ${curr === 'todos' ? 'selected' : ''}>Todos los Años (Histórico)</option>`;
        fYear.innerHTML = html;
        if (curr) fYear.value = curr;
        fYear.dataset.populated = 'true';
    }

    // resumen-prov-anio (Reporte Proveedores)
    const pYear = document.getElementById('resumen-prov-anio');
    if (pYear) {
        const curr = pYear.value;
        let html = '';
        anios.forEach(y => {
            const isSel = (!curr && y === currentYear) || (curr === String(y));
            html += `<option value="${y}" ${isSel ? 'selected' : ''}>${y}</option>`;
        });
        html += `<option value="todos" ${curr === 'todos' ? 'selected' : ''}>Todos los Años</option>`;
        pYear.innerHTML = html;
        if (curr) pYear.value = curr;
    }
}


// Argentine driver license categories (Transport, Machinery, and General)
const ARG_LICENCIAS = [
    'E.1',
    'C.1',
    'C.2',
    'C.3',
    'E.2',
    'G.1',
    'G.2',
    'LINTI Cargas Generales',
    'LINTI Peligrosas',
    'B.1',
    'B.2',
    'D.1',
    'D.2',
    'A',
    'Otra'
];

// Multi-Licence & Date Helpers for Employees
function formatDateForInput(dateVal) {
    if (!dateVal) return '';
    const s = String(dateVal).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(s)) {
        const parts = s.split('/');
        return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
    }
    return s;
}

function parseEmpleadoLicencias(row) {
    if (!row) return [{ tipo: 'E.1', vencimiento: '' }];
    const rawVence = getRowProp(row, ['Licencia vence', 'Vencimiento Licencia', 'licencia_vence']);
    const rawTipo = getRowProp(row, ['Tipo de licencia', 'Licencia', 'tipo_licencia']);

    if (rawVence && str(rawVence).trim().startsWith('[')) {
        try {
            const parsed = JSON.parse(rawVence);
            if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        } catch(e) {}
    }

    if (rawVence && (str(rawVence).includes('//') || str(rawVence).includes(','))) {
        const dates = str(rawVence).split(/\/\/|,/).map(d => d.trim());
        const types = str(rawTipo || '').split(/\/\/|,/).map(t => t.trim());
        return dates.map((d, i) => ({
            tipo: types[i] || types[0] || 'E.1',
            vencimiento: d
        }));
    }

    if (rawVence || rawTipo) {
        return [{
            tipo: rawTipo || 'E.1',
            vencimiento: rawVence || ''
        }];
    }

    return [{ tipo: 'E.1', vencimiento: '' }];
}

function formatEmpleadoLicenciasBadges(row) {
    const lics = parseEmpleadoLicencias(row);
    if (!lics || lics.length === 0 || (!lics[0].vencimiento && !lics[0].tipo)) {
        return `<span class="text-slate-400 font-normal">-</span>`;
    }

    return lics.map(l => {
        const badge = formatExpirationBadge(l.vencimiento);
        const tipoLabel = l.tipo ? `<span class="font-bold text-purple-900 bg-purple-100 px-1.5 py-0.5 rounded text-[10px] border border-purple-200">${l.tipo}</span> ` : '';
        return `<div class="inline-flex items-center gap-1 my-0.5">${tipoLabel}${badge}</div>`;
    }).join('<br/>');
}

let currentEmpleadoLicencias = [];

function resetEmpleadoLicencias() {
    currentEmpleadoLicencias = [{ tipo: 'E.1', vencimiento: '' }];
    renderEmpleadoLicenciasRows();
}

function saveCurrentEmpleadoLicenciasFromDOM() {
    currentEmpleadoLicencias.forEach((l, idx) => {
        const tipoEl = document.getElementById(`me-lic-tipo-${idx}`);
        if (tipoEl) l.tipo = tipoEl.value;
        const venceEl = document.getElementById(`me-lic-vence-${idx}`);
        if (venceEl) l.vencimiento = venceEl.value;
    });
}

function addEmpleadoLicenciaRow() {
    saveCurrentEmpleadoLicenciasFromDOM();
    currentEmpleadoLicencias.push({ tipo: 'E.1', vencimiento: '' });
    renderEmpleadoLicenciasRows();
}

function removeEmpleadoLicenciaRow(idx) {
    if (currentEmpleadoLicencias.length <= 1) {
        currentEmpleadoLicencias = [{ tipo: 'E.1', vencimiento: '' }];
        renderEmpleadoLicenciasRows();
        return;
    }
    saveCurrentEmpleadoLicenciasFromDOM();
    currentEmpleadoLicencias.splice(idx, 1);
    renderEmpleadoLicenciasRows();
}

function renderEmpleadoLicenciasRows() {
    const container = document.getElementById('me-licencias-container');
    if (!container) return;

    if (!currentEmpleadoLicencias || currentEmpleadoLicencias.length === 0) {
        currentEmpleadoLicencias = [{ tipo: 'E.1', vencimiento: '' }];
    }

    container.innerHTML = currentEmpleadoLicencias.map((l, idx) => {
        const rawTipo = (l.tipo || 'E.1').trim();
        const cleanRaw = rawTipo.toLowerCase().replace(/[\.\s\-\/]/g, '');

        const match = ARG_LICENCIAS.find(opt => {
            const cleanOpt = opt.toLowerCase().replace(/[\.\s\-\/]/g, '');
            return cleanOpt === cleanRaw || opt.toLowerCase() === rawTipo.toLowerCase();
        });

        const selectedVal = match || rawTipo;

        const optionsHtml = ARG_LICENCIAS.map(opt => {
            const isSel = opt === selectedVal ? 'selected' : '';
            return `<option value="${opt}" ${isSel}>${opt}</option>`;
        }).join('');

        const customOption = (!match && rawTipo)
            ? `<option value="${rawTipo}" selected>${rawTipo}</option>`
            : '';

        return `
        <div class="grid grid-cols-1 sm:grid-cols-5 gap-2 items-center bg-white p-2.5 rounded-xl border border-purple-100 shadow-sm">
            <div class="sm:col-span-2">
                <label class="text-[10px] text-slate-500 font-bold block mb-0.5">Tipo / Categoría de Licencia</label>
                <select id="me-lic-tipo-${idx}" class="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium text-xs outline-none focus:ring-2 focus:ring-purple-500">
                    ${optionsHtml}
                    ${customOption}
                </select>
            </div>
            <div class="sm:col-span-2">
                <label class="text-[10px] text-slate-500 font-bold block mb-0.5">Fecha de Vencimiento</label>
                <input type="date" id="me-lic-vence-${idx}" value="${formatDateForInput(l.vencimiento)}" class="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg font-medium text-xs outline-none focus:ring-2 focus:ring-purple-500">
            </div>
            <div class="flex justify-end pt-2 sm:pt-4">
                <button type="button" onclick="removeEmpleadoLicenciaRow(${idx})" class="text-rose-500 hover:text-rose-700 font-bold px-2.5 py-1.5 bg-rose-50 hover:bg-rose-100 rounded-lg border border-rose-200 text-xs flex items-center gap-1 cursor-pointer transition-all" title="Eliminar esta Licencia">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        </div>
        `;
    }).join('');
}


// MASTER ENTITY CREATION SUBMISSIONS & EDITING
function openNuevaUnidadModal() {
    const form = document.getElementById('form-unidad');
    if (form) form.reset();
    const editId = document.getElementById('mu-id-edit');
    if (editId) editId.value = '';
    const titleEl = document.getElementById('modal-mu-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-truck text-amber"></i> Registrar Nueva Unidad / Maquinaria`;
    if (document.getElementById('mu-tipo')) document.getElementById('mu-tipo').value = 'Camión';
    const counterEl = document.getElementById('mu-patente-counter');
    if (counterEl) counterEl.innerText = '0/7';
    openModal('modal-unidad');
}

function editUnidad(uid) {
    const target = currentMasterUnidades.find(r => str(getRowProp(r, ['ID unidad', 'ID'])).trim() === str(uid).trim());
    if (!target) return;

    const patVal = (getRowProp(target, ['Dominio/Patente', 'Patente']) || '').trim().toUpperCase();
    document.getElementById('modal-mu-title').innerHTML = `<i class="fa-solid fa-pen text-amber"></i> Editar Unidad / Maquinaria (${uid})`;
    document.getElementById('mu-id-edit').value = uid;
    document.getElementById('mu-tipo').value = getRowProp(target, ['Tipo']) || 'Camión';
    document.getElementById('mu-patente').value = patVal;
    const counterEl = document.getElementById('mu-patente-counter');
    if (counterEl) counterEl.innerText = `${patVal.length}/7`;
    document.getElementById('mu-marca').value = getRowProp(target, ['Marca']);
    document.getElementById('mu-modelo').value = getRowProp(target, ['Modelo']);
    document.getElementById('mu-seguro').value = getRowProp(target, ['Seguro vence', 'Vencimiento Seguro']);
    document.getElementById('mu-rto').value = getRowProp(target, ['RTO/ITV vence', 'Vencimiento ITV']);
    document.getElementById('mu-descripcion').value = getRowProp(target, ['Descripción']);

    openModal('modal-unidad');
}

async function deleteUnidad(uid) {
    const confirmed = await showConfirmModal(
        "Eliminar Unidad",
        `¿Estás seguro de eliminar la unidad <b>${uid}</b>? Esta acción no se puede deshacer.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Unidad", `Eliminando ${uid} de la base de datos...`);
    try {
        const res = await fetch('/api/maestros/unidad/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: uid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('mu-id-edit') && document.getElementById('mu-id-edit').value === uid) {
                document.getElementById('mu-id-edit').value = '';
                const form = document.getElementById('form-unidad');
                if (form) form.reset();
            }
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'unidades' ? switchMasterTab('unidades') : Promise.resolve()
            ]);
            showToast(`Unidad ${uid} eliminada correctamente.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar unidad.", "error");
    } finally {
        hideLoading();
    }
}

function editEmpleado(eid) {
    const target = currentMasterEmpleados.find(r => str(getRowProp(r, ['ID empleado', 'ID', 'id_empleado'])).trim() === str(eid).trim());
    if (!target) return;

    document.getElementById('modal-me-title').innerHTML = `<i class="fa-solid fa-user-pen text-amber"></i> Editar Ficha de Personal (${eid})`;
    document.getElementById('me-id-edit').value = eid;

    document.getElementById('me-nombre').value = getRowProp(target, ['Apellido y nombre', 'Empleado', 'Nombre', 'apellido_nombre']);
    document.getElementById('me-dni').value = String(getRowProp(target, ['DNI', 'dni']) || '').replace(/\D/g, '').slice(0, 8);
    document.getElementById('me-cuil').value = formatCuitCuil(getRowProp(target, ['CUIL', 'cuil']));
    document.getElementById('me-fecha-nacimiento').value = formatDateForInput(getRowProp(target, ['Fecha de nacimiento', 'Nacimiento', 'fecha_nacimiento']));
    document.getElementById('me-estado-civil').value = getRowProp(target, ['Estado civil', 'estado_civil']) || 'Soltero';
    document.getElementById('me-domicilio').value = getRowProp(target, ['Domicilio real actual', 'Domicilio', 'domicilio_real_actual', 'domicilio']);
    document.getElementById('me-barrio').value = getRowProp(target, ['Barrio / Zona', 'Barrio', 'barrio_zona', 'barrio']);
    document.getElementById('me-localidad').value = getRowProp(target, ['Localidad', 'localidad']);
    document.getElementById('me-telefono').value = getRowProp(target, ['Teléfono', 'Celular', 'telefono']);
    document.getElementById('me-email').value = getRowProp(target, ['Email', 'Correo', 'email']);

    document.getElementById('me-emergencia-nombre').value = getRowProp(target, ['Contacto de emergencia', 'Emergencia', 'contacto_emergencia', 'emergencia_nombre']);
    document.getElementById('me-emergencia-vinculo').value = getRowProp(target, ['Vínculo / Parentesco', 'Vínculo', 'vinculo_parentesco', 'emergencia_vinculo']);
    document.getElementById('me-emergencia-domicilio').value = getRowProp(target, ['Domicilio contacto', 'domicilio_contacto', 'emergencia_domicilio']);
    document.getElementById('me-emergencia-localidad').value = getRowProp(target, ['Localidad contacto', 'localidad_contacto', 'emergencia_localidad']);
    document.getElementById('me-emergencia-telefono').value = getRowProp(target, ['Teléfono contacto', 'Telefono contacto', 'telefono_contacto', 'Emergencia teléfono']);

    document.getElementById('me-banco').value = getRowProp(target, ['Entidad bancaria', 'Banco', 'banco']);
    document.getElementById('me-titular-cuenta').value = getRowProp(target, ['Titularidad cuenta', 'Titular', 'titular_cuenta']);
    document.getElementById('me-cbu').value = String(getRowProp(target, ['CBU', 'cbu']) || '').replace(/\D/g, '').slice(0, 22);
    document.getElementById('me-alias-cbu').value = getRowProp(target, ['Alias CBU', 'Alias', 'alias_cbu']);

    document.getElementById('me-fecha-inicio').value = formatDateForInput(getRowProp(target, ['Fecha inicio actividad', 'Fecha alta', 'Fecha de ingreso', 'fecha_inicio', 'fecha_ingreso']));
    document.getElementById('me-puesto').value = getRowProp(target, ['Cargo / Puesto', 'Puesto', 'puesto']) || 'Chofer de Camión';
    document.getElementById('me-jornada').value = getRowProp(target, ['Jornada laboral', 'Jornada', 'jornada']) || 'Completa';
    document.getElementById('me-modalidad-trabajo').value = getRowProp(target, ['Modalidad de trabajo', 'Forma de cobro', 'modalidad_trabajo']);
    document.getElementById('me-sueldo-fijo').value = getRowProp(target, ['Sueldo fijo', 'Sueldo', 'Sueldo básico', 'sueldo_fijo', 'sueldo_basico']) || '';
    document.getElementById('me-comision-pct').value = getRowProp(target, ['Porcentaje comisión (%)', 'Porcentaje comision', 'Comisión %', 'comision_pct']) || '';
    document.getElementById('me-modalidad-pago').value = getRowProp(target, ['Modalidad de pago', 'modalidad_pago']) || 'Transferencia Bancaria';
    document.getElementById('me-seguro-art').value = getRowProp(target, ['Seguro personal / ART', 'ART', 'seguro_art']);

    currentEmpleadoLicencias = parseEmpleadoLicencias(target);
    renderEmpleadoLicenciasRows();

    document.getElementById('me-talle-remera').value = getRowProp(target, ['Talle remera', 'Remera', 'talle_remera']) || 'M';
    document.getElementById('me-talle-campera').value = getRowProp(target, ['Talle campera / buzo', 'Buzo', 'talle_campera']) || 'M';
    document.getElementById('me-talle-pantalon').value = String(getRowProp(target, ['Talle pantalón', 'Pantalón', 'talle_pantalon']) || '42').replace(/\D/g, '') || '42';
    document.getElementById('me-calzado').value = String(getRowProp(target, ['N° calzado de seguridad', 'Calzado', 'calzado']) || '40').replace(/\D/g, '') || '40';

    document.getElementById('me-observaciones').value = getRowProp(target, ['Observaciones', 'observaciones']);

    const rawEst = String(getRowProp(target, ['Estado', 'estado']) || '').trim().toLowerCase();
    if (document.getElementById('me-estado')) {
        document.getElementById('me-estado').value = (rawEst === 'baja' || rawEst === 'inactivo' || rawEst === '0') ? 'Baja' : 'Activo';
    }

    openModal('modal-empleado');
}

async function toggleEstadoEmpleado(eid, nuevoEstado) {
    const accion = nuevoEstado === 'Baja' ? 'dar de baja' : 'reactivar';
    const confirmed = await showConfirmModal(
        nuevoEstado === 'Baja' ? "Dar de Baja Personal" : "Reactivar Personal",
        `¿Deseas ${accion} al empleado <b>${eid}</b>?<br><span class="text-xs text-slate-500">${nuevoEstado === 'Baja' ? 'Al darlo de baja no figurará para liquidaciones de sueldo ni como chofer activo en nuevos viajes, pero se conservará todo su legajo e historial.' : 'El empleado volverá a figurar activo en la nómina y liquidaciones.'}</span>`,
        {
            iconClass: nuevoEstado === 'Baja' ? "fa-solid fa-user-slash text-amber-500 text-3xl" : "fa-solid fa-user-check text-emerald-500 text-3xl",
            confirmText: nuevoEstado === 'Baja' ? "Sí, Dar de Baja" : "Sí, Activar",
            confirmBtnClass: nuevoEstado === 'Baja' ? "px-5 py-2.5 rounded-xl text-white font-bold bg-amber-600 hover:bg-amber-700 shadow-md transition-all cursor-pointer text-sm" : "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Actualizando Estado", `Actualizando estado de ${eid}...`);
    try {
        const res = await fetch('/api/maestros/empleado/estado', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: eid, estado: nuevoEstado })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'empleados' ? switchMasterTab('empleados') : Promise.resolve()
            ]);
            showToast(`Estado del empleado ${eid} actualizado a '${nuevoEstado}'.`);
        } else {
            showToast(json.message || "Error al actualizar estado", "error");
        }
    } catch (e) {
        showToast("Error de conexión al actualizar estado.", "error");
    } finally {
        hideLoading();
    }
}

async function deleteEmpleado(eid) {
    const confirmed = await showConfirmModal(
        "Eliminar Personal",
        `¿Estás seguro de eliminar el empleado <b>${eid}</b>? Se removerá de la nómina.<br><span class="text-xs text-slate-500">Los registros históricos de viajes y liquidaciones pasadas permanecerán archivados.</span>`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Personal", `Eliminando ${eid} de la base de datos...`);
    try {
        const res = await fetch('/api/maestros/empleado/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: eid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('me-id-edit') && document.getElementById('me-id-edit').value === eid) {
                document.getElementById('me-id-edit').value = '';
                const form = document.getElementById('form-empleado');
                if (form) form.reset();
            }
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'empleados' ? switchMasterTab('empleados') : Promise.resolve()
            ]);
            showToast(`Personal ${eid} eliminado correctamente.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar personal.", "error");
    } finally {
        hideLoading();
    }
}

function onClienteSelectChange(clientName, cuitInputId = 'p-cuit') {
    const targetInput = document.getElementById(cuitInputId);
    if (!targetInput) return;

    const cleanName = str(clientName).trim();
    if (!cleanName || !masterLists || !masterLists.clientes_dict) {
        targetInput.value = '';
        return;
    }

    let clientData = masterLists.clientes_dict[cleanName];
    if (!clientData) {
        const lowerName = cleanName.toLowerCase();
        const foundKey = Object.keys(masterLists.clientes_dict).find(k => k.toLowerCase() === lowerName);
        if (foundKey) {
            clientData = masterLists.clientes_dict[foundKey];
        }
    }

    if (clientData && clientData.cuit) {
        targetInput.value = clientData.cuit;
    } else {
        targetInput.value = '';
    }
}

function clearClienteErrors() {
    const errorBox = document.getElementById('mc-error-box');
    if (errorBox) errorBox.classList.add('hidden');
    
    ['mc-nombre', 'mc-cuit', 'mc-email'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.classList.remove('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
            input.classList.add('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
        }
    });
}

function showClienteFieldError(inputId, message) {
    const input = document.getElementById(inputId);
    const errorBox = document.getElementById('mc-error-box');
    const errorMsg = document.getElementById('mc-error-msg');

    if (errorBox && errorMsg) {
        errorMsg.textContent = message;
        errorBox.classList.remove('hidden');
    }

    if (input) {
        input.classList.remove('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
        input.classList.add('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
        input.focus();
    }
}

// Resetear estilos de error en tiempo real al tipear
document.addEventListener('DOMContentLoaded', () => {
    ['mc-nombre', 'mc-cuit', 'mc-email'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                el.classList.remove('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
                el.classList.add('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
                const errorBox = document.getElementById('mc-error-box');
                if (errorBox) errorBox.classList.add('hidden');
            });
        }
    });

    ['mp-razon', 'mp-rubro', 'mp-cuit'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            ['input', 'change'].forEach(evt => {
                el.addEventListener(evt, () => {
                    el.classList.remove('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
                    el.classList.add('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
                    const errorBox = document.getElementById('mp-error-box');
                    if (errorBox) errorBox.classList.add('hidden');
                });
            });
        }
    });
});

function openNuevoClienteModal() {
    if (document.getElementById('form-cliente')) document.getElementById('form-cliente').reset();
    if (document.getElementById('mc-id')) document.getElementById('mc-id').value = '';
    clearClienteErrors();
    const titleEl = document.getElementById('modal-cliente-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-user-plus text-amber"></i> Registrar Nuevo Cliente`;
    openModal('modal-cliente');
}

async function submitCliente(e) {
    e.preventDefault();
    clearClienteErrors();

    const cid = document.getElementById('mc-id')?.value || '';
    const nombre = (document.getElementById('mc-nombre')?.value || '').trim();
    const cuit = (document.getElementById('mc-cuit')?.value || '').trim();
    const email = (document.getElementById('mc-email')?.value || '').trim();

    if (!nombre) {
        showClienteFieldError('mc-nombre', 'La Razón Social o Nombre Completo es obligatorio.');
        return;
    }

    if (!cuit) {
        showClienteFieldError('mc-cuit', 'El CUIT / CUIL es obligatorio.');
        return;
    }

    const cleanCuitDigits = cuit.replace(/\D/g, '');
    if (cleanCuitDigits.length !== 11) {
        showClienteFieldError('mc-cuit', 'El CUIT / CUIL debe contener exactamente 11 dígitos numéricos.');
        return;
    }

    // Validación preventiva en cliente si masterLists.clientes_dict está cargado
    if (window.masterLists && window.masterLists.clientes_dict) {
        const cleanCuitDigits = cuit.replace(/\D/g, '');
        const cleanEmail = email.toLowerCase();
        const cleanNombre = nombre.toLowerCase();

        for (const [existingName, info] of Object.entries(window.masterLists.clientes_dict)) {
            const isSelf = cid && info.id && String(info.id).trim() === String(cid).trim();
            if (isSelf) continue;

            // Validar CUIT duplicado
            if (cuit && info.cuit) {
                const existDigits = String(info.cuit).replace(/\D/g, '');
                const exactMatch = cuit.toLowerCase() === String(info.cuit).trim().toLowerCase();
                const digitsMatch = cleanCuitDigits.length >= 8 && existDigits.length >= 8 && cleanCuitDigits === existDigits;
                if (exactMatch || digitsMatch) {
                    const msg = `Ya existe un cliente registrado con el CUIT/CUIL '${cuit}' (${existingName}).`;
                    showClienteFieldError('mc-cuit', msg);
                    return;
                }
            }

            // Validar Email duplicado
            if (email && info.email) {
                if (cleanEmail === String(info.email).trim().toLowerCase()) {
                    const msg = `Ya existe un cliente registrado con el correo electrónico '${email}' (${existingName}).`;
                    showClienteFieldError('mc-email', msg);
                    return;
                }
            }

            // Validar Nombre duplicado
            if (cleanNombre && existingName.toLowerCase() === cleanNombre) {
                const msg = `Ya existe un cliente registrado con el nombre '${nombre}'.`;
                showClienteFieldError('mc-nombre', msg);
                return;
            }
        }
    }

    const payload = {
        id: cid,
        nombre: nombre,
        cuit: formatCuitCuil(cleanCuitDigits),
        tipo: document.getElementById('mc-tipo')?.value || 'Empresa',
        condicion_iva: document.getElementById('mc-iva')?.value || 'Responsable Inscripto',
        telefono: document.getElementById('mc-telefono')?.value || '',
        email: email,
        domicilio: document.getElementById('mc-domicilio')?.value || ''
    };

    const url = cid ? '/api/maestros/cliente/update' : '/api/maestros/cliente/add';
    const btnSave = document.getElementById('btn-save-cliente');
    const originalBtnText = btnSave ? btnSave.innerHTML : 'Guardar Cliente';

    try {
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> Guardando...`;
        }

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();

        if (json.status === 'success') {
            closeModal('modal-cliente');
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'clientes' ? switchMasterTab('clientes') : Promise.resolve()
            ]);
            
            const pClientSel = document.getElementById('p-cliente');
            if (pClientSel && json.nombre) {
                pClientSel.value = json.nombre;
                onClienteSelectChange(json.nombre, 'p-cuit');
            }
            const iClientSel = document.getElementById('i-cliente');
            if (iClientSel && json.nombre && !iClientSel.disabled) {
                iClientSel.value = json.nombre;
            }

            showToast(`Cliente '${json.nombre || payload.nombre}' ${cid ? 'actualizado' : 'registrado'} con éxito.`);
        } else {
            const field = json.field;
            const message = json.message || "Error al procesar cliente.";
            if (field === 'cuit') {
                showClienteFieldError('mc-cuit', message);
            } else if (field === 'email') {
                showClienteFieldError('mc-email', message);
            } else if (field === 'nombre') {
                showClienteFieldError('mc-nombre', message);
            } else {
                const errorBox = document.getElementById('mc-error-box');
                const errorMsg = document.getElementById('mc-error-msg');
                if (errorBox && errorMsg) {
                    errorMsg.textContent = message;
                    errorBox.classList.remove('hidden');
                }
            }
        }
    } catch (err) {
        showToast("Error de conexión al guardar cliente.", "error");
    } finally {
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.innerHTML = originalBtnText;
        }
    }
}

async function editCliente(cid) {
    clearClienteErrors();
    let clientList = currentMasterClientes || [];
    if (!clientList || !clientList.length) {
        try {
            const res = await fetch(`/api/sheet/CLIENTES?_t=${Date.now()}`);
            const json = await res.json();
            if (json.status === 'success' && json.rows) {
                clientList = json.rows;
                currentMasterClientes = json.rows;
            }
        } catch (e) {
            console.error("Error al obtener lista de clientes:", e);
        }
    }

    const item = clientList.find(c => {
        const idVal = getRowProp(c, ['ID cliente', 'ID', 'ID Cliente']);
        return String(idVal).trim() === String(cid).trim();
    });

    if (!item) {
        showToast("No se encontró el cliente a editar.", "error");
        return;
    }

    if (document.getElementById('mc-id')) document.getElementById('mc-id').value = cid;
    if (document.getElementById('mc-nombre')) document.getElementById('mc-nombre').value = getRowProp(item, ['Razón social / Nombre', 'Razón Social / Nombre', 'Razón social', 'Razón Social', 'Nombre']) || '';
    if (document.getElementById('mc-cuit')) document.getElementById('mc-cuit').value = getRowProp(item, ['CUIT/CUIL', 'CUIT / CUIL', 'CUIT', 'CUIL']) || '';
    if (document.getElementById('mc-tipo')) document.getElementById('mc-tipo').value = getRowProp(item, ['Tipo de cliente', 'Tipo']) || 'Empresa';
    if (document.getElementById('mc-iva')) document.getElementById('mc-iva').value = getRowProp(item, ['Condición IVA', 'Condición IVA / Estado', 'IVA']) || 'Responsable Inscripto';
    if (document.getElementById('mc-telefono')) document.getElementById('mc-telefono').value = getRowProp(item, ['Teléfono', 'Telefono', 'Celular']) || '';
    if (document.getElementById('mc-email')) document.getElementById('mc-email').value = getRowProp(item, ['Correo', 'Email', 'Correo electrónico']) || '';
    if (document.getElementById('mc-domicilio')) document.getElementById('mc-domicilio').value = getRowProp(item, ['Domicilio']) || '';

    const titleEl = document.getElementById('modal-cliente-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-pen-to-square text-amber"></i> Editar Cliente ${cid}`;

    openModal('modal-cliente');
}

async function deleteCliente(cid) {
    const confirmed = await showConfirmModal(
        "Eliminar Cliente",
        `¿Estás seguro de eliminar el cliente <b>${cid}</b>? Esta acción no se puede deshacer.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Cliente", `Eliminando ${cid} de la base de datos...`);
    try {
        const res = await fetch('/api/maestros/cliente/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('mc-id') && document.getElementById('mc-id').value === cid) {
                document.getElementById('mc-id').value = '';
                const form = document.getElementById('form-cliente');
                if (form) form.reset();
            }
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'clientes' ? switchMasterTab('clientes') : Promise.resolve()
            ]);
            showToast(`Cliente ${cid} eliminado.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar cliente.", "error");
    } finally {
        hideLoading();
    }
}

async function submitUnidad(e) {
    e.preventDefault();
    const u_id = document.getElementById('mu-id-edit').value;
    const patenteEl = document.getElementById('mu-patente');
    const cleanPatente = (patenteEl ? patenteEl.value : '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');

    if (!cleanPatente) {
        showToast("El dominio / patente es obligatorio.", "warning");
        if (patenteEl) patenteEl.focus();
        return;
    }

    if (cleanPatente.length > 7) {
        showToast("La patente no puede tener más de 7 caracteres (máximo admitido en Argentina).", "warning");
        if (patenteEl) patenteEl.focus();
        return;
    }

    const payload = {
        tipo: document.getElementById('mu-tipo').value,
        patente: cleanPatente,
        marca: document.getElementById('mu-marca').value,
        modelo: document.getElementById('mu-modelo').value,
        seguro_vence: document.getElementById('mu-seguro').value,
        rto_vence: document.getElementById('mu-rto').value,
        descripcion: document.getElementById('mu-descripcion').value
    };

    const endpoint = u_id ? '/api/maestros/unidad/update' : '/api/maestros/unidad/add';
    if (u_id) payload.id = u_id;

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-unidad');
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'unidades' ? switchMasterTab('unidades') : Promise.resolve()
            ]);
            const modalAsignar = document.getElementById('modal-asignar-viaje');
            if (modalAsignar && !modalAsignar.classList.contains('hidden')) {
                if (typeof renderViajeUnidadesRows === 'function') {
                    renderViajeUnidadesRows();
                }
            }
            showToast(`Unidad '${json.patente || u_id}' guardada correctamente.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar unidad.", "error");
    }
}

function openNuevoEmpleadoModal() {
    const form = document.getElementById('form-empleado');
    if (form) form.reset();
    const editId = document.getElementById('me-id-edit');
    if (editId) editId.value = '';

    const titleEl = document.getElementById('modal-me-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-id-card text-amber"></i> Registrar Ficha de Personal`;

    if (document.getElementById('me-puesto')) document.getElementById('me-puesto').value = 'Chofer de Camión';
    if (document.getElementById('me-estado')) document.getElementById('me-estado').value = 'Activo';
    if (document.getElementById('me-jornada')) document.getElementById('me-jornada').value = 'Completa';
    if (document.getElementById('me-modalidad-pago')) document.getElementById('me-modalidad-pago').value = 'Transferencia Bancaria';
    if (document.getElementById('me-talle-remera')) document.getElementById('me-talle-remera').value = 'M';
    if (document.getElementById('me-talle-campera')) document.getElementById('me-talle-campera').value = 'M';
    if (document.getElementById('me-talle-pantalon')) document.getElementById('me-talle-pantalon').value = '42';
    if (document.getElementById('me-calzado')) document.getElementById('me-calzado').value = '40';

    resetEmpleadoLicencias();
    openModal('modal-empleado');
}

async function submitEmpleado(e) {
    e.preventDefault();
    const e_id = document.getElementById('me-id-edit').value;
    saveCurrentEmpleadoLicenciasFromDOM();

    // Validar DNI numérico obligatorio (7 a 8 dígitos)
    const rawDni = (document.getElementById('me-dni')?.value || '').trim();
    const cleanDni = rawDni.replace(/\D/g, '');
    if (!cleanDni || cleanDni.length < 7 || cleanDni.length > 8) {
        showToast("El DNI debe contener entre 7 y 8 dígitos numéricos (sin puntos ni letras).", "error");
        document.getElementById('me-dni')?.focus();
        return;
    }

    // Validar CBU numérico de exactamente 22 dígitos (opcional si está vacío)
    const rawCbu = (document.getElementById('me-cbu')?.value || '').trim();
    const cleanCbu = rawCbu.replace(/\D/g, '');
    if (cleanCbu && cleanCbu.length !== 22) {
        showToast("El CBU debe contener exactamente 22 dígitos numéricos.", "error");
        document.getElementById('me-cbu')?.focus();
        return;
    }

    // Validar CUIL numérico de exactamente 11 dígitos (opcional si está vacío)
    const rawCuil = (document.getElementById('me-cuil')?.value || '').trim();
    const cleanCuil = rawCuil.replace(/\D/g, '');
    if (cleanCuil && cleanCuil.length !== 11) {
        showToast("El CUIL debe contener exactamente 11 dígitos numéricos.", "error");
        document.getElementById('me-cuil')?.focus();
        return;
    }

    // Validar Porcentaje de Comisión (máx. 100%, mín. 0%)
    const comisionEl = document.getElementById('me-comision-pct');
    const comisionRaw = (comisionEl ? comisionEl.value : '').trim();
    let comisionVal = comisionRaw !== '' ? parseFloat(comisionRaw) : 0;
    if (isNaN(comisionVal)) comisionVal = 0;

    if (comisionVal < 0 || comisionVal > 100) {
        showToast("El porcentaje de comisión debe estar entre 0% y 100%.", "warning");
        if (comisionEl) {
            comisionEl.focus();
            if (comisionVal < 0) comisionEl.value = 0;
            if (comisionVal > 100) comisionEl.value = 100;
        }
        return;
    }

    const payload = {
        nombre: document.getElementById('me-nombre').value,
        dni: cleanDni,
        cuil: cleanCuil ? formatCuitCuil(cleanCuil) : '',
        fecha_nacimiento: document.getElementById('me-fecha-nacimiento').value,
        estado_civil: document.getElementById('me-estado-civil').value,
        domicilio: document.getElementById('me-domicilio').value,
        barrio: document.getElementById('me-barrio').value,
        localidad: document.getElementById('me-localidad').value,
        telefono: document.getElementById('me-telefono').value,
        email: document.getElementById('me-email').value,

        emergencia_nombre: document.getElementById('me-emergencia-nombre').value,
        emergencia_vinculo: document.getElementById('me-emergencia-vinculo').value,
        emergencia_domicilio: document.getElementById('me-emergencia-domicilio').value,
        emergencia_localidad: document.getElementById('me-emergencia-localidad').value,
        emergencia_telefono: document.getElementById('me-emergencia-telefono').value,

        banco: document.getElementById('me-banco').value,
        titular_cuenta: document.getElementById('me-titular-cuenta').value,
        cbu: cleanCbu,
        alias_cbu: (document.getElementById('me-alias-cbu')?.value || '').trim(),

        fecha_inicio: document.getElementById('me-fecha-inicio').value,
        puesto: document.getElementById('me-puesto').value,
        estado: document.getElementById('me-estado')?.value || 'Activo',
        jornada: document.getElementById('me-jornada').value,
        modalidad_trabajo: document.getElementById('me-modalidad-trabajo').value,
        sueldo_fijo: document.getElementById('me-sueldo-fijo').value,
        comision_pct: Math.min(100, Math.max(0, comisionVal)),
        modalidad_pago: document.getElementById('me-modalidad-pago').value,
        seguro_art: document.getElementById('me-seguro-art').value,

        licencias: currentEmpleadoLicencias,
        tipo_licencia: currentEmpleadoLicencias.map(l => l.tipo).filter(Boolean).join(', '),
        licencia_vence: currentEmpleadoLicencias.length > 1 ? JSON.stringify(currentEmpleadoLicencias) : (currentEmpleadoLicencias[0]?.vencimiento || ''),

        talle_remera: document.getElementById('me-talle-remera')?.value || 'M',
        talle_campera: document.getElementById('me-talle-campera')?.value || 'M',
        talle_pantalon: (document.getElementById('me-talle-pantalon')?.value || '42').replace(/\D/g, '') || '42',
        calzado: (document.getElementById('me-calzado')?.value || '40').replace(/\D/g, '') || '40',

        observaciones: document.getElementById('me-observaciones').value
    };

    const endpoint = e_id ? '/api/maestros/empleado/update' : '/api/maestros/empleado/add';
    if (e_id) payload.id = e_id;

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-empleado');
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'empleados' ? switchMasterTab('empleados') : Promise.resolve()
            ]);
            const modalAsignar = document.getElementById('modal-asignar-viaje');
            if (modalAsignar && !modalAsignar.classList.contains('hidden')) {
                if (typeof renderViajeChoferesRows === 'function') {
                    renderViajeChoferesRows();
                }
            }
            showToast(`Ficha de Personal de '${json.nombre || e_id}' guardada con éxito.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al guardar la ficha de personal.", "error");
    }
}

function clearProveedorErrors() {
    const errorBox = document.getElementById('mp-error-box');
    if (errorBox) errorBox.classList.add('hidden');
    
    ['mp-razon', 'mp-rubro', 'mp-cuit', 'mp-comercial', 'mp-cbu', 'mp-telefono', 'mp-correo'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.classList.remove('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
            input.classList.add('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
        }
    });
}

function showProveedorFieldError(inputId, message) {
    const input = document.getElementById(inputId);
    const errorBox = document.getElementById('mp-error-box');
    const errorMsg = document.getElementById('mp-error-msg');

    if (errorBox && errorMsg) {
        errorMsg.textContent = message;
        errorBox.classList.remove('hidden');
    }

    if (input) {
        input.classList.remove('border-slate-200', 'bg-slate-50', 'focus:ring-navy');
        input.classList.add('border-rose-500', 'bg-rose-50/40', 'focus:ring-rose-500');
        input.focus();
    }
}

async function submitProveedor(e) {
    e.preventDefault();
    clearProveedorErrors();

    const pid = document.getElementById('mp-id')?.value || '';
    const razonSocial = (document.getElementById('mp-razon')?.value || '').trim();
    const rubro = (document.getElementById('mp-rubro')?.value || '').trim();
    const rawProvCuit = (document.getElementById('mp-cuit')?.value || '').trim();
    const cleanProvCuit = rawProvCuit.replace(/\D/g, '');

    if (!razonSocial) {
        showProveedorFieldError('mp-razon', 'La Razón Social del proveedor es obligatoria.');
        return;
    }

    if (!rubro) {
        showProveedorFieldError('mp-rubro', 'Debe seleccionar el Tipo de Proveedor / Rubro.');
        return;
    }

    if (!cleanProvCuit) {
        showProveedorFieldError('mp-cuit', 'El CUIT / CUIL del proveedor es obligatorio (11 dígitos).');
        return;
    }

    if (cleanProvCuit.length !== 11) {
        showProveedorFieldError('mp-cuit', 'El CUIT / CUIL debe contener exactamente 11 dígitos numéricos.');
        return;
    }

    // Validar CUIT duplicado en proveedores existentes
    let provList = currentMasterProveedores || [];
    if ((!provList || !provList.length) && window.masterLists && window.masterLists.proveedores_dict) {
        provList = Object.entries(window.masterLists.proveedores_dict).map(([name, data]) => ({
            'ID proveedor': data.id,
            'Razón social': name,
            'CUIT': data.cuit
        }));
    }

    if (provList && provList.length) {
        for (const p of provList) {
            const pId = getRowProp(p, ['ID proveedor', 'ID', 'ID Proveedor', 'id_proveedor']) || p.id;
            const isSelf = pid && pId && String(pId).trim() === String(pid).trim();
            if (isSelf) continue;

            const existCuit = getRowProp(p, ['CUIT', 'CUIT / CUIL', 'CUIT/CUIL', 'cuit']) || p.cuit;
            if (existCuit) {
                const existDigits = String(existCuit).replace(/\D/g, '');
                if (existDigits.length === 11 && existDigits === cleanProvCuit) {
                    const existName = getRowProp(p, ['Razón social / Nombre', 'Razón Social / Nombre', 'Razón social', 'Razón Social', 'Nombre', 'razon_social']) || p.razon_social || 'Proveedor Existente';
                    showProveedorFieldError('mp-cuit', `Ya existe un proveedor registrado con el CUIT/CUIL '${formatCuitCuil(cleanProvCuit)}' (${existName}).`);
                    return;
                }
            }
        }
    }

    const payload = {
        id: pid,
        razon_social: razonSocial,
        nombre_comercial: (document.getElementById('mp-comercial')?.value || '').trim(),
        rubro: rubro,
        cuit: formatCuitCuil(cleanProvCuit),
        cbu_alias: (document.getElementById('mp-cbu')?.value || '').trim(),
        telefono: (document.getElementById('mp-telefono')?.value || '').trim(),
        correo: (document.getElementById('mp-correo')?.value || '').trim()
    };

    const url = pid ? '/api/maestros/proveedor/update' : '/api/maestros/proveedor/add';
    const btnSave = document.getElementById('btn-save-proveedor');
    const originalBtnText = btnSave ? btnSave.innerHTML : 'Guardar Proveedor';

    try {
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> Guardando...`;
        }

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-proveedor');
            const provName = json.nombre || payload.razon_social || payload.nombre_comercial;
            if (provName) {
                const oProv = document.getElementById('o-proveedor');
                if (oProv) oProv.value = provName;
                const eProv = document.getElementById('e-proveedor');
                if (eProv && !eProv.value) eProv.value = provName;
            }
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'proveedores' ? switchMasterTab('proveedores') : Promise.resolve()
            ]);
            showToast(`Proveedor '${provName}' guardado con éxito.`);
        } else {
            const field = json.field;
            const message = json.message || "Error al guardar proveedor.";
            if (field === 'cuit' || (message && message.toLowerCase().includes('cuit'))) {
                showProveedorFieldError('mp-cuit', message);
            } else if (field === 'rubro' || (message && message.toLowerCase().includes('rubro'))) {
                showProveedorFieldError('mp-rubro', message);
            } else if (field === 'razon_social' || field === 'razon' || (message && message.toLowerCase().includes('razón social'))) {
                showProveedorFieldError('mp-razon', message);
            } else {
                const errorBox = document.getElementById('mp-error-box');
                const errorMsg = document.getElementById('mp-error-msg');
                if (errorBox && errorMsg) {
                    errorMsg.textContent = message;
                    errorBox.classList.remove('hidden');
                } else {
                    showToast(message, "error");
                }
            }
        }
    } catch (err) {
        const errorBox = document.getElementById('mp-error-box');
        const errorMsg = document.getElementById('mp-error-msg');
        if (errorBox && errorMsg) {
            errorMsg.textContent = "Error de conexión al guardar proveedor.";
            errorBox.classList.remove('hidden');
        } else {
            showToast("Error al guardar proveedor.", "error");
        }
    } finally {
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.innerHTML = originalBtnText;
        }
    }
}

function openNuevoProveedorModal() {
    if (document.getElementById('form-proveedor')) document.getElementById('form-proveedor').reset();
    if (document.getElementById('mp-id')) document.getElementById('mp-id').value = '';
    if (document.getElementById('mp-rubro')) document.getElementById('mp-rubro').value = '';
    clearProveedorErrors();
    const titleEl = document.getElementById('modal-prov-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-store text-amber"></i> Registrar Proveedor`;
    openModal('modal-proveedor');
}

async function editProveedor(pid) {
    clearProveedorErrors();
    let provList = currentMasterProveedores || [];
    if (!provList || !provList.length) {
        try {
            const res = await fetch(`/api/sheet/PROVEEDORES?_t=${Date.now()}`);
            const json = await res.json();
            if (json.status === 'success' && json.rows) {
                provList = json.rows;
                currentMasterProveedores = json.rows;
            }
        } catch (e) {
            console.error("Error al obtener lista de proveedores:", e);
        }
    }

    const item = provList.find(p => {
        const idVal = getRowProp(p, ['ID proveedor', 'ID', 'ID Proveedor']);
        return String(idVal).trim() === String(pid).trim();
    });

    if (!item) {
        showToast("No se encontró el proveedor a editar.", "error");
        return;
    }

    if (document.getElementById('mp-id')) document.getElementById('mp-id').value = pid;
    if (document.getElementById('mp-razon')) document.getElementById('mp-razon').value = getRowProp(item, ['Razón social / Nombre', 'Razón Social / Nombre', 'Razón social', 'Razón Social', 'Nombre']) || '';
    if (document.getElementById('mp-comercial')) document.getElementById('mp-comercial').value = getRowProp(item, ['Nombre comercial', 'Nombre Comercial']) || '';
    if (document.getElementById('mp-rubro')) document.getElementById('mp-rubro').value = getRowProp(item, ['Rubro']) || '';
    if (document.getElementById('mp-cuit')) document.getElementById('mp-cuit').value = formatCuitCuil(getRowProp(item, ['CUIT', 'CUIT / CUIL', 'CUIT/CUIL'])) || '';
    if (document.getElementById('mp-cbu')) document.getElementById('mp-cbu').value = getRowProp(item, ['CBU / ALIAS', 'CBU/ALIAS', 'CBU', 'ALIAS']) || '';
    if (document.getElementById('mp-telefono')) document.getElementById('mp-telefono').value = getRowProp(item, ['Teléfono', 'Telefono', 'Celular']) || '';
    if (document.getElementById('mp-correo')) document.getElementById('mp-correo').value = getRowProp(item, ['Correo', 'Email', 'Correo electrónico']) || '';

    const titleEl = document.getElementById('modal-prov-title');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-pen-to-square text-amber"></i> Editar Proveedor ${pid}`;

    openModal('modal-proveedor');
}

async function deleteProveedor(pid) {
    const confirmed = await showConfirmModal(
        "Eliminar Proveedor",
        `¿Estás seguro de eliminar el proveedor <b>${pid}</b>? Esta acción no se puede deshacer.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Proveedor", `Eliminando ${pid} de la base de datos...`);
    try {
        const res = await fetch('/api/maestros/proveedor/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: pid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (document.getElementById('mp-id') && document.getElementById('mp-id').value === pid) {
                document.getElementById('mp-id').value = '';
                const form = document.getElementById('form-proveedor');
                if (form) form.reset();
            }
            await Promise.all([
                loadMasterLists(),
                currentMasterTab === 'proveedores' ? switchMasterTab('proveedores') : Promise.resolve()
            ]);
            showToast(`Proveedor ${pid} eliminado.`);
        } else {
            showToast("Error: " + json.message, "error");
        }
    } catch (err) {
        showToast("Error al eliminar proveedor.", "error");
    } finally {
        hideLoading();
    }
}

// Master Tabs Switcher
async function switchMasterTab(masterName) {
    if (masterName === 'usuarios' && window.CURRENT_USER_ROLE !== 'Administrador') {
        alert("Acceso denegado: La administración de cuentas y usuarios es exclusiva para el rol Administrador.");
        return switchMasterTab('clientes');
    }

    currentMasterTab = masterName;
    resetTablePaginationPage('maestros');
    document.querySelectorAll('.subnav-btn').forEach(btn => {
        btn.classList.remove('bg-navy', 'text-white');
        btn.classList.add('bg-slate-100', 'text-slate-600');
    });

    const activeBtn = document.getElementById(`subnav-${masterName}`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-100', 'text-slate-600');
        activeBtn.classList.add('bg-navy', 'text-white');
    }

    const container = document.getElementById('master-add-btn-container');
    if (container) {
        if (masterName === 'clientes') container.innerHTML = `<button onclick="openNuevoClienteModal()" class="bg-amber hover:bg-amber-dark text-white font-bold px-4 py-2 rounded-xl shadow text-xs flex items-center gap-2 cursor-pointer"><i class="fa-solid fa-user-plus"></i> + Registrar Cliente</button>`;
        if (masterName === 'unidades') container.innerHTML = `<button onclick="openNuevaUnidadModal()" class="bg-amber hover:bg-amber-dark text-white font-bold px-4 py-2 rounded-xl shadow text-xs flex items-center gap-2 cursor-pointer"><i class="fa-solid fa-truck"></i> + Registrar Unidad / Máquina</button>`;
        if (masterName === 'empleados') container.innerHTML = `<button onclick="openNuevoEmpleadoModal()" class="bg-amber hover:bg-amber-dark text-white font-bold px-4 py-2 rounded-xl shadow text-xs flex items-center gap-2 cursor-pointer"><i class="fa-solid fa-id-card"></i> + Registrar Personal / Chofer</button>`;
        if (masterName === 'proveedores') container.innerHTML = `<button onclick="openNuevoProveedorModal()" class="bg-amber hover:bg-amber-dark text-white font-bold px-4 py-2 rounded-xl shadow text-xs flex items-center gap-2 cursor-pointer"><i class="fa-solid fa-store"></i> + Registrar Proveedor</button>`;
        if (masterName === 'usuarios') container.innerHTML = `<button onclick="openNuevoUsuarioModal()" class="bg-amber hover:bg-amber-dark text-white font-bold px-4 py-2 rounded-xl shadow text-xs flex items-center gap-2 cursor-pointer"><i class="fa-solid fa-user-plus"></i> + Registrar Nuevo Usuario</button>`;
    }

    // Configuración contextual por pestaña (Placeholder y loader)
    const tabConfigs = {
        clientes: {
            placeholder: 'Buscar por cliente, CUIT, teléfono, email, ID...',
            label: 'clientes',
            loading: 'Cargando clientes...'
        },
        unidades: {
            placeholder: 'Buscar por patente/dominio, modelo, marca, tipo, ID...',
            label: 'unidades / máquinas',
            loading: 'Cargando unidades y maquinarias...'
        },
        empleados: {
            placeholder: 'Buscar por chofer/personal, cargo, teléfono, ID...',
            label: 'personal / choferes',
            loading: 'Cargando personal y choferes...'
        },
        proveedores: {
            placeholder: 'Buscar por proveedor, CUIT, rubro, contacto, ID...',
            label: 'proveedores',
            loading: 'Cargando proveedores...'
        },
        usuarios: {
            placeholder: 'Buscar por usuario, nombre completo, rol, estado...',
            label: 'usuarios del sistema',
            loading: 'Cargando usuarios del sistema...'
        }
    };

    const cfg = tabConfigs[masterName] || {
        placeholder: 'Buscar registro...',
        label: 'registros',
        loading: 'Cargando datos...'
    };

    // Actualizar Placeholder dinámico y limpiar input
    const searchInput = document.getElementById('search-maestros');
    if (searchInput) {
        searchInput.placeholder = cfg.placeholder;
        searchInput.value = '';
    }

    const counter = document.getElementById('counter-maestros');
    if (counter) counter.innerText = 'Cargando...';

    const thead = document.getElementById('thead-maestros');
    const tbody = document.getElementById('tbody-maestros');

    // Loader centrado en el medio de la tabla para transición suave
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" class="py-24 text-center">
                    <div class="flex flex-col items-center justify-center gap-3">
                        <div class="relative w-10 h-10">
                            <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                            <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                        </div>
                        <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                            ${cfg.loading}
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    try {
        const [res] = await Promise.all([
            fetch(`/api/sheet/${masterName.toUpperCase()}?_t=${Date.now()}`),
            new Promise(r => setTimeout(r, 180))
        ]);
        const json = await res.json();

        if (json.status !== 'success' || !json.headers.length) {
            thead.innerHTML = '';
            tbody.innerHTML = `<tr><td class="p-4 text-slate-400">Sin datos en ${masterName}.</td></tr>`;
            renderPaginationBar('maestros', 'pagination-maestros', { totalItems: 0 });
            return;
        }

        if (masterName === 'unidades') {
            currentMasterUnidades = json.rows || [];
            thead.innerHTML = `
                <tr>
                    <th class="px-4 py-3">ID Unidad</th>
                    <th class="px-4 py-3">Tipo</th>
                    <th class="px-4 py-3">Dominio / Patente</th>
                    <th class="px-4 py-3">Marca / Modelo</th>
                    <th class="px-4 py-3">Descripción</th>
                    <th class="px-4 py-3"><i class="fa-solid fa-shield-halved text-amber mr-1"></i>Vencimiento Seguro</th>
                    <th class="px-4 py-3"><i class="fa-solid fa-clipboard-check text-amber mr-1"></i>Vencimiento ITV / RTO</th>
                    <th class="px-4 py-3 text-right">Acciones</th>
                </tr>
            `;
        } else if (masterName === 'empleados') {
            currentMasterEmpleados = json.rows || [];
            thead.innerHTML = `
                <tr>
                    <th class="px-4 py-3">ID Personal</th>
                    <th class="px-4 py-3">Empleado</th>
                    <th class="px-4 py-3 text-center">Estado</th>
                    <th class="px-4 py-3">Puesto / Cargo</th>
                    <th class="px-4 py-3">Sueldo Fijo ($)</th>
                    <th class="px-4 py-3">% Com. Granel</th>
                    <th class="px-4 py-3">Teléfono / Contacto</th>
                    <th class="px-4 py-3">Datos Bancarios</th>
                    <th class="px-4 py-3"><i class="fa-solid fa-id-card text-amber mr-1"></i>Venc. Licencia</th>
                    <th class="px-4 py-3 text-right">Acciones</th>
                </tr>
            `;
        } else if (masterName === 'clientes') {
            currentMasterClientes = json.rows || [];
            thead.innerHTML = `
                <tr>
                    <th class="px-4 py-3">ID Cliente</th>
                    <th class="px-4 py-3">Razón Social / Nombre</th>
                    <th class="px-4 py-3">CUIT / CUIL</th>
                    <th class="px-4 py-3"><i class="fa-solid fa-envelope text-amber mr-1"></i>Email / Correo</th>
                    <th class="px-4 py-3">Teléfono</th>
                    <th class="px-4 py-3">Condición IVA</th>
                    <th class="px-4 py-3">Domicilio</th>
                    <th class="px-4 py-3 text-right">Acciones</th>
                </tr>
            `;
        } else if (masterName === 'proveedores') {
            currentMasterProveedores = json.rows || [];
            thead.innerHTML = `
                <tr>
                    <th class="px-4 py-3">ID Proveedor</th>
                    <th class="px-4 py-3">Razón Social / Nombre</th>
                    <th class="px-4 py-3">CUIT</th>
                    <th class="px-4 py-3"><i class="fa-solid fa-building-columns text-amber mr-1"></i>CBU / ALIAS</th>
                    <th class="px-4 py-3">Rubro / Insumo</th>
                    <th class="px-4 py-3">Contacto (Tel / Email)</th>
                    <th class="px-4 py-3 text-right">Acciones / Reportes</th>
                </tr>
            `;
        } else if (masterName === 'usuarios') {
            currentMasterUsuarios = json.rows || [];
            thead.innerHTML = `
                <tr>
                    <th class="px-4 py-3">ID Usuario</th>
                    <th class="px-4 py-3">Nombre Completo</th>
                    <th class="px-4 py-3">Usuario (Login)</th>
                    <th class="px-4 py-3">Rol</th>
                    <th class="px-4 py-3">Estado</th>
                    <th class="px-4 py-3">Último Acceso</th>
                    <th class="px-4 py-3 text-right">Acciones</th>
                </tr>
            `;
        } else {
            currentGenericMasterHeaders = json.headers || [];
            currentGenericMasterRows = json.rows || [];
            thead.innerHTML = `<tr>${json.headers.map(h => `<th class="px-4 py-3">${h}</th>`).join('')}</tr>`;
        }

        filterMasterTable(0, true);

    } catch (err) {
        console.error("Error al cargar maestro:", err);
    }
}

// Master Row Render Functions
function renderMasterRowUnidad(r) {
    const uid = getRowProp(r, ['ID unidad', 'ID']);
    const tipo = getRowProp(r, ['Tipo']) || '-';
    const patente = getRowProp(r, ['Dominio/Patente', 'Patente']) || '-';
    const marcaMod = `${getRowProp(r, ['Marca']) || ''} ${getRowProp(r, ['Modelo']) || ''}`.trim() || '-';
    const desc = getRowProp(r, ['Descripción']) || '-';
    const seguroBadge = formatExpirationBadge(getRowProp(r, ['Seguro vence', 'Vencimiento Seguro']));
    const rtoBadge = formatExpirationBadge(getRowProp(r, ['RTO/ITV vence', 'Vencimiento ITV', 'RTO vence']));

    return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
            <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${uid}</td>
            <td class="px-4 py-3 font-medium">${tipo}</td>
            <td class="px-4 py-3 font-bold text-slate-800 whitespace-nowrap">${patente}</td>
            <td class="px-4 py-3 font-medium">${marcaMod}</td>
            <td class="px-4 py-3 text-slate-600">${desc}</td>
            <td class="px-4 py-3 whitespace-nowrap">${seguroBadge}</td>
            <td class="px-4 py-3 whitespace-nowrap">${rtoBadge}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="editUnidad('${uid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[11px] transition-all cursor-pointer" title="Editar Unidad y Fechas de Vencimiento">
                        <i class="fa-solid fa-pen"></i> Editar
                    </button>
                    <button onclick="deleteUnidad('${uid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 transition-all cursor-pointer" title="Eliminar Registro">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function renderMasterRowEmpleado(r) {
    const eid = getRowProp(r, ['ID empleado', 'ID', 'id_empleado']);
    const nombre = getRowProp(r, ['Apellido y nombre', 'Empleado', 'Nombre', 'apellido_nombre']) || '-';
    const puesto = getRowProp(r, ['Cargo / Puesto', 'Puesto', 'Cargo', 'puesto']) || 'Chofer';
    const sFijoVal = getRowProp(r, ['Sueldo fijo', 'Sueldo', 'Sueldo básico', 'sueldo_fijo', 'sueldo_basico']);
    const sFijo = parseFloat(String(sFijoVal || '0').replace(/[^0-9.-]+/g, '')) || 0;
    const pctComVal = getRowProp(r, ['Porcentaje comisión (%)', 'Porcentaje comision', 'Comisión %', 'comision_pct']);
    const pctCom = parseFloat(String(pctComVal || '0').replace(/[^0-9.-]+/g, '')) || 0;
    
    const tel = getRowProp(r, ['Teléfono', 'Celular', 'telefono', 'Teléfono contacto', 'telefono_contacto']) || '-';
    const cbuAlias = getRowProp(r, ['Alias CBU', 'Alias', 'alias_cbu']) || getRowProp(r, ['CBU', 'cbu']) || '-';
    const licBadge = formatEmpleadoLicenciasBadges(r);

    const pctBadge = pctCom > 0 ? `<span class="bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded text-[11px] border border-emerald-200">${pctCom}%</span>` : `<span class="text-slate-400">0%</span>`;

    const rawEst = String(getRowProp(r, ['Estado', 'estado']) || '').trim().toLowerCase();
    const isActivo = !rawEst || rawEst === 'activo';
    const estBadge = isActivo
        ? `<span class="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px] border border-emerald-200"><i class="fa-solid fa-circle text-[6px] text-emerald-500"></i>Activo</span>`
        : `<span class="inline-flex items-center gap-1 bg-rose-50 text-rose-700 font-bold px-2 py-0.5 rounded-full text-[10px] border border-rose-200"><i class="fa-solid fa-circle text-[6px] text-rose-500"></i>Baja</span>`;

    const toggleEstadoBtn = isActivo
        ? `<button onclick="toggleEstadoEmpleado('${eid}', 'Baja')" class="inline-flex items-center gap-1 bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold px-2 py-1 rounded text-[11px] border border-amber-200 transition-all cursor-pointer" title="Dar de Baja a este Empleado">
               <i class="fa-solid fa-user-slash"></i> Baja
           </button>`
        : `<button onclick="toggleEstadoEmpleado('${eid}', 'Activo')" class="inline-flex items-center gap-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold px-2 py-1 rounded text-[11px] border border-emerald-200 transition-all cursor-pointer" title="Reactivar Empleado">
               <i class="fa-solid fa-user-check"></i> Activar
           </button>`;

    return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
            <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${eid}</td>
            <td class="px-4 py-3 font-bold text-slate-800">${nombre}</td>
            <td class="px-4 py-3 text-center whitespace-nowrap">${estBadge}</td>
            <td class="px-4 py-3 font-semibold text-slate-700"><span class="bg-blue-50 text-navy px-2 py-0.5 rounded border border-blue-100">${puesto}</span></td>
            <td class="px-4 py-3 font-semibold text-slate-800">${sFijo > 0 ? formatARS(sFijo) : '-'}</td>
            <td class="px-4 py-3 whitespace-nowrap">${pctBadge}</td>
            <td class="px-4 py-3 text-slate-600">${tel}</td>
            <td class="px-4 py-3 font-mono text-[11px] text-slate-700">${cbuAlias}</td>
            <td class="px-4 py-3 whitespace-nowrap">${licBadge}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <div class="inline-flex items-center justify-end gap-1.5">
                    ${toggleEstadoBtn}
                    <button onclick="editEmpleado('${eid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[11px] transition-all cursor-pointer" title="Ver / Editar Ficha de Personal y Comisiones">
                        <i class="fa-solid fa-user-pen"></i> Editar Ficha
                    </button>
                    <button onclick="deleteEmpleado('${eid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-[11px] border border-rose-200 transition-all cursor-pointer" title="Eliminar Personal">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function renderMasterRowCliente(r) {
    const cid = getRowProp(r, ['ID cliente', 'ID', 'ID Cliente']);
    const nombre = getRowProp(r, ['Razón social / Nombre', 'Razón Social / Nombre', 'Razó­n social / Nombre', 'Nombre']) || '-';
    const cuit = getRowProp(r, ['CUIT/CUIL', 'CUIT / CUIL', 'CUIT', 'CUIL']) || '-';
    const email = getRowProp(r, ['Correo', 'Correo electrónico', 'Email']) || '-';
    const tel = getRowProp(r, ['Teléfono', 'Celular']) || '-';
    const iva = getRowProp(r, ['Condición IVA', 'IVA']) || '-';
    const dom = getRowProp(r, ['Domicilio']) || '-';

    return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
            <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${cid}</td>
            <td class="px-4 py-3 font-bold text-slate-800">${nombre}</td>
            <td class="px-4 py-3 font-bold text-slate-700 whitespace-nowrap">${cuit}</td>
            <td class="px-4 py-3 text-slate-600 font-medium whitespace-nowrap">${email !== '-' ? `<a href="mailto:${email}" class="text-navy hover:underline font-semibold"><i class="fa-solid fa-envelope text-amber mr-1"></i>${email}</a>` : '-'}</td>
            <td class="px-4 py-3 text-slate-600 whitespace-nowrap">${tel}</td>
            <td class="px-4 py-3 font-medium text-slate-700">${iva}</td>
            <td class="px-4 py-3 text-slate-600">${dom}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="editCliente('${cid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-xs transition-all cursor-pointer" title="Editar cliente">
                        <i class="fa-solid fa-pen-to-square"></i> Editar
                    </button>
                    <button onclick="deleteCliente('${cid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-xs border border-rose-200 transition-all cursor-pointer" title="Eliminar cliente">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function renderMasterRowProveedor(r) {
    const pid = getRowProp(r, ['ID proveedor', 'ID', 'ID Proveedor']);
    const nombre = getRowProp(r, ['Razón social / Nombre', 'Razón Social / Nombre', 'Razón social', 'Nombre']) || '-';
    const cuit = getRowProp(r, ['CUIT / CUIL', 'CUIT', 'CUIL']) || '-';
    const cbu = getRowProp(r, ['CBU / ALIAS', 'CBU/ALIAS', 'CBU', 'ALIAS']) || '-';
    const rubro = getRowProp(r, ['Rubro']) || 'Combustible';
    const email = getRowProp(r, ['Correo electrónico', 'Correo electronico', 'Email', 'Correo']) || '';
    const tel = getRowProp(r, ['Teléfono', 'Telefono', 'Celular']) || '';
    const safeNombre = nombre.replace(/'/g, "\\'");

    let contactoStr = '-';
    if (tel && email) contactoStr = `${tel} | ${email}`;
    else if (tel) contactoStr = tel;
    else if (email) contactoStr = email;

    const cbuDisplay = cbu && cbu !== '-'
        ? `<span class="bg-amber-50 text-amber-950 font-bold px-2 py-0.5 rounded border border-amber-200 font-mono text-[11px] inline-flex items-center gap-1"><i class="fa-solid fa-building-columns text-amber-600"></i>${cbu}</span>`
        : `<span class="text-slate-400 font-normal">-</span>`;

    return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
            <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${pid}</td>
            <td class="px-4 py-3 font-bold text-slate-800">${nombre}</td>
            <td class="px-4 py-3 font-bold text-slate-700 whitespace-nowrap">${cuit}</td>
            <td class="px-4 py-3 whitespace-nowrap">${cbuDisplay}</td>
            <td class="px-4 py-3 font-semibold text-slate-700 whitespace-nowrap"><span class="bg-slate-100 text-slate-800 px-2 py-0.5 rounded border border-slate-200">${rubro}</span></td>
            <td class="px-4 py-3 text-slate-600">${contactoStr}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="openResumenProveedorModal('${safeNombre}')" class="inline-flex items-center gap-1 bg-amber/10 hover:bg-amber/20 text-amber-dark font-bold px-2.5 py-1 rounded text-xs border border-amber/30 transition-all cursor-pointer shadow-sm" title="Descargar Resumen PDF del Proveedor">
                        <i class="fa-solid fa-file-pdf text-amber"></i> Resumen PDF
                    </button>
                    <button onclick="editProveedor('${pid}')" class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-xs transition-all cursor-pointer" title="Editar proveedor">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button onclick="deleteProveedor('${pid}')" class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-xs border border-rose-200 transition-all cursor-pointer" title="Eliminar proveedor">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function renderMasterRowUsuario(r) {
    const uid = getRowProp(r, ['ID usuario', 'id_usuario', 'ID']);
    const nombre = getRowProp(r, ['Nombre completo', 'nombre_completo', 'Nombre']) || '-';
    const uname = getRowProp(r, ['Usuario', 'usuario']) || '-';
    const rol = getRowProp(r, ['Rol', 'rol']) || 'Usuario';
    const estado = getRowProp(r, ['Estado', 'estado']) || 'Activo';
    const ultAcceso = formatDateTimeAR(getRowProp(r, ['Último acceso', 'ultimo_acceso']));

    const isActivo = estado.toLowerCase() === 'activo';
    const estadoBadge = isActivo 
        ? `<span class="bg-emerald-100 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-full font-bold text-[10px] inline-flex items-center gap-1"><i class="fa-solid fa-circle text-[6px]"></i> Activo</span>`
        : `<span class="bg-rose-100 text-rose-700 border border-rose-200 px-2.5 py-0.5 rounded-full font-bold text-[10px] inline-flex items-center gap-1"><i class="fa-solid fa-ban text-[8px]"></i> Inactivo</span>`;

    let rolBadge = `<span class="bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-lg font-bold text-[10px]">Usuario</span>`;
    if (rol === 'Administrador') {
        rolBadge = `<span class="bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-lg font-black text-[10px] inline-flex items-center gap-1"><i class="fa-solid fa-shield-halved text-amber-600"></i> Administrador</span>`;
    }

    const isSelf = uid === window.CURRENT_USER_ID || uname.toLowerCase() === (window.CURRENT_USER_NAME || '').toLowerCase();
    const toggleBtnText = isActivo ? 'Desactivar' : 'Activar';
    const toggleBtnClass = isActivo 
        ? 'bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200' 
        : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200';

    return `
        <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
            <td class="px-4 py-3 font-bold text-navy whitespace-nowrap">${uid}</td>
            <td class="px-4 py-3 font-bold text-slate-800">${nombre}</td>
            <td class="px-4 py-3 font-mono font-bold text-slate-600">@${uname}</td>
            <td class="px-4 py-3 whitespace-nowrap">${rolBadge}</td>
            <td class="px-4 py-3 whitespace-nowrap">${estadoBadge}</td>
            <td class="px-4 py-3 text-slate-500 whitespace-nowrap">${ultAcceso}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <div class="inline-flex items-center justify-end gap-1.5">
                    <button onclick="openCambiarPasswordUsuarioModal('${uid}', '${nombre.replace(/'/g, "\\'")}', '${uname.replace(/'/g, "\\'")}')" 
                        class="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-xs transition-all cursor-pointer" title="Cambiar Contraseña">
                        <i class="fa-solid fa-key text-amber-600"></i> Clave
                    </button>
                    ${!isSelf ? `
                        <button onclick="toggleEstadoUsuario('${uid}', '${uname.replace(/'/g, "\\'")}', '${estado}')" 
                            class="inline-flex items-center gap-1 ${toggleBtnClass} font-bold px-2 py-1 rounded text-xs transition-all cursor-pointer" title="${toggleBtnText} Acceso">
                            <i class="fa-solid fa-power-off"></i> ${toggleBtnText}
                        </button>
                        <button onclick="deleteUsuario('${uid}', '${uname.replace(/'/g, "\\'")}')" 
                            class="inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold px-2 py-1 rounded text-xs border border-rose-200 transition-all cursor-pointer" title="Eliminar Usuario">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    ` : `
                        <span class="text-[10px] text-slate-400 font-semibold italic px-1">(Tu cuenta)</span>
                    `}
                </div>
            </td>
        </tr>
    `;
}

let currentGenericMasterHeaders = [];
let currentGenericMasterRows = [];
let masterFilterDebounceTimer = null;
let lastMasterQueryActive = false;

function getActiveMasterDataList() {
    if (currentMasterTab === 'unidades') return currentMasterUnidades || [];
    if (currentMasterTab === 'empleados') return currentMasterEmpleados || [];
    if (currentMasterTab === 'clientes') return currentMasterClientes || [];
    if (currentMasterTab === 'proveedores') return currentMasterProveedores || [];
    if (currentMasterTab === 'usuarios') return currentMasterUsuarios || [];
    return currentGenericMasterRows || [];
}

function filterMasterTable(delay = 180, isDropdown = false) {
    const rawQ = (document.getElementById('search-maestros')?.value || '').trim();
    const isNowActive = rawQ.length >= 3;

    if (!isDropdown && !isNowActive && !lastMasterQueryActive && rawQ.length > 0) {
        return;
    }

    if (masterFilterDebounceTimer) {
        clearTimeout(masterFilterDebounceTimer);
    }

    lastMasterQueryActive = isNowActive;
    resetTablePaginationPage('maestros');

    masterFilterDebounceTimer = setTimeout(() => {
        applyMasterFilter();
    }, delay);
}

function applyMasterFilter() {
    const searchInput = document.getElementById('search-maestros');
    const rawQ = (searchInput?.value || '').trim();
    const q = rawQ.length >= 3 ? rawQ.toLowerCase() : '';
    const allRows = getActiveMasterDataList();

    const filtered = allRows.filter(r => {
        if (!q) return true;
        const text = Object.values(r).map(v => str(v)).join(' ').toLowerCase();
        return text.includes(q);
    });

    const counter = document.getElementById('counter-maestros');
    if (counter) {
        let label = 'registros';
        if (currentMasterTab === 'clientes') label = 'clientes';
        else if (currentMasterTab === 'unidades') label = 'unidades / máquinas';
        else if (currentMasterTab === 'empleados') label = 'empleados';
        else if (currentMasterTab === 'proveedores') label = 'proveedores';
        else if (currentMasterTab === 'usuarios') label = 'usuarios';

        counter.innerText = `${filtered.length} ${label}`;
    }

    renderMasterCurrentTable(filtered);
}

function renderMasterCurrentTable(rowsToRender) {
    const tbody = document.getElementById('tbody-maestros');
    if (!tbody) return;

    if (!rowsToRender.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center py-6 text-slate-400 font-medium">No se encontraron registros con los filtros seleccionados.</td></tr>`;
        renderPaginationBar('maestros', 'pagination-maestros', { totalItems: 0 });
        return;
    }

    paginateAndRender('maestros', 'pagination-maestros', rowsToRender, (pageRows) => {
        let rowHtml = '';
        if (currentMasterTab === 'unidades') {
            rowHtml = pageRows.map(renderMasterRowUnidad).join('');
        } else if (currentMasterTab === 'empleados') {
            rowHtml = pageRows.map(renderMasterRowEmpleado).join('');
        } else if (currentMasterTab === 'clientes') {
            rowHtml = pageRows.map(renderMasterRowCliente).join('');
        } else if (currentMasterTab === 'proveedores') {
            rowHtml = pageRows.map(renderMasterRowProveedor).join('');
        } else if (currentMasterTab === 'usuarios') {
            rowHtml = pageRows.map(renderMasterRowUsuario).join('');
        } else {
            rowHtml = pageRows.map(r => `
                <tr class="hover:bg-slate-50 border-b border-slate-100 text-xs">
                    ${(currentGenericMasterHeaders || []).map(h => `<td class="px-4 py-3">${r[h] || '-'}</td>`).join('')}
                </tr>
            `).join('');
        }
        tbody.innerHTML = rowHtml;
    }, 10);
}


function populateResumenProveedorAnios(defaultToCurrent = true) {
    const anioSel = document.getElementById('resumen-prov-anio');
    if (!anioSel) return;

    const currentYear = new Date().getFullYear();
    const targetYear = defaultToCurrent ? currentYear.toString() : (anioSel.value || currentYear.toString());

    // Año base del sistema: 2026. No muestra años anteriores a este.
    // Muestra dinámicamente desde el año actual + 1 hasta 2026 cada vez que pasemos de año.
    const baseYear = Math.min(2026, currentYear);
    const maxYear = Math.max(currentYear + 1, baseYear + 1);

    let html = '';
    for (let y = maxYear; y >= baseYear; y--) {
        const isSelected = String(y) === String(targetYear);
        html += `<option value="${y}" ${isSelected ? 'selected' : ''}>${y}</option>`;
    }
    html += `<option value="todos" ${targetYear === 'todos' ? 'selected' : ''}>Todos los Años</option>`;

    anioSel.innerHTML = html;
    anioSel.value = targetYear;
}

function openResumenProveedorModal(provName) {
    document.getElementById('resumen-prov-nombre').value = provName;
    document.getElementById('resumen-prov-title-lbl').innerText = provName;
    document.getElementById('resumen-prov-mes').value = 'todas';
    populateResumenProveedorAnios(true);
    const anioSel = document.getElementById('resumen-prov-anio');
    if (anioSel) {
        anioSel.value = new Date().getFullYear().toString();
    }
    openModal('modal-resumen-proveedor');
}

function downloadResumenProveedorPDF(e) {
    if (e && e.preventDefault) e.preventDefault();
    const prov = encodeURIComponent(document.getElementById('resumen-prov-nombre').value || '');
    const mes = encodeURIComponent(document.getElementById('resumen-prov-mes').value || 'todas');
    const anio = encodeURIComponent(document.getElementById('resumen-prov-anio').value || 'todos');
    closeModal('modal-resumen-proveedor');
    window.open(`/api/maestros/proveedor/resumen_pdf?proveedor=${prov}&mes=${mes}&anio=${anio}`, '_blank');
}

function verDesgloseLiquidacion(eid) {
    let item = currentTabLiquidacionesData.find(l => l.id_empleado === eid);
    if (!item) item = currentHistorialLiquidacionesData.find(l => l.id_empleado === eid);
    if (!item) item = currentLiquidacionesData.find(l => l.id_empleado === eid);
    if (!item) return;

    document.getElementById('modal-dl-title').innerHTML = `<i class="fa-solid fa-calculator text-emerald-600"></i> Desglose de Liquidación (${item.periodo_label}): ${item.nombre} (${item.id_empleado})`;
    document.getElementById('dl-sueldo-fijo').innerText = formatARS(item.sueldo_fijo_base);
    document.getElementById('dl-total-comisiones').innerText = formatARS(item.total_comisiones);
    document.getElementById('dl-sueldo-final').innerText = formatARS(item.sueldo_final);

    const tbody = document.getElementById('dl-tbody-viajes');
    const viajesList = item.desglose_viajes || item.viajes || [];
    if (!viajesList.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="p-6 text-center text-slate-500 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                    <p class="font-semibold text-slate-700">El empleado no posee operaciones asignadas en <strong>${item.periodo_label}</strong>.</p>
                    <p class="text-slate-400 mt-1">Si el viaje se realizó después del día 15 (o en otro período), puedes cambiar la quincena:</p>
                    <div class="flex justify-center gap-2 pt-3">
                        <button type="button" onclick="switchQuincenaTab('q2', '${eid}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer">
                            <i class="fa-solid fa-calendar-days mr-1"></i> Ver 2ª Quincena (Días 16-31)
                        </button>
                        <button type="button" onclick="switchQuincenaTab('todas', '${eid}')" class="bg-amber hover:bg-amber-dark text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer">
                            <i class="fa-solid fa-calendar-check mr-1"></i> Ver Mes Completo
                        </button>
                    </div>
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = viajesList.map(v => {
            const aplicaCom = v.aplica_comision !== undefined ? v.aplica_comision : true;
            return `
                <tr class="hover:bg-slate-50 border-b border-slate-100 text-xs">
                    <td class="px-3 py-2 font-bold text-navy">${v.id || getRowProp(v, ['ID viaje', 'ID']) || '-'}</td>
                    <td class="px-3 py-2 text-slate-700 font-medium">${v.nro_factura || getRowProp(v, ['N° remito', 'remito']) || '-'}</td>
                    <td class="px-3 py-2 text-slate-600 whitespace-nowrap">${formatDateAR(v.fecha || getRowProp(v, ['Fecha salida', 'Fecha']))}</td>
                    <td class="px-3 py-2 text-slate-800 font-medium">${v.cliente || getRowProp(v, ['Cliente']) || '-'}</td>
                    <td class="px-3 py-2 text-right font-medium text-slate-700">${formatARS(v.monto_neto !== undefined ? v.monto_neto : parseFloat(getRowProp(v, ['Valor viaje neto', 'Monto']) || 0))}</td>
                    <td class="px-3 py-2 text-right font-bold text-emerald-700">${v.comision_pct || item.comision_pct || 0}%</td>
                    <td class="px-3 py-2 text-right font-bold text-emerald-600">${formatARS(v.comision_ganada !== undefined ? v.comision_ganada : (v.comision_monto || 0))}</td>
                </tr>
            `;
        }).join('');
    }

    // Render novelties section inside desglose modal
    let novSection = document.getElementById('dl-novedades-container');
    if (!novSection) {
        novSection = document.createElement('div');
        novSection.id = 'dl-novedades-container';
        novSection.className = 'space-y-2 pt-2 border-t border-slate-200 mt-4';
        const modalBody = document.querySelector('#modal-desglose-liquidacion > div');
        if (modalBody) {
            const btnCloseContainer = modalBody.lastElementChild;
            modalBody.insertBefore(novSection, btnCloseContainer);
        }
    }

    const novedades = item.novedades || item.novedades_emp || [];
    if (!novedades.length) {
        novSection.innerHTML = `
            <h4 class="font-bold text-slate-800 text-xs flex items-center gap-1.5 mt-3">
                <i class="fa-solid fa-receipt text-amber"></i> Novedades de Personal (Adelantos & Reintegros):
            </h4>
            <div class="p-3 text-center text-slate-400 bg-slate-50 rounded-xl border border-slate-200 text-xs">Sin adelantos ni reintegros registrados en este período.</div>
        `;
    } else {
        novSection.innerHTML = `
            <h4 class="font-bold text-slate-800 text-xs flex items-center gap-1.5 mt-3">
                <i class="fa-solid fa-receipt text-amber"></i> Novedades de Personal (Adelantos & Reintegros):
            </h4>
            <div class="overflow-x-auto border border-slate-200 rounded-xl">
                <table class="w-full text-left text-xs text-slate-700">
                    <thead class="bg-slate-100 font-semibold border-b border-slate-200 text-slate-600">
                        <tr>
                            <th class="px-3 py-2">ID Novedad</th>
                            <th class="px-3 py-2">Fecha</th>
                            <th class="px-3 py-2">Tipo</th>
                            <th class="px-3 py-2">Concepto / Motivo</th>
                            <th class="px-3 py-2">Medio Pago</th>
                            <th class="px-3 py-2 text-right">Monto ($)</th>
                            <th class="px-3 py-2 text-center">Acción</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        ${novedades.map(n => {
                            const nid = n.id || n['ID novedad'] || n['ID'] || '';
                            const tipoStr = String(n.tipo || n['Tipo'] || 'Deducción');
                            const isDed = tipoStr.toLowerCase().includes('deduc') || tipoStr.toLowerCase().includes('adelanto');
                            const badge = isDed 
                                ? `<span class="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded text-[10px]">🔻 Deducción</span>`
                                : `<span class="bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded text-[10px]">🔺 Reintegro</span>`;
                            const montoVal = n.monto !== undefined ? parseFloat(n.monto) : (parseFloat(n['Monto']) || 0);
                            const montoFormatted = isDed ? `-${formatARS(montoVal)}` : `+${formatARS(montoVal)}`;
                            const montoColor = isDed ? 'text-rose-600 font-bold' : 'text-emerald-700 font-bold';
                            const st = String(n.estado || n['Estado'] || 'Pendiente').toLowerCase();
                            const isLiq = st === 'liquidado';

                            const btnAction = isLiq
                                ? `<span class="text-slate-400 text-[10px]"><i class="fa-solid fa-lock text-emerald-600"></i> Liquidado</span>`
                                : `<button onclick="confirmarEliminarNovedad('${nid}', '${item.nombre}', ${montoVal}); closeModal('modal-desglose-liquidacion');" class="bg-rose-50 hover:bg-rose-100 text-rose-700 p-1 rounded transition-all cursor-pointer" title="Eliminar novedad y devolver fondos">
                                    <i class="fa-solid fa-trash-can"></i>
                                   </button>`;

                            return `
                                <tr class="hover:bg-slate-50 border-b border-slate-100 transition-all text-xs">
                                    <td class="px-3 py-2 font-bold text-navy font-mono">${nid || '-'}</td>
                                    <td class="px-3 py-2 text-slate-600">${formatDateAR(n.fecha || n['Fecha'])}</td>
                                    <td class="px-3 py-2">${badge}</td>
                                    <td class="px-3 py-2 text-slate-800 font-medium">${n.concepto || n['Concepto'] || '-'}</td>
                                    <td class="px-3 py-2 text-slate-600">${n.medio_pago || n['Medio de pago'] || n['Medio Pago'] || '-'}</td>
                                    <td class="px-3 py-2 text-right ${montoColor}">${montoFormatted}</td>
                                    <td class="px-3 py-2 text-center">${btnAction}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    openModal('modal-desglose-liquidacion');
}

// ==================== GESTIÓN DE USUARIOS DEL SISTEMA (ADMIN) ====================
let currentMasterUsuarios = [];

function togglePasswordVisibilityField(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    } else {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
}

function openNuevoUsuarioModal() {
    if (window.CURRENT_USER_ROLE !== 'Administrador') {
        alert("Acceso denegado: Esta función es exclusiva para el rol Administrador.");
        return;
    }
    const form = document.getElementById('form-usuario');
    if (form) form.reset();
    const errBox = document.getElementById('mu-error-box');
    if (errBox) errBox.classList.add('hidden');
    openModal('modal-usuario');
}

async function handleGuardarUsuario(e) {
    e.preventDefault();
    const errBox = document.getElementById('mu-error-box');
    const errMsg = document.getElementById('mu-error-msg');
    const btn = document.getElementById('mu-submit-btn');

    const nombre = document.getElementById('mu-nombre')?.value.trim();
    const username = document.getElementById('mu-username')?.value.trim();
    const rol = document.getElementById('mu-rol')?.value;
    const password = document.getElementById('mu-password')?.value.trim();

    if (!nombre || !username || !password) {
        if (errBox && errMsg) {
            errMsg.innerText = "Por favor complete todos los campos obligatorios.";
            errBox.classList.remove('hidden');
        }
        return;
    }

    if (password.length < 4) {
        if (errBox && errMsg) {
            errMsg.innerText = "La contraseña debe tener al menos 4 caracteres.";
            errBox.classList.remove('hidden');
        }
        return;
    }

    if (errBox) errBox.classList.add('hidden');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`;
    }

    try {
        const res = await fetch('/api/maestros/usuario/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre_completo: nombre,
                usuario: username,
                rol: rol,
                password: password
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            closeModal('modal-usuario');
            if (typeof showToast === 'function') {
                showToast(`Usuario @${username} creado exitosamente`, 'success');
            } else {
                alert(`Usuario @${username} registrado con éxito.`);
            }
            await switchMasterTab('usuarios');
        } else {
            if (errBox && errMsg) {
                errMsg.innerText = data.message || "Error al registrar el usuario.";
                errBox.classList.remove('hidden');
            } else {
                alert(data.message || "Error al registrar el usuario.");
            }
        }
    } catch (err) {
        console.error("Error al registrar usuario:", err);
        if (errBox && errMsg) {
            errMsg.innerText = "Error de conexión con el servidor.";
            errBox.classList.remove('hidden');
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-check"></i> Registrar Usuario`;
        }
    }
}

function openCambiarPasswordUsuarioModal(userId, nombre, username) {
    if (window.CURRENT_USER_ROLE !== 'Administrador') {
        alert("Acceso denegado: Esta función es exclusiva para el rol Administrador.");
        return;
    }
    const inputId = document.getElementById('cp-user-id');
    const label = document.getElementById('cp-user-label');
    const pwd1 = document.getElementById('cp-password');
    const pwd2 = document.getElementById('cp-password-confirm');
    const errBox = document.getElementById('cp-error-box');

    if (inputId) inputId.value = userId;
    if (label) label.innerText = `${nombre} (@${username})`;
    if (pwd1) pwd1.value = '';
    if (pwd2) pwd2.value = '';
    if (errBox) errBox.classList.add('hidden');

    openModal('modal-cambiar-password-usuario');
}

async function handleGuardarPasswordUsuario(e) {
    e.preventDefault();
    const errBox = document.getElementById('cp-error-box');
    const errMsg = document.getElementById('cp-error-msg');
    const btn = document.getElementById('cp-submit-btn');

    const uid = document.getElementById('cp-user-id')?.value;
    const pwd1 = document.getElementById('cp-password')?.value.trim();
    const pwd2 = document.getElementById('cp-password-confirm')?.value.trim();

    if (!pwd1 || !pwd2) {
        if (errBox && errMsg) {
            errMsg.innerText = "Por favor ingrese y confirme la nueva clave.";
            errBox.classList.remove('hidden');
        }
        return;
    }

    if (pwd1 !== pwd2) {
        if (errBox && errMsg) {
            errMsg.innerText = "Las contraseñas no coinciden.";
            errBox.classList.remove('hidden');
        }
        return;
    }

    if (pwd1.length < 4) {
        if (errBox && errMsg) {
            errMsg.innerText = "La contraseña debe tener al menos 4 caracteres.";
            errBox.classList.remove('hidden');
        }
        return;
    }

    if (errBox) errBox.classList.add('hidden');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`;
    }

    try {
        const res = await fetch('/api/maestros/usuario/change_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_usuario: uid, password: pwd1 })
        });
        const data = await res.json();

        if (data.status === 'success') {
            closeModal('modal-cambiar-password-usuario');
            if (typeof showToast === 'function') {
                showToast("Contraseña actualizada exitosamente", 'success');
            } else {
                alert("Contraseña actualizada con éxito.");
            }
        } else {
            if (errBox && errMsg) {
                errMsg.innerText = data.message || "Error al actualizar la contraseña.";
                errBox.classList.remove('hidden');
            } else {
                alert(data.message || "Error al actualizar la contraseña.");
            }
        }
    } catch (err) {
        console.error("Error al actualizar contraseña:", err);
        if (errBox && errMsg) {
            errMsg.innerText = "Error de conexión con el servidor.";
            errBox.classList.remove('hidden');
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Guardar Nueva Clave`;
        }
    }
}

async function toggleEstadoUsuario(userId, username = '', estadoActual = 'Activo') {
    if (window.CURRENT_USER_ROLE !== 'Administrador') {
        if (typeof showToast === 'function') showToast("Acceso exclusivo para Administradores.", 'error');
        return;
    }

    const esActivo = String(estadoActual || 'Activo').toLowerCase() === 'activo';
    const accion = esActivo ? 'Desactivar' : 'Activar';
    const userLabel = username ? `<b>@${username}</b>` : `<b>${userId}</b>`;
    const iconClass = esActivo 
        ? "fa-solid fa-user-slash text-amber-500 text-3xl"
        : "fa-solid fa-user-check text-emerald-500 text-3xl";
    const btnClass = esActivo
        ? "px-5 py-2.5 rounded-xl text-white font-bold bg-amber-600 hover:bg-amber-700 shadow-md transition-all cursor-pointer text-sm"
        : "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-sm";

    const confirmed = await showConfirmModal(
        `${accion} Usuario`,
        `¿Estás seguro de ${accion.toLowerCase()} el acceso al sistema para el usuario ${userLabel}?`,
        {
            iconClass: iconClass,
            confirmText: `Sí, ${accion}`,
            confirmBtnClass: btnClass
        }
    );
    if (!confirmed) return;

    if (typeof showLoading === 'function') {
        showLoading(`${accion} Usuario`, `Actualizando estado de ${userId}...`);
    }

    try {
        const res = await fetch('/api/maestros/usuario/toggle_estado', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_usuario: userId })
        });
        const data = await res.json();
        if (typeof hideLoading === 'function') hideLoading();

        if (data.status === 'success') {
            if (typeof showToast === 'function') showToast(data.message, 'success');
            await switchMasterTab('usuarios');
        } else {
            if (typeof showToast === 'function') showToast(data.message || "Error al modificar estado.", 'error');
        }
    } catch (err) {
        if (typeof hideLoading === 'function') hideLoading();
        console.error("Error al modificar estado:", err);
        if (typeof showToast === 'function') showToast("Error de conexión al modificar estado.", 'error');
    }
}

async function deleteUsuario(userId, username) {
    if (window.CURRENT_USER_ROLE !== 'Administrador') {
        if (typeof showToast === 'function') showToast("Acceso exclusivo para Administradores.", 'error');
        return;
    }

    const userLabel = username ? `<b>@${username}</b>` : `<b>${userId}</b>`;
    const confirmed = await showConfirmModal(
        "Eliminar Usuario",
        `¿Estás seguro de eliminar definitivamente al usuario ${userLabel}? Esta acción borrará sus credenciales y no se puede deshacer.`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar Usuario",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    if (typeof showLoading === 'function') {
        showLoading("Eliminando Usuario", `Eliminando ${userId} de la base de datos...`);
    }

    try {
        const res = await fetch('/api/maestros/usuario/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_usuario: userId })
        });
        const data = await res.json();
        if (typeof hideLoading === 'function') hideLoading();

        if (data.status === 'success') {
            if (typeof showToast === 'function') showToast(data.message, 'success');
            await switchMasterTab('usuarios');
        } else {
            if (typeof showToast === 'function') showToast(data.message || "Error al eliminar usuario.", 'error');
        }
    } catch (err) {
        if (typeof hideLoading === 'function') hideLoading();
        console.error("Error al eliminar usuario:", err);
        if (typeof showToast === 'function') showToast("Error de conexión al eliminar usuario.", 'error');
    }
}


