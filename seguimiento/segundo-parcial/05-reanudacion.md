# Guía de reanudación para otro chat

**Fecha de corte:** 05/11/2026. **Fuentes operativas vigentes:** [entrega técnica E1 y plan E2](14-entrega-e1-y-plan-e2.md), [encargo E2](15-ejecucion-e2.md) y [auditoría independiente posterior al checkpoint 19](20-auditoria-independiente-post-checkpoint-19.md). Contrato 0.3.2, protocolo 0.4.0.

## Estado comprobado

- E1 comprende 14 CU: CU01, CU02, CU03, CU04, CU06, CU07, CU12, CU13, CU14, CU15, CU16, CU17, CU18 y CU26. Hay commits de código y contrato en los tres repositorios: backend `8b42fef` en `feature/sp2-e1-b1-identidad`, frontend `1efa89f` en la misma rama y Flutter `41463a7` en `refactor/paquetes-cu`.
- Backend: 122 pruebas aprobadas en copia PostgreSQL migrada 0010–0013. Frontend: 201 pruebas, build y TypeScript aprobados. Flutter: 196 pruebas y análisis estático aprobados. La aserción de selección de cupo tras conciliación parcial se corrigió y su widget pasó 2/2.
- Base local: PostgreSQL `fashionstore_db` en `127.0.0.1:5432`, revisión Alembic `0013_cupo_merma_eventos_kardex`. Las migraciones versionadas están en `backend/alembic/versions`. Nunca asumir que la base sea un archivo SQLite.
- La entrega técnica está registrada; la aceptación formal del propietario y recorridos manuales PWA/Android físico siguen pendientes. Las auditorías 12 y 13 son históricas; el documento 14 tiene prioridad para el estado de pruebas y Git.
- E2 comprende 13 CU. Tras el checkpoint 19, la auditoría 20 comprobó avances y nuevos bloqueos P0/P1 en preparación Stripe, uso único del cargo en CU19, autorización v3, continuación de compras, Flutter y push. Backend 194/194 y Angular 242/242 pasan; las suites no cubren esos contraejemplos. El propietario autorizó un checkpoint WIP: backend código `d548b94`, Angular `9992cdc`, Flutter `7880a15`. Mantener E2 observada, sin aceptación ni nuevos commits de cierre hasta corregir y revisar. Caja Flutter CU06/CU07 pertenece a E1 y ya está en el commit móvil.

## Primeros pasos en un nuevo chat

1. Leer `README.md`, `02-estado-cu.md`, `20-auditoria-independiente-post-checkpoint-19.md`, `21-plan-mejora-y-cierre-e2.md`, `18-auditoria-independiente-e2.md`, `14-entrega-e1-y-plan-e2.md`, `03-ramas-y-commits.md` y las fichas 0.3.2 del CU a trabajar.
2. Consultar `git status --short`, rama y `git rev-parse HEAD` por separado en `backend`, `frontend-web` y `app-movil`. Son tres repositorios Git con checkpoint WIP en las ramas E2 integrales. Preservar cualquier cambio posterior al checkpoint.
3. Repetir las comprobaciones pertinentes al lote y ensayar migraciones en una copia PostgreSQL con datos. Mantener idempotencia, concurrencia, aislamiento por empresa y pruebas de regresión E1.
4. Registrar cada lote completado en `02-estado-cu.md` y `04-bitacora.md` con hashes reales, rutas, migraciones, pruebas y límites. No marcar «Aceptado» por una respuesta del implementador ni por el mero commit.
5. El propietario decide si/ cuándo integrar, publicar o desplegar. No inferir push o merge por existir los commits.
