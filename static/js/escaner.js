/* ==========================================================================
   Aula CyT — Escáner de DNI
   Cámara + envío al servidor para lectura OCR y llenado del formulario.
   ========================================================================== */

(function () {
  "use strict";

  const $ = function (selector) {
    return document.querySelector(selector);
  };

  const camara = $("#camara");
  const video = $("#video");
  const botonActivar = $("#btn-activar-camara");
  const botonCapturar = $("#btn-capturar");
  const botonDetener = $("#btn-detener");
  const botonCodigo = $("#btn-codigo-barras");
  const entradaArchivo = $("#archivo-foto");
  const estado = $("#estado-lectura");
  const panelResultado = $("#panel-resultado");
  const textoOcr = $("#texto-ocr");
  const detalleOcr = $("#detalle-ocr");
  const botonUsar = $("#btn-usar-datos");
  const botonLimpiar = $("#btn-limpiar-resultado");

  const campos = {
    nombres: $("#res-nombres"),
    apellidos: $("#res-apellidos"),
    dni: $("#res-dni"),
    fecha_nacimiento: $("#res-fecha"),
    sexo: $("#res-sexo"),
  };

  let stream = null;
  let ocupado = false;
  let detector = null;
  let bucleCodigo = null;
  let temporizadorCodigo = null;

  function mostrarEstado(mensaje, tipo) {
    if (!estado) return;
    estado.textContent = mensaje;
    estado.className = "estado-lectura visible " + (tipo || "info");
  }

  function ocultarEstado() {
    if (!estado) return;
    estado.className = "estado-lectura";
    estado.textContent = "";
  }

  function actualizarEnlace() {
    if (!botonUsar) return;
    const parametros = new URLSearchParams();
    Object.keys(campos).forEach(function (clave) {
      const valor = campos[clave] ? campos[clave].value.trim() : "";
      if (valor) parametros.set(clave, valor);
    });
    botonUsar.href = "/estudiantes/nuevo?" + parametros.toString();
  }

  function mostrarDatos(datos, detectados, texto) {
    Object.keys(campos).forEach(function (clave) {
      if (!campos[clave]) return;
      campos[clave].value = datos[clave] || "";
    });
    if (textoOcr) textoOcr.textContent = texto || "";
    if (detalleOcr) detalleOcr.open = false;
    if (panelResultado) {
      panelResultado.classList.remove("oculto");
      panelResultado.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    const cantidad = (detectados || []).length;
    mostrarEstado(
      "Se detectaron " +
        cantidad +
        " dato(s). Revisa y corrige si es necesario antes de registrar al estudiante.",
      "exito"
    );
    actualizarEnlace();
  }

  function limpiarResultado() {
    Object.keys(campos).forEach(function (clave) {
      if (campos[clave]) campos[clave].value = "";
    });
    if (textoOcr) textoOcr.textContent = "";
    if (panelResultado) panelResultado.classList.add("oculto");
    ocultarEstado();
    actualizarEnlace();
  }

  async function enviarImagen(archivo) {
    if (!archivo || ocupado) return;
    ocupado = true;
    mostrarEstado("Leyendo la imagen… esto puede tardar unos segundos.", "info");
    if (botonCapturar) botonCapturar.disabled = true;
    if (entradaArchivo) entradaArchivo.disabled = true;

    const datos = new FormData();
    datos.append("imagen", archivo, archivo.name || "dni.jpg");

    try {
      const respuesta = await fetch("/api/escanear", {
        method: "POST",
        body: datos,
      });
      const resultado = await respuesta.json().catch(function () {
        return {
          ok: false,
          mensaje: "El servidor devolvió una respuesta inesperada.",
        };
      });

      if (resultado.ok) {
        mostrarDatos(
          resultado.datos || {},
          resultado.detectados || [],
          resultado.texto || ""
        );
      } else {
        mostrarEstado(
          resultado.mensaje || "No se pudo leer la imagen.",
          "error"
        );
        if (resultado.texto && textoOcr) {
          textoOcr.textContent = resultado.texto;
          if (detalleOcr) detalleOcr.open = true;
        }
      }
    } catch (error) {
      mostrarEstado(
        "No se pudo conectar con el servidor. Revisa que la aplicación esté encendida.",
        "error"
      );
    } finally {
      ocupado = false;
      if (botonCapturar) botonCapturar.disabled = !stream;
      if (entradaArchivo) entradaArchivo.disabled = false;
    }
  }

  function detenerCamara() {
    if (bucleCodigo) {
      window.clearInterval(bucleCodigo);
      bucleCodigo = null;
    }
    if (temporizadorCodigo) {
      window.clearTimeout(temporizadorCodigo);
      temporizadorCodigo = null;
    }
    if (stream) {
      stream.getTracks().forEach(function (pista) {
        pista.stop();
      });
      stream = null;
    }
    if (video) {
      video.srcObject = null;
      video.style.display = "";
    }
    if (camara) camara.classList.remove("activa");
    if (botonActivar) botonActivar.disabled = false;
    if (botonCapturar) botonCapturar.disabled = true;
    if (botonDetener) botonDetener.classList.add("oculto");
  }

  async function iniciarCamara() {
    if (stream) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      mostrarEstado(
        "Este navegador no permite abrir la cámara. Usa el botón «Tomar o subir foto».",
        "error"
      );
      return;
    }
    if (!window.isSecureContext) {
      mostrarEstado(
        "La cámara en vivo requiere abrir la app en localhost o con HTTPS. " +
          "En el celular, usa «Tomar o subir foto»: la cámara del teléfono sí funciona.",
        "error"
      );
      return;
    }

    mostrarEstado("Solicitando permiso para usar la cámara…", "info");
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      if (video) {
        video.srcObject = stream;
        await video.play().catch(function () {});
      }
      if (camara) camara.classList.add("activa");
      if (botonActivar) botonActivar.disabled = true;
      if (botonCapturar) botonCapturar.disabled = false;
      if (botonDetener) botonDetener.classList.remove("oculto");
      mostrarEstado(
        "Cámara lista. Coloca el DNI dentro del recuadro, con buena luz y sin reflejos.",
        "info"
      );
    } catch (error) {
      detenerCamara();
      let mensaje =
        "No se pudo abrir la cámara. Revisa los permisos del navegador.";
      if (error && error.name === "NotAllowedError") {
        mensaje =
          "Permiso de cámara denegado. Habilítalo en el navegador o usa «Tomar o subir foto».";
      } else if (error && error.name === "NotFoundError") {
        mensaje =
          "No se encontró una cámara disponible. Usa «Tomar o subir foto».";
      } else if (error && error.name === "NotReadableError") {
        mensaje =
          "La cámara está siendo usada por otra aplicación. Ciérrala e inténtalo de nuevo.";
      }
      mostrarEstado(mensaje, "error");
    }
  }

  function capturar() {
    if (!video || !stream) return;
    const ancho = video.videoWidth || 1280;
    const alto = video.videoHeight || 720;
    const lienzo = document.createElement("canvas");
    lienzo.width = ancho;
    lienzo.height = alto;
    const contexto = lienzo.getContext("2d");
    contexto.drawImage(video, 0, 0, ancho, alto);
    lienzo.toBlob(
      function (blob) {
        if (blob) {
          const archivo = new File([blob], "dni-camara.jpg", {
            type: "image/jpeg",
          });
          enviarImagen(archivo);
        }
      },
      "image/jpeg",
      0.92
    );
  }

  async function iniciarCodigoBarras() {
    if (!("BarcodeDetector" in window)) {
      mostrarEstado(
        "Tu navegador no permite leer códigos de barras. Usa la foto con OCR o completa los datos manualmente.",
        "error"
      );
      return;
    }
    if (!stream) {
      await iniciarCamara();
    }
    if (!stream) return;

    try {
      detector = new window.BarcodeDetector({
        formats: ["pdf417", "code_128", "qr_code"],
      });
    } catch (error) {
      mostrarEstado(
        "Este dispositivo no admite la lectura de códigos PDF417. Usa la foto o el formulario manual.",
        "error"
      );
      return;
    }

    if (bucleCodigo) window.clearInterval(bucleCodigo);
    mostrarEstado(
      "Acerca el código de barras del reverso del DNI a la cámara. Buscando…",
      "info"
    );

    bucleCodigo = window.setInterval(async function () {
      if (!video || !detector || ocupado) return;
      try {
        const codigos = await detector.detect(video);
        if (codigos && codigos.length > 0 && codigos[0].rawValue) {
          window.clearInterval(bucleCodigo);
          bucleCodigo = null;
          if (temporizadorCodigo) window.clearTimeout(temporizadorCodigo);
          await enviarTextoCodigo(codigos[0].rawValue);
        }
      } catch (error) {
        // La detección falla en algunos fotogramas; se ignora y se reintenta.
      }
    }, 450);

    temporizadorCodigo = window.setTimeout(function () {
      if (bucleCodigo) {
        window.clearInterval(bucleCodigo);
        bucleCodigo = null;
      }
      mostrarEstado(
        "No se detectó el código en 20 segundos. Acércalo más, evita reflejos o usa la foto del DNI.",
        "error"
      );
    }, 20000);
  }

  async function enviarTextoCodigo(texto) {
    mostrarEstado("Código detectado. Interpretando datos…", "info");
    try {
      const respuesta = await fetch("/api/decodificar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: texto }),
      });
      const resultado = await respuesta.json();
      if (resultado.ok) {
        mostrarDatos(
          resultado.datos || {},
          resultado.detectados || [],
          resultado.texto || ""
        );
        detenerCamara();
      } else {
        mostrarEstado(
          resultado.mensaje ||
            "El código se leyó, pero no se reconocieron los datos. Completa el formulario manualmente.",
          "error"
        );
      }
    } catch (error) {
      mostrarEstado("No se pudo interpretar el código leído.", "error");
    }
  }

  // ---------------------------------------------------------------------
  // Eventos
  // ---------------------------------------------------------------------
  if (botonActivar) botonActivar.addEventListener("click", iniciarCamara);
  if (botonCapturar) botonCapturar.addEventListener("click", capturar);
  if (botonDetener) botonDetener.addEventListener("click", detenerCamara);
  if (botonCodigo) botonCodigo.addEventListener("click", iniciarCodigoBarras);
  if (botonLimpiar) botonLimpiar.addEventListener("click", limpiarResultado);

  if (entradaArchivo) {
    entradaArchivo.addEventListener("change", function () {
      if (entradaArchivo.files && entradaArchivo.files[0]) {
        enviarImagen(entradaArchivo.files[0]);
        entradaArchivo.value = "";
      }
    });
  }

  Object.keys(campos).forEach(function (clave) {
    if (campos[clave]) {
      campos[clave].addEventListener("input", actualizarEnlace);
      campos[clave].addEventListener("change", actualizarEnlace);
    }
  });

  if (botonCodigo && !("BarcodeDetector" in window)) {
    botonCodigo.classList.add("oculto");
  }

  if (!window.isSecureContext) {
    const avisoCamara = $("#aviso-camara");
    if (avisoCamara) avisoCamara.classList.remove("oculto");
  }

  window.addEventListener("pagehide", detenerCamara);
})();
