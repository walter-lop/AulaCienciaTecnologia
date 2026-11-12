/* ==========================================================================
   Aula CyT — Interacciones generales
   ========================================================================== */

(function () {
  "use strict";

  const documento = document;

  // ---------------------------------------------------------------------
  // Menú móvil
  // ---------------------------------------------------------------------
  const cabecera = documento.getElementById("cabecera");
  const botonMenu = documento.querySelector("[data-nav-toggle]");

  function cerrarMenu() {
    if (!cabecera) return;
    cabecera.classList.remove("nav-abierta");
    if (botonMenu) botonMenu.setAttribute("aria-expanded", "false");
  }

  if (botonMenu && cabecera) {
    botonMenu.addEventListener("click", function () {
      const abierto = cabecera.classList.toggle("nav-abierta");
      botonMenu.setAttribute("aria-expanded", abierto ? "true" : "false");
    });

    documento.addEventListener("click", function (evento) {
      if (!cabecera.classList.contains("nav-abierta")) return;
      if (!cabecera.contains(evento.target)) cerrarMenu();
    });

    documento.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") cerrarMenu();
    });

    cabecera.querySelectorAll(".nav a").forEach(function (enlace) {
      enlace.addEventListener("click", cerrarMenu);
    });
  }

  // ---------------------------------------------------------------------
  // Mensajes flash
  // ---------------------------------------------------------------------
  documento.querySelectorAll("[data-cerrar-flash]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      const flash = boton.closest(".flash");
      if (flash) flash.remove();
    });
  });

  documento.querySelectorAll(".flash").forEach(function (flash) {
    window.setTimeout(function () {
      flash.style.transition = "opacity 300ms ease, transform 300ms ease";
      flash.style.opacity = "0";
      flash.style.transform = "translateY(-4px)";
      window.setTimeout(function () {
        flash.remove();
      }, 320);
    }, 9000);
  });

  // ---------------------------------------------------------------------
  // Filtros que se envían solos
  // ---------------------------------------------------------------------
  documento.querySelectorAll("[data-auto-submit]").forEach(function (campo) {
    campo.addEventListener("change", function () {
      const formulario = campo.closest("form");
      if (formulario) formulario.submit();
    });
  });

  // ---------------------------------------------------------------------
  // Confirmaciones
  // ---------------------------------------------------------------------
  documento.querySelectorAll("form[data-confirmar]").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
      const mensaje =
        formulario.getAttribute("data-confirmar") ||
        "¿Seguro que deseas continuar?";
      if (!window.confirm(mensaje)) {
        evento.preventDefault();
        return;
      }
      const boton = formulario.querySelector('button[type="submit"]');
      if (boton) {
        boton.disabled = true;
        boton.dataset.textoOriginal = boton.textContent;
        boton.textContent = "Procesando…";
      }
    });
  });

  // ---------------------------------------------------------------------
  // DNI: solo números (delegado para filas nuevas)
  // ---------------------------------------------------------------------
  documento.addEventListener("input", function (evento) {
    const campo = evento.target.closest("[data-dni]");
    if (!campo) return;
    campo.value = campo.value.replace(/\D/g, "").slice(0, 8);
  });

  // ---------------------------------------------------------------------
  // Padres / apoderados dinámicos
  // ---------------------------------------------------------------------
  const contenedorPadres = documento.getElementById("padres");
  const plantillaPadre = documento.getElementById("plantilla-padre");
  const botonAgregarPadre = documento.querySelector("[data-agregar-padre]");

  function agregarPadre() {
    if (!contenedorPadres || !plantillaPadre) return;
    const fragmento = plantillaPadre.content.cloneNode(true);
    contenedorPadres.appendChild(fragmento);
    const filas = contenedorPadres.querySelectorAll(".padre-fila");
    const ultima = filas[filas.length - 1];
    if (ultima) {
      const primerCampo = ultima.querySelector("input");
      if (primerCampo) primerCampo.focus();
    }
  }

  if (botonAgregarPadre) {
    botonAgregarPadre.addEventListener("click", agregarPadre);
  }

  if (contenedorPadres) {
    contenedorPadres.addEventListener("click", function (evento) {
      const boton = evento.target.closest("[data-quitar-padre]");
      if (!boton) return;
      const fila = boton.closest(".padre-fila");
      if (fila) fila.remove();
    });
  }

  // ---------------------------------------------------------------------
  // Asistencia: botones rápidos y conteo en vivo
  // ---------------------------------------------------------------------
  documento.querySelectorAll("[data-marcar-todos]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      const estado = boton.getAttribute("data-marcar-todos");
      documento
        .querySelectorAll('.asistencia-item input[type="radio"][value="' + estado + '"]')
        .forEach(function (radio) {
          radio.checked = true;
          radio.dispatchEvent(new Event("change", { bubbles: true }));
        });
    });
  });

  const resumen = documento.getElementById("resumen-asistencia");
  if (resumen) {
    const actualizarResumen = function () {
      const conteos = {
        presente: 0,
        tarde: 0,
        ausente: 0,
        justificado: 0,
      };
      documento
        .querySelectorAll(".asistencia-item input[type=radio]:checked")
        .forEach(function (radio) {
          if (conteos[radio.value] !== undefined) conteos[radio.value] += 1;
        });
      Object.keys(conteos).forEach(function (clave) {
        const nodo = resumen.querySelector('[data-cuenta="' + clave + '"]');
        if (nodo) nodo.textContent = conteos[clave];
      });
    };
    documento
      .querySelectorAll(".asistencia-item input[type=radio]")
      .forEach(function (radio) {
        radio.addEventListener("change", actualizarResumen);
      });
    actualizarResumen();
  }

  // ---------------------------------------------------------------------
  // Calificaciones: color del selector
  // ---------------------------------------------------------------------
  documento.querySelectorAll(".nota-select").forEach(function (select) {
    const actualizarColor = function () {
      select.classList.remove("nota-ad", "nota-a", "nota-b", "nota-c");
      const valor = select.value.toLowerCase();
      if (valor) select.classList.add("nota-" + valor);
    };
    select.addEventListener("change", actualizarColor);
    actualizarColor();
  });

  // ---------------------------------------------------------------------
  // Imprimir
  // ---------------------------------------------------------------------
  documento.querySelectorAll("[data-imprimir]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      window.print();
    });
  });
})();
