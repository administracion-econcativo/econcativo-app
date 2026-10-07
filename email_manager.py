import os
import smtplib
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage

class EmailManager:
    def __init__(self, data_manager=None):
        self.db = data_manager
        self.last_html_body = None

    def get_smtp_config(self):
        """Retrieves SMTP configuration from CONFIGURACION sheet or fallback environment variables."""
        config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email_user': '',
            'email_password': '',
            'admin_phone': '',
            'sender_name': 'ECONCATIVO S.A.S.'
        }
        if self.db:
            try:
                cfg_dict = self.db.get_configuracion() if hasattr(self.db, 'get_configuracion') else {}
                config['email_user'] = cfg_dict.get('smtp_email') or cfg_dict.get('correo_empresa') or ''
                config['email_password'] = cfg_dict.get('smtp_password') or cfg_dict.get('clave_gmail') or ''
                config['admin_phone'] = cfg_dict.get('telefono_administracion') or cfg_dict.get('telefono') or ''
                if cfg_dict.get('nombre_empresa'):
                    config['sender_name'] = cfg_dict.get('nombre_empresa')
            except Exception as e:
                print(f"[EMAIL CONFIG ERROR] {e}")

        # Fallbacks to environment variables if sheet values are missing
        if not config['email_user']:
            config['email_user'] = os.environ.get('SMTP_EMAIL', '')
        if not config['email_password']:
            config['email_password'] = os.environ.get('SMTP_PASSWORD', '')
        if not config['admin_phone']:
            config['admin_phone'] = os.environ.get('ADMIN_PHONE', '')

        return config

    def _parse_account_details(self, nombre, cbu_alias):
        """Parses pipe-separated CBU string into structured dictionary."""
        details = {
            'nombre': nombre,
            'banco': '',
            'nro_cuenta': '',
            'cbu': '',
            'alias': '',
            'titular': ''
        }
        if not cbu_alias or str(cbu_alias).strip() == '-':
            return details

        cbu_str = str(cbu_alias).strip()
        if '|' in cbu_str:
            parts = [p.strip() for p in cbu_str.split('|')]
            for p in parts:
                if ':' in p:
                    k, v = p.split(':', 1)
                    k_l = k.strip().lower()
                    v_s = v.strip()
                    if 'banco' in k_l:
                        details['banco'] = v_s
                    elif 'cta' in k_l or 'cuenta' in k_l:
                        details['nro_cuenta'] = v_s
                    elif 'cbu' in k_l:
                        details['cbu'] = v_s
                    elif 'alias' in k_l:
                        details['alias'] = v_s
                    elif 'titular' in k_l:
                        details['titular'] = v_s
        else:
            details['cbu'] = cbu_str

        return details

    def get_active_bank_accounts_formatted(self):
        """Fetches active bank accounts and CBUs from Tesorería to build live email text and HTML."""
        accounts_text = []
        accounts_html_list = []

        if self.db:
            try:
                rows = []
                if hasattr(self.db, 'get_sheet_data'):
                    _, rows = self.db.get_sheet_data('TESORERIA')
                elif hasattr(self.db, 'load_wb'):
                    wb = self.db.load_wb(data_only=True)
                    if 'TESORERIA' in wb.sheetnames:
                        _, rows = self.db._read_sheet_rows(wb['TESORERIA'])
                for r in rows:
                    nombre = str(self.db._get_row_prop(r, ['Nombre cuenta', 'Cuenta', 'Nombre']) or '').strip()
                    cbu_alias = str(self.db._get_row_prop(r, ['CBU / ALIAS', 'CBU/ALIAS', 'N° Cuenta / CBU / Alias', 'CBU', 'ALIAS']) or '').strip()
                    tipo = str(self.db._get_row_prop(r, ['Tipo']) or 'Banco').strip().lower()
                    estado = str(self.db._get_row_prop(r, ['Estado']) or 'Activa').strip().lower()

                    nomb_l = nombre.lower()
                    is_cash_or_cheque = any(w in nomb_l or w in tipo for w in ['caja', 'efectivo', 'cheque', 'valores'])

                    if nombre and 'activa' in estado and not is_cash_or_cheque:
                        details = self._parse_account_details(nombre, cbu_alias)
                        
                        # Plain text formatting
                        banco_label = f" ({details['banco']})" if details['banco'] else ""
                        txt_line = f"🏦 {nombre}{banco_label}"
                        sub_lines = []
                        if details['nro_cuenta']: sub_lines.append(f"  • N° de Cuenta: {details['nro_cuenta']}")
                        if details['cbu']: sub_lines.append(f"  • CBU: {details['cbu']}")
                        if details['alias']: sub_lines.append(f"  • ALIAS: {details['alias']}")
                        if details['titular']: sub_lines.append(f"  • Titular: {details['titular']}")

                        if sub_lines:
                            txt_line += "\n" + "\n".join(sub_lines)
                        elif cbu_alias and cbu_alias != '-':
                            txt_line += f"\n  • {cbu_alias}"

                        accounts_text.append(txt_line)

                        # HTML formatting
                        h_rows = []
                        if details['nro_cuenta']:
                            h_rows.append(f'<tr><td style="padding: 2px 0; font-weight: bold; width: 130px; color: #475569;">• N° de Cuenta:</td><td>{details["nro_cuenta"]}</td></tr>')
                        if details['cbu']:
                            h_rows.append(f'<tr><td style="padding: 2px 0; font-weight: bold; color: #475569;">• CBU:</td><td style="font-family: monospace; font-weight: bold; color: #0f172a; font-size: 14px;">{details["cbu"]}</td></tr>')
                        if details['alias']:
                            h_rows.append(f'<tr><td style="padding: 2px 0; font-weight: bold; color: #475569;">• ALIAS:</td><td style="font-weight: bold; color: #059669; font-size: 14px;">{details["alias"]}</td></tr>')
                        if details['titular']:
                            h_rows.append(f'<tr><td style="padding: 2px 0; font-weight: bold; color: #475569;">• Titular:</td><td>{details["titular"]}</td></tr>')

                        if not h_rows and cbu_alias and cbu_alias != '-':
                            h_rows.append(f'<tr><td colspan="2" style="padding: 2px 0; font-weight: bold; color: #059669;">• {cbu_alias}</td></tr>')

                        title_str = f'🏦 {nombre}' + (f' <span style="font-size: 13px; font-weight: normal; color: #64748b;">({details["banco"]})</span>' if details['banco'] else '')
                        
                        html_card = f"""
                        <div style="background: #ffffff; border: 1px solid #cbd5e1; border-left: 5px solid #059669; padding: 14px 18px; margin-bottom: 12px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                            <div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-bottom: 6px;">{title_str}</div>
                            <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #334155;">
                                {"".join(h_rows)}
                            </table>
                        </div>
                        """
                        accounts_html_list.append(html_card)
            except Exception as e:
                print(f"[FETCH BANK ACCOUNTS ERROR] {e}")

        # Fallbacks if none found
        if not accounts_text:
            accounts_text = ["🏦 Banco Galicia Cta Cte\n  • CBU: 0070244920000001234567\n  • ALIAS: ECONCATIVO.GALICIA"]
            accounts_html_list = ["""
            <div style="background: #ffffff; border: 1px solid #cbd5e1; border-left: 5px solid #059669; padding: 14px 18px; margin-bottom: 12px; border-radius: 10px;">
                <div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-bottom: 6px;">🏦 Banco Galicia Cta Cte</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #334155;">
                    <tr><td style="padding: 2px 0; font-weight: bold; width: 130px;">• CBU:</td><td style="font-family: monospace; font-weight: bold; color: #0f172a;">0070244920000001234567</td></tr>
                    <tr><td style="padding: 2px 0; font-weight: bold;">• ALIAS:</td><td style="font-weight: bold; color: #059669;">ECONCATIVO.GALICIA</td></tr>
                </table>
            </div>
            """]

        return "\n\n".join(accounts_text), "".join(accounts_html_list)

    def build_factura_email_template(self, cliente_nombre, nro_factura, total_factura, message_override=None):
        """Builds standardized corporate HTML & plain text email body with live bank accounts & contact phone."""
        cfg = self.get_smtp_config()
        bank_accounts_text, bank_accounts_html = self.get_active_bank_accounts_formatted()
        admin_phone = cfg.get('admin_phone') or '3572-15400000'
        company_email = cfg.get('email_user') or 'administracion@econcativo.com.ar'

        nro_str = f"N° {nro_factura}" if nro_factura else "correspondiente"
        total_str = f"${total_factura:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(total_factura, (int, float)) else str(total_factura)

        if message_override and str(message_override).strip():
            body_text = str(message_override).strip()
        else:
            body_text = f"""Estimado/a {cliente_nombre},

Se remite adjunta su factura oficial {nro_str} por un importe total de {total_str}.

💳 DATOS BANCARIOS PARA TRANSFERENCIA / PAGO:
{bank_accounts_text}

📞 CONTACTO DE ADMINISTRACIÓN:
Por cualquier duda, aclaración o envío de comprobantes de pago, podés contactarte con nuestra Administración:
• Teléfono / WhatsApp: {admin_phone}
• Correo Electrónico: {company_email}

Atentamente,
Administración ECONCATIVO S.A.S.
"""

        # Generate Corporate HTML Body with logo CID header
        self.last_html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Factura de Servicio - ECONCATIVO S.A.S.</title>
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 20px;">
    <div style="max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
        
        <!-- Header -->
        <div style="background: #0f172a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #f59e0b;">
            <img src="cid:logo_econcativo" alt="ECONCATIVO S.A.S." style="height: 52px; width: auto; max-width: 220px; display: block; margin: 0 auto 10px auto;">
            <h1 style="color: #ffffff; font-size: 20px; margin: 0; font-weight: 700; letter-spacing: 1px;">ECONCATIVO S.A.S.</h1>
            <div style="color: #94a3b8; font-size: 12px; margin-top: 4px;">Servicios de Transporte & Logística</div>
        </div>

        <!-- Content -->
        <div style="padding: 30px;">
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 16px;">
                Estimado/a {cliente_nombre},
            </div>

            <div style="background: #f8fafc; border-left: 4px solid #0284c7; padding: 16px 20px; border-radius: 8px; font-size: 14px; line-height: 1.6; color: #334155; margin-bottom: 24px;">
                Se remite adjunta su factura oficial <strong>{nro_str}</strong> por un importe total de:<br>
                <div style="font-size: 19px; font-weight: bold; color: #059669; background: #ecfdf5; border: 1px solid #a7f3d0; padding: 8px 16px; border-radius: 8px; display: inline-block; margin-top: 10px;">
                    {total_str}
                </div>
            </div>

            <div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-top: 25px; margin-bottom: 14px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
                💳 DATOS BANCARIOS PARA TRANSFERENCIA / PAGO:
            </div>
            
            {bank_accounts_html}

            <div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-top: 25px; margin-bottom: 14px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
                📞 CONTACTO DE ADMINISTRACIÓN:
            </div>
            
            <div style="background: #fffbeb; border: 1px solid #fde68a; padding: 16px; border-radius: 10px; font-size: 13px; color: #78350f; line-height: 1.7;">
                Por cualquier duda, aclaración o envío de comprobantes de pago, podés contactarte con nuestra Administración:<br>
                <strong>• Teléfono / WhatsApp:</strong> {admin_phone}<br>
                <strong>• Correo Electrónico:</strong> <a href="mailto:{company_email}" style="color: #d97706; text-decoration: none; font-weight: bold;">{company_email}</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background: #f8fafc; padding: 20px 30px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; line-height: 1.5;">
            Atentamente,<br>
            <strong style="color: #0f172a; font-size: 13px;">Administración ECONCATIVO S.A.S.</strong><br>
            <span style="font-size: 11px; color: #94a3b8;">Sistema Integral de Gestión Comercial & Logística</span>
        </div>
    </div>
</body>
</html>"""

        return body_text

    def _text_to_html_body(self, body_text):
        """Converts plain text body into corporate branded HTML layout with logo and styled sections."""
        import html
        
        escaped_text = html.escape(body_text or '')
        lines = escaped_text.split('\n')
        html_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                html_lines.append('<div style="height: 10px;"></div>')
            elif line_str.startswith('💳') or 'DATOS BANCARIOS' in line_str:
                html_lines.append(f'<div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-top: 22px; margin-bottom: 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">{line}</div>')
            elif line_str.startswith('📞') or 'CONTACTO DE ADMINISTRACIÓN' in line_str:
                html_lines.append(f'<div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-top: 22px; margin-bottom: 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">{line}</div>')
            elif line_str.startswith('🏦'):
                html_lines.append(f'<div style="font-size: 15px; font-weight: bold; color: #0f172a; margin-top: 8px; margin-bottom: 4px;">{line}</div>')
            elif line_str.startswith('•') or line_str.startswith('&bull;'):
                html_lines.append(f'<div style="margin-left: 12px; font-size: 13px; color: #334155; margin-bottom: 4px; font-weight: 500;">{line}</div>')
            elif line_str.startswith('Estimado'):
                html_lines.append(f'<div style="font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 14px;">{line}</div>')
            else:
                html_lines.append(f'<div style="font-size: 13px; line-height: 1.6; color: #334155; margin-bottom: 6px;">{line}</div>')
                
        content_html = "\n".join(html_lines)
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Factura de Servicio - ECONCATIVO S.A.S.</title>
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 20px;">
    <div style="max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
        <!-- Header -->
        <div style="background: #0f172a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #f59e0b;">
            <img src="cid:logo_econcativo" alt="ECONCATIVO S.A.S." style="height: 52px; width: auto; max-width: 220px; display: block; margin: 0 auto 10px auto;">
            <h1 style="color: #ffffff; font-size: 20px; margin: 0; font-weight: 700; letter-spacing: 1px;">ECONCATIVO S.A.S.</h1>
            <div style="color: #94a3b8; font-size: 12px; margin-top: 4px;">Servicios de Transporte & Logística</div>
        </div>
        <!-- Content -->
        <div style="padding: 26px 30px;">
            {content_html}
        </div>
        <!-- Footer -->
        <div style="background: #f8fafc; padding: 18px 30px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; line-height: 1.5;">
            Atentamente,<br>
            <strong style="color: #0f172a; font-size: 13px;">Administración ECONCATIVO S.A.S.</strong><br>
            <span style="font-size: 11px; color: #94a3b8;">Sistema Integral de Gestión Comercial & Logística</span>
        </div>
    </div>
</body>
</html>"""

    def send_email_with_pdf(self, to_email, subject, body_text, pdf_bytes, pdf_filename="Factura_ARCA.pdf", html_body=None):
        """Sends MIME email via Gmail SMTP with optional PDF file attached and embedded corporate logo."""
        cfg = self.get_smtp_config()
        sender_email = cfg.get('email_user')
        sender_password = cfg.get('email_password')

        if not sender_email or not sender_password:
            return {
                "status": "error",
                "message": "Falta configurar el email de la empresa y la clave de aplicación de Gmail en la solapa CONFIGURACIÓN."
            }

        if not to_email or '@' not in str(to_email):
            return {
                "status": "error",
                "message": "El correo electrónico del destinatario no es válido o no está registrado."
            }

        try:
            # Main mixed container
            msg = MIMEMultipart('mixed')
            msg['From'] = sender_email
            msg['Reply-To'] = sender_email
            msg['To'] = str(to_email).strip()
            msg['Subject'] = str(subject).strip()
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Message-ID'] = email.utils.make_msgid(domain='gmail.com')

            # Related container for HTML + Inline CID images
            msg_related = MIMEMultipart('related')
            
            # Alternative container for plain text and HTML
            msg_alternative = MIMEMultipart('alternative')
            msg_alternative.attach(MIMEText(body_text, 'plain', 'utf-8'))

            # Prioritize rich corporate HTML body (self.last_html_body) or fallback to text parser
            final_html_body = html_body or self.last_html_body or self._text_to_html_body(body_text)
            msg_alternative.attach(MIMEText(final_html_body, 'html', 'utf-8'))

            msg_related.attach(msg_alternative)

            # Attach inline Logo CID if file exists
            base_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(base_dir, 'static', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as img_f:
                    img_bytes = img_f.read()
                img_mime = MIMEImage(img_bytes)
                img_mime.add_header('Content-ID', '<logo_econcativo>')
                img_mime.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg_related.attach(img_mime)

            msg.attach(msg_related)

            # Attach PDF file if provided
            if pdf_bytes:
                part = MIMEApplication(pdf_bytes, Name=pdf_filename)
                part['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                msg.attach(part)

            # Connect to Gmail SMTP
            server = smtplib.SMTP(cfg['smtp_server'], cfg['smtp_port'], timeout=15)
            server.starttls()
            server.login(sender_email, sender_password.replace(' ', ''))
            server.sendmail(sender_email, [to_email], msg.as_string())
            server.quit()

            success_msg = f"Factura enviada con éxito a {to_email}" + (" con el PDF adjunto." if pdf_bytes else ".")
            return {
                "status": "success",
                "message": success_msg
            }
        except smtplib.SMTPAuthenticationError:
            return {
                "status": "error",
                "message": "Error de autenticación en Gmail: Verifica que el email y la Contraseña de Aplicación de 16 caracteres en Configuración sean correctos."
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error al enviar el correo: {str(e)}"
            }
