# Aula CyT · Registro docente de Ciencia y Tecnología

Aplicación web local hecha con **Flask** para docentes de secundaria del área de
**Ciencia y Tecnología (1.° a 5.° grado)**. Guarda todos los registros en una base
de datos SQLite dentro de tu propia computadora.

**Creado por: Walter López Culqui**

---

## ¿Qué incluye?

- Registro de estudiantes: nombres, apellidos, DNI, grado, sección, sexo, fecha de
  nacimiento, dirección y teléfono.
- Registro de padres o apoderados: nombre, parentesco, teléfono y DNI.
- Escáner de DNI con cámara o foto: lee el documento y propone los datos para
  completar el formulario (requiere Tesseract OCR, ver más abajo).
- Calificaciones por competencia del CNEB y por bimestre, con escala **AD / A / B / C**.
- Control de asistencia diaria: presente, tarde, ausente o justificado, con
  observaciones y resumen del día.
- Anexos de comportamiento: méritos, observaciones y llamados de atención.
- Registro de faltas: inasistencias injustificadas, tardanzas e incidencias
  disciplinarias, con medida correctiva y aviso a la familia.
- Anexo imprimible por estudiante con comportamiento, faltas, resumen de asistencia
  y espacios para firmas.
- Exportación de estudiantes a CSV y descarga de respaldo de la base de datos.
- Interfaz adaptable a celular (Android / iOS), tablet y computadora.
- Configuración del nombre de la I.E., docente y año escolar.

---

## Requisitos

- Windows, macOS o Linux.
- **Python 3.10 o superior** (probado con Python 3.15).
- Un navegador moderno: Chrome, Edge, Firefox o Safari.
- Opcional para el escáner automático: **Tesseract OCR** con el idioma español.

---

## Instalación rápida en Windows

1. Descomprime o copia la carpeta `AulaCienciaTecnologia` en tu computadora.
2. Haz doble clic en **`iniciar.bat`**.
3. La primera vez se crea un entorno virtual y se instalan las dependencias.
4. Cuando termine, se abrirá el navegador en:

   ```
   http://127.0.0.1:5000
   ```

Para detener el servidor, presiona **Ctrl + C** en la ventana negra.

> Si Windows muestra un aviso de Firewall, permite el acceso solo en redes privadas
> si quieres usar la app desde tu celular.

### Instalación manual (cualquier sistema)

```bash
cd AulaCienciaTecnologia
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador.

---

## Usar la app desde el celular o tablet

1. Conecta la computadora y el celular a la **misma red Wi-Fi**.
2. Ejecuta **`iniciar_red.bat`** (o define `HOST=0.0.0.0` antes de `python app.py`).
3. En la ventana del servidor aparecerá una dirección similar a:

   ```
   Desde tu celular o tablet: http://192.168.1.25:5000
   ```

4. Escribe esa dirección en el navegador del celular.
5. Si no carga, revisa el Firewall de Windows y permite Python/Flask en redes privadas.

> **Cámara en el celular:** la vista en vivo de la cámara solo funciona en
> `localhost` o con HTTPS. Al entrar desde la IP de la red, usa el botón
> **«Tomar o subir foto»**, que abre la cámara del teléfono y sí funciona.
> También puedes escribir los datos manualmente.

---

## Escáner de DNI (opcional)

La app intenta leer el DNI con OCR y extraer nombres, apellidos, número, fecha de
nacimiento y sexo. **No consulta RENIEC**: siempre revisa y corrige los datos antes
de guardar.

### Instalar Tesseract OCR en Windows

1. Descarga el instalador desde la página oficial de la comunidad:
   <https://github.com/UB-Mannheim/tesseract/wiki>
2. Durante la instalación, marca el idioma **Spanish** (o instala `spa.traineddata`).
3. Deja la ruta por defecto: `C:\Program Files\Tesseract-OCR`.
4. Reinicia la app. La aplicación detecta Tesseract automáticamente.

Si lo instalaste en otra ruta, crea la variable de entorno `TESSERACT_CMD` con la
ruta completa del ejecutable, por ejemplo:

```bat
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
python app.py
```

### Consejos para una buena lectura

- Buena luz, sin reflejos ni sombras.
- DNI completo y enfocado, sobre una superficie plana.
- Toma la foto de frente, sin inclinación.
- Revisa siempre los campos detectados antes de registrar.

Si Tesseract no está instalado, el escáner muestra un aviso y permite completar los
datos manualmente. Todas las demás funciones siguen funcionando con normalidad.

---

## Cómo se usa cada sección

| Sección | Para qué sirve |
|---|---|
| **Inicio** | Resumen de estudiantes, asistencia del día, convivencia y accesos rápidos. |
| **Estudiantes** | Alta, edición, búsqueda, exportación CSV y ficha completa. |
| **Escáner DNI** | Foto o cámara para autocompletar los datos personales. |
| **Calificaciones** | Notas por competencia y bimestre para un grado y sección. |
| **Asistencia** | Marcado diario con resumen y observaciones. |
| **Comportamiento** | Méritos, observaciones y llamados de atención. |
| **Faltas** | Inasistencias, tardanzas y faltas disciplinarias con medidas. |
| **Anexo** | Documento imprimible por estudiante, con firmas. |
| **Configuración** | Nombre de la I.E., docente, año escolar y respaldo. |

### Flujo recomendado

1. Configura el nombre de tu I.E. y el año escolar.
2. Registra a los estudiantes (puedes usar el escáner de DNI).
3. Agrega al menos un apoderado con teléfono.
4. Toma asistencia y registra calificaciones por bimestre.
5. Anota comportamientos y faltas cuando ocurran.
6. Imprime el anexo de comportamiento desde la ficha del estudiante.
7. Descarga un respaldo de la base de datos periódicamente.

---

## Dónde se guardan los datos

La base de datos se crea automáticamente en:

```
AulaCienciaTecnologia\instance\registro.db
```

- No borres ni muevas esa carpeta mientras la app esté en uso.
- Para hacer un respaldo, usa **Configuración → Descargar respaldo** o copia el
  archivo `registro.db` con la app detenida.
- Para restaurar, reemplaza `instance\registro.db` por tu copia de respaldo.
- Si quieres empezar de cero, detén la app, renombra o elimina `registro.db` y
  vuelve a iniciarla. Se creará una base vacía.

> **Importante:** la app no tiene inicio de sesión. Está pensada para uso local en
> tu computadora. Si la vas a publicar en internet o compartir en una red, protege
> el acceso con autenticación y HTTPS, y respeta las normas de protección de datos
> personales de tu institución.

---

## Estructura del proyecto

```
AulaCienciaTecnologia/
├── app.py                  # Lógica Flask, rutas y base de datos
├── schema.sql              # Estructura de las tablas SQLite
├── requirements.txt        # Dependencias de Python
├── iniciar.bat             # Inicio rápido en Windows (solo esta PC)
├── iniciar_red.bat         # Inicio para acceder desde celular/tablet
├── README.md               # Este archivo
├── instance/
│   └── registro.db         # Base de datos (se crea sola)
├── static/
│   ├── css/estilos.css
│   ├── js/app.js
│   ├── js/escaner.js
│   └── img/favicon.svg
└── templates/
    ├── base.html
    ├── inicio.html
    ├── estudiantes_lista.html
    ├── estudiante_form.html
    ├── estudiante_detalle.html
    ├── escaner.html
    ├── calificaciones.html
    ├── asistencia.html
    ├── comportamiento.html
    ├── faltas.html
    ├── anexo.html
    ├── configuracion.html
    └── error.html
```

---

## Solución de problemas

**`python` no se reconoce como comando**
Instala Python desde <https://www.python.org/downloads/> y marca la opción
«Add Python to PATH». En Windows también puedes usar `py` en lugar de `python`.

**El puerto 5000 está ocupado**
Ejecuta en otra terminal:

```bat
set PORT=5001
python app.py
```

Y abre `http://127.0.0.1:5001`.

**No se puede acceder desde el celular**
Verifica que ambos dispositivos estén en la misma Wi-Fi, que usaste
`iniciar_red.bat` y que el Firewall permite Python en redes privadas.

**El escáner no completa los datos**
Comprueba que Tesseract OCR esté instalado con el idioma español, que la foto tenga
buena calidad y que la app se haya reiniciado. También puedes escribir los datos a
mano en el panel derecho del escáner.

**Quiero cambiar la clave secreta de Flask**
Define la variable de entorno `SECRET_KEY` antes de iniciar la app:

```bat
set SECRET_KEY=una-clave-larga-y-privada
python app.py
```

---

## Créditos

**Aula CyT** fue creado por **Walter López Culqui** para apoyar el trabajo diario
del docente de Ciencia y Tecnología en secundaria.

Hecho con Flask, SQLite, HTML, CSS y JavaScript. Sin dependencias de servicios en
la nube: tus datos se quedan en tu computadora.
