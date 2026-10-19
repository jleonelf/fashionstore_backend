# Guía de revisión manual del contrato

Este contrato puede revisarse con **solo este repositorio**. La versión 0.1.1 sigue siendo una propuesta de diseño; ninguna ruta nueva ni CU nuevo se considera implementado por estar documentado. No hay que hacer commits ni publicar antes de la prueba manual y el OK del propietario.

## Orden de lectura

1. Leer [README.md](README.md) para conocer el alcance del repositorio.
2. Leer [reglas-aprobadas.md](reglas-aprobadas.md) y comprobar los acuerdos C01–C30, el alcance por canal y las reglas de dinero, stock, plazos y notificación.
3. Abrir [casos-de-uso.md](casos-de-uso.md): están CU01–CU37. Para un CU concreto, comparar su flujo normal y alternativo con la fila de [trazabilidad-cu.md](trazabilidad-cu.md) y su paquete en [paquetes-cu.md](paquetes-cu.md).
4. Leer [integracion.md](integracion.md), [compartido.md](compartido.md), [payloads.md](payloads.md) e [interfaz.json](interfaz.json). Confirmar que solicitud, estado, error, importe y plazo cuentan la misma historia. Las rutas marcadas como nuevas son propuestas hasta cotejarlas con OpenAPI real.
5. Revisar el archivo propio de este repositorio indicado abajo y el reparto E1–E6 de [flujo-trabajo.md](flujo-trabajo.md).

## Comprobaciones concretas

- CU01–CU25: verificar qué comportamiento existente se conserva y cuál se amplía; CU26–CU37: verificar que no se marcan como implementados sin evidencia de código/prueba.
- Compra cliente offline: solicitud → validación central de stock/precio → apartado de 60 minutos → aviso → aceptación y pago Stripe online. Ante `SIN_STOCK` no existe cobro.
- Caja web offline: cupo previo, turno de ocho horas, efectivo y entrega local, sincronización idempotente y recuperación auditada. Flutter no tiene caja.
- Planes, cambios, saldo, tasa BOB/USD, reportes y ML: contrastar plazos, permisos, importes y canal en reglas, casos de uso e integración.
- Abrir los enlaces Markdown locales de esta carpeta. Ningún paso de esta guía requiere `docu_general`, un archivo de otro repositorio ni el respaldo privado de la base de datos.

## Integridad de la interfaz

Desde la raíz de este repositorio, ejecutar en PowerShell `Get-FileHash contratos/segundo-parcial/interfaz.json -Algorithm SHA256` y repetir para `operacion.schema.json` y `resultado.schema.json`. Comparar cada valor con [version.json](version.json), campo `sha256` (sin distinguir mayúsculas). Los tres archivos JSON deben abrir sin error; al integrar repositorios, sus copias deben tener la misma versión y huellas. La revisión de este clon por sí solo no necesita acceso a los otros.

## Revisión específica

Leer [backend.md](backend.md) y [plan-migracion-db.md](plan-migracion-db.md). Comprobar tenant en cada consulta, transacciones y bloqueos de inventario, idempotencia, webhook Stripe, conciliación y seguridad de RLS. Para E1, [PROMPT-AGENTE-E1.md](PROMPT-AGENTE-E1.md) contiene el encargo completo dentro del repositorio. El respaldo citado en el plan es evidencia histórica y no se entrega con el contrato.

## Cómo registrar un hallazgo

Anotar `CU`, archivo y sección, texto observado, regla esperada y cambio propuesto. Clasificarlo como contradicción funcional, mensaje/API, ubicación de paquete o evidencia pendiente. Una discrepancia se resuelve y versiona antes de implementarla en varios repositorios; no se corrige solo una copia compartida.
