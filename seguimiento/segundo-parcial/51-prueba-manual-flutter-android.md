# Revisión móvil y pruebas pendientes

- **Fecha:** 7 de noviembre de 2026
- **Dispositivo:** Xiaomi 21061110AG, Android 13 (API 33)
- **APK:** `app-movil/build/app/outputs/flutter-apk/app-debug.apk`
**API y datos:** FastAPI local por USB/`adb reverse`; bases locales separadas `fashionstore_manual_test` (prueba en teléfono) y `fashionstore_test` (pytest). No se usó ni modificó la base oficial.

Este informe reemplaza los resultados intermedios anteriores de esta auditoría. Separa los flujos ejecutados en el teléfono, las pruebas automatizadas y lo que aún requiere una prueba manual o una corrección adicional.

## Correcciones incorporadas

- **Caja Flutter CU06/CU07:** el selector consulta variantes activas y existencias de la sucursal; excluye artículos sin disponibilidad, muestra el stock libre, inicia la cantidad en una unidad y limita las unidades que se pueden añadir. Al cerrar o conciliar un turno, vuelve a consultar existencias para evitar dejar cantidades antiguas en pantalla.
- **Caja Flutter:** se corrigió el ancho del selector de artículo que desbordaba el formulario en el teléfono.
- **Checkout Flutter CU21:** la respuesta durable basada en `pedido_id` continúa al pago del pedido mediante PaymentSheet y confirmación del backend, en lugar de interpretar la respuesta como una venta CU14.
- **Posventa Flutter:** servicio, modelos e historial usan las rutas y respuestas actuales de saldos, devoluciones, cambios y reembolsos. La pantalla de historial permite solicitar devolución.
- **Backend de traslados CU09:** al reintentar una línea rechazada, el nuevo traslado toma explícitamente `empresa_id` de su reserva. El disparador multitenant ya no rechaza esa operación válida.
- **Fixtures de vencimiento:** el helper de pruebas mueve conjuntamente el origen temporal y el vencimiento, conservando la restricción `vence_en >= origen_plazo_en` y la ventana original de 24/72 horas.
- **OpenAPI segundo parcial:** se regeneró `contratos/segundo-parcial/openapi-segundo-parcial.json` desde `backend.app.main.app.openapi()` después de que la prueba detectara que el contrato exportado estaba desactualizado.

## Prueba manual en el teléfono

| Flujo | Resultado | Evidencia y alcance |
|---|---|---|
| API local y conexión USB | **Verificado** | `/health` operativo. Se restauró `adb reverse tcp:8000 tcp:8000` cuando fue necesario. |
| Inicio de sesión y catálogo | **Verificado** | Inicio como cliente y como cajero; catálogo FashionStore, variantes y disponibilidad cargaron desde la API local. |
| Catálogo offline | **Verificado** | Se descargó la copia y continuó visible tras desactivar Wi-Fi en la prueba previa de esta sesión. |
| Notificación FCM | **Verificado** | Se registró el token del dispositivo, Firebase aceptó el envío de prueba y Android mostró la notificación. No se revalidó una notificación posterior a una compra Stripe. |
| Reserva online | **Verificado** | Crear, consultar detalle y cancelar; la cancelación liberó el stock. |
| Carrito | **Verificado** | Precio durable correcto: una unidad Bs 130; dos unidades Bs 260. |
| Caja: apertura con stock real | **Verificado** | La lista móvil mostró para `DEMO-CAMISETA-L-AZUL` una unidad disponible, asignó ese cupo y abrió el turno por ocho horas. |
| Caja: venta en efectivo sin enlace con la API | **Verificado** | Se quitó temporalmente `adb reverse` para simular pérdida de conexión con la API local. Se registró una unidad por Bs 145, recibido Bs 150, cambio Bs 5 y comprobante local `COMP-LOC-7F2A50FC`. La venta quedó pendiente en el teléfono y el cupo libre pasó a cero. Esto prueba pérdida del enlace a la API local, no una certificación de todos los modos de radio del teléfono. |
| Caja: sincronización | **Verificado** | Al restaurar `adb reverse`, la sincronización quitó la venta de pendientes. La base `fashionstore_manual_test` muestra venta `PAGADA` y `recibida_central_en` asignado; el turno cerró con arqueo Bs 145. |
| Caja: conciliación supervisada | **Verificado** | Un segundo cierre sin arqueo entró en `CONCILIACION`; se resolvió en la app con conteo físico y referencia de acta. El historial registra cierre en conciliación y posterior conciliación supervisada; terminó `CERRADO`. La unidad no vendida quedó disponible: SKU M con 8 unidades y cupo comprometido en cero. El SKU L vendido quedó con cero unidades libres. No hay turno de prueba abierto. |
| Refresco visual de stock tras cierre | **Pendiente de confirmación física** | Antes del último ajuste, la pantalla conservaba 7 aunque la base ya mostraba 8. Se implementó la recarga y el widget test comprueba que no siga ofreciendo la prenda agotada al cerrar. La APK final se compiló e instaló, pero Android quedó bloqueado antes de observar en pantalla la recarga final. |
| Checkout/Stripe en el teléfono | **No probado de extremo a extremo** | El código y la pantalla de pago de pedido tienen pruebas automatizadas, pero no se completó un cobro Stripe con el teléfono. Requiere conectividad externa y una compra de prueba. |
| Compra diferida sin conexión y confirmación posterior | **No probado físicamente** | Falta recorrer en el teléfono el estado pendiente, recuperación de red, reintento automático, confirmación del backend y notificación push de compra exitosa. |
| Solicitud de devolución/cambio desde cliente | **No probada de extremo a extremo** | Las rutas/modelos móviles y la lógica backend se alinearon; falta una compra pagada/entregada de prueba para recorrer el ciclo completo y observar el saldo/reembolso. |
| Reserva offline y sincronización | **No probada en teléfono** | Hay pruebas automatizadas del detalle/cola offline, pero no se completó el recorrido físico de crear offline y sincronizar después. |
| Probador CU17 | **No probado** | No se llegó al SDK realtime. Falta contenido compatible y la arquitectura requerida `docu_general/ciclo-3/07-arquitectura-probador-decart.md` no está en el repositorio. El `AGENTS.md` prohíbe modificar CU17 en backend o Flutter sin ese documento; queda como bloqueo documental y de configuración Decart.

Las operaciones de Caja se ejecutaron únicamente en `fashionstore_manual_test`. No se tocaron inventarios, ventas ni turnos de la base oficial.

## Verificación automatizada

| Verificación | Resultado |
|---|---|
| `flutter analyze --no-pub` | Sin problemas. |
| `flutter test --no-pub --reporter compact` | **243 aprobadas, 0 fallidas, 0 omitidas.** |
| Widgets de Caja tras recarga de stock | **7 aprobadas** (`caja_flujo_productivo_completo_test.dart`, `caja_offline_screen_test.dart`). |
| Compilación APK debug | Correcta e instalada en el dispositivo. |
| `python -m compileall -q app tests` | Correcto después de las correcciones CU09 y del helper de pruebas. |
| Pruebas backend focalizadas anteriores (CU03/04/06/07/12) | **23 aprobadas**, 3 advertencias, en `fashionstore_test`. |
| CU09 reintento de traslado + CU10 preparación + CU11 venta de reserva | **3 aprobadas** tras corregir CU09 y el helper de vencimiento. |
| Suite principal `python -m pytest tests/ -q` | **128 aprobadas, 48 fallidas** en 587.99 s, antes de las dos últimas correcciones. Tres fallos de esa corrida se volvieron a ejecutar y aprobaron por separado; no se repitió la suite completa después, así que no se presenta un nuevo total global. |

Los fallos backend restantes requieren clasificación y corrección; se concentran en pruebas `test_ciclo3_correcciones_*`, CU02, CU14–CU17, CU18/CU20, CU19/CU21/CU25, CU22 y CU24. Entre los síntomas observados hay pruebas que todavía esperan `venta_id`/`pedido_entrega_id` mientras el checkout durable actual devuelve `pedido_id`, escenarios de concurrencia/idempotencia, promociones, roles y expiración. No se concluye que todas sean solo pruebas desactualizadas: hace falta resolverlas contra el contrato vigente.

La suite aislada `tests_segundo_parcial_bloque_b/` se ejecutó en `fashionstore_test`: **289 aprobadas y 1 fallida** porque el OpenAPI exportado estaba desincronizado. Se regeneró el JSON desde FastAPI y las tres pruebas del archivo OpenAPI pasaron al repetirlas. No se repitieron los 290 casos del bloque completo después de regenerarlo. La primera invocación general de `pytest` sí abortó durante colección porque faltaba `FASHIONSTORE_TEST_DATABASE_URL`; esa invocación no llegó a ejecutar pruebas.

## Pendientes para dar por verificada la app móvil

1. Desbloquear el teléfono y confirmar en la APK instalada que la disponibilidad de Caja se refresca en pantalla tras cierre normal y conciliación supervisada.
2. Ejecutar compra Stripe de prueba completa y comprobar estado de pedido y push de éxito.
3. Ejecutar compra diferida sin conexión, recuperación de conectividad y sincronización automática hasta recibir push.
4. Crear una compra pagada y entregada, pedir una devolución desde Flutter y revisar inspección, saldo y reembolso.
5. Ejecutar reserva offline y sincronizarla físicamente.
6. Para CU17, incorporar primero la arquitectura Decart faltante; después configurar credenciales y validar con Android físico.
7. Clasificar y corregir el conjunto de fallos de backend; hasta entonces la verificación global del proyecto no está cerrada.

## Actualización backend del 8 de noviembre de 2026

- Se unificó la ruta `/carritos/mio/checkout`: el cuerpo con `canal` conserva la respuesta legada `venta_id`; el cuerpo sin `canal` usa el pedido durable CU21 y responde con `pedido_id`. Se regeneró el OpenAPI vigente.
- Se corrigieron el tenant de la venta/entrega legada, la correspondencia ORM de entregas con la base migrada y la idempotencia de mutaciones del carrito durable.
- La suite aislada del segundo parcial terminó con **290 aprobadas** y 3 advertencias en `fashionstore_test`.
- La suite principal terminó con **165 aprobadas y 11 fallidas** antes de la corrección del test de concurrencia Stripe. Ese test reutilizaba un ID de evento para seis pagos, se corrigió y pasó de forma aislada. La suite global no se repitió después de esa corrección; permanecen 10 fallos observados en la corrida global, principalmente CU17/Decart, identidad, IA y un caso de entregas sensible al orden.
- La solicitud de checkout actual de Flutter aún incluye `canal` en el cuerpo, por lo que entra en la rama legada. Para usar la compra durable desde móvil deberá actualizarse el cliente Flutter y probarse el pago de extremo a extremo en el teléfono. Este commit modifica únicamente el repositorio backend.
