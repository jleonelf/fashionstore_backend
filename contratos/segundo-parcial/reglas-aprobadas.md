# Reglas aprobadas y criterios de diseño — segundo parcial

Este archivo reúne en el propio repositorio las decisiones funcionales C01–C30 y los criterios técnicos que rigen la implementación. Las preguntas históricas abiertas de la planificación no forman parte del contrato. Leer junto con [casos-de-uso.md](casos-de-uso.md), [integracion.md](integracion.md) e [interfaz.json](interfaz.json). Ninguna función prevista se considera implementada por aparecer aquí. Si una regla y un mensaje técnico parecen incompatibles, documentar el conflicto y coordinar una corrección versionada antes de cambiar el flujo.

## 1. Acuerdos que ya no necesitan confirmación

| ID | Acuerdo | Procedencia |
|---|---|---|
| C01 | PWA cliente limitada a secciones acordadas; administración ordinaria online. Caja web offline es la única excepción posterior | Aclaración del usuario y elección de caja web |
| C02 | Guardar solicitud de compra offline; al sincronizar verificar y apartar stock; avisar que falta pagar; cliente paga explícitamente con Stripe conectado | Primera alternativa aprobada expresamente |
| C03 | Mantener inicialmente 60 minutos de compromiso digital, configurables; contar desde apartado central, sin extender por reintentos/notificaciones | Continuidad del valor existente incluida en la propuesta aceptada |
| C04 | Push en Android para comunicar resultado y siguiente acción | Requisito explícito del usuario |
| C05 | Elegir estrategia de notificación PWA adecuada al navegador | Decisión técnica delegada al asistente; resuelta en sección 2 |
| C06 | Asignación y renovación administrativa de Básico/Profesional, sin cobro SaaS en esta entrega | Respuesta explícita del usuario a D01 |
| C07 | Flutter/móvil exclusivamente cliente; toda la administración y los reportes en web online | Aclaración explícita del usuario; amplía C01 |
| C08 | Reportes web con exportación Excel, CSV y PDF; entrada por texto y voz | Formatos explícitos; “aplica el paso 1” interpretado y comunicado como elección de la propuesta de texto y voz web |
| C09 | Permitir cambios a otros productos y con diferencias de precio | Respuesta explícita a D10; condiciones y liquidación completadas por C10/C11 |
| C10 | Diferencia a favor del cliente como saldo para futuras compras en la misma empresa; diferencia a favor de tienda cobrada antes de entrega mediante caja web o Stripe online | Elección de saldo dentro de la propuesta de liquidación presentada |
| C11 | Cambios hasta 15 días desde entrega, comprobante, prenda sin uso, online en sucursal de origen; plazo configurable por empresa | Condiciones confirmadas expresamente |
| C12 | Planes con fechas de vigencia manuales y 3 días de gracia; después consultas y finalización de pedidos aceptados, bloqueo de nuevas operaciones comerciales; reducción a Básico dentro de 2 sucursales activas, sin borrar datos | El usuario eligió fechas manuales con gracia sobre la política presentada |
| C13 | Saldo personal, sin vencimiento, no transferible ni convertible a dinero; uso parcial online en cualquier sucursal de la misma empresa y en web/móvil; complemento con efectivo en tienda o Stripe | Aprobación expresa de todas las reglas y canales propuestos |
| C14 | PWA offline: catálogo/detalle descargados, carrito y solicitud de compra diferida, selección y solicitud de reserva para visita, pendientes y últimos estados descargados. Invitado solo consulta catálogo; solicitudes requieren cuenta previa y revalidación al sincronizar | Alcance aprobado expresamente; pago, seguimiento actualizado, IA y administración requieren conexión |
| C15 | Vigencia de reservas de visita desde creación local; rechazar solicitudes que llegan vencidas | Elección expresa de la alternativa local, sustituyendo la propuesta de contar desde aceptación central |
| C16 | BOB para catálogo, ventas, saldo y reportes; Stripe Test cobra USD mediante conversión explícita | Elección expresa del usuario; tasa única de plataforma elegida en C20 |
| C17 | Predicción supervisada de unidades vendidas por producto/sucursal y agrupación no supervisada de productos; ambos módulos ML solo Profesional en web administrativa | Elección expresa; reportes generativos siguen exclusivos de Profesional |
| C18 | Venta local de contado sin Internet, con cobro de efectivo y entrega de prendas durante la desconexión; el resto de administración sigue online | Corrección y confirmación expresas del usuario |
| C19 | Caja web instalada en la sucursal como única excepción offline administrativa; cajero/administrador previamente autenticado. Móvil y PWA cliente conservan su alcance | Aprobación explícita de la primera opción de canal |
| C20 | Tasa BOB por USD única y configurable a nivel de plataforma | Aprobación explícita; congelar tasa, vigencia y USD aceptado por operación |
| C21 | Cupos de unidades por variante asignados previamente a cada caja web offline; el servidor los aparta de la disponibilidad general | Aprobación expresa para garantizar venta local dentro del cupo, sin doble asignación |
| C22 | Turno offline de caja de 8 horas desde última autorización online; al vencer se bloquean nuevas ventas, pero cupos y pendientes permanecen hasta sincronizar/cerrar | Elección expresa del usuario frente a 24 horas |
| C23 | Caja o almacenamiento perdido: cupos retenidos hasta conteo físico y cierre con ajuste auditado por encargado | Aprobación expresa del proceso de recuperación |
| C24 | Ventas físicamente cobradas y entregadas dentro de cupo/autorización vigente se registran al sincronizar aunque empleado o plan hayan vencido después; se marcan para revisión administrativa | Aprobación expresa; las nuevas ventas offline se bloquean |
| C25 | Precios BOB y promociones expresamente autorizadas al abrir el turno de caja; respetar esos importes en ventas dentro del cupo y de las 8 h aunque cambie el precio online | Aprobación expresa del usuario |
| C26 | Cambio de prenda: reconocer importe neto pagado por unidad devuelta, prorrateando descuentos y saldo usado para trazabilidad; excluir entrega. Reemplazo al precio vigente mostrado y aceptado | Aprobación expresa del usuario |
| C27 | Reportes por defecto según fecha de aceptación central; fecha física local visible y filtrable. Mostrar brutas, descuentos, cambios/devoluciones y netas por separado; saldo emitido/usado no es ingreso nuevo | Aprobación expresa del usuario |
| C28 | Tras los 3 días de gracia, permitir online posventa dentro de plazo, reclamos y cierre de pedidos/compromisos aceptados; bloquear nuevas ventas, reservas y turnos de caja. No desactivar sucursales con pedidos o cupos pendientes | Aprobación expresa del usuario |
| C29 | Cliente: catálogo público offline; carrito, reservas y pendientes privados visibles solo hasta 8 horas desde último login online. Al vencer o cerrar sesión se ocultan, conservan aislados y requieren reautenticación; backend revalida al sincronizar | El usuario eligió 8 horas frente a la propuesta de 24 |
| C30 | Flutter es exclusivamente cliente. Las ventas de contado son presenciales en caja web; se documenta que el requisito académico de contado offline móvil no se cubre | Confirmación expresa del usuario; no ampliar Flutter a personal |

Del flujo aprobado se derivan: ausencia de cobro durante la desconexión; validación central de precios y disponibilidad; aceptación de un importe cambiado antes de continuar; pedido completo desde una sucursal conforme al checkout existente; intento de compra estable e idempotente; webhook verificado para completar la compra. No guardar datos de tarjeta en persistencia offline. Los errores de red se reconcilian; no se interpretan como pago rechazado.

La reserva de prendas para visita, el compromiso de compra digital y la venta local de contado son procesos distintos. La reserva vence a las 24 horas desde creación local; un adelanto confirmado online dentro de la vigencia permite extender a 72 horas desde esa misma creación. Los 60 minutos del compromiso digital se cuentan desde el apartado central. En caja web offline, efectivo y entrega ocurren localmente contra un cupo asignado previamente; el registro central ocurre al sincronizar. No trasladar el origen de tiempo ni estados de pago de un flujo al otro.

## 2. Notificaciones: diseño elegido

### Android

Integrar Firebase Cloud Messaging en Flutter para push reales originados en backend. Mantener una bandeja propia como historial y recuperación. La notificación abre el pedido de su empresa/propietario y vuelve a consultar su estado; nunca dispara el pago por tocarla.

Solicitar permiso en contexto y manejar recepción con app abierta, en segundo plano y al abrir desde una notificación. En Android 13 o posterior se requiere permiso de notificaciones. Si el usuario lo deniega, mostrar el estado en la app; esa contingencia no sustituye la prueba de push real con permisos concedidos. la documentación oficial de Firebase para Flutter.

El envío de la solicitud offline y la recepción de push son trabajos distintos. Planificar sincronización Android con trabajo persistente condicionado a red, reintentos y recuperación al abrir, reutilizando el mismo sincronizador. WorkManager ofrece restricciones de red y reintentos; su ejecución depende del sistema y no debe prometerse instantaneidad. Verificar compatibilidad del adaptador Flutter antes de fijar dependencias. la documentación oficial de Android sobre trabajo persistente.

### PWA

Adoptar tres mecanismos coordinados:

1. Bandeja persistente de avisos dentro del área cliente, alimentada por el backend y recuperada al abrir/reconectar.
2. Aviso visible dentro de la app al recibir un resultado, sin depender de permisos de notificación del sistema.
3. Web Push mediante Push API/service worker en navegadores compatibles, con consentimiento. Usar la integración de la PWA para recibir push, evitando registrar workers competidores con el mismo ámbito.

La Push API permite recibir mensajes del servidor aunque la PWA no esté ejecutándose, sujeto al entorno y permisos. Se conserva la bandeja cuando no hay soporte o permiso. la documentación de navegador sobre operación offline y en segundo plano.

Sincronizar al abrir, volver al primer plano y recuperar comunicación, con reintento manual. Background Sync es una mejora según soporte; el flujo no depende exclusivamente de él. El backend no puede validar una solicitud aún no enviada desde el dispositivo. Web Push tampoco transporta esa solicitud al servidor por sí solo.

### Backend compartido y eventos

Un único servicio de notificaciones con dos adaptadores: FCM para Android y Web Push para navegador. Evento y resultado se guardan junto con el cambio de negocio; un proceso posterior envía y reintenta sin duplicar avisos. PostgreSQL puede almacenar los pendientes de envío en esta entrega, sin introducir infraestructura adicional por defecto.

Registrar destinatario, empresa, dispositivo/suscripción, tipo de evento, recurso, versión de estado, fechas e intentos. Administrar renovación de tokens, bajas del proveedor y desvinculación al logout. Ningún token push concede permisos de negocio. Evitar datos sensibles en pantalla bloqueada, secretos de pago y enlaces que eludan autenticación.

Eventos iniciales: stock apartado/falta pago; productos no disponibles; importe que requiere revisión; pago confirmado; pago rechazado; apartado vencido. Un pago incierto se muestra como en verificación, sin aviso falso de rechazo. Deduplicar por recurso/evento/versión y ajustar vigencia de avisos de pago a la del apartado; un aviso tardío no renueva el stock.

Dependencias de implementación: proyecto Firebase, configuración de la app Android y credenciales de envío solo en servidor; claves Web Push en backend y suscripción del navegador; Android físico con servicios compatibles para aceptación. No se crearon recursos externos ni se inspeccionaron credenciales en esta planificación.

## Criterios técnicos que pasan a los contratos

| Tema | Criterio de diseño |
|---|---|
| Identidad multitenant | Una cuenta pertenece a una empresa; el mismo correo puede existir en empresas distintas. El login selecciona empresa. El backend obtiene `tenant_id` de la identidad validada y no de un campo libre del cliente. Datos, claves idempotentes, trabajos, artefactos ML, notificaciones y exportaciones se aíslan por empresa. |
| Planes | Fechas manuales introducidas en hora de Bolivia, almacenadas en UTC; intervalos con inicio inclusivo y fin exclusivo. Gracia de 72 horas continuas desde fin de vigencia. Al bajar a Básico, validar hasta dos sucursales activas y compromisos pendientes antes de aplicar. No hay cobro SaaS. |
| Compra digital | Solicitud offline con UUID estable. En sincronización se valida empresa, actor, plan, stock y precio. Si el total cambió, se pide aceptación expresa antes de apartar; sin aceptación no se cobra. Apartado atómico de pedido completo en una sucursal durante 60 minutos desde aceptación central; reintentar o recibir una notificación no amplía el plazo. Pago explícito online; estados de Stripe inciertos se reconcilian antes de liberar stock. |
| Reserva offline | Creación local inicia 24 horas, o 72 horas desde la misma creación si el adelanto quedó confirmado online antes de vencer. Se conserva fecha local declarada, referencia de hora del servidor obtenida previamente, fecha de recepción y secuencia. Ante referencias incoherentes o imposibles de validar, dejar en conflicto sin apartar stock automáticamente. No afirmar que el servidor puede probar el instante físico de creación en un dispositivo desconectado. |
| Caja offline | Cupos por variante, caja, sucursal, empresa y turno, separados del stock libre. Una venta, sus líneas, efectivo, entrega y descuento local de cupo se guardan en una sola transacción local. Turno de ocho horas; al vencer no se crean ventas nuevas. Precios/promociones son la versión autorizada al abrir. Se sincronizan ventas antes de cerrar y devolver cupos no usados. Pérdida de almacenamiento requiere conteo y cierre auditado. |
| Sincronización | Contrato común de comandos/resultados para IndexedDB y SQLite: versión de esquema, UUID de operación, actor/empresa, marca local, tipo, payload, estado y revisión del servidor. Misma clave y mismo contenido devuelve el resultado persistido; misma clave con contenido distinto es conflicto. Cada operación del lote tiene transacción y resultado propios. Revalidar autorización antes de devolver resultados anteriores. Los clientes consultan resultados después de pérdida de respuesta. |
| Tasa y dinero | Una tasa global `BOB por 1 USD`, administrada por superadministración, con inicio y fin de vigencia explícitos y auditoría. Importes comerciales BOB y cobro Stripe USD con dos decimales; calcular con `Decimal` y redondeo `ROUND_HALF_UP`. Congelar BOB, tasa/version, fecha y USD mostrado/aceptado al crear la intención; reintento y webhook no recalculan. Tasa inexistente o vencida impide preparar Stripe. El importe final en USD se muestra antes de confirmar. |
| Cambio y saldo | Valorar cada unidad por precio neto de descuentos de su línea; el saldo usado es medio de pago, no descuento adicional. Repartir centavos de descuento de forma determinista por orden estable de líneas/unidades y conservar exactamente el total. Excluir entrega. Diferencia favorable al cliente: saldo personal en la misma empresa; desfavorable: cobrar antes de entregar. Reservar tanto reemplazo como saldo aplicado mientras se resuelve Stripe; liberar al cancelar sin duplicar efectos. |
| Reportes | Cuatro tipos iniciales: ventas por sucursal/periodo, productos más/menos vendidos, evolución semanal y ventas/ingresos por categoría. Filtros variables y datos reales, con fecha de aceptación central por defecto. Usar un mismo resultado tipado para pantalla, Excel, CSV y PDF; incluir brutas, descuentos, cambios/devoluciones y netas por separado. La voz se transcribe en web online y sigue la misma validación que el texto. |
| ML | Pronóstico de unidades **de la próxima semana** por producto/sucursal y agrupación de productos por comportamiento. Generador sintético con semilla/versión separado de ventas reales. Entrenamiento fuera de solicitudes HTTP; preprocesado y artefactos versionados, evaluación temporal del pronóstico frente a referencia simple y métricas de agrupación. Dashboard solo Profesional con versión, periodo, métricas y advertencia cuando el modelo solo fue evaluado con datos sintéticos. Si falta historial suficiente, mostrar datos insuficientes y no inventar predicciones confiables. Inferencia y cualquier reentrenamiento sobre datos reales se aíslan por empresa. |
| Límites de uso | Los planes solo imponen los límites comerciales acordados de sucursales y acceso Profesional a analítica. No inventar cuotas de productos, empleados o clientes. Aplicar límites técnicos de frecuencia, tamaño de consulta y costo de proveedores de forma configurable y auditable; agotarlos produce respuesta recuperable, no una baja de plan. |
| Acceso tras bajar de plan | Conservar artefactos/resultados históricos para auditoría, pero bloquear endpoints y vistas de reportes generativos y ML mientras la empresa no tenga Profesional vigente o en gracia. Posventa y cierre de compromisos ya aceptados siguen las reglas acordadas. |

## Dependencias de configuración y evidencia

No son decisiones comerciales abiertas; deben prepararse y verificarse durante implementación:

1. Credenciales de Gemini para reportes, Firebase/FCM para Android, Web Push para PWA, Stripe Test y Decart existente. Las claves residen solo en servidor o en la configuración pública permitida por cada proveedor; ningún secreto permanente en cliente.
2. Valor inicial y vencimiento de la tasa BOB/USD antes de habilitar pagos Stripe; no se fija aquí una cotización ficticia ni se altera el historial del primer parcial.
3. Pruebas de compatibilidad y despliegue, migración en base de prueba, aislamiento de dos empresas, concurrencia de stock/cupos/saldo, recuperación de pagos y dispositivos, exportaciones, calidad de modelos y requisitos de ICONIX/UML.
