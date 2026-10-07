import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify, request, send_file, make_response, redirect, url_for, session
from data_manager import DataManager
from email_manager import EmailManager
from pdf_generator import generate_presupuesto_pdf, generate_resumen_cuenta_corriente_pdf

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'econcativo_secret_key_2026_auth')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['JSON_SORT_KEYS'] = False
try:
    app.json.sort_keys = False
except Exception:
    pass

db = DataManager()
db.init_default_users()
email_mgr = EmailManager(db)

PUBLIC_PATHS = ['/login', '/api/login', '/favicon.ico', '/api/health', '/api/db/status']

@app.before_request
def check_authentication():    
    path = request.path
    if path in PUBLIC_PATHS or path.startswith('/static/'):
        return None
    
    if not session.get('user_id'):
        if path.startswith('/api/'):
            return jsonify({"status": "error", "message": "Acceso no autorizado o sesión expirada. Inicie sesión.", "session_expired": True}), 401
        return redirect(url_for('login_page', expired=1))
    
    session.modified = True

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    payload = request.json or {}
    username = payload.get('username')
    password = payload.get('password')

    user = db.authenticate_user(username, password)
    if user:
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['nombre']
        session['user_role'] = user['rol']
        return jsonify({"status": "success", "user": user})

    return jsonify({"status": "error", "message": "Usuario o contraseña incorrectos."}), 401

@app.route('/logout')
@app.route('/api/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
def index():
    user_name = session.get('user_name', 'Ailen Avalle')
    user_role = session.get('user_role', 'Administrador')
    return render_template('index.html', user_name=user_name, user_role=user_role)

@app.route('/api/manual_pdf')
def api_pdf_manual_instructivo():
    try:
        pdf_path = os.path.join(os.path.dirname(__file__), "Instructivo_Manual_ECONCATIVO.pdf")
        if not os.path.exists(pdf_path):
            return jsonify({"status": "error", "message": "Manual instructivo no encontrado."}), 404
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=False, download_name='Instructivo_Manual_ECONCATIVO.pdf')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.static_folder, 'favicon.ico'), mimetype='image/vnd.microsoft.icon')

@app.route('/api/health')
def health():
    return jsonify({
        "service": "ECONCATIVO Management System",
        "status": "healthy",
        "version": "1.5.0"
    })

@app.route('/api/db/status')
def api_db_status():
    is_sb = False
    if hasattr(db, 'supabase_service') and db.supabase_service:
        is_sb = db.supabase_service.is_connected()
    return jsonify({
        "status": "success",
        "engine": "Supabase PostgreSQL" if is_sb else "Excel Local (Fallback)",
        "supabase_connected": is_sb
    })


@app.route('/api/dashboard')
def api_dashboard():
    try:
        anio = request.args.get('anio', 'todos')
        data = db.get_dashboard_data(anio=anio)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/masters')
def api_masters():
    try:
        masters = db.get_master_lists()
        return jsonify({"status": "success", "data": masters})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categorias/add', methods=['POST'])
def api_add_categoria():
    try:
        data = request.get_json() or {}
        cat_name = data.get('categoria')
        res = db.add_categoria(cat_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sheet/<sheet_name>')
def api_get_sheet(sheet_name):
    try:
        s_upper = sheet_name.upper()
        if s_upper == 'USUARIOS':
            if session.get('user_role') != 'Administrador':
                return jsonify({"status": "error", "message": "Acceso restringido únicamente a usuarios con rol Administrador."}), 403
            headers = ['ID usuario', 'Nombre completo', 'Usuario', 'Rol', 'Estado', 'Último acceso']
            users = db.get_usuarios()
            rows = []
            for u in users:
                rows.append({
                    'ID usuario': u['id_usuario'],
                    'Nombre completo': u['nombre_completo'],
                    'Usuario': u['usuario'],
                    'Rol': u['rol'],
                    'Estado': u['estado'],
                    'Último acceso': u['ultimo_acceso']
                })
            return jsonify({"status": "success", "headers": headers, "rows": rows})

        headers, rows = db.get_sheet_data(s_upper)
        return jsonify({"status": "success", "headers": headers, "rows": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# PRESUPUESTOS ENDPOINTS
@app.route('/api/presupuestos', methods=['GET'])
def api_get_presupuestos():
    try:
        headers, rows = db.get_presupuestos()
        return jsonify({"status": "success", "headers": headers, "rows": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/add', methods=['POST'])
def api_add_presupuesto():
    try:
        payload = request.json or {}
        items = payload.get('items', [])
        if not items:
            return jsonify({"status": "error", "message": "El presupuesto debe incluir al menos una actividad o ítem cotizado."}), 400
        
        subtotal = 0.0
        for idx, it in enumerate(items, 1):
            try:
                neto = float(it.get('neto', 0))
            except (ValueError, TypeError):
                return jsonify({"status": "error", "message": f"El importe neto de la actividad #{idx} no es un número válido."}), 400
            if neto < 0:
                return jsonify({"status": "error", "message": f"El importe neto de la actividad #{idx} no puede ser negativo (${neto:,.2f})."}), 400
            if neto == 0:
                return jsonify({"status": "error", "message": f"La actividad #{idx} debe tener un importe neto mayor a cero."}), 400
            
            for field, label in [('km', 'distancia (km)'), ('toneladas', 'toneladas'), ('horas', 'horas')]:
                val = it.get(field)
                if val is not None and str(val).strip() != '':
                    try:
                        if float(val) < 0:
                            return jsonify({"status": "error", "message": f"El campo {label} de la actividad #{idx} no puede ser negativo."}), 400
                    except (ValueError, TypeError):
                        pass
            subtotal += neto

        if subtotal <= 0:
            return jsonify({"status": "error", "message": "El importe total del presupuesto debe ser mayor a cero ($0.00)."}), 400

        res = db.add_presupuesto(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/update', methods=['POST'])
def api_update_presupuesto():
    try:
        payload = request.json or {}
        p_id = payload.get('id')
        if not p_id:
            return jsonify({"status": "error", "message": "ID de presupuesto requerido"}), 400

        items = payload.get('items', [])
        if items:
            subtotal = 0.0
            for idx, it in enumerate(items, 1):
                try:
                    neto = float(it.get('neto', 0))
                except (ValueError, TypeError):
                    return jsonify({"status": "error", "message": f"El importe neto de la actividad #{idx} no es un número válido."}), 400
                if neto < 0:
                    return jsonify({"status": "error", "message": f"El importe neto de la actividad #{idx} no puede ser negativo (${neto:,.2f})."}), 400
                if neto == 0:
                    return jsonify({"status": "error", "message": f"La actividad #{idx} debe tener un importe neto mayor a cero."}), 400
                
                for field, label in [('km', 'distancia (km)'), ('toneladas', 'toneladas'), ('horas', 'horas')]:
                    val = it.get(field)
                    if val is not None and str(val).strip() != '':
                        try:
                            if float(val) < 0:
                                return jsonify({"status": "error", "message": f"El campo {label} de la actividad #{idx} no puede ser negativo."}), 400
                        except (ValueError, TypeError):
                            pass
                subtotal += neto

            if subtotal <= 0:
                return jsonify({"status": "error", "message": "El importe total del presupuesto debe ser mayor a cero ($0.00)."}), 400

        res = db.update_presupuesto(p_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/delete', methods=['POST'])
def api_delete_presupuesto():
    try:
        payload = request.json or {}
        p_id = payload.get('id')
        if not p_id:
            return jsonify({"status": "error", "message": "ID de presupuesto requerido"}), 400
        res = db.delete_presupuesto(p_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/aprobar', methods=['POST'])
def api_aprobar_presupuesto():
    try:
        payload = request.json or {}
        p_id = payload.get('id')
        if not p_id:
            return jsonify({"status": "error", "message": "ID de presupuesto requerido"}), 400
        res = db.aprobar_presupuesto(p_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/rechazar', methods=['POST'])
def api_rechazar_presupuesto():
    try:
        payload = request.json or {}
        p_id = payload.get('id')
        if not p_id:
            return jsonify({"status": "error", "message": "ID de presupuesto requerido"}), 400
        res = db.rechazar_presupuesto(p_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/presupuestos/<p_id>/pdf')
def api_pdf_presupuesto(p_id):
    try:
        headers, rows = db.get_presupuestos()
        target = None
        for r in rows:
            if str(r.get('ID presupuesto', '')).strip() == str(p_id).strip():
                target = r
                break
        
        pdata = {
            "id": p_id,
            "fecha": target.get('Fecha', '') if target else '',
            "cliente": target.get('Cliente', 'Cliente') if target else 'Cliente',
            "cuit": target.get('CUIT', '') if target else '',
            "validez": target.get('Validez', '15 días') if target else '15 días',
            "forma_pago": target.get('Forma pago', 'Cuenta Corriente') if target else 'Cuenta Corriente',
            "detalle": target.get('Detalle/Concepto', 'Servicio Cotizado') if target else 'Servicio Cotizado',
            "total": float(target.get('Total', 0)) if target else 0.0,
            "iva_pct": float(target.get('IVA %')) if (target and target.get('IVA %') is not None and str(target.get('IVA %')).strip() != '') else 21.0,
            "observaciones": target.get('Observaciones', '') if target else ''
        }

        items_str = str(target.get('Items JSON', '') or target.get('items_json', '') or target.get('ID viaje asociado / Items JSON', '') or target.get('ID viaje asociado', '') or '').strip() if target else ''
        if items_str and items_str.startswith('['):
            import json
            try:
                pdata['items'] = json.loads(items_str)
            except Exception:
                pass

        pdf_bytes = generate_presupuesto_pdf(pdata)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Presupuesto_{p_id}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ingresos/<target_id>/recibo_pdf')
def api_pdf_recibo(target_id):
    try:
        from pdf_generator import generate_recibo_pdf
        rdata = db.get_recibo_data(target_id)
        if not rdata:
            return jsonify({"status": "error", "message": f"Registro de cobro o recibo {target_id} no encontrado."}), 404

        pdf_bytes = generate_recibo_pdf(rdata)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"inline; filename=Recibo_{rdata.get('recibo_id', target_id)}.pdf"
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# VIAJES ENDPOINTS
@app.route('/api/viajes/add', methods=['POST'])
def api_add_viaje():
    try:
        payload = request.json or {}
        res = db.add_viaje(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/update', methods=['POST'])
def api_update_viaje():
    try:
        payload = request.json or {}
        v_id = payload.get('id')
        if not v_id:
            return jsonify({"status": "error", "message": "ID de viaje requerido"}), 400
        res = db.update_viaje(v_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/finalizar', methods=['POST'])
def api_finalizar_viaje():
    try:
        payload = request.json or {}
        v_id = payload.get('id')
        if not v_id:
            return jsonify({"status": "error", "message": "ID de viaje requerido"}), 400
        res = db.finalizar_viaje(v_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/add_adelanto', methods=['POST'])
def api_add_adelanto_viaje():
    try:
        payload = request.json or {}
        v_id = payload.get('viaje_id') or payload.get('id')
        if not v_id:
            return jsonify({"status": "error", "message": "ID de viaje requerido"}), 400
        fecha = payload.get('fecha')
        monto = payload.get('monto')
        medio_pago = payload.get('medio_pago')
        cuenta_tesoreria = payload.get('cuenta_tesoreria', '')
        comprobante = payload.get('comprobante', '')
        observaciones = payload.get('observaciones', '')
        res = db.add_adelanto_viaje(v_id, fecha, monto, medio_pago, comprobante, observaciones, cuenta_tesoreria=cuenta_tesoreria)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/add_adicional', methods=['POST'])
def api_add_adicional_viaje():
    try:
        payload = request.json or {}
        v_id = payload.get('viaje_id') or payload.get('id')
        if not v_id:
            return jsonify({"status": "error", "message": "ID de viaje requerido"}), 400
        concepto = payload.get('concepto')
        monto = payload.get('monto')
        res = db.add_adicional_viaje(v_id, concepto, monto)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/<vid>/summary', methods=['GET'])
def api_viaje_summary(vid):
    try:
        summary = db.get_viaje_facturacion_summary(vid)
        if not summary:
            return jsonify({"status": "error", "message": f"Resumen no encontrado para viaje {vid}"}), 404
        return jsonify({"status": "success", "summary": summary})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/<vid>/resumen_pdf', methods=['GET'])
def api_viaje_resumen_pdf(vid):
    try:
        from pdf_generator import generate_resumen_facturacion_pdf
        summary = db.get_viaje_facturacion_summary(vid)
        if not summary:
            return jsonify({"status": "error", "message": f"Resumen no encontrado para viaje {vid}"}), 404
        pdf_bytes = generate_resumen_facturacion_pdf(summary)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Resumen_Facturacion_{vid}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/delete', methods=['POST'])
def api_delete_viaje():
    try:
        payload = request.json or {}
        v_id = payload.get('id')
        if not v_id:
            return jsonify({"status": "error", "message": "ID de viaje requerido"}), 400
        res = db.delete_viaje(v_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/viajes/<vid>/pdf', methods=['GET'])
def api_pdf_viaje(vid):
    try:
        from pdf_generator import generate_viaje_pdf
        row = db.get_viaje_by_id(vid)
        if not row:
            return jsonify({"status": "error", "message": f"Registro de Operación {vid} no encontrado"}), 404
        
        origen_val = str(row.get('Origen', '') or '').strip()
        destino_val = str(row.get('Destino', '') or '').strip()

        # If Origen or Destino is 'POR DEFINIR' or missing, attempt to recover from linked Presupuesto
        if origen_val in ('', 'POR DEFINIR', '-') or destino_val in ('', 'POR DEFINIR', '-'):
            carga_str = str(row.get('Carga', ''))
            import re
            m = re.search(r'PRE-\d+', carga_str)
            if m:
                p_id = m.group(0)
                try:
                    _, p_rows = db.get_presupuestos()
                    for p in p_rows:
                        if str(p.get('ID presupuesto', '')).strip() == p_id:
                            p_items_str = str(p.get('Items JSON', '') or p.get('items_json', '') or p.get('ID viaje asociado', '') or '').strip()
                            if p_items_str and p_items_str.startswith('['):
                                import json
                                p_items = json.loads(p_items_str)
                                for pit in p_items:
                                    if pit.get('origen') and origen_val in ('', 'POR DEFINIR', '-'):
                                        origen_val = str(pit.get('origen')).strip()
                                    if pit.get('destino') and destino_val in ('', 'POR DEFINIR', '-'):
                                        destino_val = str(pit.get('destino')).strip()
                                    if pit.get('ubicacion') and origen_val in ('', 'POR DEFINIR', '-'):
                                        origen_val = str(pit.get('ubicacion')).strip()
                                        destino_val = str(pit.get('ubicacion')).strip()
                except Exception:
                    pass

        vdata = {
            "id": vid,
            "tipo": row.get('Actividad', ''),
            "fecha_emision": row.get('Fecha salida', datetime.now().strftime('%d/%m/%Y')),
            "fecha_salida": row.get('Fecha salida', datetime.now().strftime('%d/%m/%Y')),
            "chofer": row.get('Chofer', 'POR ASIGNAR'),
            "unidad": row.get('Unidad', 'POR ASIGNAR'),
            "cliente": row.get('Cliente', '-'),
            "origen": origen_val if origen_val else '-',
            "destino": destino_val if destino_val else '-',
            "carga": row.get('Carga', '-'),
            "remito": row.get('N° remito', row.get('Remito', 'PENDIENTE')),
            "observaciones": row.get('Observaciones', '')
        }
        
        pdf_bytes = generate_viaje_pdf(vdata)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Hoja_de_Ruta_{vid}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ingresos/pasar_a_ingresos', methods=['POST'])
def api_pasar_a_ingresos():
    try:
        payload = request.json or {}
        i_id = payload.get('id')
        if not i_id:
            return jsonify({"status": "error", "message": "ID de ingreso requerido"}), 400
        res = db.pasar_a_ingresos(i_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# MASTER ADDERS ENDPOINTS
@app.route('/api/maestros/cliente/add', methods=['POST'])
def api_add_cliente():
    try:
        payload = request.json or {}
        res = db.add_cliente(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/cliente/update', methods=['POST'])
def api_update_cliente():
    try:
        payload = request.json or {}
        c_id = payload.get('id') or payload.get('id_cliente')
        res = db.update_cliente(c_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/cliente/delete', methods=['POST'])
def api_delete_cliente():
    try:
        payload = request.json or {}
        c_id = payload.get('id') or payload.get('id_cliente')
        res = db.delete_cliente(c_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/unidad/add', methods=['POST'])
def api_add_unidad():
    try:
        payload = request.json or {}
        patente = str(payload.get('patente') or '').strip().upper().replace(' ', '')
        if patente and len(patente) > 7:
            return jsonify({"status": "error", "message": "La patente no puede tener más de 7 caracteres (máximo admitido en Argentina)."}), 400
        payload['patente'] = patente
        res = db.add_unidad(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/unidad/update', methods=['POST'])
def api_update_unidad():
    try:
        payload = request.json or {}
        u_id = payload.get('id')
        if not u_id:
            return jsonify({"status": "error", "message": "ID de unidad requerido"}), 400
        patente = str(payload.get('patente') or '').strip().upper().replace(' ', '')
        if patente and len(patente) > 7:
            return jsonify({"status": "error", "message": "La patente no puede tener más de 7 caracteres (máximo admitido en Argentina)."}), 400
        payload['patente'] = patente
        res = db.update_unidad(u_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/unidad/delete', methods=['POST'])
def api_delete_unidad():
    try:
        payload = request.json or {}
        u_id = payload.get('id')
        if not u_id:
            return jsonify({"status": "error", "message": "ID de unidad requerido"}), 400
        res = db.delete_unidad(u_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/empleado/add', methods=['POST'])
def api_add_empleado():
    try:
        payload = request.json or {}
        comision_pct = payload.get('comision_pct')
        if comision_pct is not None and str(comision_pct).strip() != '':
            try:
                c_val = float(comision_pct)
                if c_val < 0 or c_val > 100:
                    return jsonify({"status": "error", "message": "El porcentaje de comisión debe estar entre 0% y 100%."}), 400
                payload['comision_pct'] = round(min(100.0, max(0.0, c_val)), 2)
            except (ValueError, TypeError):
                payload['comision_pct'] = 0.0
        res = db.add_empleado(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/empleado/update', methods=['POST'])
def api_update_empleado():
    try:
        payload = request.json or {}
        e_id = payload.get('id')
        if not e_id:
            return jsonify({"status": "error", "message": "ID de empleado requerido"}), 400
        comision_pct = payload.get('comision_pct')
        if comision_pct is not None and str(comision_pct).strip() != '':
            try:
                c_val = float(comision_pct)
                if c_val < 0 or c_val > 100:
                    return jsonify({"status": "error", "message": "El porcentaje de comisión debe estar entre 0% y 100%."}), 400
                payload['comision_pct'] = round(min(100.0, max(0.0, c_val)), 2)
            except (ValueError, TypeError):
                payload['comision_pct'] = 0.0
        res = db.update_empleado(e_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/empleado/delete', methods=['POST'])
def api_delete_empleado():
    try:
        payload = request.json or {}
        e_id = payload.get('id')
        if not e_id:
            return jsonify({"status": "error", "message": "ID de empleado requerido"}), 400
        res = db.delete_empleado(e_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/empleado/estado', methods=['POST'])
def api_toggle_empleado_estado():
    try:
        payload = request.json or {}
        e_id = payload.get('id')
        nuevo_estado = payload.get('estado', 'Baja')
        if not e_id:
            return jsonify({"status": "error", "message": "ID de empleado requerido"}), 400
        res = db.update_empleado(e_id, {'estado': nuevo_estado})
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/empleado/liquidaciones', methods=['GET'])
def api_liquidaciones_empleados():
    try:
        quincena = request.args.get('quincena', 'todas')
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        fecha_desde = request.args.get('fecha_desde') or request.args.get('desde')
        fecha_hasta = request.args.get('fecha_hasta') or request.args.get('hasta')
        liquidaciones = db.get_liquidaciones_personal(
            quincena=quincena, mes=mes, anio=anio, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
        )
        return jsonify({"status": "success", "data": liquidaciones})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/novedades', methods=['GET'])
def api_get_novedades_personal():
    try:
        quincena = request.args.get('quincena', 'todas')
        empleado = request.args.get('empleado')
        estado = request.args.get('estado')
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        fecha_desde = request.args.get('fecha_desde') or request.args.get('desde')
        fecha_hasta = request.args.get('fecha_hasta') or request.args.get('hasta')
        novedades = db.get_novedades_personal(
            quincena=quincena, empleado_nombre=empleado, estado=estado, mes=mes, anio=anio,
            fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
        )
        return jsonify({"status": "success", "data": novedades})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/novedades/add', methods=['POST'])
def api_add_novedad_personal():
    try:
        payload = request.json or {}
        res = db.add_novedad_personal(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/novedades/delete', methods=['POST'])
def api_delete_novedad_personal():
    try:
        payload = request.json or {}
        nov_id = payload.get('id') or payload.get('nov_id')
        res = db.delete_novedad_personal(nov_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/disponibles', methods=['GET'])
def api_get_cheques_disponibles():
    try:
        disponibles = db.get_available_cheques()
        return jsonify({"status": "success", "data": disponibles})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/planilla_pdf')
def api_pdf_planilla_liquidaciones():
    try:
        from pdf_generator import generate_planilla_liquidaciones_pdf
        quincena = request.args.get('quincena', 'q1')
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        fecha_desde = request.args.get('fecha_desde') or request.args.get('desde')
        fecha_hasta = request.args.get('fecha_hasta') or request.args.get('hasta')
        liquidaciones = db.get_liquidaciones_personal(
            quincena=quincena, mes=mes, anio=anio, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
        )
        
        q_labels = {
            'q1': '1ª Quincena (Días 1 al 15)',
            'q2': '2ª Quincena (Días 16 al 30/31)',
            'todas': 'Mes Completo (1ª y 2ª Quincena)'
        }
        q_label = q_labels.get(quincena, 'Período Liquidado')
        if fecha_desde and fecha_hasta:
            q_label = f"{q_label} ({fecha_desde} al {fecha_hasta})"

        pdf_bytes = generate_planilla_liquidaciones_pdf(liquidaciones, quincena_label=q_label)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Planilla_Liquidacion_Sueldos_{quincena}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/<eid>/pdf')
def api_pdf_liquidacion_individual(eid):
    try:
        from pdf_generator import generate_recibo_sueldo_pdf
        quincena = request.args.get('quincena', 'q1')
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        fecha_desde = request.args.get('fecha_desde') or request.args.get('desde')
        fecha_hasta = request.args.get('fecha_hasta') or request.args.get('hasta')
        
        item = None
        # First check in current live calculation if parameters are provided
        if fecha_desde or fecha_hasta or mes or anio or quincena:
            live_items = db.get_liquidaciones_personal(
                quincena=quincena, mes=mes, anio=anio, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
            )
            item = next((l for l in live_items if str(l.get('id_empleado')) == str(eid)), None)
            
        # Fallback to historial
        if not item:
            hist = db.get_historial_liquidaciones(
                mes=mes, anio=anio, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
            )
            item = next((h for h in hist if str(h.get('id_liquidacion')) == str(eid) or str(h.get('id_empleado')) == str(eid)), None)
            
        if not item:
            hist_all = db.get_historial_liquidaciones()
            item = next((h for h in hist_all if str(h.get('id_liquidacion')) == str(eid) or str(h.get('id_empleado')) == str(eid)), None)

        if not item:
            return jsonify({"status": "error", "message": "Liquidación no encontrada para el empleado y período seleccionados."}), 404
        
        pdf_bytes = generate_recibo_sueldo_pdf(item)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Recibo_Sueldo_{eid}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/confirmar', methods=['POST'])
def api_confirmar_liquidacion():
    try:
        payload = request.json or {}
        res = db.confirmar_liquidacion(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/historial', methods=['GET'])
def api_historial_liquidaciones():
    try:
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        fecha_desde = request.args.get('fecha_desde') or request.args.get('desde')
        fecha_hasta = request.args.get('fecha_hasta') or request.args.get('hasta')
        data = db.get_historial_liquidaciones(
            mes=mes, anio=anio, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
        )
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/liquidaciones/delete', methods=['POST'])
def api_delete_liquidacion():
    try:
        payload = request.json or {}
        lid = payload.get('id') or payload.get('id_liquidacion')
        if not lid:
            return jsonify({"status": "error", "message": "ID de liquidación requerido"}), 400
        res = db.delete_liquidacion_historica(lid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ÓRDENES DE COMPRA ENDPOINTS
@app.route('/api/ordenes_compra', methods=['GET'])
def api_get_ordenes_compra():
    try:
        rows = db.get_ordenes_compra()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ordenes_compra/add', methods=['POST'])
def api_add_orden_compra():
    try:
        payload = request.json or {}
        res = db.add_orden_compra(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ordenes_compra/update', methods=['POST'])
def api_update_orden_compra():
    try:
        payload = request.json or {}
        oid = payload.get('id')
        if not oid:
            return jsonify({"status": "error", "message": "ID de orden de compra requerido"}), 400
        res = db.update_orden_compra(oid, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ordenes_compra/confirmar_pago', methods=['POST'])
def api_confirmar_pago_orden_compra():
    try:
        payload = request.json or {}
        oid = payload.get('id')
        if not oid:
            return jsonify({"status": "error", "message": "ID de orden de compra requerido"}), 400
        res = db.confirmar_pago_orden_compra(oid, pdata=payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ordenes_compra/delete', methods=['POST'])
def api_delete_orden_compra():
    try:
        payload = request.json or {}
        oid = payload.get('id')
        if not oid:
            return jsonify({"status": "error", "message": "ID de orden de compra requerido"}), 400
        res = db.delete_orden_compra(oid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/proveedor/resumen_pdf', methods=['GET'])
def api_proveedor_resumen_pdf():
    try:
        from pdf_generator import generate_resumen_proveedor_pdf
        prov_nombre = request.args.get('proveedor')
        if not prov_nombre:
            return jsonify({"status": "error", "message": "Nombre de proveedor requerido"}), 400

        mes = request.args.get('mes', 'todas')
        anio = request.args.get('anio', 'todos')

        summary = db.get_proveedor_summary(prov_nombre, mes=mes, anio=anio)
        pdf_bytes = generate_resumen_proveedor_pdf(summary)

        safe_name = prov_nombre.replace(' ', '_').replace('/', '_')
        period_str = str(summary.get('periodo_label', 'Todas')).replace(' ', '_')

        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Resumen_Proveedor_{safe_name}_{period_str}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/proveedores/saldo/<path:prov_nombre>')
def api_get_proveedor_saldo(prov_nombre):
    try:
        if not prov_nombre:
            return jsonify({"status": "error", "message": "Nombre de proveedor requerido"}), 400
        summary = db.get_proveedor_summary(prov_nombre)
        saldo_val = summary.get('saldo', 0.0)
        saldo_favor = summary.get('saldo_favor', 0.0)
        saldo_deudor = summary.get('saldo_deudor', 0.0)
        return jsonify({
            "status": "success",
            "proveedor": prov_nombre,
            "saldo_consolidado": saldo_val,
            "saldo_favor": saldo_favor,
            "saldo_adeudado": saldo_deudor,
            "tot_comprado": summary.get('total_comprado', 0.0),
            "tot_pagado": summary.get('total_pagado', 0.0),
            "estado_label": summary.get('saldo_label', '')
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ordenes_compra/<oid>/pdf')
def api_pdf_orden_compra(oid):
    try:
        from pdf_generator import generate_orden_compra_pdf
        rows = db.get_ordenes_compra()
        target = None
        for r in rows:
            if str(r.get('ID orden', '')).strip().lower() == str(oid).strip().lower():
                target = r
                break
        
        if not target:
            return jsonify({"status": "error", "message": f"Orden de Compra {oid} no encontrada."}), 404

        odata = {
            "id": oid,
            "fecha": target.get('Fecha', datetime.now().strftime('%Y-%m-%d')),
            "proveedor": target.get('Proveedor', 'Proveedor'),
            "cuit": target.get('CUIT proveedor', ''),
            "tipo_insumo": target.get('Tipo insumo', 'Insumos Generales'),
            "unidad": target.get('Unidad', 'General'),
            "detalle": target.get('Detalle', ''),
            "neto": db._to_float(target.get('Neto')),
            "iva_pct": db._to_float(target.get('IVA %'), 21.0) if (target.get('IVA %') is not None and str(target.get('IVA %')).strip() != '') else 21.0,
            "total": db._to_float(target.get('Total')),
            "forma_pago": target.get('Forma pago', 'Cuenta Corriente 30 días'),
            "estado": target.get('Estado', 'Pendiente'),
            "observaciones": target.get('Observaciones', '')
        }

        pdf_bytes = generate_orden_compra_pdf(odata)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Orden_Compra_{oid}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# CHEQUES ENDPOINTS
@app.route('/api/cheques', methods=['GET'])
def api_get_cheques():
    try:
        data = db.get_cheques()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/update', methods=['POST'])
def api_update_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.update_cheque(cid, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/usar', methods=['POST'])
def api_usar_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.usar_cheque(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/revertir', methods=['POST'])
def api_revertir_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.revertir_uso_cheque(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/regularizar', methods=['POST'])
def api_regularizar_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.regularizar_cheque(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/representar', methods=['POST'])
def api_representar_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.representar_cheque(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/incobrable', methods=['POST'])
def api_incobrable_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.marcar_incobrable_cheque(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/delete', methods=['POST'])
def api_delete_cheque():
    try:
        payload = request.json or {}
        cid = payload.get('id')
        if not cid:
            return jsonify({"status": "error", "message": "ID de cheque requerido"}), 400
        res = db.delete_cheque(cid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# CUENTAS CORRIENTES DE CLIENTES ENDPOINTS
@app.route('/api/cuentas_corrientes/<path:cliente_nombre>', methods=['GET'])
def api_get_cuenta_corriente(cliente_nombre):
    try:
        f_desde = request.args.get('fecha_desde')
        f_hasta = request.args.get('fecha_hasta')
        res = db.get_cuenta_corriente_cliente(cliente_nombre, f_desde, f_hasta)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cuentas_corrientes/<path:cliente_nombre>/unpaid_invoices', methods=['GET'])
def api_unpaid_invoices_cuenta_corriente(cliente_nombre):
    try:
        invoices = db.get_unpaid_invoices_client(cliente_nombre)
        return jsonify({"status": "success", "data": invoices})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cuentas_corrientes/pago', methods=['POST'])
def api_add_pago_cuenta_corriente():
    try:
        payload = request.json or {}
        res = db.add_pago_cuenta_corriente(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cuentas_corrientes/<path:cliente_nombre>/pdf', methods=['GET'])
def api_pdf_cuenta_corriente(cliente_nombre):
    try:
        f_desde = request.args.get('fecha_desde')
        f_hasta = request.args.get('fecha_hasta')
        cc_data = db.get_cuenta_corriente_cliente(cliente_nombre, f_desde, f_hasta)
        pdf_bytes = generate_resumen_cuenta_corriente_pdf(cc_data)
        
        response = make_response(pdf_bytes)
        safe_name = str(cliente_nombre).replace(' ', '_').replace('/', '_')
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Resumen_Cuenta_Corriente_{safe_name}.pdf'
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/proveedor/add', methods=['POST'])
def api_add_proveedor():
    try:
        payload = request.json or {}
        razon = str(payload.get('razon_social', '')).strip()
        rubro = str(payload.get('rubro', '')).strip()
        cuit = str(payload.get('cuit', '')).strip()
        clean_cuit = re.sub(r'\D', '', cuit)

        if not razon:
            return jsonify({"status": "error", "message": "La Razón Social del proveedor es obligatoria.", "field": "razon"}), 400
        if not rubro:
            return jsonify({"status": "error", "message": "El Tipo de Proveedor / Rubro es obligatorio.", "field": "rubro"}), 400
        if not clean_cuit or len(clean_cuit) != 11:
            return jsonify({"status": "error", "message": "El CUIT / CUIL del proveedor es obligatorio y debe contener exactamente 11 dígitos numéricos.", "field": "cuit"}), 400

        payload['cuit'] = f"{clean_cuit[:2]}-{clean_cuit[2:10]}-{clean_cuit[10:]}"
        payload['razon_social'] = razon
        payload['rubro'] = rubro

        res = db.add_proveedor(payload)
        if res.get('status') == 'error':
            return jsonify(res), 400
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/proveedor/update', methods=['POST'])
def api_update_proveedor():
    try:
        payload = request.json or {}
        p_id = payload.get('id') or payload.get('id_proveedor')
        if not p_id:
            return jsonify({"status": "error", "message": "ID de proveedor requerido."}), 400

        razon = str(payload.get('razon_social', '')).strip()
        rubro = str(payload.get('rubro', '')).strip()
        cuit = str(payload.get('cuit', '')).strip()
        clean_cuit = re.sub(r'\D', '', cuit)

        if not razon:
            return jsonify({"status": "error", "message": "La Razón Social del proveedor es obligatoria.", "field": "razon"}), 400
        if not rubro:
            return jsonify({"status": "error", "message": "El Tipo de Proveedor / Rubro es obligatorio.", "field": "rubro"}), 400
        if not clean_cuit or len(clean_cuit) != 11:
            return jsonify({"status": "error", "message": "El CUIT / CUIL del proveedor es obligatorio y debe contener exactamente 11 dígitos numéricos.", "field": "cuit"}), 400

        payload['cuit'] = f"{clean_cuit[:2]}-{clean_cuit[2:10]}-{clean_cuit[10:]}"
        payload['razon_social'] = razon
        payload['rubro'] = rubro

        res = db.update_proveedor(p_id, payload)
        if res.get('status') == 'error':
            return jsonify(res), 400
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/proveedor/delete', methods=['POST'])
def api_delete_proveedor():
    try:
        payload = request.json or {}
        p_id = payload.get('id') or payload.get('id_proveedor')
        res = db.delete_proveedor(p_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# USUARIOS DEL SISTEMA ENDPOINTS (Solo Administradores)
@app.route('/api/maestros/usuario/add', methods=['POST'])
def api_add_usuario():
    try:
        if session.get('user_role') != 'Administrador':
            return jsonify({"status": "error", "message": "Acceso restringido: Solo un Administrador puede crear usuarios."}), 403
        payload = request.json or {}
        res = db.add_usuario(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/usuario/change_password', methods=['POST'])
def api_change_password_usuario():
    try:
        if session.get('user_role') != 'Administrador':
            return jsonify({"status": "error", "message": "Acceso restringido: Solo un Administrador puede cambiar contraseñas."}), 403
        payload = request.json or {}
        uid = payload.get('id_usuario') or payload.get('id')
        pwd = payload.get('password') or payload.get('new_password')
        res = db.update_usuario_password(uid, pwd)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/usuario/toggle_estado', methods=['POST'])
def api_toggle_estado_usuario():
    try:
        if session.get('user_role') != 'Administrador':
            return jsonify({"status": "error", "message": "Acceso restringido: Solo un Administrador puede modificar estados de usuario."}), 403
        payload = request.json or {}
        uid = payload.get('id_usuario') or payload.get('id')
        current_uid = session.get('user_id')
        res = db.toggle_usuario_estado(uid, current_uid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maestros/usuario/delete', methods=['POST'])
def api_delete_usuario():
    try:
        if session.get('user_role') != 'Administrador':
            return jsonify({"status": "error", "message": "Acceso restringido: Solo un Administrador puede eliminar usuarios."}), 403
        payload = request.json or {}
        uid = payload.get('id_usuario') or payload.get('id')
        current_uid = session.get('user_id')
        res = db.delete_usuario(uid, current_uid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# INGRESOS & EGRESOS ADDERS
@app.route('/api/ingresos/factura/update', methods=['POST'])
@app.route('/api/ingresos/factura/add', methods=['POST'])
@app.route('/api/ingresos/add', methods=['POST'])
def api_update_ingreso_factura():
    try:
        payload = request.json or {}
        i_id = payload.get('id')
        if not i_id:
            res = db.add_ingreso_factura(payload)
            return jsonify(res)
        res = db.update_ingreso_factura(i_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ingresos/cobro/add', methods=['POST'])
def api_registrar_cobro_ingreso():
    try:
        payload = request.json or {}
        i_id = payload.get('id')
        if not i_id:
            return jsonify({"status": "error", "message": "ID de ingreso requerido"}), 400
        res = db.registrar_cobro_ingreso(i_id, payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ingresos/add', methods=['POST'])
def api_add_ingreso():
    try:
        payload = request.json or {}
        wb = db.load_wb(data_only=False)
        ws = wb['INGRESOS']
        next_row = ws.max_row + 1
        new_id = f"ING-{next_row - 4:06d}"
        
        cliente = payload.get('cliente', '')
        cuit = payload.get('cuit', '')
        if not cuit:
            try:
                masters = db.get_master_lists()
                cli_info = masters.get('clientes_dict', {}).get(cliente, {})
                cuit = cli_info.get('cuit', '')
            except Exception:
                cuit = ''

        tipo_comp = payload.get('tipo_comprobante', 'Factura A')
        nro_fact = payload.get('nro_factura', '')
        fecha = payload.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        concepto = payload.get('concepto', 'Servicio de Flete')
        neto = float(payload.get('neto', 0))
        raw_iva = payload.get('iva_pct')
        iva_pct = float(raw_iva) if (raw_iva is not None and str(raw_iva).strip() != '') else 21.0
        iva = neto * (iva_pct / 100.0)
        total = float(payload.get('total', 0))
        if total <= 0:
            total = neto + iva

        est_cobro = payload.get('estado_cobro', 'PENDIENTE')
        imp_cobrado = 0.0
        saldo_remanente = total
        
        # Auto-absorb Saldo a Favor if client has credit balance in C/C
        try:
            cc_info = db.get_cuenta_corriente_cliente(cliente)
            saldo_cc = cc_info.get('saldo_final', 0.0)
            if saldo_cc < 0 and total > 0:
                saldo_favor = abs(saldo_cc)
                imp_cobrado = min(total, saldo_favor)
                saldo_remanente = max(0.0, total - imp_cobrado)
                if imp_cobrado >= total:
                    est_cobro = 'COBRADO'
                else:
                    est_cobro = 'COBRADO PARCIAL'
        except Exception:
            pass

        row_dict = {
            1: new_id,
            2: fecha,
            3: tipo_comp,
            4: '0001',
            5: nro_fact,
            6: cliente,
            7: cuit,
            8: concepto,
            9: payload.get('chofer', ''),
            10: payload.get('unidad', ''),
            11: 0,
            12: 0,
            13: neto,
            14: iva_pct,
            15: iva,
            16: total,
            17: est_cobro,
            18: imp_cobrado,
            19: fecha if imp_cobrado > 0 else '',
            20: 'Saldo a Favor C/C' if imp_cobrado > 0 else '',
            21: saldo_remanente,
            22: 'CC-AUTO-ABSORB' if imp_cobrado > 0 else '',
            28: payload.get('observaciones', '')
        }
        for col_idx, val in row_dict.items():
            ws.cell(next_row, col_idx, val)

        wb.save(db.excel_path)
        return jsonify({"status": "success", "id": new_id, "estado": est_cobro, "cobrado": imp_cobrado})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/egresos/add', methods=['POST'])
def api_add_egreso():
    try:
        payload = request.json or {}
        wb = db.load_wb(data_only=False)
        ws = wb['EGRESOS']
        
        max_egr_num = 0
        for r_idx in range(5, ws.max_row + 1):
            ev = str(ws.cell(r_idx, 1).value or '').strip()
            if ev.startswith('EGR-'):
                try:
                    num = int(ev.split('-')[-1])
                    if num > max_egr_num:
                        max_egr_num = num
                except Exception:
                    pass

        # Check Supabase for max ID as well to guarantee consistency
        if db.supabase_service and db.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                with db.supabase_service.engine.connect() as conn:
                    max_id_rows = conn.execute(text("SELECT id_egreso FROM egresos WHERE id_egreso LIKE 'EGR-%'")).fetchall()
                    for (eid_val,) in max_id_rows:
                        try:
                            num = int(str(eid_val).split('-')[-1])
                            if num > max_egr_num:
                                max_egr_num = num
                        except Exception:
                            pass
            except Exception as e:
                print(f"[api_add_egreso Supabase ID Error] {e}")

        new_id = f"EGR-{max_egr_num + 1:06d}"
        
        next_row = ws.max_row + 1
        fecha_val = payload.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        total_val = float(payload.get('total', 0))
        if total_val <= 0:
            return jsonify({"status": "error", "message": "El importe total del egreso debe ser mayor a 0."}), 400

        litros_val = payload.get('cantidad_litros', '')
        if litros_val not in (None, ''):
            try:
                litros_num = float(str(litros_val).replace(',', '.'))
                if litros_num < 0:
                    return jsonify({"status": "error", "message": "La cantidad de litros no puede ser un valor negativo."}), 400
            except ValueError:
                pass

        est_pago = payload.get('estado_pago', 'Pagado')
        prov_val = payload.get('proveedor', '')
        cheque_id = str(payload.get('cheque_id') or '').strip()
        cuenta_tes = payload.get('cuenta_tesoreria') or payload.get('medio_pago', 'Efectivo')

        saldo_favor_aplicado = float(payload.get('saldo_favor_aplicado', 0))
        monto_neto_desembolso = float(payload.get('monto_neto_desembolso', total_val)) if cuenta_tes != 'Saldo a Favor C/C' else 0.0

        if saldo_favor_aplicado > 0:
            imp_pagado = round(monto_neto_desembolso, 2)
            if monto_neto_desembolso == 0:
                cuenta_tes = 'Saldo a Favor C/C'
            elif 'Saldo a Favor' not in cuenta_tes:
                cuenta_tes = f"{cuenta_tes} (Neto: ${monto_neto_desembolso:,.2f} | Saldo Favor C/C: ${saldo_favor_aplicado:,.2f})"
        else:
            imp_pagado = total_val if est_pago.lower() == 'pagado' else 0.0

        # Enforce cash / treasury funds availability validation
        if imp_pagado > 0:
            is_valid, disp_amt, acc_name, err_msg = db.validate_treasury_disponibilidad(cuenta_tes, imp_pagado)
            if not is_valid:
                return jsonify({"status": "error", "message": err_msg}), 400

        saldo_rem = 0.0 if est_pago.lower() == 'pagado' else max(0.0, total_val - imp_pagado)

        nro_cheque = ''
        monto_cheque = 0.0
        if cheque_id and 'CHEQUES' in wb.sheetnames:
            ws_chq = wb['CHEQUES']
            target_chq_row = None
            for r in range(5, ws_chq.max_row + 1):
                if str(ws_chq.cell(r, 1).value or '').strip() == str(cheque_id).strip():
                    target_chq_row = r
                    break
            if target_chq_row:
                nro_cheque = str(ws_chq.cell(target_chq_row, 8).value or '')
                monto_cheque = db._to_float(ws_chq.cell(target_chq_row, 4).value)
                ws_chq.cell(target_chq_row, 5, prov_val)
                ws_chq.cell(target_chq_row, 10, prov_val)
                ws_chq.cell(target_chq_row, 11, 'Entregado Proveedor')
                ws_chq.cell(target_chq_row, 12, f"Pago Egreso {new_id} - {prov_val}")
                ws_chq.cell(target_chq_row, 13, fecha_val)
                ws_chq.cell(target_chq_row, 14, new_id)
                cuenta_tes = f"Cheque N° {nro_cheque}" if nro_cheque else f"Cheque {cheque_id}"

        row_dict = {
            1: new_id,
            2: fecha_val,
            3: fecha_val,
            4: payload.get('categoria', 'Combustible'),
            5: payload.get('subcategoria', ''),
            6: prov_val,
            7: payload.get('cuit', ''),
            8: payload.get('tipo_comprobante', 'Factura / Comprobante'),
            9: payload.get('nro_comprobante', ''),
            10: payload.get('unidad', ''),
            11: payload.get('empleado', payload.get('chofer', '')),
            12: payload.get('detalle', payload.get('observaciones', 'Gasto operativo')),
            13: litros_val,
            14: total_val,
            15: 0.0,
            16: total_val,
            17: est_pago,
            18: imp_pagado,
            19: fecha_val if imp_pagado > 0 else '',
            20: cuenta_tes,
            21: cheque_id or 0,
            24: payload.get('observaciones', '')
        }

        for col_idx, val in row_dict.items():
            ws.cell(next_row, col_idx, val)

        # Inserción directa y síncrona en Supabase PostgreSQL
        if db.supabase_service and db.supabase_service.is_connected():
            from sqlalchemy import text
            try:
                litros_float_val = None
                if litros_val not in (None, ''):
                    try:
                        litros_float_val = float(str(litros_val).replace(',', '.'))
                    except Exception:
                        pass

                with db.supabase_service.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO egresos (
                            id_egreso, fecha_comprobante, fecha_vencimiento, categoria, subcategoria,
                            proveedor, cuit, tipo_comprobante, nro_comprobante, unidad,
                            empleado, descripcion, cantidad_litros, neto, iva,
                            total, estado_pago, importe_pagado, fecha_pago, medio_pago,
                            saldo, observaciones, updated_at
                        ) VALUES (
                            :id, :fecha, :fecha, :cat, :subcat,
                            :prov, :cuit, :tipo_comp, :nro_comp, :unidad,
                            :emp, :desc, :litros, :neto, :iva,
                            :total, :estado, :pagado, :fpago, :medio,
                            :saldo, :obs, NOW()
                        )
                        ON CONFLICT (id_egreso) DO UPDATE SET
                            fecha_comprobante = EXCLUDED.fecha_comprobante,
                            fecha_vencimiento = EXCLUDED.fecha_vencimiento,
                            categoria = EXCLUDED.categoria,
                            subcategoria = EXCLUDED.subcategoria,
                            proveedor = EXCLUDED.proveedor,
                            cuit = EXCLUDED.cuit,
                            tipo_comprobante = EXCLUDED.tipo_comprobante,
                            nro_comprobante = EXCLUDED.nro_comprobante,
                            unidad = EXCLUDED.unidad,
                            empleado = EXCLUDED.empleado,
                            descripcion = EXCLUDED.descripcion,
                            cantidad_litros = EXCLUDED.cantidad_litros,
                            neto = EXCLUDED.neto,
                            iva = EXCLUDED.iva,
                            total = EXCLUDED.total,
                            estado_pago = EXCLUDED.estado_pago,
                            importe_pagado = EXCLUDED.importe_pagado,
                            fecha_pago = EXCLUDED.fecha_pago,
                            medio_pago = EXCLUDED.medio_pago,
                            saldo = EXCLUDED.saldo,
                            observaciones = EXCLUDED.observaciones,
                            updated_at = NOW();
                    """), {
                        'id': new_id,
                        'fecha': fecha_val,
                        'cat': payload.get('categoria', 'Combustible'),
                        'subcat': payload.get('subcategoria', ''),
                        'prov': prov_val,
                        'cuit': payload.get('cuit', ''),
                        'tipo_comp': payload.get('tipo_comprobante', 'Factura / Comprobante'),
                        'nro_comp': payload.get('nro_comprobante', ''),
                        'unidad': payload.get('unidad', ''),
                        'emp': payload.get('empleado', payload.get('chofer', '')),
                        'desc': payload.get('detalle', payload.get('observaciones', 'Gasto operativo')),
                        'litros': litros_float_val,
                        'neto': total_val,
                        'iva': 0.0,
                        'total': total_val,
                        'estado': est_pago,
                        'pagado': imp_pagado,
                        'fpago': fecha_val if imp_pagado > 0 else None,
                        'medio': cuenta_tes,
                        'saldo': saldo_rem,
                        'obs': payload.get('observaciones', '')
                    })

                    # Si se utilizó un cheque de cartera, sincronizar su estado entregado
                    if cheque_id:
                        conn.execute(text("""
                            UPDATE cheques SET
                                endosado_tenedor = :prov,
                                estado = 'Entregado Proveedor',
                                destino_usado_en = :dest,
                                fecha_uso = :fuso,
                                id_egreso = :eid,
                                updated_at = NOW()
                            WHERE id_cheque = :cid
                        """), {
                            'prov': prov_val,
                            'dest': f"Pago Egreso {new_id} - {prov_val}",
                            'fuso': fecha_val,
                            'eid': new_id,
                            'cid': str(cheque_id).strip()
                        })
            except Exception as e:
                print(f"[api_add_egreso Supabase Direct Insert Error] {e}")

        # Handle overpayment difference if cheque amount > egreso total
        if monto_cheque > total_val and prov_val:
            diferencia = round(monto_cheque - total_val, 2)
            opcion_sobrepago = str(payload.get('opcion_sobrepago') or payload.get('vuelto_opcion') or 'saldo_favor').lower()
            vuelto_monto = float(payload.get('vuelto_monto') or diferencia)

            if ('vuelto' in opcion_sobrepago) and 'INGRESOS' in wb.sheetnames:
                ws_ing = wb['INGRESOS']
                next_ing_r = ws_ing.max_row + 1
                vuelto_cuenta = payload.get('vuelto_cuenta') or 'Caja Chica Efectivo'
                vuelto_medio = str(payload.get('vuelto_medio') or 'efectivo').lower()

                if vuelto_medio == 'cheque' and 'CHEQUES' in wb.sheetnames:
                    ws_chq = db._ensure_cheques_sheet(wb)
                    cid_vuel = db._get_next_cheque_id(ws_chq)
                    v_banco = payload.get('vuelto_chq_banco') or 'A completar'
                    v_nro = payload.get('vuelto_chq_nro') or f"CHQ-{vuelto_monto:.0f}"
                    v_emisor = payload.get('vuelto_chq_emisor') or prov_val
                    v_venc = payload.get('vuelto_chq_vencimiento') or fecha_val

                    row_chq = [
                        cid_vuel,
                        fecha_val,
                        'Cheque Físico',
                        vuelto_monto,
                        v_emisor,
                        payload.get('cuit', ''),
                        v_banco,
                        v_nro,
                        v_venc,
                        'ECONCATIVO S.A.S.',
                        'Disponible',
                        '', '', '', f"EGR-{new_id}",
                        f"Vuelto de Cheque en Egreso {new_id} ({prov_val})"
                    ]
                    ws_chq.append(row_chq)
                    medio_str = f"Cheque de Terceros N° {v_nro} ({v_banco})"
                else:
                    medio_str = f"{vuelto_cuenta} (Vuelto)"

                ws_ing.cell(next_ing_r, 1, f"ING-VUELTO-{new_id}")
                ws_ing.cell(next_ing_r, 2, fecha_val)
                ws_ing.cell(next_ing_r, 3, 'Vuelto Proveedor')
                ws_ing.cell(next_ing_r, 6, prov_val)
                ws_ing.cell(next_ing_r, 8, 'Vuelto por diferencia de pago con cheque')
                ws_ing.cell(next_ing_r, 16, vuelto_monto)
                ws_ing.cell(next_ing_r, 17, 'COBRADO')
                ws_ing.cell(next_ing_r, 18, vuelto_monto)
                ws_ing.cell(next_ing_r, 19, fecha_val)
                ws_ing.cell(next_ing_r, 20, medio_str)
                ws_ing.cell(next_ing_r, 21, 0.0)
                ws_ing.cell(next_ing_r, 28, f"Vuelto por diferencia de cheque N° {nro_cheque} (${monto_cheque:,.2f}) en Egreso {new_id} (${total_val:,.2f})")

                if db.supabase_service and db.supabase_service.is_connected():
                    from sqlalchemy import text
                    try:
                        with db.supabase_service.engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO ingresos (
                                    id_ingreso, fecha_emision, tipo_comprobante, cliente,
                                    neto, total, estado_cobro, importe_cobrado, fecha_cobro, medio_cobro,
                                    saldo, observaciones, updated_at
                                ) VALUES (
                                    :id, :fecha, 'Vuelto Proveedor', :prov,
                                    :neto, :total, 'COBRADO', :cobrado, :fcobro, :medio,
                                    0.0, :obs, NOW()
                                )
                                ON CONFLICT (id_ingreso) DO NOTHING;
                            """), {
                                'id': f"ING-VUELTO-{new_id}",
                                'fecha': fecha_val,
                                'prov': prov_val,
                                'neto': vuelto_monto,
                                'total': vuelto_monto,
                                'cobrado': vuelto_monto,
                                'fcobro': fecha_val,
                                'medio': medio_str,
                                'obs': f"Vuelto por diferencia de cheque N° {nro_cheque} (${monto_cheque:,.2f}) en Egreso {new_id} (${total_val:,.2f})"
                            })
                    except Exception as e:
                        print(f"[api_add_egreso Vuelto Supabase Error] {e}")
            else:
                # Default: Dejar como Saldo a Favor C/C con el proveedor
                cc_row = ws.max_row + 1
                cc_id = f"EGR-{max_egr_num + 2:06d}"
                cc_row_dict = {
                    1: cc_id,
                    2: fecha_val,
                    3: fecha_val,
                    4: 'Entrega a Cuenta C/C',
                    5: 'Saldo a Favor C/C',
                    6: prov_val,
                    7: payload.get('cuit', ''),
                    8: 'Comprobante Interno',
                    9: f"CC-{new_id}",
                    10: '',
                    11: '',
                    12: f"Saldo a favor C/C generado por diferencia de cheque N° {nro_cheque} (${monto_cheque:,.2f}) en Egreso {new_id} (${total_val:,.2f})",
                    13: '',
                    14: diferencia,
                    15: 0.0,
                    16: diferencia,
                    17: 'Pagado',
                    18: diferencia,
                    19: fecha_val,
                    20: f"Cheque N° {nro_cheque} (Diferencia sobrepago)",
                    21: cheque_id or 0,
                    24: f"Diferencia de cheque ${monto_cheque:,.2f} vs ${total_val:,.2f} egreso."
                }
                for c_idx, c_val in cc_row_dict.items():
                    ws.cell(cc_row, c_idx, c_val)

                if db.supabase_service and db.supabase_service.is_connected():
                    from sqlalchemy import text
                    try:
                        with db.supabase_service.engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO egresos (
                                    id_egreso, fecha_comprobante, fecha_vencimiento, categoria, subcategoria,
                                    proveedor, cuit, tipo_comprobante, nro_comprobante, unidad,
                                    empleado, descripcion, cantidad_litros, neto, iva,
                                    total, estado_pago, importe_pagado, fecha_pago, medio_pago,
                                    saldo, observaciones, updated_at
                                ) VALUES (
                                    :id, :fecha, :fecha, :cat, :subcat,
                                    :prov, :cuit, :tipo_comp, :nro_comp, '',
                                    '', :desc, NULL, :neto, 0.0,
                                    :total, 'Pagado', :pagado, :fecha, :medio,
                                    0.0, :obs, NOW()
                                )
                                ON CONFLICT (id_egreso) DO NOTHING;
                            """), {
                                'id': cc_id,
                                'fecha': fecha_val,
                                'cat': 'Entrega a Cuenta C/C',
                                'subcat': 'Saldo a Favor C/C',
                                'prov': prov_val,
                                'cuit': payload.get('cuit', ''),
                                'tipo_comp': 'Comprobante Interno',
                                'nro_comp': f"CC-{new_id}",
                                'desc': f"Saldo a favor C/C generado por diferencia de cheque N° {nro_cheque} (${monto_cheque:,.2f}) en Egreso {new_id} (${total_val:,.2f})",
                                'neto': diferencia,
                                'total': diferencia,
                                'pagado': diferencia,
                                'medio': f"Cheque N° {nro_cheque} (Diferencia sobrepago)",
                                'obs': f"Diferencia de cheque ${monto_cheque:,.2f} vs ${total_val:,.2f} egreso."
                            })
                    except Exception as e:
                        print(f"[api_add_egreso CC Supabase Error] {e}")

        wb.save(db.excel_path)
        db._invalidate_cache()
        return jsonify({"status": "success", "id": new_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/backup/download')
def download_backup_excel():
    try:
        master_file = os.path.join(app.root_path, 'operation_data.xlsx')
        if not os.path.exists(master_file):
            master_file = os.path.join(app.root_path, 'ECONCATIVO_BASE_SISTEMA.xlsx')
        return send_file(
            master_file,
            as_attachment=True,
            download_name=f"ECONCATIVO_BASE_SISTEMA_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# TESORERIA & CONCILIACION API ENDPOINTS
@app.route('/api/tesoreria/summary', methods=['GET'])
def api_tesoreria_summary():
    try:
        data = db.get_tesoreria_summary()
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/saldos_iniciales', methods=['POST'])
def api_tesoreria_saldos_iniciales():
    try:
        payload = request.json or {}
        res = db.update_saldos_iniciales_tesoreria(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/gastos_bancarios', methods=['POST'])
def api_tesoreria_gastos_bancarios():
    try:
        payload = request.json or {}
        cuenta_nombre = payload.get('cuenta_nombre')
        monto = payload.get('monto')
        if not cuenta_nombre or not monto:
            return jsonify({"status": "error", "message": "Cuenta y monto son obligatorios."}), 400
        res = db.add_gasto_bancario_tesoreria(
            cuenta_nombre=cuenta_nombre,
            monto=monto,
            fecha=payload.get('fecha'),
            concepto=payload.get('concepto'),
            observaciones=payload.get('observaciones')
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/transferencia', methods=['POST'])
def api_tesoreria_transferencia():
    try:
        payload = request.json or {}
        origen = payload.get('origen')
        destino = payload.get('destino')
        monto = payload.get('monto')
        if not origen or not destino or not monto:
            return jsonify({"status": "error", "message": "Origen, destino y monto son requeridos."}), 400
        
        # Enforce funds availability check for outgoing transfers
        is_valid, disp_amt, acc_name, err_msg = db.validate_treasury_disponibilidad(origen, monto)
        if not is_valid:
            return jsonify({"status": "error", "message": err_msg}), 400
        res = db.registrar_transferencia_tesoreria(
            origen=origen,
            destino=destino,
            monto=monto,
            fecha=payload.get('fecha'),
            concepto=payload.get('concepto'),
            observaciones=payload.get('observaciones')
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/conciliar', methods=['POST'])
def api_tesoreria_conciliar():
    try:
        payload = request.json or {}
        account_id = payload.get('account_id')
        saldo_real = payload.get('saldo_real')
        if not account_id or saldo_real is None:
            return jsonify({"status": "error", "message": "account_id y saldo_real son requeridos."}), 400
        res = db.update_saldo_real_tesoreria(
            account_id=account_id,
            saldo_real=saldo_real,
            fecha_cotejo=payload.get('fecha_cotejo')
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/account/add', methods=['POST'])
def api_tesoreria_account_add():
    try:
        payload = request.json or {}
        nombre = payload.get('nombre')
        if not nombre:
            return jsonify({"status": "error", "message": "El nombre de la cuenta es requerido."}), 400
        
        banco = str(payload.get('banco') or '').strip()
        nro_cuenta = str(payload.get('nro_cuenta') or '').strip()
        cbu_num = str(payload.get('cbu_num') or payload.get('cbu') or '').strip()
        alias = str(payload.get('alias') or '').strip()
        titular = str(payload.get('titular') or '').strip()
        cuit = str(payload.get('cuit') or '').strip()

        parts = []
        if banco:
            parts.append(f"Banco: {banco}")
        if nro_cuenta:
            parts.append(f"Cta: {nro_cuenta}")
        if cbu_num:
            parts.append(f"CBU: {cbu_num}")
        if alias:
            parts.append(f"ALIAS: {alias}")
        if titular:
            tit_str = f"Titular: {titular}"
            if cuit:
                tit_str += f" ({cuit})"
            parts.append(tit_str)

        combined_cbu = " | ".join(parts) if parts else (payload.get('cbu') or '')

        res = db.add_tesoreria_account(
            nombre=nombre,
            tipo=payload.get('tipo', 'Banco'),
            cbu=combined_cbu,
            saldo_inicial=payload.get('saldo_inicial', 0.0),
            observaciones=payload.get('observaciones', '')
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tesoreria/account/delete', methods=['POST'])
def api_tesoreria_account_delete():
    try:
        payload = request.json or {}
        account_id = payload.get('account_id')
        if not account_id:
            return jsonify({"status": "error", "message": "account_id es requerido."}), 400
        res = db.delete_tesoreria_account(account_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/emitir_propio', methods=['POST'])
def api_emitir_cheque_propio():
    try:
        payload = request.json or {}
        banco = payload.get('banco')
        monto = payload.get('monto')
        if not banco or not monto:
            return jsonify({"status": "error", "message": "Banco emisor y monto son obligatorios."}), 400
        res = db.add_cheque_propio(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cheques/marcar_debitado', methods=['POST'])
def api_marcar_cheque_debitado():
    try:
        payload = request.json or {}
        cheque_id = payload.get('cheque_id')
        if not cheque_id:
            return jsonify({"status": "error", "message": "cheque_id es requerido."}), 400
        res = db.marcar_cheque_propio_debitado(cheque_id, fecha_debito=payload.get('fecha_debito'))
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/config/smtp', methods=['GET', 'POST'])
def api_config_smtp():
    try:
        if request.method == 'POST':
            payload = request.json or {}
            res = db.save_configuracion({
                'smtp_email': payload.get('smtp_email', ''),
                'smtp_password': payload.get('smtp_password', ''),
                'telefono_administracion': payload.get('telefono_administracion', ''),
                'nombre_empresa': payload.get('nombre_empresa', 'ECONCATIVO S.A.S.')
            })
            return jsonify(res)
        else:
            cfg = db.get_configuracion()
            return jsonify({
                "status": "success",
                "data": {
                    "smtp_email": cfg.get('smtp_email') or cfg.get('correo_empresa') or '',
                    "smtp_password": cfg.get('smtp_password') or cfg.get('clave_gmail') or '',
                    "telefono_administracion": cfg.get('telefono_administracion') or cfg.get('telefono') or '',
                    "nombre_empresa": cfg.get('nombre_empresa') or 'ECONCATIVO S.A.S.'
                }
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/facturacion/send_email', methods=['POST'])
def api_send_factura_email():
    try:
        to_email = None
        subject = None
        message = None
        pdf_bytes = None
        pdf_filename = "Factura_ARCA.pdf"
        ingreso_id = None

        if request.form:
            to_email = request.form.get('to_email')
            subject = request.form.get('subject')
            message = request.form.get('message')
            ingreso_id = request.form.get('ingreso_id')
        elif request.is_json:
            payload = request.get_json(silent=True) or {}
            to_email = payload.get('to_email')
            subject = payload.get('subject')
            message = payload.get('message')
            ingreso_id = payload.get('ingreso_id')
        else:
            payload = request.get_json(silent=True) or request.form.to_dict() or {}
            to_email = payload.get('to_email') or request.form.get('to_email')
            subject = payload.get('subject') or request.form.get('subject')
            message = payload.get('message') or request.form.get('message')
            ingreso_id = payload.get('ingreso_id') or request.form.get('ingreso_id')

        if request.files and 'pdf_file' in request.files:
            pdf_file = request.files.get('pdf_file')
            if pdf_file and pdf_file.filename:
                raw_bytes = pdf_file.read()
                if raw_bytes:
                    pdf_bytes = raw_bytes
                    pdf_filename = pdf_file.filename

        if not to_email:
            return jsonify({"status": "error", "message": "Debe especificar el correo electrónico destinatario."}), 400

        # Build fresh branded HTML body with live bank accounts
        if ingreso_id:
            try:
                _, facturacion_rows = db.get_sheet_data('INGRESOS')
                target = next((r for r in facturacion_rows if str(db._get_row_prop(r, ['id_ingreso', 'ID ingreso/factura', 'ID ingreso', 'ID']) or '').strip() == str(ingreso_id).strip()), None)
                if target:
                    cliente_nombre = db._get_row_prop(target, ['cliente', 'Cliente']) or "Cliente"
                    nro_factura = db._get_row_prop(target, ['nro_factura_arca', 'N° factura ARCA', 'Factura']) or ingreso_id
                    total_val = db._get_row_prop(target, ['total', 'Total']) or 0
                    try:
                        total_val = float(total_val)
                    except (ValueError, TypeError):
                        pass
                    email_mgr.build_factura_email_template(cliente_nombre, nro_factura, total_val, message_override=message)
            except Exception as bld_err:
                print(f"[api_send_factura_email build template error] {bld_err}")

        res = email_mgr.send_email_with_pdf(
            to_email=to_email,
            subject=subject or "Factura de Venta / Comprobante - ECONCATIVO S.A.S.",
            body_text=message or "Se remite comprobante de facturación de ECONCATIVO S.A.S.",
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            html_body=email_mgr.last_html_body
        )
        return jsonify(res)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/facturacion/<target_id>/email_preview', methods=['GET'])
def api_factura_email_preview(target_id):
    try:
        _, facturacion_rows = db.get_sheet_data('INGRESOS')
        target = next((r for r in facturacion_rows if str(db._get_row_prop(r, ['id_ingreso', 'ID ingreso/factura', 'ID ingreso', 'ID']) or '').strip() == str(target_id).strip()), None)
        
        cliente_nombre = db._get_row_prop(target, ['cliente', 'Cliente']) if target else ''
        nro_factura = db._get_row_prop(target, ['nro_factura_arca', 'N° factura ARCA', 'Factura']) if target else ''
        total = db._get_row_prop(target, ['total', 'Total']) if target else 0
        try:
            total_val = float(total)
        except (ValueError, TypeError):
            total_val = total

        # Recipient email lookup from Clientes master list
        recipient_email = ""
        email_found = False
        if cliente_nombre:
            _, c_rows = db.get_sheet_data('CLIENTES')
            c_name_norm = str(cliente_nombre).strip().lower()
            match = next((c for c in c_rows if str(db._get_row_prop(c, ['razon_social', 'Razón social / Nombre', 'Razon social / Nombre', 'Razon Social', 'Nombre', 'Cliente']) or '').strip().lower() == c_name_norm), None)
            if not match:
                match = next((c for c in c_rows if c_name_norm in str(db._get_row_prop(c, ['razon_social', 'Razón social / Nombre', 'Razon social / Nombre', 'Razon Social', 'Nombre', 'Cliente']) or '').strip().lower() or str(db._get_row_prop(c, ['razon_social', 'Razón social / Nombre', 'Razon social / Nombre', 'Razon Social', 'Nombre', 'Cliente']) or '').strip().lower() in c_name_norm), None)
            
            if match:
                recipient_email = str(db._get_row_prop(match, ['correo', 'Correo', 'Email', 'Correo electrónico', 'Correo electronico']) or '').strip()
                if recipient_email:
                    email_found = True

        # Also check cuit_cuil on target invoice to see if client can be matched by CUIT
        if not email_found and target:
            target_cuit = str(db._get_row_prop(target, ['cuit_cuil', 'CUIT/CUIL', 'cuit']) or '').strip()
            if target_cuit:
                _, c_rows = db.get_sheet_data('CLIENTES')
                clean_target_cuit = target_cuit.replace('-', '').replace(' ', '')
                for c in c_rows:
                    c_cuit = str(db._get_row_prop(c, ['cuit_cuil', 'CUIT/CUIL', 'cuit']) or '').strip().replace('-', '').replace(' ', '')
                    if c_cuit and c_cuit == clean_target_cuit:
                        found_em = str(db._get_row_prop(c, ['correo', 'Correo', 'Email']) or '').strip()
                        if found_em:
                            recipient_email = found_em
                            email_found = True
                            break

        subject = f"Factura de Venta / Comprobante - ECONCATIVO S.A.S. ({nro_factura or target_id})"
        body_text = email_mgr.build_factura_email_template(cliente_nombre or "Cliente", nro_factura or target_id, total_val)

        return jsonify({
            "status": "success",
            "cliente_nombre": cliente_nombre,
            "to_email": recipient_email,
            "email_found": email_found,
            "subject": subject,
            "message": body_text
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("Iniciando ECONCATIVO System Server en puerto 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)



