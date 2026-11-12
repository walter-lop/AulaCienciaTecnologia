# -*- coding: utf-8 -*-
"""
Aula CyT - Registro docente de Ciencia y Tecnología
Sistema web local para 1.° a 5.° de secundaria.

Creado por: Walter López Culqui
"""

from __future__ import annotations

import csv
import io
import os
import re
import socket
import sqlite3
import tempfile
from datetime import date, datetime

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "aula-cyt-cambia-esta-clave-2026"),
    DATABASE=os.environ.get(
        "DATABASE_PATH", os.path.join(app.instance_path, "registro.db")
    ),
    MAX_CONTENT_LENGTH=15 * 1024 * 1024,
)
os.makedirs(app.instance_path, exist_ok=True)

# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

GRADOS = [1, 2, 3, 4, 5]
SECCIONES = ["A", "B", "C", "D", "E"]
BIMESTRES = [1, 2, 3, 4]

NOTAS = {
    "AD": "Logro destacado",
    "A": "Logro esperado",
    "B": "En proceso",
    "C": "En inicio",
}

COMPETENCIAS = [
    {
        "codigo": "indaga",
        "nombre": "Indaga mediante métodos científicos",
        "descripcion": "Construye conocimientos científicos a partir de la indagación.",
    },
    {
        "codigo": "explica",
        "nombre": "Explica el mundo físico",
        "descripcion": "Comprende y explica los fenómenos naturales y la tecnología.",
    },
    {
        "codigo": "disena",
        "nombre": "Diseña y construye soluciones tecnológicas",
        "descripcion": "Diseña y construye soluciones para problemas de su entorno.",
    },
]
COMPETENCIAS_MAP = {c["codigo"]: c for c in COMPETENCIAS}

ESTADOS_ASISTENCIA = {
    "presente": "Presente",
    "tarde": "Tarde",
    "ausente": "Ausente",
    "justificado": "Justificado",
}

TIPOS_COMPORTAMIENTO = {
    "merito": {"nombre": "Mérito / aspecto positivo", "clase": "merito"},
    "observacion": {"nombre": "Observación", "clase": "observacion"},
    "llamado": {"nombre": "Llamado de atención", "clase": "llamado"},
}

TIPOS_FALTA = {
    "inasistencia": "Inasistencia injustificada",
    "tardanza": "Tardanza reiterada",
    "leve": "Falta leve",
    "grave": "Falta grave",
    "muy_grave": "Falta muy grave",
}

CONFIG_DEFAULTS = {
    "ie_nombre": "Institución Educativa",
    "docente": "Walter López Culqui",
    "anio": str(datetime.now().year),
}

MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as archivo:
        db.executescript(archivo.read())
    db.commit()


with app.app_context():
    init_db()


def obtener_config() -> dict:
    config = dict(CONFIG_DEFAULTS)
    for fila in get_db().execute("SELECT clave, valor FROM configuracion"):
        config[fila["clave"]] = fila["valor"]
    return config


def guardar_config(clave: str, valor: str) -> None:
    get_db().execute(
        """
        INSERT INTO configuracion (clave, valor) VALUES (?, ?)
        ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
        """,
        (clave, valor),
    )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _texto(valor, limite: int = 200) -> str:
    return (valor or "").strip()[:limite]


def _fecha_iso(valor, defecto=None):
    valor = (valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            continue
    return defecto


def _combo_inicial(db):
    combos = db.execute(
        "SELECT DISTINCT grado, seccion FROM estudiantes ORDER BY grado, seccion"
    ).fetchall()
    if not combos:
        return None, None, combos
    return combos[0]["grado"], combos[0]["seccion"], combos


def _seccion_para_grado(combos, grado, seccion):
    secciones = [c["seccion"] for c in combos if c["grado"] == grado]
    if seccion in secciones:
        return seccion
    return secciones[0] if secciones else (combos[0]["seccion"] if combos else "A")


def _estudiantes_de(db, grado, seccion):
    return db.execute(
        """
        SELECT * FROM estudiantes
        WHERE grado = ? AND seccion = ?
        ORDER BY apellidos COLLATE NOCASE, nombres COLLATE NOCASE
        """,
        (grado, seccion),
    ).fetchall()


def _resumen_asistencia(db, estudiante_id):
    filas = db.execute(
        "SELECT estado, COUNT(*) AS total FROM asistencia WHERE estudiante_id = ? GROUP BY estado",
        (estudiante_id,),
    ).fetchall()
    resumen = {clave: 0 for clave in ESTADOS_ASISTENCIA}
    for fila in filas:
        resumen[fila["estado"]] = fila["total"]
    total = sum(resumen.values())
    efectiva = resumen["presente"] + resumen["tarde"]
    porcentaje = round(efectiva * 100 / total) if total else 0
    return resumen, total, porcentaje


def _padres_desde_form():
    nombres = request.form.getlist("padre_nombre")
    parentescos = request.form.getlist("padre_parentesco")
    telefonos = request.form.getlist("padre_telefono")
    dnis = request.form.getlist("padre_dni")
    padres = []
    for i, nombre in enumerate(nombres):
        nombre = _texto(nombre, 120)
        if not nombre:
            continue
        padres.append(
            {
                "nombre": nombre,
                "parentesco": _texto(
                    parentescos[i] if i < len(parentescos) else "", 40
                ),
                "telefono": _texto(
                    telefonos[i] if i < len(telefonos) else "", 30
                ),
                "dni": _texto(dnis[i] if i < len(dnis) else "", 12),
            }
        )
    return padres


def _datos_estudiante_form():
    grado = request.form.get("grado", type=int)
    return {
        "nombres": _texto(request.form.get("nombres"), 80),
        "apellidos": _texto(request.form.get("apellidos"), 80),
        "dni": _texto(request.form.get("dni"), 12),
        "grado": grado,
        "seccion": _texto(request.form.get("seccion"), 2).upper(),
        "sexo": _texto(request.form.get("sexo"), 1).upper(),
        "fecha_nacimiento": _fecha_iso(request.form.get("fecha_nacimiento"), ""),
        "direccion": _texto(request.form.get("direccion"), 200),
        "telefono": _texto(request.form.get("telefono"), 30),
    }


def _validar_estudiante(datos, db=None, estudiante_id=None):
    errores = []
    if not datos["nombres"]:
        errores.append("Los nombres son obligatorios.")
    if not datos["apellidos"]:
        errores.append("Los apellidos son obligatorios.")
    if datos["grado"] not in GRADOS:
        errores.append("Selecciona un grado válido (1.° a 5.°).")
    if not datos["seccion"]:
        errores.append("Selecciona una sección.")
    if datos["dni"] and not re.fullmatch(r"\d{8}", datos["dni"]):
        errores.append("El DNI debe tener exactamente 8 dígitos.")
    if datos["sexo"] not in ("", "M", "F"):
        errores.append("Selecciona un sexo válido.")
    if db is not None and datos["dni"] and re.fullmatch(r"\d{8}", datos["dni"]):
        if estudiante_id is None:
            duplicado = db.execute(
                "SELECT 1 FROM estudiantes WHERE dni = ?", (datos["dni"],)
            ).fetchone()
        else:
            duplicado = db.execute(
                "SELECT 1 FROM estudiantes WHERE dni = ? AND id <> ?",
                (datos["dni"], estudiante_id),
            ).fetchone()
        if duplicado:
            errores.append("Ya existe un estudiante registrado con ese DNI.")
    return errores


def _guardar_padres(db, estudiante_id, padres):
    for padre in padres:
        db.execute(
            """
            INSERT INTO padres (estudiante_id, nombre, parentesco, telefono, dni)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                estudiante_id,
                padre["nombre"],
                padre["parentesco"],
                padre["telefono"],
                padre["dni"],
            ),
        )


def _nota_badge(nota):
    return nota if nota in NOTAS else ""


# ---------------------------------------------------------------------------
# Filtros y contexto de plantillas
# ---------------------------------------------------------------------------


@app.template_filter("fecha")
def fecha_filter(valor):
    if not valor:
        return "—"
    try:
        fecha = datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        return valor
    return fecha.strftime("%d/%m/%Y")


@app.template_filter("fecha_larga")
def fecha_larga_filter(valor):
    if not valor:
        return "—"
    try:
        fecha = datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        return valor
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


@app.template_filter("iniciales")
def iniciales_filter(estudiante):
    nombres = (estudiante["nombres"] or " ").strip()
    apellidos = (estudiante["apellidos"] or " ").strip()
    return ((nombres[:1] + apellidos[:1]) or "?").upper()


@app.template_filter("nota_clase")
def nota_clase_filter(nota):
    return _nota_badge(nota).lower() or "sin-nota"


@app.context_processor
def injectar_globales():
    return {
        "cfg": obtener_config(),
        "GRADOS": GRADOS,
        "SECCIONES": SECCIONES,
        "BIMESTRES": BIMESTRES,
        "NOTAS": NOTAS,
        "COMPETENCIAS": COMPETENCIAS,
        "COMPETENCIAS_MAP": COMPETENCIAS_MAP,
        "ESTADOS_ASISTENCIA": ESTADOS_ASISTENCIA,
        "TIPOS_COMPORTAMIENTO": TIPOS_COMPORTAMIENTO,
        "TIPOS_FALTA": TIPOS_FALTA,
        "creador": "Walter López Culqui",
        "hoy": date.today().isoformat(),
        "anio_actual": datetime.now().year,
    }


# ---------------------------------------------------------------------------
# Inicio
# ---------------------------------------------------------------------------


@app.route("/")
def inicio():
    db = get_db()
    hoy_iso = date.today().isoformat()

    total_estudiantes = db.execute(
        "SELECT COUNT(*) AS total FROM estudiantes"
    ).fetchone()["total"]
    total_secciones = db.execute(
        "SELECT COUNT(DISTINCT grado || '-' || seccion) AS total FROM estudiantes"
    ).fetchone()["total"]

    conteo_hoy = {
        fila["estado"]: fila["total"]
        for fila in db.execute(
            "SELECT estado, COUNT(*) AS total FROM asistencia WHERE fecha = ? GROUP BY estado",
            (hoy_iso,),
        )
    }
    marcados_hoy = sum(conteo_hoy.values())
    efectivos_hoy = conteo_hoy.get("presente", 0) + conteo_hoy.get("tarde", 0)
    porcentaje_hoy = (
        round(efectivos_hoy * 100 / marcados_hoy) if marcados_hoy else None
    )

    inicio_mes = date.today().replace(day=1).isoformat()
    incidencias_mes = db.execute(
        "SELECT COUNT(*) AS total FROM comportamiento WHERE fecha >= ?", (inicio_mes,)
    ).fetchone()["total"] + db.execute(
        "SELECT COUNT(*) AS total FROM faltas WHERE fecha >= ?", (inicio_mes,)
    ).fetchone()[
        "total"
    ]

    por_grado = {grado: 0 for grado in GRADOS}
    for fila in db.execute(
        "SELECT grado, COUNT(*) AS total FROM estudiantes GROUP BY grado"
    ):
        por_grado[fila["grado"]] = fila["total"]

    recientes = db.execute(
        """
        SELECT * FROM (
            SELECT 'comportamiento' AS clase, c.id, c.fecha, c.tipo, c.descripcion,
                   e.nombres, e.apellidos, e.grado, e.seccion, e.id AS estudiante_id
            FROM comportamiento c
            JOIN estudiantes e ON e.id = c.estudiante_id
            UNION ALL
            SELECT 'falta' AS clase, f.id, f.fecha, f.tipo, f.descripcion,
                   e.nombres, e.apellidos, e.grado, e.seccion, e.id AS estudiante_id
            FROM faltas f
            JOIN estudiantes e ON e.id = f.estudiante_id
        )
        ORDER BY fecha DESC, id DESC
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "inicio.html",
        total_estudiantes=total_estudiantes,
        total_secciones=total_secciones,
        conteo_hoy=conteo_hoy,
        marcados_hoy=marcados_hoy,
        efectivos_hoy=efectivos_hoy,
        porcentaje_hoy=porcentaje_hoy,
        incidencias_mes=incidencias_mes,
        por_grado=por_grado,
        recientes=recientes,
        max_grado=max(por_grado.values()) if por_grado else 0,
    )


# ---------------------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------------------


@app.route("/estudiantes")
def estudiantes():
    db = get_db()
    grado = request.args.get("grado", type=int)
    seccion = _texto(request.args.get("seccion"), 2).upper()
    q = _texto(request.args.get("q"), 80)

    sql = """
        SELECT e.*,
               (SELECT COUNT(*) FROM padres p WHERE p.estudiante_id = e.id) AS total_padres,
               (SELECT p.telefono FROM padres p
                 WHERE p.estudiante_id = e.id AND p.telefono <> ''
                 ORDER BY p.id LIMIT 1) AS telefono_apoderado
        FROM estudiantes e
        WHERE 1 = 1
    """
    parametros = []
    if grado in GRADOS:
        sql += " AND e.grado = ?"
        parametros.append(grado)
    if seccion:
        sql += " AND e.seccion = ?"
        parametros.append(seccion)
    if q:
        sql += " AND (e.nombres LIKE ? OR e.apellidos LIKE ? OR e.dni LIKE ?)"
        parametros.extend([f"%{q}%"] * 3)
    sql += " ORDER BY e.grado, e.seccion, e.apellidos COLLATE NOCASE, e.nombres COLLATE NOCASE"

    lista = db.execute(sql, parametros).fetchall()
    return render_template(
        "estudiantes_lista.html",
        estudiantes=lista,
        grado=grado,
        seccion=seccion,
        q=q,
    )


@app.route("/estudiantes/nuevo", methods=["GET", "POST"])
def estudiante_nuevo():
    db = get_db()

    if request.method == "POST":
        datos = _datos_estudiante_form()
        padres = _padres_desde_form()
        errores = _validar_estudiante(datos, db)
        if errores:
            for error in errores:
                flash(error, "error")
            return render_template(
                "estudiante_form.html",
                estudiante=datos,
                padres=padres,
                modo="nuevo",
            )

        cursor = db.execute(
            """
            INSERT INTO estudiantes
                (nombres, apellidos, dni, grado, seccion, sexo,
                 fecha_nacimiento, direccion, telefono)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datos["nombres"],
                datos["apellidos"],
                datos["dni"],
                datos["grado"],
                datos["seccion"],
                datos["sexo"],
                datos["fecha_nacimiento"],
                datos["direccion"],
                datos["telefono"],
            ),
        )
        _guardar_padres(db, cursor.lastrowid, padres)
        db.commit()
        flash(
            f"Estudiante {datos['nombres']} {datos['apellidos']} registrado correctamente.",
            "exito",
        )
        return redirect(url_for("estudiante_detalle", estudiante_id=cursor.lastrowid))

    datos = {
        "nombres": _texto(request.args.get("nombres"), 80),
        "apellidos": _texto(request.args.get("apellidos"), 80),
        "dni": _texto(request.args.get("dni"), 12),
        "grado": request.args.get("grado", type=int),
        "seccion": _texto(request.args.get("seccion"), 2).upper(),
        "sexo": _texto(request.args.get("sexo"), 1).upper(),
        "fecha_nacimiento": _fecha_iso(
            request.args.get("fecha_nacimiento"), ""
        ),
        "direccion": "",
        "telefono": "",
    }
    return render_template(
        "estudiante_form.html", estudiante=datos, padres=[], modo="nuevo"
    )


@app.route("/estudiantes/<int:estudiante_id>/editar", methods=["GET", "POST"])
def estudiante_editar(estudiante_id):
    db = get_db()
    fila = db.execute(
        "SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)
    ).fetchone()
    if fila is None:
        abort(404)

    if request.method == "POST":
        datos = _datos_estudiante_form()
        padres = _padres_desde_form()
        errores = _validar_estudiante(datos, db, estudiante_id)
        if errores:
            for error in errores:
                flash(error, "error")
            datos["id"] = estudiante_id
            return render_template(
                "estudiante_form.html",
                estudiante=datos,
                padres=padres,
                modo="editar",
            )

        db.execute(
            """
            UPDATE estudiantes SET
                nombres = ?, apellidos = ?, dni = ?, grado = ?, seccion = ?,
                sexo = ?, fecha_nacimiento = ?, direccion = ?, telefono = ?
            WHERE id = ?
            """,
            (
                datos["nombres"],
                datos["apellidos"],
                datos["dni"],
                datos["grado"],
                datos["seccion"],
                datos["sexo"],
                datos["fecha_nacimiento"],
                datos["direccion"],
                datos["telefono"],
                estudiante_id,
            ),
        )
        db.execute("DELETE FROM padres WHERE estudiante_id = ?", (estudiante_id,))
        _guardar_padres(db, estudiante_id, padres)
        db.commit()
        flash("Datos del estudiante actualizados.", "exito")
        return redirect(url_for("estudiante_detalle", estudiante_id=estudiante_id))

    datos = dict(fila)
    padres = [
        dict(p)
        for p in db.execute(
            "SELECT * FROM padres WHERE estudiante_id = ? ORDER BY id",
            (estudiante_id,),
        )
    ]
    return render_template(
        "estudiante_form.html", estudiante=datos, padres=padres, modo="editar"
    )


@app.route("/estudiantes/<int:estudiante_id>")
def estudiante_detalle(estudiante_id):
    db = get_db()
    estudiante = db.execute(
        "SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)
    ).fetchone()
    if estudiante is None:
        abort(404)

    padres = db.execute(
        "SELECT * FROM padres WHERE estudiante_id = ? ORDER BY id", (estudiante_id,)
    ).fetchall()

    notas = {}
    for fila in db.execute(
        "SELECT competencia, bimestre, nota FROM calificaciones WHERE estudiante_id = ?",
        (estudiante_id,),
    ):
        notas[f"{fila['competencia']}:{fila['bimestre']}"] = fila["nota"]

    resumen_asistencia, total_asistencia, porcentaje_asistencia = _resumen_asistencia(
        db, estudiante_id
    )

    comportamiento = db.execute(
        """
        SELECT * FROM comportamiento WHERE estudiante_id = ?
        ORDER BY fecha DESC, id DESC
        """,
        (estudiante_id,),
    ).fetchall()

    faltas = db.execute(
        """
        SELECT * FROM faltas WHERE estudiante_id = ?
        ORDER BY fecha DESC, id DESC
        """,
        (estudiante_id,),
    ).fetchall()

    return render_template(
        "estudiante_detalle.html",
        estudiante=estudiante,
        padres=padres,
        notas=notas,
        resumen_asistencia=resumen_asistencia,
        total_asistencia=total_asistencia,
        porcentaje_asistencia=porcentaje_asistencia,
        comportamiento=comportamiento,
        faltas=faltas,
    )


@app.route("/estudiantes/<int:estudiante_id>/eliminar", methods=["POST"])
def estudiante_eliminar(estudiante_id):
    db = get_db()
    fila = db.execute(
        "SELECT nombres, apellidos FROM estudiantes WHERE id = ?", (estudiante_id,)
    ).fetchone()
    if fila is None:
        abort(404)
    db.execute("DELETE FROM estudiantes WHERE id = ?", (estudiante_id,))
    db.commit()
    flash(
        f"Se eliminó a {fila['nombres']} {fila['apellidos']} y todos sus registros.",
        "info",
    )
    return redirect(url_for("estudiantes"))


# ---------------------------------------------------------------------------
# Calificaciones
# ---------------------------------------------------------------------------


@app.route("/calificaciones", methods=["GET", "POST"])
def calificaciones():
    db = get_db()
    grado_inicial, seccion_inicial, combos = _combo_inicial(db)

    if request.method == "POST":
        grado = request.form.get("grado", type=int)
        seccion = _texto(request.form.get("seccion"), 2).upper()
        bimestre = request.form.get("bimestre", type=int)
        if grado not in GRADOS or not seccion or bimestre not in BIMESTRES:
            flash("Los filtros enviados no son válidos.", "error")
            return redirect(url_for("calificaciones"))

        lista = _estudiantes_de(db, grado, seccion)
        for estudiante in lista:
            for competencia in COMPETENCIAS:
                campo = f"nota_{estudiante['id']}_{competencia['codigo']}"
                nota = _texto(request.form.get(campo), 2).upper()
                if nota in NOTAS:
                    db.execute(
                        """
                        INSERT INTO calificaciones
                            (estudiante_id, competencia, bimestre, nota, actualizado_en)
                        VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
                        ON CONFLICT(estudiante_id, competencia, bimestre)
                        DO UPDATE SET nota = excluded.nota,
                                      actualizado_en = excluded.actualizado_en
                        """,
                        (estudiante["id"], competencia["codigo"], bimestre, nota),
                    )
                else:
                    db.execute(
                        """
                        DELETE FROM calificaciones
                        WHERE estudiante_id = ? AND competencia = ? AND bimestre = ?
                        """,
                        (estudiante["id"], competencia["codigo"], bimestre),
                    )
        db.commit()
        flash(
            f"Calificaciones del {bimestre}.° bimestre guardadas para {grado}.° {seccion}.",
            "exito",
        )
        return redirect(
            url_for(
                "calificaciones", grado=grado, seccion=seccion, bimestre=bimestre
            )
        )

    grado = request.args.get("grado", type=int)
    seccion = _texto(request.args.get("seccion"), 2).upper()
    bimestre = request.args.get("bimestre", type=int)

    if not combos:
        return render_template(
            "calificaciones.html",
            estudiantes=[],
            notas={},
            grado=None,
            seccion=None,
            bimestre=1,
            sin_datos=True,
        )

    if grado not in GRADOS:
        grado = grado_inicial
    seccion = _seccion_para_grado(combos, grado, seccion)
    if bimestre not in BIMESTRES:
        bimestre = 1

    lista = _estudiantes_de(db, grado, seccion)
    notas = {}
    if lista:
        marcadores = ",".join("?" for _ in lista)
        parametros = [e["id"] for e in lista] + [bimestre]
        for fila in db.execute(
            f"""
            SELECT estudiante_id, competencia, nota FROM calificaciones
            WHERE estudiante_id IN ({marcadores}) AND bimestre = ?
            """,
            parametros,
        ):
            notas[f"{fila['estudiante_id']}:{fila['competencia']}"] = fila["nota"]

    return render_template(
        "calificaciones.html",
        estudiantes=lista,
        notas=notas,
        grado=grado,
        seccion=seccion,
        bimestre=bimestre,
        sin_datos=False,
    )


# ---------------------------------------------------------------------------
# Asistencia
# ---------------------------------------------------------------------------


@app.route("/asistencia", methods=["GET", "POST"])
def asistencia():
    db = get_db()

    if request.method == "POST":
        grado = request.form.get("grado", type=int)
        seccion = _texto(request.form.get("seccion"), 2).upper()
        fecha = _fecha_iso(request.form.get("fecha"), "")
        if grado not in GRADOS or not seccion or not fecha:
            flash("No se pudo guardar: filtros o fecha no válidos.", "error")
            return redirect(url_for("asistencia"))

        for estudiante in _estudiantes_de(db, grado, seccion):
            estado = _texto(request.form.get(f"estado_{estudiante['id']}"), 20)
            observacion = _texto(
                request.form.get(f"obs_{estudiante['id']}"), 200
            )
            if estado in ESTADOS_ASISTENCIA:
                db.execute(
                    """
                    INSERT INTO asistencia (estudiante_id, fecha, estado, observacion)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(estudiante_id, fecha)
                    DO UPDATE SET estado = excluded.estado,
                                  observacion = excluded.observacion
                    """,
                    (estudiante["id"], fecha, estado, observacion),
                )
            else:
                db.execute(
                    "DELETE FROM asistencia WHERE estudiante_id = ? AND fecha = ?",
                    (estudiante["id"], fecha),
                )
        db.commit()
        flash(f"Asistencia de {grado}.° {seccion} guardada para el {fecha}.", "exito")
        return redirect(
            url_for("asistencia", grado=grado, seccion=seccion, fecha=fecha)
        )

    grado_inicial, seccion_inicial, combos = _combo_inicial(db)
    grado = request.args.get("grado", type=int)
    seccion = _texto(request.args.get("seccion"), 2).upper()
    fecha = _fecha_iso(request.args.get("fecha"), date.today().isoformat())

    if not combos:
        return render_template(
            "asistencia.html",
            estudiantes=[],
            registros={},
            resumen={clave: 0 for clave in ESTADOS_ASISTENCIA},
            sin_registrar=0,
            grado=None,
            seccion=None,
            fecha=fecha,
            sin_datos=True,
        )

    if grado not in GRADOS:
        grado = grado_inicial
    seccion = _seccion_para_grado(combos, grado, seccion)

    lista = _estudiantes_de(db, grado, seccion)
    registros = {}
    if lista:
        marcadores = ",".join("?" for _ in lista)
        parametros = [fecha] + [e["id"] for e in lista]
        for fila in db.execute(
            f"""
            SELECT * FROM asistencia
            WHERE fecha = ? AND estudiante_id IN ({marcadores})
            """,
            parametros,
        ):
            registros[fila["estudiante_id"]] = fila

    resumen = {clave: 0 for clave in ESTADOS_ASISTENCIA}
    for fila in registros.values():
        resumen[fila["estado"]] += 1
    sin_registrar = len(lista) - len(registros)

    return render_template(
        "asistencia.html",
        estudiantes=lista,
        registros=registros,
        resumen=resumen,
        sin_registrar=sin_registrar,
        grado=grado,
        seccion=seccion,
        fecha=fecha,
        sin_datos=False,
    )


# ---------------------------------------------------------------------------
# Comportamiento
# ---------------------------------------------------------------------------


@app.route("/comportamiento", methods=["GET", "POST"])
def comportamiento():
    db = get_db()

    if request.method == "POST":
        estudiante_id = request.form.get("estudiante_id", type=int)
        estudiante = db.execute(
            "SELECT id, grado, seccion FROM estudiantes WHERE id = ?",
            (estudiante_id,),
        ).fetchone()
        fecha = _fecha_iso(request.form.get("fecha"), "")
        tipo = _texto(request.form.get("tipo"), 20)
        descripcion = _texto(request.form.get("descripcion"), 1000)
        accion = _texto(request.form.get("accion"), 500)

        if estudiante is None or not fecha or tipo not in TIPOS_COMPORTAMIENTO:
            flash("Completa el estudiante, la fecha y el tipo de registro.", "error")
            return redirect(url_for("comportamiento"))
        if not descripcion:
            flash("Escribe una descripción del comportamiento.", "error")
            return redirect(url_for("comportamiento"))

        db.execute(
            """
            INSERT INTO comportamiento
                (estudiante_id, fecha, tipo, descripcion, accion)
            VALUES (?, ?, ?, ?, ?)
            """,
            (estudiante_id, fecha, tipo, descripcion, accion),
        )
        db.commit()
        flash("Registro de comportamiento guardado.", "exito")
        return redirect(
            url_for(
                "comportamiento",
                grado=estudiante["grado"],
                seccion=estudiante["seccion"],
            )
        )

    grado = request.args.get("grado", type=int)
    seccion = _texto(request.args.get("seccion"), 2).upper()
    tipo = _texto(request.args.get("tipo"), 20)
    preseleccionado = request.args.get("estudiante_id", type=int)

    sql = """
        SELECT c.*, e.nombres, e.apellidos, e.grado, e.seccion
        FROM comportamiento c
        JOIN estudiantes e ON e.id = c.estudiante_id
        WHERE 1 = 1
    """
    parametros = []
    if grado in GRADOS:
        sql += " AND e.grado = ?"
        parametros.append(grado)
    if seccion:
        sql += " AND e.seccion = ?"
        parametros.append(seccion)
    if tipo in TIPOS_COMPORTAMIENTO:
        sql += " AND c.tipo = ?"
        parametros.append(tipo)
    sql += " ORDER BY c.fecha DESC, c.id DESC LIMIT 300"

    registros = db.execute(sql, parametros).fetchall()
    estudiantes_todos = db.execute(
        """
        SELECT id, nombres, apellidos, grado, seccion FROM estudiantes
        ORDER BY grado, seccion, apellidos COLLATE NOCASE, nombres COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "comportamiento.html",
        registros=registros,
        estudiantes_todos=estudiantes_todos,
        grado=grado,
        seccion=seccion,
        tipo=tipo,
        preseleccionado=preseleccionado,
    )


@app.route("/comportamiento/<int:registro_id>/eliminar", methods=["POST"])
def comportamiento_eliminar(registro_id):
    db = get_db()
    db.execute("DELETE FROM comportamiento WHERE id = ?", (registro_id,))
    db.commit()
    flash("Registro de comportamiento eliminado.", "info")
    return redirect(url_for("comportamiento"))


# ---------------------------------------------------------------------------
# Faltas
# ---------------------------------------------------------------------------


@app.route("/faltas", methods=["GET", "POST"])
def faltas():
    db = get_db()

    if request.method == "POST":
        estudiante_id = request.form.get("estudiante_id", type=int)
        estudiante = db.execute(
            "SELECT id, grado, seccion FROM estudiantes WHERE id = ?",
            (estudiante_id,),
        ).fetchone()
        fecha = _fecha_iso(request.form.get("fecha"), "")
        tipo = _texto(request.form.get("tipo"), 20)
        descripcion = _texto(request.form.get("descripcion"), 1000)
        medida = _texto(request.form.get("medida"), 500)
        comunicado = 1 if request.form.get("comunicado") else 0

        if estudiante is None or not fecha or tipo not in TIPOS_FALTA:
            flash("Completa el estudiante, la fecha y el tipo de falta.", "error")
            return redirect(url_for("faltas"))
        if not descripcion:
            flash("Describe la falta registrada.", "error")
            return redirect(url_for("faltas"))

        db.execute(
            """
            INSERT INTO faltas
                (estudiante_id, fecha, tipo, descripcion, medida, comunicado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (estudiante_id, fecha, tipo, descripcion, medida, comunicado),
        )
        db.commit()
        flash("Falta registrada correctamente.", "exito")
        return redirect(
            url_for("faltas", grado=estudiante["grado"], seccion=estudiante["seccion"])
        )

    grado = request.args.get("grado", type=int)
    seccion = _texto(request.args.get("seccion"), 2).upper()
    tipo = _texto(request.args.get("tipo"), 20)
    preseleccionado = request.args.get("estudiante_id", type=int)

    sql = """
        SELECT f.*, e.nombres, e.apellidos, e.grado, e.seccion
        FROM faltas f
        JOIN estudiantes e ON e.id = f.estudiante_id
        WHERE 1 = 1
    """
    parametros = []
    if grado in GRADOS:
        sql += " AND e.grado = ?"
        parametros.append(grado)
    if seccion:
        sql += " AND e.seccion = ?"
        parametros.append(seccion)
    if tipo in TIPOS_FALTA:
        sql += " AND f.tipo = ?"
        parametros.append(tipo)
    sql += " ORDER BY f.fecha DESC, f.id DESC LIMIT 300"

    registros = db.execute(sql, parametros).fetchall()
    estudiantes_todos = db.execute(
        """
        SELECT id, nombres, apellidos, grado, seccion FROM estudiantes
        ORDER BY grado, seccion, apellidos COLLATE NOCASE, nombres COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "faltas.html",
        registros=registros,
        estudiantes_todos=estudiantes_todos,
        grado=grado,
        seccion=seccion,
        tipo=tipo,
        preseleccionado=preseleccionado,
    )


@app.route("/faltas/<int:registro_id>/eliminar", methods=["POST"])
def falta_eliminar(registro_id):
    db = get_db()
    db.execute("DELETE FROM faltas WHERE id = ?", (registro_id,))
    db.commit()
    flash("Registro de falta eliminado.", "info")
    return redirect(url_for("faltas"))


# ---------------------------------------------------------------------------
# Anexo imprimible
# ---------------------------------------------------------------------------


@app.route("/estudiantes/<int:estudiante_id>/anexo")
def estudiante_anexo(estudiante_id):
    db = get_db()
    estudiante = db.execute(
        "SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)
    ).fetchone()
    if estudiante is None:
        abort(404)

    padres = db.execute(
        "SELECT * FROM padres WHERE estudiante_id = ? ORDER BY id", (estudiante_id,)
    ).fetchall()
    comportamiento = db.execute(
        """
        SELECT * FROM comportamiento WHERE estudiante_id = ?
        ORDER BY fecha ASC, id ASC
        """,
        (estudiante_id,),
    ).fetchall()
    faltas = db.execute(
        """
        SELECT * FROM faltas WHERE estudiante_id = ?
        ORDER BY fecha ASC, id ASC
        """,
        (estudiante_id,),
    ).fetchall()
    resumen_asistencia, total_asistencia, porcentaje_asistencia = _resumen_asistencia(
        db, estudiante_id
    )

    conteo_comportamiento = {clave: 0 for clave in TIPOS_COMPORTAMIENTO}
    for fila in comportamiento:
        conteo_comportamiento[fila["tipo"]] += 1
    conteo_faltas = {clave: 0 for clave in TIPOS_FALTA}
    for fila in faltas:
        conteo_faltas[fila["tipo"]] += 1

    return render_template(
        "anexo.html",
        estudiante=estudiante,
        padres=padres,
        comportamiento=comportamiento,
        faltas=faltas,
        resumen_asistencia=resumen_asistencia,
        total_asistencia=total_asistencia,
        porcentaje_asistencia=porcentaje_asistencia,
        conteo_comportamiento=conteo_comportamiento,
        conteo_faltas=conteo_faltas,
    )


# ---------------------------------------------------------------------------
# Escáner de DNI
# ---------------------------------------------------------------------------


@app.route("/escaner")
def escaner():
    return render_template("escaner.html")


def _configurar_tesseract(pytesseract):
    candidatos = [
        os.environ.get("TESSERACT_CMD"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for candidato in candidatos:
        if candidato and os.path.exists(candidato):
            pytesseract.pytesseract.tesseract_cmd = candidato
            return


def _ocr_imagen(ruta):
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError:
        return None, (
            "El lector automático no está instalado. Puedes completar los datos "
            "manualmente o instalar Tesseract OCR (revisa el README)."
        )

    _configurar_tesseract(pytesseract)
    try:
        with Image.open(ruta) as original:
            imagen = ImageOps.exif_transpose(original)
            imagen = imagen.convert("RGB")
            lado_mayor = max(imagen.size)
            if lado_mayor < 1600:
                factor = 1600 / lado_mayor
                imagen = imagen.resize(
                    (round(imagen.width * factor), round(imagen.height * factor)),
                    Image.Resampling.LANCZOS,
                )
            elif lado_mayor > 3000:
                factor = 3000 / lado_mayor
                imagen = imagen.resize(
                    (round(imagen.width * factor), round(imagen.height * factor)),
                    Image.Resampling.LANCZOS,
                )
            imagen = ImageOps.grayscale(imagen)
            imagen = ImageOps.autocontrast(imagen)

        try:
            texto = pytesseract.image_to_string(
                imagen, lang="spa", config="--psm 6"
            )
        except Exception:
            texto = pytesseract.image_to_string(imagen, config="--psm 6")
        return texto, None
    except Exception:
        return None, (
            "No se pudo leer la imagen. Verifica que Tesseract OCR esté instalado "
            "y que la foto tenga buena luz y enfoque."
        )


ETIQUETAS_IGNORADAS = {
    "PERU",
    "PERÚ",
    "REPUBLICA",
    "REPÚBLICA",
    "DOCUMENTO",
    "NACIONAL",
    "IDENTIDAD",
    "DNI",
    "APELLIDOS",
    "APELLIDO",
    "NOMBRES",
    "NOMBRE",
    "SEXO",
    "FECHA",
    "NACIMIENTO",
    "EMISION",
    "EMISIÓN",
    "CADUCIDAD",
    "FIRMA",
    "HUELLA",
    "DONACION",
    "DONACIÓN",
    "ORGANO",
    "ÓRGANO",
    "ELECTORAL",
    "RENIEC",
    "MASCULINO",
    "FEMENINO",
    "SOLTERO",
    "SOLTERA",
    "CASADO",
    "CASADA",
    "VIUDO",
    "VIUDA",
    "DIVORCIADO",
    "DIVORCIADA",
    "INSCRIPCION",
    "INSCRIPCIÓN",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",
    "DIRECCION",
    "DIRECCIÓN",
    "GRUPO",
    "VOTACION",
    "VOTACIÓN",
    "PERMANENTE",
    "DE",
    "DEL",
    "LA",
    "LAS",
    "LOS",
    "Y",
    "EL",
}


def _parece_nombre(texto: str) -> bool:
    texto = (texto or "").strip()
    if len(texto) < 3:
        return False
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}", texto):
        return False
    if re.search(r"\d{4}", texto):
        return False
    palabras = [p for p in re.split(r"\s+", texto) if p]
    if not palabras:
        return False
    return any(p.upper() not in ETIQUETAS_IGNORADAS for p in palabras)


def _limpiar_nombre(texto: str) -> str:
    texto = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ' \-]", " ", texto or "")
    texto = re.sub(r"\s+", " ", texto).strip(" -'")
    return texto.title()


def _extraer_bloque(lineas, etiqueta):
    for indice, linea in enumerate(lineas):
        if etiqueta in linea.upper():
            resto = re.sub(
                r"^.*?" + etiqueta, "", linea.upper(), count=1
            ).strip(" :.-")
            if _parece_nombre(resto):
                return _limpiar_nombre(resto)
            for siguiente in lineas[indice + 1 : indice + 4]:
                candidato = siguiente.strip(" :.-")
                if _parece_nombre(candidato):
                    return _limpiar_nombre(candidato)
    return ""


def parsear_texto_dni(texto: str) -> dict:
    texto = texto or ""
    lineas = [
        re.sub(r"\s+", " ", linea).strip()
        for linea in re.split(r"[\r\n|]+", texto)
        if linea.strip()
    ]
    datos = {
        "nombres": "",
        "apellidos": "",
        "dni": "",
        "fecha_nacimiento": "",
        "sexo": "",
    }

    coincidencia_dni = re.search(r"(?<!\d)(\d{8})(?!\d)", texto)
    if coincidencia_dni:
        datos["dni"] = coincidencia_dni.group(1)

    fechas = []
    for coincidencia in re.finditer(
        r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?!\d)", texto
    ):
        dia, mes, anio = map(int, coincidencia.groups())
        try:
            fechas.append(date(anio, mes, dia))
        except ValueError:
            continue
    if fechas:
        hoy_local = date.today()
        candidatas = [f for f in fechas if 3 <= hoy_local.year - f.year <= 100]
        elegida = min(candidatas) if candidatas else fechas[0]
        datos["fecha_nacimiento"] = elegida.isoformat()

    texto_mayus = texto.upper()
    if "FEMENINO" in texto_mayus:
        datos["sexo"] = "F"
    elif "MASCULINO" in texto_mayus:
        datos["sexo"] = "M"
    else:
        coincidencia_sexo = re.search(r"\bSEXO\b[^\n]{0,15}\b([MF])\b", texto_mayus)
        if coincidencia_sexo:
            datos["sexo"] = coincidencia_sexo.group(1)
        else:
            for linea in lineas:
                if linea.strip().upper() in ("M", "F"):
                    datos["sexo"] = linea.strip().upper()
                    break

    datos["apellidos"] = _extraer_bloque(lineas, "APELLIDOS")
    datos["nombres"] = _extraer_bloque(lineas, "NOMBRES")

    utiles = []
    for linea in lineas:
        limpia = linea.strip(" :.-")
        if not _parece_nombre(limpia):
            continue
        if all(p.upper() in ETIQUETAS_IGNORADAS for p in limpia.split()):
            continue
        nombre = _limpiar_nombre(limpia)
        if nombre and nombre not in utiles:
            utiles.append(nombre)

    if not datos["apellidos"] and utiles:
        hay_senales = bool(datos["dni"] or datos["fecha_nacimiento"] or datos["sexo"])
        if hay_senales or len(utiles) >= 2:
            datos["apellidos"] = utiles[0]
    if not datos["nombres"] and datos["apellidos"]:
        for candidato in utiles:
            if candidato != datos["apellidos"]:
                datos["nombres"] = candidato
                break

    detectados = [clave for clave, valor in datos.items() if valor]
    return {
        "datos": datos,
        "detectados": detectados,
        "texto": texto[:6000],
    }


@app.route("/api/escanear", methods=["POST"])
def api_escanear():
    archivo = request.files.get("imagen")
    if archivo is None or not archivo.filename:
        return jsonify({"ok": False, "mensaje": "No se recibió ninguna imagen."}), 400

    sufijo = os.path.splitext(archivo.filename)[1].lower()
    if sufijo not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"):
        sufijo = ".jpg"

    temporal = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    ruta_temporal = temporal.name
    temporal.close()
    try:
        archivo.save(ruta_temporal)
        texto, error = _ocr_imagen(ruta_temporal)
        if error:
            return jsonify({"ok": False, "mensaje": error}), 200
        if not (texto or "").strip():
            return jsonify(
                {
                    "ok": False,
                    "mensaje": (
                        "No se detectó texto en la foto. Acerca el DNI, evita reflejos "
                        "y vuelve a intentarlo, o completa los datos manualmente."
                    ),
                }
            ), 200

        resultado = parsear_texto_dni(texto)
        if not resultado["detectados"]:
            return jsonify(
                {
                    "ok": False,
                    "mensaje": (
                        "Se leyó la imagen, pero no se reconocieron datos del DNI. "
                        "Prueba con otra foto o completa el formulario manualmente."
                    ),
                    "texto": resultado["texto"],
                }
            ), 200

        return jsonify(
            {
                "ok": True,
                "datos": resultado["datos"],
                "detectados": resultado["detectados"],
                "texto": resultado["texto"],
                "mensaje": "Datos detectados. Revísalos antes de guardar.",
            }
        )
    finally:
        try:
            os.unlink(temporal.name)
        except OSError:
            pass


@app.route("/api/decodificar", methods=["POST"])
def api_decodificar():
    payload = request.get_json(silent=True) or {}
    texto = payload.get("texto", "")
    if not isinstance(texto, str) or not texto.strip():
        return jsonify({"ok": False, "mensaje": "No se recibió texto para analizar."}), 400
    resultado = parsear_texto_dni(texto)
    if not resultado["detectados"]:
        return jsonify(
            {
                "ok": False,
                "mensaje": "No se reconocieron datos en el código leído.",
                "texto": resultado["texto"],
            }
        )
    return jsonify(
        {
            "ok": True,
            "datos": resultado["datos"],
            "detectados": resultado["detectados"],
            "texto": resultado["texto"],
            "mensaje": "Código leído. Revisa los datos antes de guardar.",
        }
    )


# ---------------------------------------------------------------------------
# Configuración, respaldo y exportación
# ---------------------------------------------------------------------------


@app.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    if request.method == "POST":
        ie_nombre = _texto(request.form.get("ie_nombre"), 150)
        docente = _texto(request.form.get("docente"), 120)
        anio = _texto(request.form.get("anio"), 4)
        guardar_config("ie_nombre", ie_nombre or CONFIG_DEFAULTS["ie_nombre"])
        guardar_config("docente", docente or CONFIG_DEFAULTS["docente"])
        guardar_config("anio", anio or CONFIG_DEFAULTS["anio"])
        get_db().commit()
        flash("Configuración guardada.", "exito")
        return redirect(url_for("configuracion"))

    return render_template("configuracion.html", ruta_bd=app.config["DATABASE"])


@app.route("/respaldo")
def respaldo():
    nombre = f"respaldo-aula-cyt-{date.today().isoformat()}.db"
    return send_file(
        app.config["DATABASE"], as_attachment=True, download_name=nombre
    )


@app.route("/exportar/estudiantes.csv")
def exportar_estudiantes():
    db = get_db()
    filas = db.execute(
        """
        SELECT e.*,
               (SELECT GROUP_CONCAT(p.nombre || COALESCE(' (' || p.parentesco || ')', ''), '; ')
                  FROM padres p WHERE p.estudiante_id = e.id) AS apoderados,
               (SELECT GROUP_CONCAT(p.telefono, ' / ')
                  FROM padres p WHERE p.estudiante_id = e.id AND p.telefono <> '') AS telefonos
        FROM estudiantes e
        ORDER BY e.grado, e.seccion, e.apellidos COLLATE NOCASE, e.nombres COLLATE NOCASE
        """
    ).fetchall()

    salida = io.StringIO()
    salida.write("\ufeff")
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(
        [
            "Apellidos",
            "Nombres",
            "DNI",
            "Grado",
            "Sección",
            "Sexo",
            "Fecha de nacimiento",
            "Dirección",
            "Teléfono",
            "Apoderados",
            "Teléfonos de apoderados",
        ]
    )
    for fila in filas:
        escritor.writerow(
            [
                fila["apellidos"],
                fila["nombres"],
                fila["dni"],
                fila["grado"],
                fila["seccion"],
                fila["sexo"],
                fila["fecha_nacimiento"],
                fila["direccion"],
                fila["telefono"],
                fila["apoderados"],
                fila["telefonos"],
            ]
        )

    return Response(
        salida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=estudiantes-aula-cyt.csv"
        },
    )


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


@app.errorhandler(404)
def no_encontrado(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "mensaje": "Recurso no encontrado."}), 404
    return (
        render_template(
            "error.html",
            codigo=404,
            titulo="Página no encontrada",
            mensaje="La página o el registro que buscas no existe.",
        ),
        404,
    )


@app.errorhandler(413)
def archivo_muy_grande(_error):
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "ok": False,
                    "mensaje": "La imagen es demasiado grande (máximo 15 MB).",
                }
            ),
            413,
        )
    flash("El archivo supera el tamaño máximo permitido (15 MB).", "error")
    return redirect(url_for("escaner"))


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    try:
        puerto = int(os.environ.get("PORT", "5000"))
    except ValueError:
        puerto = 5000
    depurar = os.environ.get("FLASK_DEBUG", "0") == "1"

    print("\n" + "=" * 62)
    print("  Aula CyT - Registro docente de Ciencia y Tecnología")
    print("  Creado por Walter López Culqui")
    print("=" * 62)
    print(f"  Abre en tu navegador: http://127.0.0.1:{puerto}")
    if host == "0.0.0.0":
        try:
            sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sonda.connect(("8.8.8.8", 80))
            ip_local = sonda.getsockname()[0]
            sonda.close()
        except OSError:
            ip_local = None
        if ip_local:
            print(f"  Desde tu celular o tablet: http://{ip_local}:{puerto}")
        print("  (Asegúrate de permitir Flask en el Firewall de Windows)")
    print("  Para detener el servidor: Ctrl + C")
    print("=" * 62 + "\n")
    app.run(host=host, port=puerto, debug=depurar)
