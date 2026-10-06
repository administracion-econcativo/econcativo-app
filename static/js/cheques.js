/**
 * ECONCATIVO - Cheques (Cartera & Propios) Module
 */

// CHEQUES MODULE FRONTEND LOGIC
let globalChequesData = [];
let chequesFilterDebounceTimer = null;
let lastChequesQueryActive = false;

function showChequesLoaders() {
    const tbodyDisp = document.getElementById('tbody-cheques-disponibles');
    const tbodyUsados = document.getElementById('tbody-cheques-usados');
    const counter = document.getElementById('counter-cheques');
    if (counter) counter.innerText = 'Cargando...';

    const getLoader = (label) => `
        <tr>
            <td colspan="8" class="py-24 text-center">
                <div class="flex flex-col items-center justify-center gap-3">
                    <div class="relative w-10 h-10">
                        <div class="w-10 h-10 rounded-full border-4 border-slate-200"></div>
                        <div class="w-10 h-10 rounded-full border-4 border-navy border-t-transparent animate-spin absolute top-0 left-0"></div>
                    </div>
                    <div class="text-xs font-semibold text-slate-500 animate-pulse tracking-wide">
                        ${label}
                    </div>
                </div>
            </td>
        </tr>
    `;

    if (tbodyDisp) tbodyDisp.innerHTML = getLoader('Cargando cartera de cheques disponibles...');
    if (tbodyUsados) tbodyUsados.innerHTML = getLoader('Cargando historial de cheques...');
}

async function loadChequesData() {
    showChequesLoaders();
    try {
        const res = await fetch(`/api/cheques?_t=${Date.now()}`);
        const json = await res.json();
        if (json.status === 'success') {
            globalChequesData = json.data || [];
            renderChequesTables();
        }
    } catch (err) {
        console.error("Error al cargar datos de cheques:", err);
    }
}

function renderChequesTables() {
    const rawSearch = (document.getElementById('search-cheques')?.value || '').trim();
    const searchVal = rawSearch.length >= 3 ? rawSearch.toLowerCase() : '';
    const tipoVal = document.getElementById('filter-chq-tipo')?.value || '';
    const origenVal = document.getElementById('filter-chq-origen')?.value || '';

    let filtered = globalChequesData.filter(c => {
        if (tipoVal && c.tipo !== tipoVal) return false;
        
        const isPropio = (c.id && c.id.startsWith('CHQP-')) || str(c.origen).toLowerCase() === 'propio';
        if (origenVal === 'Propio' && !isPropio) return false;
        if (origenVal === 'Terceros' && isPropio) return false;

        if (searchVal) {
            const matchTxt = `${c.id} ${c.cliente} ${c.banco} ${c.nro_cheque} ${c.endosado} ${c.destino} ${c.observaciones} ${c.origen}`.toLowerCase();
            if (!matchTxt.includes(searchVal)) return false;
        }
        return true;
    });

    const isDisponibleOrPending = (c) => {
        const st = str(c.estado).toLowerCase().trim();
        if (st.includes('rechazado') || st.includes('rebotado') || st.includes('re-presentac') || st.includes('anulado') || st.includes('incobrable') || st.includes('usado') || st.includes('debitado') || st.includes('regularizado')) {
            return false;
        }
        return st === 'disponible' || st === 'en cartera' || st === 'pendiente';
    };

    const disponibles = filtered.filter(isDisponibleOrPending);
    const usados = filtered.filter(c => !isDisponibleOrPending(c));

    // Cartera Disponible: sum of 'Disponible' cheques
    // Total Endosados / Usados: sum of valid used/endorsed cheques (excluding Anulados/Rebotados)
    const dispMonto = disponibles.reduce((sum, c) => sum + (parseFloat(c.monto) || 0), 0);
    const usadosValidos = usados.filter(c => {
        const st = str(c.estado).toLowerCase();
        return st !== 'anulado' && !st.includes('rechazado') && !st.includes('re-presentaci');
    });
    const usadoMonto = usadosValidos.reduce((sum, c) => sum + (parseFloat(c.monto) || 0), 0);
    const usadosValidosCant = usadosValidos.length;

    if (document.getElementById('card-chq-disponible-monto')) document.getElementById('card-chq-disponible-monto').innerText = formatARS(dispMonto);
    if (document.getElementById('card-chq-disponible-cant')) document.getElementById('card-chq-disponible-cant').innerText = disponibles.length;
    if (document.getElementById('card-chq-usado-monto')) document.getElementById('card-chq-usado-monto').innerText = formatARS(usadoMonto);
    if (document.getElementById('card-chq-usado-cant')) document.getElementById('card-chq-usado-cant').innerText = usadosValidosCant;

    if (document.getElementById('badge-count-disponibles')) document.getElementById('badge-count-disponibles').innerText = `${disponibles.length} disponibles / pendientes`;
    if (document.getElementById('badge-count-usados')) document.getElementById('badge-count-usados').innerText = `${usados.length} en historial`;
    if (document.getElementById('counter-cheques')) document.getElementById('counter-cheques').innerText = `${filtered.length} cheques de ${globalChequesData.length}`;

    // Render Tabla 1: Cheques Disponibles / Pendientes
    const tbodyDisp = document.getElementById('tbody-cheques-disponibles');
    const sortedDisponibles = sortRecordsMostRecent(disponibles, ['fecha_cobro', 'fecha_ingreso', 'fecha'], ['id', 'ID']);
    if (tbodyDisp) {
        if (!sortedDisponibles.length) {
            tbodyDisp.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-400 font-medium">No hay cheques disponibles o pendientes en cartera.</td></tr>`;
            renderPaginationBar('cheques_disp', 'pagination-cheques-disponibles', { totalItems: 0 });
        } else {
            paginateAndRender('cheques_disp', 'pagination-cheques-disponibles', sortedDisponibles, (pageRows) => {
                tbodyDisp.innerHTML = pageRows.map(c => {
                const isPropio = (c.id && c.id.startsWith('CHQP-')) || str(c.origen).toLowerCase() === 'propio';
                if (isPropio) {
                    const hasRecipient = c.cliente && c.cliente !== 'Beneficiario' && c.cliente !== 'En Chequera (Sin Asignar)';
                    return `
                        <tr class="hover:bg-slate-50 transition-all border-b border-slate-100 bg-amber-50/20">
                            <td class="px-4 py-3 font-bold text-amber-900 flex items-center gap-1">
                                <span>💳</span> ${c.id}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-800 block">${c.tipo}</span>
                                <span class="text-[11px] text-amber-700 font-semibold">💳 Cheque Propio</span>
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-semibold text-slate-800 block">${hasRecipient ? c.cliente : 'En Chequera (Sin Asignar)'}</span>
                                <span class="text-[11px] text-slate-500">Emisión Propia</span>
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-navy block">${c.banco || 'Banco'}</span>
                                <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : '⚠️ Sin N° Cheque'}</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-700">
                                ${formatChequeExpirationBadge(c.fecha_cobro)}
                            </td>
                            <td class="px-4 py-3 font-black text-amber-800 text-sm">
                                ${formatARS(c.monto)}
                            </td>
                            <td class="px-4 py-3">
                                <span class="bg-emerald-100 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] shadow-sm">
                                    🟢 Disponible (Chequera)
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <div class="flex items-center justify-end gap-1.5">
                                    <button onclick="openUsarChequeModal('${c.id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1.5 rounded-lg transition-all text-xs flex items-center gap-1 shadow-sm cursor-pointer" title="Asignar a Proveedor/Chofer y registrar egreso">
                                        <i class="fa-solid fa-hand-holding-dollar"></i> Usar Cheque 💳
                                    </button>
                                    <button onclick="deleteCheque('${c.id}')" class="text-rose-400 hover:text-rose-600 p-1.5 rounded-lg transition-all text-xs" title="Eliminar cheque propio">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }

                return `
                    <tr class="hover:bg-slate-50 transition-all border-b border-slate-100">
                        <td class="px-4 py-3 font-bold text-navy">${c.id}</td>
                        <td class="px-4 py-3">
                            <span class="font-bold text-slate-800 block">${c.tipo}</span>
                            <span class="text-[11px] text-slate-400">Emisión: ${formatDateAR(c.fecha_ingreso)}</span>
                        </td>
                        <td class="px-4 py-3">
                            <span class="font-semibold text-slate-800 block">${c.cliente || '-'}</span>
                            <span class="text-[11px] text-slate-500">${c.cuit_emisor ? 'CUIT: ' + c.cuit_emisor : (c.id_ingreso ? 'Ingreso: ' + c.id_ingreso : '')}</span>
                        </td>
                        <td class="px-4 py-3">
                            <span class="font-bold text-slate-800 block">${c.banco || '⚠️ Completar Banco'}</span>
                            <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : '⚠️ Sin N° Cheque'}</span>
                        </td>
                        <td class="px-4 py-3 font-medium text-slate-700">
                            ${formatChequeExpirationBadge(c.fecha_cobro)}
                        </td>
                        <td class="px-4 py-3 font-black text-emerald-700 text-sm">
                            ${formatARS(c.monto)}
                        </td>
                        <td class="px-4 py-3">
                            <span class="bg-emerald-100 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] shadow-sm">
                                🟢 ${c.estado || 'Disponible'}
                            </span>
                        </td>
                        <td class="px-4 py-3 text-right">
                            <div class="flex items-center justify-end gap-1.5">
                                <button onclick="openUsarChequeModal('${c.id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2.5 py-1.5 rounded-lg transition-all text-xs flex items-center gap-1 shadow-sm cursor-pointer" title="Usar o endosar cheque">
                                    <i class="fa-solid fa-hand-holding-dollar"></i> Usar Cheque 💳
                                </button>
                                <button onclick="editCheque('${c.id}')" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold px-2.5 py-1.5 rounded-lg transition-all text-xs cursor-pointer" title="Completar o editar datos de banco/vencimiento">
                                    <i class="fa-solid fa-pen"></i> Datos
                                </button>
                                <button onclick="deleteCheque('${c.id}')" class="text-rose-400 hover:text-rose-600 p-1.5 rounded-lg transition-all text-xs" title="Eliminar de la cartera">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
            }, 10);
        }
    }

    // Render Tabla 2: Historial de Cheques Usados, Rebotados & Regularizados
    const tbodyUsados = document.getElementById('tbody-cheques-usados');
    const sortedUsados = sortRecordsMostRecent(usados, ['fecha_uso', 'fecha_cobro', 'fecha_ingreso'], ['id', 'ID']);
    if (tbodyUsados) {
        if (!sortedUsados.length) {
            tbodyUsados.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-400 font-medium">No hay registros de cheques usados o anulados.</td></tr>`;
            renderPaginationBar('cheques_usados', 'pagination-cheques-usados', { totalItems: 0 });
        } else {
            paginateAndRender('cheques_usados', 'pagination-cheques-usados', sortedUsados, (pageRows) => {
                tbodyUsados.innerHTML = pageRows.map(c => {
                const st = str(c.estado).toLowerCase();
                const isPropio = (c.id && c.id.startsWith('CHQP-')) || str(c.origen).toLowerCase() === 'propio';
                const isRebotadoPendiente = st.includes('rechazado') || st.includes('re-presentación');
                const isRegularizado = st.includes('regularizado');
                const isAnulado = st.includes('anulado') || st.includes('incobrable');

                if (isPropio && st.includes('debitado')) {
                    return `
                        <tr class="hover:bg-slate-50 transition-all border-b border-slate-100 bg-blue-50/20 text-xs">
                            <td class="px-4 py-3 font-bold text-navy flex items-center gap-1">
                                <span>💳</span> ${c.id}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-800 block">${c.tipo}</span>
                                <span class="text-[11px] text-blue-700 font-semibold">💳 Cheque Propio</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-800">
                                ${c.cliente || c.beneficiario || '-'}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-blue-950 block">${c.banco || '-'}</span>
                                <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : ''}</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-600">
                                ${formatDateAR(c.fecha_uso || c.fecha_cobro)}
                            </td>
                            <td class="px-4 py-3 font-black text-blue-900 text-sm">
                                ${formatARS(c.monto)}
                            </td>
                            <td class="px-4 py-3">
                                <span class="bg-blue-100 text-blue-900 font-bold px-2.5 py-1 rounded-full text-[10px] inline-flex items-center gap-1 shadow-sm border border-blue-200">
                                    <i class="fa-solid fa-check-double text-blue-600"></i> Debitado en Banco
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <div class="flex items-center justify-end gap-1.5">
                                    <button onclick="deleteCheque('${c.id}')" class="text-rose-400 hover:text-rose-600 p-1.5 rounded-lg transition-all text-xs" title="Eliminar registro">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }

                if (isRebotadoPendiente) {
                    const isRepresentacion = st.includes('re-presentación');
                    return `
                        <tr class="bg-rose-50/50 border-b border-rose-200 hover:bg-rose-100/50 transition-all text-xs">
                            <td class="px-4 py-3 font-bold text-rose-950">${c.id}</td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-800 block">${c.tipo}</span>
                                <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : ''} (${c.banco || '-'})</span>
                            </td>
                            <td class="px-4 py-3 font-bold text-slate-800">
                                ${c.cliente || '-'}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-semibold text-rose-900 block">${c.destino || 'Gestión de Cobro'}</span>
                                <span class="text-[11px] text-slate-600 italic block">${c.observaciones || ''}</span>
                            </td>
                            <td class="px-4 py-3 text-slate-600">
                                ${formatDateAR(c.fecha_uso)}
                            </td>
                            <td class="px-4 py-3 font-black text-rose-700 text-sm">
                                ${formatARS(c.monto)}
                            </td>
                            <td class="px-4 py-3">
                                ${isRepresentacion ? `
                                    <span class="bg-amber-100 text-amber-900 font-bold px-2.5 py-1 rounded-full text-[10px] inline-flex items-center gap-1 shadow-sm border border-amber-200">
                                        <i class="fa-solid fa-clock text-amber-600"></i> En Re-presentación
                                    </span>
                                ` : `
                                    <span class="bg-rose-100 text-rose-900 font-bold px-2.5 py-1 rounded-full text-[10px] inline-flex items-center gap-1 shadow-sm border border-rose-200">
                                        <i class="fa-solid fa-triangle-exclamation text-rose-600"></i> Rechazado - Pendiente
                                    </span>
                                `}
                            </td>
                            <td class="px-4 py-3 text-right">
                                <div class="flex items-center justify-end gap-1.5 flex-wrap">
                                    <button onclick="openRegularizarChequeModal('${c.id}')" class="bg-slate-800 hover:bg-slate-900 text-white font-bold px-2 py-1 rounded-lg transition-all text-[11px] flex items-center gap-1 shadow cursor-pointer" title="Registrar cobro en efectivo, transferencia o nuevo cheque">
                                        <i class="fa-solid fa-hand-holding-dollar"></i> Regularizar
                                    </button>
                                    ${isRepresentacion ? `
                                        <button onclick="acreditarSegundaVuelta('${c.id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2 py-1 rounded-lg transition-all text-[11px] flex items-center gap-1 shadow cursor-pointer" title="Marcar como acreditado/cobrado exitosamente en 2° intento">
                                            <i class="fa-solid fa-circle-check"></i> Acreditar (2° Intento)
                                        </button>
                                    ` : `
                                        <button onclick="representarCheque('${c.id}')" class="bg-amber-500 hover:bg-amber-600 text-white font-bold px-2 py-1 rounded-lg transition-all text-[11px] flex items-center gap-1 cursor-pointer" title="Re-presentar al banco">
                                            <i class="fa-solid fa-rotate-right"></i> Re-presentar
                                        </button>
                                    `}
                                    <button onclick="marcarIncobrableCheque('${c.id}')" class="bg-rose-700 hover:bg-rose-800 text-white font-bold px-2 py-1 rounded-lg transition-all text-[11px] flex items-center gap-1 cursor-pointer" title="Marcar como incobrable">
                                        <i class="fa-solid fa-ban"></i> Incobrable
                                    </button>
                                    <button onclick="restaurarChequeDisponible('${c.id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2 py-1 rounded-lg transition-all text-[11px] flex items-center gap-1 shadow cursor-pointer" title="Restaurar cheque a Disponible en Cartera">
                                        <i class="fa-solid fa-arrow-rotate-left"></i> A Cartera
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                } else if (isRegularizado) {
                    return `
                        <tr class="bg-emerald-50/40 border-b border-emerald-100 hover:bg-emerald-50/80 transition-all text-xs">
                            <td class="px-4 py-3 font-bold text-emerald-950">${c.id}</td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-800 block">${c.tipo}</span>
                                <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : ''} (${c.banco || '-'})</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-800">
                                ${c.cliente || '-'}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-emerald-800 block">${c.estado}</span>
                                <span class="text-[11px] text-slate-600 block">${c.observaciones || ''}</span>
                            </td>
                            <td class="px-4 py-3 text-slate-600">
                                ${formatDateAR(c.fecha_uso)}
                            </td>
                            <td class="px-4 py-3 font-black text-emerald-800 text-sm">
                                ${formatARS(c.monto)}
                            </td>
                            <td class="px-4 py-3">
                                <span class="bg-emerald-100 text-emerald-900 font-bold px-2.5 py-1 rounded-full text-[10px] inline-flex items-center gap-1 shadow-sm">
                                    <i class="fa-solid fa-circle-check text-emerald-600"></i> ${c.estado}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <span class="text-[11px] text-emerald-700 font-bold">✓ Saldado</span>
                            </td>
                        </tr>
                    `;
                } else if (isAnulado) {
                    return `
                        <tr class="bg-slate-100/80 text-slate-400 border-b border-slate-200 opacity-70 transition-all select-none text-xs">
                            <td class="px-4 py-3 font-bold text-slate-500 line-through">${c.id}</td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-500 block line-through">${c.tipo}</span>
                                <span class="text-[11px] text-slate-400 font-mono">${c.nro_cheque ? 'N° ' + c.nro_cheque : ''} (${c.banco || '-'})</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-500 line-through">
                                ${c.cliente || '-'}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-500 block line-through">${c.destino || '-'}</span>
                                <span class="text-[10px] text-rose-700 font-semibold block">${c.observaciones || ''}</span>
                            </td>
                            <td class="px-4 py-3 text-slate-400">
                                ${formatDateAR(c.fecha_uso)}
                            </td>
                            <td class="px-4 py-3 font-bold text-slate-400 text-sm line-through">
                                ${formatARS(c.monto)} <span class="text-[10px] font-normal text-rose-600 block">(No suma $0.00)</span>
                            </td>
                            <td class="px-4 py-3">
                                <span class="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded-full text-[10px] inline-flex items-center gap-1 shadow-sm">
                                    <i class="fa-solid fa-ban text-rose-600"></i> ${c.estado}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <span class="text-[11px] text-slate-400 font-semibold italic">Deshabilitado</span>
                            </td>
                        </tr>
                    `;
                } else {
                    return `
                        <tr class="hover:bg-slate-50 transition-all border-b border-slate-100 bg-slate-50/50 text-xs">
                            <td class="px-4 py-3 font-bold text-navy">${c.id}</td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-slate-800 block">${c.tipo}</span>
                                <span class="text-[11px] text-slate-500">${c.nro_cheque ? 'N° ' + c.nro_cheque : ''} (${c.banco || '-'})</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-700">
                                ${c.cliente || '-'}
                            </td>
                            <td class="px-4 py-3">
                                <span class="font-bold text-purple-900 block">${c.destino || '-'}</span>
                            </td>
                            <td class="px-4 py-3 font-medium text-slate-600">
                                ${formatDateAR(c.fecha_uso)}
                            </td>
                            <td class="px-4 py-3 font-black text-purple-900 text-sm">
                                ${formatARS(c.monto)}
                            </td>
                            <td class="px-4 py-3">
                                <span class="bg-purple-100 text-purple-800 font-bold px-2 py-0.5 rounded-full text-[10px]">
                                    🟣 Usado
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <div class="flex items-center justify-end gap-1.5">
                                    <button onclick="openRevertirChequeModal('${c.id}')" class="bg-rose-100 hover:bg-rose-200 text-rose-900 font-bold px-2.5 py-1.5 rounded-lg transition-all text-xs flex items-center gap-1 cursor-pointer" title="Anular/Rebotar cheque o regresar a disponible">
                                        <i class="fa-solid fa-rotate-left"></i> Revertir / Anular
                                    </button>
                                    <button onclick="deleteCheque('${c.id}')" class="text-rose-400 hover:text-rose-600 p-1.5 rounded-lg transition-all text-xs" title="Eliminar registro">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }
            }).join('');
            }, 10);
        }
    }
}

function filterChequesTables(delay = 180, isDropdown = false) {
    resetTablePaginationPage('cheques_disp');
    resetTablePaginationPage('cheques_usados');
    const rawSearch = (document.getElementById('search-cheques')?.value || '').trim();
    const isNowActive = rawSearch.length >= 3;

    if (!isDropdown && !isNowActive && !lastChequesQueryActive && rawSearch.length > 0) {
        return;
    }

    if (chequesFilterDebounceTimer) {
        clearTimeout(chequesFilterDebounceTimer);
    }

    if (delay > 0) {
        showChequesLoaders();
    }
    lastChequesQueryActive = isNowActive;

    chequesFilterDebounceTimer = setTimeout(() => {
        renderChequesTables();
    }, delay);
}

function resetChequesFilters() {
    resetTablePaginationPage('cheques_disp');
    resetTablePaginationPage('cheques_usados');
    const s = document.getElementById('search-cheques');
    const t = document.getElementById('filter-chq-tipo');
    const o = document.getElementById('filter-chq-origen');
    if (s) s.value = '';
    if (t) t.value = '';
    if (o) o.value = '';
    lastChequesQueryActive = false;
    filterChequesTables(120, true);
}

function editCheque(cid) {
    const c = globalChequesData.find(x => x.id === cid);
    if (!c) return;

    document.getElementById('chq-id-edit').value = c.id;
    document.getElementById('chq-tipo').value = c.tipo || 'Cheque Físico';
    document.getElementById('chq-monto').value = c.monto || '';
    document.getElementById('chq-banco').value = c.banco || '';
    document.getElementById('chq-nro').value = c.nro_cheque || '';
    document.getElementById('chq-cliente').value = c.cliente || '';
    document.getElementById('chq-fecha-cobro').value = c.fecha_cobro || '';
    document.getElementById('chq-endosado').value = c.endosado || 'ECONCATIVO S.A.S.';
    document.getElementById('chq-observaciones').value = c.observaciones || '';

    openModal('modal-cheque-edit');
}

async function submitChequeEdit(e) {
    e.preventDefault();
    const cid = document.getElementById('chq-id-edit').value;
    const payload = {
        id: cid,
        tipo: document.getElementById('chq-tipo').value,
        monto: parseFloat(document.getElementById('chq-monto').value) || 0,
        banco: document.getElementById('chq-banco').value,
        nro_cheque: document.getElementById('chq-nro').value,
        cliente: document.getElementById('chq-cliente').value,
        fecha_cobro: document.getElementById('chq-fecha-cobro').value,
        endosado: document.getElementById('chq-endosado').value,
        observaciones: document.getElementById('chq-observaciones').value
    };

    try {
        const res = await fetch('/api/cheques/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cheque-edit');
            await loadChequesData();
            showToast("Datos de cheque actualizados correctamente.");
        } else {
            showToast("Error al actualizar cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al guardar cheque:", err);
        showToast("Error de conexión al guardar cheque.", "error");
    }
}

function openUsarChequeModal(cid) {
    const c = globalChequesData.find(x => x.id === cid);
    if (!c) return;

    document.getElementById('chq-id-usar').value = c.id;
    document.getElementById('usar-chq-id-lbl').innerText = `${c.id} (${c.tipo} N° ${c.nro_cheque || '-'})`;
    document.getElementById('usar-chq-monto-lbl').innerText = formatARS(c.monto);
    document.getElementById('usar-chq-fecha').value = new Date().toISOString().split('T')[0];
    document.getElementById('usar-chq-concepto').value = `Uso / Endoso de ${c.tipo} N° ${c.nro_cheque || c.id}`;

    // Populate recipient dropdown grouped by Maestros categories (excluding vehicles/unidades)
    const provSel = document.getElementById('usar-chq-proveedor');
    if (provSel) {
        const provs = masterLists.proveedores || [];
        const clis = masterLists.clientes || [];
        const emps = currentMasterEmpleados || masterLists.empleados || [];

        let html = `<option value="">Seleccionar Destinatario (Maestros)...</option>`;
        
        if (provs.length) {
            html += `<optgroup label="🏢 Proveedores">`;
            html += provs.map(p => {
                const nombre = typeof p === 'object' ? (getRowProp(p, ['Razón social / Nombre', 'Razón social', 'Nombre', 'razon_social', 'nombre']) || p.razon_social || p.nombre || '') : p;
                const cuit = typeof p === 'object' ? (getRowProp(p, ['CUIT / CUIL', 'CUIT', 'cuit']) || p.cuit || '') : '';
                return `<option value="Proveedor: ${nombre}">${nombre}${cuit ? ' (CUIT: ' + cuit + ')' : ''}</option>`;
            }).join('');
            html += `</optgroup>`;
        }

        if (clis.length) {
            html += `<optgroup label="🧑‍💼 Clientes">`;
            html += clis.map(c => {
                const nombre = typeof c === 'object' ? (getRowProp(c, ['Razón social / Nombre', 'Nombre', 'razon_social', 'nombre']) || c.razon_social || c.nombre || '') : c;
                const cuit = typeof c === 'object' ? (getRowProp(c, ['CUIT / CUIL', 'CUIT', 'cuit']) || c.cuit || '') : (masterLists.clientes_dict && masterLists.clientes_dict[c] ? masterLists.clientes_dict[c].cuit : '');
                return `<option value="Cliente: ${nombre}">${nombre}${cuit ? ' (CUIT: ' + cuit + ')' : ''}</option>`;
            }).join('');
            html += `</optgroup>`;
        }

        if (emps.length) {
            html += `<optgroup label="👷 Empleados / Personal">`;
            html += emps.map(e => {
                const nombre = typeof e === 'object' ? (getRowProp(e, ['Apellido y nombre', 'Empleado', 'Nombre', 'nombre']) || e.nombre || e.nombre_completo || '') : e;
                const doc = typeof e === 'object' ? (getRowProp(e, ['CUIL / DNI', 'DNI', 'CUIL', 'dni', 'cuil']) || e.dni || e.cuil || '') : '';
                return `<option value="Empleado: ${nombre}">${nombre}${doc ? ' (DNI/CUIL: ' + doc + ')' : ''}</option>`;
            }).join('');
            html += `</optgroup>`;
        }

        provSel.innerHTML = html;
    }

    openModal('modal-cheque-usar');
}

async function submitUsarCheque(e) {
    e.preventDefault();
    const cid = document.getElementById('chq-id-usar').value;
    const destinatario = document.getElementById('usar-chq-proveedor').value;
    const fecha = document.getElementById('usar-chq-fecha').value;
    const concepto = document.getElementById('usar-chq-concepto').value;

    if (!destinatario) {
        showToast("Selecciona un destinatario de las categorías de Maestros.", "error");
        return;
    }

    const payload = {
        id: cid,
        destino: destinatario,
        proveedor: destinatario,
        fecha_uso: fecha,
        concepto: concepto
    };

    try {
        const res = await fetch('/api/cheques/usar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cheque-usar');
            await loadChequesData();
            await loadEgresosData();
            await loadDashboardData();
            showToast(`¡Cheque ${cid} asignado a ${destinatario} y registrado automáticamente en Egresos!`);
        } else {
            showToast("Error al registrar uso de cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al usar cheque:", err);
        showToast("Error al conectar con el servidor.", "error");
    }
}

function toggleRevMotivoOptions() {
    const accion = document.querySelector('input[name="rev-accion"]:checked')?.value;
    const container = document.getElementById('rev-motivos-container');
    if (container) {
        if (accion === 'disponible') {
            container.classList.add('hidden');
        } else {
            container.classList.remove('hidden');
        }
    }
}

function openRevertirChequeModal(cid) {
    const c = globalChequesData.find(x => x.id === cid);
    if (!c) return;

    document.getElementById('rev-chq-id').value = c.id;
    document.getElementById('rev-chq-lbl').innerText = `${c.id} (${c.tipo} N° ${c.nro_cheque || '-'}) por ${formatARS(c.monto)}`;
    document.getElementById('rev-chq-obs').value = '';
    
    const radioRech = document.querySelector('input[name="rev-accion"][value="rechazado_pendiente"]');
    if (radioRech) radioRech.checked = true;
    toggleRevMotivoOptions();

    openModal('modal-cheque-revertir');
}

async function submitRevertirCheque(e) {
    e.preventDefault();
    const cid = document.getElementById('rev-chq-id').value;
    const accion = document.querySelector('input[name="rev-accion"]:checked')?.value || 'rechazado_pendiente';
    const motivoSelect = document.getElementById('rev-chq-motivo').value;
    const obs = document.getElementById('rev-chq-obs').value;

    const fullMotivo = accion !== 'disponible' ? `${motivoSelect}${obs ? ' - ' + obs : ''}` : 'Error de Carga / Reversión Manual a Disponible';

    const payload = {
        id: cid,
        accion: accion,
        motivo: fullMotivo
    };

    try {
        const res = await fetch('/api/cheques/revertir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cheque-revertir');
            await loadChequesData();
            await loadDashboardData();
            if (accion === 'disponible') {
                showToast(`Cheque ${cid} revertido a Disponible en cartera activa.`);
            } else {
                showToast(`Estado del cheque ${cid} actualizado a '${json.estado}'.`);
            }
        } else {
            showToast("Error al revertir cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al revertir cheque:", err);
        showToast("Error de conexión con el servidor.", "error");
    }
}

function openRegularizarChequeModal(cid) {
    const c = globalChequesData.find(x => x.id === cid);
    if (!c) return;

    document.getElementById('reg-chq-id').value = c.id;
    document.getElementById('reg-chq-lbl').innerText = `${c.id} (${c.tipo} N° ${c.nro_cheque || '-'}) por ${formatARS(c.monto)} - Emisor: ${c.cliente || 'Cliente'}`;
    document.getElementById('reg-fecha').value = new Date().toISOString().split('T')[0];
    document.getElementById('reg-monto').value = c.monto || 0;
    document.getElementById('reg-concepto').value = `Regularización de Cheque Rebotado ${c.id} (${c.cliente || ''})`;
    document.getElementById('reg-obs').value = '';
    document.getElementById('reg-metodo').value = 'transferencia';
    toggleRegNuevoChequeFields();

    openModal('modal-cheque-regularizar');
}

function toggleRegNuevoChequeFields() {
    const metodo = document.getElementById('reg-metodo')?.value;
    const container = document.getElementById('reg-nuevo-cheque-container');
    if (container) {
        if (metodo === 'nuevo_cheque') {
            container.classList.remove('hidden');
        } else {
            container.classList.add('hidden');
        }
    }
}

async function submitRegularizarCheque(e) {
    e.preventDefault();
    const cid = document.getElementById('reg-chq-id').value;
    const payload = {
        id: cid,
        metodo: document.getElementById('reg-metodo').value,
        fecha: document.getElementById('reg-fecha').value,
        monto: parseFloat(document.getElementById('reg-monto').value) || 0,
        concepto: document.getElementById('reg-concepto').value,
        tipo_nuevo: document.getElementById('reg-nuevo-tipo').value,
        banco_nuevo: document.getElementById('reg-nuevo-banco').value,
        nro_nuevo: document.getElementById('reg-nuevo-nro').value,
        vencimiento_nuevo: document.getElementById('reg-nuevo-vencimiento').value,
        observaciones: document.getElementById('reg-obs').value
    };

    try {
        const res = await fetch('/api/cheques/regularizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-cheque-regularizar');
            await loadChequesData();
            await loadIngresosData();
            await loadDashboardData();
            showToast(`Cheque ${cid} regularizado con éxito (${json.estado}).`);
        } else {
            showToast("Error al regularizar cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al regularizar cheque:", err);
        showToast("Error de conexión con el servidor.", "error");
    }
}



async function representarCheque(cid) {
    const confirmed = await showConfirmModal(
        "Re-presentar Cheque",
        `¿Confirmas re-presentar el cheque <b>${cid}</b> al banco para un segundo intento de cobro?`,
        {
            iconClass: "fa-solid fa-rotate-right text-amber-500 text-3xl",
            confirmText: "Sí, Re-presentar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-amber-500 hover:bg-amber-600 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/cheques/representar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            showToast(`Cheque ${cid} marcado como 'En Re-presentación Bancaria'.`);
        } else {
            showToast("Error: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error al conectar con el servidor.", "error");
    }
}

async function acreditarSegundaVuelta(cid) {
    const confirmed = await showConfirmModal(
        "Acreditar Cheque en 2° Intento",
        `¿Confirmas que el cheque <b>${cid}</b> fue cobrado/acreditado exitosamente en el segundo intento de depósito bancario?`,
        {
            iconClass: "fa-solid fa-circle-check text-emerald-600 text-3xl",
            confirmText: "Sí, Acreditar Cobro",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/cheques/regularizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cid, metodo: 'acreditado', concepto: `Acreditación exitosa en 2° intento de re-presentación del cheque ${cid}` })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            showToast(`Cheque ${cid} acreditado y cobrado exitosamente en 2° intento.`);
        } else {
            showToast("Error: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error al conectar con el servidor.", "error");
    }
}

async function marcarIncobrableCheque(cid) {
    const confirmed = await showConfirmModal(
        "Marcar como Incobrable",
        `¿Estás seguro de marcar el cheque <b>${cid}</b> como Anulado / Incobrable?`,
        {
            iconClass: "fa-solid fa-ban text-rose-500 text-3xl",
            confirmText: "Marcar Incobrable",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-700 hover:bg-rose-800 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/cheques/incobrable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            showToast(`Cheque ${cid} registrado como Anulado / Incobrable.`, "error");
        } else {
            showToast("Error: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error al conectar con el servidor.", "error");
    }
}

async function restaurarChequeDisponible(cid) {
    const confirmed = await showConfirmModal(
        "Restaurar Cheque a Cartera",
        `¿Deseas restaurar el cheque <b>${cid}</b> a <b>Disponible</b> en cartera?`,
        {
            iconClass: "fa-solid fa-rotate-left text-emerald-500 text-3xl",
            confirmText: "Restaurar a Disponible",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/cheques/revertir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: cid,
                accion: 'disponible',
                motivo: 'Restaurado a Cartera Disponible'
            })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            showToast(`Cheque ${cid} restaurado a Disponible en Cartera.`, "success");
        } else {
            showToast("Error: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error al conectar con el servidor.", "error");
    }
}

async function deleteCheque(cid) {
    const confirmed = await showConfirmModal(
        "Eliminar Cheque",
        `¿Estás seguro de eliminar el cheque <b>${cid}</b> de la cartera?`,
        {
            iconClass: "fa-solid fa-trash-can text-rose-500 text-3xl",
            confirmText: "Sí, Eliminar",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;
    showLoading("Eliminando Cheque", `Eliminando ${cid} de la base de datos...`);
    try {
        const res = await fetch('/api/cheques/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            await loadEgresosData();
            await loadDashboardData();
            showToast(`Cheque ${cid} eliminado.`);
        } else {
            showToast("Error al eliminar cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        showToast("Error de conexión al eliminar cheque.", "error");
    } finally {
        hideLoading();
    }
}

// EMISIÓN & MANEJO DE CHEQUES PROPIOS (CHEQUERA)
function openModalEmitirChequePropio() {
    const today = new Date().toISOString().split('T')[0];
    if (document.getElementById('chqp-fecha-emision')) document.getElementById('chqp-fecha-emision').value = today;
    if (document.getElementById('chqp-fecha-cobro')) document.getElementById('chqp-fecha-cobro').value = today;
    if (document.getElementById('chqp-monto')) document.getElementById('chqp-monto').value = '';
    if (document.getElementById('chqp-nro')) document.getElementById('chqp-nro').value = '';
    if (document.getElementById('chqp-concepto')) document.getElementById('chqp-concepto').value = '';
    if (document.getElementById('chqp-obs')) document.getElementById('chqp-obs').value = '';

    // Poblar selector de Bancos de Tesorería
    const bancoSel = document.getElementById('chqp-banco');
    if (bancoSel) {
        const allAccs = (window.masterLists && window.masterLists.cuentas_tesoreria && window.masterLists.cuentas_tesoreria.length)
            ? window.masterLists.cuentas_tesoreria
            : ((typeof currentTesoreriaAccounts !== 'undefined' && currentTesoreriaAccounts.length) ? currentTesoreriaAccounts : []);
        const bankAccounts = allAccs.filter(a => a.tipo === 'Banco' || a.tipo === 'Billetera');
        if (bankAccounts.length > 0) {
            bancoSel.innerHTML = bankAccounts.map(a => `<option value="${a.nombre}">${a.nombre}</option>`).join('');
        }
    }

    openModal('modal-emitir-cheque-propio');
}

async function submitEmitirChequePropio(e) {
    if (e) e.preventDefault();
    const payload = {
        banco: document.getElementById('chqp-banco')?.value || '',
        tipo: document.getElementById('chqp-tipo')?.value || 'Cheque Físico',
        nro_cheque: document.getElementById('chqp-nro')?.value || '',
        monto: parseFloat(document.getElementById('chqp-monto')?.value) || 0,
        fecha_emision: document.getElementById('chqp-fecha-emision')?.value || '',
        fecha_cobro: document.getElementById('chqp-fecha-cobro')?.value || '',
        estado: 'Disponible',
        concepto: document.getElementById('chqp-concepto')?.value || 'Cheque Propio en Chequera',
        observaciones: document.getElementById('chqp-obs')?.value || ''
    };

    if (!payload.banco || !payload.monto || payload.monto <= 0) {
        showToast("Seleccione el banco emisor y especifique un monto válido.", "error");
        return;
    }

    try {
        const res = await fetch('/api/cheques/emitir_propio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal('modal-emitir-cheque-propio');
            await loadChequesData();
            await loadTesoreriaData();
            await loadDashboardData();
            showToast(`¡Cheque propio ${json.id} creado en Cheques Disponibles por ${formatARS(json.monto)}!`);
        } else {
            showToast("Error al emitir cheque: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al emitir cheque propio:", err);
        showToast("Error de conexión al emitir cheque propio.", "error");
    }
}

async function marcarChequePropioDebitado(cid) {
    const confirmed = await showConfirmModal(
        "Debitar Cheque Propio",
        `¿Confirmar que el cheque propio <b>${cid}</b> ha sido debitado/cobrado de la cuenta bancaria?`,
        {
            iconClass: "fa-solid fa-check-double text-blue-600 text-3xl",
            confirmText: "Sí, Marcar Debitado",
            confirmBtnClass: "px-5 py-2.5 rounded-xl text-white font-bold bg-blue-600 hover:bg-blue-700 shadow-md transition-all cursor-pointer text-sm"
        }
    );
    if (!confirmed) return;

    try {
        const res = await fetch('/api/cheques/marcar_debitado', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cheque_id: cid })
        });
        const json = await res.json();
        if (json.status === 'success') {
            await loadChequesData();
            await loadTesoreriaData();
            await loadDashboardData();
            showToast(`Cheque ${cid} marcado como debitado. Se actualizó el saldo en Tesorería.`);
        } else {
            showToast("Error al marcar como debitado: " + (json.message || 'Error desconocido'), "error");
        }
    } catch (err) {
        console.error("Error al debitar cheque propio:", err);
        showToast("Error de conexión al procesar el débito.", "error");
    }
}

