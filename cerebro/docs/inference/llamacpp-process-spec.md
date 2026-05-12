Actúa como Ingeniero de Machine Learning Senior. Implementa una capa de inferencia local optimizada para hardware de 8GB de RAM siguiendo estos requisitos:

Gestión Dinámica de Procesos: Crea un script de orquestación en Python/Bash que inicie llama-server solo cuando sea necesario y lo cierre automáticamente tras 5 minutos de inactividad para liberar la RAM unificada.

Configuración Quirúrgica de llama.cpp: Configura el servidor para usar el modelo Qwen3-1.7B-Instruct-IQ4_XS.gguf (o la versión 4B si el usuario lo prefiere, pero con estas restricciones) con:

-ngl 99 y -fa (Flash Attention) habilitados.

--ctk q4_0 y --ctv q4_0 (Cuantización de 4 bits para el KV Cache).

Un límite estricto de contexto -c 2048 para evitar el desbordamiento de memoria.

--mlock para prevenir que macOS envíe el proceso al Swap.

Capa de 'Resumen de Memoria' (Memory Distillation): Implementa una lógica en el backend que, antes de enviar el historial al modelo, verifique si supera los 1500 tokens. Si es así, debe pedirle al modelo un resumen de la charla, limpiar el historial y colocar el resumen en el System Prompt.

Pre-procesado de Prompts: Añade una función de limpieza que elimine stop-words y espacios redundantes de las entradas del usuario antes de la inferencia para ahorrar espacio de tokens (Token Savings).

Monitoreo de Seguridad: El programa debe consultar vm_stat antes de cada inferencia. Si la memoria libre es inferior a 200MB, debe arrojar una advertencia amigable en lugar de intentar procesar y congelar el sistema