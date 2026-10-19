# Paquetes funcionales y casos de uso

Este mapa complementa [trazabilidad-cu.md](trazabilidad-cu.md) y las [fichas CU01–CU37](casos-de-uso.md). Fija un **paquete principal por CU** para localizar su implementación; una llamada a otro paquete no cambia la pertenencia. No agrega endpoints, tablas ni estados al contrato `0.1.1`.

| Paquete principal | CU de la línea base (implementados) | CU del segundo parcial (previstos) | Código backend |
|---|---|---|---|
| `identidad_empresas` | CU01 sesión; CU02 usuarios y roles | CU26 registrar empresa; CU27 administrar suscripción | `app/core/modules/identidad_empresas/` |
| `organizacion` | CU03 ciudades, sucursales y tarifas | CU37 tasa global BOB/USD | `app/core/modules/organizacion/` |
| `catalogo` | CU05 productos; CU06 catálogo; CU22 promociones | CU28 descarga de catálogo offline | `app/core/modules/catalogo/` |
| `inventario` | CU04 proveedor y lote; CU07 Kardex y valorización | — | `app/core/modules/inventario/` |
| `reservas_traslados` | CU08 reserva; CU09 traslado; CU10 preparación; CU24 expiración | CU29 sincronización de reserva | `app/core/modules/reservas_traslados/` |
| `ventas_pagos` | CU11 venta presencial; CU13 historial; CU14 carrito; CU15 Stripe; CU16 entrega | CU30 sincronización de compra | `app/core/modules/ventas_pagos/` |
| `caja_offline` | — | CU31 turno y cupos; CU32 venta de contado offline | Solo asignación documental; el paquete se creará al implementar CU31–CU32. |
| `posventa` | CU12 devolución y merma | CU33 cambio; CU34 saldo personal | `app/core/modules/posventa/` |
| `experiencia_cliente` | CU17 probador; CU18 recomendaciones; CU20 búsqueda | — | `app/core/modules/experiencia_cliente/` |
| `analitica` | CU19 dashboard; CU21 reporte generativo; CU23 ventas por sucursal; CU25 decisiones de inventario | CU35 pronóstico supervisado; CU36 grupos no supervisados | `app/core/modules/analitica/` |

## Correspondencia entre repositorios

- **Backend:** `app/core/modules/<paquete>/` es dueño de sus routers, servicios, esquemas, repositorios y modelos. Las Entity compartidas tienen una sola definición; por ejemplo, CU12 usa `MovimientoInventario` y `DetalleVenta` desde sus paquetes dueños. `app/core/` conserva infraestructura transversal; Decart vive en `experiencia_cliente/integraciones/`, Stripe en `ventas_pagos/integraciones/` y el proveedor IA compartido en `app/core/integraciones/`. El montaje de rutas se hace en `app/api/v1/api.py`; `app/db/modelos.py` registra los modelos para Alembic. Las antiguas carpetas `app/api/v1/endpoints/`, `app/services/`, `app/schemas/`, `app/repositories/` y `app/models/` ya no forman parte de la estructura.
- **Angular:** `src/app/features/<paquete>/` contiene las pantallas de cada CU junto con sus servicios y DTO propios. `src/app/core/` conserva guardas, interceptores, utilidades y tipos genéricos compartidos. Una página puede orquestar servicios de otros paquetes sin duplicar su implementación. CU31–CU32 se implementarán solo en caja web; `caja_offline` aún no tiene código. El modo offline del cliente se limita a CU28–CU30 y las secciones aprobadas; el resto administrativo sigue online.
- **Flutter:** `lib/features/<paquete>/` agrupa pantallas, servicios y modelos de cliente. `lib/core/` conserva configuración, red, sesión, utilidades y UI compartida. No se implementa caja ni administración. CU28–CU30 y la parte cliente de CU34 tendrán consumidores móviles; CU17 mantiene el puente Android con Decart, sin cambios de protocolo ni lógica nativa por esta refactorización.

Las nuevas capacidades CU26–CU37 permanecen **previstas**: las carpetas actuales de CU anteriores y las pantallas de caja o inteligencia no constituyen implementación de esas capacidades. La operación de caja web offline, el saldo, el ML local y la tasa BOB/USD necesitan sus propios cambios de modelo, API, cliente y pruebas conforme a [integracion.md](integracion.md).

### Ruta visual de Angular

| Paquete | Carpetas actuales bajo `src/app/features/<paquete>/` |
|---|---|
| `identidad_empresas` | `auth/`, `usuarios/`, `services/`, `models/` |
| `organizacion` | `sucursales/`, `services/`, `models/` |
| `catalogo` | `catalogo/`, `productos/`, `promociones/`, `services/`, `models/` |
| `inventario` | `inventario/`, `recepciones/`, `services/`, `models/` |
| `reservas_traslados` | `reservas/`, `traslados/`, `services/`, `models/` |
| `ventas_pagos` | `caja/` (CU11 online), `carrito/`, `checkout/`, `pago/`, `pedidos/`, `mis-pedidos/`, `historial/`, `services/`, `models/` |
| `caja_offline` | Previsto para CU31–CU32; sin carpeta de implementación. |
| `posventa` | `operaciones/`, `services/`, `models/` |
| `experiencia_cliente` | `landing/`, `services/`, `models/` |
| `analitica` | `dashboard/`, `inteligencia/`, `services/`, `models/` |

`operaciones/` reúne la interfaz de reporte de ventas, devolución y merma; consume los servicios dueños de `analitica`, `ventas_pagos` y `posventa`. La ruta pública de Angular y sus permisos permanecen en `app.routes.ts` sin cambios de URL.

### Ruta visual de Flutter cliente

| Paquete | Carpetas actuales bajo `lib/features/<paquete>/` |
|---|---|
| `identidad_empresas` | `auth/`, `cuenta/`, `services/`, `models/` |
| `organizacion` | `services/`, `models/` para consulta de sucursales; sin pantalla administrativa. |
| `catalogo` | `catalogo/`, `services/`, `models/` |
| `reservas_traslados` | `reservas/`, `services/`, `models/` |
| `ventas_pagos` | `carrito/`, `checkout/`, `pago/`, `pedidos/`, `historial/`, `services/`, `models/` |
| `experiencia_cliente` | `home/`, `busqueda/`, `recomendaciones/`, `probador/`, `services/`, `models/` |
| `posventa` | Previsto para CU34: saldo del cliente y su uso online; sin carpeta móvil actual. CU33 se tramita en web. |

Los paquetes solo administrativos (`inventario`, `analitica` y `caja_offline`) no se crean en Flutter. `posventa` sí tendrá la parte cliente de CU34, sin habilitar cambios administrativos de CU33. La pantalla de catálogo puede consumir IA del paquete `experiencia_cliente` y la selección de sucursal del paquete `organizacion`, manteniendo un único dueño por servicio y DTO.

## Ubicación obligatoria para CU26–CU37

La tabla fija el **paquete dueño y la carpeta de entrada** de cada CU nuevo. Dentro del paquete backend se reutilizan `routers/`, `services/`, `repositories/`, `schemas.py` y `models.py` según la necesidad real; una operación no exige crear cinco archivos vacíos. En Angular y Flutter, la pantalla queda en la subcarpeta indicada y sus servicios/modelos en `services/` y `models/` del mismo paquete. Los nombres nuevos de funciones y métodos siguen el patrón español acordado.

| CU | Backend: `app/core/modules/` | Angular: `src/app/features/` | Flutter: `lib/features/` |
|---|---|---|---|
| CU26 Registrar empresa | `identidad_empresas/` | `identidad_empresas/empresas/` | Sin alta de empresa; adaptar `identidad_empresas/auth/` al contexto de empresa. |
| CU27 Administrar suscripción | `identidad_empresas/` | `identidad_empresas/planes/` | Sin administración; mostrar capacidad de la empresa en sesión/cuenta si corresponde. |
| CU28 Descargar catálogo | `catalogo/` | `catalogo/catalogo/` | `catalogo/catalogo/` |
| CU29 Sincronizar reserva | `reservas_traslados/` | `reservas_traslados/reservas/` | `reservas_traslados/reservas/` |
| CU30 Sincronizar compra | `ventas_pagos/` | `ventas_pagos/carrito/`, `checkout/` y `mis-pedidos/` | `ventas_pagos/carrito/`, `checkout/` y `pedidos/` |
| CU31 Habilitar caja offline | `caja_offline/` (nuevo paquete) | `caja_offline/turnos/` (nuevo paquete) | Fuera de alcance. |
| CU32 Venta de contado offline | `caja_offline/` | `caja_offline/ventas/` | Fuera de alcance. |
| CU33 Cambio de prenda | `posventa/` | `posventa/cambios/` | Fuera de alcance; trámite web online. |
| CU34 Aplicar saldo | `posventa/` | `posventa/saldo/`; checkout consume su servicio | `posventa/saldo/` (nuevo paquete); checkout consume su servicio |
| CU35 Pronóstico supervisado | `analitica/` | `analitica/pronosticos/` | Fuera de alcance. |
| CU36 Grupos no supervisados | `analitica/` | `analitica/grupos/` | Fuera de alcance. |
| CU37 Tasa BOB/USD | `organizacion/` | `organizacion/tasa/` | Sin configuración; checkout muestra la conversión devuelta por backend. |

Las adaptaciones de CU01–CU25 se realizan en sus paquetes dueños de la primera tabla; [trazabilidad-cu.md](trazabilidad-cu.md) identifica la regla modificada. El endpoint común de sincronización es solo un adaptador de transporte: despacha cada tipo de operación al servicio dueño de CU29, CU30 o CU32, sin guardar allí lógica de stock, pagos o caja. Los contratos `interfaz.json`, los JSON Schema y los payloads fijan la interfaz pública independientemente de estas rutas internas. La infraestructura transversal (sesión, reloj, persistencia local, emisor de notificaciones y registro de modelos) permanece en `core`/`db` cuando sirve a varios paquetes; no se duplican DTO ni reglas entre paquetes.

## Límites de dependencia

`catalogo` y `organizacion` aportan variantes, precios, sucursales y tarifas. `inventario` es dueño de existencias y Kardex. `reservas_traslados`, `ventas_pagos`, `caja_offline` y `posventa` consumen esas capacidades sin duplicar stock ni dinero. `analitica` consulta hechos de los demás paquetes y es dueña de los DTO de CU21/CU25; `experiencia_cliente` es dueña de CU17/CU18/CU20. `HistorialComprasDTO` pertenece a `ventas_pagos` (CU13).

Las modificaciones concretas de los CU01–CU25 y las salidas verificables de CU26–CU37 se detallan en [trazabilidad-cu.md](trazabilidad-cu.md). Las interfaces compartidas están en [interfaz.json](interfaz.json) e [integracion.md](integracion.md); los detalles por cliente y backend permanecen en los archivos propios de cada repositorio. Este mapa no los reemplaza.
