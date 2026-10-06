import os
import re
from io import BytesIO
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "logo.png")

NAVY = colors.HexColor('#002B5C')
AMBER = colors.HexColor('#D48806')
DARK_GRAY = colors.HexColor('#334155')
LIGHT_BG = colors.HexColor('#F8FAFC')
EMERALD = colors.HexColor('#059669')

def _format_date_ar(d_str, default='-'):
    if not d_str or str(d_str).strip() in ('', '-', 'None', 'null'):
        return default
    if isinstance(d_str, (datetime, date)):
        return d_str.strftime('%d/%m/%Y')
    s = str(d_str).strip().split('T')[0].split(' ')[0]
    parts = s.replace('/', '-').split('-')
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
        elif len(parts[2]) == 4:
            return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
    return s

def generate_presupuesto_pdf(presupuesto_data):
    """Generates an official PDF quote for ECONCATIVO."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=NAVY,
        alignment=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=AMBER,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=NAVY
    )

    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    # Load Vertical Emblem Logo
    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=110, height=80)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=22 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=9 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    f_pres = _format_date_ar(presupuesto_data.get('fecha'), default=datetime.now().strftime('%d/%m/%Y'))
    header_right = [
        Paragraph("PRESUPUESTO DE SERVICIO", title_style),
        Paragraph(f"N°: <b>{presupuesto_data.get('id', 'PRE-000001')}</b>", subtitle_style),
        Paragraph(f"Fecha: {f_pres}", ParagraphStyle('RightDate', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[200, 340])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=12))

    client_info_data = [
        [
            Paragraph("<b>EMISOR DE LA COTIZACIÓN</b>", label_style),
            Paragraph("<b>CLIENTE / SOLICITANTE</b>", label_style)
        ],
        [
            Paragraph("<b>ECONCATIVO S.A.S.</b><br/>CUIT: 30-71954400-9<br/>Transporte de Carga & Servicios de Maquinaria<br/>Oncativo, Córdoba, Argentina<br/>Contacto: administracion.econcativo@gmail.com", company_info_style),
            Paragraph(f"<b>{presupuesto_data.get('cliente', '-')}</b><br/>CUIT: {presupuesto_data.get('cuit', '-')}<br/>Validez: {presupuesto_data.get('validez', '15 días')}<br/>Forma de Pago: {presupuesto_data.get('forma_pago', 'Cuenta Corriente')}", company_info_style)
        ]
    ]

    client_table = Table(client_info_data, colWidths=[270, 270])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("DETALLE DEL SERVICIO COTIZADO", label_style))
    story.append(Spacer(1, 6))

    items_list = presupuesto_data.get('items', [])
    if not items_list and isinstance(presupuesto_data.get('detalle'), str) and presupuesto_data['detalle'].startswith('['):
        import json
        try:
            items_list = json.loads(presupuesto_data['detalle'])
        except Exception:
            items_list = []

    items_headers = [Paragraph("<b>Tipo Servicio / Actividad</b>", label_style), Paragraph("<b>Descripción / Detalle del Trabajo / Tramo</b>", label_style), Paragraph("<b>Importe Neto ($)</b>", label_style)]
    items_rows = [items_headers]

    neto_val = 0.0

    if items_list:
        for idx, item in enumerate(items_list, 1):
            act_title = item.get('actividad') or item.get('tipo_servicio') or f"Ítem {idx}"
            tipo_op = item.get('tipo') or item.get('tipo_operacion') or 'Servicio'
            
            if tipo_op == 'Viaje':
                det_parts = []
                if item.get('origen') or item.get('destino'):
                    det_parts.append(f"<b>Trayecto:</b> {item.get('origen', '-')} ➔ {item.get('destino', '-')}")
                if item.get('km'): det_parts.append(f"<b>Distancia Estimada:</b> {item['km']} km")
                if item.get('subtipo_granel') and item.get('subtipo_granel') != 'General': det_parts.append(f"<b>Carga / Material:</b> {item['subtipo_granel']}")
                if item.get('toneladas'): det_parts.append(f"<b>Peso Estimado:</b> {item['toneladas']} Tn")
                if item.get('descripcion'): det_parts.append(f"<b>Detalles Carga:</b> {item['descripcion']}")
                det_text = "<br/>".join(det_parts) or item.get('detalle', 'Transporte de Cargas')
            else:
                det_parts = []
                if item.get('detalle_trabajo'): det_parts.append(f"<b>Trabajo:</b> {item['detalle_trabajo']}")
                if item.get('ubicacion'): det_parts.append(f"<b>Ubicación/Obra:</b> {item['ubicacion']}")
                if item.get('horas'): det_parts.append(f"<b>Horas Estimadas:</b> {item['horas']} hs")
                det_text = "<br/>".join(det_parts) or item.get('detalle', 'Servicio de Maquinaria')

            item_neto = float(item.get('neto', 0))
            neto_val += item_neto
            items_rows.append([
                Paragraph(f"<b>[{tipo_op.upper()}]</b><br/>{act_title}", val_style),
                Paragraph(det_text, val_style),
                Paragraph(f"${item_neto:,.2f}", ParagraphStyle('RightVal', parent=val_style, alignment=2))
            ])
    else:
        neto_val = float(presupuesto_data.get('total', 0))
        det_parts = []
        if presupuesto_data.get('origen') or presupuesto_data.get('destino'):
            det_parts.append(f"<b>Trayecto:</b> {presupuesto_data.get('origen', '-')} ➔ {presupuesto_data.get('destino', '-')}")
        if presupuesto_data.get('km') or presupuesto_data.get('distancia_km'):
            det_parts.append(f"<b>Distancia Estimada:</b> {presupuesto_data.get('km') or presupuesto_data.get('distancia_km')} km")
        det_raw = str(presupuesto_data.get('detalle', '-'))
        if det_raw and det_raw != '-':
            det_parts.append(f"<b>Detalle:</b> {det_raw}")
        det_text = "<br/>".join(det_parts) if det_parts else det_raw
        items_rows.append([
            Paragraph(str(presupuesto_data.get('tipo_servicio', 'Servicio')), val_style),
            Paragraph(det_text, val_style),
            Paragraph(f"${neto_val:,.2f}", ParagraphStyle('RightVal', parent=val_style, alignment=2))
        ])

    items_table = Table(items_rows, colWidths=[150, 260, 130])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 12))

    raw_pdf_iva = presupuesto_data.get('iva_pct')
    iva_pct = float(raw_pdf_iva) if (raw_pdf_iva is not None and str(raw_pdf_iva).strip() != '') else 21.0
    iva_val = neto_val * (iva_pct / 100.0)
    total_val = neto_val + iva_val

    iva_label_str = "IVA (Exento 0%):" if iva_pct == 0 else f"IVA ({iva_pct}%):"

    totals_data = [
        [Paragraph("Neto Gravado:", label_style), Paragraph(f"${neto_val:,.2f}", ParagraphStyle('R1', parent=val_style, alignment=2))],
        [Paragraph(iva_label_str, label_style), Paragraph(f"${iva_val:,.2f}", ParagraphStyle('R2', parent=val_style, alignment=2))],
        [Paragraph("<b>TOTAL ESTIMADO:</b>", ParagraphStyle('TotLbl', parent=label_style, fontSize=11, textColor=NAVY)), Paragraph(f"<b>${total_val:,.2f}</b>", ParagraphStyle('TotR', parent=label_style, fontSize=11, textColor=NAVY, alignment=2))]
    ]

    totals_table = Table(totals_data, colWidths=[380, 160])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('LINEABOVE', (0,2), (-1,2), 1, NAVY),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 16))

    comb_mod = presupuesto_data.get('modalidad_combustible') or presupuesto_data.get('combustible_modalidad') or ''
    if 'sin combustible' in str(comb_mod).lower() or 'sin combustible' in str(presupuesto_data.get('observaciones', '')).lower():
        fuel_note = "<b>NOTA DE CONDICIONES:</b> Cotización efectuada <b>SIN COMBUSTIBLE INCLUIDO</b>. El consumo de gas-oil se medirá y liquidará al finalizar el servicio según los litros efectivamente consumidos."
        story.append(Paragraph(f"<font color='#B37000'>{fuel_note}</font>", ParagraphStyle('FuelNote', parent=val_style, fontSize=9, leading=12)))
        story.append(Spacer(1, 8))
    elif 'con combustible' in str(comb_mod).lower():
        fuel_note = "<b>MODALIDAD DE COMBUSTIBLE:</b> Tarifa cotizada con combustible incluido."
        story.append(Paragraph(f"<font color='#002B5C'>{fuel_note}</font>", ParagraphStyle('FuelNote', parent=val_style, fontSize=9, leading=12)))
        story.append(Spacer(1, 8))

    if presupuesto_data.get('observaciones'):
        story.append(Paragraph(f"<b>Observaciones:</b> {presupuesto_data['observaciones']}", company_info_style))
        story.append(Spacer(1, 14))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_recibo_pdf(recibo_data):
    """Generates an official PDF receipt ('Recibo Oficial de Cobro') for a fully paid invoice."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    NAVY = colors.HexColor('#002B5C')
    EMERALD = colors.HexColor('#10B981')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    EMERALD_BG = colors.HexColor('#ECFDF5')

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=NAVY,
        alignment=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=EMERALD,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=NAVY
    )

    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    # Logo
    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=110, height=80)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=22 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=9 color='#10B981'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    recibo_id = recibo_data.get('recibo_id', 'REC-000001')
    fecha_cobro = _format_date_ar(recibo_data.get('fecha_cobro'), default=datetime.now().strftime('%d/%m/%Y'))

    header_right = [
        Paragraph("RECIBO OFICIAL DE COBRO", title_style),
        Paragraph(f"Designación Única: <b>{recibo_id}</b>", subtitle_style),
        Paragraph(f"Fecha de Cobro: <b>{fecha_cobro}</b>", ParagraphStyle('RightDate', parent=val_style, alignment=2)),
        Paragraph("<font color='#10B981'><b>[ COMPROBANTE DE CANCELACIÓN TOTAL DE DEUDA ]</b></font>", ParagraphStyle('StateLabel', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[200, 340])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=12))

    # Company & Client info grid
    client_info_data = [
        [
            Paragraph("<b>EMISOR DE RECIBO</b>", label_style),
            Paragraph("<b>CLIENTE / PAGADOR</b>", label_style)
        ],
        [
            Paragraph("<b>ECONCATIVO S.A.S.</b><br/>CUIT: 30-71954400-9<br/>Transporte de Carga & Servicios de Maquinaria<br/>Oncativo, Córdoba, Argentina<br/>Contacto: administracion.econcativo@gmail.com", company_info_style),
            Paragraph(f"<b>{recibo_data.get('cliente', '-')}</b><br/>CUIT/CUIL: {recibo_data.get('cuit', '-')}<br/>Factura Cancelada: <b>{recibo_data.get('nro_factura', '-')}</b> ({recibo_data.get('tipo_comprobante', 'Factura A')})", company_info_style)
        ]
    ]

    client_table = Table(client_info_data, colWidths=[270, 270])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 14))

    # Operation / Trip & Service Details Section
    story.append(Paragraph("DETALLE DE LA OPERACIÓN Y SERVICIO REALIZADO", label_style))
    story.append(Spacer(1, 4))

    op_table_data = [
        [Paragraph("<b>ID Operación</b>", label_style), Paragraph("<b>Chofer / Operador</b>", label_style), Paragraph("<b>Unidad / Maquinaria</b>", label_style), Paragraph("<b>Detalle / Actividad</b>", label_style)],
        [
            Paragraph(str(recibo_data.get('ingreso_id', '-')), val_style),
            Paragraph(str(recibo_data.get('chofer', '-')), val_style),
            Paragraph(str(recibo_data.get('unidad', '-')), val_style),
            Paragraph(str(recibo_data.get('actividad', '-')), val_style)
        ]
    ]
    op_table = Table(op_table_data, colWidths=[100, 140, 120, 180])
    op_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(op_table)
    story.append(Spacer(1, 14))

    # Payment Methods Breakdown Section ("Detalle de Medios de Pago")
    story.append(Paragraph("DESGLOSE DE MEDIOS DE PAGO RECIBIDOS", label_style))
    story.append(Spacer(1, 4))

    medios_headers = [Paragraph("<b>Medio de Pago Aplicado</b>", label_style), Paragraph("<b>Importe Cancelado ($)</b>", label_style)]
    medios_rows = [medios_headers]

    medios_dict = recibo_data.get('medios_pago_dict', {})
    if not medios_dict:
        medios_rows.append([Paragraph(str(recibo_data.get('medio_cobro', 'Transferencia Bancaria')), val_style), Paragraph(f"${recibo_data.get('total', 0):,.2f}", val_style)])
    else:
        for m_name, m_val in medios_dict.items():
            if m_val > 0:
                medios_rows.append([Paragraph(str(m_name), val_style), Paragraph(f"${m_val:,.2f}", val_style)])

    total_recibido = recibo_data.get('importe_cobrado', recibo_data.get('total', 0))
    medios_rows.append([
        Paragraph("<b>TOTAL CANCELADO Y RECIBIDO EN CAJA</b>", ParagraphStyle('TotLabel', parent=label_style, fontSize=10, textColor=EMERALD)),
        Paragraph(f"<b>${total_recibido:,.2f}</b>", ParagraphStyle('TotVal', parent=label_style, fontSize=11, textColor=EMERALD, alignment=2))
    ])

    medios_table = Table(medios_rows, colWidths=[360, 180])
    medios_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), EMERALD_BG),
        ('BACKGROUND', (0,-1), (-1,-1), EMERALD_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(medios_table)
    story.append(Spacer(1, 14))

    if recibo_data.get('observaciones'):
        story.append(Paragraph(f"<b>Observaciones / Referencias de Pago:</b> {recibo_data['observaciones']}", company_info_style))
        story.append(Spacer(1, 14))

    # Official Signatures & Receipt Declaration Block
    story.append(Spacer(1, 20))
    signature_data = [
        [
            Paragraph("___________________________________<br/><b>Firma y Sello Autorizado</b><br/>ECONCATIVO S.A.S.", company_info_style),
            Paragraph("___________________________________<br/><b>Conformidad de Pago</b><br/>Firma Cliente Pagador", company_info_style)
        ]
    ]
    sig_table = Table(signature_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM')
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_planilla_liquidaciones_pdf(data_list, quincena_label="Período"):
    """Generates a consolidated payroll and bank transfer summary PDF for ECONCATIVO."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    EMERALD = colors.HexColor('#047857')
    EMERALD_BG = colors.HexColor('#ECFDF5')

    title_style = ParagraphStyle(
        'DocTitlePlanilla',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=NAVY,
        alignment=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitlePlanilla',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=AMBER,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'CompanyInfoPlanilla',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=DARK_GRAY
    )

    label_style = ParagraphStyle(
        'LabelStylePlanilla',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=NAVY
    )

    val_style = ParagraphStyle(
        'ValStylePlanilla',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=DARK_GRAY
    )

    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=100, height=70)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=20 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=8 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    header_right = [
        Paragraph("PLANILLA RESUMEN DE LIQUIDACIÓN Y TRANSFERENCIAS", title_style),
        Paragraph(f"Período: <b>{quincena_label}</b>", subtitle_style),
        Paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle('RightDatePlanilla', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[180, 360])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10))

    total_personas = len(data_list)
    total_fijo = sum(item.get('sueldo_fijo_base', 0) for item in data_list)
    total_comisiones = sum(item.get('total_comisiones', 0) for item in data_list)
    total_reintegros = sum(item.get('tot_reintegros', 0) for item in data_list)
    total_deducciones = sum(item.get('tot_deducciones', 0) for item in data_list)
    total_transferir = sum(item.get('sueldo_final', 0) for item in data_list)

    kpi_data = [
        [
            Paragraph("<b>Personal</b>", label_style),
            Paragraph("<b>Total Fijo</b>", label_style),
            Paragraph("<b>Comisiones</b>", label_style),
            Paragraph("<b>Reintegros (+)</b>", label_style),
            Paragraph("<b>Adelantos (-)</b>", label_style),
            Paragraph("<b>TOTAL BANCO</b>", ParagraphStyle('TLabelPlanilla', parent=label_style, textColor=EMERALD))
        ],
        [
            Paragraph(f"<b>{total_personas} choferes</b>", val_style),
            Paragraph(f"${total_fijo:,.2f}", val_style),
            Paragraph(f"${total_comisiones:,.2f}", val_style),
            Paragraph(f"${total_reintegros:,.2f}", val_style),
            Paragraph(f"${total_deducciones:,.2f}", val_style),
            Paragraph(f"<b>${total_transferir:,.2f}</b>", ParagraphStyle('TValPlanilla', parent=val_style, fontSize=10, fontName='Helvetica-Bold', textColor=EMERALD))
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[80, 90, 95, 85, 85, 105])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('BACKGROUND', (5,0), (5,-1), EMERALD_BG),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    table_headers = [
        Paragraph("<b>Legajo / Personal</b>", label_style),
        Paragraph("<b>Fijo Base ($)</b>", ParagraphStyle('RHead1', parent=label_style, alignment=2)),
        Paragraph("<b>Com. Cereales ($)</b>", ParagraphStyle('RHead2', parent=label_style, alignment=2)),
        Paragraph("<b>Reintegros (+)</b>", ParagraphStyle('RHeadReint', parent=label_style, alignment=2)),
        Paragraph("<b>Adelantos (-)</b>", ParagraphStyle('RHeadDed', parent=label_style, alignment=2)),
        Paragraph("<b>SUELDO NETO ($)</b>", ParagraphStyle('RHead3', parent=label_style, alignment=2, textColor=EMERALD)),
        Paragraph("<b>Datos Bancarios Transferencia</b>", label_style)
    ]
    table_rows = [table_headers]

    for item in data_list:
        eid = item.get('id_empleado', '-')
        nombre = item.get('nombre', '-')
        dni = item.get('dni', '-')
        puesto = item.get('puesto', 'Chofer')
        s_base = item.get('sueldo_fijo_base', 0)
        s_com = item.get('total_comisiones', 0)
        s_reint = item.get('tot_reintegros', 0)
        s_ded = item.get('tot_deducciones', 0)
        s_total = item.get('sueldo_final', 0)

        banco = item.get('banco', '-')
        cbu = item.get('cbu', '-')
        alias = item.get('alias_cbu', '-')
        
        bank_str = f"<b>{banco}</b>"
        if alias and alias != '-':
            bank_str += f"<br/>Alias: {alias}"
        elif cbu and cbu != '-':
            bank_str += f"<br/>CBU: {cbu}"

        table_rows.append([
            Paragraph(f"<b>{nombre}</b><br/><font size=7 color='#64748B'>{eid} | DNI: {dni}</font>", val_style),
            Paragraph(f"${s_base:,.2f}", ParagraphStyle('ValR1', parent=val_style, alignment=2)),
            Paragraph(f"${s_com:,.2f}", ParagraphStyle('ValR2', parent=val_style, alignment=2)),
            Paragraph(f"${s_reint:,.2f}", ParagraphStyle('ValRReint', parent=val_style, alignment=2)),
            Paragraph(f"${s_ded:,.2f}", ParagraphStyle('ValRDed', parent=val_style, alignment=2)),
            Paragraph(f"<b>${s_total:,.2f}</b>", ParagraphStyle('ValRBold1', parent=val_style, fontName='Helvetica-Bold', alignment=2, textColor=EMERALD)),
            Paragraph(bank_str, company_info_style)
        ])

    table_rows.append([
        Paragraph("<b>TOTALES GENERALES</b>", ParagraphStyle('TotG1', parent=label_style, fontSize=9, textColor=NAVY)),
        Paragraph(f"<b>${total_fijo:,.2f}</b>", ParagraphStyle('TotF1', parent=label_style, alignment=2)),
        Paragraph(f"<b>${total_comisiones:,.2f}</b>", ParagraphStyle('TotC1', parent=label_style, alignment=2)),
        Paragraph(f"<b>${total_reintegros:,.2f}</b>", ParagraphStyle('TotReint1', parent=label_style, alignment=2)),
        Paragraph(f"<b>${total_deducciones:,.2f}</b>", ParagraphStyle('TotDed1', parent=label_style, alignment=2)),
        Paragraph(f"<b>${total_transferir:,.2f}</b>", ParagraphStyle('TotT1', parent=label_style, fontSize=9.5, alignment=2, textColor=EMERALD)),
        Paragraph("", val_style)
    ])

    emp_table = Table(table_rows, colWidths=[110, 65, 75, 65, 65, 75, 85])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BACKGROUND', (0,-1), (-1,-1), EMERALD_BG),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 20))

    sig_data = [
        [
            Paragraph("___________________________________<br/><b>Administración y Finanzas</b><br/>ECONCATIVO S.A.S.", company_info_style),
            Paragraph("___________________________________<br/><b>Revisión Contable y Tesorería</b><br/>Liquidación de Sueldos", company_info_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM')
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_liquidacion_individual_pdf(item):
    """Generates an individual salary & commission liquidation voucher PDF for an employee."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    EMERALD = colors.HexColor('#047857')
    EMERALD_BG = colors.HexColor('#ECFDF5')

    title_style = ParagraphStyle(
        'DocTitleIndiv',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=NAVY,
        alignment=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitleIndiv',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=AMBER,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'CompanyInfoIndiv',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=DARK_GRAY
    )

    label_style = ParagraphStyle(
        'LabelStyleIndiv',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=NAVY
    )

    val_style = ParagraphStyle(
        'ValStyleIndiv',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=DARK_GRAY
    )

    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=100, height=70)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=20 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=8 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    header_right = [
        Paragraph("LIQUIDACIÓN DE REMUNERACIONES Y COMISIONES", title_style),
        Paragraph(f"Período: <b>{item.get('periodo_label', 'Quincenal')}</b>", subtitle_style),
        Paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('RightDateIndiv', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[180, 360])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10))

    story.append(Paragraph("DATOS DEL PERSONAL / CHOFER", label_style))
    story.append(Spacer(1, 4))

    banco_str = item.get('banco', '-')
    alias_str = item.get('alias_cbu', '-')
    cbu_str = item.get('cbu', '-')
    datos_banco = f"Banco: {banco_str} | Alias: {alias_str} | CBU: {cbu_str}"

    emp_info_data = [
        [
            Paragraph("<b>Apellido y Nombre:</b>", label_style), Paragraph(str(item.get('nombre', '-')), val_style),
            Paragraph("<b>Legajo Personal:</b>", label_style), Paragraph(str(item.get('id_empleado', '-')), val_style)
        ],
        [
            Paragraph("<b>DNI / CUIL:</b>", label_style), Paragraph(f"{item.get('dni', '-')} / {item.get('cuil', '-')}", val_style),
            Paragraph("<b>Puesto / Cargo:</b>", label_style), Paragraph(str(item.get('puesto', 'Chofer')), val_style)
        ],
        [
            Paragraph("<b>Cuenta Bancaria:</b>", label_style), Paragraph(datos_banco, val_style),
            Paragraph("<b>Período Liquidado:</b>", label_style), Paragraph(str(item.get('periodo_label', '-')), val_style)
        ]
    ]
    emp_info_table = Table(emp_info_data, colWidths=[110, 180, 110, 140])
    emp_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(emp_info_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("RESUMEN DE LIQUIDACIÓN DE REMUNERACIÓN Y COMISIONES", label_style))
    story.append(Spacer(1, 4))

    s_base = item.get('sueldo_fijo_base', 0)
    s_com = item.get('total_comisiones', 0)
    s_reint = item.get('tot_reintegros', 0)
    s_ded = item.get('tot_deducciones', 0)
    s_total = item.get('sueldo_final', 0)

    resumen_rows = [
        [Paragraph("<b>Concepto Remunerativo</b>", label_style), Paragraph("<b>Período Aplicado</b>", label_style), Paragraph("<b>Monto Liquidado ($)</b>", ParagraphStyle('R1Indiv', parent=label_style, alignment=2))],
        [Paragraph("Sueldo Fijo Base Quincenal", val_style), Paragraph(str(item.get('periodo_label', '-')), val_style), Paragraph(f"${s_base:,.2f}", ParagraphStyle('R2Indiv', parent=val_style, alignment=2))],
        [Paragraph(f"Comisiones por Transporte a Granel de Cereales ({item.get('comision_pct', 0)}%)", val_style), Paragraph(f"{item.get('cant_viajes', 0)} viajes a granel", val_style), Paragraph(f"${s_com:,.2f}", ParagraphStyle('R3Indiv', parent=val_style, alignment=2))],
    ]

    if s_reint > 0:
        resumen_rows.append([Paragraph("Reintegro de Gastos / Repuestos (+)", val_style), Paragraph("Compras / Insumos", val_style), Paragraph(f"+${s_reint:,.2f}", ParagraphStyle('RReintIndiv', parent=val_style, alignment=2, textColor=EMERALD))])

    if s_ded > 0:
        resumen_rows.append([Paragraph("Adelantos de Sueldo / Viáticos Entregados (-)", val_style), Paragraph("Entregas a cuenta", val_style), Paragraph(f"-${s_ded:,.2f}", ParagraphStyle('RDedIndiv', parent=val_style, alignment=2, textColor=colors.HexColor('#DC2626')))])

    resumen_rows.append([
        Paragraph("<b>TOTAL MONTO A FACTURAR Y TRANSFERIR</b>", ParagraphStyle('RTLIndiv', parent=label_style, fontSize=9.5, textColor=EMERALD)),
        Paragraph("", val_style),
        Paragraph(f"<b>${s_total:,.2f}</b>", ParagraphStyle('RTVIndiv', parent=val_style, fontSize=11, fontName='Helvetica-Bold', alignment=2, textColor=EMERALD))
    ])
    resumen_table = Table(resumen_rows, colWidths=[240, 160, 140])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BACKGROUND', (0,-1), (-1,-1), EMERALD_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(resumen_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("DETALLE DE VIAJES / SERVICIOS ASIGNADOS EN EL PERÍODO", label_style))
    story.append(Spacer(1, 4))

    viajes_headers = [
        Paragraph("<b>ID Operación</b>", label_style),
        Paragraph("<b>Fecha</b>", label_style),
        Paragraph("<b>Cliente / Destino</b>", label_style),
        Paragraph("<b>Importe Neto ($)</b>", ParagraphStyle('VR1Indiv', parent=label_style, alignment=2)),
        Paragraph("<b>% Com.</b>", ParagraphStyle('VR2Indiv', parent=label_style, alignment=2)),
        Paragraph("<b>Comisión Ganada ($)</b>", ParagraphStyle('VR3Indiv', parent=label_style, alignment=2))
    ]
    viajes_rows = [viajes_headers]

    desglose = item.get('desglose_viajes', [])
    if not desglose:
        viajes_rows.append([Paragraph("Sin operaciones registradas en el período seleccionado.", val_style), "", "", "", "", ""])
    else:
        for v in desglose:
            aplica = v.get('aplica_comision', False)
            com_pct_str = f"{v.get('comision_pct', 0)}%" if aplica else "0%"
            com_val = v.get('comision_ganada', 0)
            
            viajes_rows.append([
                Paragraph(f"<b>{v.get('id', '-')}</b>", val_style),
                Paragraph(_format_date_ar(v.get('fecha')), val_style),
                Paragraph(str(v.get('cliente', '-')), val_style),
                Paragraph(f"${v.get('monto_neto', 0):,.2f}", ParagraphStyle('RNetIndiv', parent=val_style, alignment=2)),
                Paragraph(com_pct_str, ParagraphStyle('RPctIndiv', parent=val_style, alignment=2)),
                Paragraph(f"${com_val:,.2f}", ParagraphStyle('RComIndiv', parent=val_style, fontName='Helvetica-Bold' if aplica else 'Helvetica', alignment=2, textColor=EMERALD if aplica else DARK_GRAY))
            ])

    viajes_table = Table(viajes_rows, colWidths=[90, 75, 175, 75, 45, 80])
    viajes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(viajes_table)
    story.append(Spacer(1, 10))

    # Add Novelties / Advances Table if present
    novedades_list = item.get('novedades', [])
    if novedades_list:
        story.append(Paragraph("DETALLE DE ADELANTOS Y REINTEGROS DE PERSONAL", label_style))
        story.append(Spacer(1, 4))
        nov_headers = [
            Paragraph("<b>ID Novedad</b>", label_style),
            Paragraph("<b>Fecha</b>", label_style),
            Paragraph("<b>Tipo</b>", label_style),
            Paragraph("<b>Concepto / Detalle</b>", label_style),
            Paragraph("<b>Medio Pago</b>", label_style),
            Paragraph("<b>Importe ($)</b>", ParagraphStyle('NVH1', parent=label_style, alignment=2))
        ]
        nov_rows = [nov_headers]
        for n in novedades_list:
            t_str = str(n.get('tipo', 'Deducción'))
            is_reint = 'reintegr' in t_str.lower()
            m_val = float(n.get('monto', 0))
            m_disp = f"+${m_val:,.2f}" if is_reint else f"-${m_val:,.2f}"
            t_color = EMERALD if is_reint else colors.HexColor('#DC2626')
            mp = str(n.get('medio_pago', 'Efectivo'))
            if n.get('nro_cheque'):
                mp += f" (N° {n.get('nro_cheque')})"
            nov_rows.append([
                Paragraph(str(n.get('id', '-')), val_style),
                Paragraph(_format_date_ar(n.get('fecha')), val_style),
                Paragraph(f"<b>{t_str}</b>", ParagraphStyle('NVT1', parent=val_style, textColor=t_color)),
                Paragraph(str(n.get('concepto', '-')), val_style),
                Paragraph(mp, val_style),
                Paragraph(f"<b>{m_disp}</b>", ParagraphStyle('NVM1', parent=val_style, alignment=2, textColor=t_color))
            ])
        nov_table = Table(nov_rows, colWidths=[75, 65, 90, 155, 85, 70])
        nov_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(nov_table)
        story.append(Spacer(1, 12))

    instr_text = f"<b>Instrucción de Facturación ARCA para el Empleado / Chofer:</b><br/>" \
                 f"Estimado/a <b>{item.get('nombre')}</b>: Por favor, emitir la <b>Factura Electrónica ARCA</b> (Monotributo / Factura C) correspondiente por el importe total exacto de <b>${s_total:,.2f}</b> a nombre de <b>ECONCATIVO S.A.S.</b> y adjuntarla para proceder a la acreditación de la transferencia bancaria."
    
    instr_table = Table([[Paragraph(instr_text, company_info_style)]], colWidths=[540])
    instr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEF3C7')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#F59E0B')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(instr_table)
    story.append(Spacer(1, 20))

    sig_data = [
        [
            Paragraph("___________________________________<br/><b>Emisión de Liquidación</b><br/>ECONCATIVO S.A.S.", company_info_style),
            Paragraph("___________________________________<br/><b>Conformidad del Empleado</b><br/>Firma y Aclaración", company_info_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM')
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

generate_recibo_sueldo_pdf = generate_liquidacion_individual_pdf

def generate_orden_compra_pdf(odata):
    """Generates an official Purchase Order (Orden de Compra) PDF document."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('OCTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY)
    subtitle_style = ParagraphStyle('OCSubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=13, textColor=DARK_GRAY)
    header_right_style = ParagraphStyle('OCHHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=2, textColor=AMBER)
    date_style = ParagraphStyle('OCDate', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=2, textColor=DARK_GRAY)
    
    lbl_style = ParagraphStyle('OCLbl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=NAVY)
    val_style = ParagraphStyle('OCVal', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=DARK_GRAY)
    company_info_style = ParagraphStyle('OCCompInfo', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=DARK_GRAY)

    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=140, height=50)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=20 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=9 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    oid = odata.get('id', 'ORD-000000')
    fecha = _format_date_ar(odata.get('fecha'), default=datetime.now().strftime('%d/%m/%Y'))
    proveedor = odata.get('proveedor', 'Proveedor Genérico')
    cuit = odata.get('cuit', '-')
    tipo_insumo = odata.get('tipo_insumo', 'Insumos Generales')
    unidad = odata.get('unidad', 'General')
    detalle = odata.get('detalle', 'Sin detalle especificado.')
    neto = float(odata.get('neto', 0))
    iva_pct = float(odata.get('iva_pct', 21))
    iva_amt = neto * (iva_pct / 100.0)
    total = float(odata.get('total', neto + iva_amt))
    forma_pago = odata.get('forma_pago', 'Cuenta Corriente 30 días')
    estado = odata.get('estado', 'Pendiente')
    observaciones = odata.get('observaciones', '')

    company_text = "<b>ECONCATIVO S.A.S.</b><br/>" \
                   "Transporte Automotor & Maquinaria Vial<br/>" \
                   "CUIT: 30-71954400-9<br/>" \
                   "Oncativo, Córdoba, Argentina<br/>" \
                   "Contacto: administracion.econcativo@gmail.com"
    
    header_right_text = f"<b>ÓRDEN DE COMPRA</b><br/><font color='#002B5C' size=14>N° {oid}</font><br/><br/><b>FECHA:</b> {fecha}"

    header_table = Table([[logo_element, Paragraph(company_text, company_info_style), Paragraph(header_right_text, header_right_style)]], colWidths=[160, 210, 170])
    
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (2,0), 'RIGHT')
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceBefore=2, spaceAfter=10))

    # Supplier Box
    supplier_info = [
        [
            Paragraph("<b>PROVEEDOR / ADJUDICATARIO:</b>", lbl_style),
            Paragraph(f"<b>{proveedor}</b>", ParagraphStyle('PName', parent=lbl_style, fontSize=10, textColor=NAVY)),
            Paragraph("<b>CUIT / CDI:</b>", lbl_style),
            Paragraph(str(cuit), val_style)
        ],
        [
            Paragraph("<b>TIPO DE INSUMO / RUBRO:</b>", lbl_style),
            Paragraph(str(tipo_insumo), val_style),
            Paragraph("<b>DESTINO / UNIDAD:</b>", lbl_style),
            Paragraph(str(unidad), val_style)
        ],
        [
            Paragraph("<b>CONDICIÓN DE PAGO:</b>", lbl_style),
            Paragraph(str(forma_pago), val_style),
            Paragraph("<b>ESTADO ÓRDEN:</b>", lbl_style),
            Paragraph(f"<b>{estado.upper()}</b>", ParagraphStyle('PEst', parent=val_style, fontName='Helvetica-Bold', textColor=EMERALD if estado.lower() == 'pagado' else AMBER))
        ]
    ]

    supplier_table = Table(supplier_info, colWidths=[140, 160, 100, 140])
    supplier_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))

    story.append(supplier_table)
    story.append(Spacer(1, 12))

    # Purchase Items Table
    items_headers = [
        Paragraph("<b>Concepto / Descripción del Insumo o Servicio</b>", lbl_style),
        Paragraph("<b>Neto ($)</b>", ParagraphStyle('RNetHead', parent=lbl_style, alignment=2)),
        Paragraph("<b>IVA %</b>", ParagraphStyle('RIvaPctHead', parent=lbl_style, alignment=2)),
        Paragraph("<b>IVA ($)</b>", ParagraphStyle('RIvaAmtHead', parent=lbl_style, alignment=2)),
        Paragraph("<b>Total ($)</b>", ParagraphStyle('RTotHead', parent=lbl_style, alignment=2))
    ]

    items_rows = [items_headers]
    items_rows.append([
        Paragraph(detalle.replace('\n', '<br/>'), val_style),
        Paragraph(f"${neto:,.2f}", ParagraphStyle('RNetRow', parent=val_style, alignment=2)),
        Paragraph(f"{iva_pct}%", ParagraphStyle('RIvaPctRow', parent=val_style, alignment=2)),
        Paragraph(f"${iva_amt:,.2f}", ParagraphStyle('RIvaAmtRow', parent=val_style, alignment=2)),
        Paragraph(f"<b>${total:,.2f}</b>", ParagraphStyle('RTotRow', parent=val_style, fontName='Helvetica-Bold', alignment=2, textColor=NAVY))
    ])

    items_table = Table(items_rows, colWidths=[240, 75, 55, 75, 95])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    story.append(items_table)
    story.append(Spacer(1, 10))

    # Totals summary box
    totals_data = [
        [Paragraph("<b>Subtotal Neto Gravado:</b>", val_style), Paragraph(f"${neto:,.2f}", ParagraphStyle('RT1', parent=val_style, alignment=2))],
        [Paragraph(f"<b>IVA ({iva_pct}%):</b>", val_style), Paragraph(f"${iva_amt:,.2f}", ParagraphStyle('RT2', parent=val_style, alignment=2))],
        [Paragraph("<b>TOTAL ÓRDEN DE COMPRA:</b>", ParagraphStyle('RTTL', parent=lbl_style, fontSize=11, textColor=NAVY)), Paragraph(f"<b>${total:,.2f}</b>", ParagraphStyle('RTTLVal', parent=lbl_style, fontSize=11, alignment=2, textColor=NAVY))]
    ]
    totals_table = Table(totals_data, colWidths=[380, 160])
    totals_table.setStyle(TableStyle([
        ('BACKGROUND', (0,2), (1,2), colors.HexColor('#DCFCE7')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,2), (1,2), 1, colors.HexColor('#10B981')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))

    story.append(totals_table)
    story.append(Spacer(1, 14))

    # Terms & Observations
    terms_text = f"<b>Condiciones & Términos de Entrega:</b><br/>" \
                 f"1. La presente Órden de Compra constituye la autorización formal de suministro de bienes/servicios.<br/>" \
                 f"2. Indicar el número de Órden de Compra <b>({oid})</b> en el remito y factura correspondientes.<br/>" \
                 f"3. Emitir la factura a nombre de <b>ECONCATIVO S.A.S.</b> (CUIT: 30-71954400-9, Oncativo, Córdoba - Contacto: administracion.econcativo@gmail.com)."
    
    if observaciones:
        terms_text += f"<br/><br/><b>Observaciones Generales:</b> {observaciones}"

    terms_table = Table([[Paragraph(terms_text, company_info_style)]], colWidths=[540])
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(terms_table)
    story.append(Spacer(1, 25))

    # Signatures
    sig_data = [
        [
            Paragraph("___________________________________<br/><b>Solicitado / Comprador</b><br/>Departamento de Compras", company_info_style),
            Paragraph("___________________________________<br/><b>Autorizado por Administración</b><br/>ECONCATIVO S.A.S.", company_info_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM')
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_viaje_pdf(vdata):
    """Generates an official Work Order / Hoja de Ruta PDF for drivers/operators."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=NAVY,
        alignment=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=AMBER,
        alignment=2
    )

    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    lbl_style = ParagraphStyle(
        'LblStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=NAVY
    )

    company_info_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=DARK_GRAY
    )

    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=110, height=80)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=22 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=9 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    vid = str(vdata.get('id', 'VIA-000000'))
    is_srv = vid.upper().startswith('SRV') or 'servicio' in str(vdata.get('tipo', '')).lower() or 'maquinaria' in str(vdata.get('tipo', '')).lower()
    doc_type_title = "ORDEN DE SERVICIO Y MAQUINARIA" if is_srv else "ORDEN DE TRABAJO / HOJA DE RUTA"

    f_emi = _format_date_ar(vdata.get('fecha_emision'), default=datetime.now().strftime('%d/%m/%Y'))
    header_right = [
        Paragraph(doc_type_title, title_style),
        Paragraph(f"N°: <b>{vid}</b>", subtitle_style),
        Paragraph(f"Fecha Emisión: {f_emi}", ParagraphStyle('RightDate', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[240, 300])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))

    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=10))

    import re
    chofer_raw = str(vdata.get('chofer', 'POR ASIGNAR'))
    if ',' in chofer_raw or '//' in chofer_raw:
        chofer_items = [c.strip() for c in re.split(r'//|,', chofer_raw) if c.strip()]
        chofer_text = "<br/>".join(f"• <b>{c}</b>" for c in chofer_items)
    else:
        chofer_text = f"<b>{chofer_raw}</b>"

    unidad_raw = str(vdata.get('unidad', 'POR ASIGNAR'))
    if ',' in unidad_raw or '//' in unidad_raw:
        unidad_items = [u.strip() for u in re.split(r'//|,', unidad_raw) if u.strip()]
        unidad_text = "<br/>".join(f"• <b>{u}</b>" for u in unidad_items)
    else:
        unidad_text = f"<b>{unidad_raw}</b>"

    cliente = vdata.get('cliente', '-')
    fecha_salida = _format_date_ar(vdata.get('fecha_salida'), default=datetime.now().strftime('%d/%m/%Y'))
    remito = vdata.get('remito', 'PENDIENTE')
    origen = vdata.get('origen', '-')
    destino = vdata.get('destino', '-')
    carga_detalle = vdata.get('carga', '-')
    observaciones = vdata.get('observaciones', '')

    op_info_data = [
        [
            Paragraph("<b>CLIENTE / SOLICITANTE:</b>", lbl_style),
            Paragraph(str(cliente), val_style),
            Paragraph("<b>FECHA EJECUCIÓN:</b>", lbl_style),
            Paragraph(str(fecha_salida), val_style)
        ],
        [
            Paragraph("<b>CHOFER(ES) / OPERADOR(ES):</b>", lbl_style),
            Paragraph(chofer_text, ParagraphStyle('ChoferVal', parent=val_style, textColor=NAVY)),
            Paragraph("<b>UNIDAD(ES) / VEHÍCULO(S):</b>", lbl_style),
            Paragraph(unidad_text, ParagraphStyle('UnidadVal', parent=val_style, textColor=AMBER))
        ],
        [
            Paragraph("<b>REMITO / CPE / HOJA RUTA:</b>", lbl_style),
            Paragraph(str(remito), val_style),
            Paragraph("<b>TIPO DE OPERACIÓN:</b>", lbl_style),
            Paragraph("Servicio de Maquinaria" if is_srv else "Transporte de Cargas", val_style)
        ]
    ]

    op_table = Table(op_info_data, colWidths=[140, 160, 110, 130])
    op_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))

    story.append(op_table)
    story.append(Spacer(1, 10))

    detail_headers = [
        Paragraph("<b>Origen / Salida</b>", lbl_style),
        Paragraph("<b>Destino / Entrega</b>", lbl_style),
        Paragraph("<b>Detalle de Cargas / Trabajo a Realizar</b>", lbl_style)
    ]

    detail_rows = [detail_headers]
    detail_rows.append([
        Paragraph(str(origen), val_style),
        Paragraph(str(destino), val_style),
        Paragraph(str(carga_detalle).replace('\n', '<br/>'), val_style)
    ])

    detail_table = Table(detail_rows, colWidths=[150, 150, 240])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    story.append(detail_table)
    story.append(Spacer(1, 12))

    instructions_text = f"<b>INDICACIONES OPERATIVAS Y NORMAS DE SEGURIDAD PARA EL PERSONAL:</b><br/>" \
                         f"1. El chofer/operador debe contar con su licencia de conducir/LINTI vigente y EPP de seguridad (calzado, chaleco reflector).<br/>" \
                         f"2. Verificar presión de neumáticos, niveles de fluido e inspección visual de la unidad antes del inicio del trayecto.<br/>" \
                         f"3. En caso de emergencias, demoras o siniestros en ruta, notificar de inmediato a la base operativa.<br/>" \
                         f"4. Requerir firma y sello del receptor al momento de la entrega de la carga o finalización del servicio."

    if observaciones:
        instructions_text += f"<br/><br/><b>Observaciones Específicas de la Hoja de Ruta:</b> {observaciones}"

    inst_table = Table([[Paragraph(instructions_text, company_info_style)]], colWidths=[540])
    inst_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEF3C7')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.8, AMBER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(inst_table)
    story.append(Spacer(1, 30))

    sig_data = [
        [
            Paragraph("___________________________________<br/><b>Firma del Chofer / Operador</b><br/>Recibí Conforme Hoja de Ruta", company_info_style),
            Paragraph("___________________________________<br/><b>Control Operativo & Logística</b><br/>ECONCATIVO S.A.S.", company_info_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM')
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_resumen_facturacion_pdf(summary_data):
    """Generates an official PDF summary of a completed Viaje for billing (Base + Extras - Señas = Saldo Final)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=NAVY,
        alignment=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=AMBER,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=NAVY
    )

    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY
    )

    logo_element = None
    if os.path.exists(LOGO_PATH):
        try:
            from reportlab.platypus import Image as RLImage
            logo_element = RLImage(LOGO_PATH, width=110, height=80)
        except Exception:
            logo_element = None

    if not logo_element:
        logo_element = Paragraph("<font size=20 color='#002B5C'><b>ECONCATIVO</b></font><br/><font size=8 color='#D48806'>TRANSPORTE & MAQUINARIAS</font>", styles['Normal'])

    viaje_id = summary_data.get('viaje_id', 'VIA-000000')
    fecha_str = _format_date_ar(summary_data.get('fecha'), default=datetime.now().strftime('%d/%m/%Y'))

    header_right = [
        Paragraph("RESUMEN DE SERVICIO PARA FACTURACIÓN", title_style),
        Paragraph(f"Operación N°: <b>{viaje_id}</b>", subtitle_style),
        Paragraph(f"Fecha Emisión: {fecha_str}", ParagraphStyle('RightDate', parent=val_style, alignment=2))
    ]

    header_table = Table([[logo_element, header_right]], colWidths=[200, 340])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=12))

    client_info_data = [
        [
            Paragraph("<b>EMPRESA PRESTADORA</b>", label_style),
            Paragraph("<b>CLIENTE A FACTURAR</b>", label_style)
        ],
        [
            Paragraph("<b>ECONCATIVO S.A.S.</b><br/>CUIT: 30-71954400-9<br/>Transporte de Cargas & Servicios de Maquinaria<br/>Oncativo, Córdoba, Argentina<br/>Contacto: administracion.econcativo@gmail.com", company_info_style),
            Paragraph(f"<b>{summary_data.get('cliente', '-')}</b><br/>CUIT: {summary_data.get('cuit', '-')}<br/>Chofer: {summary_data.get('chofer', '-')}<br/>Unidad: {summary_data.get('unidad', '-')}", company_info_style)
        ]
    ]

    client_table = Table(client_info_data, colWidths=[270, 270])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 14))

    # Servicio Base Table
    story.append(Paragraph("1. SERVICIO BASE PRESUPUESTADO", label_style))
    story.append(Spacer(1, 4))

    base_headers = [Paragraph("<b>Concepto / Servicio Base</b>", label_style), Paragraph("<b>Detalle / Trayecto / Carga</b>", label_style), Paragraph("<b>Subtotal Neto ($)</b>", label_style)]
    base_rows = [base_headers]

    det_presup = summary_data.get('detalle_presupuesto') or summary_data.get('carga') or 'Servicio Operativo Realizado'
    base_neto = float(summary_data.get('base_neto', 0))

    base_rows.append([
        Paragraph(f"Presupuesto Origen: <b>{summary_data.get('id_presupuesto', '-')}</b>", val_style),
        Paragraph(str(det_presup), val_style),
        Paragraph(f"${base_neto:,.2f}", ParagraphStyle('R1', parent=val_style, alignment=2))
    ])

    table_base = Table(base_rows, colWidths=[160, 250, 130])
    table_base.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(table_base)
    story.append(Spacer(1, 12))

    # Adicionales Table
    adicionales = summary_data.get('adicionales', [])
    tot_adicionales = float(summary_data.get('tot_adicionales', 0))
    if adicionales:
        story.append(Paragraph("2. ADICIONALES / HORAS EXTRAS Y MODIFICACIONES DE VIAJE", label_style))
        story.append(Spacer(1, 4))
        adic_headers = [Paragraph("<b>Fecha</b>", label_style), Paragraph("<b>Concepto del Adicional</b>", label_style), Paragraph("<b>Importe ($)</b>", label_style)]
        adic_rows = [adic_headers]
        for ad in adicionales:
            m = float(ad.get('monto', 0))
            adic_rows.append([
                Paragraph(_format_date_ar(ad.get('fecha')), val_style),
                Paragraph(str(ad.get('concepto', 'Adicional')), val_style),
                Paragraph(f"${m:,.2f}", ParagraphStyle('R2', parent=val_style, alignment=2))
            ])
        table_adic = Table(adic_rows, colWidths=[110, 300, 130])
        table_adic.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EFF6FF')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BFDBFE')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(table_adic)
        story.append(Spacer(1, 12))

    # Adelantos / Señas Table
    adelantos = summary_data.get('adelantos', [])
    tot_adelantos = float(summary_data.get('tot_adelantos', 0))
    if adelantos:
        story.append(Paragraph("3. SEÑAS / ADELANTOS COBRADOS PREVIAMENTE", label_style))
        story.append(Spacer(1, 4))
        adel_headers = [Paragraph("<b>Fecha Cobro</b>", label_style), Paragraph("<b>Medio de Pago / Referencia</b>", label_style), Paragraph("<b>Monto Cobrado ($)</b>", label_style)]
        adel_rows = [adel_headers]
        for ad in adelantos:
            m = float(ad.get('monto', 0))
            med = str(ad.get('medio_pago', 'Transferencia'))
            ref = str(ad.get('comprobante', ''))
            det_med = f"{med} (Ref: {ref})" if ref else med
            adel_rows.append([
                Paragraph(_format_date_ar(ad.get('fecha')), val_style),
                Paragraph(det_med, val_style),
                Paragraph(f"-${m:,.2f}", ParagraphStyle('R3', parent=val_style, alignment=2, textColor=colors.HexColor('#DC2626')))
            ])
        table_adel = Table(adel_rows, colWidths=[110, 300, 130])
        table_adel.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ECFDF5')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#A7F3D0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(table_adel)
        story.append(Spacer(1, 14))

    # Totals Summary Box
    subtotal_neto = float(summary_data.get('subtotal_neto', 0))
    iva_pct = float(summary_data.get('iva_pct', 21))
    iva_amt = float(summary_data.get('iva_amt', 0))
    total_con_iva = float(summary_data.get('total_con_iva', 0))
    saldo_final = float(summary_data.get('saldo_neto_facturar', 0))

    summary_rows = [
        [Paragraph("Subtotal Servicio Base:", label_style), Paragraph(f"${base_neto:,.2f}", ParagraphStyle('S1', parent=val_style, alignment=2))],
        [Paragraph("Total Adicionales / Extras:", label_style), Paragraph(f"${tot_adicionales:,.2f}", ParagraphStyle('S2', parent=val_style, alignment=2))],
        [Paragraph("Subtotal Neto:", label_style), Paragraph(f"${subtotal_neto:,.2f}", ParagraphStyle('S3', parent=label_style, alignment=2))],
        [Paragraph(f"IVA ({iva_pct:.0f}%):", label_style), Paragraph(f"${iva_amt:,.2f}", ParagraphStyle('S4', parent=val_style, alignment=2))],
        [Paragraph("Total Trabajo con IVA:", label_style), Paragraph(f"${total_con_iva:,.2f}", ParagraphStyle('S5', parent=label_style, alignment=2))],
        [Paragraph("<b>(-) Señas / Adelantos Cobrados:</b>", label_style), Paragraph(f"<b>-${tot_adelantos:,.2f}</b>", ParagraphStyle('S6', parent=val_style, alignment=2, textColor=colors.HexColor('#DC2626')))],
        [Paragraph("<font size=11 color='#002B5C'><b>👉 SALDO FINAL A FACTURAR / COBRAR:</b></font>", label_style), Paragraph(f"<font size=12 color='#002B5C'><b>${saldo_final:,.2f}</b></font>", ParagraphStyle('S7', parent=label_style, alignment=2))]
    ]

    summary_table = Table(summary_rows, colWidths=[320, 220])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-2), LIGHT_BG),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF3C7')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, NAVY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_resumen_cuenta_corriente_pdf(cc_data):
    """Generates an official Client Statement of Account PDF (Resumen de Cuenta Corriente) for ECONCATIVO S.A.S."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    EMERALD = colors.HexColor('#059669')

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=NAVY, alignment=2)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=AMBER, alignment=2)
    company_style = ParagraphStyle('CompInfo', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=DARK_GRAY)
    header_right_style = ParagraphStyle('HeadRight', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=DARK_GRAY, alignment=2)

    cliente_nombre = cc_data.get('cliente', 'CLIENTE')
    fecha_emision = datetime.now().strftime('%d/%m/%Y')
    f_desde = _format_date_ar(cc_data.get('fecha_desde')) if cc_data.get('fecha_desde') else 'Inicio'
    f_hasta = _format_date_ar(cc_data.get('fecha_hasta')) if cc_data.get('fecha_hasta') else datetime.now().strftime('%d/%m/%Y')

    # Top Header Table
    header_data = [
        [
            Paragraph("<b>ECONCATIVO S.A.S.</b><br/>Servicios Agrícolas, Transporte y Logística<br/>CUIT: 30-71954400-9<br/>administracion.econcativo@gmail.com", company_style),
            Paragraph("<b>RESUMEN DE CUENTA CORRIENTE</b><br/><font color='#D48806'>ESTADO DE CUENTA / CLIENTE</font><br/><b>Fecha Emisión:</b> " + fecha_emision, header_right_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=12))

    # Client Info Box
    client_box_style = ParagraphStyle('CBox', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=DARK_GRAY)
    client_title_style = ParagraphStyle('CTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=NAVY)

    # Format and fallback for CUIT / CUIL
    cuit_raw = str(cc_data.get('cuit') or '').strip()
    if not cuit_raw or cuit_raw.lower() in ['none', 'null', '', '-']:
        for m in cc_data.get('movimientos', []):
            mc = str(m.get('cuit') or '').strip()
            if mc and mc.lower() not in ['none', 'null', '', '-']:
                cuit_raw = mc
                break

    clean_digits = re.sub(r'\D', '', cuit_raw) if cuit_raw else ''
    if len(clean_digits) == 11:
        cuit_display = f"{clean_digits[:2]}-{clean_digits[2:10]}-{clean_digits[10]}"
    elif cuit_raw and cuit_raw.lower() not in ['none', 'null', '']:
        cuit_display = cuit_raw
    else:
        cuit_display = '-'

    client_box_data = [
        [
            Paragraph(f"<b>Sres:</b> <font color='#002B5C' size=11><b>{cliente_nombre.upper()}</b></font>", client_title_style),
            Paragraph(f"<b>Período:</b> {f_desde} al {f_hasta}", ParagraphStyle('R1', parent=client_box_style, alignment=2))
        ],
        [
            Paragraph("<b>CUIT / CUIL:</b> " + cuit_display, client_box_style),
            Paragraph("<b>Estado de Saldo:</b> " + str(cc_data.get('estado_saldo', 'SALDO DEUDOR')), ParagraphStyle('R2', parent=client_box_style, alignment=2))
        ]
    ]
    client_table = Table(client_box_data, colWidths=[340, 200])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 14))

    # Table Header & Rows
    hdr_cell_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white)
    cell_style = ParagraphStyle('TD', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=DARK_GRAY)
    cell_right = ParagraphStyle('TDR', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=DARK_GRAY, alignment=2)
    cell_bold_right = ParagraphStyle('TDBR', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=NAVY, alignment=2)

    table_data = [
        [
            Paragraph("<b>FECHA VTO</b>", hdr_cell_style),
            Paragraph("<b>CONCEPTO / COMPROBANTE</b>", hdr_cell_style),
            Paragraph("<b>POR COBRAR ($)</b>", ParagraphStyle('TH2', parent=hdr_cell_style, alignment=2)),
            Paragraph("<b>COBRADO ($)</b>", ParagraphStyle('TH3', parent=hdr_cell_style, alignment=2)),
            Paragraph("<b>SALDO TOTAL ($)</b>", ParagraphStyle('TH4', parent=hdr_cell_style, alignment=2))
        ]
    ]

    movs = cc_data.get('movimientos', [])
    sorted_movs = list(reversed(movs))
    for m in sorted_movs:
        f_vto = _format_date_ar(m.get('vencimiento') or m.get('fecha') or '-')
        con = str(m.get('concepto') or m.get('tipo') or '-')
        d_val = float(m.get('debe', 0.0))
        h_val = float(m.get('haber', 0.0))
        s_val = float(m.get('saldo_acumulado', 0.0))

        d_str = f"${d_val:,.2f}" if d_val > 0 else "-"
        h_str = f"${h_val:,.2f}" if h_val > 0 else "-"

        table_data.append([
            Paragraph(f_vto, cell_style),
            Paragraph(con, cell_style),
            Paragraph(d_str, cell_right),
            Paragraph(h_str, cell_right),
            Paragraph(f"${s_val:,.2f}", cell_bold_right)
        ])

    # Initial Balance Row at the end of statement
    saldo_anterior = float(cc_data.get('saldo_anterior', 0.0))
    table_data.append([
        Paragraph(f_desde, cell_style),
        Paragraph("<b>SALDO ANTERIOR DE LA CUENTA</b>", cell_style),
        Paragraph("-", cell_right),
        Paragraph("-", cell_right),
        Paragraph(f"${saldo_anterior:,.2f}", cell_bold_right)
    ])

    mov_table = Table(table_data, colWidths=[75, 225, 80, 80, 80])
    mov_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
    ]))
    story.append(mov_table)
    story.append(Spacer(1, 14))

    # Totals & Balance Summary Box
    tot_debe = float(cc_data.get('total_debe', 0.0))
    tot_haber = float(cc_data.get('total_haber', 0.0))
    saldo_final = float(cc_data.get('saldo_final', 0.0))
    estado_lbl = "AL DÍA (SIN DEUDA)" if abs(saldo_final) < 0.01 else ("SALDO DEUDOR (PENDIENTE)" if saldo_final > 0 else "SALDO ACREEDOR (A FAVOR)")

    summary_rows = [
        [
            Paragraph("<b>SUMAS TOTALES DEL PERÍODO:</b>", ParagraphStyle('S1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=NAVY)),
            Paragraph(f"<b>POR COBRAR:</b> ${tot_debe:,.2f}", cell_bold_right),
            Paragraph(f"<b>COBRADO:</b> ${tot_haber:,.2f}", cell_bold_right)
        ],
        [
            Paragraph(f"<b>{estado_lbl}:</b>", ParagraphStyle('S2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=NAVY)),
            Paragraph("", cell_style),
            Paragraph(f"<font size=11 color='#002B5C'><b>${abs(saldo_final):,.2f}</b></font>", cell_bold_right)
        ]
    ]

    summary_table = Table(summary_rows, colWidths=[240, 150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#FEF3C7')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('LINEABOVE', (0,1), (-1,1), 1.5, NAVY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Legal Disclaimer Footer
    footer_style = ParagraphStyle('FooterLegal', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=7.5, leading=10, textColor=DARK_GRAY, alignment=1)
    story.append(Paragraph("<i>Sr. Cliente: Destacamos que ante la falta de observaciones o reparos por escrito dentro de los treinta días corridos de la recepción del presente resumen de su cuenta corriente, se tendrá por conformada la misma.</i>", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_resumen_proveedor_pdf(summary_data):
    """Generates an official PDF summary of operations, purchase orders, payments and balance for a Supplier."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    NAVY = colors.HexColor('#002B5C')
    AMBER = colors.HexColor('#D48806')
    DARK_GRAY = colors.HexColor('#334155')
    LIGHT_BG = colors.HexColor('#F8FAFC')
    
    title_style = ParagraphStyle(
        'ProvTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=NAVY,
        alignment=2
    )
    
    subtitle_style = ParagraphStyle(
        'ProvSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=AMBER,
        alignment=2
    )

    company_info_style = ParagraphStyle(
        'ProvCompInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=DARK_GRAY
    )

    cell_style = ParagraphStyle('ProvCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=DARK_GRAY)
    cell_bold = ParagraphStyle('ProvCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=NAVY)
    cell_bold_right = ParagraphStyle('ProvCellBoldRight', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=NAVY, alignment=2)
    cell_right = ParagraphStyle('ProvCellRight', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=DARK_GRAY, alignment=2)

    # Header Table
    comp_text = "<b>ECONCATIVO S.A.S.</b><br/>Servicios de Transporte & Logística de Cargas<br/>Ruta Nac. 9 - Oncativo, Córdoba<br/>CUIT: 30-71829304-9"
    header_right = [
        Paragraph("<b>RESUMEN DE CUENTA PROVEEDOR</b>", title_style),
        Paragraph(f"PERÍODO: <b>{str(summary_data.get('periodo_label', 'Todas las Fechas')).upper()}</b>", subtitle_style),
        Paragraph(f"Fecha Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle('EmissionDate', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=DARK_GRAY, alignment=2))
    ]
    
    header_table = Table([[Paragraph(comp_text, company_info_style), header_right]], colWidths=[240, 300])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceBefore=4, spaceAfter=10))

    # Supplier Info Box
    prov_info = summary_data.get('proveedor_info', {})
    prov_nombre = prov_info.get('nombre') or summary_data.get('proveedor_nombre', 'PROVEEDOR')
    prov_cuit = prov_info.get('cuit') or summary_data.get('cuit', '-')
    prov_email = prov_info.get('email') or '-'
    prov_tel = prov_info.get('telefono') or '-'
    prov_iva = prov_info.get('iva') or 'Responsable Inscripto'

    pbox_left = f"<b>PROVEEDOR / RAZÓN SOCIAL:</b> {prov_nombre}<br/><b>CUIT / CUIL:</b> {prov_cuit}<br/><b>CONDICIÓN IVA:</b> {prov_iva}"
    pbox_right = f"<b>TELÉFONO / CONTACTO:</b> {prov_tel}<br/><b>EMAIL / CORREO:</b> {prov_email}<br/><b>FECHA DE CONSULTA:</b> {datetime.now().strftime('%d/%m/%Y')}"

    prov_table = Table([[Paragraph(pbox_left, cell_style), Paragraph(pbox_right, cell_style)]], colWidths=[270, 270])
    prov_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(prov_table)
    story.append(Spacer(1, 14))

    # Opening Balance Callout Block (if period filtering is active)
    is_period = summary_data.get('is_period_filtered', False)
    saldo_ant = float(summary_data.get('saldo_anterior', 0.0))
    fecha_ini = _format_date_ar(summary_data.get('fecha_inicio_label', ''))

    if is_period and abs(saldo_ant) > 0.01:
        if saldo_ant < -0.01:
            sa_text = f"<b>SALDO ANTERIOR ACUMULADO (al {fecha_ini}):</b> 🟢 <b>${abs(saldo_ant):,.2f} (SALDO A FAVOR DE LA EMPRESA)</b>"
            sa_bg = colors.HexColor('#D1FAE5')
            sa_border = colors.HexColor('#059669')
            sa_tc = colors.HexColor('#047857')
        else:
            sa_text = f"<b>SALDO ANTERIOR ACUMULADO (al {fecha_ini}):</b> 🔴 <b>${saldo_ant:,.2f} (SALDO ADEUDADO AL PROVEEDOR)</b>"
            sa_bg = colors.HexColor('#FEE2E2')
            sa_border = colors.HexColor('#DC2626')
            sa_tc = colors.HexColor('#B91C1C')

        sa_p = Paragraph(sa_text, ParagraphStyle('SaStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=sa_tc))
        sa_table = Table([[sa_p]], colWidths=[540])
        sa_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), sa_bg),
            ('PADDING', (0,0), (-1,-1), 7),
            ('BOX', (0,0), (-1,-1), 1, sa_border),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(sa_table)
        story.append(Spacer(1, 12))

    # Section 1: Órdenes de Compra y Compras Directas
    story.append(Paragraph("<b>1. DETALLE DE ÓRDENES DE COMPRA Y GASTOS DIRECTOS REALIZADOS</b>", ParagraphStyle('SecTitle1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=NAVY)))
    story.append(Spacer(1, 4))

    ordenes = summary_data.get('ordenes', [])
    if not ordenes:
        story.append(Paragraph("<i>No se registran compras u órdenes de compra para el período seleccionado.</i>", cell_style))
    else:
        oc_headers = ['ID Orden', 'Fecha', 'Insumo / Cant.', 'Detalle / Ítems', 'Total ($)', 'Estado']
        oc_rows = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)) for h in oc_headers]]
        
        for o in ordenes:
            oid = str(o.get('ID orden') or o.get('id', ''))
            fec = _format_date_ar(o.get('Fecha') or o.get('fecha') or '-')
            tipo = str(o.get('Tipo insumo') or '')
            lit = float(o.get('Cantidad/Litros') or o.get('litros') or 0)
            tipo_cant = f"{tipo} ({lit:,.1f} L)" if lit > 0 else tipo
            det = str(o.get('Detalle') or '-')
            tot = float(o.get('Total') or 0)
            est = str(o.get('Estado') or 'Pendiente')

            oc_rows.append([
                Paragraph(f"<b>{oid}</b>", cell_style),
                Paragraph(fec, cell_style),
                Paragraph(tipo_cant, cell_style),
                Paragraph(det, cell_style),
                Paragraph(f"${tot:,.2f}", cell_right),
                Paragraph(f"<b>{est.upper()}</b>", cell_style)
            ])

        oc_table = Table(oc_rows, colWidths=[65, 60, 95, 170, 75, 75])
        oc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(oc_table)

    story.append(Spacer(1, 14))

    # Section 2: Pagos y Egresos Realizados
    story.append(Paragraph("<b>2. DETALLE DE PAGOS Y EGRESOS REALIZADOS</b>", ParagraphStyle('SecTitle2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=NAVY)))
    story.append(Spacer(1, 4))

    egresos = summary_data.get('egresos', [])
    if not egresos:
        story.append(Paragraph("<i>No se registran pagos o egresos para el período seleccionado.</i>", cell_style))
    else:
        eg_headers = ['ID Egreso', 'Fecha', 'Medio de Pago', 'Detalle / Concepto', 'Importe ($)']
        eg_rows = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)) for h in eg_headers]]
        
        for e in egresos:
            eid = str(e.get('ID') or e.get('ID egreso') or e.get('id', ''))
            fec = _format_date_ar(e.get('Fecha') or e.get('fecha') or '-')
            medio = str(e.get('Forma de Pago') or e.get('Medio de Pago') or e.get('medio_pago') or 'Transferencia / Cheque')
            det = str(e.get('Descripción') or e.get('Detalle') or '-')
            tot = float(e.get('Total') or e.get('Monto') or 0)
            pag = float(e.get('Pagado') if e.get('Pagado') is not None else tot)
            est = str(e.get('Estado') or '').upper()
            is_rev = (est in ['REVERTIDO', 'RECHAZADO'] or 'REVERSIÓN' in det.upper() or 'REVERSION' in det.upper() or pag == 0.0)

            if is_rev:
                amt_p = Paragraph('<font color="#DC2626"><b>$0.00 (REVERTIDO)</b></font>', cell_right)
            else:
                amt_p = Paragraph(f"${tot:,.2f}", cell_right)

            eg_rows.append([
                Paragraph(f"<b>{eid}</b>", cell_style),
                Paragraph(fec, cell_style),
                Paragraph(medio, cell_style),
                Paragraph(det, cell_style),
                amt_p
            ])

        eg_table = Table(eg_rows, colWidths=[70, 65, 120, 205, 80])
        eg_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(eg_table)

    story.append(Spacer(1, 16))

    # Totals & Balance Summary Box
    tot_comprado = float(summary_data.get('total_comprado', 0.0))
    tot_pagado = float(summary_data.get('total_pagado', 0.0))
    tot_litros = float(summary_data.get('total_litros', 0.0))
    saldo = float(summary_data.get('saldo', tot_comprado - tot_pagado))

    if saldo > 0.01:
        estado_lbl = "🔴 SALDO ADEUDADO AL PROVEEDOR"
        bg_color = colors.HexColor('#FEE2E2')
        val_color = '#B91C1C'
    elif saldo < -0.01:
        estado_lbl = "🟢 SALDO A FAVOR DE LA EMPRESA"
        bg_color = colors.HexColor('#D1FAE5')
        val_color = '#047857'
    else:
        estado_lbl = "⚪ CUENTA AL DÍA (SIN SALDO PENDIENTE)"
        bg_color = colors.HexColor('#F1F5F9')
        val_color = '#002B5C'

    litros_lbl = f"<br/><b>LITROS DE COMBUSTIBLE COMPRADOS:</b> {tot_litros:,.1f} L" if tot_litros > 0 else ""

    if is_period:
        sa_fmt = f"-${abs(saldo_ant):,.2f}" if saldo_ant < 0 else f"${saldo_ant:,.2f}"
        summary_rows = [
            [
                Paragraph(f"<b>RESUMEN CONSOLIDADO DEL PERÍODO:</b>{litros_lbl}", ParagraphStyle('S1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=NAVY)),
                Paragraph(f"<b>SALDO ANTERIOR:</b><br/>{sa_fmt}", ParagraphStyle('SB1', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=NAVY, alignment=2)),
                Paragraph(f"<b>COMPRAS PERÍODO:</b><br/>${tot_comprado:,.2f}", ParagraphStyle('SB2', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=NAVY, alignment=2)),
                Paragraph(f"<b>PAGOS PERÍODO:</b><br/>${tot_pagado:,.2f}", ParagraphStyle('SB3', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=NAVY, alignment=2))
            ],
            [
                Paragraph(f"<b>{estado_lbl}:</b>", ParagraphStyle('S2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=NAVY)),
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph(f"<font size=11 color='{val_color}'><b>${abs(saldo):,.2f}</b></font>", cell_bold_right)
            ]
        ]
        summary_table = Table(summary_rows, colWidths=[180, 120, 120, 120])
    else:
        summary_rows = [
            [
                Paragraph(f"<b>RESUMEN CONSOLIDADO DE LA CUENTA:</b>{litros_lbl}", ParagraphStyle('S1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=NAVY)),
                Paragraph(f"<b>TOTAL COMPRADO:</b> ${tot_comprado:,.2f}", cell_bold_right),
                Paragraph(f"<b>TOTAL PAGADO:</b> ${tot_pagado:,.2f}", cell_bold_right)
            ],
            [
                Paragraph(f"<b>{estado_lbl}:</b>", ParagraphStyle('S2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=NAVY)),
                Paragraph("", cell_style),
                Paragraph(f"<font size=11 color='{val_color}'><b>${abs(saldo):,.2f}</b></font>", cell_bold_right)
            ]
        ]
        summary_table = Table(summary_rows, colWidths=[240, 150, 150])

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (0,1), (-1,1), bg_color),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('LINEABOVE', (0,1), (-1,1), 1.5, NAVY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    footer_style = ParagraphStyle('FooterLegalProv', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=7.5, leading=10, textColor=DARK_GRAY, alignment=1)
    story.append(Paragraph("<i>Documento generado automáticamente por ECONCATIVO Management System para control interno de cuenta corriente y comprobantes.</i>", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


