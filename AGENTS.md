# REGLAS DEL AGENTE

## Regla 1: leer memoria primero

Antes de analizar, modificar o documentar cualquier parte del proyecto, el agente debe leer `memoria.mc`.

## Regla 2: no trabajar sin contexto

El agente no debe asumir el estado del proyecto a partir de memoria interna o conversaciones pasadas si no ha revisado `memoria.mc` y, cuando haga falta, los archivos reales del repositorio.

## Regla 3: actualizar memoria despues de cambios

Despues de cualquier cambio en codigo, documentacion, arquitectura, scripts, instalacion o comportamiento visible, el agente debe actualizar `memoria.mc`.

## Regla 4: preservar historial

El agente no debe borrar historial relevante de `memoria.mc`. Debe acumular cambios, problemas y soluciones para mantener continuidad entre sesiones.

## Regla 5: mantener consistencia

El agente debe mantener consistencia entre:

- `memoria.mc`
- codigo fuente
- `README.md`
- `requirements.txt`
- scripts de instalacion y ejecucion

## Regla 6: no introducir dependencias inventadas

Si se documentan dependencias, deben salir de `requirements.txt` o del codigo real. No se deben inventar librerias ni capacidades no implementadas.

## Regla 7: documentar con criterio

Los cambios deben dejar el proyecto mas entendible. Se deben preferir docstrings y comentarios utiles, evitando ruido o comentarios triviales.

## Regla 8: no romper compatibilidad sin registrarlo

Si un cambio afecta compatibilidad, instalacion o comportamiento de usuario, el agente debe reflejarlo en:

- `memoria.mc`
- `README.md` si aplica
- `CHANGELOG.md` si corresponde

## Regla 9: validar despues de editar

Siempre que sea posible, el agente debe verificar el proyecto despues de editarlo, por ejemplo con compilacion, importacion o pruebas disponibles.

## Regla 10: este archivo gobierna futuras sesiones

`AGENTS.md` debe considerarse parte del sistema operativo del proyecto para agentes de IA. Su lectura es obligatoria antes de continuar cualquier trabajo.
