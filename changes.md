# Cambios realizados

- Hice que los adjuntos se envíen como contexto real al chat, no solo como nombres de archivo.
- Añadí lectura local en el frontend para archivos de texto e imágenes.
- Hice que el backend procese adjuntos y los mezcle en el prompt del modelo.
- Sincronizé la copia `cerebro/` para que use el mismo flujo de adjuntos que la app principal.
- Añadí la ruta de subida de archivos en la copia `cerebro/` y el handler de procesamiento correspondiente.
- Ajusté los tests para cubrir `intent_query` y el contexto de adjuntos.
