# Contrato compartido de API y sincronización

**Estado:** diseño para CU28–CU34 y cambios en CU08/CU14/CU15. No equivale al OpenAPI real. Las decisiones aprobadas se resumen aquí y en [integracion.md](integracion.md); las 37 fichas funcionales están en [casos-de-uso.md](casos-de-uso.md) y los acuerdos íntegros aplicables en [reglas-aprobadas.md](reglas-aprobadas.md).

## Identidad y versión

- Todas las operaciones privadas requieren sesión/identidad válida. El backend deriva `empresa_id` del usuario autenticado y comprueba la pertenencia de cada recurso, sucursal y cliente. Los identificadores de empresa incluidos en comandos son referencias de comprobación, nunca autorización suficiente.
- `version_esquema` identifica la forma del comando. Cambios incompatibles producen versión nueva y migración local; no reinterpretar silenciosamente pendientes antiguos.
- Cada comando tiene `operacion_id` UUID estable, `tipo`, `creada_local_en`, `empresa_id`, `usuario_id`, `dispositivo_id`, `secuencia_local` y `datos` tipados. Caja añade `turno_id`, `habilitacion_id`, versión de precios y cupos consumidos. El servidor conserva hash canónico del comando y respuesta.
- Repetir mismo `operacion_id` y contenido devuelve el mismo resultado tras reautorizar actor y empresa. Mismo ID con contenido diferente devuelve conflicto `OPERACION_MODIFICADA`. Los reintentos no cambian la fecha original ni prolongan vencimientos.
- El resultado contiene `operacion_id`, `estado`, `codigo`, `recibida_en`, `aceptada_en` si aplica, `recurso_id` si aplica, `revision` y detalle legible. La pérdida de respuesta se resuelve consultando por ID, no enviando una nueva operación con otro ID.

## Familias de operaciones

| Tipo lógico | Origen y datos mínimos | Efecto central |
|---|---|---|
| `SOLICITAR_RESERVA` | Cliente PWA/Flutter: sucursal, visita, variantes/cantidades y fecha local | Revalidar tiempo, identidad y stock; aceptar y reservar o rechazar/conflicto. |
| `SOLICITAR_COMPRA` | Cliente PWA/Flutter: sucursal elegida, líneas y precios vistos | Revalidar total y stock; pedir aceptación de precio si cambió, o apartar 60 min y ofrecer pago online. |
| `REGISTRAR_VENTA_CAJA` | Caja web: turno, habilitación, líneas, precio autorizado, total BOB, efectivo/entrega y cupo consumido | Registrar venta/pago/Kardex contra cupo asignado; auditar incidencias. |

Esta versión transporta **un comando por solicitud** y cada comando tiene transacción y resultado independiente. Las colas cliente envían operaciones en orden; un rechazo no revierte otras operaciones ya aceptadas. No mezclar ventas físicas cobradas con solicitudes digitales pendientes de pago. Los comandos cliente se envían solo después de reautenticación online; la caja envía ventas realizadas bajo habilitación original y el backend audita revocaciones posteriores.

## Estados visibles

| Flujo | Estados locales/centrales principales |
|---|---|
| Reserva | `GUARDADA_LOCAL`, `PENDIENTE_ENVIO`, `EN_REVISION`, `ACEPTADA`, `RECHAZADA`, `CONFLICTO`. Solo `ACEPTADA` aparta stock. |
| Compra digital | `GUARDADA_LOCAL`, `PENDIENTE_ENVIO`, `REQUIERE_ACEPTACION_PRECIO`, `SIN_STOCK`, `PENDIENTE_PAGO`, `PAGO_EN_VERIFICACION`, `PAGADA`, `PAGO_FALLIDO`, `VENCIDA`. Solo webhook/reconciliación confiable confirma `PAGADA`. |
| Venta de caja | `BORRADOR_LOCAL`, `COBRADA_ENTREGADA_LOCAL`, `PENDIENTE_ENVIO`, `REGISTRADA_CENTRAL`, `CONCILIACION_REQUERIDA`. La etiqueta local no se presenta como confirmación central. |

Los nombres se precisarán en enums del backend y se exportarán una sola vez a clientes. Las transiciones permitidas deberán probarse; un aviso tardío no retrocede ni renueva un estado.

## Causas de resultado y recuperación

| Código | Significado y acción de interfaz |
|---|---|
| `SIN_STOCK` | Mostrar variantes faltantes; no cobrar ni crear reserva/venta digital parcial. |
| `PRECIO_CAMBIADO` | Mostrar total actualizado y pedir aceptación online antes de apartar. |
| `SOLICITUD_VENCIDA` | Reserva fuera de 24/72 h: iniciar solicitud nueva si el cliente desea continuar. |
| `TIEMPO_INCOHERENTE` | Conservar operación en conflicto; no apartar automáticamente; mostrar revisión/renovación según contrato. |
| `PLAN_NO_HABILITADO` | No aceptar nuevas operaciones; las ventas de caja ya realizadas válidamente se concilian y auditan. |
| `CUPO_INSUFICIENTE` | Impedir nueva venta de caja local; una venta ya cobrada se trata mediante incidencia auditada. |
| `TASA_NO_VIGENTE` | Impedir nueva intención Stripe, conservando pedido/stock según vencimiento original. |
| `OPERACION_MODIFICADA` | No reaplicar; mantener original y registrar incidencia de sincronización. |
| `PAGO_EN_VERIFICACION` | Consultar estado remoto; no afirmar éxito ni fracaso y no liberar stock prematuramente. |

Los estados HTTP exactos y esquemas de error se fijarán en OpenAPI del backend, conservando estos códigos de negocio estables. Ningún cliente interpreta una falla de red como rechazo comercial.

## Importes, fechas y notificaciones

- BOB comercial y saldo con dos decimales. Tasa positiva BOB por USD versionada y vigente; convertir con aritmética decimal y `ROUND_HALF_UP` a USD de dos decimales. Exponer BOB, tasa, fecha de vigencia y USD final para aceptación. Webhook compara contra intención congelada. Ningún cliente calcula el monto final como autoridad.
- En reportes, fecha predeterminada de aceptación central; fecha física local y recepción son campos separados. Solicitud de compra offline no es venta confirmada. Venta de caja cobrada localmente entra al reporte central al aceptarse, con su fecha física disponible.
- Cada resultado central relevante persiste en bandeja propia. Android FCM y PWA Web Push son canales de aviso, no fuente del estado ni mecanismo para enviar un borrador que nunca salió del dispositivo. Abrir aviso vuelve a consultar recurso tras autenticar.

## Operaciones REST a concretar sobre `/api/v1`

Estas son rutas **propuestas**, nuevas o extensiones, sujetas a reconciliación con las rutas existentes al implementar:

| Propósito | Ruta de diseño |
|---|---|
| Descargar catálogo versionado | `GET /catalogo/descarga` |
| Enviar un comando | `POST /sincronizacion/operaciones` |
| Obtener referencia de hora del servidor | `GET /sincronizacion/referencia-horaria` |
| Recuperar resultado | `GET /sincronizacion/operaciones/{operacion_id}` |
| Consultar bandeja propia | `GET /notificaciones/mias` |
| Aceptar precio y preparar pago | `POST /compras/{solicitud_id}/aceptar-precio` |
| Consultar saldo propio | `GET /saldos/mio` |

No duplicar `/reservas`, `/carritos` o `/pagos` existentes sin evaluar sus contratos y compatibilidad. OpenAPI se exporta desde FastAPI después de implementar y se compara con esta especificación.
