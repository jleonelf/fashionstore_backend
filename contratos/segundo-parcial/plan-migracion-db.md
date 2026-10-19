# Plan de migración de base de datos — segundo parcial

**Estado:** diseño previo a DDL. No se ha ejecutado ninguna migración nueva sobre `fashionstore_db`. El agente debe preparar migraciones Alembic y ensayarlas en una **base de prueba restaurada**, dejando la base original intacta hasta revisión y autorización posterior del propietario.

## Línea base comprobada el 18/10/2026

- PostgreSQL local 17 en `127.0.0.1:5432`, base `fashionstore_db`; Alembic `0005_ciclo3_correcciones`.
- 37 tablas en los esquemas `seguridad`, `organizacion`, `catalogo`, `inventario`, `comercial`, `inteligencia` y `public`. Ninguna tabla empresarial tiene columna `empresa_id` todavía.
- Conteos útiles para comprobar conservación: 7 usuarios, 4 clientes, 3 sucursales (**3 activas**), 8 productos, 16 variantes, 48 filas de inventario, 1 reserva, 4 ventas, 4 pagos y 2 registros de idempotencia.
- La unicidad actual de correo de usuario y SKU/código de barras de variante es global. Hay otras claves globales en proveedor NIT, promoción, venta y reserva que deben evaluarse antes de permitir iguales entre empresas.
- `inventario.inventario_sucursal` conserva `disponible`, `reservado`, `comprometido_traslado` y `en_transito`; aún no existe `comprometido_caja`.

**Evidencia histórica de la instalación del propietario:** se generó el respaldo local `fashionstore_db_pre_segundo_parcial_20261018_141800.dump` (formato custom, esquema y datos), SHA-256 `ca82f87f99ee4557cbf30b814e13cd83afa7b783bb5440ca2e325f2dfc00d734`, y se restauró para ensayo en `fashionstore_sp2_pruebas_20261018_142115`: revisión `0005`, 7 usuarios, 3 sucursales y 4 ventas. El dump, manifiesto y base de ensayo **no forman parte del repositorio ni son requisito para leer este contrato**. En otra instalación se debe generar/verificar un respaldo propio y restaurar una base de prueba independiente antes de ensayar DDL. Ningún dump incluye roles globales ni configuración del servidor.

## Esquema objetivo por etapas

| Etapa Alembic prevista | Objetos nuevos o cambios | Conservación/validación obligatoria |
|---|---|---|
| 0006 Identidad y tenant | `organizacion.empresas`, historial de suscripciones/planes; `empresa_id` en usuarios, sucursales, catálogo, inventario, comercio e inteligencia; índices y relaciones tenant; `plataforma.tasas_cambio` global versionada. | Crear empresa heredada y asociar **todos** los registros actuales sin cambiar UUID ni borrar filas. `organizacion.ciudades` y `seguridad.roles` pueden mantenerse como referencias globales. Superadministración separada. |
| 0007 Sincronización cliente | Referencias horarias, catálogo versionado, `comercial.operaciones_sincronizacion` con UUID/hash/resultado durable; fechas local, recepción y aceptación para reservas/ventas; bandeja y suscripciones push. | El reintento no duplica reserva/venta. Nunca reconstruir resultado previo desde un payload nuevo. |
| 0008 Caja offline | `comercial.turnos_caja`, `inventario.cupos_caja`, `comprometido_caja` no negativo, versión de precios/promociones, referencia de venta local y registros de conciliación/conteo. | Al asignar cupo: libre → comprometido. Al aceptar venta: comprometido → vendido, sin nuevo débito de libre. Cupo no usado se libera solo tras cierre o conteo auditado. |
| 0009 Cambios y saldo | `comercial.cambios`, detalles/movimientos de cambio, saldo y libro de movimientos por empresa/cliente; importes BOB, pago mixto, referencias idempotentes. Extender pagos con tasa/version e importes BOB/USD congelados. | Valor por unidad y descuentos conservan centavos; saldo no se usa dos veces; no reescribir pagos históricos como USD convertidos. |
| 0010 Reportes y ML | Índices para fecha de aceptación/tenant/filtros; metadatos de modelos, datasets sintéticos versionados, evaluaciones y resultados de analítica en `inteligencia`. | Entrenamiento fuera de HTTP; artefactos/datos reales aislados por empresa y acceso Profesional. |

Los nombres `0006`–`0010` son **orden sugerido**, no migraciones ya creadas. Separar una etapa si el ensayo revela bloqueo o riesgo de backfill. El esquema final se confirma con el modelo SQLAlchemy y la migración revisada; no aceptar una autogeneración Alembic sin inspeccionarla.

## Traspaso de los datos actuales

1. Crear una empresa heredada con identificador estable y asociar usuarios, sucursales, productos/maestros, proveedores, inventario, pedidos, ventas, pagos, movimientos, promociones e IA actuales. Conservar IDs y relaciones existentes.
2. Las **3 sucursales activas** actuales exceden Básico (2). La empresa heredada necesita Profesional para seguir operando sin desactivar ninguna. La asignación es administrativa con fechas manuales; la migración no debe inventar fecha de vencimiento ni activar cobros SaaS. Preparar un paso de configuración explícito que solicite las fechas al propietario antes de habilitar nuevas operaciones bajo control de plan.
3. Sustituir unicidades globales por unicidades con empresa cuando el dato pertenezca al negocio: correo, SKU, código de barras, NIT, códigos de promoción/venta/reserva y maestros aplicables. Mantener PK UUID globales y añadir FKs compuestas o verificaciones equivalentes para impedir referencias entre empresas.
4. Crear índices por `empresa_id` y filtros de consulta. Configurar y probar RLS con el rol **real de la aplicación**, sin `BYPASSRLS`; sesiones de superadministración, jobs, webhook, exportaciones y consultas por ID deben establecer ámbito explícito. Nunca confiar en un `empresa_id` del cliente como autorización.
5. Primero añadir columnas nullable, rellenar y verificar que no quedan filas empresariales sin empresa; luego fijar `NOT NULL`, unicidades y FKs. Para usuarios de superadministración, usar regla explícita aparte de la cuenta empresarial. Evitar bloqueos largos con índices/validación por fases si el tamaño crece.

## Puertas de prueba y recuperación

1. Verificar el hash del respaldo disponible y restaurarlo en **otra base local de prueba**. En la instalación del propietario ya se comprobó `fashionstore_sp2_pruebas_20261018_142115` en revisión `0005`; en un clon independiente documentar nombre, revisión y conteos reales de su propia base. Nunca restaurar encima de la base activa para ensayar.
2. Ejecutar `alembic upgrade head` únicamente en la base de prueba verificada, usando configuración de conexión de prueba explícita. Comprobar conservación de los conteos de esa base; en la instalación registrada eran 3 sucursales heredadas. Verificar cero referencias entre tenants, restricciones de cupo/saldo y dos empresas de prueba. Ensayar regresión de Ciclo 3 y exportar OpenAPI real.
3. Preparar consulta de preflight y reporte de cambios efectivos. Entregar al propietario diff de migraciones, evidencia de prueba, pasos de prueba manual y procedimiento de recuperación. **No aplicar DDL sobre `fashionstore_db` ni hacer commit/push** antes de que el propietario haga su prueba manual y dé su OK explícito para el siguiente paso.
4. Si la base original se migra posteriormente y falla, no ejecutar downgrade destructivo a ciegas. Detener escrituras, diagnosticar estado y restaurar desde el backup verificado a una base nueva para recuperación supervisada.

Este plan cubre esquema y datos. Stripe Test, Web Push/FCM y artefactos ML tienen configuración/archivos externos que el dump de PostgreSQL no respalda.
