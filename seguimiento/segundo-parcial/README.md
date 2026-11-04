# Seguimiento operativo del segundo parcial

**Punto de entrada para cualquier chat o agente nuevo.** Decisión del propietario del 03/11/2026: una sola persona dirige el proyecto restante y usa un agente externo para implementar código. Primero se cierra la **entrega 1 de 14 CU**; después se implementa la **entrega 2 de 13 CU**. En cada entrega se trabaja primero backend y Angular; **Flutter se implementa al final de esa entrega**, sólo para los CU que le asigna el contrato. CU06/CU07 mantienen caja offline también en Flutter. Codex revisa y actualiza este seguimiento cuando el propietario informa una entrega del agente.

La carpeta vive en el repositorio `backend` para que su historial pueda registrarse en Git. El código se reparte entre los repositorios hermanos `backend`, `frontend-web` y `app-movil`, cada uno con sus ramas y commits. Este seguimiento describe el trabajo; los contratos de cada repositorio conservan las reglas de negocio y API.

## Lectura obligatoria al reanudar

1. [Alcance y orden](01-alcance-y-orden.md): 14 + 13 CU, lotes y dependencias.
2. [Estado por CU](02-estado-cu.md): evidencia actual, bloqueos, rama y commit cuando existan.
3. [Ramas, revisión y commits](03-ramas-y-commits.md): cómo preservar cambios locales y registrar cada lote aceptado.
4. [Bitácora](04-bitacora.md): hechos fechados y decisiones posteriores.
5. [Guía para otro chat](05-reanudacion.md): comprobaciones antes de continuar.
6. [Canales y cierre móvil](06-canales-y-cierre-movil.md): qué CU requieren Flutter y cuándo se abordan.
7. [Prompt inicial para agente externo](prompts/E1-B1-identidad.md), si el siguiente trabajo es el lote E1-B1.
8. [Resolución técnica final de bloqueos E1](13-resolucion-final-bloqueos-e1.md): migraciones 0012–0013, conciliación supervisada, Kardex y estado de pruebas.
9. [Entrega técnica E1 y plan E2](14-entrega-e1-y-plan-e2.md): commits reales, verificación final, límites manuales y orden de los 13 CU restantes. Es el estado vigente cuando difiere de auditorías previas.
10. [Ejecución E2 con subagentes](15-ejecucion-e2.md) y [prompt integral listo para el agente](prompts/E2-implementacion-integral-subagentes.md): alcance, ramas, propietarios de archivos, puertas técnicas y reporte.

## Fuentes y prioridad

- Decisión más reciente del propietario en este chat: **14 CU en la primera entrega y 13 en la segunda**, con él como responsable del proyecto restante. Prevalece sobre el reparto personal A/B de prompts antiguos.
- Contrato operativo: `contratos/segundo-parcial/version.json` de los tres repositorios, actualmente **0.3.2**, protocolo **0.4.0**, 27 CU. Leer ficha `casos/CUxx.md`, `api-casos.json`, `reglas-aprobadas.md`, `integracion.md`, `estados-y-transiciones.md` y contrato por canal antes de implementar.
- [Auditoría inicial](../../../docu_general/2doParcial/03-planes-de-trabajo/estado-implementacion-2026-11-03.md): evidencia de código y pruebas al 03/11/2026. Su foto inicial no sustituye el estado vivo de esta carpeta.
- El archivo contractual `primera-presentacion.md` conserva el alcance **histórico** de 8 CU. Para la planificación operativa vigente, «primera entrega/presentación» significa los **14 CU acordados** aquí. Las fichas académicas CU01–CU37 usan otra numeración.

## Regla de actualización

Al terminar cada lote, el agente externo entrega archivos cambiados, rutas/DTO, pruebas, limitaciones y ramas, sin declarar aceptación por sí mismo ni hacer commits. El propietario avisa a Codex; Codex revisa código y pruebas, actualiza `02-estado-cu.md` y agrega una entrada en `04-bitacora.md`. Los grupos técnicamente revisados pueden entrar en commits de avance por canal; la aceptación completa del CU exige todos sus canales. Registrar hashes reales de los commits de cada repositorio después de crearlos. No inferir progreso por una tabla, una ruta, un test escrito o una respuesta del agente.
