from flask import Flask, render_template, request, redirect, url_for, jsonify
from db import get_db_connection
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)

@app.template_filter('formato_fecha')
def formato_fecha(fecha_str):
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
        return fecha.strftime('%d-%m-%Y')
    except:
        return fecha_str

def calcular_dias_mora(fecha_prestamo, plazo_dias):
    try:
        fecha_venc = datetime.strptime(fecha_prestamo, '%Y-%m-%d') + timedelta(days=plazo_dias)
        hoy = datetime.now()
        return max((hoy - fecha_venc).days, 0)
    except:
        return 0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    conn = get_db_connection()

    if request.method == 'POST':
        nombre         = request.form['nombre']
        rut            = request.form['rut']
        email          = request.form['email']        # <--- aquí
        telefono       = request.form['telefono']
        direccion      = request.form['direccion']
        fecha_registro = datetime.now().strftime('%Y-%m-%d')

        conn.execute('''
            INSERT INTO clientes (nombre, rut, email, telefono, direccion, fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, rut, email, telefono, direccion, fecha_registro))
        conn.commit()
        return redirect(url_for('clientes'))

    # Cargar clientes y préstamos
    clientes_rows = conn.execute('SELECT * FROM clientes ORDER BY id DESC').fetchall()
    prestamos     = conn.execute('SELECT * FROM prestamos').fetchall()
    conn.close()

    # Agrupar préstamos por cliente
    prestamos_por_cliente = {}
    for p in prestamos:
        prestamos_por_cliente.setdefault(p['cliente_id'], []).append(p)

    # Construir lista de clientes con estado
    clientes_list = []
    for c in clientes_rows:
        cp = prestamos_por_cliente.get(c['id'], [])
        total_monto = sum(p['monto'] for p in cp)
        tiene_mora  = any(
            datetime.strptime(p['fecha'], '%Y-%m-%d').date() + timedelta(days=p['plazo_dias']) < datetime.today().date()
            for p in cp
        )
        estado = 'mora' if tiene_mora else 'activo' if cp else 'pendiente'
        clientes_list.append({
            'id': c['id'],
            'nombre': c['nombre'],
            'rut': c['rut'],
            'email': c['email'],             # <--- aquí
            'telefono': c['telefono'],
            'direccion': c['direccion'],
            'prestamos': len(cp),
            'total': total_monto,
            'estado': estado,
            'fecha_registro': c['fecha_registro']
        })

    # KPIs
    total_clientes     = len(clientes_list)
    clientes_activos   = sum(1 for x in clientes_list if x['estado']=='activo')
    clientes_mora      = sum(1 for x in clientes_list if x['estado']=='mora')
    promedio_prestamos = round(sum(x['prestamos'] for x in clientes_list)/total_clientes,1) if total_clientes else 0

    return render_template(
        'clientes.html',
        clientes=clientes_list,
        total_clientes=total_clientes,
        clientes_activos=clientes_activos,
        clientes_mora=clientes_mora,
        promedio_prestamos=promedio_prestamos,
        active_page='clientes'
    )

@app.route('/api/cliente/<int:id>')
def api_cliente(id):
    conn = get_db_connection()
    cliente = conn.execute('''
        SELECT c.*, 
            COUNT(p.id) AS prestamos,
            IFNULL(SUM(p.monto), 0) AS total,
            CASE
                WHEN SUM(CASE WHEN p.estado = 'mora' THEN 1 ELSE 0 END) > 0 THEN 'mora'
                WHEN COUNT(p.id) = 0 THEN 'pendiente'
                ELSE 'activo'
            END AS estado
        FROM clientes c
        LEFT JOIN prestamos p ON p.cliente_id = c.id
        WHERE c.id = ?
        GROUP BY c.id
    ''', (id,)).fetchone()
    conn.close()
    if cliente is None:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    return jsonify(dict(cliente))

@app.route('/cliente/<int:id>/editar', methods=['POST'])
def actualizar_cliente(id):
    nombre    = request.form['nombre']
    rut       = request.form['rut']
    email     = request.form['email']    
    telefono  = request.form['telefono']
    direccion = request.form['direccion']

    conn = get_db_connection()
    conn.execute('''
        UPDATE clientes
           SET nombre = ?, rut = ?, email = ?, telefono = ?, direccion = ?
         WHERE id = ?
    ''', (nombre, rut, email, telefono, direccion, id))
    conn.commit()
    conn.close()
    return redirect(url_for('clientes'))

@app.route('/registro_prestamo_simple', methods=['GET', 'POST'])
def registro_prestamo_simple():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        monto       = int(request.form['monto'].replace('.', ''))
        plazo_dias  = int(request.form['plazo_dias'])
        interes     = float(request.form['interes'])
        fecha       = datetime.now().strftime('%Y-%m-%d')
        conn.execute('''
            INSERT INTO prestamos (cliente_id, tipo, fecha, monto, plazo_dias, interes)
            VALUES (?, 'simple', ?, ?, ?, ?)
        ''', (cliente_id, fecha, monto, plazo_dias, interes))
        conn.commit()
        conn.close()
        return redirect('/prestamos_simple')
    clientes = conn.execute('SELECT id, nombre FROM clientes').fetchall()
    conn.close()
    return render_template('registro_prestamo_simple.html', clientes=clientes)

@app.route('/prestamos_simple', methods=['GET', 'POST'])
def prestamos_simple():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        monto       = int(request.form['monto'])
        plazo_dias  = int(request.form['plazo_dias'])
        interes     = float(request.form['interes'])
        fecha       = datetime.now().strftime('%Y-%m-%d')
        conn.execute('''
            INSERT INTO prestamos (cliente_id, tipo, fecha, monto, plazo_dias, interes)
            VALUES (?, 'simple', ?, ?, ?, ?)
        ''', (cliente_id, fecha, monto, plazo_dias, interes))
        conn.commit()
        return redirect('/prestamos_simple')
    prestamos = conn.execute('''
        SELECT p.id, p.fecha, p.monto, p.plazo_dias, p.interes, c.nombre AS cliente_nombre
        FROM prestamos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.tipo = 'simple'
        ORDER BY p.id DESC
    ''').fetchall()
    conn.close()
    return render_template('prestamos_simple.html', prestamos=prestamos)

@app.route('/prestamos_cuotas', methods=['GET', 'POST'])
def prestamos_cuotas():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        monto       = int(request.form['monto'].replace('.', ''))
        cuotas      = int(request.form['cuotas'])
        plazo_dias  = int(request.form['plazo_dias'])
        interes     = float(request.form['interes'])
        fecha       = datetime.now().strftime('%Y-%m-%d')
        conn.execute('''
            INSERT INTO prestamos (cliente_id, tipo, fecha, monto, cuotas, plazo_dias, interes)
            VALUES (?, 'cuotas', ?, ?, ?, ?, ?)
        ''', (cliente_id, fecha, monto, cuotas, plazo_dias, interes))
        conn.commit()
        conn.close()
        return redirect('/prestamos_cuotas')
    prestamos = conn.execute('''
        SELECT p.*, c.nombre AS cliente_nombre
        FROM prestamos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.tipo = 'cuotas'
        ORDER BY p.fecha DESC
    ''').fetchall()
    conn.close()
    return render_template('prestamos_cuotas.html', prestamos=prestamos)

@app.route('/registro_prestamo_cuotas', methods=['GET', 'POST'])
def registro_prestamo_cuotas():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        monto       = int(request.form['monto'].replace('.', ''))
        cuotas      = int(request.form['cuotas'])
        plazo_dias  = int(request.form['plazo_dias'])
        interes     = float(request.form['interes'])
        fecha       = datetime.now().strftime('%Y-%m-%d')
        conn.execute('''
            INSERT INTO prestamos (cliente_id, tipo, fecha, monto, cuotas, plazo_dias, interes)
            VALUES (?, 'cuotas', ?, ?, ?, ?, ?)
        ''', (cliente_id, fecha, monto, cuotas, plazo_dias, interes))
        conn.commit()
        conn.close()
        return redirect('/prestamos_cuotas')
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('registro_prestamo_cuotas.html', clientes=clientes)

@app.route('/detalle_prestamo/<int:id>')
def detalle_prestamo(id):
    conn = get_db_connection()
    prestamo = conn.execute('''
        SELECT p.*, c.nombre AS cliente_nombre, c.email, c.telefono
        FROM prestamos p
        JOIN clientes c ON c.id = p.cliente_id
        WHERE p.id = ?
    ''', (id,)).fetchone()
    pagos = conn.execute('''
        SELECT fecha_pago, monto_pagado, mora_pagada, interes_pagado, capital_pagado
        FROM pagos
        WHERE prestamo_id = ?
        ORDER BY fecha_pago DESC
    ''', (id,)).fetchall()
    conn.close()
    if prestamo is None:
        return "Préstamo no encontrado", 404
    ganancia_proy = prestamo['monto'] * prestamo['interes'] / 100 if prestamo['monto'] else None
    dias_mora     = calcular_dias_mora(prestamo['fecha'], prestamo['plazo_dias'])
    fecha_inicio  = datetime.strptime(prestamo['fecha'], '%Y-%m-%d')
    fecha_venc    = fecha_inicio + timedelta(days=prestamo['plazo_dias'])
    return render_template('detalle_prestamo.html',
                           prestamo=prestamo,
                           ganancia_proyectada=ganancia_proy,
                           dias_mora=dias_mora,
                           fecha_vencimiento=fecha_venc,
                           pagos=pagos)

@app.route('/agregar_pago', methods=['POST'])
def agregar_pago():
    prestamo_id = int(request.form['prestamo_id'])
    fecha_pago  = datetime.now().strftime('%Y-%m-%d')
    monto_pagado= int(request.form['monto'].replace('.', ''))
    conn = get_db_connection()
    p = conn.execute('SELECT * FROM prestamos WHERE id = ?', (prestamo_id,)).fetchone()
    interes_total = p['monto'] * p['interes'] / 100
    dias_mora     = calcular_dias_mora(p['fecha'], p['plazo_dias'])
    mora_total    = int(p['monto'] * 0.01 * dias_mora)
    mora_pagada   = min(monto_pagado, mora_total)
    restante      = monto_pagado - mora_pagada
    interes_pagado= min(restante, interes_total)
    restante     -= interes_pagado
    capital_pagado= max(restante, 0)
    conn.execute('''
        INSERT INTO pagos (prestamo_id, fecha_pago, monto_pagado, mora_pagada, interes_pagado, capital_pagado)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (prestamo_id, fecha_pago, monto_pagado, mora_pagada, interes_pagado, capital_pagado))
    conn.commit()
    conn.close()
    return redirect(f'/detalle_prestamo/{prestamo_id}')

@app.route('/api/ganancias')
def api_ganancias():
    conn = sqlite3.connect('pueblo.db')
    c = conn.cursor()
    c.execute("""
        SELECT strftime('%m', fecha) as mes, SUM(monto * interes / 100.0) as ganancia
        FROM prestamos
        WHERE tipo = 'simple'
        GROUP BY mes
        ORDER BY mes
    """)
    rows = c.fetchall()
    conn.close()
    meses = {
        '01':'Enero','02':'Febrero','03':'Marzo','04':'Abril',
        '05':'Mayo','06':'Junio','07':'Julio','08':'Agosto',
        '09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre'
    }
    labels = [meses.get(m, m) for m, _ in rows]
    data   = [round(g or 0,0) for _, g in rows]
    return jsonify({'labels': labels, 'data': data})

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('pueblo.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = c.fetchone()[0]
    c.execute("SELECT fecha, plazo_dias, monto, interes FROM prestamos")
    prestamos = c.fetchall()
    prestamos_activos = prestamos_vencidos = total_ganancia = 0
    hoy = datetime.today().date()
    for fecha_str, plazo, monto, interes in prestamos:
        try:
            inicio = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            continue
        venc = inicio + timedelta(days=int(plazo))
        if venc >= hoy:
            prestamos_activos += 1
        else:
            prestamos_vencidos += 1
        total_ganancia += monto * interes / 100.0
    conn.close()
    return render_template('dashboard.html',
                           total_clientes=total_clientes,
                           prestamos_activos=prestamos_activos,
                           prestamos_vencidos=prestamos_vencidos,
                           total_ganancia=total_ganancia,
                           active_page='dashboard')

@app.route('/cliente/<int:id>/eliminar', methods=['POST'])
def eliminar_cliente(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM clientes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/clientes')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)