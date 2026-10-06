/**
 * ECONCATIVO - Application Initialization
 */
document.addEventListener('DOMContentLoaded', async () => {
    if (typeof initAllSearchableSelects === 'function') {
        initAllSearchableSelects();
    }
    populateDashboardYearSelect();
    if (typeof populateResumenProveedorAnios === 'function') populateResumenProveedorAnios(true);
    if (typeof initLiquidacionesDateFilters === 'function') initLiquidacionesDateFilters();
    try { await loadDashboardData(); } catch (e) { console.error("Error al cargar Dashboard:", e); }
    try { await loadMasterLists(); } catch (e) { console.error("Error al cargar Maestros:", e); }
    loadCustomEgresoCategorias();
    try { await loadPresupuestosData(); } catch (e) { console.error("Error al cargar Presupuestos:", e); }
    try { await loadViajesData(); } catch (e) { console.error("Error al cargar Viajes:", e); }
    try { await loadFacturacionData(); } catch (e) { console.error("Error al cargar Facturación:", e); }
    try { await loadIngresosData(); } catch (e) { console.error("Error al cargar Ingresos:", e); }
    try { await loadEgresosData(); } catch (e) { console.error("Error al cargar Egresos:", e); }
    try { await loadChequesData(); } catch (e) { console.error("Error al cargar Cheques:", e); }
    try { await loadTesoreriaData(); } catch (e) { console.error("Error al cargar Tesorería:", e); }
});
