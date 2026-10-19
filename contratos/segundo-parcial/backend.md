# Contrato backend FastAPI/PostgreSQL

**Estado:** diseño previo a migraciones y endpoints. Comparte comandos/estados con [compartido.md](compartido.md). Las firmas de ejemplo son nombres **nuevos en español**; deben verificarse contra servicios actuales para reutilizar comportamiento y no romper APIs públicas.

## Ubicación de la implementación

[paquetes-cu.md](paquetes-cu.md) fija la carpeta dueña de CU26–CU37 y de las adaptaciones de CU01–CU25. Los modelos, DTO, repositorios, servicios y routers nuevos se agregan al paquete `app/core/modules/<paquete>/` correspondiente; se amplían los archivos existentes cuando la entidad o el servicio ya existe. `caja_offline` es el único paquete backend nuevo previsto. `app/api/v1/api.py` monta los routers y puede montar un adaptador común de sincronización, pero la validación y transacción de cada operación pertenecen a `reservas_traslados`, `ventas_pagos` o `caja_offline`.

`app/core/` conserva infraestructura transversal y `app/db/modelos.py` registra los modelos para Alembic. No recrear `app/models/`, `app/repositories/`, `app/schemas/`, `app/services/` ni `app/api/v1/endpoints/`. Una migración vive en `alembic/versions/`, no dentro de un paquete. Las integraciones Decart y Stripe existentes ya están bajo sus paquetes dueños; el proveedor IA compartido está en `app/core/integraciones/`.

## Autorización y planes

- Empresa se resuelve de la identidad validada; superadministración es un ámbito separado. Misma dirección de correo puede registrarse en dos empresas, pero el login identifica cuál. Consultas, escrituras, webhooks, tareas, reportes, reintentos y recursos por ID verifican tenant antes de devolver datos.
- PostgreSQL compartido: `empresa_id` en datos empresariales, relaciones compuestas y políticas RLS donde corresponda. Probar con rol de aplicación real y dos empresas, incluidas consultas indirectas, exportaciones y claves idempotentes.
- Plan Básico: máximo dos sucursales activas. Profesional: máximo diez, reportes generativos y ambos módulos ML. Ambos admiten operación offline acordada. Vigencia manual y gracia de 72 horas; tras ella no abrir ventas, reservas ni turnos nuevos, pero sí consultas, posventa en plazo y cierre de compromisos previos.

## Persistencia e invariantes

| Agregado o registro | Invariante que el backend debe imponer |
|---|---|
| Empresa/suscripción | Versiones y fechas auditadas; reducción de plan no excede sucursales activas ni desactiva sucursal con compromiso pendiente. |
| Inventario | No negativos; `disponible`, reservado, compromiso digital y `comprometido_caja` no usan la misma unidad dos veces. Cada transición tiene Kardex/referencia. |
| Turno/cupo de caja | Cupos asignados bajo bloqueo de inventario; un turno activo por caja según contrato; consumo no supera lote; cupo restante solo se libera tras cierre o recuperación auditada. |
| Resultado de sincronización | Único por empresa, actor y `operacion_id`; payload/hash y respuesta durables, reintento sin doble efecto. |
| Venta/pago | Venta digital requiere webhook o conciliación remota confiable; venta física offline registra efectivo recibido y entrega dentro de cupo. Pago tardío no pierde inventario. |
| Cambio/saldo | Unidades acumuladas no superan cantidad vendida; saldo por empresa/cliente, historial de emisión/reserva/uso/liberación sin doble gasto. |
| Tasa de plataforma | Versiones sin solape vigente, valor positivo, autor y fecha; intención Stripe conserva tasa e importe USD aceptado. |
| Analítica | Artefactos/modelos versionados; consultas e inferencia acotadas a tenant; no mezclar datos privados de empresas al reentrenar. |

## Límites transaccionales

1. **Reserva:** bloquear filas de inventario afectadas; validar plazo desde creación local, sucursal y stock; guardar reserva, líneas, cantidades/Kardex y resultado del comando en una transacción.
2. **Compra diferida:** revalidar precio y stock, pedir aceptación si corresponde; apartado completo, venta pendiente, líneas, compromiso/Kardex y resultado en una transacción. Stripe se crea después como efecto externo recuperable. Apartado: 60 minutos desde aceptación central.
3. **Caja:** asignación de cupos bloquea stock libre. Sincronización consume cupo previamente asignado y registra venta, efectivo, detalle, Kardex y resultado en una transacción **sin segundo descuento**. Ventas válidas hechas antes de baja de empleado/plan se registran y marcan para revisión.
4. **Cambio/saldo:** bloquear venta/líneas y saldo; registrar devolución, reemplazo, movimientos y diferencia. Si requiere Stripe, usar estado pendiente y reservar reemplazo/saldo; confirmar o liberar tras reconciliación, sin transacción SQL abierta durante llamada remota.
5. **Cola de sincronización:** una operación por solicitud y transacción. Un rechazo no revierte operaciones independientes ya aceptadas. Reautorizar antes de servir incluso una respuesta idempotente previa.

## Servicios y funciones nuevas propuestas

| Responsabilidad | Funciones/métodos en español sugeridos |
|---|---|
| Empresa/plan | `registrar_empresa`, `asignar_plan`, `renovar_suscripcion`, `validar_capacidad`, `validar_empresa_recurso` |
| Sincronización | `recibir_operacion`, `verificar_idempotencia`, `procesar_reserva_pendiente`, `procesar_compra_pendiente`, `consultar_resultado` |
| Caja | `abrir_turno`, `asignar_cupos`, `registrar_venta_sin_conexion`, `cerrar_turno`, `conciliar_caja_perdida` |
| Pagos/cambios | `obtener_tasa_vigente`, `convertir_bob_a_usd`, `reconciliar_pago`, `registrar_cambio`, `reservar_saldo`, `consumir_saldo` |
| Reportes/ML | `interpretar_solicitud_reporte`, `validar_filtros_reporte`, `ejecutar_reporte`, `entrenar_pronostico`, `evaluar_pronostico`, `agrupar_productos`, `consultar_analitica` |

Estos nombres son contratos de intención, no afirmación de que hoy existan. Al modificar reservas, ventas, pagos o devoluciones se conservan las reglas de bloqueo de inventario, transacción única por operación, estados por línea, idempotencia y recuperación descritas arriba y en [integracion.md](integracion.md); se comprueba ese comportamiento antes de integrar frontend. Mantener las firmas existentes que sean públicas y colocar la lógica común en servicios reutilizables.

## Reportes, ML e integraciones

- Cuatro reportes tipados con filtros permitidos; Gemini solo transforma texto/voz transcrita a una intención validable. Backend elige consulta parametrizada; nunca ejecuta SQL arbitrario generado por IA. Un resultado común alimenta pantalla y Excel/CSV/PDF, con nueva comprobación de autorización al descargar.
- Generar datos sintéticos con semilla/version y sin mezclarlos con ventas reales. Entrenar modelo supervisado de unidades semanales por producto/sucursal y agrupación no supervisada; dividir cronológicamente la evaluación del primero, comparar con referencia simple y reportar métricas/versiones. Entrenamiento fuera de solicitudes HTTP. Mostrar insuficiencia de datos reales y origen sintético de la evaluación.
- Eventos de negocio y aviso se guardan de forma durable; emisor posterior envía FCM/Web Push y reintenta. Tokens de dispositivos no otorgan permiso. Reconciliar Stripe antes de liberar un compromiso vencido con pago remoto incierto.

## Pruebas de salida del backend

- Dos empresas: acceso propio y ataques por ID, correo, operación repetida, exportación, webhook, job y datos analíticos cruzados.
- Dos compras por última unidad, dos cajas por último cupo, reintentos idénticos y payload modificado.
- Turno de ocho horas, precio congelado, caja perdida, conteo y venta física sincronizada tras baja posterior.
- Tasa vigente/ausente/cambiada, USD aceptado, webhook tardío, saldo mixto y cambio concurrente.
- Métricas de reportes por fecha central y validación reproducible de los dos modelos.

El OpenAPI real se exportará desde la aplicación implementada y se confrontará con [compartido.md](compartido.md); todavía no existe OpenAPI del segundo parcial.
