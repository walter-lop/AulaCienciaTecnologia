PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    dni TEXT,
    grado INTEGER NOT NULL CHECK (grado BETWEEN 1 AND 5),
    seccion TEXT NOT NULL,
    sexo TEXT CHECK (sexo IN ('M', 'F') OR sexo IS NULL OR sexo = ''),
    fecha_nacimiento TEXT,
    direccion TEXT,
    telefono TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_estudiantes_grado_seccion
    ON estudiantes (grado, seccion);

CREATE TABLE IF NOT EXISTS padres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL
        REFERENCES estudiantes (id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    parentesco TEXT,
    telefono TEXT,
    dni TEXT
);

CREATE INDEX IF NOT EXISTS idx_padres_estudiante
    ON padres (estudiante_id);

CREATE TABLE IF NOT EXISTS calificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL
        REFERENCES estudiantes (id) ON DELETE CASCADE,
    competencia TEXT NOT NULL,
    bimestre INTEGER NOT NULL CHECK (bimestre BETWEEN 1 AND 4),
    nota TEXT NOT NULL CHECK (nota IN ('AD', 'A', 'B', 'C')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (estudiante_id, competencia, bimestre)
);

CREATE INDEX IF NOT EXISTS idx_calificaciones_estudiante
    ON calificaciones (estudiante_id, bimestre);

CREATE TABLE IF NOT EXISTS asistencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL
        REFERENCES estudiantes (id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL
        CHECK (estado IN ('presente', 'tarde', 'ausente', 'justificado')),
    observacion TEXT,
    UNIQUE (estudiante_id, fecha)
);

CREATE INDEX IF NOT EXISTS idx_asistencia_fecha
    ON asistencia (fecha);

CREATE TABLE IF NOT EXISTS comportamiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL
        REFERENCES estudiantes (id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('merito', 'observacion', 'llamado')),
    descripcion TEXT NOT NULL,
    accion TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_comportamiento_estudiante
    ON comportamiento (estudiante_id, fecha);

CREATE TABLE IF NOT EXISTS faltas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL
        REFERENCES estudiantes (id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL
        CHECK (tipo IN ('inasistencia', 'tardanza', 'leve', 'grave', 'muy_grave')),
    descripcion TEXT NOT NULL,
    medida TEXT,
    comunicado INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_faltas_estudiante
    ON faltas (estudiante_id, fecha);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
