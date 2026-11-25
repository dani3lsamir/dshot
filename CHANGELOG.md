# Changelog

Notas de cada versión publicada. El workflow de release toma la sección del tag
correspondiente (por ejemplo `## v0.9.0`) y la usa como cuerpo del release en GitHub,
añadiéndole las instrucciones de descarga.

## v0.9.0

**Captura multi-monitor (Windows)**
- Antes solo se capturaba el monitor principal; ahora se abre una ventana de selección en **cada monitor** y puedes arrastrar la región en cualquiera de ellos. La selección se mantiene dentro de un monitor.

**Selección y anotación (Windows y Linux)**
- **8 tiradores** para redimensionar la región.
- Insignia **W × H** en vivo con el tamaño en píxeles.
- **Clic derecho** para limpiar la región (o cerrar la captura si no hay).
- Cursor de cruz y previsualización de la **punta de flecha en vivo** (lo que ves es lo que se exporta).
- En Windows: aviso en la bandeja al copiar texto por OCR y botón Cerrar en rojo al pasar el ratón.

**OCR (Windows)**
- Las capturas pequeñas se **amplían** antes del reconocimiento (mucha mejor precisión en texto de interfaz), un motor por idioma y preparación fuera del hilo de la interfaz.

### Correcciones
- **Windows:** cambiar el color o deshacer mientras se escribe texto ya funciona; el diálogo Guardar ya no queda detrás de otro monitor; selección recortada al monitor; escritura al portapapeles con reintentos; hook de Print Screen más robusto (auto-repeat y Alt+PrtSc).
- **Linux:** el OCR se cancela al cerrar la captura y tiene timeout; el socket de instancia única ya no tiene fugas; el interruptor de "iniciar al login" se revierte si falla; el archivo temporal del portal siempre se borra.

### Rendimiento
- **Linux:** repintado solo de la zona modificada y PNG más ligeros (RGB32).

## v0.8.3 y anteriores

Consulta las páginas de cada release: https://github.com/dani3lsamir/dshot/releases
