# Flujo de trabajo entre repositorios

Esta guía aplica a `backend`, `frontend-web` y `app-movil`, que tienen historiales Git separados. La versión compartida actual es **0.1.0, propuesta para revisión**. Las reglas de negocio se encuentran en `integracion.md`, los CU en `trazabilidad-cu.md`, las formas de sincronización en los dos JSON Schema y los ejemplos en `payloads.md`.

## 1. Publicar y cerrar el contrato

1. Publicar la rama `docs/contratos-segundo-parcial` de **cada** repositorio y abrir tres PR documentales relacionados. Los commits locales actuales todavía no están publicados.
2. Revisar `trazabilidad-cu.md` contra las 37 fichas académicas y `interfaz.json` contra las rutas ya existentes. Resolver observaciones en los PR; no afirmar que rutas propuestas son OpenAPI implementado.
3. Al acordar los payloads, marcar versión estable `1.0.0` simultáneamente en los tres repositorios y fusionar los PR. Antes de fusionar, comprobar que las copias de `interfaz.json`, ambos esquemas, `integracion.md` y `payloads.md` son idénticas y que `version.json` contiene las huellas correctas.

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

## 3. Rama, PR y evidencia por avance

- Abrir una rama corta por entrega y repositorio, por ejemplo `feat/sp-e2-sincronizacion` en backend y `feat/sp-e2-pwa-cliente` en Angular. Un PR implementa un conjunto revisable de CU; evitar un PR único de todo el parcial.
- En descripción del PR consignar: CU y requisito, versión de contrato, rutas/estados tocados, migraciones, cambio visual/local, pruebas ejecutadas y resultado, y enlace al PR dependiente del otro repo. Los commits pueden separar migración, servicio, endpoint, interfaz y prueba significativa.
- Backend publica el OpenAPI **real** de la entrega y ejemplos de respuesta; Angular/Flutter cotejan nombres, tipos, errores y permisos antes de retirar dobles de prueba. Si hay discrepancia, se corrige código o se versiona el contrato con un PR coordinado en los tres repositorios.
- Actualizar evidencia en la matriz académica con ruta de código, prueba y commit/PR cuando una fila esté implementada. «Previsto», «implementado» y «verificado» son estados distintos. La documentación académica original está fuera de estos tres repositorios y requiere publicación propia si el compañero debe editarla.
- Fusionar en este orden por entrega: contrato coordinado si cambió → backend y OpenAPI → cliente(s) → prueba de integración. Se pueden abrir PRs en paralelo y fusionarlos cuando la puerta de esa entrega pase.

## 4. Cambios en el contrato compartido

`backend/contratos/segundo-parcial` es origen editorial del contrato de API. Todo cambio común incluye razón, impacto en pendientes locales, ejemplo actualizado, versión semántica y nuevas huellas SHA-256. Se propagan copias idénticas a Angular y Flutter en PRs relacionados. Añadir un campo opcional compatible puede ser versión menor; quitar, renombrar o cambiar significado exige versión mayor y migración explícita de IndexedDB/SQLite. `operacion_id` y `version_esquema` de solicitudes ya guardadas nunca se reinterpretan ni se reemplazan silenciosamente.

La organización sugerida permite que una persona tome backend y otra Angular. Flutter puede asignarse después sin alterar el contrato común. La propiedad técnica de cada archivo queda en su repositorio; las decisiones de negocio y de interfaz se revisan conjuntamente.
