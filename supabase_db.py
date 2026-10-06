"""
=============================================================================
MODULO DE ACCESO A BASE DE DATOS SUPABASE / POSTGRESQL (ECONCATIVO)
=============================================================================
Este módulo gestiona la conexión con la base de datos PostgreSQL de Supabase
y proporciona operaciones optimizadas mediante SQLAlchemy y psycopg2.
"""

import os
import json
from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

load_dotenv()

# Column mapping: Database Table -> { DB Column: Excel/Frontend Header }
TABLE_MAPPINGS = {
    'clientes': {
        'table': 'clientes',
        'pk': 'id_cliente',
        'prefix': 'CLI',
        'headers': ['ID cliente', 'Razón social / Nombre', 'CUIT/CUIL', 'Tipo de cliente', 'Condición IVA', 'Teléfono', 'Correo', 'Domicilio', 'Estado', 'Observaciones'],
        'col_map': {
            'id_cliente': 'ID cliente',
            'razon_social': 'Razón social / Nombre',
            'cuit_cuil': 'CUIT/CUIL',
            'tipo_cliente': 'Tipo de cliente',
            'condicion_iva': 'Condición IVA',
            'telefono': 'Teléfono',
            'correo': 'Correo',
            'domicilio': 'Domicilio',
            'estado': 'Estado',
            'observaciones': 'Observaciones'
        }
    },
    'unidades': {
        'table': 'unidades',
        'pk': 'id_unidad',
        'prefix': 'UNI',
        'headers': ['ID unidad', 'Tipo', 'Descripción', 'Dominio/Patente', 'Marca', 'Modelo', 'Año', 'Estado', 'Seguro vence', 'RTO/ITV vence', 'Enlace documentación', 'Observaciones'],
        'col_map': {
            'id_unidad': 'ID unidad',
            'tipo': 'Tipo',
            'descripcion': 'Descripción',
            'dominio_patente': 'Dominio/Patente',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'anio': 'Año',
            'estado': 'Estado',
            'seguro_vence': 'Seguro vence',
            'rto_itv_vence': 'RTO/ITV vence',
            'enlace_documentacion': 'Enlace documentación',
            'observaciones': 'Observaciones'
        }
    },
    'empleados': {
        'table': 'empleados',
        'pk': 'id_empleado',
        'prefix': 'EMP',
        'headers': [
            'ID empleado', 'Apellido y nombre', 'DNI', 'CUIL', 'Fecha de nacimiento',
            'Estado civil', 'Domicilio real actual', 'Barrio / Zona', 'Localidad',
            'Teléfono', 'Email', 'Contacto de emergencia', 'Vínculo / Parentesco',
            'Domicilio contacto', 'Localidad contacto', 'Teléfono contacto',
            'Entidad bancaria', 'Titularidad cuenta', 'CBU', 'Alias CBU',
            'Fecha inicio actividad', 'Cargo / Puesto', 'Jornada laboral',
            'Modalidad de trabajo', 'Remuneración', 'Modalidad de pago', 'Seguro personal / ART',
            'Tipo de licencia', 'Licencia vence', 'Talle remera',
            'Talle campera / buzo', 'Talle pantalón', 'N° calzado de seguridad',
            'Estado', 'Observaciones', 'Sueldo fijo', 'Porcentaje comisión (%)'
        ],
        'col_map': {
            'id_empleado': 'ID empleado',
            'apellido_nombre': 'Apellido y nombre',
            'dni': 'DNI',
            'cuil': 'CUIL',
            'fecha_nacimiento': 'Fecha de nacimiento',
            'estado_civil': 'Estado civil',
            'domicilio_real_actual': 'Domicilio real actual',
            'barrio_zona': 'Barrio / Zona',
            'localidad': 'Localidad',
            'telefono': 'Teléfono',
            'email': 'Email',
            'contacto_emergencia': 'Contacto de emergencia',
            'vinculo_parentesco': 'Vínculo / Parentesco',
            'domicilio_contacto': 'Domicilio contacto',
            'localidad_contacto': 'Localidad contacto',
            'telefono_contacto': 'Teléfono contacto',
            'banco': 'Entidad bancaria',
            'titular_cuenta': 'Titularidad cuenta',
            'cbu': 'CBU',
            'alias_cbu': 'Alias CBU',
            'fecha_inicio': 'Fecha inicio actividad',
            'puesto': 'Cargo / Puesto',
            'jornada': 'Jornada laboral',
            'modalidad_trabajo': 'Modalidad de trabajo',
            'remuneracion': 'Remuneración',
            'modalidad_pago': 'Modalidad de pago',
            'seguro_art': 'Seguro personal / ART',
            'tipo_licencia': 'Tipo de licencia',
            'licencia_vence': 'Licencia vence',
            'talle_remera': 'Talle remera',
            'talle_campera': 'Talle campera / buzo',
            'talle_pantalon': 'Talle pantalón',
            'calzado': 'N° calzado de seguridad',
            'estado': 'Estado',
            'observaciones': 'Observaciones',
            'sueldo_fijo': 'Sueldo fijo',
            'comision_pct': 'Porcentaje comisión (%)'
        }
    },
    'proveedores': {
        'table': 'proveedores',
        'pk': 'id_proveedor',
        'prefix': 'PROV',
        'headers': ['ID proveedor', 'Razón social', 'Nombre comercial', 'CUIT', 'Rubro', 'Teléfono', 'Correo', 'Condición de pago', 'Saldo inicial', 'Fecha saldo inicial', 'Estado', 'Observaciones', 'CBU / ALIAS'],
        'col_map': {
            'id_proveedor': 'ID proveedor',
            'razon_social': 'Razón social',
            'nombre_comercial': 'Nombre comercial',
            'cuit': 'CUIT',
            'rubro': 'Rubro',
            'telefono': 'Teléfono',
            'correo': 'Correo',
            'condicion_pago': 'Condición de pago',
            'saldo_inicial': 'Saldo inicial',
            'fecha_saldo_inicial': 'Fecha saldo inicial',
            'estado': 'Estado',
            'observaciones': 'Observaciones',
            'cbu_alias': 'CBU / ALIAS'
        }
    },
    'actividades': {
        'table': 'actividades',
        'pk': 'id_actividad',
        'prefix': 'ACT',
        'headers': ['ID actividad', 'Actividad', 'Descripción', 'Estado'],
        'col_map': {
            'id_actividad': 'ID actividad',
            'actividad': 'Actividad',
            'descripcion': 'Descripción',
            'estado': 'Estado'
        }
    },
    'presupuestos': {
        'table': 'presupuestos',
        'pk': 'id_presupuesto',
        'prefix': 'PRE',
        'headers': ['ID presupuesto', 'Fecha', 'Cliente', 'CUIT', 'Tipo servicio', 'Detalle/Concepto', 'Total', 'IVA %', 'Validez', 'Forma pago', 'Estado', 'ID viaje asociado', 'Observaciones', 'Items JSON'],
        'col_map': {
            'id_presupuesto': 'ID presupuesto',
            'fecha': 'Fecha',
            'cliente': 'Cliente',
            'cuit': 'CUIT',
            'tipo_servicio': 'Tipo servicio',
            'detalle_concepto': 'Detalle/Concepto',
            'total': 'Total',
            'iva_pct': 'IVA %',
            'validez': 'Validez',
            'forma_pago': 'Forma pago',
            'estado': 'Estado',
            'id_viaje_asociado': 'ID viaje asociado',
            'observaciones': 'Observaciones',
            'items_json': 'Items JSON'
        }
    },
    'viajes': {
        'table': 'viajes',
        'pk': 'id_viaje',
        'prefix': 'VIA',
        'headers': ['ID viaje', 'Fecha salida', 'Fecha regreso', 'Chofer', 'Unidad', 'Origen', 'Destino', 'Cliente', 'Actividad', 'Carga', 'Nº remito', 'CPE', 'Km inicial', 'Km final', 'Km recorridos', 'Toneladas', 'Combustible litros', 'Gastos viaje', 'Adelanto', 'Valor servicio', 'Estado facturación', 'ID ingreso/factura', 'Observaciones'],
        'col_map': {
            'id_viaje': 'ID viaje',
            'fecha_salida': 'Fecha salida',
            'fecha_regreso': 'Fecha regreso',
            'chofer': 'Chofer',
            'unidad': 'Unidad',
            'origen': 'Origen',
            'destino': 'Destino',
            'cliente': 'Cliente',
            'actividad': 'Actividad',
            'carga': 'Carga',
            'nro_remito': 'Nº remito',
            'cpe': 'CPE',
            'km_inicial': 'Km inicial',
            'km_final': 'Km final',
            'km_recorridos': 'Km recorridos',
            'toneladas': 'Toneladas',
            'combustible_litros': 'Combustible litros',
            'gastos_viaje': 'Gastos viaje',
            'adelanto': 'Adelanto',
            'valor_servicio': 'Valor servicio',
            'estado_facturacion': 'Estado facturación',
            'id_ingreso_factura': 'ID ingreso/factura',
            'observaciones': 'Observaciones'
        }
    },
    'ingresos': {
        'table': 'ingresos',
        'pk': 'id_ingreso',
        'prefix': 'ING',
        'headers': ['ID ingreso', 'Fecha emisión', 'Tipo comprobante', 'Punto venta', 'Nº factura ARCA', 'Cliente', 'CUIT/CUIL', 'Actividad', 'Chofer', 'Unidad', 'Km', 'Toneladas', 'Neto', 'IVA %', 'IVA', 'Total', 'Estado cobro', 'Importe cobrado', 'Fecha cobro', 'Medio cobro', 'Saldo', 'ID acuerdo', 'Modalidad aplicada', 'Tarifa aplicada', 'Remuneración', 'Estado remuneración', 'Enlace factura', 'Observaciones'],
        'col_map': {
            'id_ingreso': 'ID ingreso',
            'fecha_emision': 'Fecha emisión',
            'tipo_comprobante': 'Tipo comprobante',
            'punto_venta': 'Punto venta',
            'nro_factura_arca': 'Nº factura ARCA',
            'cliente': 'Cliente',
            'cuit_cuil': 'CUIT/CUIL',
            'actividad': 'Actividad',
            'chofer': 'Chofer',
            'unidad': 'Unidad',
            'km': 'Km',
            'toneladas': 'Toneladas',
            'neto': 'Neto',
            'iva_pct': 'IVA %',
            'iva': 'IVA',
            'total': 'Total',
            'estado_cobro': 'Estado cobro',
            'importe_cobrado': 'Importe cobrado',
            'fecha_cobro': 'Fecha cobro',
            'medio_cobro': 'Medio cobro',
            'saldo': 'Saldo',
            'id_acuerdo': 'ID acuerdo',
            'modalidad_aplicada': 'Modalidad aplicada',
            'tarifa_aplicada': 'Tarifa aplicada',
            'remuneracion': 'Remuneración',
            'estado_remuneracion': 'Estado remuneración',
            'enlace_factura': 'Enlace factura',
            'observaciones': 'Observaciones'
        }
    },
    'facturacion': {
        'table': 'ingresos', # Facturación queries the ingresos table
        'pk': 'id_ingreso',
        'prefix': 'ING',
        'headers': ['ID ingreso', 'Fecha emisión', 'Tipo comprobante', 'Punto venta', 'Nº factura ARCA', 'Cliente', 'CUIT/CUIL', 'Actividad', 'Chofer', 'Unidad', 'Km', 'Toneladas', 'Neto', 'IVA %', 'IVA', 'Total', 'Estado cobro', 'Importe cobrado', 'Fecha cobro', 'Medio cobro', 'Saldo', 'ID acuerdo', 'Modalidad aplicada', 'Tarifa aplicada', 'Remuneración', 'Estado remuneración', 'Enlace factura', 'Observaciones'],
        'col_map': {
            'id_ingreso': 'ID ingreso',
            'fecha_emision': 'Fecha emisión',
            'tipo_comprobante': 'Tipo comprobante',
            'punto_venta': 'Punto venta',
            'nro_factura_arca': 'Nº factura ARCA',
            'cliente': 'Cliente',
            'cuit_cuil': 'CUIT/CUIL',
            'actividad': 'Actividad',
            'chofer': 'Chofer',
            'unidad': 'Unidad',
            'km': 'Km',
            'toneladas': 'Toneladas',
            'neto': 'Neto',
            'iva_pct': 'IVA %',
            'iva': 'IVA',
            'total': 'Total',
            'estado_cobro': 'Estado cobro',
            'importe_cobrado': 'Importe cobrado',
            'fecha_cobro': 'Fecha cobro',
            'medio_cobro': 'Medio cobro',
            'saldo': 'Saldo',
            'id_acuerdo': 'ID acuerdo',
            'modalidad_aplicada': 'Modalidad aplicada',
            'tarifa_aplicada': 'Tarifa aplicada',
            'remuneracion': 'Remuneración',
            'estado_remuneracion': 'Estado remuneración',
            'enlace_factura': 'Enlace factura',
            'observaciones': 'Observaciones'
        }
    },
    'egresos': {
        'table': 'egresos',
        'pk': 'id_egreso',
        'prefix': 'EGR',
        'headers': ['ID egreso', 'Fecha comprobante', 'Fecha vencimiento', 'Categoría', 'Subcategoría', 'Proveedor', 'CUIT', 'Tipo comprobante', 'Nº comprobante', 'Unidad', 'Empleado', 'Descripción', 'Cantidad/Litros', 'Neto', 'IVA', 'Total', 'Estado pago', 'Importe pagado', 'Fecha pago', 'Medio pago', 'Saldo', 'Enlace comprobante', 'ID liquidación', 'Observaciones'],
        'col_map': {
            'id_egreso': 'ID egreso',
            'fecha_comprobante': 'Fecha comprobante',
            'fecha_vencimiento': 'Fecha vencimiento',
            'categoria': 'Categoría',
            'subcategoria': 'Subcategoría',
            'proveedor': 'Proveedor',
            'cuit': 'CUIT',
            'tipo_comprobante': 'Tipo comprobante',
            'nro_comprobante': 'Nº comprobante',
            'unidad': 'Unidad',
            'empleado': 'Empleado',
            'descripcion': 'Descripción',
            'cantidad_litros': 'Cantidad/Litros',
            'neto': 'Neto',
            'iva': 'IVA',
            'total': 'Total',
            'estado_pago': 'Estado pago',
            'importe_pagado': 'Importe pagado',
            'fecha_pago': 'Fecha pago',
            'medio_pago': 'Medio pago',
            'saldo': 'Saldo',
            'enlace_comprobante': 'Enlace comprobante',
            'id_liquidacion': 'ID liquidación',
            'observaciones': 'Observaciones'
        }
    },
    'cheques': {
        'table': 'cheques',
        'pk': 'id_cheque',
        'prefix': 'CHQ',
        'headers': ['ID cheque', 'Fecha ingreso', 'Tipo', 'Monto', 'Cliente / Emisor', 'CUIT emisor', 'Banco', 'Nº Cheque', 'Fecha cobro', 'Endosado / Tenedor', 'Estado', 'Destino / Usado en', 'Fecha uso', 'ID egreso', 'ID ingreso origen', 'Observaciones'],
        'col_map': {
            'id_cheque': 'ID cheque',
            'fecha_ingreso': 'Fecha ingreso',
            'tipo': 'Tipo',
            'monto': 'Monto',
            'cliente_emisor': 'Cliente / Emisor',
            'cuit_emisor': 'CUIT emisor',
            'banco': 'Banco',
            'nro_cheque': 'Nº Cheque',
            'fecha_cobro': 'Fecha cobro',
            'endosado_tenedor': 'Endosado / Tenedor',
            'estado': 'Estado',
            'destino_usado_en': 'Destino / Usado en',
            'fecha_uso': 'Fecha uso',
            'id_egreso': 'ID egreso',
            'id_ingreso_origen': 'ID ingreso origen',
            'observaciones': 'Observaciones'
        }
    },
    'ordenes_compra': {
        'table': 'ordenes_compra',
        'pk': 'id_orden',
        'prefix': 'ORD',
        'headers': ['ID orden', 'Fecha', 'Proveedor', 'CUIT proveedor', 'Tipo insumo', 'Unidad', 'Detalle', 'Neto', 'IVA %', 'Total', 'Forma pago', 'Estado', 'Fecha pago', 'ID egreso', 'Observaciones', 'Cantidad/Litros', 'ID cheque', 'Nº cheque'],
        'col_map': {
            'id_orden': 'ID orden',
            'fecha': 'Fecha',
            'proveedor': 'Proveedor',
            'cuit_proveedor': 'CUIT proveedor',
            'tipo_insumo': 'Tipo insumo',
            'unidad': 'Unidad',
            'detalle': 'Detalle',
            'neto': 'Neto',
            'iva_pct': 'IVA %',
            'total': 'Total',
            'forma_pago': 'Forma pago',
            'estado': 'Estado',
            'fecha_pago': 'Fecha pago',
            'id_egreso': 'ID egreso',
            'observaciones': 'Observaciones',
            'cantidad_litros': 'Cantidad/Litros',
            'id_cheque': 'ID cheque',
            'nro_cheque': 'Nº cheque'
        }
    },
    'liquidaciones': {
        'table': 'liquidaciones',
        'pk': 'id_liquidacion',
        'prefix': 'LIQ',
        'headers': ['ID liquidación', 'Fecha confirmación', 'Período quincena', 'ID empleado', 'Empleado', 'Puesto', 'DNI', 'CUIL', 'Entidad bancaria', 'CBU', 'Alias CBU', 'Sueldo fijo base', 'Comisión pct', 'Cant viajes', 'Total comisiones', 'Sueldo final', 'Estado', 'Desglose JSON'],
        'col_map': {
            'id_liquidacion': 'ID liquidación',
            'fecha_confirmacion': 'Fecha confirmación',
            'periodo_quincena': 'Período quincena',
            'id_empleado': 'ID empleado',
            'empleado': 'Empleado',
            'puesto': 'Puesto',
            'dni': 'DNI',
            'cuil': 'CUIL',
            'entidad_bancaria': 'Entidad bancaria',
            'cbu': 'CBU',
            'alias_cbu': 'Alias CBU',
            'sueldo_fijo_base': 'Sueldo fijo base',
            'comision_pct': 'Comisión pct',
            'cant_viajes': 'Cant viajes',
            'total_comisiones': 'Total comisiones',
            'sueldo_final': 'Sueldo final',
            'estado': 'Estado',
            'desglose_json': 'Desglose JSON'
        }
    },
    'cuentas_corrientes': {
        'table': 'cuentas_corrientes',
        'pk': 'id_movimiento',
        'prefix': 'CC',
        'headers': ['ID movimiento', 'Fecha', 'Fecha vencimiento', 'Cliente', 'CUIT', 'Tipo comprobante', 'Referencia ID', 'Concepto', 'Debe', 'Haber', 'Observaciones'],
        'col_map': {
            'id_movimiento': 'ID movimiento',
            'fecha': 'Fecha',
            'fecha_vencimiento': 'Fecha vencimiento',
            'cliente': 'Cliente',
            'cuit': 'CUIT',
            'tipo_comprobante': 'Tipo comprobante',
            'referencia_id': 'Referencia ID',
            'concepto': 'Concepto',
            'debe': 'Debe',
            'haber': 'Haber',
            'observaciones': 'Observaciones'
        }
    },
    'novedades_personal': {
        'table': 'novedades_personal',
        'pk': 'id_novedad',
        'prefix': 'NOV',
        'headers': ['ID novedad', 'Fecha', 'ID empleado', 'Empleado', 'Tipo', 'Concepto', 'Monto', 'Medio pago', 'ID cheque', 'Nº cheque', 'ID liquidacion', 'Estado', 'Observaciones'],
        'col_map': {
            'id_novedad': 'ID novedad',
            'fecha': 'Fecha',
            'id_empleado': 'ID empleado',
            'empleado': 'Empleado',
            'tipo': 'Tipo',
            'concepto': 'Concepto',
            'monto': 'Monto',
            'medio_pago': 'Medio pago',
            'id_cheque': 'ID cheque',
            'nro_cheque': 'Nº cheque',
            'id_liquidacion': 'ID liquidacion',
            'estado': 'Estado',
            'observaciones': 'Observaciones'
        }
    },
    'tesoreria': {
        'table': 'tesoreria_cuentas',
        'pk': 'id_cuenta',
        'prefix': 'CTA',
        'headers': ['ID cuenta', 'Nombre cuenta', 'Tipo', 'Nº Cuenta / CBU / Alias', 'Saldo inicial', 'Saldo real cotejado', 'Fecha ultimo cotejo', 'Observaciones'],
        'col_map': {
            'id_cuenta': 'ID cuenta',
            'nombre_cuenta': 'Nombre cuenta',
            'tipo': 'Tipo',
            'nro_cuenta_cbu_alias': 'Nº Cuenta / CBU / Alias',
            'saldo_inicial': 'Saldo inicial',
            'saldo_real_cotejado': 'Saldo real cotejado',
            'fecha_ultimo_cotejo': 'Fecha ultimo cotejo',
            'observaciones': 'Observaciones'
        }
    },
    'usuarios': {
        'table': 'usuarios',
        'pk': 'id_usuario',
        'prefix': 'USR',
        'headers': ['ID usuario', 'Nombre completo', 'Usuario', 'Password Hash', 'Rol', 'Estado', 'Último acceso'],
        'col_map': {
            'id_usuario': 'ID usuario',
            'nombre_completo': 'Nombre completo',
            'usuario': 'Usuario',
            'password_hash': 'Password Hash',
            'rol': 'Rol',
            'estado': 'Estado',
            'ultimo_acceso': 'Último acceso'
        }
    }
}

class SupabaseService:
    def __init__(self, database_url=None):
        self.db_url = database_url or os.environ.get("DATABASE_URL")
        self.engine = None
        if self.db_url:
            self._init_engine()

    def _init_engine(self):
        url = self.db_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        self.engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )

    def is_connected(self):
        if not self.engine:
            return False
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("SELECT 1")).scalar()
                return res == 1
        except Exception as e:
            print(f"[SUPABASE CONNECTION ERROR] {e}")
            return False

    def _format_val(self, val):
        if val is None:
            return ""
        if isinstance(val, (datetime, date)):
            return val.strftime('%Y-%m-%d')
        if isinstance(val, Decimal):
            return float(val)
        return val

    def get_sheet_data(self, sheet_name):
        key = str(sheet_name).lower().strip()
        mapping = TABLE_MAPPINGS.get(key)
        if not mapping:
            # Fallback for tables without explicit mapping
            return [], []

        table = mapping['table']
        pk = mapping['pk']
        headers = mapping['headers']
        col_map = mapping['col_map']

        query = text(f"SELECT * FROM {table} ORDER BY {pk} ASC")
        rows = []

        with self.engine.connect() as conn:
            result = conn.execute(query)
            for row in result.mappings():
                row_dict = {}
                for k, v in row.items():
                    row_dict[k] = self._format_val(v)
                for col_name, header_name in col_map.items():
                    val = row.get(col_name)
                    if (val is None or val == '' or val == 0) and col_name == 'sueldo_fijo':
                        val = row.get('sueldo_basico') or val
                    if (val is None or val == '') and col_name == 'fecha_inicio':
                        val = row.get('fecha_ingreso') or val
                    row_dict[header_name] = self._format_val(val)
                rows.append(row_dict)

        return headers, rows

    def get_next_id(self, table_name, prefix, pk_col):
        query = text(f"SELECT {pk_col} FROM {table_name} WHERE {pk_col} LIKE :prefix")
        with self.engine.connect() as conn:
            all_ids = [r[0] for r in conn.execute(query, {"prefix": f"{prefix}-%"}).fetchall() if r[0]]
            max_num = 0
            for item in all_ids:
                val = str(item).strip()
                if val.startswith(f"{prefix}-"):
                    parts = val.split('-')
                    last_part = parts[-1]
                    if last_part.isdigit():
                        try:
                            num = int(last_part)
                            if num > max_num:
                                max_num = num
                        except:
                            pass
            return f"{prefix}-{max_num + 1:06d}"

    def execute_query(self, sql_str, params=None):
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_str), params or {})
            if result.returns_rows:
                return [dict(r) for r in result.mappings()]
            conn.commit()
            return []
