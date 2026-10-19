# Casos de uso CU01–CU37 — copia funcional autónoma

Estas 37 fichas registran descripción, actores, precondiciones, flujos y poscondiciones. CU01–CU25 documentan la línea base con las adaptaciones previstas; CU26–CU37 describen capacidades nuevas. Son especificaciones de análisis y **no prueban implementación**. Revisar el impacto por caso en [trazabilidad-cu.md](trazabilidad-cu.md), las reglas aprobadas en [reglas-aprobadas.md](reglas-aprobadas.md) y la interfaz propuesta en [interfaz.json](interfaz.json). Si aparece una discrepancia, registrarla antes de modificar el comportamiento.

Autor de las fichas: **Equipo FashionStore**. Fecha de redacción: **18/10/2026**.

## Línea base CU01–CU25

## CU01 — Registrar cliente e iniciar sesión

<table><tbody>
<tr><th>Nombre:</th><td>Registrar cliente e iniciar sesión</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Registrar cuenta de cliente e iniciar sesión en el ámbito de una empresa.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">El cliente accede a registro o ingreso de la empresa seleccionada.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente introduce sus datos o credenciales y selecciona la empresa. Así, el sistema sabe si debe crear una cuenta nueva o validar una ya existente.</li><li>El sistema valida la información.</li><li>Registra al cliente o autentica la cuenta.</li><li>Entrega la sesión con su rol y empresa.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si los datos son inválidos, el correo ya pertenece a esa empresa o la cuenta está inactiva, se informa la causa y no se crea sesión.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Cliente registrado o sesión iniciada solo para la empresa autorizada.</td></tr>
</tbody></table>

## CU02 — Gestionar usuarios y roles

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar usuarios y roles</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Crear, consultar, asignar rol y desactivar usuarios de la empresa.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autenticado en su empresa.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador abre usuarios.</li><li>Consulta o introduce datos y rol. La selección puede corresponder a consultar, crear, cambiar rol o desactivar, según la tarea del administrador.</li><li>El sistema valida permiso y pertenencia.</li><li>Registra el cambio y muestra el estado actualizado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si rol, datos o recurso no corresponden a su empresa, se rechaza sin alterar usuarios.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Usuarios y roles de la empresa quedan actualizados y auditables.</td></tr>
</tbody></table>

## CU03 — Gestionar ciudades, sucursales y tarifas

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar ciudades, sucursales y tarifas</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Administrar ubicaciones y tarifas de delivery dentro del límite de sucursales del plan.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autenticado; empresa y plan habilitados para la operación.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador consulta ciudades y sucursales.</li><li>Introduce o modifica sucursal/tarifa. El formulario deja claro si se está trabajando sobre una ciudad, una sucursal o una tarifa.</li><li>El sistema valida pertenencia y límite del plan.</li><li>Guarda y muestra la configuración.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se excede el límite de sucursales activas o hay compromisos que impiden desactivar una, se rechaza el cambio y se indica la causa.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Sucursal o tarifa queda registrada sin afectar datos de otra empresa.</td></tr>
</tbody></table>

## CU04 — Gestionar proveedores y lotes de recepción con costos

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar proveedores y lotes de recepción con costos</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Registrar proveedores y recepciones valoradas de prendas.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de Almacén o Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Personal autorizado y sucursal/empresa identificadas.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor consulta proveedor.</li><li>Registra lote, variantes, cantidades y costos. El lote identifica la fecha, sucursal de destino y documento de referencia de la recepción.</li><li>El sistema valida datos y referencias.</li><li>Actualiza inventario, costos y Kardex.</li><li>Muestra el lote.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si cantidad, costo o proveedor no son válidos o pertenecen a otra empresa, no se confirma la recepción.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Lote y movimientos de entrada quedan consistentes y auditables.</td></tr>
</tbody></table>

## CU05 — Gestionar productos, variantes y maestros

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar productos, variantes y maestros</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Mantener catálogo administrable, variantes y maestros relacionados.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autenticado en su empresa.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador consulta maestros.</li><li>Crea o edita producto.</li><li>Añade variantes de talla/color. Cada variante queda vinculada al producto y conserva su identificador comercial para inventario y ventas.</li><li>El sistema valida referencias y SKU.</li><li>Guarda y presenta catálogo actualizado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si SKU o combinación está duplicada dentro de la empresa, se solicita corrección sin crear variante.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Producto y variantes quedan vinculados a la empresa.</td></tr>
</tbody></table>

## CU06 — Consultar catálogo, filtrar y ver disponibilidad

<table><tbody>
<tr><th>Nombre:</th><td>Consultar catálogo, filtrar y ver disponibilidad</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Buscar prendas y consultar disponibilidad por variante y sucursal.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Existe catálogo publicado; si está offline debe haberse descargado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente abre catálogo.</li><li>Aplica filtros.</li><li>El sistema lista productos de la empresa. El cliente puede ajustar los criterios y volver a consultar sin perder el contexto de navegación.</li><li>Muestra detalle, variantes y disponibilidad conocida.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Sin conexión se muestra solo el catálogo descargado y su fecha; la disponibilidad local se indica como dato conocido, sin garantizar stock.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">No cambia inventario; la consulta queda acotada a la empresa.</td></tr>
</tbody></table>

## CU07 — Consultar Kardex, existencias y valorización

<table><tbody>
<tr><th>Nombre:</th><td>Consultar Kardex, existencias y valorización</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Consultar movimientos, cantidades y costos de inventario.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de Sucursal o Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Personal autenticado con permiso sobre sucursal/empresa.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor selecciona sucursal y filtro.</li><li>El sistema valida ámbito.</li><li>Obtiene existencias y Kardex. Los filtros permiten acotar la consulta a una variante o movimiento de interés.</li><li>Calcula o consulta valorización.</li><li>Presenta resultados.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se solicita una sucursal ajena o sin permiso, se rechaza sin revelar movimientos.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">El inventario no cambia por la consulta.</td></tr>
</tbody></table>

## CU08 — Crear, consultar y cancelar reserva local

<table><tbody>
<tr><th>Nombre:</th><td>Crear, consultar y cancelar reserva local</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Crear y consultar reserva propia o cancelar una vigente.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado; sucursal y variantes disponibles.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente selecciona variantes, sucursal y visita.</li><li>El sistema valida identidad, plazo y stock.</li><li>Acepta la reserva y registra inventario/Kardex. El resumen permite al cliente corregir cantidades o sucursal antes de confirmar.</li><li>Muestra código y vencimiento.</li><li>El cliente puede consultar o cancelar según estado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se crea offline, primero queda solicitud local y CU29 decide aceptación; si falta stock, vence el plazo o no pertenece al cliente, se rechaza sin apartado. La cancelación válida libera inventario.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Reserva y movimientos quedan consistentes; ninguna solicitud local se presenta como reserva central antes de aceptación.</td></tr>
</tbody></table>

## CU09 — Solicitar, aprobar y recibir traslados

<table><tbody>
<tr><th>Nombre:</th><td>Solicitar, aprobar y recibir traslados</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Gestionar traslado entre sucursales asociado a reserva.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente; Encargado de Sucursal.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Existe necesidad de traslado y personal autorizado para aprobar/recibir.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente solicita prendas en sucursal destino.</li><li>El sistema identifica necesidad de traslado.</li><li>El encargado aprueba o rechaza. La aprobación compromete las unidades en origen para evitar venderlas durante el traslado.</li><li>Si aprueba, se despacha y recibe.</li><li>El inventario/Kardex refleja cada etapa.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si no hay stock en origen o se rechaza el traslado, la línea no pasa a preparada y el cliente recibe el resultado.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Estados de traslado y cantidades por sucursal quedan consistentes.</td></tr>
</tbody></table>

## CU10 — Preparar y atender reserva

<table><tbody>
<tr><th>Nombre:</th><td>Preparar y atender reserva</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Separar prendas y atender al cliente que visita la sucursal.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de Sucursal.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Reserva aceptada de la sucursal; encargado autenticado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El encargado abre panel de reservas.</li><li>Selecciona una reserva.</li><li>Prepara las prendas y actualiza estado. La preparación se registra antes de entregar las prendas al cliente.</li><li>Atiende al cliente y registra el resultado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si la reserva venció, fue cancelada o no pertenece a la sucursal, no se prepara ni entrega como vigente.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Reserva conserva su estado de atención y trazabilidad.</td></tr>
</tbody></table>

## CU11 — Registrar venta presencial y pago en caja

<table><tbody>
<tr><th>Nombre:</th><td>Registrar venta presencial y pago en caja</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Cobrar venta presencial y registrar salida de inventario.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cajero.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cajero autorizado; prendas o reserva disponibles.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cajero selecciona prendas o reserva.</li><li>El sistema calcula total y adelanto aplicable.</li><li>El cajero registra efectivo/pago. El total presentado incluye los conceptos vigentes y el saldo de reserva que corresponda.</li><li>El sistema confirma venta, líneas, pago y Kardex.</li><li>Emite comprobante.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si falta stock o el pago no queda confirmado, no se completa la venta. Para venta sin Internet se usa el flujo específico CU31–CU32.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Venta pagada e inventario actualizado una vez.</td></tr>
</tbody></table>

## CU12 — Registrar devolución y merma

<table><tbody>
<tr><th>Nombre:</th><td>Registrar devolución y merma</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Registrar retorno de prendas o merma de inventario.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de Sucursal.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Encargado autorizado; venta o inventario de su ámbito.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El encargado selecciona venta/prenda o existencia.</li><li>Indica cantidad y motivo.</li><li>El sistema valida cantidades y permisos. El sistema conserva el motivo indicado para explicar por qué cambia la existencia.</li><li>Registra movimiento de devolución o merma.</li><li>Muestra resultado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si cantidad supera lo permitido o recurso pertenece a otra empresa, se rechaza. El cambio por otra prenda se trata en CU33.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Inventario y Kardex reflejan la operación aprobada.</td></tr>
</tbody></table>

## CU13 — Consultar historial de compras

<table><tbody>
<tr><th>Nombre:</th><td>Consultar historial de compras</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Consultar ventas y detalles propios.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado en la empresa correspondiente.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente abre historial.</li><li>El sistema valida identidad.</li><li>Lista sus ventas. El listado distingue las compras por su fecha e información de estado disponible.</li><li>El cliente abre detalle y estado de pago/entrega.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si intenta abrir compra ajena o de otra empresa, se deniega sin revelar datos.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">No hay cambios comerciales; se muestra solo historial propio.</td></tr>
</tbody></table>

## CU14 — Gestionar carrito y confirmar compra digital

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar carrito y confirmar compra digital</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Preparar compra web o móvil y confirmar un pedido digital.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado para confirmar; catálogo y sucursal disponibles.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente añade variantes al carrito.</li><li>Revisa cantidades y entrega/recojo.</li><li>Confirma. El resumen final permite detectar errores en cantidades o modalidad antes de confirmar.</li><li>El sistema valida precio y stock.</li><li>Aparta unidades y crea pedido pendiente de pago.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se preparó offline, se guarda solicitud y CU30 valida al reconectar. Si falta stock o cambia precio, se informa antes del pago.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Pedido pendiente de pago o solicitud local, claramente distinguidos.</td></tr>
</tbody></table>

## CU15 — Procesar pago digital con Stripe Test

<table><tbody>
<tr><th>Nombre:</th><td>Procesar pago digital con Stripe Test</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Completar pago digital tras aceptación explícita del monto USD.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente; Pasarela Stripe de Prueba.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Pedido con stock apartado vigente; cliente online; tasa BOB/USD vigente.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente revisa BOB, tasa y USD.</li><li>Acepta e inicia Stripe Test.</li><li>La pasarela informa resultado. La aplicación muestra la referencia del pedido para que el cliente identifique el cobro.</li><li>El backend verifica evento, importe e intención.</li><li>Confirma venta y notifica.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si tasa falta, pago falla, queda incierto o llega tarde, se muestra estado recuperable y se reconcilia antes de liberar stock; no se confirma por retorno de navegador.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Venta pagada solo tras confirmación confiable, con moneda y tasa históricas.</td></tr>
</tbody></table>

## CU16 — Configurar y simular delivery por anillos

<table><tbody>
<tr><th>Nombre:</th><td>Configurar y simular delivery por anillos</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Calcular envío y dar seguimiento interno a una entrega simulada.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador; Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Tarifas de delivery configuradas; dirección en cobertura simulada.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador configura tarifas.</li><li>El cliente elige dirección. La dirección seleccionada se conserva junto con el pedido para aplicar la tarifa correcta.</li><li>El sistema calcula anillo y costo.</li><li>El cliente confirma delivery.</li><li>El sistema muestra estado posterior.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si dirección queda fuera de cobertura o no existe tarifa válida, se solicita otra opción antes de confirmar.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Pedido conserva costo y modalidad de entrega acordados.</td></tr>
</tbody></table>

## CU17 — Usar probador virtual móvil

<table><tbody>
<tr><th>Nombre:</th><td>Usar probador virtual móvil</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Visualizar transformación remota de video para una prenda.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente en Flutter con prenda elegida, permisos y conexión necesarios.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente elige prenda y abre probador.</li><li>El backend autoriza sesión y emite token temporal.</li><li>El SDK Android oficial establece sesión Decart Lucy 2.5. El permiso temporal limita la sesión al cliente y a la prenda seleccionada.</li><li>El cliente ve el resultado y cierra sesión.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si faltan permisos, conectividad o autorización, se informa y no se expone la clave permanente ni se inicia sesión no autorizada.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Sesión temporal finalizada o activa solo para cliente/empresa autorizados.</td></tr>
</tbody></table>

## CU18 — Generar sugerencias IA para cliente

<table><tbody>
<tr><th>Nombre:</th><td>Generar sugerencias IA para cliente</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Obtener sugerencias de prendas relacionadas con preferencias o catálogo.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente; Servicio IA.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado; contexto permitido disponible online.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente solicita sugerencias.</li><li>El backend reúne contexto autorizado.</li><li>Consulta al servicio IA. La solicitud se limita al contexto necesario para que la recomendación corresponda al catálogo de la empresa.</li><li>Valida respuesta contra catálogo.</li><li>Muestra opciones.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si el servicio falla o propone artículos inválidos, se informa o usa respuesta segura sin exponer otros tenants.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">No modifica compras; recomendaciones quedan acotadas a la empresa.</td></tr>
</tbody></table>

## CU19 — Consultar dashboard e indicadores

<table><tbody>
<tr><th>Nombre:</th><td>Consultar dashboard e indicadores</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Consultar métricas operativas de la empresa.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autenticado con permiso para los indicadores solicitados.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador abre dashboard.</li><li>El backend valida empresa/plan.</li><li>Consulta ventas e inventario reales. Los indicadores aplican el mismo periodo y sucursal elegidos por el administrador.</li><li>Calcula indicadores.</li><li>Presenta tablas o gráficos.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se solicitan indicadores ML exclusivos de Profesional con plan Básico, se bloquea ese módulo; los indicadores convencionales permitidos siguen disponibles.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Consulta sin alterar datos y sin mezclar empresas.</td></tr>
</tbody></table>

## CU20 — Buscar prendas por comando de voz

<table><tbody>
<tr><th>Nombre:</th><td>Buscar prendas por comando de voz</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Buscar catálogo a partir de voz interpretada.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente; Servicio IA.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente en canal compatible con micrófono y permiso; catálogo disponible.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente dicta la búsqueda.</li><li>El sistema transcribe e interpreta los filtros.</li><li>Valida los filtros permitidos. La interpretación se convierte en filtros revisables y no en una consulta libre a la base de datos.</li><li>Consulta el catálogo y presenta prendas coincidentes.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si no hay permiso de micrófono o no se entiende el comando, se solicita reformular o buscar por texto.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Solo consulta productos autorizados; no altera inventario.</td></tr>
</tbody></table>

## CU21 — Solicitar reporte generativo por voz o texto

<table><tbody>
<tr><th>Nombre:</th><td>Solicitar reporte generativo por voz o texto</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Crear reporte variable a partir de petición en lenguaje natural.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador; Servicio IA.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador online con plan Profesional y permiso de reportes.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador escribe o dicta petición.</li><li>El sistema transcribe si procede.</li><li>Gemini interpreta intención y filtros.</li><li>FastAPI valida tipo, tenant y parámetros. Los filtros quedan visibles para que el administrador compruebe qué periodo y alcance generaron el resultado.</li><li>Ejecuta consulta controlada y muestra tabla/gráfico.</li><li>Permite Excel, CSV y PDF.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si petición es ambigua, no soportada o excede permiso, se pide precisión o se rechaza sin ejecutar SQL arbitrario.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Reporte y exportación reflejan el mismo resultado autorizado de datos reales.</td></tr>
</tbody></table>

## CU22 — Gestionar promociones

<table><tbody>
<tr><th>Nombre:</th><td>Gestionar promociones</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Crear, actualizar y consultar promociones.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autorizado; productos/variantes de su empresa disponibles.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador define promoción y vigencia.</li><li>El sistema valida condiciones y referencias.</li><li>Guarda promoción. La vista previa permite revisar vigencia y productos alcanzados antes de activar la regla.</li><li>Muestra vigentes aplicables.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si condición se solapa de modo inválido o referencia otro tenant, se rechaza. Los turnos de caja abiertos conservan su versión autorizada.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Promoción versionada para operaciones posteriores, sin revalorizar ventas previas.</td></tr>
</tbody></table>

## CU23 — Consultar ventas de la sucursal

<table><tbody>
<tr><th>Nombre:</th><td>Consultar ventas de la sucursal</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Revisar ventas registradas de una sucursal.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de Sucursal o Administrador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Personal autenticado con acceso a la sucursal.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor elige periodo/sucursal.</li><li>El backend valida ámbito.</li><li>Lista ventas aceptadas. El listado incluye las referencias necesarias para abrir el detalle de una venta autorizada.</li><li>Muestra detalle y totales.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si se consulta otra sucursal sin permiso, se rechaza. Venta offline aún no aceptada centralmente no figura como confirmada.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Consulta sin cambios; datos limitados a sucursal/empresa.</td></tr>
</tbody></table>

## CU24 — Expirar reservas automáticamente

<table><tbody>
<tr><th>Nombre:</th><td>Expirar reservas automáticamente</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Liberar stock de reservas vencidas de forma idempotente.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Temporizador.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Existen reservas vigentes con fecha de vencimiento; proceso autorizado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El proceso identifica reservas vencidas.</li><li>Bloquea registros.</li><li>Actualiza estado y libera cantidades reservadas. La comprobación evita liberar existencias asociadas a una operación que todavía debe resolverse.</li><li>Registra Kardex.</li><li>Conserva resultado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si una reserva ya se vendió, canceló o expiró, no se libera dos veces; si hay adelanto o pago en curso, se sigue su regla de conciliación.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Reservas vencidas y stock consistentes, con trazabilidad.</td></tr>
</tbody></table>

## CU25 — Consultar decisiones IA para inventario

<table><tbody>
<tr><th>Nombre:</th><td>Consultar decisiones IA para inventario</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Solicitar sugerencias interpretativas de inventario.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador; Servicio IA.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador autorizado; datos de inventario de su empresa disponibles online.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El administrador solicita análisis.</li><li>El backend prepara métricas autorizadas.</li><li>Consulta servicio IA. El sistema presenta la sugerencia como apoyo de decisión para que el administrador la evalúe.</li><li>Valida y muestra sugerencias.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li>Si faltan datos o IA falla, se informa; ninguna sugerencia ejecuta automáticamente compras o movimientos.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Recomendación consultiva sin alterar inventario.</td></tr>
</tbody></table>

## Capacidades nuevas CU26–CU37

## CU26 — Registrar empresa contratante

<table><tbody>
<tr><th>Nombre:</th><td>Registrar empresa contratante</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr>
<tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite dar de alta una empresa independiente y su administrador inicial dentro de la plataforma compartida.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador de plataforma.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Administrador de plataforma autenticado y autorizado; datos de empresa y administrador disponibles.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor abre el registro de empresas e introduce los datos solicitados y el administrador inicial.</li><li>El sistema valida los datos, la unicidad de los identificadores de empresa y los permisos del actor. El formulario identifica qué datos pertenecen a la empresa y cuáles al administrador inicial.</li><li>El sistema registra la empresa y asocia al administrador a esa empresa en una operación consistente.</li><li>El sistema presenta la empresa creada y su estado de plan pendiente de asignación.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si el identificador de empresa ya existe o faltan datos válidos, el sistema indica qué corregir y no registra la empresa.</li><li value="3">Si falla el alta del administrador, se revierte el alta incompleta y se informa el resultado.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Empresa y administrador inicial quedan asociados; no puede operar comercialmente hasta tener un plan vigente según contrato.</td></tr>
</tbody></table>

## CU27 — Administrar suscripción de empresa

<table><tbody>
<tr><th>Nombre:</th><td>Administrar suscripción de empresa</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite asignar, renovar o cambiar administrativamente el plan Básico o Profesional y sus fechas de vigencia, sin cobro SaaS.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador de plataforma.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Empresa registrada; actor autenticado; fechas y plan propuestos.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor selecciona la empresa y registra plan, inicio y fin de vigencia.</li><li>El sistema valida fechas, cambios previos y límite de sucursales activas. El resumen presenta límite de sucursales y funciones habilitadas antes de confirmar.</li><li>El actor confirma la asignación, renovación o cambio.</li><li>El sistema guarda suscripción y auditoría; calcula estado vigente, gracia o vencido.</li><li>El sistema muestra capacidades y fechas efectivas a la empresa.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si una reducción a Básico excede dos sucursales activas o intenta cerrar una con compromisos pendientes, el sistema rechaza el cambio e indica la regularización necesaria.</li><li value="4">Si vence el plan y transcurren tres días de gracia, se bloquean nuevas ventas, reservas y turnos; continúan consultas y posventa/compromisos aceptados conforme a las reglas aprobadas.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">La versión de suscripción y su auditoría quedan guardadas; ningún ingreso SaaS ficticio se registra.</td></tr>
</tbody></table>

## CU28 — Descargar catálogo para consulta offline

<table><tbody>
<tr><th>Nombre:</th><td>Descargar catálogo para consulta offline</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite consultar en PWA o Flutter fichas de productos, variantes y última disponibilidad descargada.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Existe catálogo publicado de la empresa; el dispositivo tuvo conexión para descargarlo antes de operar offline.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente abre el catálogo de una empresa mientras tiene conexión.</li><li>El sistema entrega productos, variantes y existencias conocidas del ámbito consultado, con versión y fecha de actualización. La descarga se limita a los datos públicos y al catálogo autorizado para esa empresa.</li><li>La aplicación guarda el subconjunto autorizado en IndexedDB o SQLite.</li><li>Sin conexión, el cliente abre ese catálogo y ve claramente cuándo se actualizó por última vez.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si falla la descarga, la aplicación conserva la copia previa e indica que sus cantidades podrían estar desactualizadas.</li><li value="4">Si un producto no se descargó antes, se informa que su detalle requiere conexión; el stock conocido no se presenta como stock garantizado.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">La copia local consultable queda asociada a su empresa y versión; no modifica inventario central.</td></tr>
</tbody></table>

## CU29 — Sincronizar solicitud de reserva propia

<table><tbody>
<tr><th>Nombre:</th><td>Sincronizar solicitud de reserva propia</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite crear sin conexión una solicitud de visita y obtener su aceptación o rechazo central al recuperar Internet.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado previamente; sesión local privada dentro de 8 h; catálogo/sucursal conocidos; operación propia aún no enviada.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente elige prendas, sucursal y visita; la aplicación guarda solicitud, UUID y hora local.</li><li>La aplicación muestra «pendiente de sincronización» sin afirmar que el stock está reservado.</li><li>Al reconectar y reautenticarse si corresponde, la aplicación envía la misma solicitud. La operación mantiene su identificador y hora originales durante cada reintento.</li><li>El backend valida identidad, empresa, fecha de creación coherente, plazo vigente, sucursal, visita y stock.</li><li>El backend aparta las unidades en una transacción, guarda el resultado y devuelve reserva y vencimiento.</li><li>La aplicación muestra el resultado confirmado y lo conserva tras reinicio.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="3">Si sigue sin conexión o vence la sesión, el pendiente queda aislado y se reintenta solo tras reautenticación.</li><li value="4">Si pasaron 24 h desde creación local, falta stock o la referencia temporal es incoherente, el backend registra rechazo o conflicto recuperable sin apartar unidades.</li><li value="5">Si se pierde la respuesta, repetir el mismo UUID devuelve el resultado anterior sin duplicar la reserva.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Solicitud y resultado durables; reserva e inventario solo cambian si el servidor acepta. Adelanto posterior confirmado online puede extender la vigencia hasta 72 h desde la creación original.</td></tr>
</tbody></table>

## CU30 — Sincronizar solicitud de compra digital

<table><tbody>
<tr><th>Nombre:</th><td>Sincronizar solicitud de compra digital</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite preparar una compra sin conexión y recibir una oferta de pago online solo después de verificar y apartar stock central.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Cliente autenticado previamente, sesión local privada válida, artículos seleccionados; ningún dato de tarjeta guardado localmente.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente guarda el pedido provisional en PWA o Flutter durante la desconexión.</li><li>La aplicación muestra «solicitud guardada, sin stock ni pago confirmados».</li><li>Al reconectar, envía la operación estable tras revalidar identidad.</li><li>El backend comprueba empresa, plan, precio y stock de todas las líneas desde una sucursal. La comprobación se realiza para el pedido completo y no confirma líneas parciales.</li><li>Con precio aceptado y stock suficiente, el backend aparta todas las líneas por 60 minutos y devuelve importe BOB y estado «falta pagar».</li><li>La aplicación informa el resultado por bandeja y, cuando corresponda, push; el cliente inicia CU15 online para pagar.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="4">Si falta una línea, se rechaza el pedido completo, se informa el faltante y no se cobra.</li><li value="4">Si cambió el importe, se solicita aceptación expresa del nuevo total antes de apartar y pagar; rechazarlo deja la compra sin cobro.</li><li value="5">Si otro cliente toma la última unidad primero, esta solicitud recibe indisponibilidad; un reintento con el mismo UUID no crea un segundo pedido.</li><li value="6">Si el compromiso vence antes de pagar, se libera según conciliación de Stripe y se notifica que debe comenzar una nueva solicitud.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Resultado central persistido y visible. Puede haber stock apartado temporalmente, pero la venta solo queda pagada tras CU15 y confirmación de Stripe; no hay cobro automático al reconectar.</td></tr>
</tbody></table>

## CU31 — Habilitar turno y cupos de caja offline

<table><tbody>
<tr><th>Nombre:</th><td>Habilitar turno y cupos de caja offline</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Asigna unidades físicas por variante a una caja web instalada y autoriza un turno de hasta ocho horas.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cajero o Administrador de empresa autorizado para la sucursal.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Conexión disponible; actor autenticado; sucursal activa; plan en estado que permite nuevos turnos; caja identificada.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor solicita abrir turno y especifica variantes y cantidades físicamente verificadas.</li><li>El backend valida permisos, sucursal, disponibilidad libre y que la caja no tenga un turno incompatible abierto.</li><li>El backend asigna cupos por variante sin duplicarlos y congela precios/promociones autorizados. La asignación reduce la disponibilidad general mientras el cupo está bajo responsabilidad de la caja.</li><li>El backend emite habilitación ligada a empresa, sucursal, actor, dispositivo, lote y plazo de ocho horas.</li><li>La caja persiste habilitación, cupos y precios y muestra el turno listo para operar offline.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si falta stock, permiso o vigencia de plan, se informa la causa y no se aparta el cupo.</li><li value="5">Si falla la persistencia local, la caja no inicia ventas; el cupo asignado queda pendiente de cierre o recuperación controlada.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Cupo apartado del stock general y turno auditable; no se libera automáticamente al vencer el plazo.</td></tr>
</tbody></table>

## CU32 — Registrar y sincronizar venta de contado offline

<table><tbody>
<tr><th>Nombre:</th><td>Registrar y sincronizar venta de contado offline</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite cobrar efectivo y entregar prendas en caja web sin Internet, y registrar después la venta central sin doble descuento de inventario.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cajero o Administrador de empresa autorizado para la sucursal.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Turno CU31 habilitado, dentro de ocho horas; cupo local suficiente; prendas físicamente presentes; precios autorizados descargados.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor selecciona variantes y cantidades dentro del cupo y verifica el total BOB autorizado.</li><li>La caja guarda un borrador local y bloquea temporalmente esas unidades del cupo para la operación.</li><li>El actor recibe el efectivo y confirma la operación.</li><li>La caja guarda atómicamente venta, líneas, total, efectivo, UUID y consumo definitivo del cupo; informa que el registro local es durable. La confirmación local preserva el importe efectivamente cobrado aunque la caja siga sin conexión.</li><li>El actor entrega las prendas y la caja registra la entrega en el mismo comprobante local.</li><li>La interfaz muestra «cobrado y entregado; pendiente de sincronización».</li><li>Al volver Internet, la caja envía la operación con la habilitación original.</li><li>El backend verifica cupo, turno, versión de precios y duplicados; registra venta, pago efectivo y Kardex una vez, y devuelve resultado.</li><li>La caja conserva el resultado y, al cerrar el turno tras enviar todas las ventas, devuelve solo cupo no usado.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="1">Si no hay cupo o el turno venció, la caja no permite cobrar ni entregar como venta offline.</li><li value="4">Si falla la persistencia antes de entregar, el actor devuelve el efectivo y no entrega prendas; el borrador se concilia o cancela sin consumir cupo definitivo.</li><li value="5">Si excepcionalmente falla el registro de entrega después del cobro, se conserva la venta local y se abre incidencia de entrega; no se borra el efectivo.</li><li value="8">Si plan o empleado expiró después de una venta válida, se registra y marca para revisión. Si hay corrupción, pérdida física o inconsistencia, se conserva el registro y se abre conciliación auditada.</li><li value="9">Si se perdió la caja, un encargado autorizado realiza conteo físico y cierre auditado antes de liberar cupos.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Venta físicamente realizada queda registrada o en conciliación trazable; resultado central durable, sin dos cargos de inventario ni dos pagos por reintento.</td></tr>
</tbody></table>

## CU33 — Cambiar prenda y liquidar diferencia

<table><tbody>
<tr><th>Nombre:</th><td>Cambiar prenda y liquidar diferencia</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite cambiar una o varias unidades entregadas por otra talla, color o producto, cobrando diferencia o emitiendo saldo.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Encargado de sucursal o Administrador de empresa autorizado; Cliente presenta la prenda y comprobante.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Conexión online; entrega hace como máximo el plazo configurado (15 días iniciales); sucursal de origen; comprobante; prenda sin uso; cantidad no cambiada previamente.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor localiza venta y unidades originales y registra la inspección de la prenda.</li><li>El sistema valida empresa, sucursal, plazo, comprobante, cantidades y estado.</li><li>El actor selecciona reemplazo; el sistema muestra valor neto reconocido por unidad, precio actual y diferencia. El cliente compara la prenda sustituta y la diferencia antes de autorizar el cambio.</li><li>El cliente acepta el reemplazo y el importe.</li><li>Si la diferencia favorece a la tienda, se confirma el cobro online antes de entregar; si favorece al cliente, se emite saldo personal.</li><li>El sistema registra cambio, inventario y Kardex sin duplicados y se entrega el reemplazo cuando la liquidación está resuelta.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si está fuera de plazo, usado, sin comprobante o en otra sucursal, se rechaza sin alterar venta ni inventario.</li><li value="3">Si no hay reemplazo disponible, se solicita otra opción antes de comprometer la operación.</li><li value="5">Si el pago Stripe queda incierto, se mantiene reemplazo y saldo aplicable reservados; no se entrega hasta confirmar o cancelar y conciliar.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Cambio vinculado a venta original, valores históricos y liquidación auditados; saldo emitido una sola vez o diferencia cobrada antes de entrega.</td></tr>
</tbody></table>

## CU34 — Aplicar saldo personal a una compra

<table><tbody>
<tr><th>Nombre:</th><td>Aplicar saldo personal a una compra</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Permite usar parcialmente o por completo el saldo de cambios en una compra online o presencial de la misma empresa.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Cliente; Cajero o Administrador de empresa en una venta presencial autorizada.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Conexión disponible; cliente identificado; saldo positivo propio de la empresa; compra con importe aceptado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El cliente consulta su saldo y elige cuánto aplicar a la compra.</li><li>El backend valida identidad, empresa, saldo disponible y total.</li><li>El backend reserva el importe de saldo para impedir doble gasto. El bloqueo temporal del saldo evita que otra compra del mismo cliente use ese importe simultáneamente.</li><li>Si queda diferencia, el cliente la paga mediante efectivo registrado en tienda o Stripe online; si no queda diferencia, no se crea cobro Stripe de cero.</li><li>Al confirmarse la compra, el backend consume el saldo una sola vez y muestra el nuevo balance.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si el saldo pertenece a otra empresa/persona, no está disponible o la sesión es inválida, se rechaza sin aplicarlo.</li><li value="4">Si el pago complementario falla o queda incierto, el saldo permanece reservado hasta reconciliación; al cancelar, se libera.</li><li value="5">Un reintento devuelve la liquidación previa, sin segundo consumo.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Saldo consumido y compra liquidada de forma consistente; su uso no se cuenta como ingreso comercial nuevo.</td></tr>
</tbody></table>

## CU35 — Consultar pronóstico de unidades vendidas

<table><tbody>
<tr><th>Nombre:</th><td>Consultar pronóstico de unidades vendidas</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Muestra estimaciones de unidades para la semana siguiente por producto y sucursal, junto con versión y evaluación del modelo supervisado.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador de empresa con plan Profesional.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Sesión online autorizada; modelo entrenado/evaluado y datos suficientes para el ámbito solicitado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor selecciona producto, sucursal y periodo de pronóstico en el dashboard.</li><li>El backend valida empresa, rol y plan Profesional.</li><li>El sistema prepara variables conocidas hasta la fecha de corte y ejecuta inferencia con modelo versionado. Solo se usan variables conocidas a la fecha de corte para no incorporar información futura al cálculo.</li><li>El dashboard presenta estimación, periodo, datos usados y error de evaluación, señalando si la validación fue solo sintética.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si el plan o permiso no habilita ML, se rechaza la consulta sin exponer resultados históricos de otra empresa.</li><li value="3">Si falta historial o modelo válido, se muestra «datos insuficientes» o indisponibilidad, sin inventar una predicción confiable.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Resultado de consulta auditable; ninguna venta ni inventario cambia por la estimación.</td></tr>
</tbody></table>

## CU36 — Consultar grupos de productos

<table><tbody>
<tr><th>Nombre:</th><td>Consultar grupos de productos</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Presenta agrupaciones aprendidas sin etiquetas previas a partir del comportamiento de ventas de productos.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador de empresa con plan Profesional.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Sesión online autorizada; datos e indicadores de productos de su empresa disponibles; modelo evaluado.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor abre el análisis de agrupación de productos.</li><li>El backend valida empresa, rol y plan.</li><li>El sistema calcula o recupera grupos de productos de esa empresa con el modelo versionado. El resultado se explica con los rasgos de ventas que caracterizan cada grupo.</li><li>El dashboard muestra productos por grupo, indicadores que lo caracterizan y métricas de calidad.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si no dispone de Profesional, se deniega el acceso.</li><li value="3">Si hay pocos productos o datos insuficientes para una agrupación interpretable, se muestra la causa sin asignar etiquetas arbitrarias.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Consulta registrada y resultados limitados a la empresa; ningún stock se modifica.</td></tr>
</tbody></table>

## CU37 — Configurar tasa de conversión BOB/USD

<table><tbody>
<tr><th>Nombre:</th><td>Configurar tasa de conversión BOB/USD</td></tr>
<tr><th>Autor:</th><td>Equipo FashionStore</td></tr><tr><th>Fecha:</th><td>18/10/2026</td></tr>
<tr><th colspan="2">Descripción:</th></tr><tr><td colspan="2">Registra la tasa única de plataforma necesaria para preparar cobros Stripe Test en USD de importes comerciales BOB.</td></tr>
<tr><th colspan="2">Actores:</th></tr><tr><td colspan="2">Administrador de plataforma.</td></tr>
<tr><th colspan="2">Precondiciones:</th></tr><tr><td colspan="2">Actor autenticado; tasa positiva y fechas de vigencia conocidas.</td></tr>
<tr><th colspan="2">Flujo Normal:</th></tr><tr><td colspan="2"><ol><li>El actor introduce tasa BOB por USD e intervalo de vigencia.</li><li>El sistema valida valor, fechas y que no existan versiones vigentes incompatibles.</li><li>El actor confirma; el sistema guarda nueva versión y autor del cambio. La fecha de vigencia permite saber qué versión corresponde a cada nuevo cobro.</li><li>Las nuevas intenciones de pago muestran BOB, tasa aplicada y USD redondeado antes de aceptar.</li></ol></td></tr>
<tr><th colspan="2">Flujo Alternativo:</th></tr><tr><td colspan="2"><ol><li value="2">Si la tasa es inválida o el intervalo se solapa, se rechaza y se indica qué corregir.</li><li value="4">Si no hay tasa vigente, se bloquea la preparación de un nuevo cobro Stripe; pagos existentes conservan tasa y USD previamente aceptados.</li></ol></td></tr>
<tr><th colspan="2">Poscondiciones:</th></tr><tr><td colspan="2">Versión de tasa auditada; ningún pago histórico se recalcula.</td></tr>
</tbody></table>
