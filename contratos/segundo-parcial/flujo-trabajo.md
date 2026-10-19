# Flujo de trabajo entre repositorios

Esta guía aplica a `backend`, `frontend-web` y `app-movil`, que tienen historiales Git separados. La versión compartida actual es **0.1.1, propuesta para revisión**. Las reglas de negocio se encuentran en `integracion.md`, los CU en `trazabilidad-cu.md`, las formas de sincronización en los dos JSON Schema y los ejemplos en `payloads.md`.

**Puerta fijada por el propietario:** el agente de implementación no hace `git commit`, `git push`, PR ni publicación de ningún tipo. Deja cambios locales revisables, informa las pruebas automáticas y entrega un guion de prueba manual. Solo después de que el propietario pruebe manualmente y dé su **OK explícito** se podrá preparar un commit o publicación, siguiendo la instrucción que dé entonces. La existencia de commits documentales anteriores no autoriza nuevos commits.

## 1. Revisar y cerrar el contrato antes de publicar

1. Conservar localmente los cambios de `refactor/paquetes-cu` en cada repositorio hasta la prueba manual del propietario. No crear una rama nueva si ello pone en riesgo cambios sin commit; después del OK, decidir la rama de implementación de cada entrega.
2. Revisar `trazabilidad-cu.md` contra las 37 fichas locales de [casos-de-uso.md](casos-de-uso.md) y [reglas-aprobadas.md](reglas-aprobadas.md), [paquetes-cu.md](paquetes-cu.md) contra las carpetas canónicas y `interfaz.json` contra las rutas ya existentes. Registrar correcciones localmente; no afirmar que rutas propuestas son OpenAPI implementado.
3. Al acordar los payloads, preparar la versión estable `1.0.0` simultáneamente en los tres repositorios, todavía **sin commit ni push**. Comprobar que las copias de `interfaz.json`, ambos esquemas, `integracion.md` y `payloads.md` son idénticas y que `version.json` contiene las huellas correctas. La publicación y los PR esperan la prueba manual y el OK del propietario.

## 2. Dividir por entregas verticales

| Entrega | Backend (puede asumirlo una persona) | Angular/PWA (puede asumirlo otra) | Flutter | Puerta de integración |
|---|---|---|---|---|
| E1 Base | Migraciones, tenant en identidad/relaciones, permisos, planes, tasa y regresión Ciclo 3. | Selector de empresa, rutas por rol y vistas de plan/tasa con respuestas simuladas. | Selección de empresa y aislamiento de sesión cliente. | Dos empresas aisladas; sesión/plan reales y OpenAPI exportado. |
| E2 Catálogo y solicitud cliente | Catálogo versionado, referencia horaria, sincronización/idempotencia, reserva/compra y resultado durable. | IndexedDB y PWA parcial; catálogo, cola y estados de reserva/compra. | SQLite y cola equivalente, solo cliente. | Reinicio sin red, UUID estable, reserva vencida, última unidad y precio cambiado. |
| E3 Pago y avisos | Apartado 60 min, conversión BOB/USD, webhook/reconciliación, bandeja y emisores FCM/Web Push. | Aceptación de precio/moneda, pago online, bandeja, Web Push. | Pago online, bandeja y FCM Android. | Cobro solo tras stock; USD aceptado; pago incierto recuperable; push reconsulta. |
| E4 Caja web | Cupos, turno 8 h, precios congelados, sincronización y recuperación/conteo. | Caja instalada, IndexedDB separado, cobro/entrega local, cierre y conciliación. | Sin tarea de caja. | Dos cajas, turno vencido, pérdida de almacenamiento y sin doble descuento. |
| E5 Posventa | Cambio, valor neto, saldo personal, extensión del checkout a pago mixto e inventario/Kardex. | Trámite de cambio en web online y consulta/uso de saldo cliente. | Consulta/uso de saldo online. | Centavos exactos y sin doble gasto; diferencia cobrada antes de entregar. |
| E6 Información | Cuatro consultas reales, Gemini validado, exportaciones y dos modelos ML locales/versionados. | Reportes texto/voz, tabla/gráfico/exportación y dashboard Profesional. | Sin administración ni ML. | Cuatro reportes coherentes; métricas ML y aislamiento tenant. |

Los clientes pueden construir pantallas, almacenamiento y consumidores con los ejemplos/esquemas mientras el backend avanza. La **integración real** de una entrega espera sus rutas implementadas y OpenAPI exportado; no se considera completa con solo dobles de prueba. E1 precede a E2–E6 por el ámbito tenant; dentro de cada entrega backend y clientes pueden trabajar en paralelo. Conservación y regresión de CU01–CU25 se verifican en cada entrega, no solamente al final.

Antes de editar un CU, cada agente identifica su paquete en [paquetes-cu.md](paquetes-cu.md), las reglas modificadas en [trazabilidad-cu.md](trazabilidad-cu.md) y los mensajes en `interfaz.json`/`payloads.md`. Implementa dentro del paquete dueño y registra en su entrega los archivos reales de router, servicio, DTO/modelo, persistencia, vista y prueba que correspondan. El endpoint común de sincronización solo despacha; las operaciones de reserva, compra y caja conservan sus dueños. No recrear las carpetas backend de adaptadores retiradas ni colocar administración en Flutter.

## 3. Trabajo local, revisión y evidencia por avance

- Trabajar en una rama corta por entrega y repositorio solo cuando cambiar de rama sea seguro respecto de cambios locales existentes. Por ejemplo `feat/sp-e2-sincronizacion` en backend y `feat/sp-e2-pwa-cliente` en Angular. Los cambios de implementación quedan **sin commits** hasta la prueba manual y el OK explícito del propietario.
- Entregar al propietario el diff local, CU y requisito, versión de contrato, rutas/estados tocados, migraciones, pruebas automáticas y resultados, y pasos concretos de prueba manual. Tras su OK, un PR por conjunto revisable de CU puede enlazar el PR dependiente del otro repositorio; el propietario decide cuándo y quién crea commits o publica.
- Backend publica el OpenAPI **real** de la entrega y ejemplos de respuesta; Angular/Flutter cotejan nombres, tipos, errores y permisos antes de retirar dobles de prueba. Si hay discrepancia, se corrige código o se versiona el contrato con un PR coordinado en los tres repositorios.
- Registrar en `trazabilidad-cu.md` la evidencia de implementación: ruta de código, prueba y, solo cuando el propietario autorice, commit/PR. «Previsto», «implementado» y «verificado» son estados distintos. Cada repositorio conserva aquí las fichas y reglas necesarias para trabajar sin documentación externa; el informe académico se puede actualizar por separado.
- Tras la prueba manual y el OK, integrar en este orden por entrega: contrato coordinado si cambió → backend y OpenAPI → cliente(s) → prueba de integración. Ningún agente adelanta commits o publicación por considerar que las pruebas automáticas son suficientes.

## 4. Cambios en el contrato compartido

`backend/contratos/segundo-parcial` es origen editorial del contrato de API. Todo cambio común incluye razón, impacto en pendientes locales, ejemplo actualizado, versión semántica y nuevas huellas SHA-256. Se propagan copias idénticas a Angular y Flutter en PRs relacionados. Añadir un campo opcional compatible puede ser versión menor; quitar, renombrar o cambiar significado exige versión mayor y migración explícita de IndexedDB/SQLite. `operacion_id` y `version_esquema` de solicitudes ya guardadas nunca se reinterpretan ni se reemplazan silenciosamente.

La organización sugerida permite que una persona tome backend y otra Angular. Flutter puede asignarse después sin alterar el contrato común. La propiedad técnica de cada archivo queda en su repositorio; las decisiones de negocio y de interfaz se revisan conjuntamente.
