/**
 * ECONCATIVO - Core State, Helpers & Global Utilities
 */

// Interceptor global para redirección automática si la sesión expira (401)
if (!window._fetchInterceptorInstalled) {
    window._fetchInterceptorInstalled = true;
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        try {
            const response = await originalFetch.apply(this, args);
            if (response.status === 401 && !window.location.pathname.startsWith('/login')) {
                window.location.href = '/login?expired=1';
            }
            return response;
        } catch (err) {
            throw err;
        }
    };
}

// Global State
let chartMonthly = null;
let chartExpenses = null;
let chartPayments = null;
let chartActivities = null;
let chartTopClients = null;
let chartUnitFuel = null;
let chartChequesStatus = null;
let masterLists = {};
try {
    Object.defineProperty(window, 'masterLists', {
        get() { return masterLists; },
        set(val) { masterLists = val; },
        configurable: true
    });
} catch(e) {
    window.masterLists = masterLists;
}
let currentPresupuestos = [];
let currentViajes = [];
let currentFacturacion = [];
let currentIngresos = [];
let currentMasterTab = 'clientes';
let currentMasterClientes = [];
let currentMasterUnidades = [];
let currentMasterEmpleados = [];
let currentMasterProveedores = [];
let currentLiquidacionesData = [];
let currentTabLiquidacionesData = [];
let currentHistorialLiquidacionesData = [];
let currentQuincenaFilter = 'q1';
let currentEgresosData = [];

// Helper for robust property retrieval from sheet rows
function getRowProp(row, possibleKeys) {
    if (!row) return '';
    const rowKeys = Object.keys(row);
    for (let k of possibleKeys) {
        if (row[k] !== undefined && row[k] !== null && str(row[k]).trim() !== '') return row[k];
        const match = rowKeys.find(rk => rk.toLowerCase().replace(/[^a-z0-9]/g, '') === k.toLowerCase().replace(/[^a-z0-9]/g, ''));
        if (match && row[match] !== undefined && row[match] !== null && str(row[match]).trim() !== '') return row[match];
    }
    return '';
}

// Format dates to Argentine convention DD/MM/AAAA
function formatDateAR(dateVal) {
    if (!dateVal || String(dateVal).trim() === '' || dateVal === '-') return '-';
    if (dateVal instanceof Date) {
        if (isNaN(dateVal.getTime())) return '-';
        const d = String(dateVal.getDate()).padStart(2, '0');
        const m = String(dateVal.getMonth() + 1).padStart(2, '0');
        const y = dateVal.getFullYear();
        return `${d}/${m}/${y}`;
    }
    let s = String(dateVal).trim();
    if (['none', 'null', 'undefined'].includes(s.toLowerCase())) return '-';
    if (s.includes('T')) s = s.split('T')[0];
    if (s.includes(' ')) s = s.split(' ')[0];

    // YYYY-MM-DD or YYYY/MM/DD
    const ymd = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (ymd) {
        return `${ymd[3].padStart(2, '0')}/${ymd[2].padStart(2, '0')}/${ymd[1]}`;
    }

    // DD-MM-YYYY or DD/MM/YYYY
    const dmy = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (dmy) {
        return `${dmy[1].padStart(2, '0')}/${dmy[2].padStart(2, '0')}/${dmy[3]}`;
    }

    const d = new Date(dateVal);
    if (!isNaN(d.getTime())) {
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        if (year > 1900 && year < 2100) {
            return `${day}/${month}/${year}`;
        }
    }
    return s;
}

// Format date and time to Argentine convention DD/MM/AAAA HH:mm (UTC-3)
function formatDateTimeAR(dateVal) {
    if (!dateVal || String(dateVal).trim() === '' || dateVal === '-') return '-';
    let s = String(dateVal).trim();
    if (s.toLowerCase() === 'none' || s.toLowerCase() === 'null') return '-';

    // Already in DD/MM/AAAA HH:mm:ss -> remove seconds
    const dmyWithSec = s.match(/^(\d{1,2}\/\d{1,2}\/\d{4}\s+\d{1,2}:\d{1,2})(:\d{1,2})?$/);
    if (dmyWithSec) {
        return dmyWithSec[1];
    }
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(s)) {
        return s;
    }

    // YYYY-MM-DD or YYYY-MM-DD HH:mm:ss
    const ymd = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})([ T](\d{1,2}):(\d{1,2})(:(\d{1,2}))?)?/);
    if (ymd) {
        const isoStr = s.includes('Z') || s.includes('+') ? s : s.replace(' ', 'T') + 'Z';
        const d = new Date(isoStr);
        if (!isNaN(d.getTime())) {
            const parts = d.toLocaleString('es-AR', {
                timeZone: 'America/Argentina/Buenos_Aires',
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            });
            return parts.replace(',', '');
        }
        const timePart = ymd[5] ? ` ${ymd[5].padStart(2, '0')}:${ymd[6].padStart(2, '0')}` : '';
        return `${ymd[3].padStart(2, '0')}/${ymd[2].padStart(2, '0')}/${ymd[1]}${timePart}`;
    }

    const d = new Date(dateVal);
    if (!isNaN(d.getTime())) {
        const parts = d.toLocaleString('es-AR', {
            timeZone: 'America/Argentina/Buenos_Aires',
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
        return parts.replace(',', '');
    }

    return s;
}

// Parse date string into timestamp for accurate numerical sorting
function parseDateForSort(dateVal) {
    if (!dateVal || String(dateVal).trim() === '' || dateVal === '-') return -Infinity;
    if (dateVal instanceof Date) {
        return isNaN(dateVal.getTime()) ? -Infinity : dateVal.getTime();
    }
    let s = String(dateVal).trim();
    if (s.includes('T')) s = s.split('T')[0];
    if (s.includes(' ')) s = s.split(' ')[0];

    const ymd = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (ymd) {
        return new Date(parseInt(ymd[1], 10), parseInt(ymd[2], 10) - 1, parseInt(ymd[3], 10)).getTime() || -Infinity;
    }

    const dmy = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (dmy) {
        return new Date(parseInt(dmy[3], 10), parseInt(dmy[2], 10) - 1, parseInt(dmy[1], 10)).getTime() || -Infinity;
    }

    const d = new Date(dateVal);
    if (!isNaN(d.getTime())) {
        return d.getTime();
    }
    return -Infinity;
}

// Sort an array of records by date descending (most recent first), with secondary sort by ID descending
function sortRecordsMostRecent(list, dateProps = ['Fecha'], idProps = ['ID']) {
    if (!Array.isArray(list)) return [];
    return list.slice().sort((a, b) => {
        const valDateA = (typeof getRowProp === 'function') ? getRowProp(a, dateProps) : (a[dateProps[0]] || '');
        const valDateB = (typeof getRowProp === 'function') ? getRowProp(b, dateProps) : (b[dateProps[0]] || '');
        const tsA = parseDateForSort(valDateA);
        const tsB = parseDateForSort(valDateB);
        if (tsB !== tsA) {
            return tsB - tsA;
        }
        let idA = (typeof getRowProp === 'function') ? getRowProp(a, idProps) : (a[idProps[0]] || '');
        let idB = (typeof getRowProp === 'function') ? getRowProp(b, idProps) : (b[idProps[0]] || '');
        if (!idA && a && a.id) idA = a.id;
        if (!idB && b && b.id) idB = b.id;
        return String(idB).localeCompare(String(idA), undefined, { numeric: true });
    });
}

// Format expiration dates with visual alerts (Al día / Por vencer / VENCIDO)
function formatExpirationBadge(dateStr) {
    if (!dateStr || str(dateStr).trim() === '' || dateStr === '-') return `<span class="text-slate-400 font-normal">-</span>`;
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let expDate = null;
    const cleanStr = str(dateStr).trim();
    if (cleanStr.includes('/')) {
        const dparts = cleanStr.split('/');
        if (dparts.length === 3) {
            expDate = new Date(parseInt(dparts[2], 10), parseInt(dparts[1], 10) - 1, parseInt(dparts[0], 10));
        }
    } else {
        const parts = cleanStr.split('-');
        if (parts.length === 3) {
            expDate = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        } else {
            expDate = new Date(cleanStr);
        }
    }

    if (!expDate || isNaN(expDate.getTime())) {
        return `<span class="text-slate-600">${formatDateAR(dateStr)}</span>`;
    }

    const diffDays = Math.ceil((expDate - today) / (1000 * 60 * 60 * 24));
    const formattedStr = formatDateAR(expDate);

    if (diffDays < 0) {
        return `<span class="bg-rose-600 text-white font-bold px-2 py-0.5 rounded text-[10px] shadow-sm inline-flex items-center gap-1 uppercase" title="Documentación VENCIDA"><i class="fa-solid fa-triangle-exclamation"></i> VENCIDO (${formattedStr})</span>`;
    } else if (diffDays <= 30) {
        return `<span class="bg-amber-500 text-white font-bold px-2 py-0.5 rounded text-[10px] shadow-sm inline-flex items-center gap-1 uppercase" title="Próximo a vencer (menos de 30 días)"><i class="fa-solid fa-clock"></i> Vence en ${diffDays}d (${formattedStr})</span>`;
    } else {
        return `<span class="bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded text-[10px] border border-emerald-200 inline-flex items-center gap-1"><i class="fa-solid fa-circle-check"></i> Al día (${formattedStr})</span>`;
    }
}

// Format cheque collection/maturity dates with days remaining badge & visual color indicators
function formatChequeExpirationBadge(dateStr) {
    if (!dateStr || str(dateStr).trim() === '' || dateStr === '-') {
        return `<span class="bg-amber-50 text-amber-700 font-bold px-2 py-1 rounded text-[11px] border border-amber-200 inline-flex items-center gap-1"><i class="fa-solid fa-triangle-exclamation"></i> Sin fecha cobro</span>`;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const parts = str(dateStr).split('-');
    let expDate = null;
    if (parts.length === 3) {
        expDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    } else {
        expDate = new Date(dateStr);
    }

    if (!expDate || isNaN(expDate.getTime())) {
        return `<span class="text-slate-600 text-xs font-medium">${formatDateAR(dateStr)}</span>`;
    }

    const diffDays = Math.ceil((expDate - today) / (1000 * 60 * 60 * 24));
    const formattedStr = formatDateAR(expDate);

    if (diffDays < 0) {
        const absDays = Math.abs(diffDays);
        return `<span class="bg-rose-600 text-white font-bold px-2 py-1 rounded text-[11px] shadow-sm inline-flex items-center gap-1 uppercase" title="Cheque vencido hace ${absDays} días"><i class="fa-solid fa-triangle-exclamation"></i> VENCIDO (${absDays}d) - ${formattedStr}</span>`;
    } else if (diffDays === 0) {
        return `<span class="bg-rose-500 text-white font-bold px-2 py-1 rounded text-[11px] shadow-sm inline-flex items-center gap-1 uppercase animate-pulse" title="¡Este cheque vence HOY!"><i class="fa-solid fa-bell"></i> VENCE HOY (${formattedStr})</span>`;
    } else if (diffDays <= 7) {
        return `<span class="bg-amber-500 text-white font-bold px-2 py-1 rounded text-[11px] shadow-sm inline-flex items-center gap-1 uppercase" title="Próximo a vencer (en ${diffDays} días)"><i class="fa-solid fa-clock"></i> Vence en ${diffDays}d (${formattedStr})</span>`;
    } else if (diffDays <= 30) {
        return `<span class="bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold px-2 py-1 rounded text-[11px] inline-flex items-center gap-1" title="Vence el cobro en ${diffDays} días"><i class="fa-solid fa-clock text-emerald-600"></i> En ${diffDays}d (${formattedStr})</span>`;
    } else {
        return `<span class="bg-slate-100 text-slate-700 border border-slate-200 font-semibold px-2 py-1 rounded text-[11px] inline-flex items-center gap-1" title="Vence el cobro en ${diffDays} días"><i class="fa-solid fa-calendar-check text-slate-500"></i> En ${diffDays}d (${formattedStr})</span>`;
    }
}


// Toast notification replacement for invasive browser alerts
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `px-4 py-3 rounded-xl shadow-lg text-white font-medium text-xs flex items-center gap-2.5 transition-all duration-300 pointer-events-auto transform translate-y-2 opacity-0 ${type === 'success' ? 'bg-slate-900 border border-slate-800' : 'bg-rose-600'}`;
    toast.innerHTML = `<i class="${type === 'success' ? 'fa-solid fa-circle-check text-emerald-400 text-sm' : 'fa-solid fa-triangle-exclamation text-sm'}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

function formatARS(amount) {
    return new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        minimumFractionDigits: 2
    }).format(amount || 0);
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

    const targetTab = document.getElementById(`tab-${tabId}`);
    const targetNav = document.getElementById(`nav-${tabId}`);
    
    if (targetTab) targetTab.classList.remove('hidden');
    if (targetNav) targetNav.classList.add('active');

    try {
        if (tabId === 'dashboard') loadDashboardData();
        if (tabId === 'presupuestos') loadPresupuestosData();
        if (tabId === 'viajes') loadViajesData();
        if (tabId === 'facturacion') loadFacturacionData();
        if (tabId === 'ingresos') loadIngresosData();
        if (tabId === 'egresos') loadEgresosData();
        if (tabId === 'cheques') loadChequesData();
        if (tabId === 'tesoreria') loadTesoreriaData();
        if (tabId === 'cuentas_corrientes') loadCuentaCorrienteTab();
        if (tabId === 'liquidaciones') loadLiquidacionesTab();
        if (tabId === 'ordenes') loadOrdenesCompraData();
        if (tabId === 'maestros') switchMasterTab('clientes');
    } catch (err) {
        console.error(`Error al cambiar a la pestaña ${tabId}:`, err);
    }
}

async function switchQuincenaTab(newQ, eid) {
    const qSel = document.getElementById('filter-tab-liq-quincena');
    if (qSel) {
        qSel.value = newQ;
        qSel.dataset.userModified = 'true';
    }
    await loadLiquidacionesTab();
    if (eid) {
        verDesgloseLiquidacion(eid);
    }
}


function strStatusClass(status) {
    const s = str(status).toLowerCase();
    if (s.includes('cobrado') || s.includes('pagado')) return 'badge-cobrado';
    return 'badge-pendiente';
}

function str(v) { return (v || '').toString(); }

function openModal(modalId) {
    const el = document.getElementById(modalId);
    if (!el) return;

    // Adjust zIndex dynamically if other modals are currently visible
    const openModals = Array.from(document.querySelectorAll('[id^="modal-"]:not(.hidden)'))
        .filter(m => m !== el);

    if (openModals.length > 0) {
        let maxZ = 50;
        openModals.forEach(m => {
            const computedZ = parseInt(window.getComputedStyle(m).zIndex) || 50;
            if (computedZ >= maxZ) maxZ = computedZ;
        });
        el.style.zIndex = (maxZ + 10).toString();
    } else {
        el.style.zIndex = '';
    }

    el.classList.remove('hidden');

    if (modalId === 'modal-egreso') {
        if (typeof loadCustomEgresoCategorias === 'function') loadCustomEgresoCategorias();
        if (typeof onEgresoCategoriaChanged === 'function') onEgresoCategoriaChanged();
        if (typeof checkEgresoProveedorSaldoFavor === 'function') checkEgresoProveedorSaldoFavor();
    }
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) {
        el.classList.add('hidden');
        el.style.zIndex = '';
    }

    // Limpieza automática del ID de edición y formularios al cerrar el modal
    if (modalId === 'modal-unidad') {
        const idEl = document.getElementById('mu-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-unidad');
        if (form) form.reset();
        const title = document.getElementById('modal-mu-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-truck text-amber"></i> Registrar Nueva Unidad / Maquinaria`;
    } else if (modalId === 'modal-cliente') {
        const idEl = document.getElementById('mc-id');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-cliente');
        if (form) form.reset();
        const title = document.getElementById('modal-cliente-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-user-plus text-amber"></i> Registrar Nuevo Cliente`;
        if (typeof clearClienteErrors === 'function') clearClienteErrors();
    } else if (modalId === 'modal-empleado') {
        const idEl = document.getElementById('me-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-empleado');
        if (form) form.reset();
        const title = document.getElementById('modal-me-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-id-card text-amber"></i> Registrar Ficha de Personal`;
        if (typeof resetEmpleadoLicencias === 'function') resetEmpleadoLicencias();
    } else if (modalId === 'modal-proveedor') {
        const idEl = document.getElementById('mp-id');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-proveedor');
        if (form) form.reset();
        const title = document.getElementById('modal-prov-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-store text-amber"></i> Registrar Proveedor`;
    } else if (modalId === 'modal-presupuesto') {
        const idEl = document.getElementById('p-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-presupuesto');
        if (form) form.reset();
        const title = document.getElementById('modal-p-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-file-pdf text-amber"></i> Generar Nuevo Presupuesto Comercial`;
        if (typeof resetPresupuestoItems === 'function') resetPresupuestoItems('Viaje');
    } else if (modalId === 'modal-orden-compra') {
        const idEl = document.getElementById('o-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-orden-compra');
        if (form) form.reset();
        const title = document.getElementById('modal-o-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-file-circle-plus text-amber"></i> Nueva Órden de Compra`;
    } else if (modalId === 'modal-ingreso') {
        const idEl = document.getElementById('i-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-ingreso');
        if (form) form.reset();
        const title = document.getElementById('modal-i-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-file-invoice-dollar text-amber"></i> Registrar Ingreso Manual / Factura`;
        const clienteSel = document.getElementById('i-cliente');
        if (clienteSel) {
            clienteSel.disabled = false;
            clienteSel.classList.remove('bg-slate-100', 'cursor-not-allowed');
            clienteSel.classList.add('bg-slate-50');
        }
        const tag = document.getElementById('label-i-cliente-tag');
        if (tag) tag.classList.add('hidden');
        const btnNewCli = document.getElementById('btn-nuevo-cliente-ingreso');
        if (btnNewCli) btnNewCli.classList.remove('hidden');
    } else if (modalId === 'modal-viaje') {
        const idEl = document.getElementById('v-id-edit');
        if (idEl) idEl.value = '';
        const form = document.getElementById('form-viaje');
        if (form) form.reset();
        const title = document.getElementById('modal-v-title');
        if (title) title.innerHTML = `<i class="fa-solid fa-truck-moving text-amber"></i> Registrar Operación`;
    } else if (modalId === 'modal-egreso') {
        const form = document.getElementById('form-egreso');
        if (form) form.reset();
        const alertEl = document.getElementById('alert-e-fondos');
        if (alertEl) {
            alertEl.classList.add('hidden');
            alertEl.innerHTML = '';
        }
        const btnSubmit = document.getElementById('btn-submit-egreso');
        if (btnSubmit) btnSubmit.disabled = false;
    }
}


function filterTable(tableType) {
    const input = document.getElementById(`search-${tableType}`);
    if (!input) return;
    const raw = (input.value || '').trim();
    const filter = raw.length >= 3 ? raw.toLowerCase() : '';
    const tbody = document.getElementById(`tbody-${tableType}`);
    if (!tbody) return;
    const rows = tbody.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const txt = rows[i].innerText.toLowerCase();
        rows[i].style.display = (!filter || txt.includes(filter)) ? '' : 'none';
    }
}


function formatLocation(orig, dest) {
    if (orig && dest && orig !== dest) return `${orig} ➔ ${dest}`;
    return orig || dest || '-';
}


function showConfirmModal(title, message, options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('modal-confirm-dialog');
        if (!modal) {
            resolve(confirm(`${title}\n\n${message.replace(/<[^>]*>?/gm, '')}`));
            return;
        }

        const titleEl = document.getElementById('confirm-modal-title');
        const msgEl = document.getElementById('confirm-modal-message');
        if (titleEl) titleEl.textContent = title || 'Confirmar Acción';
        if (msgEl) msgEl.innerHTML = message || '¿Está seguro de realizar esta acción?';

        const iconEl = document.getElementById('confirm-modal-icon');
        if (iconEl) {
            iconEl.className = options.iconClass || 'fa-solid fa-triangle-exclamation text-amber-500 text-3xl';
        }

        let btnConfirm = document.getElementById('confirm-modal-btn-confirm');
        let btnCancel = document.getElementById('confirm-modal-btn-cancel');

        if (!btnConfirm || !btnCancel) {
            resolve(confirm(`${title}\n\n${message.replace(/<[^>]*>?/gm, '')}`));
            return;
        }

        // Clone buttons to strip any prior listeners
        const newConfirm = btnConfirm.cloneNode(true);
        const newCancel = btnCancel.cloneNode(true);
        btnConfirm.parentNode.replaceChild(newConfirm, btnConfirm);
        btnCancel.parentNode.replaceChild(newCancel, btnCancel);

        newConfirm.textContent = options.confirmText || 'Confirmar';
        newConfirm.className = options.confirmBtnClass || 'px-5 py-2.5 rounded-xl text-white font-bold bg-amber-500 hover:bg-amber-600 shadow-md transition-all cursor-pointer text-sm';

        newConfirm.onclick = () => {
            closeModal('modal-confirm-dialog');
            resolve(true);
        };

        newCancel.onclick = () => {
            closeModal('modal-confirm-dialog');
            resolve(false);
        };

        openModal('modal-confirm-dialog');
    });
}

function showPromptModal(options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('modal-prompt-dialog');
        if (!modal) {
            const fallback = window.prompt(options.message || options.title || '', options.defaultValue || '');
            resolve(fallback);
            return;
        }

        const title = options.title || 'Ingresar Información';
        const message = options.message || '';
        const placeholder = options.placeholder || '';
        const defaultValue = options.defaultValue || '';
        const label = options.label || 'Nombre *';
        const confirmText = options.confirmText || 'Guardar';
        const cancelText = options.cancelText || 'Cancelar';
        const iconClass = options.iconClass || 'fa-solid fa-tags text-rose-600 text-xl';
        const confirmBtnClass = options.confirmBtnClass || 'px-5 py-2.5 rounded-xl text-white font-bold bg-rose-600 hover:bg-rose-700 shadow-md transition-all cursor-pointer text-xs flex items-center gap-1.5';

        const titleEl = document.getElementById('prompt-modal-title');
        const msgEl = document.getElementById('prompt-modal-message');
        const labelEl = document.getElementById('prompt-modal-label');
        const iconEl = document.getElementById('prompt-modal-icon');
        const inputEl = document.getElementById('prompt-modal-input');
        const errorEl = document.getElementById('prompt-modal-error');
        const formEl = document.getElementById('form-prompt-dialog');
        const btnCancel = document.getElementById('prompt-modal-btn-cancel');
        const btnConfirm = document.getElementById('prompt-modal-btn-confirm');

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        if (labelEl) labelEl.textContent = label;
        if (iconEl) iconEl.className = iconClass;
        if (errorEl) {
            errorEl.textContent = '';
            errorEl.classList.add('hidden');
        }
        if (inputEl) {
            inputEl.value = defaultValue;
            inputEl.placeholder = placeholder;
            inputEl.classList.remove('border-rose-500', 'ring-2', 'ring-rose-200');
        }

        // Clone buttons to strip any prior listeners
        const newConfirm = btnConfirm.cloneNode(true);
        const newCancel = btnCancel.cloneNode(true);
        btnConfirm.parentNode.replaceChild(newConfirm, btnConfirm);
        btnCancel.parentNode.replaceChild(newCancel, btnCancel);

        newConfirm.innerHTML = `<i class="fa-solid fa-check"></i> ${confirmText}`;
        newConfirm.className = confirmBtnClass;
        newCancel.textContent = cancelText;

        let isClosed = false;
        const cleanup = () => {
            if (isClosed) return;
            isClosed = true;
            closeModal('modal-prompt-dialog');
            document.removeEventListener('keydown', handleKey);
            modal.onclick = null;
        };

        const handleConfirm = () => {
            const val = (inputEl ? inputEl.value : '').trim();
            if (options.required !== false && !val) {
                if (errorEl) {
                    errorEl.textContent = options.errorMessage || 'Debe ingresar un valor.';
                    errorEl.classList.remove('hidden');
                }
                if (inputEl) {
                    inputEl.classList.add('border-rose-500', 'ring-2', 'ring-rose-200');
                    inputEl.focus();
                }
                return;
            }
            cleanup();
            resolve(val);
        };

        const handleCancel = () => {
            cleanup();
            resolve(null);
        };

        const handleKey = (e) => {
            if (e.key === 'Escape') {
                handleCancel();
            }
        };

        newConfirm.onclick = (e) => {
            e.preventDefault();
            handleConfirm();
        };

        newCancel.onclick = (e) => {
            e.preventDefault();
            handleCancel();
        };

        if (formEl) {
            formEl.onsubmit = (e) => {
                e.preventDefault();
                handleConfirm();
            };
        }

        modal.onclick = (e) => {
            if (e.target === modal) {
                handleCancel();
            }
        };

        if (inputEl) {
            inputEl.oninput = () => {
                if (errorEl && !errorEl.classList.contains('hidden')) {
                    errorEl.classList.add('hidden');
                    inputEl.classList.remove('border-rose-500', 'ring-2', 'ring-rose-200');
                }
            };
        }

        document.addEventListener('keydown', handleKey);

        openModal('modal-prompt-dialog');
        setTimeout(() => {
            if (inputEl) {
                inputEl.focus();
                inputEl.select();
            }
        }, 100);
    });
}

function showLoading(title = "Procesando...", subtext = "Sincronizando con Supabase...") {
    const el = document.getElementById('global-loading-overlay');
    if (el) {
        const titleEl = document.getElementById('global-loading-title');
        const subEl = document.getElementById('global-loading-subtext');
        if (titleEl) titleEl.textContent = title;
        if (subEl) subEl.textContent = subtext;
        el.classList.remove('hidden');
        el.classList.add('flex');
    }
}

function hideLoading() {
    const el = document.getElementById('global-loading-overlay');
    if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
    }
}

// Format Argentine CUIT / CUIL: XX-XXXXXXXX-X (11 digits max)
function formatCuitCuil(value) {
    if (!value) return '';
    const digits = String(value).replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 2) {
        return digits;
    } else if (digits.length <= 10) {
        return `${digits.slice(0, 2)}-${digits.slice(2)}`;
    } else {
        return `${digits.slice(0, 2)}-${digits.slice(2, 10)}-${digits.slice(10, 11)}`;
    }
}

function attachCuitMask(inputEl) {
    if (!inputEl || inputEl._cuitMaskAttached) return;
    inputEl._cuitMaskAttached = true;
    inputEl.setAttribute('maxlength', '13');
    inputEl.setAttribute('inputmode', 'numeric');

    if (inputEl.value) {
        inputEl.value = formatCuitCuil(inputEl.value);
    }

    inputEl.addEventListener('keydown', function(e) {
        if (e.key === 'Backspace') {
            const start = this.selectionStart;
            const end = this.selectionEnd;
            if (start === end && (start === 3 || start === 12)) {
                const val = this.value;
                if (val[start - 1] === '-') {
                    e.preventDefault();
                    const nextVal = val.slice(0, start - 2) + val.slice(start);
                    this.value = formatCuitCuil(nextVal);
                    this.setSelectionRange(start - 2, start - 2);
                }
            }
        }
    });

    inputEl.addEventListener('input', function(e) {
        const prevVal = this.value;
        const prevCursor = this.selectionStart;
        const digits = prevVal.replace(/\D/g, '').slice(0, 11);
        const formatted = formatCuitCuil(digits);
        this.value = formatted;

        if (prevCursor !== null) {
            let digitsBeforeCursor = prevVal.slice(0, prevCursor).replace(/\D/g, '').length;
            let newPos = 0;
            let countedDigits = 0;
            while (newPos < formatted.length && countedDigits < digitsBeforeCursor) {
                if (/\d/.test(formatted[newPos])) {
                    countedDigits++;
                }
                newPos++;
            }
            this.setSelectionRange(newPos, newPos);
        }
    });

    inputEl.addEventListener('paste', function(e) {
        setTimeout(() => {
            const digits = this.value.replace(/\D/g, '').slice(0, 11);
            this.value = formatCuitCuil(digits);
        }, 0);
    });
}

function attachCbuMask(inputEl) {
    if (!inputEl || inputEl._cbuMaskAttached) return;
    inputEl._cbuMaskAttached = true;
    inputEl.setAttribute('maxlength', '22');
    inputEl.setAttribute('inputmode', 'numeric');

    if (inputEl.value) {
        inputEl.value = inputEl.value.replace(/\D/g, '').slice(0, 22);
    }

    inputEl.addEventListener('input', function(e) {
        const prevCursor = this.selectionStart;
        const clean = this.value.replace(/\D/g, '').slice(0, 22);
        this.value = clean;
        if (prevCursor !== null && prevCursor <= clean.length) {
            this.setSelectionRange(prevCursor, prevCursor);
        }
    });

    inputEl.addEventListener('paste', function(e) {
        setTimeout(() => {
            this.value = this.value.replace(/\D/g, '').slice(0, 22);
        }, 0);
    });
}

function attachDniMask(inputEl) {
    if (!inputEl || inputEl._dniMaskAttached) return;
    inputEl._dniMaskAttached = true;
    inputEl.setAttribute('maxlength', '8');
    inputEl.setAttribute('inputmode', 'numeric');

    if (inputEl.value) {
        inputEl.value = inputEl.value.replace(/\D/g, '').slice(0, 8);
    }

    inputEl.addEventListener('input', function(e) {
        const prevCursor = this.selectionStart;
        const clean = this.value.replace(/\D/g, '').slice(0, 8);
        this.value = clean;
        if (prevCursor !== null && prevCursor <= clean.length) {
            this.setSelectionRange(prevCursor, prevCursor);
        }
    });

    inputEl.addEventListener('paste', function(e) {
        setTimeout(() => {
            this.value = this.value.replace(/\D/g, '').slice(0, 8);
        }, 0);
    });
}

function setupGlobalInputMasks() {
    const cuitIds = ['mc-cuit', 'me-cuil', 'mp-cuit', 'p-cuit', 'nc-cuit'];
    cuitIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) attachCuitMask(el);
    });

    const cbuIds = ['me-cbu', 'nc-cbu-val'];
    cbuIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) attachCbuMask(el);
    });

    const dniIds = ['me-dni'];
    dniIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) attachDniMask(el);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupGlobalInputMasks);
} else {
    setupGlobalInputMasks();
}

// ==================== TABLE PAGINATION SYSTEM ====================
const tablePaginationState = {};
const _lastTableData = {};
const _tablePaginationRenderers = {};

function resetTablePaginationPage(tableKey) {
    if (tablePaginationState[tableKey]) {
        tablePaginationState[tableKey].page = 1;
    }
}

function paginateData(tableKey, items, defaultPageSize = 10) {
    if (!tablePaginationState[tableKey]) {
        tablePaginationState[tableKey] = {
            page: 1,
            pageSize: defaultPageSize
        };
    }
    const state = tablePaginationState[tableKey];
    const total = items ? items.length : 0;
    const totalPages = Math.max(1, Math.ceil(total / state.pageSize));

    if (state.page > totalPages) state.page = totalPages;
    if (state.page < 1) state.page = 1;

    const startIdx = (state.page - 1) * state.pageSize;
    const endIdx = Math.min(startIdx + state.pageSize, total);
    const paginatedItems = items ? items.slice(startIdx, endIdx) : [];

    return {
        paginatedItems,
        page: state.page,
        pageSize: state.pageSize,
        totalPages,
        totalItems: total,
        startIdx: total === 0 ? 0 : startIdx + 1,
        endIdx
    };
}

function getPaginationPageList(currentPage, totalPages) {
    if (totalPages <= 5) {
        return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    let start = Math.max(1, currentPage - 1);
    let end = Math.min(totalPages, currentPage + 1);
    if (currentPage <= 2) {
        start = 1;
        end = 3;
    }
    if (currentPage >= totalPages - 1) {
        start = totalPages - 2;
        end = totalPages;
    }
    const pages = [];
    if (start > 1) {
        pages.push(1);
        if (start > 2) pages.push('...');
    }
    for (let i = start; i <= end; i++) {
        pages.push(i);
    }
    if (end < totalPages) {
        if (end < totalPages - 1) pages.push('...');
        pages.push(totalPages);
    }
    return pages;
}

function renderPaginationBar(tableKey, containerId, meta) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!meta || meta.totalItems === 0) {
        container.innerHTML = '';
        return;
    }

    const pages = getPaginationPageList(meta.page, meta.totalPages);
    const prevDisabled = meta.page <= 1;
    const nextDisabled = meta.page >= meta.totalPages;

    let counterText = '';
    if (meta.totalItems <= meta.pageSize) {
        counterText = `Mostrando ${meta.totalItems} de ${meta.totalItems} resultados`;
    } else {
        counterText = `Mostrando ${meta.startIdx} a ${meta.endIdx} de ${meta.totalItems} resultados`;
    }

    const prevButton = prevDisabled
        ? `<span class="text-slate-300 select-none flex items-center gap-1 cursor-default text-xs"><i class="fa-solid fa-chevron-left text-[9px]"></i> Anterior</span>`
        : `<button type="button" onclick="changeTablePaginationPage('${tableKey}', ${meta.page - 1})" class="text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1 text-xs cursor-pointer"><i class="fa-solid fa-chevron-left text-[9px]"></i> Anterior</button>`;

    const nextButton = nextDisabled
        ? `<span class="text-slate-300 select-none flex items-center gap-1 cursor-default text-xs">Siguiente <i class="fa-solid fa-chevron-right text-[9px]"></i></span>`
        : `<button type="button" onclick="changeTablePaginationPage('${tableKey}', ${meta.page + 1})" class="text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1 text-xs cursor-pointer">Siguiente <i class="fa-solid fa-chevron-right text-[9px]"></i></button>`;

    const pagesHtml = pages.map(p => {
        if (p === '...') {
            return `<span class="px-1 text-slate-400 select-none font-medium">...</span>`;
        }
        const isActive = p === meta.page;
        if (isActive) {
            return `<span class="min-w-[28px] h-7 px-2 border border-slate-400 bg-white text-slate-800 font-medium text-xs rounded-md shadow-xs flex items-center justify-center">${p}</span>`;
        }
        return `<button type="button" onclick="changeTablePaginationPage('${tableKey}', ${p})" class="min-w-[28px] h-7 px-2 text-slate-500 hover:text-slate-800 hover:bg-slate-50 text-xs rounded-md flex items-center justify-center cursor-pointer transition-colors">${p}</button>`;
    }).join('');

    container.innerHTML = `
        <div class="px-4 py-3 border-t border-slate-200 bg-white flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <div class="text-slate-500 font-normal w-full sm:w-auto sm:flex-1 text-center sm:text-left">
                ${counterText}
            </div>

            <nav class="flex items-center justify-center gap-1.5 flex-shrink-0" aria-label="Paginación ${tableKey}">
                ${prevButton}
                ${pagesHtml}
                ${nextButton}
            </nav>

            <div class="flex items-center justify-center sm:justify-end gap-1.5 text-slate-500 w-full sm:w-auto sm:flex-1">
                <span>Mostrar</span>
                <select onchange="changeTablePaginationSize('${tableKey}', this.value)" class="px-2 py-0.5 bg-white border border-slate-300 rounded text-xs text-slate-700 outline-none focus:border-slate-500 cursor-pointer shadow-xs">
                    <option value="5" ${meta.pageSize === 5 ? 'selected' : ''}>5</option>
                    <option value="10" ${meta.pageSize === 10 ? 'selected' : ''}>10</option>
                    <option value="25" ${meta.pageSize === 25 ? 'selected' : ''}>25</option>
                    <option value="50" ${meta.pageSize === 50 ? 'selected' : ''}>50</option>
                </select>
                <span>por página</span>
            </div>
        </div>
    `;
}

function paginateAndRender(tableKey, containerId, allRows, renderPageRowsFn, defaultPageSize = 10) {
    _lastTableData[tableKey] = allRows || [];
    _tablePaginationRenderers[tableKey] = { containerId, renderPageRowsFn, defaultPageSize };
    const meta = paginateData(tableKey, _lastTableData[tableKey], defaultPageSize);
    renderPaginationBar(tableKey, containerId, meta);
    renderPageRowsFn(meta.paginatedItems, meta);
    return meta;
}

function changeTablePaginationPage(tableKey, newPage) {
    if (!tablePaginationState[tableKey] || !_tablePaginationRenderers[tableKey]) return;
    tablePaginationState[tableKey].page = newPage;
    const { containerId, renderPageRowsFn, defaultPageSize } = _tablePaginationRenderers[tableKey];
    const meta = paginateData(tableKey, _lastTableData[tableKey] || [], defaultPageSize);
    renderPaginationBar(tableKey, containerId, meta);
    renderPageRowsFn(meta.paginatedItems, meta);
}

function changeTablePaginationSize(tableKey, newSize) {
    if (!_tablePaginationRenderers[tableKey]) return;
    if (!tablePaginationState[tableKey]) {
        tablePaginationState[tableKey] = { page: 1, pageSize: 10 };
    }
    tablePaginationState[tableKey].pageSize = parseInt(newSize, 10) || 10;
    tablePaginationState[tableKey].page = 1;
    const { containerId, renderPageRowsFn, defaultPageSize } = _tablePaginationRenderers[tableKey];
    const meta = paginateData(tableKey, _lastTableData[tableKey] || [], defaultPageSize);
    renderPaginationBar(tableKey, containerId, meta);
    renderPageRowsFn(meta.paginatedItems, meta);
}

// ==========================================
// SEARCHABLE SELECT (COMBOBOX) COMPONENT
// ==========================================

function makeSearchableSelect(selectIdOrEl, config = {}) {
    const select = typeof selectIdOrEl === 'string' ? document.getElementById(selectIdOrEl) : selectIdOrEl;
    if (!select || select.tagName !== 'SELECT') return null;

    if (select._searchableSelect) {
        select._searchableSelect.syncOptions();
        return select._searchableSelect;
    }

    const placeholder = config.placeholder || (select.options[0] ? select.options[0].text : 'Seleccionar opción...');
    const wrapperClass = config.wrapperClass || 'w-full';
    const controlClass = config.controlClass || 'h-[38px] rounded-lg bg-slate-50';

    // Wrapper
    const wrapper = document.createElement('div');
    wrapper.className = `searchable-select-wrapper relative ${wrapperClass}`;

    // Control container
    const control = document.createElement('div');
    control.className = `searchable-select-control relative flex items-center w-full border border-slate-200 text-xs font-semibold text-slate-800 focus-within:ring-2 focus-within:ring-navy focus-within:border-navy cursor-text transition-all ${controlClass}`;

    // Text Input
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'searchable-select-input w-full h-full pl-3 pr-14 bg-transparent outline-none text-xs font-semibold text-slate-800 placeholder-slate-400';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.placeholder = placeholder;

    // Right Actions (clear + chevron)
    const rightActions = document.createElement('div');
    rightActions.className = 'absolute right-2.5 flex items-center gap-1.5 pointer-events-auto';

    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'searchable-select-clear hidden text-slate-400 hover:text-rose-500 p-0.5 rounded cursor-pointer transition-colors';
    clearBtn.title = 'Limpiar filtro';
    clearBtn.innerHTML = '<i class="fa-solid fa-xmark text-xs"></i>';

    const chevron = document.createElement('span');
    chevron.className = 'searchable-select-chevron text-slate-400 p-0.5 pointer-events-none transition-transform duration-200';
    chevron.innerHTML = '<i class="fa-solid fa-chevron-down text-[10px]"></i>';

    rightActions.appendChild(clearBtn);
    rightActions.appendChild(chevron);
    control.appendChild(input);
    control.appendChild(rightActions);

    // Dropdown list
    const dropdown = document.createElement('div');
    dropdown.className = 'searchable-select-dropdown absolute left-0 right-0 top-full mt-1.5 max-h-60 overflow-y-auto bg-white rounded-xl shadow-2xl border border-slate-200 py-1.5 z-[100] hidden';

    // Insert wrapper in DOM before select, move select inside wrapper
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(control);
    wrapper.appendChild(dropdown);
    wrapper.appendChild(select);

    // Hide original select visually
    select.style.position = 'absolute';
    select.style.opacity = '0';
    select.style.pointerEvents = 'none';
    select.style.height = '0';
    select.style.width = '0';
    select.style.margin = '0';
    select.style.padding = '0';
    select.style.border = 'none';
    select.tabIndex = -1;

    let highlightedIndex = -1;
    let isOpen = false;

    function normalizeStr(str) {
        return (str || '')
            .toString()
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();
    }

    function positionDropdown() {
        const rect = control.getBoundingClientRect();
        const dropdownHeight = 240;
        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top;

        if (spaceBelow < dropdownHeight && spaceAbove > spaceBelow) {
            dropdown.classList.remove('top-full', 'mt-1.5');
            dropdown.classList.add('bottom-full', 'mb-1.5');
        } else {
            dropdown.classList.remove('bottom-full', 'mb-1.5');
            dropdown.classList.add('top-full', 'mt-1.5');
        }
    }

    function openDropdown() {
        if (isOpen) return;

        // Close any other open dropdowns
        document.querySelectorAll('.searchable-select-dropdown:not(.hidden)').forEach(d => {
            if (d !== dropdown) {
                d.classList.add('hidden');
                const parentW = d.closest('.searchable-select-wrapper');
                if (parentW) {
                    const ch = parentW.querySelector('.searchable-select-chevron');
                    if (ch) ch.classList.remove('rotate-180');
                    const ctrl = parentW.querySelector('.searchable-select-control');
                    if (ctrl) ctrl.classList.remove('ring-2', 'ring-navy', 'border-navy');
                }
            }
        });

        positionDropdown();
        isOpen = true;
        dropdown.classList.remove('hidden');
        chevron.classList.add('rotate-180');
        control.classList.add('ring-2', 'ring-navy', 'border-navy');

        filterOptions('');

        setTimeout(() => {
            input.select();
        }, 10);
    }

    function closeDropdown() {
        if (!isOpen) return;
        isOpen = false;
        dropdown.classList.add('hidden');
        chevron.classList.remove('rotate-180');
        control.classList.remove('ring-2', 'ring-navy', 'border-navy');
        highlightedIndex = -1;

        // On close, validate text against options
        const raw = input.value.trim();
        if (!raw) {
            selectValue('', '');
        } else {
            const exact = Array.from(select.options).find(o => o.value && normalizeStr(o.text) === normalizeStr(raw));
            if (exact) {
                selectValue(exact.value, exact.text);
            } else {
                syncValue();
            }
        }
    }

    function renderOptions() {
        dropdown.innerHTML = '';
        const options = Array.from(select.options);

        if (options.length === 0) {
            const emptyEl = document.createElement('div');
            emptyEl.className = 'px-3 py-3 text-xs text-slate-400 italic text-center';
            emptyEl.textContent = 'Sin opciones disponibles';
            dropdown.appendChild(emptyEl);
            return;
        }

        options.forEach((opt, idx) => {
            const optEl = document.createElement('div');
            optEl.className = 'searchable-option px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-navy cursor-pointer flex items-center justify-between transition-colors';
            optEl.dataset.value = opt.value;
            optEl.dataset.text = opt.text;
            optEl.dataset.index = idx;
            optEl.title = opt.text;

            const isSelected = opt.value === select.value || (!select.value && !opt.value);
            if (isSelected) {
                optEl.classList.add('bg-navy/5', 'text-navy', 'font-bold');
            }

            const textSpan = document.createElement('span');
            textSpan.className = 'truncate';
            textSpan.textContent = opt.text;
            optEl.appendChild(textSpan);

            const checkIcon = document.createElement('i');
            checkIcon.className = `fa-solid fa-check text-navy text-[10px] ml-2 shrink-0 ${isSelected && opt.value ? '' : 'hidden'}`;
            optEl.appendChild(checkIcon);

            optEl.addEventListener('click', (e) => {
                e.stopPropagation();
                selectValue(opt.value, opt.text);
            });

            dropdown.appendChild(optEl);
        });

        const noResults = document.createElement('div');
        noResults.className = 'searchable-no-results hidden px-3 py-3 text-xs text-slate-400 italic text-center';
        noResults.textContent = 'No se encontraron resultados';
        dropdown.appendChild(noResults);
    }

    function filterOptions(query) {
        const normQ = normalizeStr(query);
        const optionEls = dropdown.querySelectorAll('.searchable-option');
        let visibleCount = 0;

        optionEls.forEach(el => {
            const val = el.dataset.value;
            const text = el.dataset.text;
            const normText = normalizeStr(text);

            const matches = !normQ || normText.includes(normQ) || (val === '' && !normQ);
            if (matches) {
                el.classList.remove('hidden');
                visibleCount++;
            } else {
                el.classList.add('hidden');
            }
        });

        const noResults = dropdown.querySelector('.searchable-no-results');
        if (noResults) {
            noResults.classList.toggle('hidden', visibleCount > 0);
        }

        highlightedIndex = -1;
        updateHighlight();
    }

    function selectValue(val, text) {
        const changed = select.value !== val;
        select.value = val;

        if (val) {
            input.value = text;
            clearBtn.classList.remove('hidden');
        } else {
            input.value = '';
            input.placeholder = placeholder;
            clearBtn.classList.add('hidden');
        }

        isOpen = false;
        dropdown.classList.add('hidden');
        chevron.classList.remove('rotate-180');
        control.classList.remove('ring-2', 'ring-navy', 'border-navy');

        syncValue();

        if (changed) {
            select.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof select.onchange === 'function') {
                select.onchange.call(select, new Event('change', { bubbles: true }));
            }
        }
    }

    function syncValue() {
        const currVal = select.value;
        const selectedOpt = select.selectedOptions[0] || Array.from(select.options).find(o => o.value === currVal);

        if (currVal && selectedOpt) {
            input.value = selectedOpt.text;
            clearBtn.classList.remove('hidden');
        } else {
            input.value = '';
            input.placeholder = placeholder;
            clearBtn.classList.add('hidden');
        }

        dropdown.querySelectorAll('.searchable-option').forEach(el => {
            const isSelected = el.dataset.value === currVal || (!currVal && !el.dataset.value);
            el.classList.toggle('bg-navy/5', isSelected);
            el.classList.toggle('text-navy', isSelected);
            el.classList.toggle('font-bold', isSelected);
            const check = el.querySelector('.fa-check');
            if (check) check.classList.toggle('hidden', !isSelected || !currVal);
        });
    }

    function updateHighlight() {
        const visibleEls = Array.from(dropdown.querySelectorAll('.searchable-option:not(.hidden)'));
        visibleEls.forEach((el, idx) => {
            if (idx === highlightedIndex) {
                el.classList.add('bg-slate-100');
                el.scrollIntoView({ block: 'nearest' });
            } else {
                el.classList.remove('bg-slate-100');
            }
        });
    }

    control.addEventListener('click', (e) => {
        if (e.target.closest('.searchable-select-clear')) return;
        input.focus();
        openDropdown();
    });

    rightActions.addEventListener('click', (e) => {
        if (e.target.closest('.searchable-select-clear')) return;
        e.stopPropagation();
        if (isOpen) {
            closeDropdown();
        } else {
            input.focus();
            openDropdown();
        }
    });

    input.addEventListener('focus', () => {
        openDropdown();
    });

    input.addEventListener('input', () => {
        if (!isOpen) openDropdown();
        filterOptions(input.value);
        if (input.value.trim()) {
            clearBtn.classList.remove('hidden');
        } else if (!select.value) {
            clearBtn.classList.add('hidden');
        }
    });

    input.addEventListener('keydown', (e) => {
        const visibleEls = Array.from(dropdown.querySelectorAll('.searchable-option:not(.hidden)'));

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (!isOpen) {
                openDropdown();
                return;
            }
            if (visibleEls.length > 0) {
                highlightedIndex = (highlightedIndex + 1) % visibleEls.length;
                updateHighlight();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (!isOpen) {
                openDropdown();
                return;
            }
            if (visibleEls.length > 0) {
                highlightedIndex = (highlightedIndex - 1 + visibleEls.length) % visibleEls.length;
                updateHighlight();
            }
        } else if (e.key === 'Enter') {
            if (isOpen) {
                e.preventDefault();
                if (highlightedIndex >= 0 && highlightedIndex < visibleEls.length) {
                    const chosen = visibleEls[highlightedIndex];
                    selectValue(chosen.dataset.value, chosen.dataset.text);
                } else if (visibleEls.length > 0) {
                    selectValue(visibleEls[0].dataset.value, visibleEls[0].dataset.text);
                } else {
                    closeDropdown();
                }
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeDropdown();
        } else if (e.key === 'Tab') {
            closeDropdown();
        }
    });

    clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        selectValue('', '');
        input.focus();
    });

    document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
            closeDropdown();
        }
    });

    if (select.form) {
        select.form.addEventListener('reset', () => {
            setTimeout(() => {
                syncValue();
            }, 10);
        });
    }

    const origValueDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    if (origValueDescriptor) {
        Object.defineProperty(select, 'value', {
            get: function() {
                return origValueDescriptor.get.call(this);
            },
            set: function(val) {
                origValueDescriptor.set.call(this, val);
                syncValue();
            },
            configurable: true
        });
    }

    const origIndexDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    if (origIndexDescriptor) {
        Object.defineProperty(select, 'selectedIndex', {
            get: function() {
                return origIndexDescriptor.get.call(this);
            },
            set: function(idx) {
                origIndexDescriptor.set.call(this, idx);
                syncValue();
            },
            configurable: true
        });
    }

    const instance = {
        wrapper,
        input,
        dropdown,
        select,
        syncOptions: () => {
            renderOptions();
            syncValue();
        },
        syncValue: () => {
            syncValue();
        },
        open: openDropdown,
        close: closeDropdown
    };

    select._searchableSelect = instance;

    renderOptions();
    syncValue();

    return instance;
}

function initAllSearchableSelects() {
    makeSearchableSelect('filter-p-cliente', {
        placeholder: 'Todos los Clientes',
        wrapperClass: 'w-full',
        controlClass: 'h-[38px] rounded-lg bg-slate-50'
    });
    makeSearchableSelect('select-cc-cliente', {
        placeholder: 'Seleccionar Cliente...',
        wrapperClass: 'w-full max-w-xs',
        controlClass: 'h-[40px] rounded-xl font-bold bg-slate-50'
    });
    makeSearchableSelect('filter-ord-proveedor', {
        placeholder: 'Todos los Proveedores',
        wrapperClass: 'w-full sm:w-56',
        controlClass: 'h-[38px] rounded-xl font-semibold bg-slate-50'
    });
    makeSearchableSelect('o-proveedor', {
        placeholder: 'Seleccionar Proveedor...',
        wrapperClass: 'w-full',
        controlClass: 'h-[40px] rounded-xl font-semibold bg-slate-50'
    });
    makeSearchableSelect('pago-cc-cliente', {
        placeholder: 'Seleccionar Cliente...',
        wrapperClass: 'w-full',
        controlClass: 'h-[40px] rounded-xl font-bold bg-slate-50'
    });
    makeSearchableSelect('p-cliente', {
        placeholder: 'Seleccionar Cliente...',
        wrapperClass: 'w-full mt-1',
        controlClass: 'h-[38px] rounded-lg font-medium bg-white'
    });
}

// Bloqueo global de valores negativos en todos los campos numéricos (importes, litros, cantidades)
document.addEventListener('keydown', function(e) {
    if (e.target && e.target.matches && e.target.matches('input[type="number"]')) {
        if (e.key === '-' || e.key === 'e' || e.key === 'E') {
            e.preventDefault();
        }
    }
}, true);

document.addEventListener('input', function(e) {
    if (e.target && e.target.matches && e.target.matches('input[type="number"]')) {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val < 0) {
            e.target.value = '';
            e.target.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
}, true);
