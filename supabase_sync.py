"""
=============================================================================
MODULO DE SINCRONIZACIÓN SUPABASE <-> EXCEL (ECONCATIVO)
=============================================================================
Permite sincronización bidireccional en tiempo real:
1. En el arranque: Si existe conexión a Supabase, descarga el estado más
   reciente de la base de datos para garantizar persistencia en la nube
   (evita pérdida de datos por sistemas de archivos efímeros en Render/Railway).
2. En cada guardado: Sincroniza inmediatamente los cambios a Supabase PostgreSQL.
"""

import os
import json
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import text
from supabase_db import TABLE_MAPPINGS

def sync_sheet_to_supabase(engine, sheet_name, headers, rows):
    """Sincroniza una lista de filas de una hoja específica a la tabla de Supabase."""
    if not engine or not rows:
        return

    key = str(sheet_name).lower().strip()
    mapping = TABLE_MAPPINGS.get(key)
    if not mapping:
        return

    table = mapping['table']
    pk = mapping['pk']
    col_map = mapping['col_map'] # db_col -> header_name
    inv_map = {v: k for k, v in col_map.items()} # header_name -> db_col

    # Prepare rows for PostgreSQL
    db_rows = []
    for r in rows:
        row_dict = {}
        for h, val in r.items():
            if h.startswith('_'):
                continue
            # Find matching db_col
            db_col = inv_map.get(h)
            if not db_col:
                # Try normalized match
                norm_h = str(h).lower().replace(' ', '').replace('ó', 'o').replace('á', 'a').replace('é', 'e').replace('í', 'i')
                for k, v in inv_map.items():
                    norm_k = str(k).lower().replace(' ', '').replace('ó', 'o').replace('á', 'a').replace('é', 'e').replace('í', 'i')
                    if norm_h == norm_k:
                        db_col = v
                        break
            
            if db_col:
                # Clean value
                if val == '' or val is None:
                    row_dict[db_col] = None
                else:
                    row_dict[db_col] = val

        if pk in row_dict and row_dict[pk]:
            # Ensure essential text columns have fallback values to prevent NOT NULL violations
            if key == 'clientes' and not row_dict.get('razon_social'):
                row_dict['razon_social'] = f"Cliente {row_dict[pk]}"
            elif key == 'empleados' and not row_dict.get('apellido_nombre'):
                row_dict['apellido_nombre'] = f"Empleado {row_dict[pk]}"
            elif key == 'proveedores' and not row_dict.get('razon_social'):
                row_dict['razon_social'] = f"Proveedor {row_dict[pk]}"
            elif key == 'unidades' and not row_dict.get('dominio_patente'):
                row_dict['dominio_patente'] = str(row_dict[pk])
            db_rows.append(row_dict)

    if not db_rows:
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table}"))
        return

    # Build upsert query
    cols = list(db_rows[0].keys())
    cols_str = ", ".join(cols)
    placeholders = ", ".join([f":{c}" for c in cols])
    update_cols = [f"{c} = EXCLUDED.{c}" for c in cols if c != pk]
    update_str = ", ".join(update_cols)

    sql = f"""
        INSERT INTO {table} ({cols_str})
        VALUES ({placeholders})
        ON CONFLICT ({pk}) DO UPDATE SET {update_str};
    """

    active_pks = [r[pk] for r in db_rows if pk in r and r[pk]]

    with engine.begin() as conn:
        conn.execute(text(sql), db_rows)
        if active_pks:
            del_sql = text(f"DELETE FROM {table} WHERE {pk} NOT IN :active_pks")
            conn.execute(del_sql, {"active_pks": tuple(active_pks)})

def delete_row_from_supabase(engine, sheet_name, pk_val):
    """Elimina explícitamente un registro de Supabase por su clave primaria."""
    if not engine or not pk_val:
        return
    key = str(sheet_name).lower().strip()
    mapping = TABLE_MAPPINGS.get(key)
    if not mapping:
        return
    table = mapping['table']
    pk = mapping['pk']
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table} WHERE {pk} = :pk_val"), {"pk_val": str(pk_val).strip()})


def sync_all_from_supabase_to_wb(engine, wb):
    """Descarga todas las tablas desde Supabase y actualiza las hojas en memoria."""
    if not engine:
        return False

    try:
        with engine.connect() as conn:
            for key, mapping in TABLE_MAPPINGS.items():
                table = mapping['table']
                pk = mapping['pk']
                sheet_name = key.upper()
                headers = mapping['headers']
                col_map = mapping['col_map']

                if sheet_name not in wb.sheetnames:
                    continue

                res = conn.execute(text(f"SELECT * FROM {table} ORDER BY {pk} ASC"))
                rows = [dict(r) for r in res.mappings()]
                if not rows:
                    continue

                ws = wb[sheet_name]
                # Clear existing rows from row 5 onwards
                if ws.max_row >= 5:
                    ws.delete_rows(5, ws.max_row - 4)

                for r_data in rows:
                    row_vals = []
                    for h in headers:
                        # Find corresponding db column
                        db_col = None
                        for c_col, c_header in col_map.items():
                            if c_header == h:
                                db_col = c_col
                                break
                        val = r_data.get(db_col) if db_col else None
                        if isinstance(val, (datetime, date)):
                            val = val.strftime('%Y-%m-%d')
                        elif isinstance(val, Decimal):
                            val = float(val)
                        elif isinstance(val, (dict, list)):
                            val = json.dumps(val, ensure_ascii=False)
                        row_vals.append(val if val is not None else "")
                    ws.append(row_vals)

        return True
    except Exception as e:
        print(f"[SYNC SUPABASE -> EXCEL ERROR] {e}")
        return False
