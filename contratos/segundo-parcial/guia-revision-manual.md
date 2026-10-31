# Plan de aceptación — pendiente de ejecución

Cada CU exige prueba positiva, negativa de permiso/tenant y los escenarios específicos siguientes. Ejecutar W y M por separado cuando aplique. No marcar aprobada por lectura de código ni documentación. Automatizar reglas críticas RNF11; capturas manuales no bastan.

| CU | Escenarios mínimos |
|---|---|
| CU01 | Alta duplicada con misma clave no duplica empresa/administrador.; A no lee ni modifica datos privados de B. |
| CU02 | Básico rechaza tercera activa incluso con peticiones concurrentes.; Gracia/vencimiento no impiden registrar venta offline efectuada válidamente antes. |
| CU03 | Descarga/reinicio sin conexión permite consultar CU16.; Ningún dato de clientes, costos privados o usuarios se filtra en copia pública. |
| CU04 | Dos envíos producen una reserva y un apartado.; Vencida localmente no obtiene 24 h nuevas al sincronizar. |
| CU05 | Pedido cobrado sin stock conserva pago y genera un único reembolso íntegro.; Fallo o reintento no repite cobro, asignación, reembolso ni notificación. |
| CU06 | Dos cajas concurrentes no reciben la misma unidad.; Flutter y PWA aplican mismo negocio y conservan habilitación al reiniciar. |
| CU07 | Reinicio no pierde venta/efectivo/cupo; reenvío no duplica Kardex.; Caja perdida no libera stock por simple timeout. |
| CU08 | Nota sin stock sobrevive reinicio, avisa y se resuelve trazablemente.; Misma unidad no obtiene simultáneamente reemplazo, saldo y reembolso. |
| CU09 | Saldo sin vencimiento y no transferible; aislamiento por empresa.; Reembolso mixto no convierte saldo en dinero. |
| CU10 | Semilla y dataset versionados reproducen evaluación.; Básico no accede y métricas sintéticas no se presentan como precisión real comercial. |
| CU11 | Identidades del mismo modelo se conservan al consultar; entre versiones no prometer igual numeración.; Resultado contiene trazabilidad y no es una respuesta generativa sin entrenamiento. |
| CU12 | Cambio de tasa no altera cobro ya emitido.; Reembolsos parciales nunca exceden centavos capturados restantes. |
| CU13 | Dos empresas pueden tener mismo correo normalizado sin mezclar cuentas.; Vencimiento 8 h oculta datos sin borrar pendientes. |
| CU14 | Usuario de A no administra B aun con ID válido.; Rol revocado no borra efectivo/entrega válidos anteriores. |
| CU15 | Límite activo resiste peticiones simultáneas.; Tarifa se congela en pedido aceptado, no altera entregas anteriores. |
| CU16 | Filtro de color compuesto coincide en W/M y online/offline.; Promoción identifica umbral y no promete precio incondicional para una unidad. |
| CU17 | Venta/transferencia/devolución generan movimientos únicos con origen.; Asignar cupo disminuye libre; sincronizar su venta no descuenta físico dos veces. |
| CU18 | Cancelación repetida no aumenta stock.; Carrera adelanto/expiración tiene una decisión consistente bajo bloqueo. |
| CU19 | Monto recibido - cambio = importe efectivo debido.; Pago mixto no duplica ingresos ni entrega antes de liquidación. |
| CU20 | Misma unidad no se devuelve dos veces ni suma merma y reposición simultánea.; Parcialidad se refiere a unidades/importes elegibles, no retención automática del 50 %. |
| CU21 | Pedido cobrado sin stock se deriva CU27 íntegro sin perder solicitud.; No mezclar carritos ni direcciones entre empresas. |
| CU22 | Webhook repetido/desordenado no repite venta ni pago.; BOB/USD y centavos originales permanecen en reembolsos. |
| CU23 | Saldo emitido/usado no suma ingreso nuevo.; Pedido no cumplido reembolsado no queda como venta neta entregada. |
| CU24 | Cuatro reportes con filtros variables y datos reales, exportados coinciden con pantalla.; Prompt que solicita datos de otra empresa o DROP se rechaza. |
| CU25 | Sincronizar una venta antigua no altera su fecha física.; Una venta no aparece duplicada por reintento. |
| CU26 | Dos workers no duplican liberación.; Carrera cancelación/pago/expiración preserva invariantes. |
| CU27 | Dos solicitudes concurrentes no reembolsan dos veces.; Reembolso no repone stock por sí mismo: devolución física CU20 controla inventario. |

## Escenarios transversales adicionales
- Timeout después de commit, caída antes/después de llamada Stripe, webhook duplicado/desordenado y respuesta perdida.
- Dos pagos/reembolsos simultáneos, gasto concurrente de saldo, última unidad, cierre de caja con cola pendiente y pérdida de dispositivo.
- Pedido pagado sin stock: devolución íntegra por medio original y saldo restaurado; nunca desaparición del comando.
- Cambio fuera de stock: nota7d, aviso, traslado, aceptación48h, pago diferencia y envío con comprobantes.
- Devolución parcial con descuento cantidad: prorrateo y centavos originales; no recalcular promoción histórica.
- PWA instalable y FlutterSQLite reales: reinicio offline y migración local con comandos v1 pendientes.
- Dos tenants, permisos por sucursal, token vencido, privacidad8h y turno8h independientes.
- Reportes4 tipos reales: filtros y exports coincidentes; ML reproducible con métricas y origen sintético identificado.

Registrar para cada ejecución: CP-ID, CU/RNF, commit, entorno, responsable, entrada/pasos, esperado, obtenido, estado y evidencia. No se han ejecutado estas pruebas en esta revisión.
