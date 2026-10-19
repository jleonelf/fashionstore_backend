# Trazabilidad de casos de uso a contratos

Versión documental 0.1.1. Las fichas académicas CU01–CU25 son la línea base **actualizada** y CU26–CU37 son las ampliaciones del segundo parcial. Este mapa identifica qué se conserva, qué se extiende y qué contrato implementa cada cambio; [paquetes-cu.md](paquetes-cu.md) fija el paquete y la carpeta donde se implementa cada CU. `B` = backend, `W` = Angular web/PWA, `M` = Flutter cliente. Todos los datos empresariales de CU01–CU25 requieren aislamiento por empresa, aunque una fila no repita ese requisito. «Online» significa que no se agrega comportamiento offline a ese CU.

## CU existentes: impacto concreto

| CU | Cambio de segundo parcial | Dueño principal | Relación nueva |
|---|---|---|---|
| CU01 Registro y sesión | Seleccionar empresa en login; sesión, cliente y pertenencia ligados a empresa. Datos privados locales visibles hasta 8 h del último login online. | B, W, M | CU26–CU27 |
| CU02 Usuarios y roles | Superadministración separada; usuarios, permisos y sucursal siempre dentro de empresa. Revocación posterior no borra ventas de caja ya realizadas válidamente. | B, W | CU26–CU27, CU31–CU32 |
| CU03 Ciudades, sucursales y tarifas | Sucursales por empresa; límite de 2/10 activas por plan y compromisos antes de desactivar. Administración online. | B, W | CU27 |
| CU04 Proveedores y recepción | Proveedor, lote, costo y recepción de la empresa; inventario recibido no invade cupos de otra caja/empresa. Gestión online. | B, W | CU26, CU31 |
| CU05 Productos y variantes | Catálogo y SKU en ámbito de empresa; precio/promoción autorizado se congela para turno de caja. Gestión online. | B, W | CU26, CU28, CU31 |
| CU06 Catálogo y disponibilidad | Descarga pública versionada para consulta offline; mostrar fecha y existencia conocida, no reserva de stock. | B, W, M | CU28 |
| CU07 Kardex y existencias | Reflejar stock libre, reservado y comprometido a caja sin doble descuento; movimientos y valoración por empresa. | B, W | CU31–CU32 |
| CU08 Reserva | Conservar reserva online; solicitud offline propia, plazo desde creación local y aceptación central con stock antes de apartar. | B, W, M | CU29 |
| CU09 Traslados | Mantener operación online; validar empresa y disponibilidad que excluye cupos/compromisos. | B, W | CU26, CU31 |
| CU10 Preparación de reserva | Preparar solo reservas aceptadas centralmente; la solicitud local aún no crea trabajo de sucursal. | B, W | CU29 |
| CU11 Venta presencial | Reutilizar venta y pago online; caja web offline cobra/entrega dentro de cupo y sincroniza venta/Kardex una vez. | B, W | CU31–CU32 |
| CU12 Devolución y merma | Mantener cantidades e inventario; cambio de prenda es flujo vinculado con valoración, diferencia y saldo auditado. | B, W | CU33–CU34 |
| CU13 Historial de compras | Mostrar solo compras del cliente y empresa; distinguir solicitud local, venta central y pago confirmado. Últimos estados descargados en clientes. | B, W, M | CU30 |
| CU14 Carrito y checkout | Carrito local/solicitud diferida; revalidar stock y precio central, apartado 60 min y saldo solo online. | B, W, M | CU30, CU34 |
| CU15 Stripe Test | Pago únicamente tras apartado/aceptación; BOB comercial convertido explícitamente a USD con tasa congelada; webhook/reconciliación confiable y pago mixto. | B, W, M | CU30, CU34, CU37 |
| CU16 Delivery por anillos | Conservar cálculo/confirmación online y ámbito de empresa; una copia local no confirma tarifa ni pedido. | B, W, M | CU30 |
| CU17 Probador móvil | Mantener Decart/SDK Android existente online; validar ámbito de empresa y cliente. Sin cambio funcional de ML. | B, M | CU26 |
| CU18 Sugerencias IA cliente | Mantener online y acotar contexto/catálogo a empresa; no confundir con los dos modelos ML nuevos. | B, W, M | CU26, CU35–CU36 |
| CU19 Dashboard | Indicadores reales por empresa; fecha central y métricas separadas. Vistas ML nuevas solo Profesional. | B, W | CU27, CU35–CU36 |
| CU20 Búsqueda por voz cliente | Mantener online, filtros de catálogo validados y ámbito de empresa; distinta de la voz de reportes web. | B, W, M | CU26 |
| CU21 Reporte generativo | Voz o texto en web online; Gemini interpreta, FastAPI valida y ejecuta cuatro consultas tipadas; Excel/CSV/PDF. Solo Profesional. | B, W | CU27 |
| CU22 Promociones | Mantener gestión online por empresa; turno offline usa solo promociones congeladas al abrir. | B, W | CU31–CU32 |
| CU23 Ventas de sucursal | Incluir ventas de caja sincronizadas; fecha de aceptación central predeterminada y fecha física local visible/filtrable. | B, W | CU32 |
| CU24 Expiración de reservas | Expirar solo reservas aceptadas y liberar stock una vez; solicitud local vencida se rechaza al sincronizar. Mantener auditoría e idempotencia. | B | CU29 |
| CU25 Decisiones IA inventario | Mantener apoyo online con métricas autorizadas por empresa; no presentarlo como modelo supervisado/no supervisado entrenado. | B, W | CU35–CU36 |

## CU nuevos: capacidad y salida verificable

| CU | Implementación y contrato | Componentes | Evidencia mínima |
|---|---|---|---|
| CU26 Registrar empresa | Alta multitenant, administrador inicial, identificador propio y aislamiento. `integracion.md`: identidad/empresa. | B, W | Dos empresas sin lectura/escritura cruzada. |
| CU27 Administrar suscripción | Plan administrativo, fechas manuales, gracia 72 h, 2/10 sucursales, posventa tras expiración. | B, W | Cambio/reducción de plan y compromisos previos. |
| CU28 Descargar catálogo | `GET /catalogo/descarga`, versión/fecha, caché público por empresa. | B, W, M | Reinicio sin red y existencia marcada como conocida. |
| CU29 Sincronizar reserva | `SOLICITAR_RESERVA` de `operacion.schema.json`, resultado durable y tiempo desde creación local. | B, W, M | Vencimiento, stock y UUID repetido. |
| CU30 Sincronizar compra | `SOLICITAR_COMPRA`, precio aceptado online, apartado y Stripe posterior; push/bandeja. | B, W, M | Última unidad, precio cambiado y ningún cobro previo. |
| CU31 Habilitar caja | Turno 8 h, cupos por variante, precios/promociones congelados. | B, W | Cupos asignados concurrentemente sin duplicación. |
| CU32 Venta de contado offline | `REGISTRAR_VENTA_CAJA`, efectivo/entrega local, sincronización, cierre y recuperación auditada. | B, W | Reinicio, reintento, turno vencido y caja perdida. |
| CU33 Cambio de prenda | Valor neto por unidad, plazo/estado/sucursal, reemplazo y diferencia pagada o saldo emitido. | B, W | Centavos, Stripe incierto y entrega posterior al pago. |
| CU34 Aplicar saldo | Saldo personal BOB, uso parcial online y reserva contra doble gasto. | B, W, M | Dos usos concurrentes; compra mixta. |
| CU35 Pronóstico supervisado | Unidades de próxima semana por producto/sucursal; entrenamiento local y métricas, Profesional. | B, W | Artefacto/versiones y evaluación reproducible. |
| CU36 Grupos no supervisados | Agrupación por comportamiento de ventas, entrenamiento local y métricas, Profesional. | B, W | Grupos por empresa y datos insuficientes. |
| CU37 Tasa BOB/USD | Versión global, vigencia, conversión decimal, importe USD mostrado/congelado. | B, W | Tasa ausente/cambiada y webhook tardío. |

## Límite académico explícito

Flutter es cliente. La venta de contado offline y persistencia de ventas físicas locales que el enunciado pide en Flutter **no están cubiertas** por decisión de alcance; CU31–CU32 se implementan únicamente en caja web. La compra diferida de CU30 no se presenta como venta de contado móvil. Ninguna fila «evidencia mínima» está marcada como ejecutada en esta fase documental.
