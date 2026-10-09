import os
import json
import openpyxl
from datetime import datetime, timezone, timedelta
import re
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
    ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:
    ARG_TZ = timezone(timedelta(hours=-3))

def format_datetime_ar(dt_val):
    if not dt_val:
        return '-'
    if isinstance(dt_val, str):
        s = dt_val.strip()
        if not s or s == '-' or s.lower() in ('none', 'null'):
            return '-'
        m_dmy = re.match(r'^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{1,2})(:\d{1,2})?$', s)
        if m_dmy:
            return m_dmy.group(1)
        if len(s) == 10 and s[2] == '/' and s[5] == '/':
            return s
        try:
            dt_val = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            try:
                dt_val = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
            except Exception:
                return s

    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is not None:
            dt_ar = dt_val.astimezone(ARG_TZ)
        else:
            dt_ar = dt_val.replace(tzinfo=timezone.utc).astimezone(ARG_TZ)
        return dt_ar.strftime('%d/%m/%Y %H:%M')

    return str(dt_val)

load_dotenv()

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "operation_data.xlsx")
if not os.path.exists(EXCEL_PATH):
    SCRATCH_EXCEL = r"C:\Users\Usuario\.gemini\antigravity\scratch\operation_data.xlsx"
    if os.path.exists(SCRATCH_EXCEL):
        import shutil
        shutil.copy(SCRATCH_EXCEL, EXCEL_PATH)

# GOOGLE DRIVE CONFIGURATION FOR PRESUPUESTOS PDF
GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_ID = "1dUuP47Qeznou-FGsdUgemOIG8dF6XbJX"
GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_URL = "https://drive.google.com/drive/folders/1dUuP47Qeznou-FGsdUgemOIG8dF6XbJX"

PDF_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "presupuestos_pdf")
if not os.path.exists(PDF_OUTPUT_DIR):
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

class DataManager:
    def __init__(self, excel_path=EXCEL_PATH):
        self.excel_path = excel_path
        self.drive_folder_id = GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_ID
        self.drive_folder_url = GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_URL
        self._wb_cache_data_only = None
        self._wb_cache_mtime = None

        # Supabase connection
        self.supabase_service = None
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            try:
                from supabase_db import SupabaseService
                from supabase_sync import sync_all_from_supabase_to_wb
                self.supabase_service = SupabaseService(db_url)
                if self.supabase_service.is_connected():
                    print("[DataManager] Conexión establecida con Supabase PostgreSQL.")
                    wb = openpyxl.load_workbook(self.excel_path, data_only=False)
                    if sync_all_from_supabase_to_wb(self.supabase_service.engine, wb):
                        wb.save(self.excel_path)
                        print("[DataManager] Sincronización inicial desde Supabase completada.")
            except Exception as e:
                print(f"[DataManager] Advertencia al conectar con Supabase: {e}")

    def _invalidate_cache(self):
        self._wb_cache_data_only = None
        self._wb_cache_mtime = None

    def _on_wb_saved(self, wb):
        # Supabase PostgreSQL is the 100% primary source of truth and all mutations
        # write directly to Supabase with SQL before mirroring to Excel.
        # We do NOT reverse-sync Excel back to Supabase to prevent stale Excel data from overwriting database state.
        pass

    def load_wb(self, data_only=True):
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"No se encuentra el archivo {self.excel_path}")
        
        current_mtime = os.path.getmtime(self.excel_path)
        if data_only:
            if self._wb_cache_data_only is not None and self._wb_cache_mtime == current_mtime:
                return self._wb_cache_data_only
            wb = openpyxl.load_workbook(self.excel_path, data_only=True)
            self._wb_cache_data_only = wb
            self._wb_cache_mtime = current_mtime
            return wb

        self._invalidate_cache()
        wb = openpyxl.load_workbook(self.excel_path, data_only=False)
        orig_save = wb.save
        def wrapped_save(target_path):
            orig_save(target_path)
            # Sincronización asíncrona en segundo plano para no demorar la respuesta web
            import threading
            threading.Thread(target=self._on_wb_saved, args=(wb,), daemon=True).start()
        wb.save = wrapped_save
        return wb

    def _ensure_usuarios_sheet(self, wb):
        if 'USUARIOS' not in wb.sheetnames:
            ws = wb.create_sheet('USUARIOS')
            ws.cell(1, 1, 'USUARIOS Y CREDENCIALES DE ACCESO')
            headers = ['ID usuario', 'Nombre completo', 'Usuario', 'Password Hash', 'Rol', 'Estado', 'Último acceso']
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        return wb['USUARIOS']

    def init_default_users(self):
        """Ensures default user Ailen Avalle exists in USUARIOS sheet with password Ailen.1234."""
        from werkzeug.security import generate_password_hash
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_usuarios_sheet(wb)
            
            has_ailen = False
            for r in range(5, ws.max_row + 1):
                u_val = str(ws.cell(r, 3).value or '').strip().lower()
                n_val = str(ws.cell(r, 2).value or '').strip().lower()
                if u_val in ['ailen', 'ailen.avalle', 'ailen avalle'] or n_val in ['ailen avalle']:
                    has_ailen = True
                    break
                    
            if not has_ailen:
                r = max(5, ws.max_row + 1)
                pwd_hash = generate_password_hash('Ailen.1234')
                ws.cell(r, 1, 'USR-000001')
                ws.cell(r, 2, 'Ailen Avalle')
                ws.cell(r, 3, 'Ailen Avalle')
                ws.cell(r, 4, pwd_hash)
                ws.cell(r, 5, 'Administrador')
                ws.cell(r, 6, 'Activo')
                ws.cell(r, 7, datetime.now(ARG_TZ).strftime('%d/%m/%Y %H:%M'))
                wb.save(self.excel_path)
        except Exception as e:
            print("Error initializing default users:", e)

    def get_usuarios(self):
        """Returns all registered users without password hashes, with Argentine formatted dates."""
        users = []
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    rows = conn.execute(text("""
                        SELECT id_usuario, nombre_completo, usuario, rol, estado, ultimo_acceso, created_at
                        FROM usuarios
                        ORDER BY id_usuario ASC
                    """)).mappings().fetchall()
                    for r in rows:
                        users.append({
                            'id_usuario': str(r.get('id_usuario') or '').strip(),
                            'nombre_completo': str(r.get('nombre_completo') or '').strip(),
                            'usuario': str(r.get('usuario') or '').strip(),
                            'rol': str(r.get('rol') or 'Usuario').strip(),
                            'estado': str(r.get('estado') or 'Activo').strip(),
                            'ultimo_acceso': format_datetime_ar(r.get('ultimo_acceso')),
                            'created_at': format_datetime_ar(r.get('created_at'))
                        })
                    if users:
                        return users
            except Exception as e:
                print(f"[get_usuarios Supabase Error] {e}")

        # Excel fallback
        self.init_default_users()
        wb = self.load_wb(data_only=True)
        if 'USUARIOS' not in wb.sheetnames:
            return []
        ws = wb['USUARIOS']
        for r in range(5, ws.max_row + 1):
            uid = str(ws.cell(r, 1).value or '').strip()
            if not uid:
                continue
            nombre = str(ws.cell(r, 2).value or '').strip()
            uname = str(ws.cell(r, 3).value or '').strip()
            rol = str(ws.cell(r, 5).value or 'Usuario').strip()
            estado = str(ws.cell(r, 6).value or 'Activo').strip()
            u_acc = format_datetime_ar(ws.cell(r, 7).value)
            users.append({
                'id_usuario': uid,
                'nombre_completo': nombre,
                'usuario': uname,
                'rol': rol,
                'estado': estado,
                'ultimo_acceso': u_acc,
                'created_at': '-'
            })
        return users

    def add_usuario(self, data):
        """Registers a new user, hashes password, saves to Supabase and Excel."""
        from werkzeug.security import generate_password_hash
        nombre = str(data.get('nombre_completo') or data.get('nombre', '')).strip()
        uname = str(data.get('usuario', '')).strip()
        pwd = str(data.get('password', '')).strip()
        rol = str(data.get('rol', 'Usuario')).strip()

        if not nombre:
            return {"status": "error", "message": "El nombre completo es obligatorio."}
        if not uname:
            return {"status": "error", "message": "El nombre de usuario (login) es obligatorio."}
        if not pwd or len(pwd) < 4:
            return {"status": "error", "message": "La contraseña debe tener al menos 4 caracteres."}
        if rol != 'Administrador':
            rol = 'Usuario'

        u_clean = uname.lower()

        # Check existing in Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    exists = conn.execute(text("SELECT id_usuario FROM usuarios WHERE LOWER(usuario) = :u"), {'u': u_clean}).fetchone()
                    if exists:
                        return {"status": "error", "message": f"El usuario '{uname}' ya existe en el sistema."}
            except Exception as e:
                print(f"[add_usuario check Supabase Error] {e}")

        # Check existing in Excel
        wb = self.load_wb(data_only=False)
        ws = self._ensure_usuarios_sheet(wb)
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 3).value or '').strip().lower() == u_clean:
                return {"status": "error", "message": f"El usuario '{uname}' ya existe en el sistema."}

        # Generate next ID
        new_id = self._get_next_entity_id(ws, 'USR')
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_usuario FROM usuarios WHERE id_usuario LIKE 'USR-%'")).fetchall()
                    max_num = 0
                    for (uid_val,) in max_id_rows:
                        try:
                            num = int(str(uid_val).split('-')[-1])
                            if num > max_num:
                                max_num = num
                        except Exception:
                            pass
                    wb_num = int(new_id.split('-')[-1]) if '-' in new_id else 0
                    if max_num >= wb_num:
                        new_id = f"USR-{max_num + 1:06d}"
            except Exception as e:
                print(f"[add_usuario Supabase ID Error] {e}")

        pwd_hash = generate_password_hash(pwd)

        # Insert Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO usuarios (id_usuario, nombre_completo, usuario, password_hash, rol, estado, ultimo_acceso, created_at, updated_at)
                        VALUES (:id, :nom, :u, :hash, :rol, 'Activo', NULL, NOW(), NOW())
                        ON CONFLICT (id_usuario) DO UPDATE SET
                            nombre_completo = EXCLUDED.nombre_completo,
                            usuario = EXCLUDED.usuario,
                            password_hash = EXCLUDED.password_hash,
                            rol = EXCLUDED.rol,
                            estado = EXCLUDED.estado,
                            updated_at = NOW()
                    """), {
                        'id': new_id,
                        'nom': nombre,
                        'u': uname,
                        'hash': pwd_hash,
                        'rol': rol
                    })
            except Exception as e:
                print(f"[add_usuario Supabase Insert Error] {e}")

        # Insert Excel
        r = max(5, ws.max_row + 1)
        ws.cell(r, 1, new_id)
        ws.cell(r, 2, nombre)
        ws.cell(r, 3, uname)
        ws.cell(r, 4, pwd_hash)
        ws.cell(r, 5, rol)
        ws.cell(r, 6, 'Activo')
        ws.cell(r, 7, '-')
        wb.save(self.excel_path)

        return {
            "status": "success",
            "message": f"Usuario '{uname}' registrado exitosamente.",
            "data": {
                "id_usuario": new_id,
                "nombre_completo": nombre,
                "usuario": uname,
                "rol": rol,
                "estado": "Activo"
            }
        }

    def update_usuario_password(self, id_usuario, new_password):
        """Updates user password hash in Supabase and Excel."""
        from werkzeug.security import generate_password_hash
        uid = str(id_usuario or '').strip()
        pwd = str(new_password or '').strip()
        if not uid:
            return {"status": "error", "message": "ID de usuario requerido."}
        if not pwd or len(pwd) < 4:
            return {"status": "error", "message": "La nueva contraseña debe tener al menos 4 caracteres."}

        pwd_hash = generate_password_hash(pwd)

        # Update Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE usuarios
                        SET password_hash = :hash, updated_at = NOW()
                        WHERE id_usuario = :uid
                    """), {'hash': pwd_hash, 'uid': uid})
            except Exception as e:
                print(f"[update_usuario_password Supabase Error] {e}")

        # Update Excel
        wb = self.load_wb(data_only=False)
        if 'USUARIOS' in wb.sheetnames:
            ws = wb['USUARIOS']
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip() == uid:
                    ws.cell(r, 4, pwd_hash)
                    wb.save(self.excel_path)
                    break

        return {"status": "success", "message": "Contraseña actualizada exitosamente."}

    def toggle_usuario_estado(self, id_usuario, current_user_id=None):
        """Toggles user status between Activo and Inactivo."""
        uid = str(id_usuario or '').strip()
        if not uid:
            return {"status": "error", "message": "ID de usuario requerido."}
        if current_user_id and uid == current_user_id:
            return {"status": "error", "message": "No puedes desactivar tu propia cuenta en uso."}

        nuevo_estado = 'Activo'

        # Get current status & toggle
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    row = conn.execute(text("SELECT estado, rol FROM usuarios WHERE id_usuario = :uid"), {'uid': uid}).mappings().fetchone()
                    if row:
                        curr = str(row.get('estado') or 'Activo').strip()
                        nuevo_estado = 'Inactivo' if curr.lower() == 'activo' else 'Activo'
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("UPDATE usuarios SET estado = :est, updated_at = NOW() WHERE id_usuario = :uid"), {'est': nuevo_estado, 'uid': uid})
            except Exception as e:
                print(f"[toggle_usuario_estado Supabase Error] {e}")

        wb = self.load_wb(data_only=False)
        if 'USUARIOS' in wb.sheetnames:
            ws = wb['USUARIOS']
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip() == uid:
                    curr = str(ws.cell(r, 6).value or 'Activo').strip()
                    nuevo_estado = 'Inactivo' if curr.lower() == 'activo' else 'Activo'
                    ws.cell(r, 6, nuevo_estado)
                    wb.save(self.excel_path)
                    break

        return {"status": "success", "message": f"Estado del usuario cambiado a {nuevo_estado}.", "nuevo_estado": nuevo_estado}

    def delete_usuario(self, id_usuario, current_user_id=None):
        """Deletes user from Supabase and Excel."""
        uid = str(id_usuario or '').strip()
        if not uid:
            return {"status": "error", "message": "ID de usuario requerido."}
        if current_user_id and uid == current_user_id:
            return {"status": "error", "message": "No puedes eliminar tu propia cuenta en uso."}

        # Supabase delete
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("DELETE FROM usuarios WHERE id_usuario = :uid"), {'uid': uid})
            except Exception as e:
                print(f"[delete_usuario Supabase Error] {e}")

        # Excel delete
        wb = self.load_wb(data_only=False)
        if 'USUARIOS' in wb.sheetnames:
            ws = wb['USUARIOS']
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip() == uid:
                    target_row = r
                    break
            if target_row:
                ws.delete_rows(target_row, 1)
                wb.save(self.excel_path)

        return {"status": "success", "message": "Usuario eliminado correctamente."}

    def authenticate_user(self, username, password):
        """Authenticates user against Supabase PostgreSQL (with Excel fallback). Returns dict user info or None."""
        from werkzeug.security import check_password_hash
        if not username or not password:
            return None

        u_clean = str(username).strip().lower()

        # 1. Supabase Master Authentication
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    users = conn.execute(text("SELECT id_usuario, nombre_completo, usuario, password_hash, rol, estado FROM usuarios WHERE LOWER(estado) = 'activo'")).mappings().fetchall()
                    for u in users:
                        uid = str(u.get('id_usuario') or '').strip()
                        nombre = str(u.get('nombre_completo') or '').strip()
                        uname = str(u.get('usuario') or '').strip()
                        pwd_hash = str(u.get('password_hash') or '').strip()
                        rol = str(u.get('rol') or 'Administrador').strip()

                        match_username = (
                            u_clean == uname.lower() or
                            u_clean == nombre.lower() or
                            u_clean == uname.lower().replace(' ', '') or
                            u_clean == nombre.lower().replace(' ', '.') or
                            (u_clean == 'ailen' and 'ailen' in nombre.lower())
                        )
                        if match_username and check_password_hash(pwd_hash, str(password).strip()):
                            try:
                                with self.supabase_service.engine.begin() as upd_conn:
                                    upd_conn.execute(text("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id_usuario = :uid"), {'uid': uid})
                            except Exception:
                                pass
                            return {
                                'id': uid or 'USR-000001',
                                'nombre': nombre or 'Ailen Avalle',
                                'usuario': uname or username,
                                'rol': rol or 'Administrador'
                            }
            except Exception as e:
                print(f"[authenticate_user Supabase Error] {e}")

        # 2. Excel Fallback
        self.init_default_users()
        wb = self.load_wb(data_only=True)
        if 'USUARIOS' not in wb.sheetnames:
            return None
            
        ws = wb['USUARIOS']
        for r in range(5, ws.max_row + 1):
            uid = str(ws.cell(r, 1).value or '').strip()
            nombre = str(ws.cell(r, 2).value or '').strip()
            uname = str(ws.cell(r, 3).value or '').strip()
            pwd_hash = str(ws.cell(r, 4).value or '').strip()
            rol = str(ws.cell(r, 5).value or 'Administrador').strip()
            estado = str(ws.cell(r, 6).value or 'Activo').strip()
            
            match_username = (
                u_clean == uname.lower() or
                u_clean == nombre.lower() or
                u_clean == uname.lower().replace(' ', '') or
                u_clean == nombre.lower().replace(' ', '.') or
                (u_clean == 'ailen' and 'ailen' in nombre.lower())
            )
            
            if match_username and estado.lower() == 'activo':
                if check_password_hash(pwd_hash, str(password).strip()):
                    return {
                        'id': uid or 'USR-000001',
                        'nombre': nombre or 'Ailen Avalle',
                        'usuario': uname or username,
                        'rol': rol or 'Administrador'
                    }
        return None

    def _ensure_presupuestos_sheet(self, wb):
        if 'PRESUPUESTOS' not in wb.sheetnames:
            ws = wb.create_sheet('PRESUPUESTOS')
            ws.cell(1, 1, 'PRESUPUESTOS Y COTIZACIONES')
            ws.cell(2, 1, 'Gestión comercial en cascada')
            headers = ['ID presupuesto', 'Fecha', 'Cliente', 'CUIT', 'Tipo servicio', 'Detalle/Concepto', 'Total', 'IVA %', 'Validez', 'Forma pago', 'Estado', 'ID viaje asociado', 'Observaciones', 'Items JSON']
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        else:
            ws = wb['PRESUPUESTOS']
            if ws.cell(4, 14).value != 'Items JSON':
                ws.cell(4, 14, 'Items JSON')
        return wb['PRESUPUESTOS']

    def _read_sheet_rows(self, ws, start_row=5):
        raw_headers = [str(ws.cell(4, col).value or '').strip() for col in range(1, ws.max_column + 1)]
        
        data = []
        for r in range(start_row, ws.max_row + 1):
            row_data = {}
            has_val = False
            for col_idx, h in enumerate(raw_headers, 1):
                if not h:
                    continue
                val = ws.cell(r, col_idx).value
                if val is not None:
                    has_val = True
                    if isinstance(val, (datetime,)):
                        val = val.strftime('%Y-%m-%d')
                row_data[h] = val if val is not None else ""
            if has_val and any(str(v).strip() for v in row_data.values()):
                row_data['_row_idx'] = r
                data.append(row_data)
        
        clean_headers = [h for h in raw_headers if h]
        return clean_headers, data

    def get_presupuestos(self):
        if self.supabase_service and self.supabase_service.is_connected():
            headers, rows = self.supabase_service.get_sheet_data('presupuestos')
            if headers or rows:
                return headers, rows
        wb = self.load_wb(data_only=True)
        ws = self._ensure_presupuestos_sheet(wb)
        return self._read_sheet_rows(ws)

    def _get_next_presupuesto_id(self, ws):
        max_num = 0
        for r in range(5, ws.max_row + 1):
            val = str(ws.cell(r, 1).value or '').strip()
            if val.startswith('PRE-'):
                try:
                    num = int(val.replace('PRE-', ''))
                    if num > max_num:
                        max_num = num
                except:
                    pass
        return f"PRE-{max_num + 1:06d}"

    def add_presupuesto(self, pdata):
        import json
        wb = self.load_wb(data_only=False)
        ws = self._ensure_presupuestos_sheet(wb)
        new_id = self._get_next_presupuesto_id(ws)
        
        items = pdata.get('items', [])
        if items:
            total = sum(float(it.get('neto', 0)) for it in items)
            if len(items) > 1:
                tipo_servicio = f"Multi-Actividad ({len(items)} ítems)"
                detalle_parts = []
                for i, it in enumerate(items, 1):
                    t_op = it.get('tipo', 'Servicio')
                    act = it.get('actividad', '')
                    n_amt = float(it.get('neto', 0))
                    detalle_parts.append(f"[{i}] {t_op}: {act} (${n_amt:,.2f})")
                detalle_summary = " // ".join(detalle_parts)
            else:
                it = items[0]
                tipo_servicio = it.get('tipo', 'Viaje')
                detalle_summary = pdata.get('detalle') or it.get('descripcion') or it.get('detalle_trabajo') or 'Cotización de Servicio'
            items_json = json.dumps(items, ensure_ascii=False)
        else:
            total = float(pdata.get('total', 0))
            tipo_servicio = pdata.get('tipo_servicio', 'Viaje')
            detalle_summary = pdata.get('detalle', '')
            items_json = ''

        raw_iva_p = pdata.get('iva_pct')
        iva_pct = float(raw_iva_p) if (raw_iva_p is not None and str(raw_iva_p).strip() != '') else 21.0

        comb_mod = pdata.get('modalidad_combustible', '')
        obs = pdata.get('observaciones', '')
        if comb_mod and comb_mod not in obs:
            obs = f"[{comb_mod}] {obs}".strip()

        fecha_val = pdata.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        cliente_val = pdata.get('cliente', '')
        cuit_val = pdata.get('cuit', '')
        validez_val = pdata.get('validez', '15 días')
        forma_pago_val = pdata.get('forma_pago', 'Cuenta Corriente')
        estado_val = pdata.get('estado', 'Pendiente')
        id_viaje_val = pdata.get('id_viaje_asociado', '')

        row_vals = [
            new_id,
            fecha_val,
            cliente_val,
            cuit_val,
            tipo_servicio,
            detalle_summary,
            total,
            iva_pct,
            validez_val,
            forma_pago_val,
            estado_val,
            id_viaje_val,
            obs,
            items_json
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO presupuestos (
                            id_presupuesto, fecha, cliente, cuit, tipo_servicio,
                            detalle_concepto, total, iva_pct, validez, forma_pago,
                            estado, id_viaje_asociado, observaciones, items_json,
                            created_at, updated_at
                        ) VALUES (
                            :id, :fecha, :cliente, :cuit, :tipo_servicio,
                            :detalle_concepto, :total, :iva_pct, :validez, :forma_pago,
                            :estado, :id_viaje_asociado, :observaciones, :items_json,
                            NOW(), NOW()
                        )
                        ON CONFLICT (id_presupuesto) DO UPDATE SET
                            fecha = EXCLUDED.fecha,
                            cliente = EXCLUDED.cliente,
                            cuit = EXCLUDED.cuit,
                            tipo_servicio = EXCLUDED.tipo_servicio,
                            detalle_concepto = EXCLUDED.detalle_concepto,
                            total = EXCLUDED.total,
                            iva_pct = EXCLUDED.iva_pct,
                            validez = EXCLUDED.validez,
                            forma_pago = EXCLUDED.forma_pago,
                            estado = EXCLUDED.estado,
                            id_viaje_asociado = EXCLUDED.id_viaje_asociado,
                            observaciones = EXCLUDED.observaciones,
                            items_json = EXCLUDED.items_json,
                            updated_at = NOW();
                    """), {
                        'id': new_id,
                        'fecha': fecha_val,
                        'cliente': cliente_val,
                        'cuit': cuit_val,
                        'tipo_servicio': tipo_servicio,
                        'detalle_concepto': detalle_summary,
                        'total': total,
                        'iva_pct': iva_pct,
                        'validez': validez_val,
                        'forma_pago': forma_pago_val,
                        'estado': estado_val,
                        'id_viaje_asociado': id_viaje_val,
                        'observaciones': obs,
                        'items_json': items_json
                    })
            except Exception as e:
                print(f"[add_presupuesto Supabase Error] {e}")

        return {"status": "success", "id": new_id}

    def update_presupuesto(self, p_id, pdata):
        import json
        wb = self.load_wb(data_only=False)
        ws = self._ensure_presupuestos_sheet(wb)
        
        target_row = None
        current_status = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(p_id).strip():
                target_row = r
                current_status = str(ws.cell(r, 11).value or '').strip()
                break
        
        if not target_row:
            return {"status": "error", "message": f"Presupuesto {p_id} no encontrado."}

        if current_status.lower() == 'aprobado':
            return {"status": "error", "message": f"El Presupuesto {p_id} ya fue APROBADO y no se puede modificar para preservar la integridad del proceso."}

        items = pdata.get('items', [])
        if items:
            total = sum(float(it.get('neto', 0)) for it in items)
            if len(items) > 1:
                tipo_servicio = f"Multi-Actividad ({len(items)} ítems)"
                detalle_parts = []
                for i, it in enumerate(items, 1):
                    t_op = it.get('tipo', 'Servicio')
                    act = it.get('actividad', '')
                    n_amt = float(it.get('neto', 0))
                    detalle_parts.append(f"[{i}] {t_op}: {act} (${n_amt:,.2f})")
                detalle_summary = " // ".join(detalle_parts)
            else:
                it = items[0]
                tipo_servicio = it.get('tipo', 'Viaje')
                detalle_summary = pdata.get('detalle') or it.get('descripcion') or it.get('detalle_trabajo') or 'Cotización de Servicio'
            items_json = json.dumps(items, ensure_ascii=False)
            
            ws.cell(target_row, 5, tipo_servicio)
            ws.cell(target_row, 6, detalle_summary)
            ws.cell(target_row, 7, total)
            ws.cell(target_row, 14, items_json)
        else:
            if 'tipo_servicio' in pdata: ws.cell(target_row, 5, pdata['tipo_servicio'])
            if 'detalle' in pdata: ws.cell(target_row, 6, pdata['detalle'])
            if 'total' in pdata: ws.cell(target_row, 7, float(pdata['total']))
            tipo_servicio = ws.cell(target_row, 5).value
            detalle_summary = ws.cell(target_row, 6).value
            total = float(ws.cell(target_row, 7).value or 0)
            items_json = ws.cell(target_row, 14).value or ''

        cliente_val = pdata.get('cliente', ws.cell(target_row, 3).value)
        cuit_val = pdata.get('cuit', ws.cell(target_row, 4).value)
        ws.cell(target_row, 3, cliente_val)
        ws.cell(target_row, 4, cuit_val)
        raw_upd_iva = pdata.get('iva_pct')
        if raw_upd_iva is not None and str(raw_upd_iva).strip() != '':
            iva_pct = float(raw_upd_iva)
            ws.cell(target_row, 8, iva_pct)
        elif ws.cell(target_row, 8).value is None or str(ws.cell(target_row, 8).value).strip() == '':
            iva_pct = 21.0
            ws.cell(target_row, 8, 21.0)
        else:
            iva_pct = float(ws.cell(target_row, 8).value or 21.0)
        validez_val = pdata.get('validez', ws.cell(target_row, 9).value)
        forma_pago_val = pdata.get('forma_pago', ws.cell(target_row, 10).value)
        ws.cell(target_row, 9, validez_val)
        ws.cell(target_row, 10, forma_pago_val)
        if 'estado' in pdata:
            ws.cell(target_row, 11, pdata['estado'])
        if 'id_viaje_asociado' in pdata:
            ws.cell(target_row, 12, pdata['id_viaje_asociado'])
        if 'observaciones' in pdata:
            ws.cell(target_row, 13, pdata['observaciones'])

        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE presupuestos SET
                            cliente = :cliente,
                            cuit = :cuit,
                            tipo_servicio = :tipo_servicio,
                            detalle_concepto = :detalle_concepto,
                            total = :total,
                            iva_pct = :iva_pct,
                            validez = :validez,
                            forma_pago = :forma_pago,
                            observaciones = :observaciones,
                            items_json = :items_json,
                            updated_at = NOW()
                        WHERE id_presupuesto = :id;
                    """), {
                        'id': p_id,
                        'cliente': cliente_val,
                        'cuit': cuit_val,
                        'tipo_servicio': tipo_servicio,
                        'detalle_concepto': detalle_summary,
                        'total': total,
                        'iva_pct': iva_pct,
                        'validez': validez_val,
                        'forma_pago': forma_pago_val,
                        'observaciones': ws.cell(target_row, 13).value or '',
                        'items_json': items_json
                    })
            except Exception as e:
                print(f"[update_presupuesto Supabase Error] {e}")

        return {"status": "success", "id": p_id}

    def delete_presupuesto(self, p_id):
        wb = self.load_wb(data_only=False)
        ws = self._ensure_presupuestos_sheet(wb)
        
        target_row = None
        assoc_viaje_id = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(p_id).strip():
                target_row = r
                assoc_viaje_id = ws.cell(r, 12).value
                break
        
        if not target_row:
            return {"status": "error", "message": f"Presupuesto {p_id} no encontrado."}

        ws.delete_rows(target_row)

        if assoc_viaje_id:
            ws_v = wb['VIAJES']
            for rv in range(5, ws_v.max_row + 1):
                if str(ws_v.cell(rv, 1).value or '').strip() == str(assoc_viaje_id).strip():
                    ws_v.delete_rows(rv)
                    break
            if self.supabase_service and self.supabase_service.is_connected():
                from supabase_sync import delete_row_from_supabase
                delete_row_from_supabase(self.supabase_service.engine, 'VIAJES', assoc_viaje_id)

        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'PRESUPUESTOS', p_id)

        return {"status": "success", "id": p_id}

    def delete_viaje(self, viaje_id):
        wb = self.load_wb(data_only=False)
        ws = wb['VIAJES']
        
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(viaje_id).strip():
                target_row = r
                break
        
        if not target_row:
            if self.supabase_service and self.supabase_service.is_connected():
                from supabase_sync import delete_row_from_supabase
                delete_row_from_supabase(self.supabase_service.engine, 'VIAJES', viaje_id)
                return {"status": "success", "id": viaje_id}
            return {"status": "error", "message": f"Registro {viaje_id} no encontrado."}

        ws.delete_rows(target_row)
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'VIAJES', viaje_id)

        return {"status": "success", "id": viaje_id}

    def _save_pdf_file(self, p_id, status_label):
        """Generates and saves the final official PDF to the Drive folder upon APROBADO or RECHAZADO."""
        try:
            from pdf_generator import generate_presupuesto_pdf
            headers, rows = self.get_presupuestos()
            target = None
            for r in rows:
                if str(r.get('ID presupuesto', '')).strip() == str(p_id).strip():
                    target = r
                    break
            if not target:
                return
            
            pdata = {
                "id": p_id,
                "fecha": target.get('Fecha', ''),
                "cliente": target.get('Cliente', 'Cliente'),
                "cuit": target.get('CUIT', ''),
                "validez": target.get('Validez', '15 días'),
                "forma_pago": target.get('Forma pago', 'Cuenta Corriente'),
                "detalle": target.get('Detalle/Concepto', 'Servicio Cotizado'),
                "total": float(target.get('Total', 0)),
                "iva_pct": float(target.get('IVA %', 21)),
                "observaciones": target.get('Observaciones', '')
            }

            pdf_bytes = generate_presupuesto_pdf(pdata)
            
            cliente_sanitized = "".join(c for c in str(pdata['cliente']) if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            filename = f"{p_id}_{cliente_sanitized}_{status_label.upper()}.pdf"
            file_path = os.path.join(PDF_OUTPUT_DIR, filename)

            with open(file_path, 'wb') as f:
                f.write(pdf_bytes)

            print(f"[GOOGLE DRIVE PRESUPUESTOS] Guardado PDF oficial en carpeta {GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_ID}: {file_path}")
            return file_path
        except Exception as e:
            print(f"[ERROR GOOGLE DRIVE PRESUPUESTOS] {e}")

    def aprobar_presupuesto(self, p_id):
        import json
        wb = self.load_wb(data_only=False)
        ws = self._ensure_presupuestos_sheet(wb)
        
        target_row = None
        p_row_data = {}
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(p_id).strip():
                target_row = r
                p_row_data = {
                    'cliente': ws.cell(r, 3).value,
                    'tipo_servicio': ws.cell(r, 5).value,
                    'detalle': ws.cell(r, 6).value,
                    'total': ws.cell(r, 7).value,
                    'estado': ws.cell(r, 11).value,
                    'viaje_id': ws.cell(r, 12).value,
                    'items_json': ws.cell(r, 14).value or ws.cell(r, 12).value
                }
                break
        
        if not target_row:
            return {"status": "error", "message": f"Presupuesto {p_id} no encontrado."}

        # Strictly prevent duplicate approval!
        if str(p_row_data.get('estado', '')).strip().lower() == 'aprobado':
            existing_viaje = str(p_row_data.get('viaje_id', '')).strip()
            return {
                "status": "success", 
                "message": f"El Presupuesto {p_id} ya fue Aprobado anteriormente.", 
                "id": p_id, 
                "viaje_id": existing_viaje or "OK"
            }

        ws.cell(target_row, 11, 'Aprobado')
        
        ws_v = wb['VIAJES']
        # Calculate next trip ID by scanning highest VIA- or SRV- number
        max_v_num = 0
        for rv in range(5, ws_v.max_row + 1):
            v_val = str(ws_v.cell(rv, 1).value or '').strip()
            if '-' in v_val:
                try:
                    num = int(v_val.split('-')[-1])
                    if num > max_v_num:
                        max_v_num = num
                except:
                    pass
        
        tipo_op = "Servicio" if str(p_row_data.get('tipo_servicio', '')).lower() == 'servicio' else "Viaje"
        prefix = "VIA" if tipo_op == "Viaje" else "SRV"
        if self.supabase_service and self.supabase_service.is_connected():
            viaje_id = self.supabase_service.get_next_id('viajes', prefix, 'id_viaje')
        else:
            viaje_id = f"{prefix}-{max_v_num + 1:06d}"

        ws.cell(target_row, 12, viaje_id)

        # Parse items to extract real route, km, tons, total
        items = []
        raw_items = p_row_data.get('items_json') or ''
        if str(raw_items).strip().startswith('['):
            try:
                items = json.loads(str(raw_items).strip())
            except Exception:
                items = []

        final_origen = ''
        final_destino = ''
        km_sum = 0
        ton_sum = 0
        cargas = []
        
        for it in items:
            if it.get('origen') and not final_origen:
                final_origen = str(it.get('origen')).strip()
            if it.get('destino') and not final_destino:
                final_destino = str(it.get('destino')).strip()
            if it.get('ubicacion') and not final_origen:
                final_origen = str(it.get('ubicacion')).strip()
                final_destino = str(it.get('ubicacion')).strip()
            try:
                if it.get('km'):
                    km_sum += float(it.get('km'))
            except Exception:
                pass
            try:
                if it.get('toneladas'):
                    ton_sum += float(it.get('toneladas'))
            except Exception:
                pass
            c_desc = it.get('descripcion') or it.get('subtipo_granel') or it.get('detalle_trabajo')
            if c_desc and c_desc not in cargas:
                cargas.append(str(c_desc).strip())

        if not final_origen:
            final_origen = 'POR DEFINIR'
        if not final_destino:
            final_destino = 'POR DEFINIR'

        carga_text = " // ".join(cargas) if cargas else str(p_row_data.get('detalle') or '')
        total_val = float(p_row_data.get('total') or 0)

        row_v_vals = [
            viaje_id,
            datetime.now().strftime('%Y-%m-%d'),
            '',
            'POR ASIGNAR',
            'POR ASIGNAR',
            final_origen,
            final_destino,
            p_row_data.get('cliente', ''),
            p_row_data.get('tipo_servicio', 'Transporte'),
            f"[PRESUPUESTO APROBADO {p_id}] {carga_text}",
            '',
            'PENDIENTE',
            0,
            '',
            km_sum if km_sum > 0 else None,
            ton_sum if ton_sum > 0 else None,
            0,
            0,
            0,
            total_val,
            'Pendiente',
            '',
            f"Presupuesto {p_id}"
        ]
        ws_v.append(row_v_vals)
        wb.save(self.excel_path)

        # Sync to Supabase if connected
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    # Update Presupuesto in Supabase
                    conn.execute(text("""
                        UPDATE presupuestos 
                        SET estado = 'Aprobado', id_viaje_asociado = :vid, updated_at = NOW()
                        WHERE id_presupuesto = :pid
                    """), {'vid': viaje_id, 'pid': p_id})

                    # Insert Viaje in Supabase
                    conn.execute(text("""
                        INSERT INTO viajes (
                            id_viaje, fecha_salida, chofer, unidad, origen, destino,
                            cliente, actividad, carga, cpe, km_inicial, km_recorridos,
                            toneladas, adelanto, valor_servicio, estado_facturacion,
                            observaciones, created_at, updated_at
                        ) VALUES (
                            :vid, :fecha, 'POR ASIGNAR', 'POR ASIGNAR', :origen, :destino,
                            :cliente, :actividad, :carga, 'PENDIENTE', 0, :km,
                            :ton, 0, :valor, 'Pendiente',
                            :obs, NOW(), NOW()
                        )
                        ON CONFLICT (id_viaje) DO UPDATE SET
                            origen = EXCLUDED.origen,
                            destino = EXCLUDED.destino,
                            cliente = EXCLUDED.cliente,
                            actividad = EXCLUDED.actividad,
                            carga = EXCLUDED.carga,
                            km_recorridos = EXCLUDED.km_recorridos,
                            toneladas = EXCLUDED.toneladas,
                            valor_servicio = EXCLUDED.valor_servicio,
                            updated_at = NOW();
                    """), {
                        'vid': viaje_id,
                        'fecha': datetime.now().strftime('%Y-%m-%d'),
                        'origen': final_origen,
                        'destino': final_destino,
                        'cliente': p_row_data.get('cliente', ''),
                        'actividad': p_row_data.get('tipo_servicio', 'Transporte'),
                        'carga': f"[PRESUPUESTO APROBADO {p_id}] {carga_text}",
                        'km': km_sum if km_sum > 0 else None,
                        'ton': ton_sum if ton_sum > 0 else None,
                        'valor': total_val,
                        'obs': f"Presupuesto de origen: {p_id}"
                    })
            except Exception as e:
                print(f"[aprobar_presupuesto Supabase Error] {e}")

        pdf_saved_path = self._save_pdf_file(p_id, 'APROBADO')
        return {"status": "success", "id": p_id, "viaje_id": viaje_id, "pdf_path": pdf_saved_path, "drive_url": GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_URL}

    def rechazar_presupuesto(self, p_id):
        wb = self.load_wb(data_only=False)
        ws = self._ensure_presupuestos_sheet(wb)
        
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(p_id).strip():
                target_row = r
                break
        
        if not target_row:
            return {"status": "error", "message": f"Presupuesto {p_id} no encontrado."}

        ws.cell(target_row, 11, 'Rechazado')
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE presupuestos 
                        SET estado = 'Rechazado', updated_at = NOW()
                        WHERE id_presupuesto = :pid
                    """), {'pid': p_id})
            except Exception as e:
                print(f"[rechazar_presupuesto Supabase Error] {e}")

        pdf_saved_path = self._save_pdf_file(p_id, 'RECHAZADO')
        return {"status": "success", "id": p_id, "pdf_path": pdf_saved_path, "drive_url": GOOGLE_DRIVE_PRESUPUESTOS_FOLDER_URL}

    def add_viaje(self, vdata):
        wb = self.load_wb(data_only=False)
        ws = wb['VIAJES']
        next_v_row = ws.max_row + 1
        tipo_op = vdata.get('tipo_operacion', 'Viaje')
        prefix = "VIA" if tipo_op == "Viaje" else "SRV"
        if self.supabase_service and self.supabase_service.is_connected():
            viaje_id = self.supabase_service.get_next_id('viajes', prefix, 'id_viaje')
        else:
            viaje_id = f"{prefix}-{next_v_row - 4:06d}"

        origen = vdata.get('origen') or vdata.get('ubicacion') or ''
        destino = vdata.get('destino') or vdata.get('ubicacion') or origen
        carga = vdata.get('tipo_carga') or vdata.get('carga') or vdata.get('detalle_trabajo') or ''

        km_or_hs = ''
        if vdata.get('km_totales'):
            km_or_hs = f"{vdata['km_totales']} km"
        elif vdata.get('horas_trabajo'):
            km_or_hs = f"{vdata['horas_trabajo']} hs"

        row_vals = [
            viaje_id,
            datetime.now().strftime('%Y-%m-%d'),
            '',
            vdata.get('chofer', 'POR ASIGNAR'),
            vdata.get('unidad', 'POR ASIGNAR'),
            origen or 'POR DEFINIR',
            destino or 'POR DEFINIR',
            vdata.get('cliente', ''),
            tipo_op,
            carga,
            vdata.get('remito', ''),
            vdata.get('cpe', ''),
            0,
            km_or_hs or 'COMPLETADO'
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO viajes (
                            id_viaje, fecha_salida, chofer, unidad, origen, destino,
                            cliente, actividad, carga, nro_remito, cpe,
                            km_inicial, valor_servicio, estado_facturacion,
                            observaciones, created_at, updated_at
                        ) VALUES (
                            :vid, :fecha, :chofer, :unidad, :origen, :destino,
                            :cliente, :actividad, :carga, :remito, :cpe,
                            0, 0, 'Pendiente',
                            :obs, NOW(), NOW()
                        )
                        ON CONFLICT (id_viaje) DO UPDATE SET
                            chofer = EXCLUDED.chofer,
                            unidad = EXCLUDED.unidad,
                            origen = EXCLUDED.origen,
                            destino = EXCLUDED.destino,
                            updated_at = NOW();
                    """), {
                        'vid': viaje_id,
                        'fecha': datetime.now().strftime('%Y-%m-%d'),
                        'chofer': vdata.get('chofer', 'POR ASIGNAR'),
                        'unidad': vdata.get('unidad', 'POR ASIGNAR'),
                        'origen': origen or 'POR DEFINIR',
                        'destino': destino or 'POR DEFINIR',
                        'cliente': vdata.get('cliente', ''),
                        'actividad': tipo_op,
                        'carga': carga,
                        'remito': vdata.get('remito', ''),
                        'cpe': vdata.get('cpe', ''),
                        'obs': km_or_hs or 'COMPLETADO'
                    })
            except Exception as e:
                print(f"[add_viaje Supabase Error] {e}")

        return {"status": "success", "id": viaje_id}

    def update_viaje(self, v_id, vdata):
        wb = self.load_wb(data_only=False)
        ws = wb['VIAJES']
        
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(v_id).strip():
                target_row = r
                break
        
        if not target_row and not (self.supabase_service and self.supabase_service.is_connected()):
            return {"status": "error", "message": f"Registro {v_id} no encontrado."}

        chofer = str(vdata.get('chofer', '')).strip()
        unidad = str(vdata.get('unidad', '')).strip()
        origen = str(vdata.get('origen') or vdata.get('ubicacion') or '').strip()
        destino = str(vdata.get('destino') or vdata.get('ubicacion') or '').strip()
        cliente = str(vdata.get('cliente', '')).strip()
        carga = str(vdata.get('tipo_carga') or vdata.get('carga') or vdata.get('detalle_trabajo') or '').strip()
        km = str(vdata.get('km_totales', '')).strip()
        hs = str(vdata.get('horas_trabajo', '')).strip()

        if target_row:
            if chofer:
                ws.cell(target_row, 4, chofer)
            if unidad:
                ws.cell(target_row, 5, unidad)
            if origen:
                ws.cell(target_row, 6, origen)
            if destino:
                ws.cell(target_row, 7, destino)
            if cliente:
                ws.cell(target_row, 8, cliente)
            if carga:
                ws.cell(target_row, 10, carga)
            if vdata.get('fecha_salida') or vdata.get('fecha'): ws.cell(target_row, 2, vdata.get('fecha_salida') or vdata.get('fecha'))
            if vdata.get('remito'): ws.cell(target_row, 11, vdata['remito'])
            if vdata.get('cpe'): ws.cell(target_row, 12, vdata['cpe'])
            if vdata.get('toneladas'): ws.cell(target_row, 16, vdata['toneladas'])
            if vdata.get('observaciones'): ws.cell(target_row, 23, vdata['observaciones'])

            if km and km != '0':
                val_str = f"{km} km" if not km.endswith('km') else km
                ws.cell(target_row, 14, val_str)
            elif hs and hs != '0':
                val_str = f"{hs} hs" if not hs.endswith('hs') else hs
                ws.cell(target_row, 14, val_str)
            else:
                cur_chofer = str(ws.cell(target_row, 4).value or '').strip()
                cur_unidad = str(ws.cell(target_row, 5).value or '').strip()
                if cur_chofer and cur_chofer != 'POR ASIGNAR' and cur_unidad and cur_unidad != 'POR ASIGNAR':
                    cur_14 = str(ws.cell(target_row, 14).value or '').strip()
                    if not cur_14 or 'PENDIENTE' in cur_14:
                        ws.cell(target_row, 14, 'COMPLETADO')

            wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE viajes SET
                            chofer = COALESCE(NULLIF(:chofer, ''), chofer),
                            unidad = COALESCE(NULLIF(:unidad, ''), unidad),
                            origen = COALESCE(NULLIF(:origen, ''), origen),
                            destino = COALESCE(NULLIF(:destino, ''), destino),
                            fecha_salida = COALESCE(CAST(NULLIF(:fecha_salida, '') AS date), fecha_salida),
                            nro_remito = COALESCE(NULLIF(:remito, ''), nro_remito),
                            cpe = COALESCE(NULLIF(:cpe, ''), cpe),
                            toneladas = COALESCE(CAST(NULLIF(:toneladas, '') AS numeric), toneladas),
                            km_recorridos = COALESCE(CAST(NULLIF(:km, '') AS numeric), km_recorridos),
                            observaciones = COALESCE(NULLIF(:obs, ''), observaciones),
                            updated_at = NOW()
                        WHERE id_viaje = :vid;
                    """), {
                        'vid': v_id,
                        'chofer': chofer or None,
                        'unidad': unidad or None,
                        'origen': origen or None,
                        'destino': destino or None,
                        'fecha_salida': str(vdata.get('fecha_salida') or vdata.get('fecha') or '').strip() or None,
                        'remito': str(vdata.get('remito') or '').strip() or None,
                        'cpe': str(vdata.get('cpe') or '').strip() or None,
                        'toneladas': str(vdata.get('toneladas') or '').strip() or None,
                        'km': str(km).replace('km','').strip() if km and km != '0' else None,
                        'obs': str(vdata.get('observaciones') or '').strip() or None
                    })
            except Exception as e:
                print(f"[update_viaje Supabase Error] {e}")

        return {"status": "success", "id": v_id}

    def get_viaje_by_id(self, v_id):
        """Retrieves single trip/service row dictionary by ID."""
        headers, rows = self.get_sheet_data('VIAJES')
        for r in rows:
            if str(r.get('ID viaje', '')).strip() == str(v_id).strip():
                return r
        return None

    def finalizar_viaje(self, v_id):
        """Marks operational trip/service as FINALIZADO and pushes to INGRESOS / FACTURACION using Supabase as master."""
        import re
        v_id_clean = str(v_id).strip()
        v_data = {}
        target_row = None

        # 1. Supabase First: Load trip operational status
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    v_res = conn.execute(text("SELECT * FROM viajes WHERE id_viaje = :vid"), {'vid': v_id_clean}).fetchone()
                    if v_res:
                        v_map = dict(v_res._mapping)
                        v_data = {
                            'cliente': v_map.get('cliente') or 'Cliente',
                            'chofer': v_map.get('chofer') or '-',
                            'unidad': v_map.get('unidad') or '-',
                            'actividad': v_map.get('actividad') or 'Viaje',
                            'carga': v_map.get('carga') or '',
                            'km_hs': v_map.get('km_recorridos') or 'COMPLETADO',
                            'estado_facturacion': v_map.get('estado_facturacion') or 'Pendiente',
                            'ingreso_id': v_map.get('id_ingreso_factura') or '',
                            'valor_servicio': float(v_map.get('valor_servicio') or 0)
                        }
            except Exception as e:
                print(f"[finalizar_viaje Supabase fetch error] {e}")

        # Fallback or synchronize with Excel
        wb = None
        ws_v = None
        try:
            wb = self.load_wb(data_only=False)
            ws_v = wb['VIAJES']
            for r in range(5, ws_v.max_row + 1):
                if str(ws_v.cell(r, 1).value or '').strip() == v_id_clean:
                    target_row = r
                    if not v_data:
                        v_data = {
                            'cliente': ws_v.cell(r, 8).value,
                            'chofer': ws_v.cell(r, 4).value,
                            'unidad': ws_v.cell(r, 5).value,
                            'actividad': ws_v.cell(r, 9).value,
                            'carga': ws_v.cell(r, 10).value,
                            'km_hs': ws_v.cell(r, 14).value,
                            'estado_facturacion': ws_v.cell(r, 21).value,
                            'ingreso_id': ws_v.cell(r, 22).value,
                            'valor_servicio': float(ws_v.cell(r, 20).value or 0)
                        }
                    break
        except Exception as e:
            print(f"[finalizar_viaje Excel load error] {e}")

        if not v_data and not target_row:
            return {"status": "error", "message": f"Registro {v_id} no encontrado."}

        # 2. Look up originating budget data & extras (Supabase first)
        assoc_pdata = {}
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    p_res = conn.execute(text("""
                        SELECT id_presupuesto, cliente, cuit, total, iva_pct, detalle_concepto
                        FROM presupuestos
                        WHERE id_viaje_asociado = :vid
                        ORDER BY id_presupuesto DESC LIMIT 1
                    """), {'vid': v_id_clean}).fetchone()
                    if not p_res and v_data.get('carga'):
                        m = re.search(r'(PRE-\d+)', str(v_data.get('carga')))
                        if m:
                            p_res = conn.execute(text("""
                                SELECT id_presupuesto, cliente, cuit, total, iva_pct, detalle_concepto
                                FROM presupuestos
                                WHERE id_presupuesto = :pid
                            """), {'pid': m.group(1)}).fetchone()
                    if p_res:
                        p_map = dict(p_res._mapping)
                        assoc_pdata = {
                            'cliente': p_map.get('cliente'),
                            'cuit': p_map.get('cuit'),
                            'total': float(p_map.get('total') or 0),
                            'iva_pct': float(p_map.get('iva_pct') or 21.0),
                            'detalle': p_map.get('detalle_concepto')
                        }
            except Exception as e:
                print(f"[finalizar_viaje Supabase presupuesto fetch error] {e}")

        if not assoc_pdata and wb and 'PRESUPUESTOS' in wb.sheetnames:
            ws_p = wb['PRESUPUESTOS']
            for rp in range(5, ws_p.max_row + 1):
                p_viaje_id = str(ws_p.cell(rp, 12).value or '').strip()
                p_id = str(ws_p.cell(rp, 1).value or '').strip()
                carga_str = str(v_data.get('carga', ''))
                if p_viaje_id == v_id_clean or (p_id and p_id in carga_str):
                    assoc_pdata = {
                        'cliente': ws_p.cell(rp, 3).value,
                        'cuit': ws_p.cell(rp, 4).value,
                        'total': ws_p.cell(rp, 7).value or 0,
                        'iva_pct': float(ws_p.cell(rp, 8).value) if (ws_p.cell(rp, 8).value is not None and str(ws_p.cell(rp, 8).value).strip() != '') else 21.0,
                        'detalle': ws_p.cell(rp, 6).value
                    }
                    break

        summary = self.get_viaje_facturacion_summary(v_id_clean)
        if summary:
            neto = float(summary.get('subtotal_neto', 0))
            if summary.get('cuit') and not assoc_pdata.get('cuit'):
                assoc_pdata['cuit'] = summary.get('cuit')
        else:
            neto = float(assoc_pdata.get('total') or v_data.get('valor_servicio') or 0)

        raw_ap_iva = assoc_pdata.get('iva_pct')
        iva_pct = float(raw_ap_iva) if (raw_ap_iva is not None and str(raw_ap_iva).strip() != '') else 21.0
        iva_amt = neto * (iva_pct / 100.0)
        total = neto + iva_amt
        cliente = assoc_pdata.get('cliente') or v_data.get('cliente') or 'Cliente'
        tot_adelantos = float(summary.get('tot_adelantos', 0)) if summary else 0.0
        saldo_pendiente = max(0.0, total - tot_adelantos)

        # 3. Resolve existing or new Ingreso ID
        ingreso_id = str(v_data.get('ingreso_id') or '').strip()
        if ingreso_id.startswith('ING-'):
            # Validate that this ingreso actually belongs to this viaje
            if self.supabase_service and self.supabase_service.is_connected():
                from sqlalchemy import text
                try:
                    with self.supabase_service.engine.connect() as conn:
                        chk = conn.execute(text("SELECT observaciones FROM ingresos WHERE id_ingreso = :iid"), {'iid': ingreso_id}).fetchone()
                        if chk:
                            chk_obs = str(chk[0] or '')
                            if f"Operación origen: {v_id_clean}" not in chk_obs and "Operación origen: VIA-" in chk_obs:
                                # This ingreso belongs to a different trip! Reset so we don't hijack it.
                                ingreso_id = ''
                        else:
                            ingreso_id = ''
                except Exception as e:
                    print(f"[finalizar_viaje validate ingreso error] {e}")
            elif wb and 'INGRESOS' in wb.sheetnames:
                ws_i_chk = wb['INGRESOS']
                found_match = False
                for r in range(5, ws_i_chk.max_row + 1):
                    if str(ws_i_chk.cell(r, 1).value or '').strip() == ingreso_id:
                        obs_val = str(ws_i_chk.cell(r, 28).value or '')
                        if f"Operación origen: {v_id_clean}" in obs_val or "Operación origen: VIA-" not in obs_val:
                            found_match = True
                        break
                if not found_match:
                    ingreso_id = ''

        if not ingreso_id.startswith('ING-'):
            if self.supabase_service and self.supabase_service.is_connected():
                from sqlalchemy import text
                try:
                    with self.supabase_service.engine.connect() as conn:
                        existing_ing = conn.execute(text("""
                            SELECT id_ingreso FROM ingresos 
                            WHERE observaciones LIKE :obs_pattern 
                            ORDER BY id_ingreso DESC LIMIT 1
                        """), {
                            'obs_pattern': f'%Operación origen: {v_id_clean}%'
                        }).fetchone()
                        if existing_ing:
                            ingreso_id = existing_ing[0]
                except Exception as e:
                    print(f"[finalizar_viaje find existing ingreso error] {e}")
            elif wb and 'INGRESOS' in wb.sheetnames:
                ws_i_chk = wb['INGRESOS']
                for r in range(5, ws_i_chk.max_row + 1):
                    obs_val = str(ws_i_chk.cell(r, 28).value or '')
                    if f"Operación origen: {v_id_clean}" in obs_val:
                        ingreso_id = str(ws_i_chk.cell(r, 1).value or '').strip()
                        break

        if not ingreso_id or not ingreso_id.startswith('ING-'):
            if self.supabase_service and self.supabase_service.is_connected():
                ingreso_id = self.supabase_service.get_next_id('ingresos', 'ING', 'id_ingreso')
            elif wb and 'INGRESOS' in wb.sheetnames:
                ingreso_id = self._get_next_entity_id(wb['INGRESOS'], 'ING')
            else:
                ingreso_id = f"ING-{datetime.now().strftime('%f')[:6]}"

        obs_ingreso = f"Operación origen: {v_id_clean}"
        if tot_adelantos > 0:
            obs_ingreso += f" | Señas/Adelantos cobrados previamente: ${tot_adelantos:,.2f}"
        if summary and summary.get('adicionales'):
            extra_descs = [f"{a.get('concepto')} (${float(a.get('monto',0)):,.2f})" for a in summary['adicionales']]
            obs_ingreso += f" | Incluye Extras: {'; '.join(extra_descs)}"

        # 4. Master Transaction: Supabase PostgreSQL
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    # 1. Update viajes table in Supabase
                    conn.execute(text("""
                        UPDATE viajes SET
                            estado_facturacion = 'En Facturación',
                            id_ingreso_factura = :ing_id,
                            updated_at = NOW()
                        WHERE id_viaje = :vid;
                    """), {'ing_id': ingreso_id, 'vid': v_id_clean})

                    # 2. Insert or update ingresos table in Supabase
                    conn.execute(text("""
                        INSERT INTO ingresos (
                            id_ingreso, fecha_emision, tipo_comprobante, punto_venta,
                            nro_factura_arca, cliente, cuit_cuil, actividad, chofer, unidad,
                            neto, iva_pct, iva, total, estado_cobro, importe_cobrado,
                            saldo, observaciones, created_at, updated_at
                        ) VALUES (
                            :id_ingreso, CAST(:fecha_emision AS date), :tipo_comprobante, :punto_venta,
                            :nro_factura_arca, :cliente, :cuit_cuil, :actividad, :chofer, :unidad,
                            :neto, :iva_pct, :iva, :total, :estado_cobro, :importe_cobrado,
                            :saldo, :observaciones, NOW(), NOW()
                        )
                        ON CONFLICT (id_ingreso) DO UPDATE SET
                            cliente = EXCLUDED.cliente,
                            cuit_cuil = EXCLUDED.cuit_cuil,
                            actividad = EXCLUDED.actividad,
                            chofer = EXCLUDED.chofer,
                            unidad = EXCLUDED.unidad,
                            neto = EXCLUDED.neto,
                            iva_pct = EXCLUDED.iva_pct,
                            iva = EXCLUDED.iva,
                            total = EXCLUDED.total,
                            saldo = GREATEST(0.0, EXCLUDED.total - COALESCE(ingresos.importe_cobrado, 0.0)),
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id_ingreso': ingreso_id,
                        'fecha_emision': datetime.now().strftime('%Y-%m-%d'),
                        'tipo_comprobante': 'Factura A',
                        'punto_venta': '0001',
                        'nro_factura_arca': 'PENDIENTE DE FACTURA',
                        'cliente': cliente,
                        'cuit_cuil': str(assoc_pdata.get('cuit') or '').strip() or None,
                        'actividad': str(v_data.get('actividad') or 'Viaje').strip(),
                        'chofer': str(v_data.get('chofer') or '').strip(),
                        'unidad': str(v_data.get('unidad') or '').strip(),
                        'neto': neto,
                        'iva_pct': iva_pct,
                        'iva': iva_amt,
                        'total': total,
                        'estado_cobro': 'PENDIENTE DE FACTURA',
                        'importe_cobrado': 0.0,
                        'saldo': saldo_pendiente,
                        'observaciones': obs_ingreso
                    })
            except Exception as e:
                print(f"[finalizar_viaje Supabase Error] {e}")
                raise e

        # 5. Mirror to Excel gracefully
        if wb and target_row:
            try:
                curr_km = str(v_data.get('km_hs', 'COMPLETADO') or '').replace('(FINALIZADO)', '').strip()
                if '(FINALIZADO)' not in str(ws_v.cell(target_row, 14).value or ''):
                    ws_v.cell(target_row, 14, f"{curr_km} (FINALIZADO)")
                ws_v.cell(target_row, 21, 'En Facturación')
                ws_v.cell(target_row, 22, ingreso_id)

                if 'INGRESOS' in wb.sheetnames:
                    ws_i = wb['INGRESOS']
                    target_i_row = None
                    for r in range(5, ws_i.max_row + 1):
                        if str(ws_i.cell(r, 1).value or '').strip() == ingreso_id:
                            target_i_row = r
                            break
                    if not target_i_row:
                        target_i_row = ws_i.max_row + 1

                    row_i_dict = {
                        1: ingreso_id,
                        2: datetime.now().strftime('%Y-%m-%d'),
                        3: 'Factura A',
                        4: '0001',
                        5: ws_i.cell(target_i_row, 5).value or 'PENDIENTE DE FACTURA',
                        6: cliente,
                        7: assoc_pdata.get('cuit', ''),
                        8: v_data.get('actividad', ''),
                        9: v_data.get('chofer', ''),
                        10: v_data.get('unidad', ''),
                        13: neto,
                        14: iva_pct,
                        15: iva_amt,
                        16: total,
                        17: ws_i.cell(target_i_row, 17).value or 'PENDIENTE DE FACTURA',
                        18: ws_i.cell(target_i_row, 18).value or 0,
                        21: saldo_pendiente,
                        28: obs_ingreso
                    }
                    for col_idx, col_val in row_i_dict.items():
                        ws_i.cell(target_i_row, col_idx, col_val)

                wb.save(self.excel_path)
                self._invalidate_cache()
            except Exception as excel_err:
                print(f"[finalizar_viaje Excel mirror warning] {excel_err}")

        return {"status": "success", "id": v_id_clean, "ingreso_id": ingreso_id}

    def add_ingreso_factura(self, idata):
        """Creates a new ARCA invoice / income directly in Supabase and mirrors to Excel."""
        from datetime import datetime
        
        # 1. Generate Next ID
        ingreso_id = None
        if self.supabase_service and self.supabase_service.is_connected():
            ingreso_id = self.supabase_service.get_next_id('ingresos', 'ING', 'id_ingreso')
        
        if not ingreso_id:
            try:
                wb = self.load_wb(data_only=True)
                ws_i = wb['INGRESOS']
                max_n = 0
                for r in range(5, ws_i.max_row + 1):
                    val = str(ws_i.cell(r, 1).value or '').strip()
                    if val.startswith('ING-'):
                        try:
                            n = int(val.split('-')[-1])
                            if n > max_n:
                                max_n = n
                        except:
                            pass
                ingreso_id = f"ING-{max_n + 1:06d}"
            except Exception:
                ingreso_id = f"ING-{int(datetime.now().timestamp()):06d}"

        nro = str(idata.get('nro_factura', '')).strip().upper()
        tipo = str(idata.get('tipo_comprobante', '')).strip() or 'Factura A'
        if nro == 'COMPROBANTE-INTERNO' or 'No Fiscal' in tipo or 'Sin Factura' in tipo:
            est_cobro = 'PENDIENTE MEDIO DE PAGO'
            nro = 'COMPROBANTE-INTERNO'
        else:
            est_cobro = 'Pendiente de Cobro' if (nro and 'PENDIENTE' not in nro) else 'PENDIENTE DE FACTURA'

        neto_val = float(idata['neto']) if idata.get('neto') else 0.0
        pct_val = float(idata.get('iva_pct', 21)) if idata.get('iva_pct') is not None else 21.0
        iva_amt = round(neto_val * (pct_val / 100.0), 2)
        total_val = round(neto_val + iva_amt, 2)
        cliente = str(idata.get('cliente', '')).strip()
        fecha_emision = str(idata.get('fecha_emision', '')).strip() or datetime.now().strftime('%Y-%m-%d')
        actividad = str(idata.get('actividad', '')).strip() or 'Facturación Directa'
        obs = str(idata.get('observaciones', '')).strip() or 'Factura creada directamente'

        punto_venta = '0001'
        if '-' in nro and nro != 'COMPROBANTE-INTERNO':
            pv_part = nro.split('-')[0].strip()
            if pv_part:
                punto_venta = pv_part.zfill(4)

        cuit = str(idata.get('cuit_cuil', '')).strip() or None
        if not cuit and cliente and self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    res = conn.execute(text("SELECT cuit_cuil FROM clientes WHERE LOWER(TRIM(razon_social)) = LOWER(TRIM(:cli)) LIMIT 1"), {'cli': cliente}).fetchone()
                    if res and res[0]:
                        cuit = res[0]
            except Exception as e:
                print(f"[add_ingreso_factura client CUIT lookup error] {e}")

        # 1. Supabase Master Insert
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ingresos (
                            id_ingreso, fecha_emision, tipo_comprobante, punto_venta,
                            nro_factura_arca, cliente, cuit_cuil, actividad,
                            neto, iva_pct, iva, total, estado_cobro, importe_cobrado,
                            saldo, observaciones, created_at, updated_at
                        ) VALUES (
                            :iid, CAST(:fecha AS date), :tipo, :punto_venta,
                            :nro, :cliente, :cuit, :actividad,
                            :neto, :iva_pct, :iva, :total, :est_cobro, 0.0,
                            :saldo, :obs, NOW(), NOW()
                        );
                    """), {
                        'iid': ingreso_id,
                        'fecha': fecha_emision,
                        'tipo': tipo,
                        'punto_venta': punto_venta,
                        'nro': nro,
                        'cliente': cliente,
                        'cuit': cuit,
                        'actividad': actividad,
                        'neto': neto_val,
                        'iva_pct': pct_val,
                        'iva': iva_amt,
                        'total': total_val,
                        'est_cobro': est_cobro,
                        'saldo': total_val,
                        'obs': obs
                    })
            except Exception as e:
                print(f"[add_ingreso_factura Supabase Error] {e}")
                return {"status": "error", "message": f"Error al guardar en base de datos: {e}"}

        # 2. Mirror to Excel
        try:
            wb = self.load_wb(data_only=False)
            for sheet_name in ['INGRESOS', 'FACTURACION']:
                if sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    target_row = ws.max_row + 1
                    row_dict = {
                        1: ingreso_id,
                        2: fecha_emision,
                        3: tipo,
                        4: punto_venta,
                        5: nro,
                        6: cliente,
                        7: cuit or '',
                        8: actividad,
                        13: neto_val,
                        14: pct_val,
                        15: iva_amt,
                        16: total_val,
                        17: est_cobro,
                        18: 0.0,
                        21: total_val,
                        28: obs
                    }
                    for col_idx, col_val in row_dict.items():
                        ws.cell(target_row, col_idx, col_val)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as excel_err:
            print(f"[add_ingreso_factura Excel warning] {excel_err}")

        return {"status": "success", "id": ingreso_id, "message": "Factura guardada con éxito"}

    def update_ingreso_factura(self, i_id, idata):
        """Updates ARCA invoice details for an INGRESOS row directly in Supabase."""
        i_id_clean = str(i_id).strip()
        
        nro = str(idata.get('nro_factura', '')).strip().upper()
        tipo = str(idata.get('tipo_comprobante', '')).strip()
        if nro == 'COMPROBANTE-INTERNO' or 'No Fiscal' in tipo or 'Sin Factura' in tipo:
            est_cobro = 'PENDIENTE MEDIO DE PAGO'
        else:
            est_cobro = 'Pendiente de Cobro'

        neto_val = float(idata['neto']) if idata.get('neto') else None
        pct_val = float(idata.get('iva_pct', 21)) if idata.get('neto') else None
        iva_amt = (neto_val * (pct_val / 100.0)) if neto_val is not None else None
        total_val = (neto_val + iva_amt) if neto_val is not None else None

        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE ingresos SET
                            nro_factura_arca = COALESCE(NULLIF(:nro, ''), nro_factura_arca),
                            tipo_comprobante = COALESCE(NULLIF(:tipo, ''), tipo_comprobante),
                            cliente = COALESCE(NULLIF(:cliente, ''), cliente),
                            fecha_emision = COALESCE(CAST(NULLIF(:fecha, '') AS date), fecha_emision),
                            neto = COALESCE(:neto, neto),
                            iva_pct = COALESCE(:iva_pct, iva_pct),
                            iva = COALESCE(:iva, iva),
                            total = COALESCE(:total, total),
                            saldo = COALESCE(:total, saldo),
                            estado_cobro = :est_cobro,
                            updated_at = NOW()
                        WHERE id_ingreso = :iid;
                    """), {
                        'iid': i_id_clean,
                        'nro': idata.get('nro_factura'),
                        'tipo': idata.get('tipo_comprobante'),
                        'cliente': idata.get('cliente'),
                        'fecha': idata.get('fecha_emision'),
                        'neto': neto_val,
                        'iva_pct': pct_val,
                        'iva': iva_amt,
                        'total': total_val,
                        'est_cobro': est_cobro
                    })
            except Exception as e:
                print(f"[update_ingreso_factura Supabase Error] {e}")

        # 2. Mirror to Excel
        try:
            wb = self.load_wb(data_only=False)
            for sheet_name in ['INGRESOS', 'FACTURACION']:
                if sheet_name in wb.sheetnames:
                    ws_i = wb[sheet_name]
                    target_row = None
                    for r in range(5, ws_i.max_row + 1):
                        if str(ws_i.cell(r, 1).value or '').strip() == i_id_clean:
                            target_row = r
                            break

                    if target_row:
                        if idata.get('nro_factura'):
                            ws_i.cell(target_row, 5, idata['nro_factura'])
                        if idata.get('fecha_emision'):
                            ws_i.cell(target_row, 2, idata['fecha_emision'])
                        if idata.get('tipo_comprobante'):
                            ws_i.cell(target_row, 3, idata['tipo_comprobante'])
                        if idata.get('cliente'):
                            ws_i.cell(target_row, 6, idata['cliente'])
                        if neto_val is not None:
                            ws_i.cell(target_row, 13, neto_val)
                            ws_i.cell(target_row, 14, pct_val)
                            ws_i.cell(target_row, 15, iva_amt)
                            ws_i.cell(target_row, 16, total_val)
                            ws_i.cell(target_row, 21, total_val)
                        ws_i.cell(target_row, 17, est_cobro)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as excel_err:
            print(f"[update_ingreso_factura Excel warning] {excel_err}")

        return {"status": "success", "id": i_id_clean}

    def pasar_a_ingresos(self, i_id):
        """Transfers a billed operation from Facturación to Ingresos (state: PENDIENTE MEDIO DE PAGO)."""
        i_id_clean = str(i_id).strip()

        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE ingresos SET
                            estado_cobro = 'PENDIENTE MEDIO DE PAGO',
                            updated_at = NOW()
                        WHERE id_ingreso = :iid;
                    """), {'iid': i_id_clean})
            except Exception as e:
                print(f"[pasar_a_ingresos Supabase Error] {e}")

        # 2. Mirror to Excel
        try:
            wb = self.load_wb(data_only=False)
            for sheet_name in ['INGRESOS', 'FACTURACION']:
                if sheet_name in wb.sheetnames:
                    ws_i = wb[sheet_name]
                    for r in range(5, ws_i.max_row + 1):
                        if str(ws_i.cell(r, 1).value or '').strip() == i_id_clean:
                            ws_i.cell(r, 17, 'PENDIENTE MEDIO DE PAGO')
                            break
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as excel_err:
            print(f"[pasar_a_ingresos Excel warning] {excel_err}")

        return {"status": "success", "id": i_id_clean}

    @staticmethod
    def _to_float(v, default=0.0):
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace('$', '').replace(' ', '')
        if not s:
            return default
        if ',' in s and '.' in s:
            if s.rfind('.') > s.rfind(','):
                s = s.replace(',', '')
            else:
                s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return default

    @staticmethod
    def _clean_int(val):
        if val is None:
            return None
        s = re.sub(r'\D', '', str(val))
        return int(s) if s else None

    @staticmethod
    def _clean_date(val):
        if not val:
            return None
        s = str(val).strip()
        if not s or s.lower() in ['none', 'null', '-']:
            return None
        try:
            if '-' in s and len(s.split('-')[0]) == 4:
                return s[:10]
            if '/' in s:
                p = s.split('/')
                if len(p) == 3 and len(p[2][:4]) == 4:
                    return f"{p[2][:4]}-{int(p[1]):02d}-{int(p[0]):02d}"
            if '-' in s:
                p = s.split('-')
                if len(p) == 3 and len(p[2][:4]) == 4:
                    return f"{p[2][:4]}-{int(p[1]):02d}-{int(p[0]):02d}"
            return s[:10]
        except Exception:
            return None

    @staticmethod
    def _is_adelanto_entry(r):
        if isinstance(r, dict):
            tipo = str(r.get('Tipo comprobante') or r.get('Tipo') or '').strip().lower()
            conc = str(r.get('Concepto') or r.get('Detalle') or '').strip().lower()
        else:
            tipo = str(getattr(r, 'tipo', '') or '').strip().lower()
            conc = str(getattr(r, 'concepto', '') or '').strip().lower()
        if any(w in tipo for w in ['adelanto', 'seña', 'sena', 'entrega', 'pago a cuenta', 'cobro cc', 'vuelto', 'reintegro']):
            return True
        if any(w in conc for w in ['seña', 'sena', 'adelanto', 'entrega', 'pago a cuenta', 'vuelto', 'reintegro']):
            return True
        return False

    def registrar_cobro_ingreso(self, i_id, cdata):
        """Registers payment for an invoice in INGRESOS with support for combined payment methods and direct Supabase sync."""
        i_id_clean = str(i_id).strip()
        wb = self.load_wb(data_only=False)
        ws_i = wb['INGRESOS']
        
        target_row = None
        for r in range(5, ws_i.max_row + 1):
            if str(ws_i.cell(r, 1).value or '').strip() == i_id_clean:
                target_row = r
                break

        fecha_cobro = cdata.get('fecha_cobro') or datetime.now().strftime('%Y-%m-%d')
        
        m_transf = self._to_float(cdata.get('monto_transferencia'))
        m_echeq = self._to_float(cdata.get('monto_echeq'))
        m_cheque = self._to_float(cdata.get('monto_cheque'))
        m_efectivo = self._to_float(cdata.get('monto_efectivo'))
        m_tarjeta = self._to_float(cdata.get('monto_tarjeta'))
        m_saldo_favor = self._to_float(cdata.get('monto_saldo_favor'))

        # Normalize cheques list (support multiple cheques / e-cheqs)
        cheques_raw = cdata.get('cheques')
        processed_cheques_input = []
        if isinstance(cheques_raw, list) and len(cheques_raw) > 0:
            for ch in cheques_raw:
                m = self._to_float(ch.get('monto'))
                if m > 0:
                    t = str(ch.get('tipo') or 'Cheque Físico').strip()
                    if 'e-cheq' in t.lower() or 'echeq' in t.lower():
                        t = 'E-Cheq'
                    else:
                        t = 'Cheque Físico'
                    processed_cheques_input.append({
                        'tipo': t,
                        'monto': m,
                        'nro': str(ch.get('nro') or ch.get('nro_cheque') or '').strip(),
                        'banco': str(ch.get('banco') or ch.get('banco_cheque') or 'A completar').strip(),
                        'fecha_venc': str(ch.get('fecha_venc') or ch.get('vencimiento') or fecha_cobro).strip()
                    })
        else:
            # Legacy fallback: single cheque / e-cheq
            if m_cheque > 0:
                processed_cheques_input.append({
                    'tipo': 'Cheque Físico',
                    'monto': m_cheque,
                    'nro': str(cdata.get('nro_cheque') or '').strip(),
                    'banco': str(cdata.get('banco_cheque') or cdata.get('banco') or 'A completar').strip(),
                    'fecha_venc': str(cdata.get('fecha_venc_cheque') or cdata.get('vencimiento') or fecha_cobro).strip()
                })
            if m_echeq > 0:
                processed_cheques_input.append({
                    'tipo': 'E-Cheq',
                    'monto': m_echeq,
                    'nro': str(cdata.get('nro_echeq') or cdata.get('nro_cheque') or '').strip(),
                    'banco': str(cdata.get('banco_echeq') or cdata.get('banco') or 'A completar').strip(),
                    'fecha_venc': str(cdata.get('fecha_venc_echeq') or cdata.get('vencimiento') or fecha_cobro).strip()
                })

        total_cheques = sum(ch['monto'] for ch in processed_cheques_input)
        total_dinero_nuevo = m_transf + m_efectivo + m_tarjeta + total_cheques
        total_cobrado_ingresado = total_dinero_nuevo + m_saldo_favor
        
        # Build description of combined payment methods
        medios_list = []
        if m_saldo_favor > 0: medios_list.append(f"Saldo a Favor C/C: ${m_saldo_favor:,.2f}")
        if m_transf > 0: medios_list.append(f"Transferencia: ${m_transf:,.2f}")
        if m_efectivo > 0: medios_list.append(f"Efectivo: ${m_efectivo:,.2f}")
        if m_tarjeta > 0: medios_list.append(f"Tarjeta: ${m_tarjeta:,.2f}")
        for ch in processed_cheques_input:
            ch_tipo = ch['tipo']
            ch_monto = ch['monto']
            ch_nro = ch['nro']
            ch_banco = ch['banco']
            detalles = []
            if ch_nro: detalles.append(f"N° {ch_nro}")
            if ch_banco and ch_banco != 'A completar': detalles.append(ch_banco)
            det_str = f" ({', '.join(detalles)})" if detalles else ""
            medios_list.append(f"{ch_tipo}{det_str}: ${ch_monto:,.2f}")
        
        medio_str = " | ".join(medios_list) if medios_list else cdata.get('medio_cobro', 'Transferencia')
        cuenta_dest = cdata.get('cuenta_destino') or cdata.get('cuenta_tesoreria') or ''
        if cuenta_dest and (m_transf > 0 or total_cheques > 0 or m_efectivo > 0 or m_tarjeta > 0):
            medio_str = f"{medio_str} - {cuenta_dest}" if cuenta_dest.lower() not in medio_str.lower() else medio_str
        
        # Fetch current record values from Supabase or Excel
        total_factura = 0.0
        prev_cobrado = 0.0
        prev_estado = ''
        prev_medio = ''
        obs_current = ''
        existing_rec = ''

        cliente_actual = ''
        cuit_actual = ''

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    s_row = conn.execute(text("SELECT cliente, cuit_cuil, total, importe_cobrado, estado_cobro, medio_cobro, observaciones, id_acuerdo FROM ingresos WHERE id_ingreso = :iid"), {'iid': i_id_clean}).fetchone()
                    if s_row:
                        sm = dict(s_row._mapping)
                        cliente_actual = str(sm.get('cliente') or '').strip()
                        cuit_actual = str(sm.get('cuit_cuil') or '').strip()
                        total_factura = float(sm.get('total') or 0.0)
                        prev_cobrado = float(sm.get('importe_cobrado') or 0.0)
                        prev_estado = str(sm.get('estado_cobro') or '').strip()
                        prev_medio = str(sm.get('medio_cobro') or '').strip()
                        obs_current = str(sm.get('observaciones') or '').strip()
                        existing_rec = str(sm.get('id_acuerdo') or '').strip()
            except Exception as e:
                print(f"[registrar_cobro_ingreso Supabase fetch error] {e}")

        if not total_factura and target_row:
            cliente_actual = cliente_actual or str(ws_i.cell(target_row, 6).value or '').strip()
            cuit_actual = cuit_actual or str(ws_i.cell(target_row, 7).value or '').strip()
            total_factura = self._to_float(ws_i.cell(target_row, 16).value)
            prev_cobrado = self._to_float(ws_i.cell(target_row, 18).value)
            prev_estado = str(ws_i.cell(target_row, 17).value or '').strip()
            prev_medio = str(ws_i.cell(target_row, 20).value or '').strip()
            obs_current = str(ws_i.cell(target_row, 28).value or '').strip()
            existing_rec = str(ws_i.cell(target_row, 22).value or '').strip()

        cliente_final = str(cdata.get('cliente') or cliente_actual).strip()
        cuit_final = str(cdata.get('cuit') or cuit_actual).strip()

        tot_adelantos = 0.0
        if 'Señas/Adelantos cobrados previamente:' in obs_current:
            match = re.search(r'Señas\/Adelantos cobrados previamente:\s*\$?([\d\.,]+)', obs_current)
            if match:
                raw_str = match.group(1).strip()
                if ',' in raw_str and '.' in raw_str:
                    if raw_str.rfind('.') > raw_str.rfind(','):
                        raw_str = raw_str.replace(',', '')
                    else:
                        raw_str = raw_str.replace('.', '').replace(',', '.')
                elif ',' in raw_str:
                    raw_str = raw_str.replace(',', '.')
                try:
                    tot_adelantos = float(raw_str)
                except Exception:
                    tot_adelantos = 0.0

        if 'parcial' in prev_estado.lower() and total_cobrado_ingresado > 0:
            importe_final = prev_cobrado + total_dinero_nuevo
        else:
            importe_final = total_dinero_nuevo if total_cobrado_ingresado > 0 else self._to_float(cdata.get('importe_cobrado'), total_factura)

        total_cobrado_acumulado = importe_final + m_saldo_favor + tot_adelantos
        saldo = max(0.0, total_factura - total_cobrado_acumulado)

        if prev_medio and 'parcial' in prev_estado.lower() and medio_str not in prev_medio:
            combined_medio = f"{prev_medio} + {medio_str}"
        else:
            combined_medio = medio_str

        # Recibo ID resolution
        recibo_id = existing_rec if existing_rec and existing_rec.startswith('REC-') else None
        if not recibo_id:
            if self.supabase_service and self.supabase_service.is_connected():
                recibo_id = self.supabase_service.get_next_id('ingresos', 'REC', 'id_acuerdo')
            elif target_row:
                recibo_id = f"REC-{target_row - 4:06d}"
            else:
                recibo_id = f"REC-{datetime.now().strftime('%f')[:6]}"

        nuevo_estado = 'COBRADO' if saldo <= 0.01 else 'Cobrado Parcial'
        new_obs = obs_current
        if cdata.get('observaciones'):
            cobro_note = f"Cobro: {cdata['observaciones']}".strip()
            if cobro_note not in new_obs:
                new_obs = f"{new_obs} | {cobro_note}".strip(' |')

        created_cheques = []
        cc_mov_id = None

        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE ingresos SET
                            importe_cobrado = :imp_cobrado,
                            fecha_cobro = CAST(:fecha_cobro AS date),
                            medio_cobro = :medio_cobro,
                            saldo = :saldo,
                            estado_cobro = :estado_cobro,
                            id_acuerdo = :recibo_id,
                            observaciones = :observaciones,
                            updated_at = NOW()
                        WHERE id_ingreso = :iid;
                    """), {
                        'iid': i_id_clean,
                        'imp_cobrado': total_cobrado_acumulado,
                        'fecha_cobro': fecha_cobro,
                        'medio_cobro': combined_medio,
                        'saldo': saldo,
                        'estado_cobro': nuevo_estado,
                        'recibo_id': recibo_id,
                        'observaciones': new_obs
                    })

                    # If Saldo a Favor applied, deduct/debit from cuentas_corrientes in Supabase
                    if m_saldo_favor > 0 and cliente_final:
                        cc_mov_id = self.supabase_service.get_next_id('cuentas_corrientes', 'CC', 'id_movimiento')
                        conn.execute(text("""
                            INSERT INTO cuentas_corrientes (
                                id_movimiento, fecha, fecha_vencimiento, cliente, cuit,
                                tipo_comprobante, referencia_id, concepto, debe, haber,
                                observaciones, created_at
                            ) VALUES (
                                :cc_id, CAST(:fecha AS date), CAST(:fecha AS date), :cliente, :cuit,
                                'Aplicación Saldo a Favor', :iid, :concepto, :monto, 0.0,
                                :obs, NOW()
                            )
                        """), {
                            'cc_id': cc_mov_id,
                            'fecha': fecha_cobro,
                            'cliente': cliente_final,
                            'cuit': cuit_final or None,
                            'iid': i_id_clean,
                            'concepto': f"Imputación de Saldo a Favor a Cobro de Factura {i_id_clean}",
                            'monto': m_saldo_favor,
                            'obs': f"Cancelación de saldo de Factura {i_id_clean} aplicando Saldo a Favor de C/C"
                        })

                    # Insert each cheque into cheques table in Supabase
                    base_chq_id = self.supabase_service.get_next_id('cheques', 'CHQ', 'id_cheque')
                    try:
                        next_chq_num = int(base_chq_id.split('-')[-1])
                    except Exception:
                        next_chq_num = 1

                    for ch in processed_cheques_input:
                        cid = f"CHQ-{next_chq_num:06d}"
                        next_chq_num += 1
                        ch_tipo = ch['tipo']
                        ch_monto = ch['monto']
                        ch_nro = ch['nro']
                        ch_banco = ch['banco']
                        ch_venc = ch['fecha_venc']
                        cuit_chq = cdata.get('cuit_emisor_cheque') or cuit_final or None

                        conn.execute(text("""
                            INSERT INTO cheques (
                                id_cheque, fecha_ingreso, tipo, monto, cliente_emisor,
                                cuit_emisor, banco, nro_cheque, fecha_cobro,
                                endosado_tenedor, estado, id_ingreso_origen, observaciones,
                                created_at, updated_at
                            ) VALUES (
                                :cid, CAST(:fecha AS date), :tipo, :monto, :cliente,
                                :cuit, :banco, :nro, CAST(NULLIF(:venc, '') AS date),
                                'ECONCATIVO S.A.S.', 'Disponible', :iid, :obs,
                                NOW(), NOW()
                            ) ON CONFLICT (id_cheque) DO NOTHING;
                        """), {
                            'cid': cid,
                            'fecha': fecha_cobro,
                            'tipo': ch_tipo,
                            'monto': ch_monto,
                            'cliente': cliente_final,
                            'cuit': cuit_chq,
                            'banco': ch_banco,
                            'nro': ch_nro,
                            'venc': ch_venc,
                            'iid': i_id_clean,
                            'obs': f"Cobro de Ingreso {i_id_clean} - {cliente_final}"
                        })
                        created_cheques.append({
                            'cid': cid,
                            'fecha': fecha_cobro,
                            'tipo': ch_tipo,
                            'monto': ch_monto,
                            'cliente': cliente_final,
                            'cuit': cuit_chq,
                            'banco': ch_banco,
                            'nro': ch_nro,
                            'venc': ch_venc,
                            'iid': i_id_clean
                        })
            except Exception as e:
                print(f"[registrar_cobro_ingreso Supabase Error] {e}")
                raise e
        else:
            for ch in processed_cheques_input:
                created_cheques.append({
                    'cid': None,
                    'fecha': fecha_cobro,
                    'tipo': ch['tipo'],
                    'monto': ch['monto'],
                    'cliente': cliente_final,
                    'cuit': cuit_final or None,
                    'banco': ch['banco'],
                    'nro': ch['nro'],
                    'venc': ch['fecha_venc'],
                    'iid': i_id_clean
                })

        # 2. Mirror to Excel gracefully
        try:
            ws_c = self._ensure_cheques_sheet(wb)
            base_chq_excel = self._get_next_cheque_id(ws_c)
            try:
                next_excel_num = int(base_chq_excel.split('-')[-1])
            except Exception:
                next_excel_num = 1

            for ch in created_cheques:
                cid = ch.get('cid')
                if not cid:
                    cid = f"CHQ-{next_excel_num:06d}"
                    next_excel_num += 1
                    ch['cid'] = cid
                ws_c.append([
                    cid, ch['fecha'], ch['tipo'], ch['monto'], ch['cliente'], ch['cuit'] or '',
                    ch['banco'], ch['nro'], ch['venc'], 'ECONCATIVO S.A.S.', 'Disponible',
                    '', '', '', ch['iid'], f"Cobro de Ingreso {ch['iid']} - {ch['cliente']}"
                ])
            if m_saldo_favor > 0 and cliente_final:
                ws_cc = self._ensure_cuentas_corrientes_sheet(wb)
                if not cc_mov_id:
                    cc_mov_id = self._get_next_entity_id(ws_cc, 'CC')
                ws_cc.append([
                    cc_mov_id, fecha_cobro, fecha_cobro, cliente_final, cuit_final or '',
                    'Aplicación Saldo a Favor', i_id_clean,
                    f"Imputación de Saldo a Favor a Cobro de Factura {i_id_clean}",
                    m_saldo_favor, 0.0,
                    f"Cancelación de saldo de Factura {i_id_clean} aplicando Saldo a Favor de C/C"
                ])
            if target_row:
                ws_i.cell(target_row, 18, total_cobrado_acumulado)
                ws_i.cell(target_row, 19, fecha_cobro)
                ws_i.cell(target_row, 20, combined_medio)
                ws_i.cell(target_row, 21, saldo)
                ws_i.cell(target_row, 17, nuevo_estado)
                ws_i.cell(target_row, 22, recibo_id)
                ws_i.cell(target_row, 28, new_obs)
            wb.save(self.excel_path)
        except Exception as excel_err:
            print(f"[registrar_cobro_ingreso Excel mirror warning] {excel_err}")

        return {"status": "success", "id": i_id_clean, "recibo_id": recibo_id, "estado": nuevo_estado, "cobrado": importe_final}

    def get_recibo_data(self, target_id):
        """Fetches all operational, billing, and payment method details for generating the PDF receipt (Supabase First)."""
        target_clean = str(target_id).strip()

        # 1. Supabase First Lookup
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    res = conn.execute(text("""
                        SELECT * FROM ingresos
                        WHERE id_ingreso = :tid OR id_acuerdo = :tid
                        ORDER BY id_ingreso DESC LIMIT 1
                    """), {'tid': target_clean}).fetchone()
                    if res:
                        r = dict(res._mapping)
                        recibo_id = str(r.get('id_acuerdo') or '').strip()
                        if not recibo_id or not recibo_id.startswith('REC-'):
                            recibo_id = f"REC-{r.get('id_ingreso')}"
                        medio_str = str(r.get('medio_cobro') or '')
                        medios_dict = {}
                        if '|' in medio_str:
                            for part in medio_str.split('|'):
                                if ':' in part:
                                    k, v = part.split(':', 1)
                                    v_clean = v.split(' - ')[0] if ' - ' in v else v
                                    medios_dict[k.strip()] = self._to_float(v_clean)
                        elif medio_str:
                            medios_dict[medio_str.strip()] = float(r.get('importe_cobrado') or 0)

                        return {
                            'recibo_id': recibo_id,
                            'ingreso_id': r.get('id_ingreso'),
                            'fecha_cobro': str(r.get('fecha_cobro') or r.get('fecha_emision') or datetime.now().strftime('%Y-%m-%d')),
                            'fecha_emision': str(r.get('fecha_emision') or ''),
                            'tipo_comprobante': r.get('tipo_comprobante') or 'Factura A',
                            'nro_factura': r.get('nro_factura_arca') or '-',
                            'cliente': r.get('cliente') or 'Cliente',
                            'cuit': r.get('cuit_cuil') or '-',
                            'actividad': r.get('actividad') or 'Servicio Operativo',
                            'chofer': r.get('chofer') or '-',
                            'unidad': r.get('unidad') or '-',
                            'neto': float(r.get('neto') or 0),
                            'iva_pct': float(r.get('iva_pct') or 21),
                            'total': float(r.get('total') or 0),
                            'importe_cobrado': float(r.get('importe_cobrado') or 0),
                            'medio_cobro': medio_str,
                            'medios_pago_dict': medios_dict,
                            'observaciones': r.get('observaciones') or ''
                        }
            except Exception as e:
                print(f"[get_recibo_data Supabase Error] {e}")

        # 2. Fallback to Excel
        try:
            wb = self.load_wb(data_only=True)
            ws_i = wb['INGRESOS']
            target_row = None
            for r in range(5, ws_i.max_row + 1):
                val_id = str(ws_i.cell(r, 1).value or '').strip()
                val_rec = str(ws_i.cell(r, 22).value or '').strip()
                if val_id == target_clean or val_rec == target_clean:
                    target_row = r
                    break
            
            if not target_row:
                return None

            recibo_id = str(ws_i.cell(target_row, 22).value or '').strip()
            if not recibo_id or not recibo_id.startswith('REC-'):
                recibo_id = f"REC-{target_row - 4:06d}"

            medio_str = str(ws_i.cell(target_row, 20).value or '')
            medios_dict = {}
            if '|' in medio_str:
                for part in medio_str.split('|'):
                    if ':' in part:
                        k, v = part.split(':', 1)
                        v_clean = v.split(' - ')[0] if ' - ' in v else v
                        medios_dict[k.strip()] = self._to_float(v_clean)
            elif medio_str:
                medios_dict[medio_str.strip()] = float(ws_i.cell(target_row, 18).value or 0)

            return {
                'recibo_id': recibo_id,
                'ingreso_id': ws_i.cell(target_row, 1).value,
                'fecha_cobro': ws_i.cell(target_row, 19).value or datetime.now().strftime('%Y-%m-%d'),
                'fecha_emision': ws_i.cell(target_row, 2).value,
                'tipo_comprobante': ws_i.cell(target_row, 3).value or 'Factura A',
                'nro_factura': ws_i.cell(target_row, 5).value or '-',
                'cliente': ws_i.cell(target_row, 6).value or 'Cliente',
                'cuit': ws_i.cell(target_row, 7).value or '-',
                'actividad': ws_i.cell(target_row, 8).value or 'Servicio Operativo',
                'chofer': ws_i.cell(target_row, 9).value or '-',
                'unidad': ws_i.cell(target_row, 10).value or '-',
                'neto': float(ws_i.cell(target_row, 13).value or 0),
                'iva_pct': float(ws_i.cell(target_row, 14).value or 21),
                'total': float(ws_i.cell(target_row, 16).value or 0),
                'importe_cobrado': float(ws_i.cell(target_row, 18).value or 0),
                'medio_cobro': medio_str,
                'medios_pago_dict': medios_dict,
                'observaciones': ws_i.cell(target_row, 28).value or ''
            }
        except Exception as excel_err:
            print(f"[get_recibo_data Excel fallback error] {excel_err}")
            return None

    def _get_next_entity_id(self, ws, prefix):
        max_num = 0
        for r in range(5, ws.max_row + 1):
            val = str(ws.cell(r, 1).value or '').strip()
            if val.startswith(f"{prefix}-"):
                try:
                    num = int(val.split('-')[-1])
                    if num > max_num:
                        max_num = num
                except:
                    pass
        return f"{prefix}-{max_num + 1:06d}"

    # MASTER ENTITIES ADDERS & VALIDATION
    def validate_cliente(self, cdata, exclude_id=None):
        """
        Valida que los datos del cliente cumplan con los requisitos de negocio:
        - Razón Social obligatoria y no duplicada.
        - CUIT/CUIL obligatorio, con formato válido y no repetido (compara dígitos numéricos).
        - Correo Electrónico con formato válido y único (no repetido).
        """
        import re
        c_id = str(exclude_id or '').strip()
        c_nombre = str(cdata.get('nombre') or cdata.get('razon_social') or '').strip()
        c_cuit = str(cdata.get('cuit') or '').strip()
        c_email = str(cdata.get('email') or cdata.get('correo') or '').strip().lower()

        if not c_nombre:
            return {"valid": False, "field": "nombre", "message": "La Razón Social o Nombre Completo es obligatorio."}

        if not c_cuit:
            return {"valid": False, "field": "cuit", "message": "El CUIT / CUIL es obligatorio."}

        # Validación de formato de email si se ingresó
        if c_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", c_email):
            return {"valid": False, "field": "email", "message": f"El correo electrónico '{c_email}' no tiene un formato válido."}

        cuit_digits = re.sub(r'\D', '', c_cuit)

        # 1. Obtener registros existentes desde Supabase si está disponible
        existing_clients = []
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    query = text("SELECT id_cliente, razon_social, cuit_cuil, correo, estado FROM clientes")
                    rows = conn.execute(query).fetchall()
                    for r in rows:
                        existing_clients.append({
                            'id': str(r[0] or '').strip(),
                            'nombre': str(r[1] or '').strip(),
                            'cuit': str(r[2] or '').strip(),
                            'email': str(r[3] or '').strip().lower(),
                            'estado': str(r[4] or '').strip().lower()
                        })
            except Exception as e:
                print(f"[validate_cliente Supabase Error] {e}")

        # Si no se obtuvieron de Supabase, leer de Excel
        if not existing_clients:
            wb = self.load_wb(data_only=True)
            if 'CLIENTES' in wb.sheetnames:
                _, rows = self._read_sheet_rows(wb['CLIENTES'])
                for r in rows:
                    existing_clients.append({
                        'id': str(r.get('ID cliente') or r.get('ID') or '').strip(),
                        'nombre': str(r.get('Razón social / Nombre') or r.get('Nombre') or '').strip(),
                        'cuit': str(r.get('CUIT/CUIL') or r.get('CUIT') or '').strip(),
                        'email': str(r.get('Correo') or r.get('Email') or '').strip().lower(),
                        'estado': str(r.get('Estado') or '').strip().lower()
                    })

        # Evaluar unicidad
        for ec in existing_clients:
            # Omitir si es el mismo cliente en edición
            if c_id and ec['id'] == c_id:
                continue

            # Omitir si está marcado como eliminado
            if ec['estado'] == 'eliminado':
                continue

            ec_nombre = ec['nombre'] or ec['id']

            # Validar CUIT/CUIL duplicado
            ec_cuit = ec['cuit']
            if ec_cuit and c_cuit:
                ec_cuit_digits = re.sub(r'\D', '', ec_cuit)
                is_cuit_dup = False
                if len(cuit_digits) >= 8 and len(ec_cuit_digits) >= 8 and cuit_digits == ec_cuit_digits:
                    is_cuit_dup = True
                elif c_cuit.lower() == ec_cuit.lower():
                    is_cuit_dup = True

                if is_cuit_dup:
                    return {
                        "valid": False,
                        "field": "cuit",
                        "message": f"Ya existe un cliente registrado con el CUIT/CUIL '{c_cuit}' ({ec_nombre}, ID: {ec['id']})."
                    }

            # Validar Email duplicado
            ec_email = ec['email']
            if ec_email and c_email:
                if c_email == ec_email:
                    return {
                        "valid": False,
                        "field": "email",
                        "message": f"Ya existe un cliente registrado con el correo electrónico '{c_email}' ({ec_nombre}, ID: {ec['id']})."
                    }

            # Validar Razón Social duplicada (case-insensitive)
            if ec['nombre'] and c_nombre.lower() == ec['nombre'].lower():
                return {
                    "valid": False,
                    "field": "nombre",
                    "message": f"Ya existe un cliente registrado con el nombre o razón social '{c_nombre}' (ID: {ec['id']})."
                }

        return {"valid": True}

    def add_cliente(self, cdata):
        validation = self.validate_cliente(cdata, exclude_id=None)
        if not validation['valid']:
            return {"status": "error", "message": validation['message'], "field": validation.get('field')}

        wb = self.load_wb(data_only=False)
        ws = wb['CLIENTES']
        new_id = self._get_next_entity_id(ws, 'CLI')

        # Si está conectado a Supabase, verificar el número máximo en Supabase también
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_cliente FROM clientes WHERE id_cliente LIKE 'CLI-%'")).fetchall()
                    max_num = 0
                    for (cid_val,) in max_id_rows:
                        try:
                            num = int(str(cid_val).split('-')[-1])
                            if num > max_num:
                                max_num = num
                        except:
                            pass
                    wb_num = int(new_id.split('-')[-1]) if '-' in new_id else 0
                    if max_num >= wb_num:
                        new_id = f"CLI-{max_num + 1:06d}"
            except Exception as e:
                print(f"[add_cliente Supabase ID Error] {e}")

        c_nombre = str(cdata.get('nombre') or cdata.get('razon_social', '')).strip()
        c_cuit = str(cdata.get('cuit', '')).strip()
        c_tipo = cdata.get('tipo', 'Empresa')
        c_iva = cdata.get('condicion_iva', 'Responsable Inscripto')
        c_tel = str(cdata.get('telefono', '')).strip()
        c_email = str(cdata.get('email') or cdata.get('correo', '')).strip()
        c_dom = str(cdata.get('domicilio', '')).strip()
        c_obs = str(cdata.get('observaciones', '')).strip()

        # Inserción directa en Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO clientes (id_cliente, razon_social, cuit_cuil, tipo_cliente, condicion_iva, telefono, correo, domicilio, estado, observaciones)
                        VALUES (:id, :nom, :cuit, :tipo, :iva, :tel, :correo, :dom, 'Activo', :obs)
                        ON CONFLICT (id_cliente) DO UPDATE SET
                            razon_social = EXCLUDED.razon_social,
                            cuit_cuil = EXCLUDED.cuit_cuil,
                            tipo_cliente = EXCLUDED.tipo_cliente,
                            condicion_iva = EXCLUDED.condicion_iva,
                            telefono = EXCLUDED.telefono,
                            correo = EXCLUDED.correo,
                            domicilio = EXCLUDED.domicilio,
                            estado = 'Activo',
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id': new_id,
                        'nom': c_nombre,
                        'cuit': c_cuit,
                        'tipo': c_tipo,
                        'iva': c_iva,
                        'tel': c_tel,
                        'correo': c_email,
                        'dom': c_dom,
                        'obs': c_obs
                    })
            except Exception as e:
                print(f"[add_cliente Supabase Direct Insert Error] {e}")
                return {"status": "error", "message": f"Error al guardar cliente en base de datos: {str(e)}"}

        row_vals = [
            new_id,
            c_nombre,
            c_cuit,
            c_tipo,
            c_iva,
            c_tel,
            c_email,
            c_dom,
            'Activo',
            c_obs
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)
        return {"status": "success", "id": new_id, "nombre": c_nombre, "cuit": c_cuit, "email": c_email}

    def update_cliente(self, c_id, cdata):
        validation = self.validate_cliente(cdata, exclude_id=c_id)
        if not validation['valid']:
            return {"status": "error", "message": validation['message'], "field": validation.get('field')}

        wb = self.load_wb(data_only=False)
        ws = wb['CLIENTES']
        
        headers, rows = self._read_sheet_rows(ws)
        target_row_idx = None
        for r in rows:
            if str(r.get('ID cliente') or r.get('ID')).strip() == str(c_id).strip():
                target_row_idx = r['_row_idx']
                break

        nom_val = cdata.get('nombre') or cdata.get('razon_social')
        cuit_val = cdata.get('cuit')
        tipo_val = cdata.get('tipo')
        iva_val = cdata.get('condicion_iva') or cdata.get('iva')
        tel_val = cdata.get('telefono')
        mail_val = cdata.get('email') or cdata.get('correo')
        dom_val = cdata.get('domicilio')
        est_val = cdata.get('estado')
        obs_val = cdata.get('observaciones')

        if target_row_idx:
            if nom_val is not None: ws.cell(target_row_idx, 2, nom_val)
            if cuit_val is not None: ws.cell(target_row_idx, 3, cuit_val)
            if tipo_val is not None: ws.cell(target_row_idx, 4, tipo_val)
            if iva_val is not None: ws.cell(target_row_idx, 5, iva_val)
            if tel_val is not None: ws.cell(target_row_idx, 6, tel_val)
            if mail_val is not None: ws.cell(target_row_idx, 7, mail_val)
            if dom_val is not None: ws.cell(target_row_idx, 8, dom_val)
            if est_val is not None: ws.cell(target_row_idx, 9, est_val)
            if obs_val is not None: ws.cell(target_row_idx, 10, obs_val)
            wb.save(self.excel_path)

        # Actualización directa en Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                update_fields = []
                params = {'cid': c_id}
                if nom_val is not None:
                    update_fields.append("razon_social = :nom")
                    params['nom'] = str(nom_val).strip()
                if cuit_val is not None:
                    update_fields.append("cuit_cuil = :cuit")
                    params['cuit'] = str(cuit_val).strip()
                if tipo_val is not None:
                    update_fields.append("tipo_cliente = :tipo")
                    params['tipo'] = str(tipo_val).strip()
                if iva_val is not None:
                    update_fields.append("condicion_iva = :iva")
                    params['iva'] = str(iva_val).strip()
                if tel_val is not None:
                    update_fields.append("telefono = :tel")
                    params['tel'] = str(tel_val).strip()
                if mail_val is not None:
                    update_fields.append("correo = :correo")
                    params['correo'] = str(mail_val).strip()
                if dom_val is not None:
                    update_fields.append("domicilio = :dom")
                    params['dom'] = str(dom_val).strip()
                if est_val is not None:
                    update_fields.append("estado = :estado")
                    params['estado'] = str(est_val).strip()
                if obs_val is not None:
                    update_fields.append("observaciones = :obs")
                    params['obs'] = str(obs_val).strip()

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    sql = f"UPDATE clientes SET {', '.join(update_fields)} WHERE id_cliente = :cid"
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text(sql), params)
            except Exception as e:
                print(f"[update_cliente Supabase Direct Update Error] {e}")
                return {"status": "error", "message": f"Error al actualizar cliente en base de datos: {str(e)}"}

        final_nom = nom_val or (ws.cell(target_row_idx, 2).value if target_row_idx else c_id)
        return {"status": "success", "id": c_id, "nombre": final_nom}

    def check_cliente_dependencies(self, c_id, client_name="", cuit=""):
        """Verifica si el cliente posee registros activos en VIAJES, INGRESOS, PRESUPUESTOS o CUENTAS_CORRIENTES."""
        c_id = str(c_id or '').strip()
        client_name = str(client_name or '').strip().lower()
        cuit = str(cuit or '').strip()

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    v = conn.execute(text("""
                        SELECT count(*) FROM viajes 
                        WHERE LOWER(TRIM(cliente)) = :cname OR TRIM(cliente) = :cid
                    """), {'cname': client_name, 'cid': c_id}).scalar() or 0
                    
                    i = conn.execute(text("""
                        SELECT count(*) FROM ingresos 
                        WHERE LOWER(TRIM(cliente)) = :cname OR TRIM(cliente) = :cid OR (:cuit <> '' AND cuit_cuil = :cuit)
                    """), {'cname': client_name, 'cid': c_id, 'cuit': cuit}).scalar() or 0
                    
                    p = conn.execute(text("""
                        SELECT count(*) FROM presupuestos 
                        WHERE LOWER(TRIM(cliente)) = :cname OR TRIM(cliente) = :cid
                    """), {'cname': client_name, 'cid': c_id}).scalar() or 0
                    
                    cc = conn.execute(text("""
                        SELECT count(*) FROM cuentas_corrientes 
                        WHERE LOWER(TRIM(cliente)) = :cname OR TRIM(cliente) = :cid
                    """), {'cname': client_name, 'cid': c_id}).scalar() or 0
                    
                    return {
                        'viajes': int(v),
                        'ingresos': int(i),
                        'presupuestos': int(p),
                        'cuentas_corrientes': int(cc),
                        'total': int(v + i + p + cc)
                    }
            except Exception as e:
                print(f"[check_cliente_dependencies DB Error] {e}")

        # Fallback usando las hojas de Excel
        wb = self.load_wb(data_only=True)
        v, i, p, cc = 0, 0, 0, 0
        if 'VIAJES' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['VIAJES'])
            v = sum(1 for r in rows if str(r.get('Cliente', '')).strip().lower() == client_name or str(r.get('Cliente', '')).strip() == c_id)
        if 'INGRESOS' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['INGRESOS'])
            i = sum(1 for r in rows if str(r.get('Cliente', '')).strip().lower() == client_name or str(r.get('Cliente', '')).strip() == c_id or (cuit and str(r.get('CUIT/CUIL', '')).strip() == cuit))
        if 'PRESUPUESTOS' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['PRESUPUESTOS'])
            p = sum(1 for r in rows if str(r.get('Cliente', '')).strip().lower() == client_name or str(r.get('Cliente', '')).strip() == c_id)
        if 'CUENTAS_CORRIENTES' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['CUENTAS_CORRIENTES'])
            cc = sum(1 for r in rows if str(r.get('Cliente', '')).strip().lower() == client_name or str(r.get('Cliente', '')).strip() == c_id)

        return {
            'viajes': v,
            'ingresos': i,
            'presupuestos': p,
            'cuentas_corrientes': cc,
            'total': v + i + p + cc
        }

    def delete_cliente(self, c_id):
        wb = self.load_wb(data_only=False)
        ws = wb['CLIENTES']
        
        headers, rows = self._read_sheet_rows(ws)
        target_row_idx = None
        client_data = None
        for r in rows:
            if str(r.get('ID cliente') or r.get('ID')).strip() == str(c_id).strip():
                target_row_idx = r['_row_idx']
                client_data = r
                break

        if not target_row_idx:
            # Si ya no está en Excel, asegurarse de borrarlo en Supabase
            if self.supabase_service and self.supabase_service.is_connected():
                from supabase_sync import delete_row_from_supabase
                delete_row_from_supabase(self.supabase_service.engine, 'CLIENTES', c_id)
                return {"status": "success", "id": c_id}
            return {"status": "error", "message": f"Cliente {c_id} no encontrado."}

        c_name = str(client_data.get('Razón social / Nombre') or client_data.get('Nombre') or '').strip()
        c_cuit = str(client_data.get('CUIT/CUIL') or client_data.get('CUIT') or '').strip()

        # Validación de dependencias
        deps = self.check_cliente_dependencies(c_id, c_name, c_cuit)
        if deps['total'] > 0:
            details = []
            if deps['viajes']: details.append(f"{deps['viajes']} viaje(s)")
            if deps['ingresos']: details.append(f"{deps['ingresos']} factura(s)/ingreso(s)")
            if deps['presupuestos']: details.append(f"{deps['presupuestos']} presupuesto(s)")
            if deps['cuentas_corrientes']: details.append(f"{deps['cuentas_corrientes']} movimiento(s) de cuenta corriente")
            nombre_display = c_name if c_name else c_id
            return {
                "status": "error",
                "message": f"No se puede eliminar el cliente '{nombre_display}' ({c_id}) porque tiene operaciones asociadas: {', '.join(details)}. Elimine o reasigne sus comprobantes para preservar la integridad contable."
            }

        ws.delete_rows(target_row_idx)
        wb.save(self.excel_path)

        # Eliminación directa en Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'CLIENTES', c_id)

        return {"status": "success", "id": c_id}

    def add_unidad(self, udata):
        wb = self.load_wb(data_only=False)
        ws = wb['UNIDADES']
        new_id = self._get_next_entity_id(ws, 'UNI')
        
        # Sincronizar ID correlativo con Supabase si corresponde
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_unidad FROM unidades WHERE id_unidad LIKE 'UNI-%'")).fetchall()
                    max_num = 0
                    for (uid_val,) in max_id_rows:
                        try:
                            num = int(str(uid_val).split('-')[-1])
                            if num > max_num:
                                max_num = num
                        except:
                            pass
                    wb_num = int(new_id.split('-')[-1]) if '-' in new_id else 0
                    if max_num >= wb_num:
                        new_id = f"UNI-{max_num + 1:06d}"
            except Exception as e:
                print(f"[add_unidad Supabase ID Error] {e}")

        u_tipo = str(udata.get('tipo', 'Camión')).strip()
        u_desc = str(udata.get('descripcion', '')).strip()
        u_pat = str(udata.get('patente') or udata.get('dominio_patente', '')).strip()
        u_marca = str(udata.get('marca', '')).strip()
        u_modelo = str(udata.get('modelo', '')).strip()
        u_anio = self._clean_int(udata.get('anio'))
        u_seg = self._clean_date(udata.get('seguro_vence'))
        u_rto = self._clean_date(udata.get('rto_vence') or udata.get('rto_itv_vence'))
        u_obs = str(udata.get('observaciones', '')).strip()

        # Inserción directa y síncrona en Supabase PostgreSQL
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO unidades (
                            id_unidad, tipo, descripcion, dominio_patente, marca, modelo,
                            anio, estado, seguro_vence, rto_itv_vence, observaciones, updated_at
                        ) VALUES (
                            :id, :tipo, :desc, :pat, :marca, :modelo,
                            :anio, 'Activo', :seg, :rto, :obs, NOW()
                        )
                        ON CONFLICT (id_unidad) DO UPDATE SET
                            tipo = EXCLUDED.tipo,
                            descripcion = EXCLUDED.descripcion,
                            dominio_patente = EXCLUDED.dominio_patente,
                            marca = EXCLUDED.marca,
                            modelo = EXCLUDED.modelo,
                            anio = EXCLUDED.anio,
                            estado = 'Activo',
                            seguro_vence = EXCLUDED.seguro_vence,
                            rto_itv_vence = EXCLUDED.rto_itv_vence,
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW()
                    """), {
                        'id': new_id,
                        'tipo': u_tipo,
                        'desc': u_desc,
                        'pat': u_pat,
                        'marca': u_marca,
                        'modelo': u_modelo,
                        'anio': u_anio,
                        'seg': u_seg,
                        'rto': u_rto,
                        'obs': u_obs
                    })
            except Exception as e:
                print(f"[add_unidad Supabase Direct Insert Error] {e}")

        row_vals = [
            new_id,
            u_tipo,
            u_desc,
            u_pat,
            u_marca,
            u_modelo,
            udata.get('anio', ''),
            'Activo',
            udata.get('seguro_vence', ''),
            udata.get('rto_vence', ''),
            '',
            u_obs
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)
        return {"status": "success", "id": new_id, "patente": u_pat}

    def update_unidad(self, u_id, udata):
        wb = self.load_wb(data_only=False)
        ws = wb['UNIDADES']
        
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(u_id).strip():
                target_row = r
                break

        if target_row:
            if 'tipo' in udata: ws.cell(target_row, 2, udata['tipo'])
            if 'descripcion' in udata: ws.cell(target_row, 3, udata['descripcion'])
            if 'patente' in udata: ws.cell(target_row, 4, udata['patente'])
            if 'marca' in udata: ws.cell(target_row, 5, udata['marca'])
            if 'modelo' in udata: ws.cell(target_row, 6, udata['modelo'])
            if 'anio' in udata: ws.cell(target_row, 7, udata['anio'])
            if 'seguro_vence' in udata: ws.cell(target_row, 9, udata['seguro_vence'])
            if 'rto_vence' in udata: ws.cell(target_row, 10, udata['rto_vence'])
            if 'observaciones' in udata: ws.cell(target_row, 12, udata['observaciones'])
            wb.save(self.excel_path)

        # Actualización directa y síncrona en Supabase PostgreSQL
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                update_fields = []
                params = {'uid': u_id}
                if 'tipo' in udata:
                    update_fields.append("tipo = :tipo")
                    params['tipo'] = str(udata['tipo']).strip()
                if 'descripcion' in udata:
                    update_fields.append("descripcion = :desc")
                    params['desc'] = str(udata['descripcion']).strip()
                if 'patente' in udata or 'dominio_patente' in udata:
                    update_fields.append("dominio_patente = :pat")
                    params['pat'] = str(udata.get('patente') or udata.get('dominio_patente', '')).strip()
                if 'marca' in udata:
                    update_fields.append("marca = :marca")
                    params['marca'] = str(udata['marca']).strip()
                if 'modelo' in udata:
                    update_fields.append("modelo = :modelo")
                    params['modelo'] = str(udata['modelo']).strip()
                if 'anio' in udata:
                    update_fields.append("anio = :anio")
                    params['anio'] = self._clean_int(udata['anio'])
                if 'seguro_vence' in udata:
                    update_fields.append("seguro_vence = :seg")
                    params['seg'] = self._clean_date(udata['seguro_vence'])
                if 'rto_vence' in udata or 'rto_itv_vence' in udata:
                    update_fields.append("rto_itv_vence = :rto")
                    params['rto'] = self._clean_date(udata.get('rto_vence') or udata.get('rto_itv_vence'))
                if 'observaciones' in udata:
                    update_fields.append("observaciones = :obs")
                    params['obs'] = str(udata['observaciones']).strip()

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    sql = f"UPDATE unidades SET {', '.join(update_fields)} WHERE id_unidad = :uid"
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text(sql), params)
            except Exception as e:
                print(f"[update_unidad Supabase Direct Update Error] {e}")

        if not target_row and not (self.supabase_service and self.supabase_service.is_connected()):
            return {"status": "error", "message": f"Unidad {u_id} no encontrada."}

        return {"status": "success", "id": u_id, "patente": udata.get('patente')}

    def check_unidad_dependencies(self, u_id, patente=""):
        u_id = str(u_id or '').strip()
        patente = str(patente or '').strip().lower()
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    pat_pattern = f"%{patente}%" if len(patente) >= 3 else patente
                    v = conn.execute(text("""
                        SELECT count(*) FROM viajes 
                        WHERE LOWER(unidad) LIKE :pat OR TRIM(unidad) = :uid
                    """), {'pat': pat_pattern, 'uid': u_id}).scalar() or 0
                    o = conn.execute(text("""
                        SELECT count(*) FROM ordenes_compra 
                        WHERE LOWER(unidad) LIKE :pat OR TRIM(unidad) = :uid
                    """), {'pat': pat_pattern, 'uid': u_id}).scalar() or 0
                    return {'viajes': int(v), 'ordenes': int(o), 'total': int(v + o)}
            except Exception as e:
                print(f"[check_unidad_dependencies DB Error] {e}")

        wb = self.load_wb(data_only=True)
        v, o = 0, 0
        if 'VIAJES' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['VIAJES'])
            v = sum(1 for r in rows if (patente and len(patente) >= 3 and patente in str(r.get('Unidad', '')).strip().lower()) or str(r.get('Unidad', '')).strip() == u_id)
        if 'ORDENES_COMPRA' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['ORDENES_COMPRA'])
            o = sum(1 for r in rows if (patente and len(patente) >= 3 and patente in str(r.get('Unidad', '')).strip().lower()) or str(r.get('Unidad', '')).strip() == u_id)
        return {'viajes': v, 'ordenes': o, 'total': v + o}

    def delete_unidad(self, u_id):
        wb = self.load_wb(data_only=False)
        ws = wb['UNIDADES']
        
        target_row = None
        patente = ""
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(u_id).strip():
                target_row = r
                patente = str(ws.cell(r, 4).value or '').strip()
                break
        
        if not target_row:
            if self.supabase_service and self.supabase_service.is_connected():
                from supabase_sync import delete_row_from_supabase
                delete_row_from_supabase(self.supabase_service.engine, 'UNIDADES', u_id)
                return {"status": "success", "id": u_id}
            return {"status": "error", "message": f"Unidad {u_id} no encontrada."}

        deps = self.check_unidad_dependencies(u_id, patente)
        if deps['total'] > 0:
            details = []
            if deps['viajes']: details.append(f"{deps['viajes']} viaje(s)")
            if deps['ordenes']: details.append(f"{deps['ordenes']} orden(es) de compra")
            return {
                "status": "error",
                "message": f"No se puede eliminar la unidad '{patente or u_id}' porque está asignada a: {', '.join(details)}. Elimine o reasigne sus registros primero."
            }

        ws.delete_rows(target_row)
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'UNIDADES', u_id)

        return {"status": "success", "id": u_id}

    def add_empleado(self, edata):
        import json
        wb = self.load_wb(data_only=False)
        ws = wb['EMPLEADOS']

        max_num = 0
        for r in range(5, ws.max_row + 1):
            val = str(ws.cell(r, 1).value or '').strip()
            if val.startswith('EMP-'):
                try:
                    num = int(val.split('-')[-1])
                    if num > max_num: max_num = num
                except: pass

        new_id = f"EMP-{max_num + 1:06d}"

        licencias = edata.get('licencias', [])
        if licencias and isinstance(licencias, list):
            tipo_lic = ", ".join(l.get('tipo', '') for l in licencias if l.get('tipo'))
            if len(licencias) > 1:
                lic_vence = json.dumps(licencias, ensure_ascii=False)
            elif len(licencias) == 1:
                lic_vence = licencias[0].get('vencimiento', '')
            else:
                lic_vence = ''
        else:
            tipo_lic = edata.get('tipo_licencia', 'LINTI')
            lic_vence = edata.get('licencia_vence', '')

        raw_dni = str(edata.get('dni', '')).strip()
        clean_dni = re.sub(r'\D', '', raw_dni)[:8] if raw_dni else ''
        raw_cbu = str(edata.get('cbu', '')).strip()
        clean_cbu = re.sub(r'\D', '', raw_cbu)[:22] if raw_cbu else ''
        alias_cbu = str(edata.get('alias_cbu', '')).strip() # Preservar mayúsculas y minúsculas exactas

        # Inserción directa en Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_empleado FROM empleados WHERE id_empleado LIKE 'EMP-%'")).fetchall()
                    for (eid_val,) in max_id_rows:
                        try:
                            num = int(str(eid_val).split('-')[-1])
                            if num > max_num:
                                max_num = num
                        except:
                            pass
                    new_id = f"EMP-{max_num + 1:06d}"
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO empleados (
                            id_empleado, apellido_nombre, dni, cuil, fecha_nacimiento,
                            estado_civil, domicilio_real_actual, barrio_zona, localidad,
                            telefono, email, contacto_emergencia, vinculo_parentesco,
                            domicilio_contacto, localidad_contacto, telefono_contacto,
                            banco, titular_cuenta, cbu, alias_cbu,
                            fecha_inicio, puesto, jornada, modalidad_trabajo,
                            sueldo_fijo, sueldo_basico, comision_pct, modalidad_pago,
                            seguro_art, tipo_licencia, licencia_vence,
                            talle_remera, talle_campera, talle_pantalon, calzado,
                            estado, observaciones, updated_at
                        ) VALUES (
                            :id, :nom, :dni, :cuil, :fnac,
                            :eciv, :dom, :barr, :loc,
                            :tel, :email, :em_nom, :em_vin,
                            :em_dom, :em_loc, :em_tel,
                            :banco, :titular, :cbu, :alias,
                            :finicio, :puesto, :jornada, :mod_trab,
                            :sueldo, :sueldo, :com_pct, :mod_pago,
                            :art, :tipo_lic, :lic_vence,
                            :tremera, :tcampera, :tpantalon, :calzado,
                            :estado, :obs, NOW()
                        )
                        ON CONFLICT (id_empleado) DO UPDATE SET
                            apellido_nombre = EXCLUDED.apellido_nombre,
                            dni = EXCLUDED.dni,
                            cuil = EXCLUDED.cuil,
                            fecha_nacimiento = EXCLUDED.fecha_nacimiento,
                            estado_civil = EXCLUDED.estado_civil,
                            domicilio_real_actual = EXCLUDED.domicilio_real_actual,
                            barrio_zona = EXCLUDED.barrio_zona,
                            localidad = EXCLUDED.localidad,
                            telefono = EXCLUDED.telefono,
                            email = EXCLUDED.email,
                            contacto_emergencia = EXCLUDED.contacto_emergencia,
                            vinculo_parentesco = EXCLUDED.vinculo_parentesco,
                            domicilio_contacto = EXCLUDED.domicilio_contacto,
                            localidad_contacto = EXCLUDED.localidad_contacto,
                            telefono_contacto = EXCLUDED.telefono_contacto,
                            banco = EXCLUDED.banco,
                            titular_cuenta = EXCLUDED.titular_cuenta,
                            cbu = EXCLUDED.cbu,
                            alias_cbu = EXCLUDED.alias_cbu,
                            fecha_inicio = EXCLUDED.fecha_inicio,
                            puesto = EXCLUDED.puesto,
                            jornada = EXCLUDED.jornada,
                            modalidad_trabajo = EXCLUDED.modalidad_trabajo,
                            sueldo_fijo = EXCLUDED.sueldo_fijo,
                            sueldo_basico = EXCLUDED.sueldo_basico,
                            comision_pct = EXCLUDED.comision_pct,
                            modalidad_pago = EXCLUDED.modalidad_pago,
                            seguro_art = EXCLUDED.seguro_art,
                            tipo_licencia = EXCLUDED.tipo_licencia,
                            licencia_vence = EXCLUDED.licencia_vence,
                            talle_remera = EXCLUDED.talle_remera,
                            talle_campera = EXCLUDED.talle_campera,
                            talle_pantalon = EXCLUDED.talle_pantalon,
                            calzado = EXCLUDED.calzado,
                            estado = EXCLUDED.estado,
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id': new_id,
                        'nom': edata.get('nombre', ''),
                        'dni': clean_dni,
                        'cuil': edata.get('cuil', ''),
                        'fnac': edata.get('fecha_nacimiento') or None,
                        'eciv': edata.get('estado_civil', 'Soltero'),
                        'dom': edata.get('domicilio', ''),
                        'barr': edata.get('barrio', ''),
                        'loc': edata.get('localidad', ''),
                        'tel': edata.get('telefono', ''),
                        'email': edata.get('email', ''),
                        'em_nom': edata.get('emergencia_nombre', ''),
                        'em_vin': edata.get('emergencia_vinculo', ''),
                        'em_dom': edata.get('emergencia_domicilio', ''),
                        'em_loc': edata.get('emergencia_localidad', ''),
                        'em_tel': edata.get('emergencia_telefono', ''),
                        'banco': edata.get('banco', ''),
                        'titular': edata.get('titular_cuenta', ''),
                        'cbu': clean_cbu,
                        'alias': alias_cbu,
                        'finicio': edata.get('fecha_inicio') or None,
                        'puesto': edata.get('puesto', 'Chofer'),
                        'jornada': edata.get('jornada', 'Completa'),
                        'mod_trab': edata.get('modalidad_trabajo', ''),
                        'sueldo': self._to_float(edata.get('sueldo_fijo', 0)),
                        'com_pct': max(0.0, min(100.0, self._to_float(edata.get('comision_pct', 0)))),
                        'mod_pago': edata.get('modalidad_pago', 'Transferencia'),
                        'art': edata.get('seguro_art', ''),
                        'tipo_lic': tipo_lic,
                        'lic_vence': lic_vence,
                        'tremera': edata.get('talle_remera', 'M'),
                        'tcampera': edata.get('talle_campera', 'M'),
                        'tpantalon': str(edata.get('talle_pantalon', '42')).strip(),
                        'calzado': str(edata.get('calzado', '40')).strip(),
                        'estado': str(edata.get('estado') or 'Activo').strip(),
                        'obs': edata.get('observaciones', '')
                    })
            except Exception as e:
                print(f"[add_empleado Supabase Direct Insert Error] {e}")

        row_vals = [
            new_id,
            edata.get('nombre', ''),
            clean_dni,
            edata.get('cuil', ''),
            edata.get('fecha_nacimiento', ''),
            edata.get('estado_civil', 'Soltero'),
            edata.get('domicilio', ''),
            edata.get('barrio', ''),
            edata.get('localidad', ''),
            edata.get('telefono', ''),
            edata.get('email', ''),
            edata.get('emergencia_nombre', ''),
            edata.get('emergencia_vinculo', ''),
            edata.get('emergencia_domicilio', ''),
            edata.get('emergencia_localidad', ''),
            edata.get('emergencia_telefono', ''),
            edata.get('banco', ''),
            edata.get('titular_cuenta', ''),
            clean_cbu,
            alias_cbu,
            edata.get('fecha_inicio', ''),
            edata.get('puesto', 'Chofer'),
            edata.get('jornada', 'Completa'),
            edata.get('modalidad_trabajo', ''),
            edata.get('remuneracion', ''),
            edata.get('modalidad_pago', 'Transferencia'),
            edata.get('seguro_art', ''),
            tipo_lic,
            lic_vence,
            edata.get('talle_remera', 'M'),
            edata.get('talle_campera', 'M'),
            str(edata.get('talle_pantalon', '42')).strip(),
            str(edata.get('calzado', '40')).strip(),
            str(edata.get('estado') or 'Activo').strip(),
            edata.get('observaciones', ''),
            self._to_float(edata.get('sueldo_fijo', 0)),
            max(0.0, min(100.0, self._to_float(edata.get('comision_pct', 0))))
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)
        return {"status": "success", "id": new_id, "nombre": edata.get('nombre')}

    def update_empleado(self, e_id, edata):
        import json
        wb = self.load_wb(data_only=False)
        ws = wb['EMPLEADOS']
        
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(e_id).strip():
                target_row = r
                break

        licencias = edata.get('licencias', [])
        if licencias and isinstance(licencias, list):
            tipo_lic = ", ".join(l.get('tipo', '') for l in licencias if l.get('tipo'))
            if len(licencias) > 1:
                lic_vence = json.dumps(licencias, ensure_ascii=False)
            elif len(licencias) == 1:
                lic_vence = licencias[0].get('vencimiento', '')
            else:
                lic_vence = ''
            edata['tipo_licencia'] = tipo_lic
            edata['licencia_vence'] = lic_vence

        if 'dni' in edata:
            raw_dni = str(edata['dni']).strip()
            edata['dni'] = re.sub(r'\D', '', raw_dni)[:8] if raw_dni else ''
        if 'cbu' in edata:
            raw_cbu = str(edata['cbu']).strip()
            edata['cbu'] = re.sub(r'\D', '', raw_cbu)[:22] if raw_cbu else ''
        if 'alias_cbu' in edata:
            edata['alias_cbu'] = str(edata['alias_cbu']).strip()
        if 'talle_pantalon' in edata:
            edata['talle_pantalon'] = str(edata['talle_pantalon']).strip()
        if 'calzado' in edata:
            edata['calzado'] = str(edata['calzado']).strip()

        # Actualización directa en Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE empleados SET
                            apellido_nombre = COALESCE(:nom, apellido_nombre),
                            dni = COALESCE(:dni, dni),
                            cuil = COALESCE(:cuil, cuil),
                            fecha_nacimiento = COALESCE(:fnac, fecha_nacimiento),
                            estado_civil = COALESCE(:eciv, estado_civil),
                            domicilio_real_actual = COALESCE(:dom, domicilio_real_actual),
                            barrio_zona = COALESCE(:barr, barrio_zona),
                            localidad = COALESCE(:loc, localidad),
                            telefono = COALESCE(:tel, telefono),
                            email = COALESCE(:email, email),
                            contacto_emergencia = COALESCE(:em_nom, contacto_emergencia),
                            vinculo_parentesco = COALESCE(:em_vin, vinculo_parentesco),
                            domicilio_contacto = COALESCE(:em_dom, domicilio_contacto),
                            localidad_contacto = COALESCE(:em_loc, localidad_contacto),
                            telefono_contacto = COALESCE(:em_tel, telefono_contacto),
                            banco = COALESCE(:banco, banco),
                            titular_cuenta = COALESCE(:titular, titular_cuenta),
                            cbu = COALESCE(:cbu, cbu),
                            alias_cbu = COALESCE(:alias, alias_cbu),
                            fecha_inicio = COALESCE(:finicio, fecha_inicio),
                            puesto = COALESCE(:puesto, puesto),
                            jornada = COALESCE(:jornada, jornada),
                            modalidad_trabajo = COALESCE(:mod_trab, modalidad_trabajo),
                            sueldo_fijo = COALESCE(:sueldo, sueldo_fijo),
                            sueldo_basico = COALESCE(:sueldo, sueldo_basico),
                            comision_pct = COALESCE(:com_pct, comision_pct),
                            modalidad_pago = COALESCE(:mod_pago, modalidad_pago),
                            seguro_art = COALESCE(:art, seguro_art),
                            tipo_licencia = COALESCE(:tipo_lic, tipo_licencia),
                            licencia_vence = COALESCE(:lic_vence, licencia_vence),
                            talle_remera = COALESCE(:tremera, talle_remera),
                            talle_campera = COALESCE(:tcampera, talle_campera),
                            talle_pantalon = COALESCE(:tpantalon, talle_pantalon),
                            calzado = COALESCE(:calzado, calzado),
                            estado = COALESCE(:estado, estado),
                            observaciones = COALESCE(:obs, observaciones),
                            updated_at = NOW()
                        WHERE id_empleado = :id
                    """), {
                        'id': e_id,
                        'nom': edata.get('nombre'),
                        'dni': edata.get('dni'),
                        'cuil': edata.get('cuil'),
                        'fnac': (edata.get('fecha_nacimiento') or None) if 'fecha_nacimiento' in edata else None,
                        'eciv': edata.get('estado_civil'),
                        'dom': edata.get('domicilio'),
                        'barr': edata.get('barrio'),
                        'loc': edata.get('localidad'),
                        'tel': edata.get('telefono'),
                        'email': edata.get('email'),
                        'em_nom': edata.get('emergencia_nombre'),
                        'em_vin': edata.get('emergencia_vinculo'),
                        'em_dom': edata.get('emergencia_domicilio'),
                        'em_loc': edata.get('emergencia_localidad'),
                        'em_tel': edata.get('emergencia_telefono'),
                        'banco': edata.get('banco'),
                        'titular': edata.get('titular_cuenta'),
                        'cbu': edata.get('cbu'),
                        'alias': edata.get('alias_cbu'),
                        'finicio': (edata.get('fecha_inicio') or None) if 'fecha_inicio' in edata else None,
                        'puesto': edata.get('puesto'),
                        'jornada': edata.get('jornada'),
                        'mod_trab': edata.get('modalidad_trabajo'),
                        'sueldo': self._to_float(edata['sueldo_fijo']) if 'sueldo_fijo' in edata else None,
                        'com_pct': max(0.0, min(100.0, self._to_float(edata['comision_pct']))) if 'comision_pct' in edata else None,
                        'mod_pago': edata.get('modalidad_pago'),
                        'art': edata.get('seguro_art'),
                        'tipo_lic': edata.get('tipo_licencia', tipo_lic if 'licencias' in edata else None),
                        'lic_vence': edata.get('licencia_vence', lic_vence if 'licencias' in edata else None),
                        'tremera': edata.get('talle_remera'),
                        'tcampera': edata.get('talle_campera'),
                        'tpantalon': str(edata.get('talle_pantalon', '42')).strip() if 'talle_pantalon' in edata else None,
                        'calzado': str(edata.get('calzado', '40')).strip() if 'calzado' in edata else None,
                        'estado': str(edata.get('estado')).strip() if edata.get('estado') else None,
                        'obs': edata.get('observaciones')
                    })
            except Exception as e:
                print(f"[update_empleado Supabase Direct Update Error] {e}")

        if target_row:
            fields_map = {
                'nombre': 2, 'dni': 3, 'cuil': 4, 'fecha_nacimiento': 5, 'estado_civil': 6,
                'domicilio': 7, 'barrio': 8, 'localidad': 9, 'telefono': 10, 'email': 11,
                'emergencia_nombre': 12, 'emergencia_vinculo': 13, 'emergencia_domicilio': 14,
                'emergencia_localidad': 15, 'emergencia_telefono': 16, 'banco': 17,
                'titular_cuenta': 18, 'cbu': 19, 'alias_cbu': 20, 'fecha_inicio': 21,
                'puesto': 22, 'jornada': 23, 'modalidad_trabajo': 24, 'remuneracion': 25,
                'modalidad_pago': 26, 'seguro_art': 27, 'tipo_licencia': 28, 'licencia_vence': 29,
                'talle_remera': 30, 'talle_campera': 31, 'talle_pantalon': 32, 'calzado': 33,
                'estado': 34, 'observaciones': 35, 'sueldo_fijo': 36, 'comision_pct': 37
            }

            for field, col in fields_map.items():
                if field in edata:
                    val = edata[field]
                    if field == 'sueldo_fijo':
                        val = max(0.0, self._to_float(val))
                    elif field == 'comision_pct':
                        val = max(0.0, min(100.0, self._to_float(val)))
                    ws.cell(target_row, col, val)

            wb.save(self.excel_path)
        return {"status": "success", "id": e_id}

    def _get_row_prop(self, row, possible_keys):
        if not row: return ''
        def _clean_k(s):
            return str(s).lower().replace(' ', '').replace('_', '').replace('ó', 'o').replace('í', 'i').replace('é', 'e').replace('á', 'a').replace('ú', 'u').replace('ñ', 'n').replace('%', '').replace('º', '').replace('°', '')
        for k in possible_keys:
            if k in row and row[k] is not None and str(row[k]).strip() != '':
                return str(row[k]).strip()
            k_c = _clean_k(k)
            for rk in row.keys():
                if _clean_k(rk) == k_c:
                    if row[rk] is not None and str(row[rk]).strip() != '':
                        return str(row[rk]).strip()
        return ''

    def _ensure_novedades_personal_sheet(self, wb):
        if 'NOVEDADES_PERSONAL' not in wb.sheetnames:
            ws = wb.create_sheet('NOVEDADES_PERSONAL')
            ws.cell(1, 1, 'ECONCATIVO - LIBRO DE NOVEDADES Y ADELANTOS DE PERSONAL')
            ws.cell(2, 1, 'Generado automáticamente por Antigravity Control System')
            headers = [
                'ID novedad',
                'Fecha',
                'ID empleado',
                'Empleado',
                'Tipo',
                'Concepto',
                'Monto',
                'Medio pago',
                'ID cheque',
                'N° cheque',
                'ID liquidacion',
                'Estado',
                'Observaciones'
            ]
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
            return ws
        return wb['NOVEDADES_PERSONAL']

    def get_available_cheques(self):
        """Returns list of third-party cheques currently in cartera (Estado == 'Disponible')."""
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    res = conn.execute(text("""
                        SELECT id_cheque, nro_cheque, monto, banco, cliente_emisor, fecha_cobro, tipo
                        FROM cheques
                        WHERE LOWER(TRIM(estado)) = 'disponible'
                        ORDER BY id_cheque DESC
                    """)).fetchall()
                    disponibles = []
                    for r in res:
                        m = dict(r._mapping)
                        cid = m.get('id_cheque') or ''
                        nro = m.get('nro_cheque') or ''
                        monto = self._to_float(m.get('monto') or 0)
                        banco = m.get('banco') or ''
                        emisor = m.get('cliente_emisor') or ''
                        venc = str(m.get('fecha_cobro') or '')
                        disponibles.append({
                            'id': cid,
                            'nro_cheque': nro,
                            'monto': monto,
                            'banco': banco,
                            'emisor': emisor,
                            'vencimiento': venc,
                            'label': f"Cheque N° {nro if nro else cid} - {banco} (${monto:,.2f})"
                        })
                    return disponibles
            except Exception as e:
                print(f"[DataManager] Warning reading available cheques from Supabase: {e}")

        wb = self.load_wb(data_only=True)
        if 'CHEQUES' not in wb.sheetnames:
            return []
        _, rows = self._read_sheet_rows(wb['CHEQUES'])
        disponibles = []
        for r in rows:
            est = str(self._get_row_prop(r, ['Estado', 'Estado cheque']) or '').strip()
            if est.lower() == 'disponible':
                cid = self._get_row_prop(r, ['ID cheque', 'ID'])
                nro = self._get_row_prop(r, ['N° cheque', 'Número cheque', 'Nro cheque', 'Cheque'])
                monto = self._to_float(self._get_row_prop(r, ['Importe / Monto', 'Monto', 'Importe']))
                banco = self._get_row_prop(r, ['Banco emisor', 'Banco'])
                emisor = self._get_row_prop(r, ['Cliente / Emisor', 'Emisor', 'Cliente'])
                venc = self._get_row_prop(r, ['Fecha vencimiento', 'Vencimiento'])
                disponibles.append({
                    'id': cid,
                    'nro_cheque': nro,
                    'monto': monto,
                    'banco': banco,
                    'emisor': emisor,
                    'vencimiento': venc,
                    'label': f"Cheque N° {nro} - {banco} (${monto:,.2f})"
                })
        return disponibles

    def add_novedad_personal(self, payload):
        """Registers an advance (Deducción) or expense reimbursement (Reintegro) for an employee in Supabase and Excel mirror.
        For Deducciones (advances/viáticos), automatically creates a corresponding paid EGRESO and discounts from treasury."""
        empleado = payload.get('empleado')
        if not empleado:
            return {"status": "error", "message": "Empleado es requerido."}
        
        monto = self._to_float(payload.get('monto'))
        if monto <= 0:
            return {"status": "error", "message": "El monto debe ser mayor a 0."}
            
        tipo = payload.get('tipo', 'Deducción')
        is_deduccion = 'deduc' in str(tipo).lower() or 'adelant' in str(tipo).lower()
        concepto = payload.get('concepto') or ('Adelanto de Sueldo / Viáticos' if is_deduccion else 'Reintegro de Gastos')
        fecha = payload.get('fecha') or datetime.now().strftime('%Y-%m-%d')
        medio_pago = payload.get('medio_pago', 'Transferencia Bancaria')
        cuenta_origen = str(payload.get('cuenta_origen') or '').strip()
        cheque_id = str(payload.get('cheque_id') or '').strip()
        observaciones = payload.get('observaciones', '')
        emp_id = str(payload.get('empleado_id') or '').strip()
        emp_cuit = str(payload.get('cuit') or '').strip()
        nro_cheque = ''
        banco_cheque = ''

        # Determine detailed payment method string for Treasury and Egreso
        if cheque_id:
            medio_egreso = f"Cheque de Terceros ({cheque_id})"
        elif cuenta_origen:
            mp_l = str(medio_pago).lower()
            co_l = cuenta_origen.lower()
            if 'transferencia' in mp_l and not co_l.startswith('transferencia'):
                medio_egreso = f"Transferencia - {cuenta_origen}"
            elif ('efectivo' in mp_l or 'caja' in mp_l) and not (co_l.startswith('efectivo') or co_l.startswith('caja')):
                medio_egreso = f"Efectivo - {cuenta_origen}"
            else:
                medio_egreso = cuenta_origen
        else:
            medio_egreso = medio_pago

        # If it is an advance/deduction and not a settlement surplus, validate treasury availability
        if is_deduccion and 'excedente' not in str(medio_pago).lower() and not cheque_id:
            is_valid, disp_amt, acc_name_match, err_msg = self.validate_treasury_disponibilidad(medio_egreso, monto)
            if not is_valid:
                return {"status": "error", "message": err_msg}

        # 1. Supabase Master Execution
        nov_id = None
        egr_id = None
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                nov_id = self.supabase_service.get_next_id('novedades_personal', 'NOV', 'id_novedad')
                with self.supabase_service.engine.begin() as conn:
                    if not emp_id or not emp_cuit:
                        emp_res = conn.execute(text("SELECT id_empleado, cuil, dni FROM empleados WHERE LOWER(apellido_nombre) = LOWER(:emp) LIMIT 1"), {'emp': str(empleado).strip()}).first()
                        if emp_res:
                            if not emp_id: emp_id = str(emp_res[0] or '').strip()
                            if not emp_cuit: emp_cuit = str(emp_res[1] or emp_res[2] or '').strip()

                    if ('cheque' in str(medio_pago).lower()) and cheque_id:
                        chq_res = conn.execute(text("SELECT nro_cheque, banco FROM cheques WHERE id_cheque = :cid"), {'cid': cheque_id}).first()
                        if chq_res:
                            nro_cheque = str(chq_res[0] or '').strip()
                            banco_cheque = str(chq_res[1] or '').strip()
                            medio_egreso = f"Cheque N° {nro_cheque} ({banco_cheque})" if nro_cheque else f"Cheque {cheque_id}"

                    # If advance (Deducción) and not surplus from liquidation confirmation, create paid Egreso
                    if is_deduccion and 'excedente' not in str(medio_pago).lower():
                        egr_id = self.supabase_service.get_next_id('egresos', 'EGR', 'id_egreso')
                        desc_egreso = f"Adelanto de Sueldo: {concepto} ({medio_egreso})"
                        obs_egreso = f"[NOVEDAD: {nov_id}] {concepto} | Empleado: {empleado}"
                        
                        conn.execute(text("""
                            INSERT INTO egresos (
                                id_egreso, fecha_comprobante, fecha_vencimiento, categoria, subcategoria,
                                proveedor, cuit, tipo_comprobante, nro_comprobante, unidad,
                                empleado, descripcion, neto, iva, total,
                                estado_pago, importe_pagado, fecha_pago, medio_pago, saldo,
                                observaciones, created_at, updated_at
                            ) VALUES (
                                :id_egreso, CAST(:fecha AS date), CAST(:fecha AS date), 'Adelanto de Sueldo', 'Personal',
                                :prov, :cuit, 'Recibo de Adelanto', :nov_id, '',
                                :emp, :desc, :monto, 0, :monto,
                                'Pagado', :monto, CAST(:fecha AS date), :medio, 0,
                                :obs, NOW(), NOW()
                            );
                        """), {
                            'id_egreso': egr_id,
                            'fecha': fecha,
                            'prov': empleado,
                            'cuit': emp_cuit,
                            'nov_id': nov_id,
                            'emp': emp_id or empleado,
                            'desc': desc_egreso,
                            'monto': monto,
                            'medio': medio_egreso,
                            'obs': obs_egreso
                        })

                    if ('cheque' in str(medio_pago).lower()) and cheque_id:
                        conn.execute(text("""
                            UPDATE cheques SET
                                estado = 'Entregado Personal',
                                endosado_tenedor = :emp,
                                destino_usado_en = :destino,
                                fecha_uso = CAST(:fecha AS date),
                                id_egreso = :eid,
                                observaciones = CONCAT(COALESCE(observaciones, ''), ' | Novedad ', :nid),
                                updated_at = NOW()
                            WHERE id_cheque = :cid;
                        """), {
                            'emp': empleado,
                            'destino': f"Adelanto/Viático Chofer: {empleado}",
                            'fecha': fecha,
                            'eid': egr_id,
                            'nid': nov_id,
                            'cid': cheque_id
                        })

                    conn.execute(text("""
                        INSERT INTO novedades_personal (
                            id_novedad, fecha, id_empleado, empleado, tipo, concepto,
                            monto, medio_pago, id_cheque, nro_cheque, id_liquidacion,
                            estado, observaciones, created_at
                        ) VALUES (
                            :nid, CAST(:fecha AS date), :eid, :emp, :tipo, :concepto,
                            :monto, :medio, :cid, :nro_chq, NULL,
                            'Pendiente', :obs, NOW()
                        )
                    """), {
                        'nid': nov_id,
                        'fecha': fecha,
                        'eid': emp_id or None,
                        'emp': empleado,
                        'tipo': tipo,
                        'concepto': concepto,
                        'monto': monto,
                        'medio': medio_egreso,
                        'cid': cheque_id or None,
                        'nro_chq': nro_cheque or None,
                        'obs': observaciones
                    })
            except Exception as e:
                print(f"[add_novedad_personal Supabase Error] {e}")
                if not nov_id:
                    nov_id = f"NOV-{datetime.now().strftime('%y%m%d%H%M%S')}"
        else:
            nov_id = None

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws_nov = self._ensure_novedades_personal_sheet(wb)
            if not nov_id:
                max_num = 0
                for r in range(5, ws_nov.max_row + 1):
                    val = str(ws_nov.cell(r, 1).value or '').strip()
                    if val.startswith('NOV-'):
                        try:
                            n = int(val.replace('NOV-', ''))
                            if n > max_num: max_num = n
                        except: pass
                nov_id = f"NOV-{max_num + 1:06d}"

            if (not emp_id or not emp_cuit) and 'EMPLEADOS' in wb.sheetnames:
                _, emp_rows = self._read_sheet_rows(wb['EMPLEADOS'])
                for er in emp_rows:
                    en = self._get_row_prop(er, ['Apellido y nombre', 'Empleado', 'Nombre'])
                    if str(en or '').strip().lower() == str(empleado).strip().lower():
                        if not emp_id: emp_id = self._get_row_prop(er, ['ID empleado', 'ID'])
                        if not emp_cuit: emp_cuit = str(self._get_row_prop(er, ['CUIL', 'DNI']) or '').strip()
                        break

            if ('cheque' in str(medio_pago).lower()) and cheque_id and 'CHEQUES' in wb.sheetnames:
                ws_chq = wb['CHEQUES']
                target_chq_row = None
                for r in range(5, ws_chq.max_row + 1):
                    if str(ws_chq.cell(r, 1).value or '').strip() == str(cheque_id).strip():
                        target_chq_row = r
                        break
                if target_chq_row:
                    if not nro_cheque: nro_cheque = str(ws_chq.cell(target_chq_row, 8).value or '')
                    if not banco_cheque: banco_cheque = str(ws_chq.cell(target_chq_row, 7).value or 'Banco')
                    medio_egreso = f"Cheque N° {nro_cheque} ({banco_cheque})" if nro_cheque else f"Cheque {cheque_id}"
                    ws_chq.cell(target_chq_row, 5, empleado)
                    ws_chq.cell(target_chq_row, 10, empleado)
                    ws_chq.cell(target_chq_row, 11, 'Entregado Personal')
                    ws_chq.cell(target_chq_row, 12, f"Adelanto/Viático Chofer: {empleado}")
                    ws_chq.cell(target_chq_row, 13, fecha)
                    if egr_id: ws_chq.cell(target_chq_row, 14, egr_id)
                    cur_obs = str(ws_chq.cell(target_chq_row, 16).value or '').strip()
                    ws_chq.cell(target_chq_row, 16, f"{cur_obs} | Novedad {nov_id}".strip(' |'))

            # Insert Egreso in Excel if deduction and not surplus
            if is_deduccion and 'excedente' not in str(medio_pago).lower() and 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                if not egr_id:
                    max_e = 0
                    for r in range(5, ws_e.max_row + 1):
                        v_e = str(ws_e.cell(r, 1).value or '').strip()
                        if v_e.startswith('EGR-'):
                            try:
                                ne = int(v_e.replace('EGR-', ''))
                                if ne > max_e: max_e = ne
                            except: pass
                    egr_id = f"EGR-{max_e + 1:06d}"

                desc_egreso = f"Adelanto de Sueldo: {concepto} ({medio_egreso})"
                obs_egreso = f"[NOVEDAD: {nov_id}] {concepto} | Empleado: {empleado}"
                ws_e.append([
                    egr_id, fecha, fecha, 'Adelanto de Sueldo', 'Personal', empleado, emp_cuit,
                    'Recibo de Adelanto', nov_id, '', emp_id or empleado, desc_egreso,
                    0, monto, 0, monto, 'Pagado', monto, fecha, medio_egreso, 0, '', '', obs_egreso
                ])

            next_row = ws_nov.max_row + 1
            row_vals = [
                nov_id, fecha, emp_id or empleado, empleado, tipo,
                concepto, monto, medio_egreso, cheque_id, nro_cheque,
                '', 'Pendiente', observaciones
            ]
            for col_idx, val in enumerate(row_vals, 1):
                ws_nov.cell(next_row, col_idx, val)

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[add_novedad_personal Excel Warning] {e}")

        return {
            "status": "success",
            "id": nov_id,
            "id_egreso": egr_id,
            "tipo": tipo,
            "monto": monto,
            "empleado": empleado,
            "medio_pago": medio_egreso
        }

    def delete_novedad_personal(self, nov_id):
        """Deletes a pending novelty (advance or reimbursement), deletes any linked Egreso,
        and restores any third-party portfolio check back to Disponible."""
        nov_id = str(nov_id or '').strip()
        if not nov_id:
            return {"status": "error", "message": "ID de novedad es requerido."}

        # 1. Supabase Master Execution
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    nov = conn.execute(text("SELECT id_novedad, estado, id_cheque, id_liquidacion FROM novedades_personal WHERE id_novedad = :nid"), {'nid': nov_id}).first()
                    if not nov:
                        return {"status": "error", "message": f"Novedad {nov_id} no encontrada."}
                    
                    st = str(nov[1] or '').strip().lower()
                    cid = str(nov[2] or '').strip()
                    lid = str(nov[3] or '').strip()
                    if st == 'liquidado' or lid:
                        return {"status": "error", "message": f"La novedad {nov_id} ya fue liquidada (Liquidación {lid}). No se puede eliminar directamente. Debe anular primero la liquidación histórica correspondiente."}

                    # Revert check if any
                    if cid:
                        conn.execute(text("""
                            UPDATE cheques SET
                                estado = 'Disponible',
                                endosado_tenedor = NULL,
                                destino_usado_en = NULL,
                                fecha_uso = NULL,
                                id_egreso = NULL,
                                updated_at = NOW()
                            WHERE id_cheque = :cid;
                        """), {'cid': cid})

                    # Delete linked egreso if generated for this novelty
                    conn.execute(text("""
                        DELETE FROM egresos 
                        WHERE observaciones LIKE :pat OR nro_comprobante = :nid;
                    """), {'pat': f"%[NOVEDAD: {nov_id}]%", 'nid': nov_id})

                    # Delete novelty
                    conn.execute(text("DELETE FROM novedades_personal WHERE id_novedad = :nid"), {'nid': nov_id})
            except Exception as e:
                print(f"[delete_novedad_personal Supabase Error] {e}")
                return {"status": "error", "message": f"Error al eliminar en base de datos: {str(e)}"}

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            chq_id_excel = None
            if 'NOVEDADES_PERSONAL' in wb.sheetnames:
                ws_nov = wb['NOVEDADES_PERSONAL']
                target_nov_row = None
                for r in range(5, ws_nov.max_row + 1):
                    if str(ws_nov.cell(r, 1).value or '').strip() == nov_id:
                        target_nov_row = r
                        chq_id_excel = str(ws_nov.cell(r, 9).value or '').strip()
                        break
                if target_nov_row:
                    ws_nov.delete_rows(target_nov_row)

            if 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                for r in range(ws_e.max_row, 4, -1):
                    obs_cell = str(ws_e.cell(r, 24).value or '')
                    nro_comp_cell = str(ws_e.cell(r, 9).value or '')
                    if f"[NOVEDAD: {nov_id}]" in obs_cell or nro_comp_cell == nov_id:
                        ws_e.delete_rows(r)

            if 'CHEQUES' in wb.sheetnames and chq_id_excel:
                ws_c = wb['CHEQUES']
                for r in range(5, ws_c.max_row + 1):
                    if str(ws_c.cell(r, 1).value or '').strip() == chq_id_excel:
                        ws_c.cell(r, 5, '')
                        ws_c.cell(r, 10, '')
                        ws_c.cell(r, 11, 'Disponible')
                        ws_c.cell(r, 12, '')
                        ws_c.cell(r, 13, '')
                        ws_c.cell(r, 14, '')
                        break

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[delete_novedad_personal Excel Warning] {e}")

        return {"status": "success", "message": f"Novedad {nov_id} eliminada correctamente."}

    def get_novedades_personal(self, quincena='todas', empleado_nombre=None, estado=None, mes=None, anio=None, fecha_desde=None, fecha_hasta=None):
        """Returns novelties (advances/reimbursements) filtered by quincena, employee, status, month, year or date range."""
        _, rows = self.get_sheet_data('NOVEDADES_PERSONAL')
        if not rows:
            try:
                wb = self.load_wb(data_only=True)
                if 'NOVEDADES_PERSONAL' in wb.sheetnames:
                    _, rows = self._read_sheet_rows(wb['NOVEDADES_PERSONAL'])
            except Exception:
                pass
        novedades = []
        
        emp_norm = str(empleado_nombre or '').strip().lower() if empleado_nombre else None
        est_norm = str(estado or '').strip().lower() if estado else None
        target_month = int(mes) if mes else None
        target_year = int(anio) if anio else None
        if fecha_desde:
            try:
                p_d = str(fecha_desde).split('-')
                if len(p_d) >= 2:
                    if not target_year: target_year = int(p_d[0])
                    if not target_month: target_month = int(p_d[1])
            except: pass

        for r in rows:
            nid = self._get_row_prop(r, ['ID novedad', 'ID', 'id_novedad', 'id'])
            if not nid or not str(nid).startswith('NOV-'):
                continue
                
            emp_r = self._get_row_prop(r, ['Empleado', 'Nombre', 'empleado'])
            if emp_norm and str(emp_r or '').strip().lower() != emp_norm:
                continue
                
            st_r = str(self._get_row_prop(r, ['Estado', 'estado']) or 'Pendiente').strip()
            if est_norm and st_r.lower() != est_norm:
                continue
                
            fecha = self._get_row_prop(r, ['Fecha', 'fecha'])
            
            if fecha:
                try:
                    f_iso = str(fecha).split('T')[0].split(' ')[0]
                    if fecha_desde and f_iso < str(fecha_desde).strip():
                        continue
                    if fecha_hasta and f_iso > str(fecha_hasta).strip():
                        continue

                    parts = f_iso.split('-')
                    if len(parts) >= 3:
                        y = int(parts[0])
                        m = int(parts[1])
                        d = int(parts[2])

                        if not fecha_desde and not fecha_hasta:
                            if target_year and y != target_year:
                                continue
                            if target_month and m != target_month:
                                continue

                        if quincena in ['q1', '1', '1a_quincena', 'quincena1'] and d > 15:
                            continue
                        elif quincena in ['q2', '2', '2a_quincena', 'quincena2'] and d <= 15:
                            continue
                except Exception:
                    pass
            elif target_month or target_year or fecha_desde or fecha_hasta or quincena != 'todas':
                continue
                
            tipo = self._get_row_prop(r, ['Tipo', 'tipo']) or 'Deducción'
            monto = self._to_float(self._get_row_prop(r, ['Monto', 'Importe', 'monto']))
            
            novedades.append({
                'id': nid,
                'fecha': fecha,
                'id_empleado': self._get_row_prop(r, ['ID empleado', 'id_empleado']),
                'empleado': emp_r,
                'tipo': tipo,
                'concepto': self._get_row_prop(r, ['Concepto', 'concepto']),
                'monto': monto,
                'medio_pago': self._get_row_prop(r, ['Medio pago', 'Medio de pago', 'medio_pago']),
                'id_cheque': self._get_row_prop(r, ['ID cheque', 'Cheque ID', 'Cheque', 'id_cheque']),
                'cheque_id': self._get_row_prop(r, ['ID cheque', 'Cheque ID', 'Cheque', 'id_cheque', 'cheque_id']),
                'nro_cheque': self._get_row_prop(r, ['N° cheque', 'Nro cheque', 'Nro Cheque', 'nro_cheque']),
                'id_liquidacion': self._get_row_prop(r, ['ID liquidación', 'ID Liquidación', 'id_liquidacion', 'ID liquidacion']),
                'estado': st_r,
                'observaciones': self._get_row_prop(r, ['Observaciones', 'observaciones'])
            })
            
        return sorted(novedades, key=lambda x: str(x.get('fecha') or ''))

    def get_liquidaciones_personal(self, quincena='todas', mes=None, anio=None, fecha_desde=None, fecha_hasta=None):
        wb = self.load_wb(data_only=True)
        _, empleados_data = self.get_sheet_data('EMPLEADOS')
        if not empleados_data and 'EMPLEADOS' in wb.sheetnames:
            _, empleados_data = self._read_sheet_rows(wb['EMPLEADOS'])
        _, viajes_data = self._read_sheet_rows(wb['VIAJES']) if 'VIAJES' in wb.sheetnames else ([], [])
        _, ingresos_data = self._read_sheet_rows(wb['INGRESOS']) if 'INGRESOS' in wb.sheetnames else ([], [])

        liquidaciones = []
        target_month = int(mes) if mes else None
        target_year = int(anio) if anio else None
        if fecha_desde:
            try:
                p_d = str(fecha_desde).split('-')
                if len(p_d) >= 2:
                    if not target_year: target_year = int(p_d[0])
                    if not target_month: target_month = int(p_d[1])
            except: pass

        for emp in empleados_data:
            eid = self._get_row_prop(emp, ['ID empleado', 'ID', 'id_empleado'])
            nombre = self._get_row_prop(emp, ['Apellido y nombre', 'Empleado', 'Nombre', 'apellido_nombre'])
            if not eid or not nombre or 'completar' in nombre.lower():
                continue

            # Excluir empleados dados de baja, inactivos o no vigentes
            estado_emp = str(self._get_row_prop(emp, ['Estado', 'estado']) or '').strip().lower()
            if estado_emp in ['baja', 'inactivo', 'inactiva', 'eliminado', '0']:
                continue
            
            puesto = self._get_row_prop(emp, ['Cargo / Puesto', 'Puesto']) or 'Chofer'
            sueldo_fijo_mensual = self._to_float(self._get_row_prop(emp, ['Sueldo fijo', 'Sueldo']))
            comision_pct = self._to_float(self._get_row_prop(emp, ['Porcentaje comisión (%)', 'Porcentaje comision', 'Comisión %', 'comision_pct']))

            if quincena in ['q1', '1', '1a_quincena', 'quincena1']:
                sueldo_fijo_base = round(sueldo_fijo_mensual / 2.0, 2)
                periodo_label = "1ª Quincena (Días 1 al 15)"
            elif quincena in ['q2', '2', '2a_quincena', 'quincena2']:
                sueldo_fijo_base = round(sueldo_fijo_mensual / 2.0, 2)
                periodo_label = "2ª Quincena (Días 16 al 30/31)"
            else:
                sueldo_fijo_base = round(sueldo_fijo_mensual, 2)
                periodo_label = "Mes Completo (1ª y 2ª Quincena)"

            viajes_asignados = []
            total_facturado_viajes = 0.0
            total_comisiones_generadas = 0.0

            nombre_tokens = [t.lower() for t in nombre.split() if len(t) > 2]

            def filter_by_quincena(fecha_str):
                if not fecha_str:
                    return False if (fecha_desde or fecha_hasta) else True
                try:
                    f_iso = str(fecha_str).split('T')[0].split(' ')[0]
                    if fecha_desde and f_iso < str(fecha_desde).strip():
                        return False
                    if fecha_hasta and f_iso > str(fecha_hasta).strip():
                        return False

                    parts = f_iso.split('-')
                    if len(parts) >= 3:
                        year = int(parts[0])
                        month = int(parts[1])
                        day = int(parts[2])

                        if not fecha_desde and not fecha_hasta:
                            if target_year and year != target_year:
                                return False
                            if target_month and month != target_month:
                                return False

                        if quincena in ['q1', '1', '1a_quincena', 'quincena1']:
                            return day <= 15
                        elif quincena in ['q2', '2', '2a_quincena', 'quincena2']:
                            return day > 15
                except Exception:
                    pass
                return True

            # Index INGRESOS by associated trip ID (from 'Operación origen: VIA-XXXXXX')
            ingresos_by_viaje = {}
            standalone_ingresos = []

            for ing in ingresos_data:
                tipo_comp = str(self._get_row_prop(ing, ['Tipo comprobante', 'Tipo']) or '').strip()
                # Exclude payment receipts / advances / entregas cc
                if tipo_comp in ['Adelanto / Seña', 'Entrega CC', 'Vuelto Proveedor'] or 'entrega' in tipo_comp.lower() or 'seña' in tipo_comp.lower() or 'adelanto' in tipo_comp.lower():
                    continue

                obs = str(self._get_row_prop(ing, ['Observaciones']) or '')
                assoc_viaje = ''
                if 'Operación origen:' in obs:
                    assoc_viaje = obs.split('Operación origen:')[1].strip().split(' ')[0]
                elif 'VIA-' in obs:
                    m_v = re.search(r'VIA-\d+', obs)
                    if m_v: assoc_viaje = m_v.group(0)

                if assoc_viaje:
                    ingresos_by_viaje[assoc_viaje] = ing
                else:
                    standalone_ingresos.append(ing)

            # 1. Process operational VIAJES assigned to this driver
            for v in viajes_data:
                chofer_v = self._get_row_prop(v, ['Chofer'])
                if not chofer_v or chofer_v.startswith('POR ASIGNAR'):
                    continue
                
                chofer_v_lower = chofer_v.lower()
                is_match = any(t in chofer_v_lower for t in nombre_tokens) if nombre_tokens else (chofer_v_lower == nombre.lower())
                
                if is_match:
                    fecha = self._get_row_prop(v, ['Fecha salida', 'Fecha'])
                    if not filter_by_quincena(fecha):
                        continue

                    v_id = self._get_row_prop(v, ['ID viaje', 'ID'])
                    cliente = self._get_row_prop(v, ['Cliente'])
                    actividad = self._get_row_prop(v, ['Actividad']) or 'Servicio de Flete'

                    # Check if trip was billed in INGRESOS
                    linked_ing = ingresos_by_viaje.get(v_id)
                    if linked_ing:
                        nro_factura = self._get_row_prop(linked_ing, ['N° factura ARCA', 'Factura']) or 'Facturado'
                        monto_neto = self._to_float(self._get_row_prop(linked_ing, ['Neto']))
                        if monto_neto <= 0:
                            monto_neto = self._to_float(self._get_row_prop(linked_ing, ['Total']))
                    else:
                        nro_factura = "Pendiente Facturación"
                        val_srv = self._to_float(self._get_row_prop(v, ['Valor servicio']))
                        ext_val = self._to_float(self._get_row_prop(v, ['extras_monto']))
                        monto_neto = val_srv + ext_val

                    act_lower = (actividad + " " + str(self._get_row_prop(v, ['Carga']) or '')).lower()
                    is_non_granel = any(k in act_lower for k in ['grúa', 'grua', 'municipal', 'bodoque', 'basura', 'excavacion', 'excavación', 'alquiler'])
                    is_granel = any(k in act_lower for k in ['granel', '492229', 'flete', 'transporte', 'viaje', 'cereal', 'grano', 'maiz', 'maíz', 'soja', 'trigo', 'sorgo', 'piedra', 'arena', 'carga'])
                    
                    aplica_comision = is_granel and (not is_non_granel) and (comision_pct > 0)

                    if aplica_comision:
                        comision_ganada = round(monto_neto * (comision_pct / 100.0), 2)
                        motivo = f"Aplica Comisión Transporte Granel ({comision_pct}%)"
                    else:
                        comision_ganada = 0.0
                        motivo = "No aplica comisión (Grúa, Municipal, Bodoque, Basura o no Granel)"

                    total_facturado_viajes += monto_neto
                    total_comisiones_generadas += comision_ganada

                    viajes_asignados.append({
                        "id": v_id,
                        "nro_factura": nro_factura,
                        "fecha": fecha,
                        "cliente": cliente,
                        "actividad": actividad,
                        "monto_neto": monto_neto,
                        "comision_pct": comision_pct if aplica_comision else 0.0,
                        "comision_ganada": comision_ganada,
                        "aplica_comision": aplica_comision,
                        "motivo": motivo
                    })

            # 2. Process standalone INGRESOS (direct invoices not linked to a VIA-XXXXXX trip)
            for ing in standalone_ingresos:
                chofer_ing = self._get_row_prop(ing, ['Chofer'])
                if not chofer_ing:
                    continue

                chofer_ing_lower = chofer_ing.lower()
                is_match = any(t in chofer_ing_lower for t in nombre_tokens) if nombre_tokens else (chofer_ing_lower == nombre.lower())

                if is_match:
                    fecha = self._get_row_prop(ing, ['Fecha emisión', 'Fecha cobro', 'Fecha'])
                    if not filter_by_quincena(fecha):
                        continue

                    ing_id = self._get_row_prop(ing, ['ID ingreso', 'ID'])
                    if any(item['id'] == ing_id for item in viajes_asignados):
                        continue

                    nro_factura = self._get_row_prop(ing, ['N° factura ARCA', 'Factura']) or 'Pendiente ARCA'
                    cliente = self._get_row_prop(ing, ['Cliente'])
                    actividad = self._get_row_prop(ing, ['Actividad']) or 'Servicio de Flete'
                    
                    neto = self._to_float(self._get_row_prop(ing, ['Neto']))
                    if neto <= 0:
                        neto = self._to_float(self._get_row_prop(ing, ['Total']))

                    act_lower = (actividad + " " + str(self._get_row_prop(ing, ['Carga', 'Detalle/Concepto', 'Subtipo']) or '')).lower()
                    is_non_granel = any(k in act_lower for k in ['grúa', 'grua', 'municipal', 'bodoque', 'basura', 'excavacion', 'excavación', 'alquiler'])
                    is_granel = any(k in act_lower for k in ['granel', '492229', 'flete', 'transporte', 'viaje', 'cereal', 'grano', 'maiz', 'maíz', 'soja', 'trigo', 'sorgo', 'piedra', 'arena', 'carga'])
                    
                    aplica_comision = is_granel and (not is_non_granel) and (comision_pct > 0)

                    if aplica_comision:
                        comision_ganada = round(neto * (comision_pct / 100.0), 2)
                        motivo = f"Aplica Comisión Transporte Granel ({comision_pct}%)"
                    else:
                        comision_ganada = 0.0
                        motivo = "No aplica comisión (Grúa, Municipal, Bodoque, Basura o no Granel)"

                    total_facturado_viajes += neto
                    total_comisiones_generadas += comision_ganada

                    viajes_asignados.append({
                        "id": ing_id,
                        "nro_factura": nro_factura,
                        "fecha": fecha,
                        "cliente": cliente,
                        "actividad": actividad,
                        "monto_neto": neto,
                        "comision_pct": comision_pct if aplica_comision else 0.0,
                        "comision_ganada": comision_ganada,
                        "aplica_comision": aplica_comision,
                        "motivo": motivo
                    })

            # Fetch novelties (advances / expense reimbursements) for this employee, quincena, month, year or date range
            novedades_emp = self.get_novedades_personal(
                quincena=quincena,
                empleado_nombre=nombre,
                mes=target_month,
                anio=target_year,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta
            )
            tot_reintegros = sum(float(n['monto']) for n in novedades_emp if 'reintegr' in str(n.get('tipo', '')).lower())
            tot_deducciones = sum(float(n['monto']) for n in novedades_emp if 'deduc' in str(n.get('tipo', '')).lower() or 'adelant' in str(n.get('tipo', '')).lower())

            sueldo_final = max(0.0, (sueldo_fijo_base + total_comisiones_generadas + tot_reintegros) - tot_deducciones)

            liquidaciones.append({
                "id_empleado": eid,
                "nombre": nombre,
                "puesto": puesto,
                "dni": self._get_row_prop(emp, ['DNI']),
                "cuil": self._get_row_prop(emp, ['CUIL']),
                "banco": self._get_row_prop(emp, ['Entidad bancaria', 'Banco']),
                "cbu": self._get_row_prop(emp, ['CBU']),
                "alias_cbu": self._get_row_prop(emp, ['Alias CBU', 'Alias']),
                "sueldo_fijo_mensual": sueldo_fijo_mensual,
                "sueldo_fijo_base": sueldo_fijo_base,
                "comision_pct": comision_pct,
                "quincena": quincena,
                "periodo_label": periodo_label,
                "cant_viajes": len(viajes_asignados),
                "total_facturado": round(total_facturado_viajes, 2),
                "total_comisiones": round(total_comisiones_generadas, 2),
                "tot_reintegros": round(tot_reintegros, 2),
                "tot_deducciones": round(tot_deducciones, 2),
                "novedades": novedades_emp,
                "novedades_emp": novedades_emp,
                "sueldo_final": round(sueldo_final, 2),
                "desglose_viajes": viajes_asignados
            })

        return liquidaciones

    def check_empleado_dependencies(self, e_id, nombre=""):
        e_id = str(e_id or '').strip()
        nombre = str(nombre or '').strip().lower()
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    v = conn.execute(text("""
                        SELECT count(*) FROM viajes 
                        WHERE LOWER(TRIM(chofer)) = :nom OR TRIM(chofer) = :eid
                    """), {'nom': nombre, 'eid': e_id}).scalar() or 0
                    l = conn.execute(text("""
                        SELECT count(*) FROM liquidaciones 
                        WHERE id_empleado = :eid OR LOWER(TRIM(empleado)) = :nom
                    """), {'eid': e_id, 'nom': nombre}).scalar() or 0
                    n = conn.execute(text("""
                        SELECT count(*) FROM novedades_personal 
                        WHERE id_empleado = :eid OR LOWER(TRIM(empleado)) = :nom
                    """), {'eid': e_id, 'nom': nombre}).scalar() or 0
                    return {'viajes': int(v), 'liquidaciones': int(l), 'novedades': int(n), 'total': int(v + l + n)}
            except Exception as e:
                print(f"[check_empleado_dependencies DB Error] {e}")
        return {'viajes': 0, 'liquidaciones': 0, 'novedades': 0, 'total': 0}

    def delete_empleado(self, e_id):
        e_id_clean = str(e_id).strip()
        wb = self.load_wb(data_only=False)
        ws = wb['EMPLEADOS']
        
        target_row = None
        nombre = ""
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == e_id_clean:
                target_row = r
                nombre = str(ws.cell(r, 2).value or '').strip()
                break
        
        # Eliminar fila en Excel si existe
        if target_row:
            ws.delete_rows(target_row)
            wb.save(self.excel_path)

        # Eliminar registro en Supabase PostgreSQL (los viajes históricos quedan intactos con su chofer)
        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'EMPLEADOS', e_id_clean)

        return {"status": "success", "id": e_id_clean, "nombre": nombre}

    def validate_proveedor(self, pdata, exclude_id=None):
        import re
        p_cuit = str(pdata.get('cuit', '')).strip()
        cuit_digits = re.sub(r'\D', '', p_cuit)
        p_id = str(exclude_id or pdata.get('id') or pdata.get('id_proveedor') or '').strip()

        existing_provs = []

        # Obtener proveedores existentes de Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    query = text("SELECT id_proveedor, razon_social, cuit, estado FROM proveedores WHERE estado IS NULL OR LOWER(TRIM(estado)) != 'eliminado'")
                    rows = conn.execute(query).fetchall()
                    for r in rows:
                        existing_provs.append({
                            'id': str(r[0] or '').strip(),
                            'razon_social': str(r[1] or '').strip(),
                            'cuit': str(r[2] or '').strip(),
                            'estado': str(r[3] or '').strip().lower()
                        })
            except Exception as e:
                print(f"[validate_proveedor Supabase Error] {e}")

        # Si no se obtuvieron de Supabase, leer de Excel
        if not existing_provs:
            wb = self.load_wb(data_only=True)
            if 'PROVEEDORES' in wb.sheetnames:
                _, rows = self._read_sheet_rows(wb['PROVEEDORES'])
                for r in rows:
                    existing_provs.append({
                        'id': str(r.get('ID proveedor') or r.get('ID') or '').strip(),
                        'razon_social': str(r.get('Razón social / Nombre') or r.get('Razón social') or r.get('Nombre') or '').strip(),
                        'cuit': str(r.get('CUIT') or r.get('CUIT / CUIL') or '').strip(),
                        'estado': str(r.get('Estado') or '').strip().lower()
                    })

        # Evaluar unicidad del CUIT/CUIL
        if cuit_digits:
            for ep in existing_provs:
                if p_id and ep['id'] == p_id:
                    continue
                if ep['estado'] == 'eliminado':
                    continue

                ep_cuit = ep['cuit']
                if ep_cuit:
                    ep_cuit_digits = re.sub(r'\D', '', ep_cuit)
                    if len(cuit_digits) == 11 and len(ep_cuit_digits) == 11 and cuit_digits == ep_cuit_digits:
                        ep_nombre = ep['razon_social'] or ep['id']
                        return {
                            "valid": False,
                            "field": "cuit",
                            "message": f"Ya existe un proveedor registrado con el CUIT/CUIL '{p_cuit}' ({ep_nombre}, ID: {ep['id']})."
                        }

        return {"valid": True}

    def add_proveedor(self, pdata):
        validation = self.validate_proveedor(pdata, exclude_id=None)
        if not validation['valid']:
            return {"status": "error", "message": validation['message'], "field": validation.get('field')}

        wb = self.load_wb(data_only=False)
        ws = wb['PROVEEDORES']
        new_id = self._get_next_entity_id(ws, 'PROV')
        
        # Sincronizar ID correlativo con Supabase si corresponde
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_proveedor FROM proveedores WHERE id_proveedor LIKE 'PROV-%'")).fetchall()
                    max_num = 0
                    for (pid_val,) in max_id_rows:
                        try:
                            num = int(str(pid_val).split('-')[-1])
                            if num > max_num:
                                max_num = num
                        except:
                            pass
                    wb_num = int(new_id.split('-')[-1]) if '-' in new_id else 0
                    if max_num >= wb_num:
                        new_id = f"PROV-{max_num + 1:06d}"
            except Exception as e:
                print(f"[add_proveedor Supabase ID Error] {e}")

        p_razon = str(pdata.get('razon_social', '')).strip()
        p_com = str(pdata.get('nombre_comercial', '')).strip()
        p_cuit = str(pdata.get('cuit', '')).strip()
        p_rubro = str(pdata.get('rubro', 'Combustible')).strip()
        p_tel = str(pdata.get('telefono', '')).strip()
        p_correo = str(pdata.get('correo', '')).strip()
        p_cond = str(pdata.get('condicion_pago', 'Cuenta corriente')).strip()
        p_saldo = self._to_float(pdata.get('saldo_inicial', 0))
        p_fsaldo = self._clean_date(pdata.get('fecha_saldo_inicial'))
        p_obs = str(pdata.get('observaciones', '')).strip()
        p_cbu = str(pdata.get('cbu_alias', pdata.get('cbu', ''))).strip()

        # Inserción directa y síncrona en Supabase PostgreSQL
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO proveedores (
                            id_proveedor, razon_social, nombre_comercial, cuit, rubro,
                            telefono, correo, condicion_pago, saldo_inicial, fecha_saldo_inicial,
                            estado, observaciones, cbu_alias, updated_at
                        ) VALUES (
                            :id, :razon, :com, :cuit, :rubro,
                            :tel, :correo, :cond, :saldo, :fsaldo,
                            'Activo', :obs, :cbu, NOW()
                        )
                        ON CONFLICT (id_proveedor) DO UPDATE SET
                            razon_social = EXCLUDED.razon_social,
                            nombre_comercial = EXCLUDED.nombre_comercial,
                            cuit = EXCLUDED.cuit,
                            rubro = EXCLUDED.rubro,
                            telefono = EXCLUDED.telefono,
                            correo = EXCLUDED.correo,
                            condicion_pago = EXCLUDED.condicion_pago,
                            saldo_inicial = EXCLUDED.saldo_inicial,
                            fecha_saldo_inicial = EXCLUDED.fecha_saldo_inicial,
                            estado = 'Activo',
                            observaciones = EXCLUDED.observaciones,
                            cbu_alias = EXCLUDED.cbu_alias,
                            updated_at = NOW()
                    """), {
                        'id': new_id,
                        'razon': p_razon,
                        'com': p_com,
                        'cuit': p_cuit,
                        'rubro': p_rubro,
                        'tel': p_tel,
                        'correo': p_correo,
                        'cond': p_cond,
                        'saldo': p_saldo,
                        'fsaldo': p_fsaldo,
                        'obs': p_obs,
                        'cbu': p_cbu
                    })
            except Exception as e:
                print(f"[add_proveedor Supabase Direct Insert Error] {e}")

        if ws.cell(4, 13).value is None or str(ws.cell(4, 13).value).strip() == '':
            ws.cell(4, 13, 'CBU / ALIAS')

        row_vals = [
            new_id,
            p_razon,
            p_com,
            p_cuit,
            p_rubro,
            p_tel,
            p_correo,
            p_cond,
            p_saldo,
            pdata.get('fecha_saldo_inicial', ''),
            'Activo',
            p_obs,
            p_cbu
        ]
        ws.append(row_vals)
        wb.save(self.excel_path)
        return {"status": "success", "id": new_id, "nombre": p_razon}

    def update_proveedor(self, p_id, pdata):
        validation = self.validate_proveedor(pdata, exclude_id=p_id)
        if not validation['valid']:
            return {"status": "error", "message": validation['message'], "field": validation.get('field')}

        wb = self.load_wb(data_only=False)
        ws = wb['PROVEEDORES']
        
        if ws.cell(4, 13).value is None or str(ws.cell(4, 13).value).strip() == '':
            ws.cell(4, 13, 'CBU / ALIAS')

        headers, rows = self._read_sheet_rows(ws)
        target_row_idx = None
        for r in rows:
            if str(r.get('ID proveedor') or r.get('ID')).strip() == str(p_id).strip():
                target_row_idx = r['_row_idx']
                break

        if target_row_idx:
            if 'razon_social' in pdata: ws.cell(target_row_idx, 2, pdata['razon_social'])
            if 'nombre_comercial' in pdata: ws.cell(target_row_idx, 3, pdata['nombre_comercial'])
            if 'cuit' in pdata: ws.cell(target_row_idx, 4, pdata['cuit'])
            if 'rubro' in pdata: ws.cell(target_row_idx, 5, pdata['rubro'])
            if 'telefono' in pdata: ws.cell(target_row_idx, 6, pdata['telefono'])
            if 'correo' in pdata: ws.cell(target_row_idx, 7, pdata['correo'])
            if 'condicion_pago' in pdata: ws.cell(target_row_idx, 8, pdata['condicion_pago'])
            if 'observaciones' in pdata: ws.cell(target_row_idx, 12, pdata['observaciones'])
            if 'cbu_alias' in pdata or 'cbu' in pdata:
                ws.cell(target_row_idx, 13, pdata.get('cbu_alias', pdata.get('cbu', '')))
            wb.save(self.excel_path)

        # Actualización directa y síncrona en Supabase PostgreSQL
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                update_fields = []
                params = {'pid': p_id}
                if 'razon_social' in pdata:
                    update_fields.append("razon_social = :razon")
                    params['razon'] = str(pdata['razon_social']).strip()
                if 'nombre_comercial' in pdata:
                    update_fields.append("nombre_comercial = :com")
                    params['com'] = str(pdata['nombre_comercial']).strip()
                if 'cuit' in pdata:
                    update_fields.append("cuit = :cuit")
                    params['cuit'] = str(pdata['cuit']).strip()
                if 'rubro' in pdata:
                    update_fields.append("rubro = :rubro")
                    params['rubro'] = str(pdata['rubro']).strip()
                if 'telefono' in pdata:
                    update_fields.append("telefono = :tel")
                    params['tel'] = str(pdata['telefono']).strip()
                if 'correo' in pdata:
                    update_fields.append("correo = :correo")
                    params['correo'] = str(pdata['correo']).strip()
                if 'condicion_pago' in pdata:
                    update_fields.append("condicion_pago = :cond")
                    params['cond'] = str(pdata['condicion_pago']).strip()
                if 'saldo_inicial' in pdata:
                    update_fields.append("saldo_inicial = :saldo")
                    params['saldo'] = self._to_float(pdata['saldo_inicial'])
                if 'fecha_saldo_inicial' in pdata:
                    update_fields.append("fecha_saldo_inicial = :fsaldo")
                    params['fsaldo'] = self._clean_date(pdata['fecha_saldo_inicial'])
                if 'observaciones' in pdata:
                    update_fields.append("observaciones = :obs")
                    params['obs'] = str(pdata['observaciones']).strip()
                if 'cbu_alias' in pdata or 'cbu' in pdata:
                    update_fields.append("cbu_alias = :cbu")
                    params['cbu'] = str(pdata.get('cbu_alias', pdata.get('cbu', ''))).strip()

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    sql = f"UPDATE proveedores SET {', '.join(update_fields)} WHERE id_proveedor = :pid"
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text(sql), params)
            except Exception as e:
                print(f"[update_proveedor Supabase Direct Update Error] {e}")

        if not target_row_idx and not (self.supabase_service and self.supabase_service.is_connected()):
            return {"status": "error", "message": f"Proveedor {p_id} no encontrado."}

        return {"status": "success", "id": p_id}

    def check_proveedor_dependencies(self, p_id, razon_social="", cuit=""):
        p_id = str(p_id or '').strip()
        razon_social = str(razon_social or '').strip().lower()
        cuit = str(cuit or '').strip()
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    o = conn.execute(text("""
                        SELECT count(*) FROM ordenes_compra 
                        WHERE LOWER(TRIM(proveedor)) = :nom OR (:cuit <> '' AND cuit_proveedor = :cuit)
                    """), {'nom': razon_social, 'cuit': cuit}).scalar() or 0
                    e = conn.execute(text("""
                        SELECT count(*) FROM egresos 
                        WHERE LOWER(TRIM(proveedor)) = :nom OR (:cuit <> '' AND cuit = :cuit)
                    """), {'nom': razon_social, 'cuit': cuit}).scalar() or 0
                    return {'ordenes': int(o), 'egresos': int(e), 'total': int(o + e)}
            except Exception as e:
                print(f"[check_proveedor_dependencies DB Error] {e}")

        wb = self.load_wb(data_only=True)
        o, e = 0, 0
        if 'ORDENES_COMPRA' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['ORDENES_COMPRA'])
            o = sum(1 for r in rows if str(r.get('Proveedor', '')).strip().lower() == razon_social or (cuit and str(r.get('CUIT proveedor', '')).strip() == cuit))
        if 'EGRESOS' in wb.sheetnames:
            _, rows = self._read_sheet_rows(wb['EGRESOS'])
            e = sum(1 for r in rows if str(r.get('Proveedor', '')).strip().lower() == razon_social or (cuit and str(r.get('CUIT', '')).strip() == cuit))
        return {'ordenes': o, 'egresos': e, 'total': o + e}

    def delete_proveedor(self, p_id):
        wb = self.load_wb(data_only=False)
        ws = wb['PROVEEDORES']
        headers, rows = self._read_sheet_rows(ws)
        target_row_idx = None
        prov_data = None
        for r in rows:
            if str(r.get('ID proveedor') or r.get('ID')).strip() == str(p_id).strip():
                target_row_idx = r['_row_idx']
                prov_data = r
                break

        if not target_row_idx:
            if self.supabase_service and self.supabase_service.is_connected():
                from supabase_sync import delete_row_from_supabase
                delete_row_from_supabase(self.supabase_service.engine, 'PROVEEDORES', p_id)
                return {"status": "success", "id": p_id}
            return {"status": "error", "message": f"Proveedor {p_id} no encontrado."}

        p_name = str(prov_data.get('Razón social') or '').strip()
        p_cuit = str(prov_data.get('CUIT') or '').strip()

        deps = self.check_proveedor_dependencies(p_id, p_name, p_cuit)
        if deps['total'] > 0:
            details = []
            if deps['ordenes']: details.append(f"{deps['ordenes']} orden(es) de compra")
            if deps['egresos']: details.append(f"{deps['egresos']} egreso(s)/gasto(s)")
            return {
                "status": "error",
                "message": f"No se puede eliminar al proveedor '{p_name or p_id}' porque posee: {', '.join(details)}. Elimine o reasigne sus comprobantes primero."
            }

        ws.delete_rows(target_row_idx)
        wb.save(self.excel_path)

        if self.supabase_service and self.supabase_service.is_connected():
            from supabase_sync import delete_row_from_supabase
            delete_row_from_supabase(self.supabase_service.engine, 'PROVEEDORES', p_id)

        return {"status": "success", "id": p_id}

    def get_dashboard_data(self, anio=None):
        wb = self.load_wb(data_only=True)
        
        _, ingresos_raw = self.get_sheet_data('INGRESOS')
        _, egresos_raw = self.get_sheet_data('EGRESOS')
        _, viajes_raw = self.get_sheet_data('VIAJES')
        _, remu_raw = self.get_sheet_data('REMUNERACIONES')
        
        target_year = None
        if anio and str(anio).lower() not in ['todos', 'todas', 'all', '']:
            try:
                target_year = int(anio)
            except:
                target_year = None

        def parse_dt(f_str):
            if not f_str or f_str == '-':
                return None
            f_clean = str(f_str).strip()
            try:
                if '-' in f_clean:
                    parts = f_clean.split('-')
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                        elif len(parts[2]) == 4:
                            return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                elif '/' in f_clean:
                    parts = f_clean.split('/')
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                        elif len(parts[2]) == 4:
                            return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                pass
            return None

        # Filter dataset by year if specified
        ingresos = []
        for r in ingresos_raw:
            dt = parse_dt(self._get_row_prop(r, ['Fecha emisión', 'Fecha emisió­n', 'Fecha cobro', 'Fecha']))
            if target_year and dt and dt.year != target_year:
                continue
            r['_dt'] = dt
            ingresos.append(r)

        egresos = []
        for r in egresos_raw:
            dt = parse_dt(self._get_row_prop(r, ['Fecha comprobante', 'Fecha pago', 'Fecha']))
            if target_year and dt and dt.year != target_year:
                continue
            r['_dt'] = dt
            egresos.append(r)

        viajes = []
        for r in viajes_raw:
            dt = parse_dt(self._get_row_prop(r, ['Fecha salida', 'Fecha']))
            if target_year and dt and dt.year != target_year:
                continue
            r['_dt'] = dt
            viajes.append(r)

        remu = []
        for r in remu_raw:
            dt = parse_dt(self._get_row_prop(r, ['Fecha', 'Fecha emisión']))
            if target_year and dt and dt.year != target_year:
                continue
            r['_dt'] = dt
            remu.append(r)

        facturas_reales = [r for r in ingresos if not self._is_adelanto_entry(r)]

        facturado_neto = sum(self._to_float(r.get('Neto', 0)) for r in facturas_reales)
        iva_facturado = 0.0
        for r in facturas_reales:
            v_iva = self._to_float(r.get('IVA', 0))
            if v_iva > 0:
                iva_facturado += v_iva
            elif r.get('Total') and r.get('Neto'):
                tot = self._to_float(r.get('Total', 0))
                net = self._to_float(r.get('Neto', 0))
                if tot > net:
                    iva_facturado += (tot - net)
        facturado_bruto = facturado_neto + iva_facturado

        cobrado = sum(self._to_float(r.get('Importe cobrado', 0)) for r in ingresos)
        egresos_pagados = sum(max(0.0, self._to_float(r.get('Importe pagado', 0))) for r in egresos)
        remuneracion_generada = sum(self._to_float(r.get('Importe remuneración', 0)) for r in remu)
        
        saldo_por_cobrar = sum(
            self._to_float(r.get('Total', 0)) - self._to_float(r.get('Importe cobrado', 0)) 
            for r in ingresos if str(r.get('Estado cobro', '')).lower() != 'cobrado'
        )
        if saldo_por_cobrar < 0:
            saldo_por_cobrar = 0.0

        resultado_caja = cobrado - egresos_pagados

        months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        monthly_data = {m: {"facturado": 0.0, "facturado_neto": 0.0, "iva": 0.0, "cobrado": 0.0, "egresos": 0.0, "caja": 0.0, "viajes": 0} for m in months}

        for r in ingresos:
            dt = r.get('_dt')
            is_ad = self._is_adelanto_entry(r)
            neto = self._to_float(r.get('Neto', 0)) if not is_ad else 0.0
            iva = self._to_float(r.get('IVA', 0)) if not is_ad else 0.0
            if not is_ad and iva <= 0 and r.get('Total'):
                iva = self._to_float(r.get('Total', 0)) - neto
            if iva < 0: iva = 0.0
            cob = self._to_float(r.get('Importe cobrado', 0))

            if dt and 1 <= dt.month <= 12:
                m_name = months[dt.month - 1]
                monthly_data[m_name]["facturado"] += neto
                monthly_data[m_name]["facturado_neto"] += neto
                monthly_data[m_name]["iva"] += iva
                monthly_data[m_name]["cobrado"] += cob

        for r in egresos:
            dt = r.get('_dt')
            pagado = max(0.0, self._to_float(r.get('Importe pagado', 0)))
            if dt and 1 <= dt.month <= 12:
                m_name = months[dt.month - 1]
                monthly_data[m_name]["egresos"] += pagado

        for r in viajes:
            dt = r.get('_dt')
            if dt and 1 <= dt.month <= 12:
                m_name = months[dt.month - 1]
                monthly_data[m_name]["viajes"] += 1

        for m in months:
            monthly_data[m]["caja"] = monthly_data[m]["cobrado"] - monthly_data[m]["egresos"]

        egresos_cat = {}
        for r in egresos:
            cat = str(r.get('Categoría', 'Otros')).strip() or 'Otros'
            tot = max(0.0, self._to_float(r.get('Total', 0)))
            egresos_cat[cat] = egresos_cat.get(cat, 0.0) + tot

        def parse_money_val(val):
            if not val:
                return 0.0
            v_str = str(val).strip()
            v_clean = re.sub(r'[^\d.,]', '', v_str)
            if not v_clean:
                return 0.0
            if '.' in v_clean and ',' in v_clean:
                if v_clean.find('.') < v_clean.find(','):
                    v_clean = v_clean.replace('.', '').replace(',', '.')
                else:
                    v_clean = v_clean.replace(',', '')
            elif ',' in v_clean:
                parts = v_clean.split(',')
                if len(parts) == 2 and len(parts[1]) == 2:
                    v_clean = v_clean.replace(',', '.')
                else:
                    v_clean = v_clean.replace(',', '')
            try:
                return float(v_clean)
            except:
                return 0.0

        # Breakdown by payment method for COBRADO items
        medios_pago = {
            "Transferencia": 0.0,
            "E-Cheq": 0.0,
            "Cheque Físico": 0.0,
            "Efectivo": 0.0,
            "Tarjeta / Otros": 0.0
        }
        for r in ingresos:
            st = str(r.get('Estado cobro', '')).strip().upper()
            if st == 'COBRADO':
                medio_str = str(self._get_row_prop(r, ['Medios de pago aplicados', 'Medio cobro', 'Medio de pago', 'Forma de pago']) or '')
                if '|' in medio_str:
                    for part in medio_str.split('|'):
                        if ':' in part:
                            k, v = part.split(':', 1)
                            k_clean = k.strip().lower()
                            v_num = parse_money_val(v)
                            if 'transf' in k_clean: medios_pago["Transferencia"] += v_num
                            elif 'e-cheq' in k_clean or 'echeq' in k_clean: medios_pago["E-Cheq"] += v_num
                            elif 'cheque' in k_clean: medios_pago["Cheque Físico"] += v_num
                            elif 'efectivo' in k_clean: medios_pago["Efectivo"] += v_num
                            else: medios_pago["Tarjeta / Otros"] += v_num
                elif medio_str:
                    m_clean = medio_str.lower()
                    amt = self._to_float(r.get('Importe cobrado', 0))
                    if 'transf' in m_clean: medios_pago["Transferencia"] += amt
                    elif 'e-cheq' in m_clean or 'echeq' in m_clean: medios_pago["E-Cheq"] += amt
                    elif 'cheque' in m_clean: medios_pago["Cheque Físico"] += amt
                    elif 'efectivo' in m_clean: medios_pago["Efectivo"] += amt
                    else: medios_pago["Tarjeta / Otros"] += amt

        # Clean empty payment keys
        medios_pago = {k: round(v, 2) for k, v in medios_pago.items() if v > 0}
        if not medios_pago:
            medios_pago = {"Transferencia": round(cobrado, 2)}

        # Breakdown by Activity / Service Type
        actividades = {
            "Transporte & Viajes": 0,
            "Servicios de Maquinaria": 0
        }
        for r in viajes:
            act_str = (str(r.get('Actividad', '')) + " " + str(r.get('ID viaje', ''))).lower()
            if 'srv' in act_str or 'servicio' in act_str or 'maquinaria' in act_str or 'grúa' in act_str or 'excav' in act_str:
                actividades["Servicios de Maquinaria"] += 1
            else:
                actividades["Transporte & Viajes"] += 1

        # 1. Top Clientes por Facturación ($)
        client_totals = {}
        for r in facturas_reales:
            cli = str(self._get_row_prop(r, ['Razón social / Nombre', 'Cliente', 'Nombre']) or '').strip()
            neto = self._to_float(r.get('Neto', 0)) or self._to_float(r.get('Total', 0))
            if cli and neto > 0:
                client_totals[cli] = client_totals.get(cli, 0.0) + neto
        sorted_clients = sorted(client_totals.items(), key=lambda x: x[1], reverse=True)[:6]
        top_clientes = {k: round(v, 2) for k, v in sorted_clients}

        # 2. Consumo de Combustible por Unidad (Litros)
        unit_liters = {}
        for r in egresos:
            u = str(self._get_row_prop(r, ['Unidad', 'Dominio/Patente']) or '').strip()
            lit = self._to_float(r.get('Cantidad/Litros', 0))
            if u and u != '-' and lit > 0:
                unit_liters[u] = unit_liters.get(u, 0.0) + lit
        sorted_units = sorted(unit_liters.items(), key=lambda x: x[1], reverse=True)[:8]
        consumo_unidades = {k: round(v, 1) for k, v in sorted_units}

        # 3. Estado y Distribución de Cartera de Cheques ($)
        _, cheques_raw = self._read_sheet_rows(wb['CHEQUES']) if 'CHEQUES' in wb.sheetnames else ([], [])
        chq_status = {
            "Disponibles": 0.0,
            "Entregados / Endosados": 0.0,
            "En Re-presentación / Rechazados": 0.0,
            "Cobrados / Regularizados": 0.0
        }
        for r in cheques_raw:
            dt = parse_dt(self._get_row_prop(r, ['Fecha ingreso', 'Fecha cobro', 'Fecha']))
            if target_year and dt and dt.year != target_year:
                continue
            st = str(r.get('Estado', 'Disponible')).strip().lower()
            monto = self._to_float(r.get('Monto', 0))
            if 'disponible' in st:
                chq_status["Disponibles"] += monto
            elif 'entregado' in st or 'usado' in st:
                chq_status["Entregados / Endosados"] += monto
            elif 'rechazad' in st or 're-presentaci' in st or 'incobrable' in st:
                chq_status["En Re-presentación / Rechazados"] += monto
            elif 'cobrado' in st or 'regularizado' in st:
                chq_status["Cobrados / Regularizados"] += monto
        estado_cheques = {k: round(v, 2) for k, v in chq_status.items() if v > 0}

        total_gastos_comprados = sum(self._to_float(r.get('Total', 0)) for r in egresos)
        saldo_favor_compensado = max(0.0, total_gastos_comprados - egresos_pagados)

        return {
            "kpis": {
                "facturado_neto": round(facturado_neto, 2),
                "iva_facturado": round(iva_facturado, 2),
                "facturado_bruto": round(facturado_bruto, 2),
                "cobrado": round(cobrado, 2),
                "egresos_pagados": round(egresos_pagados, 2),
                "total_gastos_comprados": round(total_gastos_comprados, 2),
                "saldo_favor_compensado": round(saldo_favor_compensado, 2),
                "resultado_caja": round(resultado_caja, 2),
                "saldo_por_cobrar": round(saldo_por_cobrar, 2),
                "remuneracion_generada": round(remuneracion_generada, 2),
                "facturas_count": len(facturas_reales),
                "total_facturas": len(facturas_reales),
                "total_viajes": len(viajes)
            },
            "monthly": monthly_data,
            "egresos_por_categoria": egresos_cat,
            "medios_pago": medios_pago,
            "actividades": actividades,
            "top_clientes": top_clientes,
            "consumo_unidades": consumo_unidades,
            "estado_cheques": estado_cheques
        }

    def get_sheet_data(self, sheet_name):
        if self.supabase_service and self.supabase_service.is_connected():
            headers, rows = self.supabase_service.get_sheet_data(sheet_name)
            if headers or rows:
                return headers, rows
        wb = self.load_wb(data_only=True)
        if sheet_name not in wb.sheetnames:
            return [], []
        return self._read_sheet_rows(wb[sheet_name])

    def _format_unidad_label(self, pat, marca, modelo, anio):
        import re
        pat = str(pat or '').strip()
        marca = str(marca or '').strip()
        modelo = str(modelo or '').strip()
        anio = str(anio or '').strip()
        
        parts = []
        if marca:
            parts.append(marca)
        if modelo:
            if re.match(r'^\d{4}$', modelo):
                if not anio:
                    anio = modelo
                elif anio != modelo:
                    parts.append(modelo)
            else:
                if modelo.lower() != marca.lower():
                    parts.append(modelo)
        if anio:
            parts.append(f"({anio})")
            
        extra = " ".join(parts).strip()
        return f"{pat} - {extra}" if extra else pat

    def get_master_lists(self):
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    # Todos los empleados activos
                    emp = [r[0] for r in conn.execute(text("""
                        SELECT apellido_nombre FROM empleados 
                        WHERE estado IS NULL 
                           OR (LOWER(TRIM(estado)) NOT LIKE '%baja%' 
                               AND LOWER(TRIM(estado)) NOT LIKE '%inactivo%' 
                               AND LOWER(TRIM(estado)) NOT LIKE '%desvinculado%' 
                               AND LOWER(TRIM(estado)) NOT LIKE '%eliminado%')
                        ORDER BY apellido_nombre
                    """)).fetchall() if r[0]]
                    
                    # Unidades con marca, modelo y año
                    uni_records = conn.execute(text("SELECT dominio_patente, marca, modelo, anio FROM unidades WHERE estado IS NULL OR LOWER(TRIM(estado)) IN ('activo', '') ORDER BY dominio_patente")).fetchall()
                    uni = []
                    unidades_dict = {}
                    for r in uni_records:
                        pat = r[0]
                        if pat:
                            pat = str(pat).strip()
                            marca = str(r[1] or '').strip()
                            modelo = str(r[2] or '').strip()
                            anio = str(r[3] or '').strip()
                            label = self._format_unidad_label(pat, marca, modelo, anio)
                            item_obj = {
                                "value": pat,
                                "label": label,
                                "patente": pat,
                                "marca": marca,
                                "modelo": modelo,
                                "anio": anio
                            }
                            uni.append(item_obj)
                            unidades_dict[pat] = item_obj

                    cli = [r[0] for r in conn.execute(text("SELECT razon_social FROM clientes WHERE estado IS NULL OR LOWER(TRIM(estado)) IN ('activo', '') ORDER BY razon_social")).fetchall() if r[0]]
                    prov = [r[0] for r in conn.execute(text("SELECT razon_social FROM proveedores WHERE estado IS NULL OR LOWER(TRIM(estado)) IN ('activo', '') ORDER BY razon_social")).fetchall() if r[0]]
                    act = [r[0] for r in conn.execute(text("SELECT actividad FROM actividades ORDER BY actividad")).fetchall() if r[0]]
                    
                    # Categorías estrictamente reales de la base de datos (Egresos + Órdenes de Compra + Creadas en BD)
                    try:
                        cat_records = conn.execute(text("""
                            SELECT DISTINCT TRIM(valor) FROM configuracion 
                            WHERE categoria IN ('categoria_egreso', 'categoria_egreso_custom') 
                              AND (activo IS NULL OR activo = TRUE) 
                              AND valor IS NOT NULL AND TRIM(valor) != ''
                            UNION
                            SELECT DISTINCT TRIM(categoria) FROM egresos 
                            WHERE categoria IS NOT NULL AND TRIM(categoria) != ''
                            UNION
                            SELECT DISTINCT TRIM(tipo_insumo) FROM ordenes_compra 
                            WHERE tipo_insumo IS NOT NULL AND TRIM(tipo_insumo) != ''
                        """)).fetchall()
                        categorias = sorted(list(dict.fromkeys([r[0].strip() for r in cat_records if r[0] and str(r[0]).strip()])))
                    except Exception as cat_err:
                        print(f"[get_master_lists cat fetch warning] {cat_err}")
                        categorias = []

                    # Cuentas de Tesorería
                    cuentas_list = []
                    cuentas_dict = {}
                    try:
                        c_recs = conn.execute(text("""
                            SELECT id_cuenta, nombre_cuenta, tipo, saldo_real_cotejado 
                            FROM tesoreria_cuentas 
                            ORDER BY nombre_cuenta
                        """)).fetchall()
                        for cr in c_recs:
                            c_id, c_nom, c_tipo, c_saldo = cr[0], cr[1], cr[2], cr[3]
                            if c_nom:
                                c_nom = str(c_nom).strip()
                                cuentas_list.append({
                                    'id': c_id,
                                    'nombre': c_nom,
                                    'tipo': str(c_tipo or 'Banco').strip(),
                                    'saldo': float(c_saldo or 0.0)
                                })
                                cuentas_dict[c_nom] = {
                                    'id': c_id,
                                    'tipo': str(c_tipo or 'Banco').strip(),
                                    'saldo': float(c_saldo or 0.0)
                                }
                    except Exception as tc_err:
                        print(f"[get_master_lists tesoreria fetch warning] {tc_err}")

                    # Años para filtros
                    current_year = datetime.now().year
                    years_set = {current_year, 2026}
                    try:
                        y_recs = conn.execute(text("""
                            SELECT DISTINCT EXTRACT(YEAR FROM fecha_salida)::int FROM viajes WHERE fecha_salida IS NOT NULL
                            UNION
                            SELECT DISTINCT EXTRACT(YEAR FROM fecha_emision)::int FROM ingresos WHERE fecha_emision IS NOT NULL
                            UNION
                            SELECT DISTINCT EXTRACT(YEAR FROM fecha_comprobante)::int FROM egresos WHERE fecha_comprobante IS NOT NULL
                            UNION
                            SELECT DISTINCT EXTRACT(YEAR FROM fecha)::int FROM presupuestos WHERE fecha IS NOT NULL
                        """)).fetchall()
                        for yr in y_recs:
                            if yr[0] and 2000 <= int(yr[0]) <= 2100:
                                years_set.add(int(yr[0]))
                    except Exception:
                        pass
                    anios = sorted(list(years_set), reverse=True)

                    clientes_dict = {}
                    cli_records = conn.execute(text("SELECT razon_social, cuit_cuil, correo, id_cliente FROM clientes WHERE estado IS NULL OR LOWER(TRIM(estado)) IN ('activo', '')")).fetchall()
                    for c_r in cli_records:
                        if c_r[0]:
                            clientes_dict[c_r[0]] = {
                                'cuit': c_r[1] or '',
                                'email': c_r[2] or '',
                                'id': c_r[3] or ''
                            }

                    proveedores_dict = {}
                    prov_records = conn.execute(text("SELECT razon_social, cuit, id_proveedor, nombre_comercial FROM proveedores WHERE estado IS NULL OR LOWER(TRIM(estado)) != 'eliminado'")).fetchall()
                    for p_r in prov_records:
                        if p_r[0]:
                            proveedores_dict[p_r[0]] = {
                                'cuit': p_r[1] or '',
                                'id': p_r[2] or '',
                                'nombre_comercial': p_r[3] or ''
                            }

                    return {
                        "empleados": emp,
                        "unidades": uni,
                        "unidades_dict": unidades_dict,
                        "clientes": cli,
                        "clientes_dict": clientes_dict,
                        "proveedores": prov,
                        "proveedores_dict": proveedores_dict,
                        "actividades": act or ['Servicio de Flete', 'Transporte de Granos', 'Cargas Generales', 'Movimiento de Suelo'],
                        "categorias": categorias,
                        "cuentas_tesoreria": cuentas_list,
                        "cuentas_tesoreria_dict": cuentas_dict,
                        "anios": anios
                    }
            except Exception as e:
                print(f"[get_master_lists Supabase Error] {e}")

        # Fallback a Excel
        wb = self.load_wb(data_only=True)
        def get_col_values(sheet_name, col_name, start_row=5):
            if sheet_name not in wb.sheetnames:
                return []
            ws = wb[sheet_name]
            _, data = self._read_sheet_rows(ws, start_row=start_row)
            vals = []
            for r in data:
                v = str(r.get(col_name, '')).strip()
                if v and v not in vals:
                    vals.append(v)
            return vals

        emp = []
        if 'EMPLEADOS' in wb.sheetnames:
            ws_emp = wb['EMPLEADOS']
            _, emp_rows = self._read_sheet_rows(ws_emp, start_row=5)
            for r in emp_rows:
                nom = str(r.get('Apellido y nombre') or r.get('Empleado') or r.get('Nombre') or '').strip()
                est = str(r.get('Estado') or '').strip().lower()
                if nom and (not est or 'activo' in est or est not in ['baja', 'inactivo', 'desvinculado', 'eliminado', '0']):
                    if nom not in emp:
                        emp.append(nom)
        if not emp:
            emp = get_col_values('EMPLEADOS', 'Apellido y nombre') or get_col_values('EMPLEADOS', 'ID empleado')
        
        uni = []
        unidades_dict = {}
        if 'UNIDADES' in wb.sheetnames:
            ws = wb['UNIDADES']
            _, uni_rows = self._read_sheet_rows(ws, start_row=5)
            for r in uni_rows:
                pat = str(r.get('Dominio/Patente') or r.get('ID unidad') or '').strip()
                estado = str(r.get('Estado') or '').strip().lower()
                if pat and (not estado or estado in ['activo', '']):
                    marca = str(r.get('Marca') or '').strip()
                    modelo = str(r.get('Modelo') or '').strip()
                    anio = str(r.get('Año') or r.get('Ao') or r.get('Anio') or '').strip()
                    label = self._format_unidad_label(pat, marca, modelo, anio)
                    item_obj = {
                        "value": pat,
                        "label": label,
                        "patente": pat,
                        "marca": marca,
                        "modelo": modelo,
                        "anio": anio
                    }
                    if not any(x['value'] == pat for x in uni):
                        uni.append(item_obj)
                        unidades_dict[pat] = item_obj

        cli = get_col_values('CLIENTES', 'Razón social / Nombre') or get_col_values('CLIENTES', 'ID cliente')
        prov = get_col_values('PROVEEDORES', 'Razón social') or get_col_values('PROVEEDORES', 'Nombre comercial')
        act = get_col_values('ACTIVIDADES', 'Actividad')

        # Excel categorias exclusivamente de datos reales
        excel_cats = []
        if 'CONFIGURACION' in wb.sheetnames:
            ws_cfg = wb['CONFIGURACION']
            cat_col = 6
            for c in range(1, ws_cfg.max_column + 1):
                h = str(ws_cfg.cell(4, c).value or '').strip().lower()
                if 'categor' in h and 'egreso' in h:
                    cat_col = c
                    break
            for r in range(5, ws_cfg.max_row + 1):
                val = str(ws_cfg.cell(r, cat_col).value or '').strip()
                if val:
                    excel_cats.append(val)
        if 'EGRESOS' in wb.sheetnames:
            excel_cats += get_col_values('EGRESOS', 'Categoría')
        if 'ORDENES_COMPRA' in wb.sheetnames:
            excel_cats += get_col_values('ORDENES_COMPRA', 'Tipo de insumo')
        categorias_excel = sorted(list(dict.fromkeys([str(c).strip() for c in excel_cats if c and str(c).strip()])))

        # Excel cuentas tesoreria
        cuentas_list_excel = []
        cuentas_dict_excel = {}
        if 'TESORERIA' in wb.sheetnames:
            ws_tes = wb['TESORERIA']
            _, tes_rows = self._read_sheet_rows(ws_tes, start_row=5)
            for tr in tes_rows:
                c_nom = str(tr.get('Nombre cuenta') or tr.get('Cuenta') or '').strip()
                if c_nom:
                    c_id = str(tr.get('ID cuenta') or '').strip()
                    c_tipo = str(tr.get('Tipo') or 'Banco').strip()
                    c_saldo = float(tr.get('Saldo actual') or tr.get('Saldo') or 0.0)
                    cuentas_list_excel.append({'id': c_id, 'nombre': c_nom, 'tipo': c_tipo, 'saldo': c_saldo})
                    cuentas_dict_excel[c_nom] = {'id': c_id, 'tipo': c_tipo, 'saldo': c_saldo}

        clientes_dict = {}
        if 'CLIENTES' in wb.sheetnames:
            _, cli_rows = self.get_sheet_data('CLIENTES')
            for r in cli_rows:
                cname = ""
                cuit = ""
                email = ""
                cid = str(r.get('ID cliente') or r.get('ID') or '').strip()
                for k, v in r.items():
                    k_clean = str(k).lower().replace(' ', '').replace('ó', 'o').replace('á', 'a')
                    v_clean = str(v).strip()
                    if ('razon' in k_clean or 'nombre' in k_clean) and not k_clean.startswith('_'):
                        if not cname: cname = v_clean
                    elif 'cuit' in k_clean or 'cuil' in k_clean:
                        if not cuit: cuit = v_clean
                    elif 'correo' in k_clean or 'email' in k_clean:
                        if not email: email = v_clean
                
                if cname:
                    clientes_dict[cname] = {
                        'cuit': cuit,
                        'email': email,
                        'id': cid
                    }

        return {
            "empleados": emp,
            "unidades": uni,
            "unidades_dict": unidades_dict,
            "clientes": cli,
            "clientes_dict": clientes_dict,
            "proveedores": prov,
            "actividades": act or ['Servicio de Flete', 'Transporte de Granos', 'Cargas Generales', 'Movimiento de Suelo'],
            "categorias": categorias_excel,
            "cuentas_tesoreria": cuentas_list_excel,
            "cuentas_tesoreria_dict": cuentas_dict_excel,
            "anios": [datetime.now().year + 1, datetime.now().year, 2026]
        }

    def add_categoria(self, cat_name):
        cat_clean = str(cat_name or '').strip()
        if not cat_clean:
            return {"status": "error", "message": "Nombre de categoría requerido."}
        
        # 1. Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    existing = conn.execute(text("""
                        SELECT valor FROM configuracion 
                        WHERE categoria IN ('categoria_egreso', 'categoria_egreso_custom') AND LOWER(TRIM(valor)) = LOWER(:cat)
                    """), {'cat': cat_clean}).fetchone()
                    if not existing:
                        max_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM configuracion")).scalar() or 0
                        conn.execute(text("""
                            INSERT INTO configuracion (id, categoria, clave, valor, orden, activo, created_at)
                            VALUES (:id, 'categoria_egreso', :cat, :cat, 99, True, NOW())
                        """), {'id': max_id + 1, 'cat': cat_clean})
            except Exception as e:
                print(f"[add_categoria Supabase Error] {e}")

        # 2. Excel
        try:
            wb = self.load_wb(data_only=False)
            if 'CONFIGURACION' in wb.sheetnames:
                ws = wb['CONFIGURACION']
                cat_col = 6
                for c in range(1, ws.max_column + 1):
                    h = str(ws.cell(4, c).value or '').strip().lower()
                    if 'categor' in h and 'egreso' in h:
                        cat_col = c
                        break
                found = False
                for r in range(5, ws.max_row + 1):
                    if str(ws.cell(r, cat_col).value or '').strip().lower() == cat_clean.lower():
                        found = True
                        break
                if not found:
                    empty_r = None
                    for r in range(5, ws.max_row + 2):
                        if not ws.cell(r, cat_col).value:
                            empty_r = r
                            break
                    if not empty_r:
                        empty_r = ws.max_row + 1
                    ws.cell(empty_r, cat_col, cat_clean)
                    wb.save(self.excel_path)
        except Exception as e:
            print(f"[add_categoria Excel warning] {e}")

        self._invalidate_cache()
        return {"status": "success", "categoria": cat_clean}

    def _ensure_liquidaciones_sheet(self, wb):
        if 'LIQUIDACIONES' not in wb.sheetnames:
            ws = wb.create_sheet('LIQUIDACIONES')
            ws.cell(1, 1, 'ECONCATIVO - HISTORIAL DE LIQUIDACIONES DE SUELDOS')
            ws.cell(2, 1, 'Generado automáticamente por Antigravity Control System')
            headers = [
                'ID liquidación',
                'Fecha confirmación',
                'Período quincena',
                'ID empleado',
                'Empleado',
                'Puesto',
                'DNI',
                'CUIL',
                'Entidad bancaria',
                'CBU',
                'Alias CBU',
                'Sueldo fijo base',
                'Comisión pct',
                'Cant viajes',
                'Total comisiones',
                'Sueldo final',
                'Estado',
                'Desglose JSON'
            ]
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        return wb['LIQUIDACIONES']

    def _calcular_fecha_siguiente_quincena(self, periodo_str, fecha_ref=None):
        """Calculates the start date of the subsequent quincena period."""
        from datetime import datetime
        ref_dt = datetime.now()
        if fecha_ref:
            try:
                if isinstance(fecha_ref, str):
                    parts = fecha_ref.split('-')
                    if len(parts) >= 3:
                        ref_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                pass

        p_lower = str(periodo_str or '').lower()
        y = ref_dt.year
        m = ref_dt.month

        import re
        m_match = re.search(r'(\d{4})', p_lower)
        if m_match:
            try:
                y = int(m_match.group(1))
            except:
                pass

        is_q1 = any(x in p_lower for x in ['1ª', '1a', '1era', '1ra', '1º', 'q1', 'quincena 1', 'primera', '1 al 15', 'días 1 al 15', 'dias 1 al 15']) or ('1' in p_lower and 'quincena' in p_lower and '2' not in p_lower)
        if is_q1:
            return f"{y}-{m:02d}-16"
        else:
            next_m = m + 1
            next_y = y
            if next_m > 12:
                next_m = 1
                next_y += 1
            return f"{next_y}-{next_m:02d}-01"

    def confirmar_liquidacion(self, payload):
        """Confirms and archives individual or bulk salary settlement run for an employee/quincena period,
        supporting multiple split payment methods and checks, preventing duplicate confirmations,
        and automatically registering surplus amounts as advances for the next quincena."""
        quincena = payload.get('quincena', 'q1')
        items = payload.get('items', [])
        
        # Support single employee payload
        if not items:
            if payload.get('item'):
                single_item = dict(payload['item'])
                if payload.get('pagos'):
                    single_item['pagos'] = payload['pagos']
                items = [single_item]
            elif payload.get('id_empleado'):
                single_item = dict(payload)
                items = [single_item]
            else:
                items = self.get_liquidaciones_personal(quincena=quincena)
        
        if not items:
            return {"status": "error", "message": "No hay datos de liquidación para confirmar."}

        today_date = datetime.now().strftime('%Y-%m-%d')
        from sqlalchemy import text

        # 0. Strict duplicate check: verify none of the employees have already been liquidated for this period
        for item in items:
            eid = str(item.get('id_empleado', '')).strip()
            periodo = str(item.get('periodo_label', quincena)).strip()
            nombre = item.get('nombre') or item.get('nombre_empleado') or 'Empleado'
            
            # Check Supabase
            if self.supabase_service and self.supabase_service.is_connected():
                try:
                    with self.supabase_service.engine.connect() as conn:
                        existing = conn.execute(text("""
                            SELECT id_liquidacion, periodo_quincena, fecha_confirmacion 
                            FROM liquidaciones 
                            WHERE LOWER(TRIM(id_empleado)) = LOWER(TRIM(:eid))
                              AND LOWER(TRIM(periodo_quincena)) = LOWER(TRIM(:periodo))
                            LIMIT 1
                        """), {'eid': eid, 'periodo': periodo}).first()
                        if existing:
                            return {
                                "status": "error",
                                "message": f"El sueldo del empleado {nombre} ({eid}) ya fue liquidado para la quincena/período '{periodo}'. (Liquidación registrada: {existing[0]}). No se puede liquidar nuevamente."
                            }
                except Exception as e:
                    print(f"[confirmar_liquidacion duplicate check Supabase] {e}")

            # Check Excel mirror
            try:
                wb_chk = self.load_wb(data_only=True)
                if 'LIQUIDACIONES' in wb_chk.sheetnames:
                    ws_chk = wb_chk['LIQUIDACIONES']
                    for r in range(5, ws_chk.max_row + 1):
                        lid_c = str(ws_chk.cell(r, 1).value or '').strip()
                        per_c = str(ws_chk.cell(r, 3).value or '').strip().lower()
                        eid_c = str(ws_chk.cell(r, 4).value or '').strip().lower()
                        if eid_c == eid.lower() and per_c == periodo.lower():
                            return {
                                "status": "error",
                                "message": f"El sueldo del empleado {nombre} ({eid}) ya fue liquidado para la quincena/período '{periodo}'. (Liquidación registrada: {lid_c}). No se puede liquidar nuevamente."
                            }
            except Exception as e:
                pass

        saved_count = 0
        total_sum = 0.0
        adelantos_generados = []

        # 1. Supabase Master Execution
        if self.supabase_service and self.supabase_service.is_connected():
            try:
                base_liq_id = self.supabase_service.get_next_id('liquidaciones', 'LIQ', 'id_liquidacion')
                next_liq_num = int(base_liq_id.split('-')[-1])

                base_egr_id = self.supabase_service.get_next_id('egresos', 'EGR', 'id_egreso')
                next_egr_num = int(base_egr_id.split('-')[-1])

                with self.supabase_service.engine.begin() as conn:
                    for item in items:
                        eid = str(item.get('id_empleado', '')).strip()
                        periodo = str(item.get('periodo_label', quincena)).strip()
                        nombre = item.get('nombre') or item.get('nombre_empleado') or 'Empleado'
                        cuil = item.get('cuil', '') or item.get('dni', '')
                        cbu_alias = item.get('alias_cbu') or item.get('cbu') or ''
                        s_base = float(item.get('sueldo_fijo_base', 0))
                        s_com = float(item.get('total_comisiones', 0))
                        s_final = float(item.get('sueldo_final', 0))
                        total_sum += s_final

                        # Resolve payment methods list
                        pagos_list = item.get('pagos') or []
                        if not pagos_list:
                            chq_id_legacy = item.get('cheque_id')
                            cuenta_legacy = str(item.get('cuenta_tesoreria') or item.get('medio_pago') or 'Transferencia Bancaria').strip()
                            if not chq_id_legacy and cuenta_legacy.startswith('Cheque:'):
                                chq_id_legacy = cuenta_legacy.replace('Cheque:', '').strip()
                            pagos_list = [{
                                'metodo': 'Cheque de Terceros' if chq_id_legacy else 'Transferencia Bancaria',
                                'cuenta_tesoreria': cuenta_legacy,
                                'cheque_id': chq_id_legacy,
                                'monto': s_final
                            }]

                        total_pagado = sum(float(p.get('monto', 0)) for p in pagos_list)
                        excedente = max(0.0, round(total_pagado - s_final, 2))

                        desglose_obj = {
                            "viajes": item.get('desglose_viajes', []),
                            "pagos": pagos_list,
                            "total_pagado": total_pagado,
                            "excedente": excedente
                        }
                        desglose_json = json.dumps(desglose_obj, ensure_ascii=False)

                        active_liq_id = f"LIQ-{next_liq_num:06d}"
                        next_liq_num += 1
                        saved_count += 1

                        # Insert Liquidacion
                        conn.execute(text("""
                            INSERT INTO liquidaciones (
                                id_liquidacion, fecha_confirmacion, periodo_quincena, id_empleado, empleado,
                                puesto, dni, cuil, entidad_bancaria, cbu, alias_cbu,
                                sueldo_fijo_base, comision_pct, cant_viajes, total_comisiones, sueldo_final,
                                estado, desglose_json, created_at
                            ) VALUES (
                                :id_liquidacion, CAST(:fecha AS date), :periodo, :eid, :nombre,
                                :puesto, :dni, :cuil, :banco, :cbu, :alias_cbu,
                                :s_base, :comision_pct, :cant_viajes, :s_com, :s_final,
                                'CONFIRMADO', :desglose_json, NOW()
                            );
                        """), {
                            'id_liquidacion': active_liq_id,
                            'fecha': today_date,
                            'periodo': periodo,
                            'eid': eid,
                            'nombre': nombre,
                            'puesto': item.get('puesto', ''),
                            'dni': item.get('dni', ''),
                            'cuil': cuil,
                            'banco': item.get('banco', ''),
                            'cbu': item.get('cbu', ''),
                            'alias_cbu': item.get('alias_cbu', ''),
                            's_base': s_base,
                            'comision_pct': float(item.get('comision_pct', 0)),
                            'cant_viajes': int(item.get('cant_viajes', 0)),
                            's_com': s_com,
                            's_final': s_final,
                            'desglose_json': desglose_json
                        })

                        # Synchronize each payment line with EGRESOS and CHEQUES
                        for p_idx, p in enumerate(pagos_list):
                            p_monto = float(p.get('monto', 0))
                            if p_monto <= 0:
                                continue

                            p_chq = p.get('cheque_id')
                            p_cuenta = str(p.get('cuenta_tesoreria') or p.get('metodo') or 'Transferencia Bancaria').strip()

                            egr_id = f"EGR-{next_egr_num:06d}"
                            next_egr_num += 1

                            if p_chq:
                                chq_row = conn.execute(text("SELECT nro_cheque, banco, tipo FROM cheques WHERE id_cheque = :cid"), {'cid': p_chq}).first()
                                if chq_row:
                                    nro_chq = str(chq_row[0] or '')
                                    banco_chq = str(chq_row[1] or 'Banco')
                                    tipo_chq = str(chq_row[2] or '').lower()
                                    if 'propio' in tipo_chq or str(p_chq).startswith('CHQP-'):
                                        p_cuenta = f"Cheque Propio - {banco_chq} N° {nro_chq}"
                                    else:
                                        p_cuenta = f"Cheque N° {nro_chq} ({banco_chq})"

                                conn.execute(text("""
                                    UPDATE cheques SET
                                        estado = 'Usado',
                                        endosado_tenedor = :nombre,
                                        destino_usado_en = :nombre,
                                        fecha_uso = CAST(:fecha AS date),
                                        id_egreso = :egr_id,
                                        observaciones = CONCAT(COALESCE(observaciones, ''), ' | Liquidación ', :lid),
                                        updated_at = NOW()
                                    WHERE id_cheque = :cid;
                                """), {
                                    'nombre': nombre,
                                    'fecha': today_date,
                                    'egr_id': egr_id,
                                    'lid': active_liq_id,
                                    'cid': p_chq
                                })

                            obs_tag = f"[LIQUIDACIÓN: {eid}:{periodo}] {periodo} - {p_cuenta}".strip()
                            desc_egreso = f"Liquidación {periodo} - Pago {p_idx + 1} ({p_cuenta})"

                            conn.execute(text("""
                                INSERT INTO egresos (
                                    id_egreso, fecha_comprobante, categoria, subcategoria, proveedor, cuit,
                                    tipo_comprobante, empleado, descripcion, neto, iva, total,
                                    estado_pago, importe_pagado, fecha_pago, medio_pago, saldo,
                                    id_liquidacion, observaciones, created_at, updated_at
                                ) VALUES (
                                    :id_egreso, CAST(:fecha AS date), 'Liquidación de Sueldos', 'Personal', :nombre, :cuil,
                                    'Liquidación Quincenal', :eid, :descripcion, :monto, 0, :monto,
                                    'Pagado', :monto, CAST(:fecha AS date), :cuenta_tes, 0,
                                    :id_liquidacion, :obs_tag, NOW(), NOW()
                                );
                            """), {
                                'id_egreso': egr_id,
                                'fecha': today_date,
                                'nombre': nombre,
                                'cuil': cuil,
                                'eid': eid,
                                'descripcion': desc_egreso,
                                'monto': p_monto,
                                'cuenta_tes': p_cuenta,
                                'id_liquidacion': active_liq_id,
                                'obs_tag': obs_tag
                            })

                        # Mark novelties as Liquidado in Supabase
                        nov_ids = [str(n['id']).strip() for n in item.get('novedades', []) if n.get('id')]
                        if nov_ids:
                            conn.execute(text("""
                                UPDATE novedades_personal SET
                                    id_liquidacion = :lid,
                                    estado = 'Liquidado'
                                WHERE id_novedad = ANY(:nov_ids);
                            """), {'lid': active_liq_id, 'nov_ids': nov_ids})

                        # Mark remuneraciones as Liquidado in Supabase
                        conn.execute(text("""
                            UPDATE remuneraciones SET
                                id_liquidacion = :lid,
                                estado = 'Liquidado',
                                fecha_pago = CAST(:fecha AS date)
                            WHERE LOWER(empleado) = LOWER(:nombre)
                              AND (estado IS NULL OR estado = '' OR estado = 'Pendiente');
                        """), {'lid': active_liq_id, 'fecha': today_date, 'nombre': nombre})

                        item['_active_liq_id'] = active_liq_id
                        item['_total_pagado'] = total_pagado
                        item['_excedente'] = excedente

            except Exception as e:
                print(f"[confirmar_liquidacion Supabase Error] {e}")

        # 2. Safe Excel mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_liquidaciones_sheet(wb)
            ws_e = wb['EGRESOS'] if 'EGRESOS' in wb.sheetnames else None
            ws_c = wb['CHEQUES'] if 'CHEQUES' in wb.sheetnames else None

            max_num = 0
            for r in range(5, ws.max_row + 1):
                lid = str(ws.cell(r, 1).value or '').strip()
                if lid.startswith('LIQ-'):
                    try:
                        num = int(lid.split('-')[-1])
                        if num > max_num: max_num = num
                    except: pass

            max_egr_num = 0
            if ws_e:
                for r in range(5, ws_e.max_row + 1):
                    egr_id = str(ws_e.cell(r, 1).value or '').strip()
                    if egr_id.startswith('EGR-'):
                        try:
                            num = int(egr_id.split('-')[-1])
                            if num > max_egr_num: max_egr_num = num
                        except: pass

            for item in items:
                eid = str(item.get('id_empleado', '')).strip()
                periodo = str(item.get('periodo_label', quincena)).strip()
                nombre = item.get('nombre') or item.get('nombre_empleado') or 'Empleado'
                cuil = item.get('cuil', '') or item.get('dni', '')
                cbu_alias = item.get('alias_cbu') or item.get('cbu') or ''
                s_base = float(item.get('sueldo_fijo_base', 0))
                s_com = float(item.get('total_comisiones', 0))
                s_final = float(item.get('sueldo_final', 0))

                active_liq_id = item.get('_active_liq_id')
                if not active_liq_id:
                    max_num += 1
                    active_liq_id = f"LIQ-{max_num:06d}"
                    item['_active_liq_id'] = active_liq_id

                pagos_list = item.get('pagos') or []
                if not pagos_list:
                    chq_id_legacy = item.get('cheque_id')
                    cuenta_legacy = str(item.get('cuenta_tesoreria') or item.get('medio_pago') or 'Transferencia Bancaria').strip()
                    if not chq_id_legacy and cuenta_legacy.startswith('Cheque:'):
                        chq_id_legacy = cuenta_legacy.replace('Cheque:', '').strip()
                    pagos_list = [{
                        'metodo': 'Cheque de Terceros' if chq_id_legacy else 'Transferencia Bancaria',
                        'cuenta_tesoreria': cuenta_legacy,
                        'cheque_id': chq_id_legacy,
                        'monto': s_final
                    }]

                total_pagado = item.get('_total_pagado', sum(float(p.get('monto', 0)) for p in pagos_list))
                excedente = item.get('_excedente', max(0.0, round(total_pagado - s_final, 2)))

                desglose_obj = {
                    "viajes": item.get('desglose_viajes', []),
                    "pagos": pagos_list,
                    "total_pagado": total_pagado,
                    "excedente": excedente
                }
                desglose_json = json.dumps(desglose_obj, ensure_ascii=False)

                row_vals = [
                    active_liq_id, today_date, periodo, eid, nombre,
                    item.get('puesto', ''), item.get('dni', ''), cuil,
                    item.get('banco', ''), item.get('cbu', ''), item.get('alias_cbu', ''),
                    s_base, item.get('comision_pct', 0), item.get('cant_viajes', 0),
                    s_com, s_final, 'CONFIRMADO', desglose_json
                ]
                ws.append(row_vals)

                # Process payments into EGRESOS and CHEQUES
                for p_idx, p in enumerate(pagos_list):
                    p_monto = float(p.get('monto', 0))
                    if p_monto <= 0:
                        continue

                    p_chq = p.get('cheque_id')
                    p_cuenta = str(p.get('cuenta_tesoreria') or p.get('metodo') or 'Transferencia Bancaria').strip()

                    if p_chq and ws_c:
                        for r_c in range(5, ws_c.max_row + 1):
                            if str(ws_c.cell(r_c, 1).value or '').strip() == str(p_chq).strip():
                                nro_chq = str(ws_c.cell(r_c, 8).value or ws_c.cell(r_c, 1).value or '')
                                banco_chq = str(ws_c.cell(r_c, 7).value or 'Banco')
                                is_prop = str(p_chq).startswith('CHQP-') or str(ws_c.cell(r_c, 17).value or '').strip().lower() == 'propio'
                                ws_c.cell(r_c, 5, nombre)
                                ws_c.cell(r_c, 10, nombre)
                                ws_c.cell(r_c, 11, 'Usado')
                                ws_c.cell(r_c, 12, nombre)
                                ws_c.cell(r_c, 13, today_date)
                                ws_c.cell(r_c, 16, f"Liquidación de Sueldo ({periodo}) - {nombre}")
                                p_cuenta = f"Cheque Propio - {banco_chq} N° {nro_chq}" if is_prop else f"Cheque N° {nro_chq} ({banco_chq})"
                                break

                    if ws_e:
                        max_egr_num += 1
                        new_egr_id = f"EGR-{max_egr_num:06d}"
                        obs_tag = f"[LIQUIDACIÓN: {eid}:{periodo}] {periodo} - {p_cuenta}".strip()
                        ws_e.append([
                            new_egr_id, today_date, '', 'Liquidación de Sueldos', '', nombre, cuil,
                            'Liquidación Quincenal', '', '', eid, f"Sueldo ({periodo}) - Pago {p_idx + 1} ({p_cuenta})",
                            0, 0, 0, p_monto, 'Pagado', p_monto, today_date, p_cuenta, 0, '', active_liq_id, obs_tag
                        ])

                # Mark novelties as Liquidado in Excel
                if 'NOVEDADES_PERSONAL' in wb.sheetnames:
                    ws_nov = wb['NOVEDADES_PERSONAL']
                    item_nov_ids = {str(n['id']).strip() for n in item.get('novedades', []) if n.get('id')}
                    for r in range(5, ws_nov.max_row + 1):
                        nov_id_cell = str(ws_nov.cell(r, 1).value or '').strip()
                        if nov_id_cell in item_nov_ids:
                            ws_nov.cell(r, 11, active_liq_id)
                            ws_nov.cell(r, 12, 'Liquidado')

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[confirmar_liquidacion Excel Warning] {e}")

        # 3. Automatic Advance Registration for Overpayment (Surplus / Cheque mayor)
        for item in items:
            eid = str(item.get('id_empleado', '')).strip()
            periodo = str(item.get('periodo_label', quincena)).strip()
            nombre = item.get('nombre') or item.get('nombre_empleado') or 'Empleado'
            active_liq_id = item.get('_active_liq_id')
            excedente = item.get('_excedente', 0.0)

            if excedente > 0:
                next_q_date = self._calcular_fecha_siguiente_quincena(periodo, today_date)
                try:
                    nov_res = self.add_novedad_personal({
                        'empleado': nombre,
                        'empleado_id': eid,
                        'tipo': 'Deducción',
                        'concepto': f"Adelanto por excedente de pago (Liquidación {active_liq_id})",
                        'monto': excedente,
                        'fecha': next_q_date,
                        'medio_pago': 'Excedente Liquidación',
                        'observaciones': f"Generado automáticamente por sobrepago de ${excedente:,.2f} en liquidación {active_liq_id} ({periodo})."
                    })
                    adelantos_generados.append({
                        'empleado': nombre,
                        'monto': excedente,
                        'fecha': next_q_date,
                        'novedad_id': nov_res.get('id') if isinstance(nov_res, dict) else None
                    })
                except Exception as ex:
                    print(f"[confirmar_liquidacion Error al registrar adelanto por excedente] {ex}")

        # Construct informative response message
        if len(items) == 1:
            emp_nom = items[0].get('nombre', 'Empleado')
            liq_id = items[0].get('_active_liq_id', '')
            tot_p = items[0].get('_total_pagado', items[0].get('sueldo_final', 0))
            s_fin = items[0].get('sueldo_final', 0)
            exc = items[0].get('_excedente', 0)

            if exc > 0 and adelantos_generados:
                next_dt = adelantos_generados[0]['fecha']
                msg = f"¡Liquidación {liq_id} confirmada para {emp_nom}! Al pagarse ${tot_p:,.2f} sobre un sueldo de ${s_fin:,.2f}, se registró un adelanto automático de ${exc:,.2f} para la siguiente quincena ({next_dt})."
            else:
                msg = f"¡Liquidación {liq_id} confirmada con éxito para {emp_nom} por ${s_fin:,.2f}!"
        else:
            msg = f"Se procesaron {saved_count} liquidaciones exitosamente."

        return {
            "status": "success",
            "message": msg,
            "count": saved_count,
            "total": total_sum,
            "adelantos_generados": adelantos_generados
        }

    def delete_liquidacion_historica(self, liq_id):
        """Deletes a historical liquidation entry by ID from Supabase and Excel, reverts associated cheques and novelties, and removes surplus advances."""
        lid_clean = str(liq_id).strip()

        # 1. Supabase Master Delete
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    # Delete from liquidaciones
                    conn.execute(text("DELETE FROM liquidaciones WHERE id_liquidacion = :lid"), {'lid': lid_clean})
                    
                    # Delete associated Egresos
                    conn.execute(text("DELETE FROM egresos WHERE id_liquidacion = :lid"), {'lid': lid_clean})
                    
                    # Revert used cheques to Disponible
                    conn.execute(text("""
                        UPDATE cheques SET
                            estado = 'Disponible',
                            endosado_tenedor = NULL,
                            destino_usado_en = NULL,
                            fecha_uso = NULL,
                            id_egreso = NULL,
                            observaciones = REPLACE(observaciones, CONCAT(' | Liquidación ', :lid), ''),
                            updated_at = NOW()
                        WHERE observaciones LIKE :pat;
                    """), {'lid': lid_clean, 'pat': f"%{lid_clean}%"})
                    
                    # Revert novelties to Pendiente
                    conn.execute(text("""
                        UPDATE novedades_personal SET
                            id_liquidacion = NULL,
                            estado = 'Pendiente'
                        WHERE id_liquidacion = :lid;
                    """), {'lid': lid_clean})
                    
                    # Delete automatic surplus novelty generated by this liquidation
                    conn.execute(text("""
                        DELETE FROM novedades_personal 
                        WHERE (concepto LIKE :pat OR observaciones LIKE :pat) AND (LOWER(COALESCE(concepto, '')) LIKE '%excedente%' OR LOWER(COALESCE(observaciones, '')) LIKE '%excedente%');
                    """), {'pat': f"%{lid_clean}%"})
                    
                    # Revert remuneraciones to Pendiente
                    conn.execute(text("""
                        UPDATE remuneraciones SET
                            id_liquidacion = NULL,
                            estado = 'Pendiente',
                            fecha_pago = NULL
                        WHERE id_liquidacion = :lid;
                    """), {'lid': lid_clean})
            except Exception as e:
                print(f"[delete_liquidacion_historica Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            if 'LIQUIDACIONES' in wb.sheetnames:
                ws = wb['LIQUIDACIONES']
                for r in range(ws.max_row, 4, -1):
                    if str(ws.cell(r, 1).value or '').strip() == lid_clean:
                        ws.delete_rows(r)

            if 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                for r in range(ws_e.max_row, 4, -1):
                    col_liq = str(ws_e.cell(r, 23).value or '').strip()
                    if col_liq == lid_clean:
                        ws_e.delete_rows(r)

            if 'CHEQUES' in wb.sheetnames:
                ws_c = wb['CHEQUES']
                for r in range(5, ws_c.max_row + 1):
                    obs_chq = str(ws_c.cell(r, 16).value or '')
                    if f"Liquidación {lid_clean}" in obs_chq or lid_clean in obs_chq:
                        ws_c.cell(r, 11, 'Disponible')
                        ws_c.cell(r, 5, None)
                        ws_c.cell(r, 10, None)
                        ws_c.cell(r, 12, None)
                        ws_c.cell(r, 13, None)
                        ws_c.cell(r, 16, obs_chq.replace(f" | Liquidación {lid_clean}", "").replace(f"Liquidación {lid_clean}", ""))

            if 'NOVEDADES_PERSONAL' in wb.sheetnames:
                ws_nov = wb['NOVEDADES_PERSONAL']
                for r in range(ws_nov.max_row, 4, -1):
                    concep = str(ws_nov.cell(r, 6).value or '')
                    obs_nov = str(ws_nov.cell(r, 13).value or '')
                    lid_nov = str(ws_nov.cell(r, 11).value or '').strip()
                    if (lid_clean in concep or lid_clean in obs_nov) and ('excedente' in concep.lower() or 'excedente' in obs_nov.lower()):
                        ws_nov.delete_rows(r)
                    elif lid_nov == lid_clean:
                        ws_nov.cell(r, 11, None)
                        ws_nov.cell(r, 12, 'Pendiente')

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[delete_liquidacion_historica Excel Warning] {e}")

        return {"status": "success", "id": lid_clean}

    def get_historial_liquidaciones(self, mes=None, anio=None, fecha_desde=None, fecha_hasta=None):
        """Returns confirmed liquidation history from LIQUIDACIONES sheet (deduplicated)."""
        headers, data = self.get_sheet_data('LIQUIDACIONES')
        if not data:
            try:
                wb = self.load_wb(data_only=True)
                if 'LIQUIDACIONES' in wb.sheetnames:
                    ws = wb['LIQUIDACIONES']
                    headers, data = self._read_sheet_rows(ws, start_row=5)
            except Exception:
                pass
        
        rows = []
        seen_keys = set()
        target_month = int(mes) if mes else None
        target_year = int(anio) if anio else None

        for r in reversed(data):
            lid = self._get_row_prop(r, ['ID liquidación', 'ID'])
            eid = self._get_row_prop(r, ['ID empleado'])
            periodo = self._get_row_prop(r, ['Período quincena', 'Período', 'Quincena'])

            if not lid or 'ejemplo' in lid.lower():
                continue

            f_conf = self._get_row_prop(r, ['Fecha confirmación', 'Fecha'])
            if f_conf:
                f_iso = str(f_conf).split('T')[0].split(' ')[0]
                if target_month or target_year:
                    try:
                        parts = f_iso.split('-')
                        if len(parts) >= 3:
                            y = int(parts[0])
                            m = int(parts[1])
                            if target_year and y != target_year:
                                continue
                            if target_month and m != target_month:
                                continue
                    except Exception:
                        pass
                else:
                    if fecha_desde and f_iso < str(fecha_desde).strip():
                        continue
                    if fecha_hasta and f_iso > str(fecha_hasta).strip():
                        continue
            elif fecha_desde or fecha_hasta:
                continue
            
            key = (eid.lower(), periodo.lower(), str(f_conf or '')[:7])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            desglose_raw = self._get_row_prop(r, ['Desglose JSON'])
            desglose_list = []
            if desglose_raw:
                try:
                    desglose_list = json.loads(desglose_raw)
                except:
                    desglose_list = []

            rows.append({
                "id_liquidacion": lid,
                "fecha_confirmacion": self._get_row_prop(r, ['Fecha confirmación', 'Fecha']),
                "periodo_label": periodo,
                "id_empleado": eid,
                "nombre": self._get_row_prop(r, ['Empleado', 'Nombre']),
                "puesto": self._get_row_prop(r, ['Puesto']),
                "dni": self._get_row_prop(r, ['DNI']),
                "cuil": self._get_row_prop(r, ['CUIL']),
                "banco": self._get_row_prop(r, ['Entidad bancaria', 'Banco']),
                "cbu": self._get_row_prop(r, ['CBU']),
                "alias_cbu": self._get_row_prop(r, ['Alias CBU', 'Alias']),
                "sueldo_fijo_base": self._to_float(self._get_row_prop(r, ['Sueldo fijo base'])),
                "comision_pct": self._to_float(self._get_row_prop(r, ['Comisión pct'])),
                "cant_viajes": int(self._to_float(self._get_row_prop(r, ['Cant viajes']))),
                "total_comisiones": self._to_float(self._get_row_prop(r, ['Total comisiones'])),
                "sueldo_final": self._to_float(self._get_row_prop(r, ['Sueldo final'])),
                "estado": self._get_row_prop(r, ['Estado']) or 'CONFIRMADO',
                "desglose_viajes": desglose_list
            })

        return sorted(rows, key=lambda x: x.get('id_liquidacion', ''), reverse=True)

    # ÓRDENES DE COMPRA MODULE
    def _ensure_ordenes_compra_sheet(self, wb):
        headers = [
            'ID orden',
            'Fecha',
            'Proveedor',
            'CUIT proveedor',
            'Tipo insumo',
            'Unidad',
            'Detalle',
            'Neto',
            'IVA %',
            'Total',
            'Forma pago',
            'Estado',
            'Fecha pago',
            'ID egreso',
            'Observaciones',
            'Cantidad/Litros',
            'ID cheque',
            'N° cheque'
        ]
        if 'ORDENES_COMPRA' not in wb.sheetnames:
            ws = wb.create_sheet('ORDENES_COMPRA')
            ws.cell(1, 1, 'ECONCATIVO - GESTIÓN DE ÓRDENES DE COMPRA')
            ws.cell(2, 1, 'Adquisición de insumos, servicios y repuestos')
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        else:
            ws = wb['ORDENES_COMPRA']
            # Standardize row 4 headers to ensure clean column indexing
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        return wb['ORDENES_COMPRA']

    def get_ordenes_compra(self):
        headers, data = self.get_sheet_data('ORDENES_COMPRA')
        if not data:
            try:
                wb = self.load_wb(data_only=True)
                ws = self._ensure_ordenes_compra_sheet(wb)
                headers, data = self._read_sheet_rows(ws, start_row=5)
            except Exception:
                pass
        
        rows = []
        for r in data:
            oid = self._get_row_prop(r, ['ID orden', 'ID'])
            if not oid:
                continue
            
            detalle_val = self._get_row_prop(r, ['Detalle', 'Cantidad', 'Descripción'])
            litros_val = self._to_float(self._get_row_prop(r, ['Cantidad/Litros', 'Cantidad', 'Litros']))
            if litros_val <= 0 and detalle_val:
                m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:litros|litro|lts|lt|l\b)', str(detalle_val), re.IGNORECASE)
                if m:
                    try:
                        litros_val = float(m.group(1).replace(',', '.'))
                    except:
                        pass

            rows.append({
                "ID orden": oid,
                "Fecha": self._get_row_prop(r, ['Fecha']),
                "Proveedor": self._get_row_prop(r, ['Proveedor']),
                "CUIT proveedor": self._get_row_prop(r, ['CUIT proveedor', 'CUIT', 'Solicitante']),
                "Tipo insumo": self._get_row_prop(r, ['Tipo insumo', 'Rubro', 'Destino/Unidad']),
                "Unidad": self._get_row_prop(r, ['Unidad', 'Descripción', 'Destino']),
                "Detalle": detalle_val,
                "Neto": self._to_float(self._get_row_prop(r, ['Neto', 'Precio unitario'])),
                "IVA %": self._to_float(self._get_row_prop(r, ['IVA %'])) if self._get_row_prop(r, ['IVA %']) else 21.0,
                "Total": self._to_float(self._get_row_prop(r, ['Total'])),
                "Forma pago": self._get_row_prop(r, ['Forma pago', 'Condición pago']),
                "Estado": self._get_row_prop(r, ['Estado']) or 'Pendiente',
                "Fecha pago": self._get_row_prop(r, ['Fecha pago', 'Fecha requerida']),
                "ID egreso": self._get_row_prop(r, ['ID egreso', 'Enlace PDF']),
                "Observaciones": self._get_row_prop(r, ['Observaciones']),
                "Cantidad/Litros": litros_val,
                "ID cheque": self._get_row_prop(r, ['ID cheque', 'id_cheque', 'cheque_id']),
                "N° cheque": self._get_row_prop(r, ['N° cheque', 'Número cheque', 'Nro cheque', 'nro_cheque']),
                "_row_idx": r.get('_row_idx')
            })
        return sorted(rows, key=lambda x: str(x.get('ID orden', '')), reverse=True)

    def _get_next_orden_compra_id(self, ws):
        max_num = 0
        for r in range(5, ws.max_row + 1):
            val = str(ws.cell(r, 1).value or '').strip()
            if val.startswith('ORD-'):
                try:
                    num = int(val.replace('ORD-', ''))
                    if num > max_num:
                        max_num = num
                except:
                    pass
        return f"ORD-{max_num + 1:06d}"

    def add_orden_compra(self, odata):
        neto = abs(float(odata.get('neto', 0)))
        iva_pct = abs(float(odata.get('iva_pct', 21)))
        total = abs(float(odata.get('total', 0)))
        if total <= 0 and neto > 0:
            total = neto + (neto * (iva_pct / 100.0))

        litros = abs(float(odata.get('litros', 0)))
        detalle = odata.get('detalle', '')
        if litros <= 0 and detalle:
            m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:litros|litro|lts|lt|l\b)', str(detalle), re.IGNORECASE)
            if m:
                try:
                    litros = float(m.group(1).replace(',', '.'))
                except:
                    pass

        cheque_id = odata.get('cheque_id', '') or odata.get('ID cheque', '')
        nro_cheque = odata.get('nro_cheque', '') or odata.get('N° cheque', '')

        # Generate next ID
        if self.supabase_service and self.supabase_service.is_connected():
            new_id = self.supabase_service.get_next_id('ordenes_compra', 'ORD', 'id_orden')
            if cheque_id and not nro_cheque:
                try:
                    with self.supabase_service.engine.connect() as conn:
                        from sqlalchemy import text
                        row_chq = conn.execute(text("SELECT nro_cheque FROM cheques WHERE id_cheque = :cid"), {'cid': cheque_id}).fetchone()
                        if row_chq and row_chq[0]:
                            nro_cheque = str(row_chq[0])
                except Exception:
                    pass
        else:
            wb_tmp = self.load_wb(data_only=False)
            ws_tmp = self._ensure_ordenes_compra_sheet(wb_tmp)
            new_id = self._get_next_orden_compra_id(ws_tmp)

        fecha_val = odata.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        prov_val = odata.get('proveedor', '')
        cuit_val = odata.get('cuit', '')
        tipo_ins_val = odata.get('tipo_insumo', 'Combustible')
        unidad_val = odata.get('unidad', 'General')
        forma_pago_val = odata.get('forma_pago', 'Cuenta Corriente 30 días')
        estado_val = odata.get('estado', 'Pendiente')
        obs_val = odata.get('observaciones', '')

        # 1. Supabase First Insert
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ordenes_compra (
                            id_orden, fecha, proveedor, cuit_proveedor, tipo_insumo, unidad, detalle,
                            neto, iva_pct, total, forma_pago, estado, fecha_pago, id_egreso,
                            observaciones, cantidad_litros, id_cheque, nro_cheque, created_at, updated_at
                        ) VALUES (
                            :id_orden, CAST(NULLIF(:fecha, '') AS date), :proveedor, :cuit, :tipo_insumo, :unidad, :detalle,
                            :neto, :iva_pct, :total, :forma_pago, :estado, NULL, NULL,
                            :observaciones, :cantidad_litros, :id_cheque, :nro_cheque, NOW(), NOW()
                        )
                    """), {
                        'id_orden': new_id,
                        'fecha': fecha_val,
                        'proveedor': prov_val,
                        'cuit': cuit_val,
                        'tipo_insumo': tipo_ins_val,
                        'unidad': unidad_val,
                        'detalle': detalle,
                        'neto': neto,
                        'iva_pct': iva_pct,
                        'total': total,
                        'forma_pago': forma_pago_val,
                        'estado': estado_val,
                        'observaciones': obs_val,
                        'cantidad_litros': litros,
                        'id_cheque': cheque_id or None,
                        'nro_cheque': nro_cheque or None
                    })
            except Exception as e:
                print(f"[add_orden_compra Supabase Error] {e}")

        # 2. Excel safe mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_ordenes_compra_sheet(wb)
            if cheque_id and not nro_cheque and 'CHEQUES' in wb.sheetnames:
                ws_chq = wb['CHEQUES']
                for r in range(5, ws_chq.max_row + 1):
                    if str(ws_chq.cell(r, 1).value or '').strip() == str(cheque_id).strip():
                        nro_cheque = str(ws_chq.cell(r, 8).value or '')
                        break

            row_vals = [
                new_id,
                fecha_val,
                prov_val,
                cuit_val,
                tipo_ins_val,
                unidad_val,
                detalle,
                neto,
                iva_pct,
                total,
                forma_pago_val,
                estado_val,
                '',  # Fecha pago
                '',  # ID egreso
                obs_val,
                litros,
                cheque_id,
                nro_cheque
            ]
            ws.append(row_vals)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[add_orden_compra Excel Warning] {e}")

        return {"status": "success", "id": new_id, "total": total}

    def update_orden_compra(self, oid, odata):
        oid_clean = str(oid).strip()
        neto = abs(float(odata.get('neto', 0)))
        iva_pct = abs(float(odata.get('iva_pct', 21)))
        total = abs(float(odata.get('total', 0)))
        if total <= 0 and neto > 0:
            total = neto + (neto * (iva_pct / 100.0))

        litros = abs(float(odata.get('litros', 0)))
        detalle = odata.get('detalle', '')
        if litros <= 0 and detalle:
            m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:litros|litro|lts|lt|l\b)', str(detalle), re.IGNORECASE)
            if m:
                try:
                    litros = float(m.group(1).replace(',', '.'))
                except:
                    pass

        cheque_id = odata.get('cheque_id', '') or odata.get('ID cheque', '')
        nro_cheque = odata.get('nro_cheque', '') or odata.get('N° cheque', '')

        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    if cheque_id and not nro_cheque:
                        row_chq = conn.execute(text("SELECT nro_cheque FROM cheques WHERE id_cheque = :cid"), {'cid': cheque_id}).fetchone()
                        if row_chq and row_chq[0]:
                            nro_cheque = str(row_chq[0])

                    conn.execute(text("""
                        UPDATE ordenes_compra SET
                            fecha = COALESCE(CAST(NULLIF(:fecha, '') AS date), fecha),
                            proveedor = COALESCE(NULLIF(:proveedor, ''), proveedor),
                            cuit_proveedor = COALESCE(NULLIF(:cuit, ''), cuit_proveedor),
                            tipo_insumo = COALESCE(NULLIF(:tipo_insumo, ''), tipo_insumo),
                            unidad = COALESCE(NULLIF(:unidad, ''), unidad),
                            detalle = COALESCE(NULLIF(:detalle, ''), detalle),
                            neto = CASE WHEN :neto > 0 THEN :neto ELSE neto END,
                            iva_pct = :iva_pct,
                            total = CASE WHEN :total > 0 THEN :total ELSE total END,
                            forma_pago = COALESCE(NULLIF(:forma_pago, ''), forma_pago),
                            estado = COALESCE(NULLIF(:estado, ''), estado),
                            observaciones = COALESCE(NULLIF(:observaciones, ''), observaciones),
                            cantidad_litros = CASE WHEN :litros > 0 THEN :litros ELSE cantidad_litros END,
                            id_cheque = COALESCE(NULLIF(:id_cheque, ''), id_cheque),
                            nro_cheque = COALESCE(NULLIF(:nro_cheque, ''), nro_cheque),
                            updated_at = NOW()
                        WHERE id_orden = :oid;
                    """), {
                        'oid': oid_clean,
                        'fecha': str(odata.get('fecha') or '').strip() or None,
                        'proveedor': str(odata.get('proveedor') or '').strip() or None,
                        'cuit': str(odata.get('cuit') or '').strip() or None,
                        'tipo_insumo': str(odata.get('tipo_insumo') or '').strip() or None,
                        'unidad': str(odata.get('unidad') or '').strip() or None,
                        'detalle': detalle or None,
                        'neto': neto,
                        'iva_pct': iva_pct,
                        'total': total,
                        'forma_pago': str(odata.get('forma_pago') or '').strip() or None,
                        'estado': str(odata.get('estado') or '').strip() or None,
                        'observaciones': str(odata.get('observaciones') or '').strip() or None,
                        'litros': litros,
                        'id_cheque': cheque_id or None,
                        'nro_cheque': nro_cheque or None
                    })
            except Exception as e:
                print(f"[update_orden_compra Supabase Error] {e}")

        # 2. Excel safe mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_ordenes_compra_sheet(wb)
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip() == oid_clean:
                    target_row = r
                    break
            if target_row:
                if neto <= 0: neto = float(ws.cell(target_row, 8).value or 0)
                if total <= 0: total = float(ws.cell(target_row, 10).value or 0)
                if 'fecha' in odata: ws.cell(target_row, 2, odata['fecha'])
                if 'proveedor' in odata: ws.cell(target_row, 3, odata['proveedor'])
                if 'cuit' in odata: ws.cell(target_row, 4, odata['cuit'])
                if 'tipo_insumo' in odata: ws.cell(target_row, 5, odata['tipo_insumo'])
                if 'unidad' in odata: ws.cell(target_row, 6, odata['unidad'])
                if 'detalle' in odata: ws.cell(target_row, 7, odata['detalle'])
                ws.cell(target_row, 8, neto)
                ws.cell(target_row, 9, iva_pct)
                ws.cell(target_row, 10, total)
                if 'forma_pago' in odata: ws.cell(target_row, 11, odata['forma_pago'])
                if 'estado' in odata: ws.cell(target_row, 12, odata['estado'])
                if 'observaciones' in odata: ws.cell(target_row, 15, odata['observaciones'])
                if litros > 0: ws.cell(target_row, 16, litros)
                if cheque_id:
                    ws.cell(target_row, 17, cheque_id)
                    ws.cell(target_row, 18, nro_cheque)
                wb.save(self.excel_path)
                self._invalidate_cache()
        except Exception as e:
            print(f"[update_orden_compra Excel Warning] {e}")

        return {"status": "success", "id": oid_clean}

    def confirmar_pago_orden_compra(self, oid, pdata=None):
        """Marks a Purchase Order as Pagado, records it in Supabase EGRESOS (and Excel mirror), and handles Vuelto vs Credit Balance."""
        if pdata is None: pdata = {}
        oid_clean = str(oid).strip()
        today_date = datetime.now().strftime('%Y-%m-%d')

        proveedor = 'Proveedor'
        cuit = ''
        tipo_insumo = 'Insumos Generales'
        unidad = ''
        detalle = ''
        forma_pago = 'Cuenta Corriente 30 días'
        total_orden = 0.0
        neto_orden = 0.0
        litros = 0.0
        cheque_id = str(pdata.get('cheque_id') or '').strip()
        nro_cheque = str(pdata.get('nro_cheque') or '').strip()
        egreso_id = ''
        obs = ''

        # 1. Load current PO data from Supabase if connected
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    ord_row = conn.execute(text("SELECT * FROM ordenes_compra WHERE id_orden = :oid"), {'oid': oid_clean}).mappings().first()
                    if ord_row:
                        proveedor = str(ord_row.get('proveedor') or proveedor)
                        cuit = str(ord_row.get('cuit_proveedor') or cuit)
                        tipo_insumo = str(ord_row.get('tipo_insumo') or tipo_insumo)
                        unidad = str(ord_row.get('unidad') or unidad)
                        detalle = str(ord_row.get('detalle') or detalle)
                        forma_pago = str(ord_row.get('forma_pago') or forma_pago)
                        total_orden = float(ord_row.get('total') or 0.0)
                        neto_orden = float(ord_row.get('neto') or 0.0)
                        litros = float(ord_row.get('cantidad_litros') or 0.0)
                        cheque_id = cheque_id or str(ord_row.get('id_cheque') or '').strip()
                        nro_cheque = nro_cheque or str(ord_row.get('nro_cheque') or '').strip()
                        egreso_id = str(ord_row.get('id_egreso') or '').strip()
                        obs = str(ord_row.get('observaciones') or '')
            except Exception as e:
                print(f"[confirmar_pago_orden_compra fetch error] {e}")

        # Fallback to Excel if not found
        wb = self.load_wb(data_only=False)
        ws = self._ensure_ordenes_compra_sheet(wb)
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == oid_clean:
                target_row = r
                break

        if target_row and total_orden <= 0:
            proveedor = str(ws.cell(target_row, 3).value or proveedor)
            cuit = str(ws.cell(target_row, 4).value or cuit)
            tipo_insumo = str(ws.cell(target_row, 5).value or tipo_insumo)
            unidad = str(ws.cell(target_row, 6).value or unidad)
            detalle = str(ws.cell(target_row, 7).value or detalle)
            neto_orden = float(ws.cell(target_row, 8).value or 0.0)
            total_orden = float(ws.cell(target_row, 10).value or 0.0)
            forma_pago = str(ws.cell(target_row, 11).value or forma_pago)
            egreso_id = egreso_id or str(ws.cell(target_row, 14).value or '').strip()
            obs = obs or str(ws.cell(target_row, 15).value or '')
            litros = litros or float(ws.cell(target_row, 16).value or 0.0)
            cheque_id = cheque_id or str(ws.cell(target_row, 17).value or '').strip()
            nro_cheque = nro_cheque or str(ws.cell(target_row, 18).value or '').strip()

        if not target_row and not (self.supabase_service and self.supabase_service.is_connected() and total_orden > 0):
            return {"status": "error", "message": f"Orden de Compra {oid} no encontrada."}

        cuenta_origen = str(pdata.get('cuenta_origen') or pdata.get('cuenta_tesoreria') or '').strip()
        cuenta_a_validar = cuenta_origen if cuenta_origen else forma_pago

        # Treasury funds availability validation
        if total_orden > 0 and not any(k in cuenta_a_validar.lower() for k in ['cuenta corriente', '30 días', 'cheque']):
            is_valid, disp_amt, acc_name, err_msg = self.validate_treasury_disponibilidad(cuenta_a_validar, total_orden)
            if not is_valid:
                return {"status": "error", "message": err_msg}

        vuelto_opcion = pdata.get('vuelto_opcion', 'saldo_favor')
        vuelto_monto = self._to_float(pdata.get('vuelto_monto', 0))
        vuelto_cuenta = pdata.get('vuelto_cuenta', 'Caja Chica Efectivo')

        if litros <= 0 and detalle:
            m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:litros|litro|lts|lt|l\b)', str(detalle), re.IGNORECASE)
            if m:
                try:
                    litros = float(m.group(1).replace(',', '.'))
                except:
                    pass

        # Cheque amount lookup
        monto_cheque = 0.0
        if cheque_id and self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    chq_row = conn.execute(text("SELECT monto, nro_cheque FROM cheques WHERE id_cheque = :cid"), {'cid': cheque_id}).first()
                    if chq_row:
                        monto_cheque = float(chq_row[0] or 0.0)
                        if not nro_cheque: nro_cheque = str(chq_row[1] or '')
            except Exception:
                pass

        if cheque_id and monto_cheque <= 0 and 'CHEQUES' in wb.sheetnames:
            ws_chq = wb['CHEQUES']
            for r in range(5, ws_chq.max_row + 1):
                if str(ws_chq.cell(r, 1).value or '').strip() == str(cheque_id).strip():
                    monto_cheque = self._to_float(ws_chq.cell(r, 4).value)
                    if not nro_cheque: nro_cheque = str(ws_chq.cell(r, 8).value or '')
                    break

        monto_egreso = max(total_orden, monto_cheque) if monto_cheque > 0 else total_orden

        # Allocate Egreso ID
        if not egreso_id or not egreso_id.startswith('EGR-'):
            if self.supabase_service and self.supabase_service.is_connected():
                egreso_id = self.supabase_service.get_next_id('egresos', 'EGR', 'id_egreso')
            else:
                ws_e = wb['EGRESOS'] if 'EGRESOS' in wb.sheetnames else None
                max_egr_num = 0
                if ws_e:
                    for re_idx in range(5, ws_e.max_row + 1):
                        ev = str(ws_e.cell(re_idx, 1).value or '').strip()
                        if ev.startswith('EGR-'):
                            try:
                                num = int(ev.split('-')[-1])
                                if num > max_egr_num: max_egr_num = num
                            except: pass
                egreso_id = f"EGR-{max_egr_num + 1:06d}"

        cuenta_origen = pdata.get('cuenta_origen') or pdata.get('cuenta_tesoreria') or ''
        if cuenta_origen:
            medio_egreso = f"{forma_pago} - {cuenta_origen}" if forma_pago and forma_pago.lower() not in cuenta_origen.lower() else cuenta_origen
        elif nro_cheque:
            medio_egreso = f"Cheque N° {nro_cheque}"
        else:
            medio_egreso = forma_pago
        obs_egreso = f"Generado automáticamente desde Orden de Compra {oid_clean} (Cheque N° {nro_cheque} por ${monto_egreso:,.2f}). {obs}".strip() if nro_cheque else f"Generado automáticamente desde Orden de Compra {oid_clean}. {obs}".strip()

        # 2. Supabase Master Updates
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    # Update Orden de Compra
                    conn.execute(text("""
                        UPDATE ordenes_compra SET
                            estado = 'Pagado',
                            fecha_pago = CAST(:today AS date),
                            id_egreso = :egr_id,
                            id_cheque = COALESCE(NULLIF(:cid, ''), id_cheque),
                            nro_cheque = COALESCE(NULLIF(:nro_chq, ''), nro_cheque),
                            updated_at = NOW()
                        WHERE id_orden = :oid;
                    """), {
                        'today': today_date,
                        'egr_id': egreso_id,
                        'cid': cheque_id or None,
                        'nro_chq': nro_cheque or None,
                        'oid': oid_clean
                    })

                    # Update Cheque if assigned
                    if cheque_id:
                        conn.execute(text("""
                            UPDATE cheques SET
                                estado = 'Entregado Proveedor',
                                endosado_tenedor = :proveedor,
                                destino_usado_en = :destino,
                                fecha_uso = CAST(:today AS date),
                                id_egreso = :egr_id,
                                observaciones = CONCAT(COALESCE(observaciones, ''), ' | Órden ', :oid),
                                updated_at = NOW()
                            WHERE id_cheque = :cid;
                        """), {
                            'proveedor': proveedor,
                            'destino': f"Pago Órden {oid_clean} - {proveedor}",
                            'today': today_date,
                            'egr_id': egreso_id,
                            'oid': oid_clean,
                            'cid': cheque_id
                        })

                    # Upsert Egreso
                    conn.execute(text("""
                        INSERT INTO egresos (
                            id_egreso, fecha_comprobante, categoria, subcategoria, proveedor, cuit,
                            tipo_comprobante, nro_comprobante, unidad, descripcion, cantidad_litros,
                            neto, iva, total, estado_pago, importe_pagado, fecha_pago, medio_pago,
                            saldo, observaciones, created_at, updated_at
                        ) VALUES (
                            :id_egreso, CAST(:today AS date), :tipo_insumo, 'Órdenes de Compra', :proveedor, :cuit,
                            'Orden de Compra', :oid, :unidad, :detalle, :litros,
                            :neto, :iva, :total, 'Pagado', :total, CAST(:today AS date), :medio_egreso,
                            0, :obs, NOW(), NOW()
                        )
                        ON CONFLICT (id_egreso) DO UPDATE SET
                            fecha_comprobante = EXCLUDED.fecha_comprobante,
                            proveedor = EXCLUDED.proveedor,
                            cuit = EXCLUDED.cuit,
                            descripcion = EXCLUDED.descripcion,
                            cantidad_litros = EXCLUDED.cantidad_litros,
                            total = EXCLUDED.total,
                            estado_pago = 'Pagado',
                            importe_pagado = EXCLUDED.total,
                            fecha_pago = EXCLUDED.fecha_pago,
                            medio_pago = EXCLUDED.medio_pago,
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id_egreso': egreso_id,
                        'today': today_date,
                        'tipo_insumo': tipo_insumo,
                        'proveedor': proveedor,
                        'cuit': cuit,
                        'oid': oid_clean,
                        'unidad': unidad if unidad != 'General' else None,
                        'detalle': f"[ORDEN DE COMPRA {oid_clean}] {detalle}",
                        'litros': litros,
                        'neto': neto_orden,
                        'iva': max(0.0, total_orden - neto_orden),
                        'total': monto_egreso,
                        'medio_egreso': medio_egreso,
                        'obs': obs_egreso
                    })

                    # If Vuelto received
                    if vuelto_opcion == 'vuelto_recibido' and vuelto_monto > 0:
                        vuelto_medio = pdata.get('vuelto_medio', 'efectivo')
                        new_ing_id = self.supabase_service.get_next_id('ingresos', 'ING', 'id_ingreso')
                        vuelto_desc = f"Vuelto recibido de {proveedor} por pago en Orden {oid_clean}"
                        conn.execute(text("""
                            INSERT INTO ingresos (
                                id_ingreso, fecha_emision, tipo_comprobante, nro_factura_arca, cliente, cuit_cuil,
                                actividad, neto, total, estado_cobro, importe_cobrado, fecha_cobro, medio_cobro,
                                saldo, observaciones, created_at, updated_at
                            ) VALUES (
                                :iid, CAST(:today AS date), 'Vuelto Proveedor', :oid, :proveedor, :cuit,
                                'Vuelto de Pago', :monto, :monto, 'COBRADO', :monto, CAST(:today AS date), :medio,
                                0, :obs, NOW(), NOW()
                            )
                        """), {
                            'iid': new_ing_id,
                            'today': today_date,
                            'oid': oid_clean,
                            'proveedor': proveedor,
                            'cuit': cuit,
                            'monto': vuelto_monto,
                            'medio': f"Vuelto - {vuelto_cuenta}",
                            'obs': vuelto_desc
                        })
            except Exception as e:
                print(f"[confirmar_pago_orden_compra Supabase Error] {e}")

        # 3. Excel Safe Mirror
        try:
            if target_row:
                ws.cell(target_row, 12, 'Pagado')
                ws.cell(target_row, 13, today_date)
                ws.cell(target_row, 14, egreso_id)
                if nro_cheque: ws.cell(target_row, 18, nro_cheque)

            if cheque_id and 'CHEQUES' in wb.sheetnames:
                ws_chq = wb['CHEQUES']
                for r in range(5, ws_chq.max_row + 1):
                    if str(ws_chq.cell(r, 1).value or '').strip() == str(cheque_id).strip():
                        ws_chq.cell(r, 5, proveedor)
                        ws_chq.cell(r, 10, proveedor)
                        ws_chq.cell(r, 11, 'Entregado Proveedor')
                        ws_chq.cell(r, 12, f"Pago Órden {oid_clean} - {proveedor}")
                        ws_chq.cell(r, 13, today_date)
                        ws_chq.cell(r, 14, egreso_id)
                        cur_obs = str(ws_chq.cell(r, 16).value or '').strip()
                        ws_chq.cell(r, 16, f"{cur_obs} | Órden {oid_clean}".strip(' |'))
                        break

            if 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                found_egr = None
                for re_idx in range(5, ws_e.max_row + 1):
                    if str(ws_e.cell(re_idx, 1).value or '').strip() == egreso_id:
                        found_egr = re_idx
                        break
                if found_egr:
                    ws_e.cell(found_egr, 2, today_date)
                    ws_e.cell(found_egr, 4, tipo_insumo)
                    ws_e.cell(found_egr, 6, proveedor)
                    ws_e.cell(found_egr, 7, cuit)
                    ws_e.cell(found_egr, 12, f"[ORDEN DE COMPRA {oid_clean}] {detalle}")
                    ws_e.cell(found_egr, 13, litros)
                    ws_e.cell(found_egr, 16, monto_egreso)
                    ws_e.cell(found_egr, 17, 'Pagado')
                    ws_e.cell(found_egr, 19, today_date)
                    ws_e.cell(found_egr, 20, medio_egreso)
                    ws_e.cell(found_egr, 24, obs_egreso)
                else:
                    ws_e.append([
                        egreso_id, today_date, '', tipo_insumo, '', proveedor, cuit,
                        'Orden de Compra', oid_clean, unidad if unidad != 'General' else '',
                        '', f"[ORDEN DE COMPRA {oid_clean}] {detalle}", litros,
                        neto_orden, 0, monto_egreso, 'Pagado', monto_egreso, today_date,
                        medio_egreso, cheque_id or 0, '', '', obs_egreso
                    ])

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[confirmar_pago_orden_compra Excel Warning] {e}")

        return {"status": "success", "id": oid_clean, "egreso_id": egreso_id, "monto_pagado": monto_egreso}

    def delete_orden_compra(self, oid):
        """Deletes a Purchase Order from Supabase and Excel, reverts assigned cheque if any, and deletes its associated Egreso."""
        oid_clean = str(oid).strip()
        egreso_id = None
        cheque_id = None

        # 1. Supabase Master Delete
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    # Fetch linked egreso and cheque
                    row = conn.execute(text("SELECT id_egreso, id_cheque FROM ordenes_compra WHERE id_orden = :oid"), {'oid': oid_clean}).first()
                    if row:
                        egreso_id = str(row[0] or '').strip() or None
                        cheque_id = str(row[1] or '').strip() or None

                    # Delete PO
                    conn.execute(text("DELETE FROM ordenes_compra WHERE id_orden = :oid"), {'oid': oid_clean})

                    # Delete associated Egreso if exists
                    if egreso_id:
                        conn.execute(text("DELETE FROM egresos WHERE id_egreso = :eid"), {'eid': egreso_id})

                    # Revert Cheque to Disponible if exists
                    if cheque_id:
                        conn.execute(text("""
                            UPDATE cheques SET
                                estado = 'Disponible',
                                destino_usado_en = NULL,
                                fecha_uso = NULL,
                                id_egreso = NULL,
                                updated_at = NOW()
                            WHERE id_cheque = :cid
                        """), {'cid': cheque_id})
            except Exception as e:
                print(f"[delete_orden_compra Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            if 'ORDENES_COMPRA' in wb.sheetnames:
                ws = wb['ORDENES_COMPRA']
                target_row = None
                for r in range(5, ws.max_row + 1):
                    if str(ws.cell(r, 1).value or '').strip() == oid_clean:
                        target_row = r
                        if not egreso_id: egreso_id = str(ws.cell(r, 14).value or '').strip() or None
                        if not cheque_id: cheque_id = str(ws.cell(r, 17).value or '').strip() or None
                        break
                if target_row:
                    ws.delete_rows(target_row)

            if cheque_id and 'CHEQUES' in wb.sheetnames:
                ws_chq = wb['CHEQUES']
                for rc in range(5, ws_chq.max_row + 1):
                    if str(ws_chq.cell(rc, 1).value or '').strip() == str(cheque_id).strip():
                        ws_chq.cell(rc, 11, 'Disponible')
                        ws_chq.cell(rc, 12, '')
                        ws_chq.cell(rc, 13, '')
                        ws_chq.cell(rc, 14, '')
                        break

            if egreso_id and 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                for r in range(5, ws_e.max_row + 1):
                    if str(ws_e.cell(r, 1).value or '').strip() == egreso_id:
                        ws_e.delete_rows(r)
                        break

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[delete_orden_compra Excel Warning] {e}")

        return {"status": "success", "id": oid_clean}

    def get_proveedor_summary(self, proveedor_nombre, mes=None, anio=None):
        """Generates structured summary data of purchase orders, payments, vueltos, and balance for a specific provider."""
        wb = self.load_wb(data_only=True)
        
        # Helper to clean prefixes like "Proveedor: ", "Cliente: "
        def clean_p(n):
            s = str(n or '').strip().lower()
            for prefix in ['proveedor:', 'cliente:', 'empleado:', 'chofer:']:
                if s.startswith(prefix):
                    s = s[len(prefix):].strip()
            return s

        prov_clean = clean_p(proveedor_nombre)

        # 1. Fetch Provider Master Details
        prov_info = {}
        if 'PROVEEDORES' in wb.sheetnames:
            _, p_rows = self._read_sheet_rows(wb['PROVEEDORES'])
            for pr in p_rows:
                p_name = self._get_row_prop(pr, ['Razón social / Nombre', 'Nombre', 'Proveedor', 'Razón Social'])
                if clean_p(p_name) == prov_clean:
                    prov_info = {
                        'nombre': p_name,
                        'cuit': self._get_row_prop(pr, ['CUIT / CUIL', 'CUIT', 'CUIL']),
                        'email': self._get_row_prop(pr, ['Correo electrónico', 'Email', 'Correo']),
                        'telefono': self._get_row_prop(pr, ['Teléfono', 'Celular']),
                        'iva': self._get_row_prop(pr, ['Condición IVA', 'IVA'])
                    }
                    break

        if not prov_info.get('nombre'):
            prov_info['nombre'] = proveedor_nombre

        mes_val = None
        if mes and str(mes).lower() not in ['todas', 'todos', 'all', '']:
            try:
                mes_val = int(mes)
            except:
                pass

        anio_val = None
        if anio and str(anio).lower() not in ['todos', 'todas', 'all', '']:
            try:
                anio_val = int(anio)
            except:
                pass

        meses_nombres = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        periodo_label = "Todas las Fechas"
        if mes_val and anio_val:
            periodo_label = f"{meses_nombres.get(mes_val, '')} {anio_val}"
        elif mes_val:
            periodo_label = f"Mes {meses_nombres.get(mes_val, '')}"
        elif anio_val:
            periodo_label = f"Año {anio_val}"

        def parse_dt(f_str):
            if not f_str or str(f_str).strip() in ['', '-']:
                return None
            try:
                if isinstance(f_str, datetime):
                    return f_str
                f_clean = str(f_str).strip()
                if ' ' in f_clean:
                    f_clean = f_clean.split(' ')[0]
                if '-' in f_clean:
                    parts = f_clean.split('-')
                    if len(parts) == 3:
                        return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                elif '/' in f_clean:
                    parts = f_clean.split('/')
                    if len(parts) == 3:
                        return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                pass
            return None

        # Determine date filter range
        is_period_filtered = False
        period_start = None
        period_end = None

        if mes_val and anio_val:
            is_period_filtered = True
            period_start = datetime(anio_val, mes_val, 1, 0, 0, 0)
            if mes_val == 12:
                period_end = datetime(anio_val + 1, 1, 1, 0, 0, 0)
            else:
                period_end = datetime(anio_val, mes_val + 1, 1, 0, 0, 0)
        elif anio_val:
            is_period_filtered = True
            period_start = datetime(anio_val, 1, 1, 0, 0, 0)
            period_end = datetime(anio_val + 1, 1, 1, 0, 0, 0)

        # 2. Track prior period balance components and current period items
        saldo_anterior_compras = 0.0
        saldo_anterior_pagos = 0.0
        saldo_anterior_vueltos = 0.0

        filtered_ordenes = []
        tot_comprado = 0.0
        tot_litros = 0.0

        # 2a. Fetch Purchase Orders for this supplier
        all_ordenes = self.get_ordenes_compra()
        for o in all_ordenes:
            p_name = clean_p(o.get('Proveedor'))
            if prov_clean and (prov_clean in p_name or p_name in prov_clean):
                f_date = o.get('Fecha')
                dt = parse_dt(f_date)
                monto = float(o.get('Total') or 0.0)
                litros = float(o.get('Cantidad/Litros') or o.get('litros') or 0.0)

                if is_period_filtered and dt and dt < period_start:
                    saldo_anterior_compras += monto
                elif not is_period_filtered or not dt or (dt >= period_start and dt < period_end):
                    filtered_ordenes.append(o)
                    tot_comprado += monto
                    tot_litros += litros

        # 2b. Fetch Egresos / Payments for this supplier
        filtered_egresos = []
        tot_pagado = 0.0
        seen_egr_ids = set()

        if 'EGRESOS' in wb.sheetnames:
            _, e_rows = self._read_sheet_rows(wb['EGRESOS'])
            for er in e_rows:
                p_name = clean_p(self._get_row_prop(er, ['Proveedor / Destinatario', 'Proveedor', 'Destinatario']))
                det_str = str(self._get_row_prop(er, ['Descripción / Concepto', 'Descripción', 'Detalle']) or '').strip().lower()
                cat_str = str(self._get_row_prop(er, ['Categoría / Rubro', 'Categoría', 'Rubro']) or '').strip().lower()
                subcat_str = str(self._get_row_prop(er, ['Subcategoría', 'Subcat']) or '').strip().lower()
                obs_str = str(self._get_row_prop(er, ['Observaciones']) or '').strip().lower()

                if prov_clean and (prov_clean in p_name or p_name in prov_clean or prov_clean in det_str):
                    f_date = self._get_row_prop(er, ['Fecha comprobante', 'Fecha egreso', 'Fecha pago', 'Fecha'])
                    dt = parse_dt(f_date)
                    monto = self._to_float(self._get_row_prop(er, ['Importe Total ($)', 'Total', 'Importe']))
                    monto_pagado = self._to_float(self._get_row_prop(er, ['Importe Pagado ($)', 'Importe Pagado', 'Pagado', 'Importe pagado']))
                    m_pago_medio = str(self._get_row_prop(er, ['Forma de Pago', 'Medio de Pago', 'Medio Pago']) or '').lower()
                    st_pago = str(self._get_row_prop(er, ['Estado pago', 'Estado Pago', 'Estado']) or '').strip().upper()
                    is_reversion = (st_pago in ['REVERTIDO', 'RECHAZADO'] or 'reversión' in det_str or 'reversion' in det_str or 'revertid' in det_str)

                    if is_reversion:
                        monto_pagado = 0.0
                    elif 'saldo a favor' in m_pago_medio and 'neto' not in m_pago_medio and monto_pagado == monto:
                        monto_pagado = 0.0
                    elif monto_pagado == 0 and monto > 0 and 'saldo a favor' not in m_pago_medio and 'entrega' not in cat_str:
                        monto_pagado = monto

                    is_linked_to_oc = ('ord-' in det_str or 'ord-' in obs_str or 'órden de compra' in det_str or 'orden de compra' in det_str)
                    is_entrega_cc = any(w in cat_str or w in subcat_str or w in det_str for w in ['entrega a cuenta', 'pago a cuenta', 'adelanto', 'cuenta corriente', 'cc-'])
                    is_direct_purchase = (not is_linked_to_oc and not is_entrega_cc and monto > 0 and not is_reversion)
                    litros_direct = self._to_float(self._get_row_prop(er, ['Cantidad / Litros', 'Litros', 'Cantidad']))

                    eid = self._get_row_prop(er, ['ID egreso', 'ID'])

                    if is_period_filtered and dt and dt < period_start:
                        saldo_anterior_pagos += monto_pagado
                        if is_direct_purchase:
                            saldo_anterior_compras += monto
                    elif not is_period_filtered or not dt or (dt >= period_start and dt < period_end):
                        seen_egr_ids.add(eid)
                        filtered_egresos.append({
                            'ID': eid,
                            'Fecha': f_date,
                            'Forma de Pago': self._get_row_prop(er, ['Forma de Pago', 'Medio de Pago', 'Medio Pago']),
                            'Descripción': self._get_row_prop(er, ['Descripción / Concepto', 'Descripción', 'Detalle']),
                            'Total': monto,
                            'Pagado': monto_pagado,
                            'Estado': st_pago
                        })
                        tot_pagado += monto_pagado

                        if is_direct_purchase:
                            tot_comprado += monto
                            if litros_direct > 0:
                                tot_litros += litros_direct

                            cat_raw = self._get_row_prop(er, ['Categoría / Rubro', 'Categoría', 'Rubro']) or 'Gasto Directo'
                            det_raw = self._get_row_prop(er, ['Descripción / Concepto', 'Descripción', 'Detalle']) or 'Gasto operativo'
                            filtered_ordenes.append({
                                'ID orden': eid,
                                'id': eid,
                                'Fecha': f_date,
                                'Proveedor': proveedor_nombre,
                                'Tipo insumo': cat_raw,
                                'litros': litros_direct,
                                'Cantidad/Litros': litros_direct,
                                'Detalle': f"[Gasto Directo] {det_raw}",
                                'Total': monto,
                                'Estado': 'Comprado'
                            })

        # 2c. Fetch Vueltos recibidos in INGRESOS
        tot_vueltos = 0.0
        if 'INGRESOS' in wb.sheetnames:
            _, i_rows = self._read_sheet_rows(wb['INGRESOS'])
            for ir in i_rows:
                p_name = clean_p(self._get_row_prop(ir, ['Cliente', 'Cliente / Origen', 'Proveedor', 'Origen']))
                det_str = str(self._get_row_prop(ir, ['Actividad', 'Observaciones', 'Tipo comprobante', 'Detalle/Concepto', 'Concepto', 'Detalle']) or '').strip().lower()
                if (prov_clean and (prov_clean in p_name or p_name in prov_clean or prov_clean in det_str)) and 'vuelto' in det_str:
                    f_date = self._get_row_prop(ir, ['Fecha cobro', 'Fecha cobro/ingreso', 'Fecha emisión', 'Fecha'])
                    dt = parse_dt(f_date)
                    m_vuelto = self._to_float(self._get_row_prop(ir, ['Importe cobrado', 'Total', 'Monto cobrado ($)', 'Monto']))

                    if is_period_filtered and dt and dt < period_start:
                        saldo_anterior_vueltos += m_vuelto
                    elif not is_period_filtered or not dt or (dt >= period_start and dt < period_end):
                        tot_vueltos += m_vuelto

        saldo_anterior = round(saldo_anterior_compras - saldo_anterior_pagos, 2)
        tot_pagado_neto = round(tot_pagado, 2)
        saldo_periodo = round(tot_comprado - tot_pagado_neto, 2)
        saldo_final = round(saldo_anterior + saldo_periodo, 2)

        if saldo_final < -0.01:
            estado_saldo = 'SALDO_A_FAVOR'
            saldo_favor = abs(saldo_final)
            saldo_deudor = 0.0
            saldo_label = f"🟢 SALDO A FAVOR DE LA EMPRESA: ${abs(saldo_final):,.2f}"
        elif saldo_final > 0.01:
            estado_saldo = 'SALDO_ADEUDADO'
            saldo_favor = 0.0
            saldo_deudor = saldo_final
            saldo_label = f"🔴 SALDO ADEUDADO AL PROVEEDOR: ${saldo_final:,.2f}"
        else:
            estado_saldo = 'SALDO_AL_DIA'
            saldo_favor = 0.0
            saldo_deudor = 0.0
            saldo_label = "⚪ SALDO AL DÍA ($0,00)"

        fecha_inicio_label = f"01/{mes_val:02d}/{anio_val}" if (mes_val and anio_val) else f"01/01/{anio_val}" if anio_val else ""

        return {
            'proveedor_nombre': proveedor_nombre,
            'proveedor_info': prov_info,
            'periodo_label': periodo_label,
            'is_period_filtered': is_period_filtered,
            'saldo_anterior': saldo_anterior,
            'fecha_inicio_label': fecha_inicio_label,
            'ordenes': filtered_ordenes,
            'egresos': filtered_egresos,
            'total_comprado': tot_comprado,
            'total_pagado': tot_pagado_neto,
            'total_vueltos': tot_vueltos,
            'total_litros': tot_litros,
            'saldo': saldo_final,
            'saldo_favor': saldo_favor,
            'saldo_deudor': saldo_deudor,
            'estado_saldo': estado_saldo,
            'saldo_label': saldo_label
        }

    # CHEQUES MODULE
    def _ensure_cheques_sheet(self, wb):
        headers = [
            'ID cheque',
            'Fecha ingreso',
            'Tipo',
            'Monto',
            'Cliente / Emisor',
            'CUIT emisor',
            'Banco',
            'N° Cheque',
            'Fecha cobro',
            'Endosado / Tenedor',
            'Estado',
            'Destino / Usado en',
            'Fecha uso',
            'ID egreso',
            'ID ingreso origen',
            'Observaciones'
        ]
        if 'CHEQUES' not in wb.sheetnames:
            ws = wb.create_sheet('CHEQUES')
            ws.cell(1, 1, 'ECONCATIVO - GESTIÓN DE CHEQUES Y E-CHEQS EN CARTERA')
            ws.cell(2, 1, 'Registro de cheques de terceros recibidos y endosados')
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        else:
            ws = wb['CHEQUES']
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
        return ws
    def _is_duplicate_cheque(self, ws_chq, nro_cheque, banco=''):
        """Checks if a cheque with the given number and bank is already registered in the active sheet."""
        nro_clean = str(nro_cheque or '').strip()
        if not nro_clean or nro_clean.lower() in ['a completar', 's/n', '0', '-']:
            return False
        banco_clean = str(banco or '').strip().lower()
        for r in range(5, ws_chq.max_row + 1):
            ex_nro = str(ws_chq.cell(r, 8).value or '').strip()
            if ex_nro == nro_clean:
                ex_banco = str(ws_chq.cell(r, 7).value or '').strip().lower()
                if not banco_clean or not ex_banco or ex_banco == banco_clean:
                    return True
        return False

    def _sync_missing_cheques_from_ingresos(self):
        wb = self.load_wb(data_only=False)
        ws_i = wb['INGRESOS']
        ws_c = self._ensure_cheques_sheet(wb)

        existing_ing_ids = set()
        for r in range(5, ws_c.max_row + 1):
            ing_id = str(ws_c.cell(r, 15).value or '').strip()
            if ing_id:
                existing_ing_ids.add(ing_id)

        max_chq_num = 0
        for r in range(5, ws_c.max_row + 1):
            val = str(ws_c.cell(r, 1).value or '').strip()
            if val.startswith('CHQ-') and not val.startswith('CHQP-'):
                try:
                    num = int(val.replace('CHQ-', ''))
                    if num > max_chq_num:
                        max_chq_num = num
                except Exception:
                    pass

        added_count = 0
        for r in range(5, ws_i.max_row + 1):
            i_id = str(ws_i.cell(r, 1).value or '').strip()
            if not i_id or i_id in existing_ing_ids:
                continue
            
            medio = str(ws_i.cell(r, 20).value or '')
            if 'cheque' in medio.lower() or 'echeq' in medio.lower() or 'e-cheq' in medio.lower():
                match = re.search(r'(?:Cheque|E-Cheq|Echeq):\s*\$?([\d\.,]+)', medio, re.IGNORECASE)
                monto = 0.0
                if match:
                    raw = match.group(1).strip()
                    if ',' in raw and '.' in raw:
                        if raw.rfind('.') > raw.rfind(','):
                            raw = raw.replace(',', '')
                        else:
                            raw = raw.replace('.', '').replace(',', '.')
                    elif ',' in raw:
                        raw = raw.replace(',', '.')
                    try:
                        monto = float(raw)
                    except Exception:
                        monto = 0.0
                
                if monto <= 0:
                    monto = self._to_float(ws_i.cell(r, 18).value)

                if monto > 0:
                    max_chq_num += 1
                    cid = f"CHQ-{max_chq_num:06d}"
                    fecha_cobro = str(ws_i.cell(r, 19).value or ws_i.cell(r, 2).value or '2026-09-17')
                    cliente = str(ws_i.cell(r, 6).value or 'Cliente')
                    cuit = str(ws_i.cell(r, 7).value or '')
                    
                    banco = 'A completar'
                    if '-' in medio:
                        banco = medio.split('-')[-1].strip()

                    is_echeq = 'echeq' in medio.lower() or 'e-cheq' in medio.lower()
                    tipo_chq = 'E-Cheq' if is_echeq else 'Cheque Físico'
                    
                    row_chq = [
                        cid,
                        fecha_cobro,
                        tipo_chq,
                        monto,
                        cliente,
                        cuit,
                        banco,
                        f"CHQ-{monto:.0f}",
                        fecha_cobro,
                        'ECONCATIVO S.A.S.',
                        'Disponible',
                        '',
                        '',
                        '',
                        i_id,
                        f"Cobro de Ingreso {i_id}"
                    ]
                    
                    ws_c.append(row_chq)
                    existing_ing_ids.add(i_id)
                    added_count += 1

        if added_count > 0:
            wb.save(self.excel_path)

    def get_cheques(self):
        # When Supabase is connected, avoid running legacy Excel sync that could recreate deleted cheques
        if not (self.supabase_service and self.supabase_service.is_connected()):
            try:
                self._sync_missing_cheques_from_ingresos()
            except Exception:
                pass
        headers, data = self.get_sheet_data('CHEQUES')
        if not data:
            try:
                wb = self.load_wb(data_only=True)
                ws = self._ensure_cheques_sheet(wb)
                headers, data = self._read_sheet_rows(ws, start_row=5)
            except Exception:
                pass
        
        rows = []
        for r in data:
            cid = self._get_row_prop(r, ['ID cheque', 'ID', 'id_cheque'])
            if not cid:
                continue
            rows.append({
                "id": cid,
                "fecha_ingreso": self._get_row_prop(r, ['Fecha ingreso', 'Fecha', 'fecha_ingreso']),
                "tipo": self._get_row_prop(r, ['Tipo', 'tipo']) or 'Cheque Físico',
                "monto": self._to_float(self._get_row_prop(r, ['Monto', 'monto'])),
                "cliente": self._get_row_prop(r, ['Cliente / Emisor', 'Cliente', 'Emisor', 'cliente_emisor']),
                "cuit_emisor": self._get_row_prop(r, ['CUIT emisor', 'CUIT', 'cuit_emisor']),
                "banco": self._get_row_prop(r, ['Banco', 'banco']),
                "nro_cheque": self._get_row_prop(r, ['N° Cheque', 'N° cheque', 'Numero', 'nro_cheque']),
                "fecha_cobro": self._get_row_prop(r, ['Fecha cobro', 'Vencimiento', 'fecha_cobro']),
                "endosado": self._get_row_prop(r, ['Endosado / Tenedor', 'Endosado', 'endosado_tenedor']),
                "estado": self._get_row_prop(r, ['Estado', 'estado']) or 'Disponible',
                "destino": self._get_row_prop(r, ['Destino / Usado en', 'Destino', 'destino_usado_en']),
                "fecha_uso": self._get_row_prop(r, ['Fecha uso', 'fecha_uso']),
                "id_egreso": self._get_row_prop(r, ['ID egreso', 'id_egreso']),
                "id_ingreso": self._get_row_prop(r, ['ID ingreso origen', 'ID ingreso', 'id_ingreso_origen']),
                "observaciones": self._get_row_prop(r, ['Observaciones', 'observaciones']),
                "origen": "Propio" if str(cid).startswith("CHQP-") else "Terceros",
                "_row_idx": r.get('_row_idx')
            })
        return sorted(rows, key=lambda x: str(x.get('id', '')), reverse=True)

    def _get_next_cheque_id(self, ws):
        max_num = 0
        for r in range(5, ws.max_row + 1):
            val = str(ws.cell(r, 1).value or '').strip()
            if val.startswith('CHQ-'):
                try:
                    num = int(val.replace('CHQ-', ''))
                    if num > max_num:
                        max_num = num
                except:
                    pass
        return f"CHQ-{max_num + 1:06d}"

    def update_cheque(self, cid, cdata):
        """Updates cheque details (bank, cheque number, maturity date, endorsement, etc.)."""
        cid_clean = str(cid).strip()

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                update_fields = []
                params = {"cid": cid_clean}
                if 'tipo' in cdata:
                    update_fields.append("tipo = :tipo")
                    params["tipo"] = cdata['tipo']
                if 'monto' in cdata:
                    update_fields.append("monto = :monto")
                    params["monto"] = self._to_float(cdata['monto'])
                if 'cliente' in cdata:
                    update_fields.append("cliente_emisor = :cliente")
                    params["cliente"] = cdata['cliente']
                if 'cuit_emisor' in cdata:
                    update_fields.append("cuit_emisor = :cuit_emisor")
                    params["cuit_emisor"] = cdata['cuit_emisor']
                if 'banco' in cdata:
                    update_fields.append("banco = :banco")
                    params["banco"] = cdata['banco']
                if 'nro_cheque' in cdata:
                    update_fields.append("nro_cheque = :nro_cheque")
                    params["nro_cheque"] = cdata['nro_cheque']
                if 'fecha_cobro' in cdata:
                    if cdata['fecha_cobro']:
                        update_fields.append("fecha_cobro = CAST(:fecha_cobro AS date)")
                        params["fecha_cobro"] = cdata['fecha_cobro']
                    else:
                        update_fields.append("fecha_cobro = NULL")
                if 'endosado' in cdata:
                    update_fields.append("endosado_tenedor = :endosado")
                    params["endosado"] = cdata['endosado']
                if 'observaciones' in cdata:
                    update_fields.append("observaciones = :observaciones")
                    params["observaciones"] = cdata['observaciones']

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    sql_str = f"UPDATE cheques SET {', '.join(update_fields)} WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))"
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text(sql_str), params)
            except Exception as e:
                print(f"[DataManager] Error updating cheque in Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_cheques_sheet(wb)
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip().lower() == cid_clean.lower():
                    target_row = r
                    break
            if target_row:
                if 'tipo' in cdata: ws.cell(target_row, 3, cdata['tipo'])
                if 'monto' in cdata: ws.cell(target_row, 4, self._to_float(cdata['monto']))
                if 'cliente' in cdata: ws.cell(target_row, 5, cdata['cliente'])
                if 'cuit_emisor' in cdata: ws.cell(target_row, 6, cdata['cuit_emisor'])
                if 'banco' in cdata: ws.cell(target_row, 7, cdata['banco'])
                if 'nro_cheque' in cdata: ws.cell(target_row, 8, cdata['nro_cheque'])
                if 'fecha_cobro' in cdata: ws.cell(target_row, 9, cdata['fecha_cobro'])
                if 'endosado' in cdata: ws.cell(target_row, 10, cdata['endosado'])
                if 'observaciones' in cdata: ws.cell(target_row, 16, cdata['observaciones'])
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on update_cheque: {e}")

        self._invalidate_cache()
        return {"status": "success", "id": cid_clean}

    def usar_cheque(self, payload):
        """Marks a cheque as Usado with tracking of destination/recipient from Maestros, and records an automatic entry in EGRESOS in Supabase & Excel."""
        cid = str(payload.get('id') or '').strip()
        destino = payload.get('destino') or payload.get('proveedor') or 'Destinatario Registrado'
        fecha_uso = payload.get('fecha_uso') or datetime.now().strftime('%Y-%m-%d')
        monto = self._to_float(payload.get('monto') or 0)
        nro_cheque = str(payload.get('nro_cheque') or '').strip()
        banco_cheque = str(payload.get('banco') or '').strip()
        concepto = payload.get('concepto') or f"Uso/Endoso de Cheque a {destino}"
        egreso_id = None
        is_propio = cid.startswith('CHQP-')

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    chq_row = conn.execute(
                        text("SELECT id_cheque, monto, nro_cheque, banco, id_egreso FROM cheques WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))"),
                        {"cid": cid}
                    ).fetchone()
                    if chq_row:
                        cm = dict(chq_row._mapping)
                        if not monto:
                            monto = self._to_float(cm.get('monto') or 0)
                        if not nro_cheque:
                            nro_cheque = str(cm.get('nro_cheque') or '')
                        if not banco_cheque:
                            banco_cheque = str(cm.get('banco') or '')
                        egreso_id = str(cm.get('id_egreso') or '').strip()

                if not egreso_id or not egreso_id.startswith('EGR-'):
                    egreso_id = self.supabase_service.get_next_id('egresos', 'EGR', 'id_egreso')

                dest_lower = str(destino).lower()
                if 'empleado' in dest_lower or 'chofer' in dest_lower:
                    rubro = 'Liquidación de Sueldos'
                elif 'combustible' in dest_lower or 'ypf' in dest_lower or 'shell' in dest_lower:
                    rubro = 'Combustible'
                elif 'repuesto' in dest_lower or 'taller' in dest_lower or 'mantenimiento' in dest_lower:
                    rubro = 'Reparaciones & Taller'
                else:
                    rubro = 'Otros'

                medio_str = f"Cheque Propio - {banco_cheque}" if is_propio else (f"Cheque N° {nro_cheque}" if nro_cheque else "Cheque de Terceros")

                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE cheques
                        SET estado = 'Usado',
                            destino_usado_en = :destino,
                            fecha_uso = CAST(:fuso AS date),
                            endosado_tenedor = :destino,
                            id_egreso = :eid,
                            observaciones = CASE 
                                WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                ELSE observaciones || ' | ' || :obs
                            END,
                            updated_at = NOW()
                        WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                    """), {
                        "destino": destino,
                        "fuso": fecha_uso,
                        "eid": egreso_id,
                        "obs": concepto,
                        "cid": cid
                    })

                    egr_exists = conn.execute(
                        text("SELECT id_egreso FROM egresos WHERE TRIM(LOWER(id_egreso)) = TRIM(LOWER(:eid))"),
                        {"eid": egreso_id}
                    ).fetchone()

                    egr_desc = f"[CHEQUE {'PROPIO ' if is_propio else ''}{cid}] {concepto}"
                    egr_obs = f"Egreso generado automáticamente al registrar uso del cheque {cid} ({banco_cheque} N° {nro_cheque}). {concepto}".strip()

                    if egr_exists:
                        conn.execute(text("""
                            UPDATE egresos
                            SET fecha_comprobante = CAST(:fcomp AS date),
                                categoria = :cat,
                                proveedor = :prov,
                                descripcion = :desc,
                                neto = :neto,
                                total = :total,
                                estado_pago = 'Pagado',
                                importe_pagado = :total,
                                fecha_pago = CAST(:fcomp AS date),
                                medio_pago = :medio,
                                saldo = 0,
                                observaciones = :obs,
                                updated_at = NOW()
                            WHERE TRIM(LOWER(id_egreso)) = TRIM(LOWER(:eid))
                        """), {
                            "fcomp": fecha_uso,
                            "cat": rubro,
                            "prov": destino,
                            "desc": egr_desc,
                            "neto": monto,
                            "total": monto,
                            "medio": medio_str,
                            "obs": egr_obs,
                            "eid": egreso_id
                        })
                    else:
                        conn.execute(text("""
                            INSERT INTO egresos (
                                id_egreso, fecha_comprobante, categoria, proveedor,
                                tipo_comprobante, nro_comprobante, descripcion,
                                neto, total, estado_pago, importe_pagado, fecha_pago,
                                medio_pago, saldo, observaciones
                            ) VALUES (
                                :eid, CAST(:fcomp AS date), :cat, :prov,
                                :tipo_comp, :cid, :desc,
                                :neto, :total, 'Pagado', :total, CAST(:fcomp AS date),
                                :medio, 0, :obs
                            )
                        """), {
                            "eid": egreso_id,
                            "fcomp": fecha_uso,
                            "cat": rubro,
                            "prov": destino,
                            "tipo_comp": 'Cheque Propio' if is_propio else 'Cheque',
                            "cid": cid,
                            "desc": egr_desc,
                            "neto": monto,
                            "total": monto,
                            "medio": medio_str,
                            "obs": egr_obs
                        })
            except Exception as e:
                print(f"[DataManager] Error in usar_cheque Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_cheques_sheet(wb)
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip().lower() == cid.lower():
                    target_row = r
                    break
            if target_row:
                if not monto: monto = float(ws.cell(target_row, 4).value or 0)
                if not nro_cheque: nro_cheque = str(ws.cell(target_row, 8).value or '')
                if not banco_cheque: banco_cheque = str(ws.cell(target_row, 7).value or '')
                if not egreso_id: egreso_id = str(ws.cell(target_row, 14).value or '').strip()

                ws.cell(target_row, 5, destino)
                ws.cell(target_row, 10, destino)
                ws.cell(target_row, 11, 'Usado')
                ws.cell(target_row, 12, destino)
                ws.cell(target_row, 13, fecha_uso)
                if concepto:
                    ws.cell(target_row, 16, concepto)

                ws_e = wb['EGRESOS'] if 'EGRESOS' in wb.sheetnames else None
                if ws_e:
                    if not egreso_id or not egreso_id.startswith('EGR-'):
                        max_egr_num = 0
                        for re_idx in range(5, ws_e.max_row + 1):
                            ev = str(ws_e.cell(re_idx, 1).value or '').strip()
                            if ev.startswith('EGR-'):
                                try:
                                    num = int(ev.split('-')[-1])
                                    if num > max_egr_num: max_egr_num = num
                                except: pass
                        egreso_id = f"EGR-{max_egr_num + 1:06d}"
                        ws.cell(target_row, 14, egreso_id)

                        row_e_dict = {
                            1: egreso_id,
                            2: fecha_uso,
                            4: 'Otros',
                            6: destino,
                            8: 'Cheque Propio' if is_propio else 'Cheque',
                            9: cid,
                            12: f"[CHEQUE {'PROPIO ' if is_propio else ''}{cid}] {concepto}",
                            13: 0,
                            16: monto,
                            17: 'Pagado',
                            18: monto,
                            19: fecha_uso,
                            20: f"Cheque N° {nro_cheque}" if nro_cheque else "Cheque",
                            21: cid,
                            24: f"Egreso generado automáticamente al registrar uso del cheque {cid}. {concepto}".strip()
                        }
                        target_egr_row = ws_e.max_row + 1
                        for c_idx, c_val in row_e_dict.items():
                            ws_e.cell(target_egr_row, c_idx, c_val)
                    else:
                        for re_idx in range(5, ws_e.max_row + 1):
                            if str(ws_e.cell(re_idx, 1).value or '').strip() == egreso_id:
                                ws_e.cell(re_idx, 2, fecha_uso)
                                ws_e.cell(re_idx, 6, destino)
                                ws_e.cell(re_idx, 12, f"[CHEQUE {cid}] {concepto}")
                                ws_e.cell(re_idx, 16, monto)
                                ws_e.cell(re_idx, 17, 'Pagado')
                                ws_e.cell(re_idx, 18, monto)
                                ws_e.cell(re_idx, 19, fecha_uso)
                                break
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on usar_cheque: {e}")

        self._invalidate_cache()
        return {"status": "success", "id": cid, "monto": monto, "destino": destino, "egreso_id": egreso_id}

    def revertir_uso_cheque(self, payload):
        """Reverts cheque usage with full support for bounced lifecycle:
           - 'rechazado_pendiente': Rechazado - Pendiente
           - 'representacion': En Re-presentación
           - 'anulado_incobrable': Anulado / Incobrable
           - 'disponible': Disponible (Error de Carga)
        """
        if isinstance(payload, str):
            cid = payload
            motivo = ''
            accion = 'disponible'
        else:
            cid = payload.get('id')
            motivo = payload.get('motivo', '')
            accion = payload.get('accion', 'rechazado_pendiente')

        wb = self.load_wb(data_only=False)
        if 'CHEQUES' not in wb.sheetnames:
            return {"status": "error", "message": "Hoja CHEQUES no existe."}

        ws = wb['CHEQUES']
        target_row = None
        for r in range(5, ws.max_row + 1):
            if str(ws.cell(r, 1).value or '').strip() == str(cid).strip():
                target_row = r
                break

        if not target_row:
            return {"status": "error", "message": f"Cheque {cid} no encontrado."}

        today_str = datetime.now().strftime('%Y-%m-%d')

        if accion == 'representacion':
            nuevo_estado = 'En Re-presentación'
        elif accion == 'anulado_incobrable':
            nuevo_estado = 'Anulado / Incobrable'
        elif accion == 'disponible':
            nuevo_estado = 'Disponible'
        else:
            nuevo_estado = 'Rechazado - Pendiente'

        nro_cheque = str(ws.cell(target_row, 8).value or '').strip()
        egreso_id = str(ws.cell(target_row, 14).value or '').strip()
        destino = str(ws.cell(target_row, 12).value or '').strip()
        cur_obs = str(ws.cell(target_row, 16).value or '').strip()

        # Extract any linked Orden de Compra ID from Destino or Obs (e.g. ORD-000001)
        linked_oc_ids = set()
        for text in [destino, cur_obs]:
            found_ords = re.findall(r'ORD-\d+', text, re.IGNORECASE)
            for f_ord in found_ords:
                linked_oc_ids.add(f_ord.upper())

        # 1. Revert linked Purchase Orders in ORDENES_COMPRA sheet
        if 'ORDENES_COMPRA' in wb.sheetnames:
            ws_oc = wb['ORDENES_COMPRA']
            for r_oc in range(5, ws_oc.max_row + 1):
                oc_id = str(ws_oc.cell(r_oc, 1).value or '').strip().upper()
                oc_chq_id = str(ws_oc.cell(r_oc, 17).value or '').strip()
                oc_chq_nro = str(ws_oc.cell(r_oc, 18).value or '').strip()
                oc_egr_id = str(ws_oc.cell(r_oc, 14).value or '').strip()

                is_match = False
                if str(cid).strip() and oc_chq_id == str(cid).strip():
                    is_match = True
                elif nro_cheque and oc_chq_nro == nro_cheque:
                    is_match = True
                elif egreso_id and oc_egr_id == egreso_id:
                    is_match = True
                elif oc_id in linked_oc_ids:
                    is_match = True

                if is_match:
                    ws_oc.cell(r_oc, 12, 'Pendiente')  # Revert status to Pendiente (Por Pagar)
                    ws_oc.cell(r_oc, 13, '')            # Clear fecha_pago
                    ws_oc.cell(r_oc, 14, '')            # Clear egreso_id
                    ws_oc.cell(r_oc, 17, '')            # Clear cheque_id
                    ws_oc.cell(r_oc, 18, '')            # Clear nro_cheque
                    oc_obs = str(ws_oc.cell(r_oc, 15).value or '').strip()
                    ws_oc.cell(r_oc, 15, f"{oc_obs} | [Revertido uso de Cheque {cid}]".strip(' |'))
                    if oc_id:
                        linked_oc_ids.add(oc_id)

        # 2. Update or delete corresponding Egreso entries in EGRESOS sheet
        if 'EGRESOS' in wb.sheetnames:
            ws_e = wb['EGRESOS']
            found_egreso = False
            for re_idx in range(ws_e.max_row, 4, -1):
                e_id = str(ws_e.cell(re_idx, 1).value or '').strip()
                e_nro_comp = str(ws_e.cell(re_idx, 9).value or '').strip()
                e_det = str(ws_e.cell(re_idx, 12).value or '').strip().upper()
                e_chq_id = str(ws_e.cell(re_idx, 21).value or '').strip()

                should_match = False
                if egreso_id and e_id == egreso_id:
                    should_match = True
                elif str(cid).strip() and e_chq_id == str(cid).strip():
                    should_match = True
                elif nro_cheque and (e_nro_comp == nro_cheque or f"N° {nro_cheque}" in e_det or f"Nº {nro_cheque}" in e_det):
                    should_match = True
                elif str(cid).strip() and f"CHEQUE {str(cid).strip().upper()}" in e_det:
                    should_match = True
                else:
                    for oc_id in linked_oc_ids:
                        if oc_id and f"[ORDEN DE COMPRA {oc_id}]" in e_det:
                            should_match = True
                            break

                if should_match:
                    found_egreso = True
                    if accion == 'disponible':
                        # Error de carga: Hard delete row
                        ws_e.delete_rows(re_idx)
                    else:
                        # Bounced / Reverted Cheque: Keep row as REVERTIDO in Cuenta Corriente audit trail
                        monto_original_egreso = self._to_float(ws_e.cell(re_idx, 16).value or 0)
                        ws_e.cell(re_idx, 17, 'REVERTIDO')
                        ws_e.cell(re_idx, 18, 0.0) # Importe Pagado = 0.0 so debt re-opens
                        ws_e.cell(re_idx, 21, monto_original_egreso) # Saldo = full amount
                        
                        det_curr = str(ws_e.cell(re_idx, 12).value or '').strip()
                        nro_chq_str = f" N° {nro_cheque}" if nro_cheque else ""
                        motivo_str = f" | Motivo: {motivo}" if motivo else ""
                        if "[REVERSIÓN" not in det_curr.upper():
                            ws_e.cell(re_idx, 12, f"[REVERSIÓN CHEQUE{nro_chq_str}]{motivo_str} - {det_curr}".strip(' -'))
                        
                        obs_curr = str(ws_e.cell(re_idx, 24).value or '').strip()
                        ws_e.cell(re_idx, 24, f"{obs_curr} | [{today_str}] Cheque revertido ({nuevo_estado}){motivo_str}".strip(' |'))

            # If no previous Egreso row existed and we have a target supplier (Destino) for a non-disponible reversal:
            if not found_egreso and accion != 'disponible' and destino:
                reversal_e_id = self._get_next_entity_id(ws_e, 'EGR')
                nro_chq_str = f" N° {nro_cheque}" if nro_cheque else ""
                motivo_str = f" | Motivo: {motivo}" if motivo else ""
                
                target_e_row = ws_e.max_row + 1
                row_data = {
                    1: reversal_e_id,
                    2: today_str,
                    3: today_str,
                    4: 'Devolución / Reversión',
                    6: destino,
                    12: f"[REVERSIÓN CHEQUE{nro_chq_str}]{motivo_str} | Deuda Reabierta",
                    16: 0.0,
                    17: 'REVERTIDO',
                    18: 0.0,
                    20: f"Cheque{nro_chq_str} (REVERTIDO)",
                    21: 0.0,
                    24: f"Reversión de cheque {cid} ({nuevo_estado}). {motivo}".strip()
                }
                for col_idx, val in row_data.items():
                    ws_e.cell(target_e_row, col_idx, val)

        # Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    if nuevo_estado == 'Disponible':
                        conn.execute(text("""
                            UPDATE cheques
                            SET estado = 'Disponible',
                                destino_usado_en = NULL,
                                fecha_uso = NULL,
                                id_egreso = NULL,
                                observaciones = CASE 
                                    WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                    ELSE observaciones || ' | ' || :obs
                                END,
                                updated_at = NOW()
                            WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                        """), {"obs": f"Revertido a disponible ({today_str})", "cid": str(cid).strip()})

                        if egreso_id and str(egreso_id).startswith('EGR-'):
                            conn.execute(text("DELETE FROM egresos WHERE TRIM(LOWER(id_egreso)) = TRIM(LOWER(:eid))"), {"eid": egreso_id})
                    else:
                        conn.execute(text("""
                            UPDATE cheques
                            SET estado = :st,
                                observaciones = CASE 
                                    WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                    ELSE observaciones || ' | ' || :obs
                                END,
                                updated_at = NOW()
                            WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                        """), {"st": nuevo_estado, "obs": f"Estado: {nuevo_estado} ({motivo})", "cid": str(cid).strip()})

                        if egreso_id and str(egreso_id).startswith('EGR-'):
                            conn.execute(text("""
                                UPDATE egresos
                                SET estado_pago = 'REVERTIDO',
                                    importe_pagado = 0,
                                    saldo = total,
                                    updated_at = NOW()
                                WHERE TRIM(LOWER(id_egreso)) = TRIM(LOWER(:eid))
                            """), {"eid": egreso_id})
            except Exception as e:
                print(f"[DataManager] Error reverting cheque in Supabase: {e}")

        # 3. Update CHEQUES sheet row
        ws.cell(target_row, 11, nuevo_estado)
        motivo_lbl = f"Motivo: {motivo}" if motivo else ""
        new_obs = f"{cur_obs} | [{today_str}] Estado: {nuevo_estado} ({motivo_lbl})".strip(' |')
        ws.cell(target_row, 16, new_obs)

        if nuevo_estado == 'Disponible':
            ws.cell(target_row, 12, '')  # Clear Destino
            ws.cell(target_row, 13, '')  # Clear Fecha uso
            ws.cell(target_row, 14, '')  # Clear ID egreso

        wb.save(self.excel_path)
        self._invalidate_cache()
        return {"status": "success", "id": cid, "estado": nuevo_estado}

    def regularizar_cheque(self, payload):
        """Regularises a rejected cheque via Transfer/Cash or Replacement Cheque."""
        cid = payload.get('id')
        metodo = payload.get('metodo') # 'efectivo', 'transferencia', 'nuevo_cheque'
        fecha = payload.get('fecha') or datetime.now().strftime('%Y-%m-%d')
        monto = self._to_float(payload.get('monto'))
        concepto = payload.get('concepto') or f"Regularización de Cheque {cid}"
        obs = payload.get('observaciones', '')

        wb = self.load_wb(data_only=False)
        ws_chq = self._ensure_cheques_sheet(wb)

        target_row = None
        for r in range(5, ws_chq.max_row + 1):
            if str(ws_chq.cell(r, 1).value or '').strip() == str(cid).strip():
                target_row = r
                break

        if not target_row:
            return {"status": "error", "message": f"Cheque {cid} no encontrado."}

        cliente_emisor = str(ws_chq.cell(target_row, 5).value or '').strip()
        cuit_emisor = str(ws_chq.cell(target_row, 6).value or '').strip()
        nro_cheque = str(ws_chq.cell(target_row, 8).value or '').strip()
        egreso_id = str(ws_chq.cell(target_row, 14).value or '').strip()
        destino = str(ws_chq.cell(target_row, 12).value or '').strip()
        monto_original = self._to_float(ws_chq.cell(target_row, 4).value or 0)
        monto_final = monto if monto > 0 else monto_original

        if metodo in ['efectivo', 'transferencia', 'acreditado', 'cobrado', 'acreditacion']:
            nuevo_st = 'Regularizado - Cobrado'
            ws_chq.cell(target_row, 11, nuevo_st)
            cur_obs = str(ws_chq.cell(target_row, 16).value or '').strip()
            lbl_met = "Acreditación 2° Intento" if metodo in ['acreditado', 'cobrado', 'acreditacion'] else metodo.capitalize()
            ws_chq.cell(target_row, 16, f"{cur_obs} | {lbl_met} ({fecha})".strip(' |'))

            # Supabase First
            if self.supabase_service and self.supabase_service.is_connected():
                from sqlalchemy import text
                try:
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE cheques
                            SET estado = 'Regularizado - Cobrado',
                                observaciones = CASE 
                                    WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                    ELSE observaciones || ' | ' || :obs
                                END,
                                updated_at = NOW()
                            WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                        """), {"obs": f"{lbl_met} ({fecha})", "cid": str(cid).strip()})
                except Exception as e:
                    print(f"[DataManager] Error regularising cheque in Supabase: {e}")

            # Extract any linked Orden de Compra ID from Destino or Obs (e.g. ORD-000001)
            linked_oc_ids = set()
            for text in [destino, cur_obs]:
                for f_ord in re.findall(r'ORD-\d+', text, re.IGNORECASE):
                    linked_oc_ids.add(f_ord.upper())

            # 1. Update matching Purchase Orders (ORDENES_COMPRA)
            if 'ORDENES_COMPRA' in wb.sheetnames:
                ws_oc = wb['ORDENES_COMPRA']
                for r_oc in range(5, ws_oc.max_row + 1):
                    oc_id = str(ws_oc.cell(r_oc, 1).value or '').strip().upper()
                    oc_chq_id = str(ws_oc.cell(r_oc, 17).value or '').strip()
                    oc_chq_nro = str(ws_oc.cell(r_oc, 18).value or '').strip()
                    oc_egr_id = str(ws_oc.cell(r_oc, 14).value or '').strip()
                    oc_obs = str(ws_oc.cell(r_oc, 15).value or '').strip().upper()

                    is_oc_match = False
                    if str(cid).strip() and oc_chq_id == str(cid).strip():
                        is_oc_match = True
                    elif nro_cheque and oc_chq_nro == nro_cheque:
                        is_oc_match = True
                    elif egreso_id and oc_egr_id == egreso_id:
                        is_oc_match = True
                    elif oc_id in linked_oc_ids:
                        is_oc_match = True
                    elif str(cid).strip() and f"CHEQUE {str(cid).strip().upper()}" in oc_obs:
                        is_oc_match = True

                    if is_oc_match:
                        ws_oc.cell(r_oc, 12, 'Pagado')
                        ws_oc.cell(r_oc, 13, fecha)
                        ws_oc.cell(r_oc, 17, cid)
                        ws_oc.cell(r_oc, 18, nro_cheque)
                        if oc_id:
                            linked_oc_ids.add(oc_id)

            # 2. Update or recreate matching EGRESOS row
            found_linked_egreso = False
            if 'EGRESOS' in wb.sheetnames:
                ws_e = wb['EGRESOS']
                for r_e in range(5, ws_e.max_row + 1):
                    e_id = str(ws_e.cell(r_e, 1).value or '').strip()
                    e_det = str(ws_e.cell(r_e, 12).value or '').strip().upper()
                    e_chq_id = str(ws_e.cell(r_e, 21).value or '').strip()

                    is_e_match = False
                    if egreso_id and e_id == egreso_id:
                        is_e_match = True
                    elif str(cid).strip() and e_chq_id == str(cid).strip():
                        is_e_match = True
                    elif nro_cheque and f"N° {nro_cheque}" in e_det:
                        is_e_match = True
                    elif str(cid).strip() and f"CHEQUE {str(cid).strip().upper()}" in e_det:
                        is_e_match = True
                    else:
                        for oc_id in linked_oc_ids:
                            if oc_id and f"[ORDEN DE COMPRA {oc_id}]" in e_det:
                                is_e_match = True
                                break

                    if is_e_match:
                        found_linked_egreso = True
                        m_total_e = self._to_float(ws_e.cell(r_e, 16).value or monto_final)
                        ws_e.cell(r_e, 17, 'Pagado')
                        ws_e.cell(r_e, 18, m_total_e if m_total_e > 0 else monto_final)
                        ws_e.cell(r_e, 19, fecha)
                        ws_e.cell(r_e, 20, f"Cheque N° {nro_cheque} (Acreditado)")

            # If no existing EGRESOS row was found (e.g. if hard-deleted when reverted), recreate it now:
            if not found_linked_egreso and (destino or linked_oc_ids):
                ws_e = wb['EGRESOS'] if 'EGRESOS' in wb.sheetnames else wb.create_sheet('EGRESOS')
                new_e_id = egreso_id if egreso_id else self._get_next_entity_id(ws_e, 'EGR')
                target_dest = destino if destino else "Proveedor"

                prov_oc = ""
                oc_detail = ""
                monto_oc = 0.0
                if 'ORDENES_COMPRA' in wb.sheetnames:
                    ws_oc = wb['ORDENES_COMPRA']
                    for r_oc in range(5, ws_oc.max_row + 1):
                        oc_id = str(ws_oc.cell(r_oc, 1).value or '').strip().upper()
                        if oc_id in linked_oc_ids:
                            prov_oc = str(ws_oc.cell(r_oc, 3).value or '').strip()
                            oc_detail = str(ws_oc.cell(r_oc, 7).value or '').strip()
                            monto_oc = self._to_float(ws_oc.cell(r_oc, 10).value or 0)
                            ws_oc.cell(r_oc, 14, new_e_id)

                final_prov = prov_oc if prov_oc else target_dest
                final_monto = monto_oc if monto_oc > 0 else monto_final
                oc_label = f" [ORDEN DE COMPRA {list(linked_oc_ids)[0]}]" if linked_oc_ids else ""
                nro_chq_str = f" N° {nro_cheque}" if nro_cheque else ""

                target_e_row = ws_e.max_row + 1
                row_data = {
                    1: new_e_id,
                    2: fecha,
                    3: fecha,
                    4: 'Combustible / Insumos',
                    6: final_prov,
                    12: f"Pago de Compra{oc_label} vía Cheque{nro_chq_str} Acreditado".strip(),
                    16: final_monto,
                    17: 'Pagado',
                    18: final_monto,
                    19: fecha,
                    20: f"Cheque{nro_chq_str} (Acreditado)",
                    21: cid,
                    24: f"Egreso restablecido al acreditar cheque {cid} en 2° intento.".strip()
                }
                for col_idx, val in row_data.items():
                    ws_e.cell(target_e_row, col_idx, val)

                ws_chq.cell(target_row, 14, new_e_id)

            # Record in INGRESOS sheet if this was a client third-party cheque cobro
            if cliente_emisor and not destino and not linked_oc_ids:
                ws_i = wb['INGRESOS']
                target_i_row = None
                for r in range(5, ws_i.max_row + 1):
                    if not ws_i.cell(r, 1).value and not ws_i.cell(r, 4).value:
                        target_i_row = r
                        break
                if not target_i_row:
                    target_i_row = ws_i.max_row + 1

                ingreso_id = self._get_next_entity_id(ws_i, 'ING')
                medio_cobro_lbl = "Efectivo" if metodo == 'efectivo' else ("Cheque Acreditado (2° Intento)" if metodo in ['acreditado', 'cobrado', 'acreditacion'] else "Transferencia Bancaria")

                row_data = {
                    1: ingreso_id,
                    2: fecha,
                    3: fecha,
                    4: cliente_emisor,
                    5: cuit_emisor,
                    6: concepto,
                    7: 'Regularización Cheque',
                    8: monto_final,
                    9: 0,
                    10: 0,
                    11: monto_final,
                    12: 'SI',
                    13: medio_cobro_lbl,
                    14: 'Cobrado',
                    15: monto_final,
                    16: f"Regularización de Cheque {cid}. {obs}".strip()
                }
                for col_idx, val in row_data.items():
                    ws_i.cell(target_i_row, col_idx, val)

            wb.save(self.excel_path)
            self._invalidate_cache()
            return {"status": "success", "id": cid, "estado": nuevo_st}

        elif metodo == 'nuevo_cheque':
            ws_chq.cell(target_row, 11, 'Regularizado - Sustituido')
            cur_obs = str(ws_chq.cell(target_row, 16).value or '').strip()
            ws_chq.cell(target_row, 16, f"{cur_obs} | Sustituido por nuevo cheque ({fecha})".strip(' |'))

            # Supabase First
            if self.supabase_service and self.supabase_service.is_connected():
                from sqlalchemy import text
                try:
                    with self.supabase_service.engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE cheques
                            SET estado = 'Regularizado - Sustituido',
                                observaciones = CASE 
                                    WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                    ELSE observaciones || ' | ' || :obs
                                END,
                                updated_at = NOW()
                            WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                        """), {"obs": f"Sustituido por nuevo cheque ({fecha})", "cid": str(cid).strip()})

                        new_cid_sup = self.supabase_service.get_next_id('cheques', 'CHQ', 'id_cheque')
                        conn.execute(text("""
                            INSERT INTO cheques (
                                id_cheque, fecha_ingreso, tipo, monto, cliente_emisor, cuit_emisor,
                                banco, nro_cheque, fecha_cobro, endosado_tenedor, estado,
                                observaciones
                            ) VALUES (
                                :id_cheque, CAST(:fecha_ingreso AS date), :tipo, :monto, :cliente_emisor, :cuit_emisor,
                                :banco, :nro_cheque, CAST(:fecha_cobro AS date), 'ECONCATIVO S.A.S.', 'Disponible',
                                :obs
                            )
                        """), {
                            "id_cheque": new_cid_sup,
                            "fecha_ingreso": fecha,
                            "tipo": payload.get('tipo_nuevo', 'Cheque Físico'),
                            "monto": monto_final,
                            "cliente_emisor": cliente_emisor,
                            "cuit_emisor": cuit_emisor,
                            "banco": payload.get('banco_nuevo', ''),
                            "nro_cheque": payload.get('nro_nuevo', ''),
                            "fecha_cobro": payload.get('vencimiento_nuevo', fecha),
                            "obs": f"Reemplazo de Cheque Rebotado {cid}. {obs}".strip()
                        })
                except Exception as e:
                    print(f"[DataManager] Error regularising with new cheque in Supabase: {e}")

            # Insert replacement cheque
            new_cid = self._get_next_cheque_id(ws_chq)
            target_chq_row = ws_chq.max_row + 1
            new_chq_data = {
                1: new_cid,
                2: fecha,
                3: payload.get('tipo_nuevo', 'Cheque Físico'),
                4: monto_final,
                5: cliente_emisor,
                6: cuit_emisor,
                7: payload.get('banco_nuevo', ''),
                8: payload.get('nro_nuevo', ''),
                9: payload.get('vencimiento_nuevo', ''),
                10: 'ECONCATIVO S.A.S.',
                11: 'Disponible',
                16: f"Reemplazo de Cheque Rebotado {cid}. {obs}".strip()
            }
            for col_idx, val in new_chq_data.items():
                ws_chq.cell(target_chq_row, col_idx, val)

            wb.save(self.excel_path)
            return {"status": "success", "id": cid, "estado": "Regularizado - Sustituido", "nuevo_cheque_id": new_cid}

        else:
            return {"status": "error", "message": f"Método de regularización no válido: {metodo}"}

    def representar_cheque(self, payload):
        """Sets cheque status to En Re-presentación."""
        cid = payload.get('id') if isinstance(payload, dict) else payload
        cid_clean = str(cid).strip()
        obs_msg = f"Re-presentado al banco ({datetime.now().strftime('%Y-%m-%d')})"

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE cheques
                        SET estado = 'En Re-presentación',
                            observaciones = CASE 
                                WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                ELSE observaciones || ' | ' || :obs
                            END,
                            updated_at = NOW()
                        WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                    """), {"obs": obs_msg, "cid": cid_clean})
            except Exception as e:
                print(f"[DataManager] Error representing cheque in Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_cheques_sheet(wb)
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip().lower() == cid_clean.lower():
                    target_row = r
                    break
            if target_row:
                ws.cell(target_row, 11, 'En Re-presentación')
                cur_obs = str(ws.cell(target_row, 16).value or '').strip()
                ws.cell(target_row, 16, f"{cur_obs} | {obs_msg}".strip(' |'))
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on representar_cheque: {e}")

        self._invalidate_cache()
        return {"status": "success", "id": cid_clean, "estado": "En Re-presentación"}

    def marcar_incobrable_cheque(self, payload):
        """Marks cheque as Anulado / Incobrable."""
        cid = payload.get('id') if isinstance(payload, dict) else payload
        cid_clean = str(cid).strip()
        obs_msg = f"Declarado Incobrable ({datetime.now().strftime('%Y-%m-%d')})"

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE cheques
                        SET estado = 'Anulado / Incobrable',
                            observaciones = CASE 
                                WHEN observaciones IS NULL OR observaciones = '' THEN :obs
                                ELSE observaciones || ' | ' || :obs
                            END,
                            updated_at = NOW()
                        WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                    """), {"obs": obs_msg, "cid": cid_clean})
            except Exception as e:
                print(f"[DataManager] Error marking cheque incobrable in Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws = self._ensure_cheques_sheet(wb)
            target_row = None
            for r in range(5, ws.max_row + 1):
                if str(ws.cell(r, 1).value or '').strip().lower() == cid_clean.lower():
                    target_row = r
                    break
            if target_row:
                ws.cell(target_row, 11, 'Anulado / Incobrable')
                cur_obs = str(ws.cell(target_row, 16).value or '').strip()
                ws.cell(target_row, 16, f"{cur_obs} | {obs_msg}".strip(' |'))
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on marcar_incobrable_cheque: {e}")

        self._invalidate_cache()
        return {"status": "success", "id": cid_clean, "estado": "Anulado / Incobrable"}

    def delete_cheque(self, cid):
        """Deletes a Cheque entry from Supabase and Excel, and its associated Egreso if present."""
        cid_clean = str(cid).strip()
        deleted = False
        egreso_id = None

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    row = conn.execute(
                        text("SELECT id_cheque, id_egreso FROM cheques WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))"),
                        {"cid": cid_clean}
                    ).fetchone()
                    if row:
                        deleted = True
                        if row[1]:
                            egreso_id = str(row[1]).strip()
                        conn.execute(
                            text("DELETE FROM cheques WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))"),
                            {"cid": cid_clean}
                        )
                        # Revert any linked Orden de Compra
                        conn.execute(
                            text("UPDATE ordenes_compra SET id_cheque = NULL, nro_cheque = NULL WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))"),
                            {"cid": cid_clean}
                        )
                        # If there was an associated auto-generated Egreso, delete it
                        if egreso_id and egreso_id.startswith('EGR-'):
                            conn.execute(
                                text("DELETE FROM egresos WHERE TRIM(LOWER(id_egreso)) = TRIM(LOWER(:eid))"),
                                {"eid": egreso_id}
                            )
            except Exception as e:
                print(f"[DataManager] Error deleting cheque {cid_clean} from Supabase: {e}")

        # 2. Excel Mirror / Backup
        try:
            wb = self.load_wb(data_only=False)
            if 'CHEQUES' in wb.sheetnames:
                ws = wb['CHEQUES']
                target_row = None
                for r in range(5, ws.max_row + 1):
                    val = str(ws.cell(r, 1).value or '').strip()
                    if val.lower() == cid_clean.lower():
                        target_row = r
                        if not egreso_id:
                            egreso_id = str(ws.cell(r, 14).value or '').strip()
                        break
                if target_row:
                    deleted = True
                    ws.delete_rows(target_row)

                if egreso_id and 'EGRESOS' in wb.sheetnames:
                    ws_e = wb['EGRESOS']
                    for r in range(5, ws_e.max_row + 1):
                        if str(ws_e.cell(r, 1).value or '').strip().lower() == egreso_id.lower():
                            ws_e.delete_rows(r)
                            break
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on delete_cheque: {e}")

        if not deleted:
            return {"status": "error", "message": f"Cheque {cid} no encontrado."}

        self._invalidate_cache()
        return {"status": "success", "id": cid_clean}

    def add_adelanto_viaje(self, viaje_id, fecha, monto, medio_pago, comprobante='', observaciones='', cuenta_tesoreria=''):
        """Registers an advance payment for a Viaje and immediately creates an entry in INGRESOS as COBRADO in Supabase."""
        import json
        viaje_id_clean = str(viaje_id).strip()
        monto_float = self._to_float(monto)
        fecha_str = fecha or datetime.now().strftime('%Y-%m-%d')

        medio_str = medio_pago or "Transferencia"
        if cuenta_tesoreria and cuenta_tesoreria.lower() not in medio_str.lower():
            medio_str = f"{medio_str} - {cuenta_tesoreria}"

        new_adelanto = {
            "fecha": fecha_str,
            "monto": monto_float,
            "medio_pago": medio_str,
            "cuenta_tesoreria": cuenta_tesoreria,
            "comprobante": comprobante,
            "observaciones": observaciones
        }

        # 1. Fetch Voyage & Client Info (Supabase First)
        v_cliente = 'Cliente'
        v_chofer = '-'
        v_unidad = '-'
        v_actividad = 'Viaje'
        cuit = ''

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    v_res = conn.execute(text("SELECT cliente, chofer, unidad, actividad, carga FROM viajes WHERE id_viaje = :vid"), {'vid': viaje_id_clean}).fetchone()
                    if v_res:
                        vm = dict(v_res._mapping)
                        v_cliente = vm.get('cliente') or 'Cliente'
                        v_chofer = vm.get('chofer') or '-'
                        v_unidad = vm.get('unidad') or '-'
                        v_actividad = vm.get('actividad') or 'Viaje'
                    
                    p_res = conn.execute(text("SELECT cuit FROM presupuestos WHERE id_viaje_asociado = :vid LIMIT 1"), {'vid': viaje_id_clean}).fetchone()
                    if p_res:
                        cuit = p_res[0] or ''
            except Exception as e:
                print(f"[add_adelanto_viaje Supabase fetch error] {e}")

        # 2. Get unique Ingreso ID and Recibo ID
        if self.supabase_service and self.supabase_service.is_connected():
            ingreso_id = self.supabase_service.get_next_id('ingresos', 'ING', 'id_ingreso')
            recibo_id = self.supabase_service.get_next_id('ingresos', 'REC', 'id_acuerdo')
        else:
            ingreso_id = f"ING-{datetime.now().strftime('%f')[:6]}"
            recibo_id = f"REC-{datetime.now().strftime('%f')[:6]}"

        obs_adelanto = f"Adelanto / Seña por Viaje {viaje_id_clean}. {observaciones}".strip()

        # 3. Direct insert to Supabase INGRESOS
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ingresos (
                            id_ingreso, fecha_emision, tipo_comprobante, punto_venta,
                            nro_factura_arca, cliente, cuit_cuil, actividad, chofer, unidad,
                            neto, iva_pct, iva, total, estado_cobro, importe_cobrado,
                            fecha_cobro, medio_cobro, saldo, id_acuerdo, observaciones,
                            created_at, updated_at
                        ) VALUES (
                            :id_ingreso, CAST(:fecha AS date), 'Adelanto / Seña', '0001',
                            :comprobante, :cliente, :cuit, :actividad, :chofer, :unidad,
                            :monto, 0, 0, :monto, 'COBRADO', :monto,
                            CAST(:fecha AS date), :medio, 0, :recibo_id, :obs,
                            NOW(), NOW()
                        )
                        ON CONFLICT (id_ingreso) DO UPDATE SET
                            total = EXCLUDED.total,
                            importe_cobrado = EXCLUDED.importe_cobrado,
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id_ingreso': ingreso_id,
                        'fecha': fecha_str,
                        'comprobante': comprobante or 'SEÑA-PREVIA',
                        'cliente': v_cliente,
                        'cuit': cuit or None,
                        'actividad': f"Seña / Adelanto - {v_actividad}",
                        'chofer': v_chofer,
                        'unidad': v_unidad,
                        'monto': monto_float,
                        'medio': medio_str,
                        'recibo_id': recibo_id,
                        'obs': obs_adelanto
                    })

                    # If cheque/echeq, insert to cheques table in Supabase
                    med_lower = str(medio_pago or '').lower()
                    if 'cheque' in med_lower or 'echeq' in med_lower or 'e-cheq' in med_lower:
                        chq_id = self.supabase_service.get_next_id('cheques', 'CHQ', 'id_cheque')
                        tipo_chq = 'E-Cheq' if ('echeq' in med_lower or 'e-cheq' in med_lower) else 'Cheque Físico'
                        conn.execute(text("""
                            INSERT INTO cheques (
                                id_cheque, fecha_ingreso, tipo, monto, cliente_emisor,
                                cuit_emisor, banco, nro_cheque, fecha_cobro, endosado_tenedor,
                                estado, id_ingreso_origen, observaciones, created_at, updated_at
                            ) VALUES (
                                :cid, CAST(:fecha AS date), :tipo, :monto, :cliente,
                                :cuit, '', :nro, CAST(:fecha AS date), 'ECONCATIVO S.A.S.',
                                'Disponible', :iid, :obs, NOW(), NOW()
                            ) ON CONFLICT (id_cheque) DO NOTHING;
                        """), {
                            'cid': chq_id,
                            'fecha': fecha_str,
                            'tipo': tipo_chq,
                            'monto': monto_float,
                            'cliente': v_cliente,
                            'cuit': cuit or None,
                            'nro': comprobante or '',
                            'iid': ingreso_id,
                            'obs': f"Seña / Adelanto por Viaje {viaje_id_clean}"
                        })
            except Exception as e:
                print(f"[add_adelanto_viaje Supabase Error] {e}")

        # 4. Mirror to Excel gracefully
        try:
            wb = self.load_wb(data_only=False)
            ws_v = wb['VIAJES']
            target_v_row = None
            for r in range(5, ws_v.max_row + 1):
                if str(ws_v.cell(r, 1).value or '').strip() == viaje_id_clean:
                    target_v_row = r
                    break
            if target_v_row:
                existing_json = str(ws_v.cell(target_v_row, 19).value or ws_v.cell(target_v_row, 15).value or '').strip()
                adelantos_list = []
                if existing_json and existing_json.startswith('['):
                    try: adelantos_list = json.loads(existing_json)
                    except Exception: pass
                adelantos_list.append(new_adelanto)
                ws_v.cell(target_v_row, 19, json.dumps(adelantos_list, ensure_ascii=False))

                if 'INGRESOS' in wb.sheetnames:
                    ws_i = wb['INGRESOS']
                    target_i_row = ws_i.max_row + 1
                    row_i_dict = {
                        1: ingreso_id,
                        2: fecha_str,
                        3: 'Adelanto / Seña',
                        4: '0001',
                        5: comprobante or 'SEÑA-PREVIA',
                        6: v_cliente,
                        7: cuit,
                        8: f"Seña / Adelanto - {v_actividad}",
                        9: v_chofer,
                        10: v_unidad,
                        13: monto_float,
                        14: 0,
                        15: 0,
                        16: monto_float,
                        17: 'COBRADO',
                        18: monto_float,
                        19: fecha_str,
                        20: medio_str,
                        21: 0,
                        22: recibo_id,
                        28: obs_adelanto
                    }
                    for col_idx, col_val in row_i_dict.items():
                        ws_i.cell(target_i_row, col_idx, col_val)

                wb.save(self.excel_path)
        except Exception as excel_err:
            print(f"[add_adelanto_viaje Excel mirror warning] {excel_err}")

        return {"status": "success", "viaje_id": viaje_id_clean, "ingreso_id": ingreso_id, "adelanto": new_adelanto}

    def add_adicional_viaje(self, viaje_id, concepto, monto):
        """Adds an additional concept/cost to a Viaje before it is finalized."""
        import json
        viaje_id_clean = str(viaje_id).strip()
        monto_float = self._to_float(monto)
        new_adicional = {
            "concepto": concepto or "Hora Extra / Adicional",
            "monto": monto_float,
            "fecha": datetime.now().strftime('%Y-%m-%d')
        }
        add_note = f"Extra: {new_adicional['concepto']} (${monto_float:,.2f})"

        # 1. Direct update to Supabase
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE viajes SET
                            valor_servicio = COALESCE(valor_servicio, 0) + :extra_monto,
                            observaciones = CASE 
                                WHEN observaciones IS NULL OR observaciones = '' THEN :nota
                                WHEN observaciones NOT LIKE :nota_like THEN observaciones || ' | ' || :nota
                                ELSE observaciones
                            END,
                            updated_at = NOW()
                        WHERE id_viaje = :vid;
                    """), {
                        'vid': viaje_id_clean,
                        'extra_monto': monto_float,
                        'nota': add_note,
                        'nota_like': f"%{add_note}%"
                    })
            except Exception as e:
                print(f"[add_adicional_viaje Supabase Error] {e}")

        # 2. Mirror to Excel
        try:
            wb = self.load_wb(data_only=False)
            ws_v = wb['VIAJES']
            target_v_row = None
            for r in range(5, ws_v.max_row + 1):
                if str(ws_v.cell(r, 1).value or '').strip() == viaje_id_clean:
                    target_v_row = r
                    break
            if target_v_row:
                existing_json = str(ws_v.cell(target_v_row, 18).value or '').strip()
                adicionales_list = []
                if existing_json and existing_json.startswith('['):
                    try: adicionales_list = json.loads(existing_json)
                    except Exception: pass
                adicionales_list.append(new_adicional)
                ws_v.cell(target_v_row, 18, json.dumps(adicionales_list, ensure_ascii=False))

                tot_adicionales = sum(float(a.get('monto', 0)) for a in adicionales_list)
                base_val = self._to_float(ws_v.cell(target_v_row, 20).value)
                ws_v.cell(target_v_row, 20, max(base_val, tot_adicionales))

                cur_obs = str(ws_v.cell(target_v_row, 23).value or '').strip()
                if add_note not in cur_obs:
                    ws_v.cell(target_v_row, 23, f"{cur_obs} | {add_note}".strip(' |'))

                wb.save(self.excel_path)
        except Exception as excel_err:
            print(f"[add_adicional_viaje Excel mirror warning] {excel_err}")

        return {"status": "success", "viaje_id": viaje_id_clean, "adicional": new_adicional}

    def get_viaje_facturacion_summary(self, viaje_id):
        """Returns complete financial & operational summary of a Viaje for billing (Base + Adicionales - Adelantos = Saldo) Supabase-First."""
        import json
        import re
        viaje_id_clean = str(viaje_id).strip()
        v_data = None
        assoc_pdata = {}
        items_pdata = []
        cuit = ''
        adicionales = []
        adelantos = []

        # 1. Supabase First Lookup
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    # Viaje row
                    v_row = conn.execute(text("SELECT * FROM viajes WHERE id_viaje = :vid"), {'vid': viaje_id_clean}).fetchone()
                    if v_row:
                        vr = dict(v_row._mapping)
                        v_data = {
                            'id': viaje_id_clean,
                            'fecha': str(vr.get('fecha_salida') or datetime.now().strftime('%Y-%m-%d')),
                            'chofer': vr.get('chofer') or '-',
                            'unidad': vr.get('unidad') or '-',
                            'origen': vr.get('origen') or '',
                            'destino': vr.get('destino') or '',
                            'cliente': vr.get('cliente') or 'Cliente',
                            'tipo_op': vr.get('actividad') or 'Viaje',
                            'carga': vr.get('carga') or '',
                            'remito': vr.get('nro_remito') or '',
                            'cpe': vr.get('cpe') or '',
                            'km_hs': str(vr.get('km_recorridos') or ''),
                            'valor_servicio': float(vr.get('valor_servicio') or 0),
                            'observaciones': vr.get('observaciones') or ''
                        }

                    # Associated Budget row
                    p_row = conn.execute(text("""
                        SELECT * FROM presupuestos 
                        WHERE id_viaje_asociado = :vid
                        ORDER BY id_presupuesto DESC LIMIT 1
                    """), {'vid': viaje_id_clean}).fetchone()
                    if not p_row and v_data and v_data.get('carga'):
                        m = re.search(r'(PRE-\d+)', str(v_data.get('carga')))
                        if m:
                            p_row = conn.execute(text("SELECT * FROM presupuestos WHERE id_presupuesto = :pid"), {'pid': m.group(1)}).fetchone()

                    if p_row:
                        pr = dict(p_row._mapping)
                        cuit = str(pr.get('cuit') or '')
                        raw_items = str(pr.get('items_json') or '')
                        if raw_items and raw_items.startswith('['):
                            try: items_pdata = json.loads(raw_items)
                            except Exception: pass
                        assoc_pdata = {
                            'id_presupuesto': pr.get('id_presupuesto'),
                            'cliente': pr.get('cliente'),
                            'cuit': cuit,
                            'total_neto': float(pr.get('total') or 0),
                            'iva_pct': float(pr.get('iva_pct') or 21.0),
                            'detalle': pr.get('detalle_concepto')
                        }

                    # Advances / Adelantos from Supabase ingresos table
                    adv_rows = conn.execute(text("""
                        SELECT id_ingreso, fecha_emision, total, medio_cobro, observaciones
                        FROM ingresos
                        WHERE observaciones ILIKE :obs_pattern
                          AND (tipo_comprobante ILIKE '%Adelanto%' OR tipo_comprobante ILIKE '%Seña%')
                    """), {'obs_pattern': f'%{viaje_id_clean}%'}).fetchall()
                    for adv in adv_rows:
                        adv_d = dict(adv._mapping)
                        adelantos.append({
                            'id': adv_d.get('id_ingreso'),
                            'fecha': str(adv_d.get('fecha_emision') or ''),
                            'monto': float(adv_d.get('total') or 0),
                            'medio_pago': adv_d.get('medio_cobro') or '',
                            'observaciones': adv_d.get('observaciones') or ''
                        })
            except Exception as e:
                print(f"[get_viaje_facturacion_summary Supabase error] {e}")

        # 2. Fallback to Excel if not found in Supabase
        if not v_data:
            try:
                wb = self.load_wb(data_only=True)
                ws_v = wb['VIAJES']
                for r in range(5, ws_v.max_row + 1):
                    if str(ws_v.cell(r, 1).value or '').strip() == viaje_id_clean:
                        v_data = {
                            'id': viaje_id_clean,
                            'fecha': ws_v.cell(r, 2).value,
                            'chofer': ws_v.cell(r, 4).value or '-',
                            'unidad': ws_v.cell(r, 5).value or '-',
                            'origen': ws_v.cell(r, 6).value or '',
                            'destino': ws_v.cell(r, 7).value or '',
                            'cliente': ws_v.cell(r, 8).value or 'Cliente',
                            'tipo_op': ws_v.cell(r, 9).value or 'Viaje',
                            'carga': ws_v.cell(r, 10).value or '',
                            'remito': ws_v.cell(r, 11).value or '',
                            'cpe': ws_v.cell(r, 12).value or '',
                            'km_hs': ws_v.cell(r, 15).value or '',
                            'adicionales_raw': ws_v.cell(r, 18).value,
                            'adelantos_raw': ws_v.cell(r, 19).value,
                            'valor_servicio': ws_v.cell(r, 20).value
                        }
                        break

                if not v_data:
                    return None

                if v_data.get('adicionales_raw') and str(v_data['adicionales_raw']).startswith('['):
                    try: adicionales = json.loads(v_data['adicionales_raw'])
                    except Exception: pass

                if not adelantos and v_data.get('adelantos_raw') and str(v_data['adelantos_raw']).startswith('['):
                    try: adelantos = json.loads(v_data['adelantos_raw'])
                    except Exception: pass

                if not assoc_pdata and 'PRESUPUESTOS' in wb.sheetnames:
                    ws_p = wb['PRESUPUESTOS']
                    for rp in range(5, ws_p.max_row + 1):
                        if str(ws_p.cell(rp, 12).value or '').strip() == viaje_id_clean:
                            cuit = str(ws_p.cell(rp, 4).value or '')
                            tot = self._to_float(ws_p.cell(rp, 7).value)
                            iva_pct = self._to_float(ws_p.cell(rp, 8).value, 21)
                            raw_items = str(ws_p.cell(rp, 14).value or ws_p.cell(rp, 12).value or '')
                            if raw_items and raw_items.startswith('['):
                                try: items_pdata = json.loads(raw_items)
                                except Exception: pass
                            assoc_pdata = {
                                'id_presupuesto': ws_p.cell(rp, 1).value,
                                'cliente': ws_p.cell(rp, 3).value,
                                'cuit': cuit,
                                'total_neto': tot,
                                'iva_pct': iva_pct,
                                'detalle': ws_p.cell(rp, 6).value
                            }
                            break
            except Exception as e:
                print(f"[get_viaje_facturacion_summary Excel fallback error] {e}")

        if not v_data:
            return None

        # 3. Calculate Financial Summary
        base_neto = assoc_pdata.get('total_neto') or self._to_float(v_data.get('valor_servicio'))
        tot_adicionales = sum(float(a.get('monto', 0)) for a in adicionales)
        subtotal_neto = base_neto + tot_adicionales
        iva_pct = assoc_pdata.get('iva_pct', 21.0)
        iva_amt = subtotal_neto * (iva_pct / 100.0)
        total_con_iva = subtotal_neto + iva_amt
        
        tot_adelantos = sum(float(ad.get('monto', 0)) for ad in adelantos)
        saldo_neto_facturar = max(0.0, total_con_iva - tot_adelantos)

        return {
            'viaje_id': viaje_id_clean,
            'fecha': v_data.get('fecha', datetime.now().strftime('%Y-%m-%d')),
            'cliente': v_data.get('cliente'),
            'cuit': cuit or assoc_pdata.get('cuit', '-'),
            'chofer': v_data.get('chofer'),
            'unidad': v_data.get('unidad'),
            'origen': v_data.get('origen'),
            'destino': v_data.get('destino'),
            'carga': v_data.get('carga'),
            'tipo_op': v_data.get('tipo_op'),
            'id_presupuesto': assoc_pdata.get('id_presupuesto', '-'),
            'detalle_presupuesto': assoc_pdata.get('detalle', '-'),
            'items_presupuesto': items_pdata,
            'base_neto': base_neto,
            'adicionales': adicionales,
            'tot_adicionales': tot_adicionales,
            'subtotal_neto': subtotal_neto,
            'iva_pct': iva_pct,
            'iva_amt': iva_amt,
            'total_con_iva': total_con_iva,
            'adelantos': adelantos,
            'tot_adelantos': tot_adelantos,
            'saldo_neto_facturar': saldo_neto_facturar
        }

    # CUENTAS CORRIENTES DE CLIENTES MODULE
    def _ensure_cuentas_corrientes_sheet(self, wb):
        if 'CUENTAS_CORRIENTES' not in wb.sheetnames:
            ws = wb.create_sheet('CUENTAS_CORRIENTES')
            ws.cell(1, 1, 'ECONCATIVO - LIBRO MAYOR DE CUENTAS CORRIENTES DE CLIENTES')
            ws.cell(2, 1, 'Generado automáticamente por Antigravity Control System')
            headers = [
                'ID movimiento',
                'Fecha',
                'Fecha vencimiento',
                'Cliente',
                'CUIT',
                'Tipo comprobante',
                'Referencia ID',
                'Concepto',
                'Debe',
                'Haber',
                'Observaciones'
            ]
            for col_idx, h in enumerate(headers, 1):
                ws.cell(4, col_idx, h)
            return ws
        return wb['CUENTAS_CORRIENTES']

    def get_cuenta_corriente_cliente(self, cliente_nombre, fecha_desde=None, fecha_hasta=None):
        """Returns chronological statement of account (Libro Mayor) for a specific client (Supabase First)."""
        wb = None
        try:
            wb = self.load_wb(data_only=True)
        except Exception:
            pass

        _, raw_rows = self.get_sheet_data('CUENTAS_CORRIENTES')
        if not raw_rows and wb:
            ws_cc = self._ensure_cuentas_corrientes_sheet(wb)
            _, raw_rows = self._read_sheet_rows(ws_cc)

        client_norm = str(cliente_nombre or '').strip().lower()

        # Build list of all raw movements for this client
        all_movs = []
        for r in raw_rows:
            c_name = self._get_row_prop(r, ['Cliente', 'Nombre'])
            if str(c_name or '').strip().lower() == client_norm:
                all_movs.append({
                    'id': self._get_row_prop(r, ['ID movimiento', 'ID']),
                    'fecha': self._get_row_prop(r, ['Fecha']),
                    'vencimiento': self._get_row_prop(r, ['Fecha vencimiento', 'Vencimiento']) or self._get_row_prop(r, ['Fecha']),
                    'cliente': c_name,
                    'cuit': self._get_row_prop(r, ['CUIT']),
                    'tipo': self._get_row_prop(r, ['Tipo comprobante', 'Tipo']),
                    'ref_id': self._get_row_prop(r, ['Referencia ID', 'Referencia']),
                    'concepto': self._get_row_prop(r, ['Concepto']),
                    'debe': self._to_float(self._get_row_prop(r, ['Debe'])),
                    'haber': self._to_float(self._get_row_prop(r, ['Haber'])),
                    'observaciones': self._get_row_prop(r, ['Observaciones'])
                })

        # Also pull billed trips and invoices from INGRESOS if not explicitly logged in CUENTAS_CORRIENTES
        _, ing_rows = self.get_sheet_data('INGRESOS')
        if not ing_rows and wb and 'INGRESOS' in wb.sheetnames:
            _, ing_rows = self._read_sheet_rows(wb['INGRESOS'])
            logged_refs = set(m['ref_id'] for m in all_movs if m['ref_id'])
            for r in ing_rows:
                tipo_comp = str(self._get_row_prop(r, ['Tipo comprobante', 'Tipo']) or '').strip()
                
                # Skip 'Entrega CC' rows (which are cash inflows generated by CC payments)
                if tipo_comp == 'Entrega CC':
                    continue

                c_name = self._get_row_prop(r, ['Cliente', 'Razó­n social / Nombre', 'Nombre'])
                if str(c_name or '').strip().lower() == client_norm:
                    ing_id = self._get_row_prop(r, ['ID ingreso', 'ID'])
                    if ing_id and ing_id not in logged_refs:
                        f_ing = self._get_row_prop(r, ['Fecha emisión', 'Fecha emisió­n', 'Fecha cobro / depósito', 'Fecha cobro', 'Fecha'])
                        con = self._get_row_prop(r, ['Concepto / Descripción del servicio', 'Actividad', 'Concepto'])
                        est_cobro = str(self._get_row_prop(r, ['Estado cobro', 'Estado'])).lower()
                        ref_cc = str(self._get_row_prop(r, ['ID acuerdo', 'Observaciones']) or '').strip()
                        
                        m_tot = self._to_float(self._get_row_prop(r, ['Total', 'Importe total con IVA', 'Total con IVA', 'Importe total', 'Total con IVA ($)', 'Monto Total']))
                        if m_tot <= 0:
                            m_neto = self._to_float(self._get_row_prop(r, ['Neto', 'Importe neto', 'Neto gravado']))
                            m_iva = self._to_float(self._get_row_prop(r, ['IVA', 'Importe IVA']))
                            iva_pct = self._to_float(self._get_row_prop(r, ['IVA %', 'Porcentaje IVA (%)', 'Porcentaje IVA']), 21)
                            if m_iva <= 0 and m_neto > 0:
                                m_iva = m_neto * (iva_pct / 100.0)
                            m_fact = m_neto + m_iva
                        else:
                            m_fact = m_tot

                        m_cob = self._to_float(self._get_row_prop(r, ['Importe cobrado', 'Monto']))
                        is_adelanto = self._is_adelanto_entry(r)
                        
                        # Invoice charge (DEBE) - ONLY if NOT an advance payment receipt!
                        if m_fact > 0 and not is_adelanto:
                            all_movs.append({
                                'id': f"CC-FACT-{ing_id}",
                                'fecha': f_ing,
                                'vencimiento': f_ing,
                                'cliente': cliente_nombre,
                                'cuit': self._get_row_prop(r, ['CUIT / CUIL', 'CUIT']),
                                'tipo': 'Facturación / Servicio',
                                'ref_id': ing_id,
                                'concepto': f"Factura {ing_id} - {con}".strip(' -'),
                                'debe': m_fact,
                                'haber': 0.0,
                                'observaciones': ''
                            })

                        # Payment credit (HABER) ONLY for direct cash/bank cobros (deducting Saldo a Favor applied)
                        medio_str = str(self._get_row_prop(r, ['Medio cobro', 'Medio de cobro', 'Medio', 'Medio pago', 'Medio de Pago']) or '').strip()
                        medio_lower = medio_str.lower()
                        
                        sf_amt = 0.0
                        if 'saldo a favor' in medio_lower or 'saldo' in medio_lower:
                            sf_match = re.search(r'Saldo a Favor C\/C:\s*\$?([\d\.,]+)', medio_str, re.IGNORECASE)
                            if sf_match:
                                raw_sf = sf_match.group(1).strip()
                                if ',' in raw_sf and '.' in raw_sf:
                                    if raw_sf.rfind('.') > raw_sf.rfind(','):
                                        raw_sf = raw_sf.replace(',', '')
                                    else:
                                        raw_sf = raw_sf.replace('.', '').replace(',', '.')
                                elif ',' in raw_sf:
                                    raw_sf = raw_sf.replace(',', '.')
                                try:
                                    sf_amt = float(raw_sf)
                                except Exception:
                                    sf_amt = 0.0

                        real_cash_cobro = max(0.0, m_cob - sf_amt)

                        if ('cobrado' in est_cobro or 'parcial' in est_cobro) and real_cash_cobro > 0 and not (ref_cc.startswith('CC-') or 'Cuentas Corrientes' in ref_cc):
                            if sf_amt > 0:
                                cash_part_str = re.sub(r'\s*\+\s*Saldo a Favor C\/C:\s*\$?[\d\.,]+', '', medio_str, flags=re.IGNORECASE).strip()
                                sf_formatted = f"${sf_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                pago_tipo = f"Pago Parcial / {cash_part_str}" if 'parcial' in est_cobro else f"Pago / {cash_part_str}"
                                pago_concepto = f"Cobro Parcial de Factura {ing_id} vía {cash_part_str} (+ {sf_formatted} imputados de Saldo a Favor preexistente)" if 'parcial' in est_cobro else f"Cobro de Factura {ing_id} vía {cash_part_str} (+ {sf_formatted} imputados de Saldo a Favor preexistente)"
                            else:
                                pago_tipo = f"Seña / Adelanto ({medio_str})" if is_adelanto else (f"Pago Parcial / {medio_str}" if 'parcial' in est_cobro else f"Pago / {medio_str}")
                                pago_concepto = f"Seña / Adelanto cobrado vía {medio_str}" if is_adelanto else (f"Cobro Parcial de Factura {ing_id} vía {medio_str}" if 'parcial' in est_cobro else f"Cobro de Factura {ing_id} vía {medio_str}")
                            
                            all_movs.append({
                                'id': f"CC-PAGO-{ing_id}",
                                'fecha': f_ing,
                                'vencimiento': f_ing,
                                'cliente': cliente_nombre,
                                'cuit': self._get_row_prop(r, ['CUIT / CUIL', 'CUIT']),
                                'tipo': pago_tipo,
                                'ref_id': ing_id,
                                'concepto': pago_concepto,
                                'debe': 0.0,
                                'haber': real_cash_cobro,
                                'observaciones': ''
                            })

        # Sort movements by date
        all_movs.sort(key=lambda x: str(x.get('fecha') or ''))

        # Calculate initial balance (prior to fecha_desde) and period movements
        saldo_anterior = 0.0
        movimientos_periodo = []
        
        for m in all_movs:
            f = str(m.get('fecha') or '')
            if fecha_desde and f < fecha_desde:
                saldo_anterior += (m['debe'] - m['haber'])
            elif fecha_hasta and f > fecha_hasta:
                continue
            else:
                movimientos_periodo.append(m)

        # Calculate running balance for filtered period
        running_balance = saldo_anterior
        total_debe = 0.0
        total_haber = 0.0

        for m in movimientos_periodo:
            total_debe += m['debe']
            total_haber += m['haber']
            running_balance += (m['debe'] - m['haber'])
            m['saldo_acumulado'] = running_balance

        saldo_final = running_balance
        if abs(saldo_final) < 0.01:
            estado_saldo = "AL DÍA"
        elif saldo_final > 0:
            estado_saldo = "SALDO DEUDOR"
        else:
            estado_saldo = "SALDO ACREEDOR"

        # Resolve client CUIT/CUIL (Supabase First, then CLIENTES sheet, then movements, then INGRESOS)
        client_cuit = None
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    res_c = conn.execute(text("""
                        SELECT cuit_cuil FROM clientes 
                        WHERE LOWER(TRIM(razon_social)) = :cname
                        LIMIT 1
                    """), {"cname": client_norm}).fetchone()
                    if res_c and res_c[0] and str(res_c[0]).strip().lower() not in ['none', 'null', '-', '']:
                        client_cuit = str(res_c[0]).strip()
                    else:
                        res_c = conn.execute(text("""
                            SELECT cuit_cuil FROM clientes 
                            WHERE LOWER(TRIM(razon_social)) LIKE :cname
                            LIMIT 1
                        """), {"cname": f"%{client_norm}%"}).fetchone()
                        if res_c and res_c[0] and str(res_c[0]).strip().lower() not in ['none', 'null', '-', '']:
                            client_cuit = str(res_c[0]).strip()
            except Exception as e:
                print(f"[get_cuenta_corriente_cliente] Warning fetching CUIT from Supabase: {e}")

        if not client_cuit:
            try:
                _, c_rows = self.get_sheet_data('CLIENTES')
                for cr in c_rows:
                    cname = str(self._get_row_prop(cr, ['razon_social', 'Razon social / Nombre', 'Cliente', 'Nombre']) or '').strip().lower()
                    if cname == client_norm or (cname and (client_norm in cname or cname in client_norm)):
                        cval = self._get_row_prop(cr, ['cuit_cuil', 'CUIT/CUIL', 'CUIT', 'cuit'])
                        if cval and str(cval).strip().lower() not in ['none', 'null', '-', '']:
                            client_cuit = str(cval).strip()
                            break
            except Exception:
                pass

        if not client_cuit:
            for m in all_movs:
                mc = str(m.get('cuit') or '').strip()
                if mc and mc.lower() not in ['none', 'null', '-', '']:
                    client_cuit = mc
                    break

        if not client_cuit:
            try:
                _, ing_rows_all = self.get_sheet_data('INGRESOS')
                for ir in ing_rows_all:
                    ir_name = str(self._get_row_prop(ir, ['Cliente', 'Razon social / Nombre', 'Nombre']) or '').strip().lower()
                    if ir_name == client_norm or (ir_name and (client_norm in ir_name or ir_name in client_norm)):
                        cval = self._get_row_prop(ir, ['CUIT / CUIL', 'cuit_cuil', 'CUIT', 'cuit'])
                        if cval and str(cval).strip().lower() not in ['none', 'null', '-', '']:
                            client_cuit = str(cval).strip()
                            break
            except Exception:
                pass

        if not client_cuit:
            try:
                _, pres_rows = self.get_sheet_data('PRESUPUESTOS')
                for pr in pres_rows:
                    pr_name = str(self._get_row_prop(pr, ['Cliente', 'Razon social / Nombre']) or '').strip().lower()
                    if pr_name == client_norm or (pr_name and (client_norm in pr_name or pr_name in client_norm)):
                        cval = self._get_row_prop(pr, ['CUIT', 'cuit', 'CUIT / CUIL'])
                        if cval and str(cval).strip().lower() not in ['none', 'null', '-', '']:
                            client_cuit = str(cval).strip()
                            break
            except Exception:
                pass

        # Format CUIT as XX-XXXXXXXX-X if 11 digits
        clean_digits = re.sub(r'\D', '', client_cuit) if client_cuit else ''
        if len(clean_digits) == 11:
            formatted_cuit = f"{clean_digits[:2]}-{clean_digits[2:10]}-{clean_digits[10]}"
        elif client_cuit and client_cuit.lower() not in ['none', 'null', '']:
            formatted_cuit = client_cuit
        else:
            formatted_cuit = '-'

        return {
            'status': 'success',
            'cliente': cliente_nombre,
            'cuit': formatted_cuit,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'saldo_anterior': saldo_anterior,
            'movimientos': movimientos_periodo,
            'total_debe': total_debe,
            'total_haber': total_haber,
            'saldo_final': saldo_final,
            'estado_saldo': estado_saldo
        }

    def get_unpaid_invoices_client(self, cliente_nombre):
        """Returns list of pending/unpaid invoices for a client to allow direct payment imputation (Supabase First)."""
        wb = None
        try:
            wb = self.load_wb(data_only=True)
        except Exception:
            pass
        
        client_norm = str(cliente_nombre or '').strip().lower()
        _, ing_rows = self.get_sheet_data('INGRESOS')
        if not ing_rows and wb and 'INGRESOS' in wb.sheetnames:
            _, ing_rows = self._read_sheet_rows(wb['INGRESOS'])
        
        unpaid = []
        for r in ing_rows:
            c_name = self._get_row_prop(r, ['Cliente', 'Razó­n social / Nombre', 'Nombre'])
            if str(c_name or '').strip().lower() == client_norm:
                est = str(self._get_row_prop(r, ['Estado cobro', 'Estado']) or '').strip().upper()
                tipo_comp = str(self._get_row_prop(r, ['Tipo comprobante', 'Tipo']) or '').strip()
                if tipo_comp == 'Entrega CC':
                    continue
                if est in ['PENDIENTE', 'PENDIENTE ARCA', 'COBRADO PARCIAL', 'POR COBRAR', 'FACTURADO / SERVICIO']:
                    ing_id = self._get_row_prop(r, ['ID ingreso', 'ID'])
                    nro_fact = self._get_row_prop(r, ['N° factura ARCA', 'Factura']) or ing_id
                    f_ing = self._get_row_prop(r, ['Fecha emisión', 'Fecha'])
                    con = self._get_row_prop(r, ['Concepto / Descripción del servicio', 'Actividad', 'Concepto'])
                    tot = self._to_float(self._get_row_prop(r, ['Total', 'Importe total']))
                    cob = self._to_float(self._get_row_prop(r, ['Importe cobrado']))
                    saldo = self._to_float(self._get_row_prop(r, ['Saldo']))
                    if saldo <= 0 and tot > 0:
                        saldo = max(0.0, tot - cob)
                    
                    if tot > 0 and (est != 'COBRADO' or saldo > 0):
                        unpaid.append({
                            'id': ing_id,
                            'nro_factura': nro_fact,
                            'fecha': f_ing,
                            'concepto': con,
                            'total': tot,
                            'cobrado': cob,
                            'saldo_pendiente': saldo if saldo > 0 else tot,
                            'label': f"Factura {nro_fact} ({con}) - Pendiente: ${saldo if saldo > 0 else tot:,.2f}"
                        })
        return sorted(unpaid, key=lambda x: str(x.get('fecha') or ''))

    def add_pago_cuenta_corriente(self, payload):
        """Registers a payment or credit note in Cuenta Corriente, inserts cheque if applicable, and imputes to target invoice in Supabase and Excel."""
        cliente = payload.get('cliente')
        if not cliente:
            return {"status": "error", "message": "Cliente es requerido."}

        metodo_raw = str(payload.get('metodo') or '').lower().strip()
        fecha = payload.get('fecha') or datetime.now().strftime('%Y-%m-%d')
        vencimiento = payload.get('vencimiento') or fecha
        monto = self._to_float(payload.get('monto'))
        concepto = payload.get('concepto') or f"Entrega a cuenta ({metodo_raw.capitalize()})"
        cuit = payload.get('cuit', '')
        imputar_id = payload.get('imputar_a_ingreso_id') or payload.get('ingreso_id') or ''
        obs = payload.get('observaciones', '')

        # Auto-lookup CUIT from master lists if omitted
        if not cuit:
            try:
                masters = self.get_master_lists()
                cli_info = masters.get('clientes_dict', {}).get(cliente, {})
                cuit = cli_info.get('cuit', '')
            except Exception:
                cuit = ''

        tipo_lbl = f"Entrega / {metodo_raw.replace('_', ' ').title()}"
        ref_id = ""
        is_cheque = any(k in metodo_raw for k in ['cheque', 'echeq', 'e_cheq', 'e-cheq', 'chq'])
        chq_id = None
        tipo_chq = 'E-Cheq' if ('echeq' in metodo_raw or 'e_cheq' in metodo_raw or 'e-cheq' in metodo_raw) else 'Cheque Físico'
        banco = payload.get('banco') or 'A completar'
        nro_chq = payload.get('nro_cheque') or payload.get('nro_chq') or ''

        # 1. Supabase Master Execution
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                cc_id = self.supabase_service.get_next_id('cuentas_corrientes', 'CC', 'id_movimiento')
                new_ing_id = self.supabase_service.get_next_id('ingresos', 'ING', 'id_ingreso')

                with self.supabase_service.engine.begin() as conn:
                    if is_cheque:
                        # Check duplicate
                        if nro_chq and banco:
                            dup = conn.execute(text("SELECT id_cheque FROM cheques WHERE nro_cheque = :nro AND LOWER(banco) = LOWER(:banco)"), {
                                'nro': str(nro_chq).strip(),
                                'banco': str(banco).strip()
                            }).fetchone()
                            if dup:
                                return {"status": "error", "message": f"El cheque N° {nro_chq} ({banco}) ya se encuentra registrado en el sistema."}

                        chq_id = self.supabase_service.get_next_id('cheques', 'CHQ', 'id_cheque')
                        ref_id = chq_id
                        tipo_lbl = f"Entrega {tipo_chq} ({nro_chq or chq_id})"

                        conn.execute(text("""
                            INSERT INTO cheques (
                                id_cheque, fecha_ingreso, tipo, monto, cliente_emisor, cuit_emisor, banco,
                                nro_cheque, fecha_cobro, endosado_tenedor, estado, id_ingreso_origen, observaciones, created_at, updated_at
                            ) VALUES (
                                :cid, CAST(:fecha AS date), :tipo_chq, :monto, :cliente, :cuit, :banco,
                                :nro_chq, CAST(:vencimiento AS date), 'ECONCATIVO S.A.S.', 'Disponible', :cc_id, :obs_chq, NOW(), NOW()
                            )
                        """), {
                            'cid': chq_id,
                            'fecha': fecha,
                            'tipo_chq': tipo_chq,
                            'monto': monto,
                            'cliente': cliente,
                            'cuit': cuit,
                            'banco': banco,
                            'nro_chq': nro_chq,
                            'vencimiento': vencimiento,
                            'cc_id': cc_id,
                            'obs_chq': f"Ingresado como entrega a cuenta de {cliente}. {obs}".strip()
                        })

                    # Insert Cuentas Corrientes
                    conn.execute(text("""
                        INSERT INTO cuentas_corrientes (
                            id_movimiento, fecha, fecha_vencimiento, cliente, cuit,
                            tipo_comprobante, referencia_id, concepto, debe, haber, observaciones, created_at
                        ) VALUES (
                            :cc_id, CAST(:fecha AS date), CAST(:vencimiento AS date), :cliente, :cuit,
                            :tipo_lbl, :ref_id, :concepto, 0.0, :monto, :obs, NOW()
                        )
                    """), {
                        'cc_id': cc_id,
                        'fecha': fecha,
                        'vencimiento': vencimiento,
                        'cliente': cliente,
                        'cuit': cuit,
                        'tipo_lbl': tipo_lbl,
                        'ref_id': ref_id,
                        'concepto': concepto,
                        'monto': monto,
                        'obs': obs
                    })

                    # Insert Ingreso
                    medio_clean = metodo_raw.replace('_', ' ').title()
                    cuenta_tesoreria = payload.get('cuenta_tesoreria') or payload.get('cuenta_destino') or ''
                    if cuenta_tesoreria:
                        medio_clean = f"{medio_clean} - {cuenta_tesoreria}" if cuenta_tesoreria.lower() not in medio_clean.lower() else cuenta_tesoreria

                    conn.execute(text("""
                        INSERT INTO ingresos (
                            id_ingreso, fecha_emision, tipo_comprobante, nro_factura_arca, cliente, cuit_cuil,
                            actividad, neto, iva_pct, iva, total, estado_cobro, importe_cobrado,
                            fecha_cobro, medio_cobro, saldo, id_acuerdo, observaciones, created_at, updated_at
                        ) VALUES (
                            :iid, CAST(:fecha AS date), 'Entrega CC', :cc_id, :cliente, :cuit,
                            :concepto, :monto, 0, 0, :monto, 'COBRADO', :monto,
                            CAST(:fecha AS date), :medio_clean, 0, :cc_id, :obs_ing, NOW(), NOW()
                        )
                    """), {
                        'iid': new_ing_id,
                        'fecha': fecha,
                        'cc_id': cc_id,
                        'cliente': cliente,
                        'cuit': cuit,
                        'concepto': concepto,
                        'monto': monto,
                        'medio_clean': medio_clean,
                        'obs_ing': f"Entrega a cuenta Cuentas Corrientes ({cc_id}). {obs}".strip()
                    })

                    # Handle invoice imputation in Supabase
                    if imputar_id:
                        if imputar_id == 'auto_fifo':
                            unpaid_rows = conn.execute(text("""
                                SELECT id_ingreso, total, importe_cobrado FROM ingresos 
                                WHERE LOWER(cliente) = LOWER(:cli) AND (estado_cobro != 'COBRADO' OR estado_cobro IS NULL)
                                ORDER BY fecha_emision ASC, id_ingreso ASC
                            """), {'cli': cliente}).fetchall()
                            rem_monto = monto
                            for u_row in unpaid_rows:
                                if rem_monto <= 0: break
                                u_id = str(u_row[0])
                                tot_val = float(u_row[1] or 0.0)
                                prev_cob_val = float(u_row[2] or 0.0)
                                pend_val = max(0.0, tot_val - prev_cob_val)
                                apply_amt = min(rem_monto, pend_val if pend_val > 0 else tot_val)
                                new_cob = prev_cob_val + apply_amt
                                new_saldo = max(0.0, tot_val - new_cob)
                                new_st = 'COBRADO' if new_saldo <= 0 else 'COBRADO PARCIAL'
                                conn.execute(text("""
                                    UPDATE ingresos SET
                                        importe_cobrado = :cob,
                                        fecha_cobro = CAST(:fecha AS date),
                                        medio_cobro = :medio,
                                        saldo = :saldo,
                                        estado_cobro = :st,
                                        id_acuerdo = :cc_id,
                                        updated_at = NOW()
                                    WHERE id_ingreso = :iid
                                """), {
                                    'cob': new_cob,
                                    'fecha': fecha,
                                    'medio': medio_clean,
                                    'saldo': new_saldo,
                                    'st': new_st,
                                    'cc_id': cc_id,
                                    'iid': u_id
                                })
                                rem_monto -= apply_amt
                        else:
                            inv_row = conn.execute(text("SELECT total, importe_cobrado FROM ingresos WHERE id_ingreso = :iid"), {'iid': imputar_id}).fetchone()
                            if inv_row:
                                tot_val = float(inv_row[0] or 0.0)
                                prev_cob_val = float(inv_row[1] or 0.0)
                                new_cob = prev_cob_val + monto
                                new_saldo = max(0.0, tot_val - new_cob)
                                new_st = 'COBRADO' if new_saldo <= 0 else 'COBRADO PARCIAL'
                                conn.execute(text("""
                                    UPDATE ingresos SET
                                        importe_cobrado = :cob,
                                        fecha_cobro = CAST(:fecha AS date),
                                        medio_cobro = :medio,
                                        saldo = :saldo,
                                        estado_cobro = :st,
                                        id_acuerdo = :cc_id,
                                        updated_at = NOW()
                                    WHERE id_ingreso = :iid
                                """), {
                                    'cob': new_cob,
                                    'fecha': fecha,
                                    'medio': medio_clean,
                                    'saldo': new_saldo,
                                    'st': new_st,
                                    'cc_id': cc_id,
                                    'iid': imputar_id
                                })
            except Exception as e:
                print(f"[add_pago_cuenta_corriente Supabase Error] {e}")
                cc_id = f"CC-{datetime.now().strftime('%y%m%d%H%M%S')}"
        else:
            cc_id = None

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws_cc = self._ensure_cuentas_corrientes_sheet(wb)
            if not cc_id:
                cc_id = self._get_next_entity_id(ws_cc, 'CC')

            if is_cheque and not ref_id:
                ws_chq = self._ensure_cheques_sheet(wb)
                if not chq_id:
                    chq_id = self._get_next_cheque_id(ws_chq)
                ref_id = chq_id
                tipo_lbl = f"Entrega {tipo_chq} ({nro_chq or chq_id})"
                ws_chq.append([
                    chq_id, fecha, tipo_chq, monto, cliente, cuit,
                    banco, nro_chq, vencimiento, 'ECONCATIVO S.A.S.', 'Disponible',
                    '', '', '', cc_id, f"Ingresado como entrega a cuenta de {cliente}. {obs}".strip()
                ])

            ws_cc.append([
                cc_id, fecha, vencimiento, cliente, cuit,
                tipo_lbl, ref_id, concepto, 0.0, monto, obs
            ])

            if 'INGRESOS' in wb.sheetnames:
                ws_i = wb['INGRESOS']
                next_ing_row = ws_i.max_row + 1
                new_ing_id = f"ING-{next_ing_row - 4:06d}"
                medio_clean = metodo_raw.replace('_', ' ').title()
                cuenta_tesoreria = payload.get('cuenta_tesoreria') or payload.get('cuenta_destino') or ''
                if cuenta_tesoreria:
                    medio_clean = f"{medio_clean} - {cuenta_tesoreria}" if cuenta_tesoreria.lower() not in medio_clean.lower() else cuenta_tesoreria

                row_ing = {
                    1: new_ing_id, 2: fecha, 3: 'Entrega CC', 4: '', 5: cc_id,
                    6: cliente, 7: cuit, 8: concepto, 9: '', 10: '', 11: 0, 12: 0,
                    13: monto, 14: 0, 15: 0, 16: monto, 17: 'COBRADO', 18: monto,
                    19: fecha, 20: medio_clean, 21: 0, 22: cc_id,
                    28: f"Entrega a cuenta Cuentas Corrientes ({cc_id}). {obs}".strip()
                }
                for col_idx, val in row_ing.items():
                    ws_i.cell(next_ing_row, col_idx, val)

                if imputar_id:
                    if imputar_id == 'auto_fifo':
                        unpaid = self.get_unpaid_invoices_client(cliente)
                        rem_monto = monto
                        for inv in unpaid:
                            if rem_monto <= 0: break
                            target_id = inv['id']
                            for r_idx in range(5, ws_i.max_row + 1):
                                if str(ws_i.cell(r_idx, 1).value or '').strip() == str(target_id).strip():
                                    tot = self._to_float(ws_i.cell(r_idx, 16).value)
                                    prev_cob = self._to_float(ws_i.cell(r_idx, 18).value)
                                    pend = max(0.0, tot - prev_cob)
                                    apply_amt = min(rem_monto, pend if pend > 0 else tot)
                                    new_cob = prev_cob + apply_amt
                                    new_saldo = max(0.0, tot - new_cob)
                                    ws_i.cell(r_idx, 18, new_cob)
                                    ws_i.cell(r_idx, 19, fecha)
                                    ws_i.cell(r_idx, 20, medio_clean)
                                    ws_i.cell(r_idx, 21, new_saldo)
                                    ws_i.cell(r_idx, 22, cc_id)
                                    ws_i.cell(r_idx, 17, 'COBRADO' if new_saldo <= 0 else 'COBRADO PARCIAL')
                                    rem_monto -= apply_amt
                                    break
                    else:
                        for r_idx in range(5, ws_i.max_row + 1):
                            if str(ws_i.cell(r_idx, 1).value or '').strip() == str(imputar_id).strip():
                                tot = self._to_float(ws_i.cell(r_idx, 16).value)
                                prev_cob = self._to_float(ws_i.cell(r_idx, 18).value)
                                new_cob = prev_cob + monto
                                new_saldo = max(0.0, tot - new_cob)
                                ws_i.cell(r_idx, 18, new_cob)
                                ws_i.cell(r_idx, 19, fecha)
                                ws_i.cell(r_idx, 20, medio_clean)
                                ws_i.cell(r_idx, 21, new_saldo)
                                ws_i.cell(r_idx, 22, cc_id)
                                ws_i.cell(r_idx, 17, 'COBRADO' if new_saldo <= 0 else 'COBRADO PARCIAL')
                                break

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[add_pago_cuenta_corriente Excel Warning] {e}")

        return {
            'status': 'success',
            'cc_id': cc_id,
            'ref_id': ref_id,
            'cliente': cliente,
            'monto': monto,
            'fecha': fecha
        }

    # TESORERIA & CONCILIACION BANCARIA / CAJA MODULE
    def _ensure_tesoreria_sheets(self, wb):
        if 'TESORERIA' not in wb.sheetnames:
            ws_t = wb.create_sheet('TESORERIA')
            ws_t.cell(1, 1, 'ECONCATIVO - CATÁLOGO DE CUENTAS Y SALDOS DE TESORERÍA')
            ws_t.cell(2, 1, 'Generado automáticamente por Antigravity Control System')
            headers_t = ['ID cuenta', 'Nombre cuenta', 'Tipo', 'N° Cuenta / CBU / Alias', 'Saldo inicial', 'Saldo real cotejado', 'Fecha ultimo cotejo', 'Observaciones']
            for col_idx, h in enumerate(headers_t, 1):
                ws_t.cell(4, col_idx, h)
            
            default_accounts = [
                ['CTA-001', 'Caja Chica Efectivo', 'Efectivo', 'Efectivo en Caja', 0.0, 0.0, '', 'Caja Chica para Gastos Minoristas'],
                ['CTA-002', 'Banco Galicia Cta Cte', 'Banco', 'CBU Galicia Cta Cte 001', 0.0, 0.0, '', 'Cuenta Corriente Bancaria Principal'],
                ['CTA-003', 'Banco Macro Cta Cte', 'Banco', 'CBU Macro Cta Cte 002', 0.0, 0.0, '', 'Cuenta Corriente Secundaria'],
                ['CTA-004', 'Mercado Pago / Billetera Digital', 'Billetera', 'Alias Mercado Pago', 0.0, 0.0, '', 'Billetera Digital y Cobros Virtuales'],
                ['CTA-005', 'Cartera de Cheques', 'Cheques', 'Valores Físicos y E-Cheqs', 0.0, 0.0, '', 'Sincronizado automáticamente con Cartera Cheques']
            ]
            for r_idx, acc in enumerate(default_accounts, 5):
                for c_idx, val in enumerate(acc, 1):
                    ws_t.cell(r_idx, c_idx, val)

        if 'MOVIMIENTOS_TESORERIA' not in wb.sheetnames:
            ws_m = wb.create_sheet('MOVIMIENTOS_TESORERIA')
            ws_m.cell(1, 1, 'ECONCATIVO - REGISTRO DE MOVIMIENTOS Y TRANSFERENCIAS INTERNAS DE TESORERÍA')
            ws_m.cell(2, 1, 'Generado automáticamente por Antigravity Control System')
            headers_m = ['ID movimiento', 'Fecha', 'Cuenta origen', 'Cuenta destino', 'Monto', 'Concepto', 'Observaciones']
            for col_idx, h in enumerate(headers_m, 1):
                ws_m.cell(4, col_idx, h)

    def _extract_income_for_account(self, ing, acc, accounts):
        """Extracts the amount of an income entry attributed to a given treasury account, handling combined payment method breakdowns."""
        med_orig = ing.get('medio') or ''
        m_total = ing.get('monto', 0.0)
        if m_total <= 0 or not med_orig:
            return 0.0

        cid = acc['id']
        nomb = acc['nombre']
        nomb_l = nomb.lower()
        tipo = acc['tipo']
        cbu = (acc.get('cbu') or '').lower()

        def matches_acc(label_str, full_str):
            lbl_l = label_str.lower()
            full_l = full_str.lower()
            
            if nomb_l in full_l or cid.lower() in full_l:
                if tipo == 'Banco' and ('cheque' in lbl_l or 'echeq' in lbl_l or 'e-cheq' in lbl_l):
                    return False
                return True
                
            if tipo == 'Efectivo':
                return 'efectivo' in lbl_l or 'caja' in lbl_l
            elif tipo == 'Billetera':
                return any(w in lbl_l or w in full_l for w in ['mercado', 'billetera', 'ualá', 'uala', 'personal'])
            elif tipo == 'Banco':
                if 'cheque' in lbl_l or 'echeq' in lbl_l or 'e-cheq' in lbl_l:
                    return False
                is_primary = (cid == 'CTA-002' or 'galicia' in nomb_l)
                nomb_words = [w for w in re.split(r'\s+', nomb_l) if w not in ['banco', 'cta', 'cte', 'caja', 'ahorro', 'de', 'el', 'la', 'y']]
                matches_specific = any(w in full_l for w in nomb_words if len(w) > 2) or (cbu and cbu in full_l)
                
                other_bank_mentioned = False
                for other_acc in accounts:
                    if other_acc['id'] != cid and other_acc['tipo'] == 'Banco':
                        other_nomb_l = other_acc['nombre'].lower()
                        other_words = [w for w in re.split(r'\s+', other_nomb_l) if w not in ['banco', 'cta', 'cte', 'caja', 'ahorro', 'de', 'el', 'la', 'y']]
                        if any(w in full_l for w in other_words if len(w) > 2):
                            other_bank_mentioned = True
                            break
                            
                if matches_specific:
                    return True
                elif is_primary and not other_bank_mentioned and ('banco' in lbl_l or 'transfer' in lbl_l or 'banco' in full_l or 'transfer' in full_l):
                    return True
            return False

        if '|' in med_orig:
            parts = [p.strip() for p in med_orig.split('|')]
            matched_amount = 0.0
            for part in parts:
                match = re.search(r'^(.*?):\s*\$?([\d\.,]+)', part)
                if match:
                    label = match.group(1).strip()
                    amt_str = match.group(2).strip()
                    item_amt = self._to_float(amt_str)
                    if matches_acc(label, med_orig):
                        matched_amount += item_amt
            return matched_amount
        else:
            if matches_acc(med_orig, med_orig):
                return m_total
            return 0.0

    def validate_treasury_disponibilidad(self, cuenta_tesoreria, monto_desembolso):
        """Validates if a treasury/cash account has sufficient available funds for an outflow operation.
           Returns (is_valid: bool, available_balance: float, account_name: str, error_msg: str or None)
        """
        try:
            monto_val = float(monto_desembolso or 0.0)
        except (ValueError, TypeError):
            monto_val = 0.0

        if monto_val <= 0.01:
            return True, 0.0, '', None
            
        cuenta_clean = str(cuenta_tesoreria or '').strip()
        if not cuenta_clean or any(k in cuenta_clean.lower() for k in ['saldo a favor', 'cheque de terceros', 'e-cheq']):
            return True, 0.0, cuenta_clean, None

        summary = self.get_tesoreria_summary()
        accounts = summary.get('accounts', [])

        matched_acc = None
        c_lower = cuenta_clean.lower()
        
        # 1. Exact name or ID match
        for acc in accounts:
            acc_name = str(acc.get('nombre') or '').strip().lower()
            if acc_name == c_lower or acc.get('id', '').lower() == c_lower:
                matched_acc = acc
                break

        # 2. Key phrase / substring match
        if not matched_acc:
            for acc in accounts:
                acc_name = str(acc.get('nombre') or '').strip().lower()
                acc_tipo = str(acc.get('tipo') or '').strip().lower()
                if acc_name in c_lower or c_lower in acc_name:
                    matched_acc = acc
                    break
                if ('efectivo' in c_lower or 'caja' in c_lower) and (acc_tipo == 'efectivo' or 'caja' in acc_name):
                    matched_acc = acc
                    break
                elif 'galicia' in c_lower and 'galicia' in acc_name:
                    matched_acc = acc
                    break
                elif 'macro' in c_lower and 'macro' in acc_name:
                    matched_acc = acc
                    break
                elif 'mercado' in c_lower and 'mercado' in acc_name:
                    matched_acc = acc
                    break

        if matched_acc:
            saldo_disp = float(matched_acc.get('saldo_calculado', 0.0))
            acc_name_disp = matched_acc.get('nombre')

            if monto_val > saldo_disp:
                sf_formatted = f"${saldo_disp:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                des_formatted = f"${monto_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                msg = f"Fondos insuficientes en la cuenta '{acc_name_disp}'. Disponibilidad actual: {sf_formatted} | Intentas gastar/pagar: {des_formatted}."
                return False, saldo_disp, acc_name_disp, msg

        return True, 0.0, cuenta_clean, None

    def get_tesoreria_summary(self):
        """Calculates real-time financial balances and reconciliation state for all company treasury accounts."""
        # 1. Accounts (Supabase First)
        accounts = []
        _, tes_rows = self.get_sheet_data('TESORERIA')
        for r_idx, r in enumerate(tes_rows, 5):
            cid = str(self._get_row_prop(r, ['ID cuenta', 'ID']) or '').strip()
            if cid.startswith('CTA-'):
                accounts.append({
                    'id': cid,
                    'nombre': str(self._get_row_prop(r, ['Nombre cuenta', 'Nombre']) or ''),
                    'tipo': str(self._get_row_prop(r, ['Tipo']) or 'Banco'),
                    'cbu': str(self._get_row_prop(r, ['Nº Cuenta / CBU / Alias', 'CBU']) or ''),
                    'saldo_inicial': self._to_float(self._get_row_prop(r, ['Saldo inicial'])),
                    'saldo_real': self._to_float(self._get_row_prop(r, ['Saldo real cotejado'])),
                    'fecha_cotejo': str(self._get_row_prop(r, ['Fecha ultimo cotejo']) or '-'),
                    'observaciones': str(self._get_row_prop(r, ['Observaciones']) or ''),
                    'row_idx': r_idx
                })

        if not accounts:
            try:
                wb = self.load_wb(data_only=True)
                self._ensure_tesoreria_sheets(wb)
                ws_t = wb['TESORERIA']
                for r in range(5, ws_t.max_row + 1):
                    cid = str(ws_t.cell(r, 1).value or '').strip()
                    if cid.startswith('CTA-'):
                        accounts.append({
                            'id': cid,
                            'nombre': str(ws_t.cell(r, 2).value or ''),
                            'tipo': str(ws_t.cell(r, 3).value or 'Banco'),
                            'cbu': str(ws_t.cell(r, 4).value or ''),
                            'saldo_inicial': self._to_float(ws_t.cell(r, 5).value),
                            'saldo_real': self._to_float(ws_t.cell(r, 6).value),
                            'fecha_cotejo': str(ws_t.cell(r, 7).value or '-'),
                            'observaciones': str(ws_t.cell(r, 8).value or ''),
                            'row_idx': r
                        })
            except Exception:
                pass

        # Calculate Income by Account / Method
        ingresos_raw = []
        _, ing_data = self.get_sheet_data('INGRESOS')
        for r in ing_data:
            iid = str(self._get_row_prop(r, ['ID ingreso', 'ID']) or '').strip()
            if iid.startswith('ING-'):
                st = str(self._get_row_prop(r, ['Estado cobro', 'Estado']) or '').upper()
                monto_cob = self._to_float(self._get_row_prop(r, ['Importe cobrado']))
                if monto_cob <= 0 and 'COBRADO' in st:
                    monto_cob = self._to_float(self._get_row_prop(r, ['Total', 'Importe total']))
                medio = str(self._get_row_prop(r, ['Medio cobro', 'Tipo comprobante']) or '').strip()
                cliente = str(self._get_row_prop(r, ['Cliente', 'Nombre']) or '')
                ingresos_raw.append({'monto': monto_cob, 'medio': medio, 'cliente': cliente, 'estado': st})

        # Calculate Expenses by Account / Method
        egresos_raw = []
        _, egr_data = self.get_sheet_data('EGRESOS')
        for r in egr_data:
            eid = str(self._get_row_prop(r, ['ID egreso', 'ID']) or '').strip()
            if eid.startswith('EGR-'):
                monto_pag = self._to_float(self._get_row_prop(r, ['Importe pagado', 'Total']))
                if monto_pag <= 0:
                    continue
                medio = str(self._get_row_prop(r, ['Medio de pago', 'Medio pago', 'Tipo comprobante']) or '').strip()
                prov = str(self._get_row_prop(r, ['Proveedor']) or '')
                cat = str(self._get_row_prop(r, ['Categoría', 'Categoria']) or '')
                egresos_raw.append({'monto': monto_pag, 'medio': medio, 'proveedor': prov, 'categoria': cat})

        # Calculate Debited Own Checks (Cheques Propios Debitados)
        _, chq_data = self.get_sheet_data('CHEQUES')
        for r in chq_data:
            cid = str(self._get_row_prop(r, ['ID cheque', 'ID']) or '').strip()
            st = str(self._get_row_prop(r, ['Estado']) or '').strip()
            banco = str(self._get_row_prop(r, ['Banco']) or '').strip()
            monto = self._to_float(self._get_row_prop(r, ['Monto', 'monto', 'Importe', 'Importe / Monto']))
            tipo_prop = str(self._get_row_prop(r, ['Tipo']) or '').strip().lower()

            if (cid.startswith('CHQP-') or tipo_prop == 'propio') and 'debitado' in st.lower() and monto > 0:
                egresos_raw.append({
                    'monto': monto,
                    'medio': f"Cheque Propio - {banco}",
                    'proveedor': str(self._get_row_prop(r, ['Destinatario', 'Proveedor']) or ''),
                    'categoria': 'Cheque Propio Debitado'
                })

        # Calculate Internal Transfers (Supabase First)
        transfers_raw = []
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    tr_rows = conn.execute(text("SELECT id_movimiento, fecha, cuenta_origen, cuenta_destino, monto, concepto FROM tesoreria_movimientos WHERE id_movimiento LIKE 'TRF-%'")).fetchall()
                    for tr in tr_rows:
                        trm = dict(tr._mapping)
                        transfers_raw.append({
                            'id': trm.get('id_movimiento'),
                            'fecha': str(trm.get('fecha') or ''),
                            'origen': str(trm.get('cuenta_origen') or ''),
                            'destino': str(trm.get('cuenta_destino') or ''),
                            'monto': self._to_float(trm.get('monto')),
                            'concepto': str(trm.get('concepto') or '')
                        })
            except Exception as e:
                print(f"[get_tesoreria_summary transfers Supabase error] {e}")

        if not transfers_raw:
            try:
                wb = self.load_wb(data_only=True)
                if 'MOVIMIENTOS_TESORERIA' in wb.sheetnames:
                    ws_m = wb['MOVIMIENTOS_TESORERIA']
                    for r in range(5, ws_m.max_row + 1):
                        if ws_m.cell(r, 1).value and str(ws_m.cell(r, 1).value).startswith('TRF-'):
                            transfers_raw.append({
                                'id': ws_m.cell(r, 1).value,
                                'fecha': str(ws_m.cell(r, 2).value or ''),
                                'origen': str(ws_m.cell(r, 3).value or ''),
                                'destino': str(ws_m.cell(r, 4).value or ''),
                                'monto': self._to_float(ws_m.cell(r, 5).value),
                                'concepto': str(ws_m.cell(r, 6).value or '')
                            })
            except Exception:
                pass

        # Calculate Check Portfolio Total (Disponible)
        total_cheques_disponibles = 0.0
        total_cheques_ingresados = 0.0
        total_cheques_usados = 0.0

        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    res_disp = conn.execute(text("""
                        SELECT COALESCE(SUM(monto), 0)
                        FROM cheques
                        WHERE LOWER(TRIM(estado)) IN ('disponible', 'en cartera')
                          AND (id_cheque NOT LIKE 'CHQP-%')
                    """)).scalar()
                    total_cheques_disponibles = float(res_disp or 0.0)

                    res_ing = conn.execute(text("""
                        SELECT COALESCE(SUM(monto), 0)
                        FROM cheques
                        WHERE id_cheque NOT LIKE 'CHQP-%'
                    """)).scalar()
                    total_cheques_ingresados = float(res_ing or 0.0)

                    res_used = conn.execute(text("""
                        SELECT COALESCE(SUM(monto), 0)
                        FROM cheques
                        WHERE id_cheque NOT LIKE 'CHQP-%'
                          AND LOWER(TRIM(estado)) NOT IN ('disponible', 'en cartera', 'anulado')
                    """)).scalar()
                    total_cheques_usados = float(res_used or 0.0)
            except Exception as e:
                print(f"[get_tesoreria_summary cheques Supabase error] {e}")

        if total_cheques_disponibles == 0.0 and chq_data:
            for r in chq_data:
                cid = str(self._get_row_prop(r, ['ID cheque', 'ID', 'id_cheque']) or '').strip()
                if cid.startswith('CHQP-'):
                    continue
                monto = self._to_float(self._get_row_prop(r, ['Monto', 'monto', 'Importe / Monto', 'Importe', 'Total']))
                st = str(self._get_row_prop(r, ['Estado', 'estado']) or '').strip().lower()
                total_cheques_ingresados += monto
                if st in ('disponible', 'en cartera'):
                    total_cheques_disponibles += monto
                elif st not in ('anulado',):
                    total_cheques_usados += monto

        # Process Each Account
        result_accounts = []
        for acc in accounts:
            cid = acc['id']
            nomb = acc['nombre']
            tipo = acc['tipo']
            s_init = acc['saldo_inicial']
            
            tot_ing = 0.0
            tot_egr = 0.0
            tot_trf_in = 0.0
            tot_trf_out = 0.0

            if tipo == 'Cheques' or 'cheque' in nomb.lower():
                s_calc = total_cheques_disponibles
                tot_ing = total_cheques_ingresados
                tot_egr = total_cheques_usados
            else:
                # Sum income attributed to this account
                for ing in ingresos_raw:
                    tot_ing += self._extract_income_for_account(ing, acc, accounts)

                # Sum expenses attributed to this account
                for egr in egresos_raw:
                    m = egr['monto']
                    if m <= 0:
                        continue
                    med = egr['medio'].lower()
                    nomb_l = nomb.lower()
                    if nomb_l in med or cid.lower() in med:
                        tot_egr += m
                    elif tipo == 'Efectivo' and ('efectivo' in med or 'caja' in med):
                        tot_egr += m
                    elif tipo == 'Billetera' and ('mercado' in med or 'billetera' in med or 'ualá' in med or 'uala' in med or 'personal' in med):
                        tot_egr += m
                    elif tipo == 'Banco':
                        is_primary = (cid == 'CTA-002' or 'galicia' in nomb_l)
                        nomb_words = [w for w in re.split(r'\s+', nomb_l) if w not in ['banco', 'cta', 'cte', 'caja', 'ahorro', 'de', 'el', 'la', 'y']]
                        matches_specific = any(w in med for w in nomb_words if len(w) > 2) or (acc['cbu'] and acc['cbu'].lower() in med)
                        
                        other_bank_mentioned = False
                        for other_acc in accounts:
                            if other_acc['id'] != cid and other_acc['tipo'] == 'Banco':
                                other_nomb_l = other_acc['nombre'].lower()
                                other_words = [w for w in re.split(r'\s+', other_nomb_l) if w not in ['banco', 'cta', 'cte', 'caja', 'ahorro', 'de', 'el', 'la', 'y']]
                                if any(w in med for w in other_words if len(w) > 2):
                                    other_bank_mentioned = True
                                    break
                                    
                        if matches_specific:
                            tot_egr += m
                        elif is_primary and not other_bank_mentioned and ('banco' in med or 'transfer' in med):
                            tot_egr += m

                # Sum internal transfers
                for trf in transfers_raw:
                    m = trf['monto']
                    orig = trf['origen'].lower()
                    dest = trf['destino'].lower()
                    nomb_l = nomb.lower()
                    
                    if nomb_l in dest or cid.lower() in dest:
                        tot_trf_in += m
                    if nomb_l in orig or cid.lower() in orig:
                        tot_trf_out += m

                s_calc = s_init + tot_ing - tot_egr + tot_trf_in - tot_trf_out

            s_real = acc['saldo_real']
            dif = round(s_real - s_calc, 2) if s_real > 0 else 0.0
            
            if s_real <= 0:
                estado_conciliacion = 'SIN_COTEJO'
            elif abs(dif) < 0.01:
                estado_conciliacion = 'CONCILIADO'
            else:
                estado_conciliacion = 'PENDIENTE_AJUSTE'

            result_accounts.append({
                'id': cid,
                'nombre': nomb,
                'tipo': tipo,
                'cbu': acc['cbu'],
                'saldo_inicial': s_init,
                'total_ingresos': tot_ing,
                'total_egresos': tot_egr,
                'transferencias_entrantes': tot_trf_in,
                'transferencias_salientes': tot_trf_out,
                'saldo_calculado': round(s_calc, 2),
                'saldo_real': s_real,
                'diferencia': dif,
                'fecha_cotejo': acc['fecha_cotejo'],
                'estado_conciliacion': estado_conciliacion,
                'observaciones': acc['observaciones']
            })

        total_disponible = sum(a['saldo_calculado'] for a in result_accounts)
        total_bancos = sum(a['saldo_calculado'] for a in result_accounts if a['tipo'] == 'Banco')
        total_efectivo = sum(a['saldo_calculado'] for a in result_accounts if a['tipo'] == 'Efectivo')
        total_billeteras = sum(a['saldo_calculado'] for a in result_accounts if a['tipo'] == 'Billetera')
        total_cheques = sum(a['saldo_calculado'] for a in result_accounts if a['tipo'] == 'Cheques' or 'cheque' in a['nombre'].lower())

        return {
            'status': 'success',
            'accounts': result_accounts,
            'totals': {
                'total_disponible': round(total_disponible, 2),
                'total_bancos': round(total_bancos, 2),
                'total_efectivo': round(total_efectivo, 2),
                'total_billeteras': round(total_billeteras, 2),
                'total_cheques': round(total_cheques, 2)
            }
        }

    def update_saldos_iniciales_tesoreria(self, saldos_dict):
        """Updates opening initial balances for treasury accounts in Supabase and Excel mirror."""
        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    for cid, saldo in saldos_dict.items():
                        conn.execute(text("UPDATE tesoreria_cuentas SET saldo_inicial = :saldo WHERE id_cuenta = :cid"), {
                            'saldo': self._to_float(saldo),
                            'cid': str(cid).strip()
                        })
            except Exception as e:
                print(f"[update_saldos_iniciales_tesoreria Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            self._ensure_tesoreria_sheets(wb)
            ws_t = wb['TESORERIA']
            for r in range(5, ws_t.max_row + 1):
                cid = str(ws_t.cell(r, 1).value or '').strip()
                if cid in saldos_dict:
                    ws_t.cell(r, 5, self._to_float(saldos_dict[cid]))
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[update_saldos_iniciales_tesoreria Excel Warning] {e}")

        return {"status": "success", "message": "Saldos iniciales actualizados correctamente."}

    def update_saldo_real_tesoreria(self, account_id, saldo_real, fecha_cotejo=None):
        """Updates Home Banking / Cash count real balance in Supabase and Excel mirror."""
        f_str = fecha_cotejo or datetime.now().strftime('%Y-%m-%d')
        saldo_fl = self._to_float(saldo_real)
        aid_clean = str(account_id).strip()

        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE tesoreria_cuentas SET 
                            saldo_real_cotejado = :saldo,
                            fecha_ultimo_cotejo = CAST(NULLIF(:f_str, '') AS date)
                        WHERE id_cuenta = :cid
                    """), {
                        'saldo': saldo_fl,
                        'f_str': f_str,
                        'cid': aid_clean
                    })
            except Exception as e:
                print(f"[update_saldo_real_tesoreria Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            self._ensure_tesoreria_sheets(wb)
            ws_t = wb['TESORERIA']
            target_row = None
            for r in range(5, ws_t.max_row + 1):
                if str(ws_t.cell(r, 1).value or '').strip() == aid_clean:
                    target_row = r
                    break
            if target_row:
                ws_t.cell(target_row, 6, saldo_fl)
                ws_t.cell(target_row, 7, f_str)
                wb.save(self.excel_path)
                self._invalidate_cache()
        except Exception as e:
            print(f"[update_saldo_real_tesoreria Excel Warning] {e}")

        return {"status": "success", "account_id": aid_clean, "saldo_real": saldo_fl}

    def registrar_transferencia_tesoreria(self, origen, destino, monto, fecha=None, concepto=None, observaciones=None):
        """Registers an internal funds transfer between treasury accounts in Supabase and Excel mirror."""
        f_str = fecha or datetime.now().strftime('%Y-%m-%d')
        monto_fl = self._to_float(monto)
        origen_str = str(origen or 'Caja Chica Efectivo')
        destino_str = str(destino or 'Banco Galicia Cta Cte')
        concepto_str = str(concepto or 'Transferencia Interna / Ajuste de Fondos')
        obs_str = str(observaciones or '')

        # 1. Supabase Master Insert
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                m_id = self.supabase_service.get_next_id('tesoreria_movimientos', 'TRF', 'id_movimiento')
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO tesoreria_movimientos (
                            id_movimiento, fecha, cuenta_origen, cuenta_destino, monto, concepto, observaciones, created_at
                        ) VALUES (
                            :mid, CAST(:fecha AS date), :origen, :destino, :monto, :concepto, :obs, NOW()
                        )
                    """), {
                        'mid': m_id,
                        'fecha': f_str,
                        'origen': origen_str,
                        'destino': destino_str,
                        'monto': monto_fl,
                        'concepto': concepto_str,
                        'obs': obs_str
                    })
            except Exception as e:
                print(f"[registrar_transferencia_tesoreria Supabase Error] {e}")
                m_id = f"TRF-{datetime.now().strftime('%y%m%d%H%M%S')}"
        else:
            m_id = None

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            self._ensure_tesoreria_sheets(wb)
            ws_m = wb['MOVIMIENTOS_TESORERIA']
            if not m_id:
                m_id = self._get_next_entity_id(ws_m, 'TRF')
            row_vals = [
                m_id,
                f_str,
                origen_str,
                destino_str,
                monto_fl,
                concepto_str,
                obs_str
            ]
            ws_m.append(row_vals)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[registrar_transferencia_tesoreria Excel Warning] {e}")

        return {"status": "success", "id": m_id, "monto": monto_fl}

    def add_gasto_bancario_tesoreria(self, cuenta_nombre, monto, fecha=None, concepto=None, observaciones=None):
        """Batch/consolidated entry of bank commissions into Supabase EGRESOS and Excel mirror."""
        f_str = fecha or datetime.now().strftime('%Y-%m-%d')
        monto_fl = self._to_float(monto)
        det = concepto or f"Gastos Bancarios y Comisiones Mantenimiento - {cuenta_nombre}"
        obs = observaciones or f"Carga consolidada de comisiones bancarias para {cuenta_nombre}"
        cuenta_str = str(cuenta_nombre or 'Entidad Bancaria')
        medio_str = f"Transferencia - {cuenta_str}"

        # 1. Supabase Master Insert
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                egr_id = self.supabase_service.get_next_id('egresos', 'EGR', 'id_egreso')
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO egresos (
                            id_egreso, fecha_comprobante, tipo_comprobante, nro_comprobante, categoria, subcategoria,
                            proveedor, descripcion, neto, total, estado_pago, importe_pagado, fecha_pago,
                            medio_pago, saldo, observaciones, created_at, updated_at
                        ) VALUES (
                            :eid, CAST(:fecha AS date), 'Comprobante Bancario', 'GASTO-BANCARIO', 'Gastos Bancarios', 'Comisiones',
                            :cuenta, :det, :monto, :monto, 'Pagado', :monto, CAST(:fecha AS date),
                            :medio, 0, :obs, NOW(), NOW()
                        )
                    """), {
                        'eid': egr_id,
                        'fecha': f_str,
                        'cuenta': cuenta_str,
                        'det': det,
                        'monto': monto_fl,
                        'medio': medio_str,
                        'obs': obs
                    })
            except Exception as e:
                print(f"[add_gasto_bancario_tesoreria Supabase Error] {e}")
                egr_id = f"EGR-{datetime.now().strftime('%y%m%d%H%M%S')}"
        else:
            egr_id = None

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            ws_e = wb['EGRESOS']
            if not egr_id:
                egr_id = self._get_next_entity_id(ws_e, 'EGR')
            row_dict = {
                1: egr_id,
                2: f_str,
                3: 'Comprobante Bancario',
                4: '0001',
                5: 'GASTO-BANCARIO',
                6: cuenta_str,
                7: 'Gastos y Comisiones Bancarias',
                8: 'Gastos Bancarios',
                13: monto_fl,
                14: 0,
                15: 0,
                16: monto_fl,
                17: 'PAGADO',
                18: monto_fl,
                19: f_str,
                20: medio_str,
                28: obs
            }
            target_r = ws_e.max_row + 1
            for col_idx, val in row_dict.items():
                ws_e.cell(target_r, col_idx, val)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[add_gasto_bancario_tesoreria Excel Warning] {e}")

        return {"status": "success", "id": egr_id, "monto": monto_fl}

    def add_tesoreria_account(self, nombre, tipo='Banco', cbu='', saldo_inicial=0.0, observaciones=''):
        """Adds a new bank account, cash box, or digital wallet to Supabase and Excel mirror."""
        s_init = self._to_float(saldo_inicial)
        nom_str = str(nombre or 'Nueva Cuenta').strip()
        tipo_str = str(tipo or 'Banco').strip()
        cbu_str = str(cbu or '').strip()
        obs_str = str(observaciones or '').strip()

        # 1. Supabase Master Insert
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                acc_id = self.supabase_service.get_next_id('tesoreria_cuentas', 'CTA', 'id_cuenta')
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO tesoreria_cuentas (
                            id_cuenta, nombre_cuenta, tipo, nro_cuenta_cbu_alias, saldo_inicial,
                            saldo_real_cotejado, fecha_ultimo_cotejo, observaciones, created_at
                        ) VALUES (
                            :cid, :nombre, :tipo, :cbu, :s_init, 0.0, NULL, :obs, NOW()
                        )
                    """), {
                        'cid': acc_id,
                        'nombre': nom_str,
                        'tipo': tipo_str,
                        'cbu': cbu_str,
                        's_init': s_init,
                        'obs': obs_str
                    })
            except Exception as e:
                print(f"[add_tesoreria_account Supabase Error] {e}")
                acc_id = f"CTA-{datetime.now().strftime('%y%m%d%H%M%S')}"
        else:
            acc_id = None

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            self._ensure_tesoreria_sheets(wb)
            ws_t = wb['TESORERIA']
            if not acc_id:
                acc_id = self._get_next_entity_id(ws_t, 'CTA')
            row_vals = [
                acc_id,
                nom_str,
                tipo_str,
                cbu_str,
                s_init,
                0.0,
                None,
                obs_str
            ]
            ws_t.append(row_vals)
            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[add_tesoreria_account Excel Warning] {e}")

        return {"status": "success", "id": acc_id, "nombre": nom_str, "saldo_inicial": s_init}

    def delete_tesoreria_account(self, account_id):
        """Deletes/removes a user-created account from Supabase and Excel (protects CTA-005 Cartera de Cheques)."""
        aid_clean = str(account_id).strip()
        if aid_clean == 'CTA-005':
            return {"status": "error", "message": "No se puede eliminar la Cartera de Cheques del sistema."}

        # 1. Supabase Master Delete
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("DELETE FROM tesoreria_cuentas WHERE id_cuenta = :cid"), {'cid': aid_clean})
            except Exception as e:
                print(f"[delete_tesoreria_account Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            self._ensure_tesoreria_sheets(wb)
            ws_t = wb['TESORERIA']
            target_row = None
            for r in range(5, ws_t.max_row + 1):
                if str(ws_t.cell(r, 1).value or '').strip() == aid_clean:
                    target_row = r
                    break
            if target_row:
                ws_t.delete_rows(target_row)
                wb.save(self.excel_path)
                self._invalidate_cache()
        except Exception as e:
            print(f"[delete_tesoreria_account Excel Warning] {e}")

        return {"status": "success", "account_id": aid_clean, "message": "Cuenta eliminada correctamente."}

    def add_cheque_propio(self, payload):
        """Issues a new own check (Cheque Propio / Chequera) into Cheques Disponibles in company chequera."""
        fecha_emision = payload.get('fecha_emision') or payload.get('fecha') or datetime.now().strftime('%Y-%m-%d')
        fecha_cobro = payload.get('fecha_cobro') or payload.get('vencimiento') or fecha_emision
        monto_fl = self._to_float(payload.get('monto', 0))
        banco = payload.get('banco', 'Banco Galicia Cta Cte')
        beneficiario = payload.get('beneficiario') or 'En Chequera (Sin Asignar)'
        tipo_chq = payload.get('tipo', 'Cheque Físico')
        nro_chq = payload.get('nro_cheque', '')
        estado = payload.get('estado', 'Disponible')
        concepto = payload.get('concepto', 'Cheque Propio en Chequera')
        obs = payload.get('observaciones', '')
        cuit = payload.get('cuit', '')
        id_egreso = payload.get('id_egreso', '')
        obs_total = f"{concepto} | {obs}".strip(' |')
        chq_id = None

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                chq_id = self.supabase_service.get_next_id('cheques', 'CHQP', 'id_cheque')
                with self.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO cheques (
                            id_cheque, fecha_ingreso, tipo, monto, cliente_emisor, cuit_emisor,
                            banco, nro_cheque, fecha_cobro, endosado_tenedor, estado,
                            destino_usado_en, fecha_uso, id_egreso, id_ingreso_origen, observaciones
                        ) VALUES (
                            :id_cheque, CAST(:fecha_ingreso AS date), :tipo, :monto, :cliente_emisor, :cuit_emisor,
                            :banco, :nro_cheque, CAST(:fecha_cobro AS date), :endosado_tenedor, :estado,
                            :destino_usado_en, CAST(:fecha_uso AS date), :id_egreso, :id_ingreso_origen, :observaciones
                        )
                    """), {
                        "id_cheque": chq_id,
                        "fecha_ingreso": fecha_emision,
                        "tipo": tipo_chq,
                        "monto": monto_fl,
                        "cliente_emisor": beneficiario,
                        "cuit_emisor": cuit,
                        "banco": banco,
                        "nro_cheque": nro_chq,
                        "fecha_cobro": fecha_cobro,
                        "endosado_tenedor": beneficiario,
                        "estado": estado,
                        "destino_usado_en": f"Emisión Propia ({banco})",
                        "fecha_uso": fecha_emision,
                        "id_egreso": id_egreso,
                        "id_ingreso_origen": '',
                        "observaciones": obs_total
                    })
            except Exception as e:
                print(f"[DataManager] Error inserting cheque propio to Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            if 'CHEQUES' in wb.sheetnames:
                ws_c = wb['CHEQUES']
                if not chq_id:
                    chq_id = self._get_next_entity_id(ws_c, 'CHQP')

                row_vals = [
                    chq_id,
                    fecha_emision,
                    tipo_chq,
                    monto_fl,
                    beneficiario,
                    cuit,
                    banco,
                    nro_chq,
                    fecha_cobro,
                    beneficiario,
                    estado,
                    f"Emisión Propia ({banco})",
                    fecha_emision,
                    id_egreso,
                    '',
                    obs_total,
                    'Propio'
                ]

                target_r = None
                for r in range(5, ws_c.max_row + 2):
                    val_id = str(ws_c.cell(r, 1).value or '')
                    if not val_id or val_id.strip() == '':
                        target_r = r
                        break
                if not target_r:
                    target_r = ws_c.max_row + 1

                for col_idx, val in enumerate(row_vals, 1):
                    ws_c.cell(target_r, col_idx, val)

                wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on add_cheque_propio: {e}")

        self._invalidate_cache()
        return {"status": "success", "id": chq_id, "monto": monto_fl, "banco": banco, "estado": estado}

    def marcar_cheque_propio_debitado(self, cheque_id, fecha_debito=None):
        """Marks an own check as cleared/debited from bank account."""
        cid_clean = str(cheque_id).strip()
        f_str = fecha_debito or datetime.now().strftime('%Y-%m-%d')
        found = False

        # 1. Supabase First
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    res = conn.execute(text("""
                        UPDATE cheques
                        SET estado = 'Debitado / Pagado',
                            fecha_uso = CAST(:fdeb AS date),
                            observaciones = CASE 
                                WHEN observaciones IS NULL OR observaciones = '' THEN :obs_new
                                ELSE observaciones || ' | ' || :obs_new
                            END,
                            updated_at = NOW()
                        WHERE TRIM(LOWER(id_cheque)) = TRIM(LOWER(:cid))
                    """), {
                        "fdeb": f_str,
                        "obs_new": f"Debitado en banco ({f_str})",
                        "cid": cid_clean
                    })
                    if res.rowcount > 0:
                        found = True
            except Exception as e:
                print(f"[DataManager] Error marking cheque propio as debitado in Supabase: {e}")

        # 2. Excel Mirror
        try:
            wb = self.load_wb(data_only=False)
            if 'CHEQUES' in wb.sheetnames:
                ws_c = wb['CHEQUES']
                target_row = None
                for r in range(5, ws_c.max_row + 1):
                    if str(ws_c.cell(r, 1).value or '').strip().lower() == cid_clean.lower():
                        target_row = r
                        break
                if target_row:
                    found = True
                    ws_c.cell(target_row, 11, 'Debitado / Cobrado por Banco')
                    ws_c.cell(target_row, 13, f_str)
                    curr_obs = str(ws_c.cell(target_row, 16).value or '')
                    ws_c.cell(target_row, 16, f"{curr_obs} | [Debitado en banco el {f_str}]".strip(' |'))
                    wb.save(self.excel_path)
        except Exception as e:
            print(f"[DataManager] Warning updating Excel on marcar_cheque_propio_debitado: {e}")

        if not found:
            return {"status": "error", "message": f"Cheque {cheque_id} no encontrado."}

        self._invalidate_cache()
        return {"status": "success", "id": cid_clean, "estado": "Debitado / Pagado"}

    def get_configuracion(self):
        """Returns key-value dictionary of configuration parameters from Supabase (with Excel fallback)."""
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.connect() as conn:
                    res = conn.execute(text("SELECT clave, valor, categoria FROM configuracion WHERE activo = true ORDER BY CASE WHEN categoria = 'general' THEN 1 ELSE 0 END ASC"))
                    cfg = {}
                    for row in res.fetchall():
                        if row[0]:
                            cfg[str(row[0]).strip().lower()] = str(row[1] or '').strip()
                    if cfg:
                        return cfg
            except Exception as e:
                print(f"[get_configuracion Supabase Error] {e}")

        wb = self.load_wb(data_only=True)
        if 'CONFIGURACION' not in wb.sheetnames:
            return {}
        ws = wb['CONFIGURACION']
        cfg = {}
        for r in range(5, ws.max_row + 1):
            param = str(ws.cell(r, 1).value or '').strip().lower()
            val = str(ws.cell(r, 2).value or '').strip()
            if param and param not in ['activo', 'inactivo']:
                cfg[param] = val
        return cfg

    def save_configuracion(self, cfg_data):
        """Saves configuration key-values to Supabase configuracion table and Excel mirror."""
        # 1. Supabase Master Update
        if self.supabase_service and self.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with self.supabase_service.engine.begin() as conn:
                    for key, value in cfg_data.items():
                        k_clean = str(key).strip().lower()
                        val_str = str(value).strip()
                        conn.execute(text("DELETE FROM configuracion WHERE LOWER(clave) = :k"), {'k': k_clean})
                        conn.execute(text("""
                            INSERT INTO configuracion (clave, valor, categoria, activo, created_at)
                            VALUES (:k, :v, 'general', true, NOW())
                        """), {'k': k_clean, 'v': val_str})
            except Exception as e:
                print(f"[save_configuracion Supabase Error] {e}")

        # 2. Excel Safe Mirror
        try:
            wb = self.load_wb(data_only=False)
            if 'CONFIGURACION' not in wb.sheetnames:
                ws = wb.create_sheet('CONFIGURACION')
                ws.cell(4, 1, 'Parámetro')
                ws.cell(4, 2, 'Valor')
            else:
                ws = wb['CONFIGURACION']

            row_map = {}
            for r in range(5, ws.max_row + 1):
                p = str(ws.cell(r, 1).value or '').strip().lower()
                if p and p not in ['activo', 'inactivo']:
                    row_map[p] = r

            for key, value in cfg_data.items():
                k_clean = str(key).strip().lower()
                val_str = str(value).strip()
                if k_clean in row_map:
                    r_idx = row_map[k_clean]
                    ws.cell(r_idx, 2, val_str)
                else:
                    next_r = max(5, ws.max_row + 1)
                    ws.cell(next_r, 1, str(key).strip())
                    ws.cell(next_r, 2, val_str)
                    row_map[k_clean] = next_r

            wb.save(self.excel_path)
            self._invalidate_cache()
        except Exception as e:
            print(f"[save_configuracion Excel Warning] {e}")

        return {"status": "success", "message": "Configuración guardada exitosamente."}




