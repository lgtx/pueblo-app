import sqlite3

# Conexión reutilizable
def get_db_connection():
    conn = sqlite3.connect('pueblo.db')
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    return conn

# Inicializar la base de datos
def init_db():
    conn = get_db_connection()

    # Crear tabla de clientes con fecha_registro incluida
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT NOT NULL,
            fecha_registro TEXT
        )
    ''')

    # Crear tabla de préstamos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            monto INTEGER NOT NULL,
            plazo_dias INTEGER NOT NULL,
            interes REAL NOT NULL,
            cuotas INTEGER,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    # Tabla de pagos con desglose
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prestamo_id INTEGER NOT NULL,
            fecha_pago TEXT NOT NULL,
            monto_pagado INTEGER NOT NULL,
            mora_pagada INTEGER DEFAULT 0,
            interes_pagado INTEGER DEFAULT 0,
            capital_pagado INTEGER DEFAULT 0,
            observacion TEXT,
            FOREIGN KEY (prestamo_id) REFERENCES prestamos(id)
        )
    ''')

    conn.commit()
    conn.close()