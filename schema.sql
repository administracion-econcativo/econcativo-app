-- =============================================================================
-- ESQUEMA DE BASE DE DATOS ECONCATIVO PARA SUPABASE (POSTGRESQL)
-- =============================================================================

-- Habilitar extensión UUID por si es requerida
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TABLA: USUARIOS
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario VARCHAR(50) PRIMARY KEY,
    nombre_completo VARCHAR(255) NOT NULL,
    usuario VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol VARCHAR(50) DEFAULT 'Administrador',
    estado VARCHAR(50) DEFAULT 'Activo',
    ultimo_acceso TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. TABLA: CONFIGURACION (Parámetros y Listas Maestras)
CREATE TABLE IF NOT EXISTS configuracion (
    id SERIAL PRIMARY KEY,
    categoria VARCHAR(100) NOT NULL,
    clave VARCHAR(255) NOT NULL,
    valor TEXT,
    orden INT DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TABLA: CLIENTES
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente VARCHAR(50) PRIMARY KEY,
    razon_social VARCHAR(255) NOT NULL,
    cuit_cuil VARCHAR(50),
    tipo_cliente VARCHAR(100) DEFAULT 'Empresa',
    condicion_iva VARCHAR(100) DEFAULT 'Responsable Inscripto',
    telefono VARCHAR(100),
    correo VARCHAR(255),
    domicilio TEXT,
    estado VARCHAR(50) DEFAULT 'Activo',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. TABLA: UNIDADES
CREATE TABLE IF NOT EXISTS unidades (
    id_unidad VARCHAR(50) PRIMARY KEY,
    tipo VARCHAR(100),
    descripcion VARCHAR(255),
    dominio_patente VARCHAR(50) NOT NULL,
    marca VARCHAR(100),
    modelo VARCHAR(100),
    anio INT,
    estado VARCHAR(50) DEFAULT 'Activo',
    seguro_vence DATE,
    rto_itv_vence DATE,
    enlace_documentacion TEXT,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. TABLA: EMPLEADOS
CREATE TABLE IF NOT EXISTS empleados (
    id_empleado VARCHAR(50) PRIMARY KEY,
    apellido_nombre VARCHAR(255) NOT NULL,
    dni VARCHAR(50),
    cuil VARCHAR(50),
    fecha_nacimiento DATE,
    estado_civil VARCHAR(50),
    domicilio_real_actual TEXT,
    barrio_zona VARCHAR(100),
    localidad VARCHAR(100),
    telefono VARCHAR(100),
    email VARCHAR(255),
    contacto_emergencia VARCHAR(255),
    vinculo_parentesco VARCHAR(100),
    domicilio_contacto TEXT,
    localidad_contacto VARCHAR(100),
    fecha_ingreso DATE,
    puesto VARCHAR(100),
    modalidad_contratacion VARCHAR(100),
    sueldo_basico NUMERIC(24, 2) DEFAULT 0,
    comision_pct NUMERIC(24, 2) DEFAULT 0,
    banco VARCHAR(100),
    cbu VARCHAR(100),
    alias_cbu VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'Activo',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. TABLA: PROVEEDORES
CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor VARCHAR(50) PRIMARY KEY,
    razon_social VARCHAR(255) NOT NULL,
    nombre_comercial VARCHAR(255),
    cuit VARCHAR(50),
    rubro VARCHAR(100),
    telefono VARCHAR(100),
    correo VARCHAR(255),
    condicion_pago VARCHAR(100),
    saldo_inicial NUMERIC(24, 2) DEFAULT 0,
    fecha_saldo_inicial DATE,
    estado VARCHAR(50) DEFAULT 'Activo',
    observaciones TEXT,
    cbu_alias VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. TABLA: ACTIVIDADES
CREATE TABLE IF NOT EXISTS actividades (
    id_actividad VARCHAR(50) PRIMARY KEY,
    actividad VARCHAR(100) NOT NULL,
    descripcion TEXT,
    estado VARCHAR(50) DEFAULT 'Activo',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. TABLA: PRESUPUESTOS
CREATE TABLE IF NOT EXISTS presupuestos (
    id_presupuesto VARCHAR(50) PRIMARY KEY,
    fecha DATE NOT NULL,
    cliente VARCHAR(255) NOT NULL,
    cuit VARCHAR(50),
    tipo_servicio VARCHAR(100),
    detalle_concepto TEXT,
    total NUMERIC(24, 2) DEFAULT 0,
    iva_pct NUMERIC(24, 2) DEFAULT 0,
    validez VARCHAR(100),
    forma_pago VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'Pendiente',
    id_viaje_asociado VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. TABLA: VIAJES
CREATE TABLE IF NOT EXISTS viajes (
    id_viaje VARCHAR(50) PRIMARY KEY,
    fecha_salida DATE NOT NULL,
    fecha_regreso DATE,
    chofer VARCHAR(255),
    unidad VARCHAR(255),
    origen VARCHAR(255),
    destino VARCHAR(255),
    cliente VARCHAR(255) NOT NULL,
    actividad VARCHAR(100),
    carga TEXT,
    nro_remito VARCHAR(100),
    cpe VARCHAR(100),
    km_inicial NUMERIC(24, 2),
    km_final NUMERIC(24, 2),
    km_recorridos NUMERIC(24, 2),
    toneladas NUMERIC(24, 2),
    combustible_litros NUMERIC(24, 2),
    gastos_viaje NUMERIC(24, 2) DEFAULT 0,
    adelanto NUMERIC(24, 2) DEFAULT 0,
    valor_servicio NUMERIC(24, 2) DEFAULT 0,
    estado_facturacion VARCHAR(50) DEFAULT 'No facturado',
    id_ingreso_factura VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. TABLA: INGRESOS (Facturación y Cobranzas)
CREATE TABLE IF NOT EXISTS ingresos (
    id_ingreso VARCHAR(50) PRIMARY KEY,
    fecha_emision DATE NOT NULL,
    tipo_comprobante VARCHAR(100),
    punto_venta VARCHAR(20),
    nro_factura_arca VARCHAR(100),
    cliente VARCHAR(255) NOT NULL,
    cuit_cuil VARCHAR(50),
    actividad VARCHAR(100),
    chofer VARCHAR(255),
    unidad VARCHAR(255),
    km NUMERIC(24, 2),
    toneladas NUMERIC(24, 2),
    neto NUMERIC(24, 2) DEFAULT 0,
    iva_pct NUMERIC(24, 2) DEFAULT 0,
    iva NUMERIC(24, 2) DEFAULT 0,
    total NUMERIC(24, 2) DEFAULT 0,
    estado_cobro VARCHAR(50) DEFAULT 'PENDIENTE',
    importe_cobrado NUMERIC(24, 2) DEFAULT 0,
    fecha_cobro DATE,
    medio_cobro TEXT,
    saldo NUMERIC(24, 2) DEFAULT 0,
    id_acuerdo VARCHAR(100),
    modalidad_aplicada VARCHAR(100),
    tarifa_aplicada NUMERIC(24, 2),
    remuneracion NUMERIC(24, 2),
    estado_remuneracion VARCHAR(50),
    enlace_factura TEXT,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. TABLA: EGRESOS (Gastos, Pagos y Facturas de Compra)
CREATE TABLE IF NOT EXISTS egresos (
    id_egreso VARCHAR(50) PRIMARY KEY,
    fecha_comprobante DATE NOT NULL,
    fecha_vencimiento DATE,
    categoria VARCHAR(100),
    subcategoria VARCHAR(100),
    proveedor VARCHAR(255),
    cuit VARCHAR(50),
    tipo_comprobante VARCHAR(100),
    nro_comprobante VARCHAR(100),
    unidad VARCHAR(255),
    empleado VARCHAR(255),
    descripcion TEXT,
    cantidad_litros NUMERIC(24, 2),
    neto NUMERIC(24, 2) DEFAULT 0,
    iva NUMERIC(24, 2) DEFAULT 0,
    total NUMERIC(24, 2) DEFAULT 0,
    estado_pago VARCHAR(50) DEFAULT 'Pendiente',
    importe_pagado NUMERIC(24, 2) DEFAULT 0,
    fecha_pago DATE,
    medio_pago VARCHAR(100),
    saldo NUMERIC(24, 2) DEFAULT 0,
    enlace_comprobante TEXT,
    id_liquidacion VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. TABLA: CHEQUES (Cartera, Emitidos y Transferidos)
CREATE TABLE IF NOT EXISTS cheques (
    id_cheque VARCHAR(50) PRIMARY KEY,
    fecha_ingreso DATE NOT NULL,
    tipo VARCHAR(100),
    monto NUMERIC(24, 2) NOT NULL,
    cliente_emisor VARCHAR(255),
    cuit_emisor VARCHAR(50),
    banco VARCHAR(100),
    nro_cheque VARCHAR(100),
    fecha_cobro DATE,
    endosado_tenedor VARCHAR(255),
    estado VARCHAR(50) DEFAULT 'En Cartera',
    destino_usado_en TEXT,
    fecha_uso DATE,
    id_egreso VARCHAR(50),
    id_ingreso_origen VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. TABLA: ORDENES_COMPRA
CREATE TABLE IF NOT EXISTS ordenes_compra (
    id_orden VARCHAR(50) PRIMARY KEY,
    fecha DATE NOT NULL,
    proveedor VARCHAR(255) NOT NULL,
    cuit_proveedor VARCHAR(50),
    tipo_insumo VARCHAR(100),
    unidad VARCHAR(255),
    detalle TEXT,
    neto NUMERIC(24, 2) DEFAULT 0,
    iva_pct NUMERIC(24, 2) DEFAULT 0,
    total NUMERIC(24, 2) DEFAULT 0,
    forma_pago VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'Pendiente',
    fecha_pago DATE,
    id_egreso VARCHAR(50),
    observaciones TEXT,
    cantidad_litros NUMERIC(24, 2),
    id_cheque VARCHAR(50),
    nro_cheque VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 14. TABLA: LIQUIDACIONES
CREATE TABLE IF NOT EXISTS liquidaciones (
    id_liquidacion VARCHAR(50) PRIMARY KEY,
    fecha_confirmacion DATE,
    periodo_quincena VARCHAR(100),
    id_empleado VARCHAR(50),
    empleado VARCHAR(255),
    puesto VARCHAR(100),
    dni VARCHAR(50),
    cuil VARCHAR(50),
    entidad_bancaria VARCHAR(100),
    cbu VARCHAR(100),
    alias_cbu VARCHAR(100),
    sueldo_fijo_base NUMERIC(24, 2) DEFAULT 0,
    comision_pct NUMERIC(24, 2) DEFAULT 0,
    cant_viajes INT DEFAULT 0,
    total_comisiones NUMERIC(24, 2) DEFAULT 0,
    sueldo_final NUMERIC(24, 2) DEFAULT 0,
    estado VARCHAR(50) DEFAULT 'PENDIENTE',
    desglose_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 15. TABLA: CUENTAS_CORRIENTES (Movimientos de Clientes)
CREATE TABLE IF NOT EXISTS cuentas_corrientes (
    id_movimiento VARCHAR(50) PRIMARY KEY,
    fecha DATE NOT NULL,
    fecha_vencimiento DATE,
    cliente VARCHAR(255) NOT NULL,
    cuit VARCHAR(50),
    tipo_comprobante VARCHAR(100),
    referencia_id VARCHAR(100),
    concepto TEXT,
    debe NUMERIC(24, 2) DEFAULT 0,
    haber NUMERIC(24, 2) DEFAULT 0,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 16. TABLA: NOVEDADES_PERSONAL (Adelantos, Sanciones, Reintegros)
CREATE TABLE IF NOT EXISTS novedades_personal (
    id_novedad VARCHAR(50) PRIMARY KEY,
    fecha DATE NOT NULL,
    id_empleado VARCHAR(50),
    empleado VARCHAR(255),
    tipo VARCHAR(100),
    concepto TEXT,
    monto NUMERIC(24, 2) DEFAULT 0,
    medio_pago VARCHAR(100),
    id_cheque VARCHAR(50),
    nro_cheque VARCHAR(100),
    id_liquidacion VARCHAR(50),
    estado VARCHAR(50) DEFAULT 'Pendiente',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 17. TABLA: REMUNERACIONES
CREATE TABLE IF NOT EXISTS remuneraciones (
    id_remuneracion VARCHAR(50) PRIMARY KEY,
    id_ingreso VARCHAR(50),
    fecha_factura DATE,
    empleado VARCHAR(255),
    actividad VARCHAR(100),
    nro_factura VARCHAR(100),
    neto_factura NUMERIC(24, 2) DEFAULT 0,
    id_acuerdo VARCHAR(50),
    modalidad VARCHAR(100),
    base_calculo VARCHAR(100),
    tarifa NUMERIC(24, 2) DEFAULT 0,
    importe_remuneracion NUMERIC(24, 2) DEFAULT 0,
    frecuencia VARCHAR(50),
    periodo_sugerido VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'Pendiente',
    id_liquidacion VARCHAR(50),
    fecha_pago DATE,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 18. TABLA: ACUERDOS
CREATE TABLE IF NOT EXISTS acuerdos (
    id_acuerdo VARCHAR(50) PRIMARY KEY,
    empleado VARCHAR(255),
    actividad VARCHAR(100),
    modalidad VARCHAR(100),
    valor_tarifa NUMERIC(24, 2) DEFAULT 0,
    vigencia_desde DATE,
    vigencia_hasta DATE,
    frecuencia VARCHAR(50),
    estado VARCHAR(50) DEFAULT 'Activo',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 19. TABLA: TESORERIA (Cuentas bancarias y Cajas)
CREATE TABLE IF NOT EXISTS tesoreria_cuentas (
    id_cuenta VARCHAR(50) PRIMARY KEY,
    nombre_cuenta VARCHAR(255) NOT NULL,
    tipo VARCHAR(50),
    nro_cuenta_cbu_alias VARCHAR(100),
    saldo_inicial NUMERIC(24, 2) DEFAULT 0,
    saldo_real_cotejado NUMERIC(24, 2),
    fecha_ultimo_cotejo DATE,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 20. TABLA: MOVIMIENTOS_TESORERIA (Transferencias entre cuentas / Ajustes)
CREATE TABLE IF NOT EXISTS tesoreria_movimientos (
    id_movimiento VARCHAR(50) PRIMARY KEY,
    fecha DATE NOT NULL,
    cuenta_origen VARCHAR(255),
    cuenta_destino VARCHAR(255),
    monto NUMERIC(24, 2) NOT NULL,
    concepto TEXT,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- ÍNDICES PARA ALTO RENDIMIENTO
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_clientes_cuit ON clientes(cuit_cuil);
CREATE INDEX IF NOT EXISTS idx_viajes_fecha ON viajes(fecha_salida);
CREATE INDEX IF NOT EXISTS idx_viajes_cliente ON viajes(cliente);
CREATE INDEX IF NOT EXISTS idx_viajes_chofer ON viajes(chofer);
CREATE INDEX IF NOT EXISTS idx_ingresos_fecha ON ingresos(fecha_emision);
CREATE INDEX IF NOT EXISTS idx_ingresos_cliente ON ingresos(cliente);
CREATE INDEX IF NOT EXISTS idx_egresos_fecha ON egresos(fecha_comprobante);
CREATE INDEX IF NOT EXISTS idx_egresos_proveedor ON egresos(proveedor);
CREATE INDEX IF NOT EXISTS idx_cheques_estado ON cheques(estado);
CREATE INDEX IF NOT EXISTS idx_cheques_fecha_cobro ON cheques(fecha_cobro);
CREATE INDEX IF NOT EXISTS idx_cc_cliente ON cuentas_corrientes(cliente);
CREATE INDEX IF NOT EXISTS idx_ordenes_proveedor ON ordenes_compra(proveedor);
