# Contrato del segundo parcial — backend

**Versión propuesta: 0.1.1.** Estos archivos especifican el trabajo acordado y las interfaces propuestas para revisión; las rutas nuevas todavía no están implementadas. El OpenAPI real se exportará desde FastAPI cuando exista el código y se cotejará con este contrato.

**Implementación por agente:** dejar cambios locales sin commits, push ni PR hasta que el propietario haga pruebas manuales y dé su OK explícito. Ver [flujo-trabajo.md](flujo-trabajo.md).

## Contenido

- [reglas-aprobadas.md](reglas-aprobadas.md): acuerdos C01–C30, notificaciones y criterios técnicos completos para este repositorio.
- [casos-de-uso.md](casos-de-uso.md): las 37 fichas CU01–CU37 con actores, flujos y alternativas.
- [guia-revision-manual.md](guia-revision-manual.md): pasos para comprobar por cuenta propia el alcance, los mensajes y la trazabilidad.
- [interfaz.json](interfaz.json): versión compartida de mensajes, estados, rutas y errores. El backend es su repositorio de origen.
- [operacion.schema.json](operacion.schema.json) y [resultado.schema.json](resultado.schema.json): esquemas JSON verificables de la sincronización.
- [compartido.md](compartido.md): reglas de sincronización, dinero y notificaciones.
- [backend.md](backend.md): invariantes, transacciones, permisos y servicios.
- [integracion.md](integracion.md): flujos y contratos funcionales para todos los módulos.
- [payloads.md](payloads.md): ejemplos de solicitudes y respuestas para que los clientes puedan preparar consumidores y dobles de prueba.
- [trazabilidad-cu.md](trazabilidad-cu.md): impacto de CU01–CU25 y alcance de CU26–CU37.
- [paquetes-cu.md](paquetes-cu.md): paquete principal y ruta de código de cada CU; capacidades nuevas marcadas como previstas.
- [flujo-trabajo.md](flujo-trabajo.md): entregas, PRs, responsables y puertas de integración entre repositorios.
- [plan-migracion-db.md](plan-migracion-db.md): estado real de la base local, respaldo y cambios de esquema previstos.
- [PROMPT-AGENTE-E1.md](PROMPT-AGENTE-E1.md): encargo listo para el primer agente de implementación backend.

Los clientes llevan una copia **idéntica** de `interfaz.json`, los dos esquemas y `compartido.md` en `contratos/segundo-parcial` de sus propios repositorios. Cada clon se puede revisar sin el monorepositorio de documentación académica. Los hashes SHA-256 de los tres JSON se anotan en [version.json](version.json); cualquier diferencia entre repositorios detiene la integración.

## Reparto y cambios

El backend es responsable de migraciones, autorización, reglas de negocio, idempotencia, OpenAPI, pruebas de concurrencia y notificaciones durables. Angular y Flutter implementan sus clientes contra la misma versión. La división puede asignarse entre compañeros sin cambiar el contrato.

Para cambiar campos o estados: abrir un cambio en este repositorio, describir compatibilidad y migración de pendientes, incrementar versión semántica, actualizar las tres copias y cotejar sus hashes antes de integrar. Los cambios compatibles pueden añadir campos opcionales; retirar o reinterpretar campos, estados o significados exige versión mayor. Los clientes conservan compatibilidad con pendientes de versiones anteriores o ejecutan migración explícita. Cada repo mantiene sus commits y PR propios; un PR de implementación cita la versión del contrato y los PR relacionados. No se considera terminada una integración solo porque exista esta documentación.

## Puerta de implementación

1. Conciliar rutas nuevas con routers actuales y proteger rutas existentes.
2. Implementar primero modelos/migraciones y API reutilizable; exportar OpenAPI real.
3. Comparar los payloads y códigos reales con `interfaz.json` y publicar ejemplos de respuesta verificables.
4. Ejecutar escenarios de aislamiento tenant, última unidad, reintento, turno de caja, cambio/saldo y pago Stripe antes de integrar los clientes.

Las funciones y métodos **nuevos** tienen nombre en español: `snake_case` Python y `camelCase` TypeScript/Dart. Se preservan firmas obligatorias de frameworks y contratos públicos existentes mediante adaptadores.

Las fichas, reglas, trazabilidad, ejemplos, esquemas y guía de revisión residen en este repositorio. Los otros repositorios solo se necesitan para integrar sus implementaciones, no para conocer este contrato.
