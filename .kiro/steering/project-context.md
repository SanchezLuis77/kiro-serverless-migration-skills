# Contexto del Proyecto de Investigación

## Descripción General

Este proyecto es un trabajo de grado de Maestría en Ingeniería de Software (Pontificia Universidad Javeriana Cali) que diseña, desarrolla y evalúa **Agent Skills para Kiro IDE** orientados a reducir las brechas de automatización en la migración de aplicaciones monolíticas Flask a arquitecturas serverless en AWS.

**Investigador:** Luis Gerardo Sánchez Ordóñez  
**Director:** Juan Gabriel Quintero Barbosa (Head Solutions Architecture, AWS Colombia)  
**Duración:** 5 meses | 192 horas de esfuerzo total

## Estructura del Proyecto

```
Kiro_MSI_Project/
├── .kiro/
│   ├── steering/           # Archivos de contexto para el agente (este directorio)
│   └── specs/              # Especificaciones de cada artefacto a construir
├── monolith/               # Aplicación Flask monolítica de referencia
├── skills/                 # Los 5 Agent Skills desarrollados
│   ├── skill-01-analyzer/
│   ├── skill-02-persistence/
│   ├── skill-03-strangler/
│   ├── skill-04-uploads/
│   └── skill-05-validator/
├── evaluation/             # Scripts y resultados del experimento comparativo
└── docs/                   # Documentación académica del proyecto
```

## Los 5 Agent Skills a Desarrollar

| # | Skill | Capa que cierra | Prioridad |
|---|-------|----------------|-----------|
| 1 | Analizador de monolito + manifiesto de migración | Análisis | Alta |
| 2 | Migrador de persistencia (RDS/VPC/migraciones) | Persistencia | Alta |
| 3 | Orquestador de coexistencia Strangler Fig | Autenticación/Coexistencia | Alta |
| 4 | Migrador de uploads (S3/pre-signed URLs) | Operacional | Media |
| 5 | Validador post-generación (completitud del output) | Observabilidad/Validación | Media |

## Brechas de Automatización Identificadas (Baseline)

El experimento preliminar sobre el monolito de referencia reveló:

- **Claude:** ~18% cobertura funcional, 78 gaps documentados
- **Kiro sin Skills:** ~62% cobertura funcional, 14 gaps, ~37-40 días-persona residuales

### Brechas Sistemáticas por Capa

1. **Persistencia:** Sin generación de RDS, VPC, subnets, security groups, RDS Proxy ni scripts de migración SQLite → PostgreSQL
2. **Autenticación/Coexistencia:** Incompatibilidad JWT monolito-Lambda, blacklist de tokens sin equivalente serverless
3. **Observabilidad:** Sin alarmas, dashboards ni métricas personalizadas de CloudWatch
4. **Operacional:** Sin tests unitarios/integración, sin scripts de migración de datos, sin rollback granular en CI/CD

## Métricas de Evaluación

| Métrica | Baseline (sin Skills) | Objetivo (con Skills) |
|---------|----------------------|----------------------|
| Cobertura funcional | 62% | >85% |
| Esfuerzo residual | ~37-40 días-persona | Reducción ≥60% |
| Tasa de desplegabilidad | Por medir | >80% |

## Servicios AWS Objetivo

Lambda, Fargate, App Runner, API Gateway, Aurora Serverless v2, RDS Proxy, S3, CloudWatch, X-Ray, SSM Parameter Store.  
**IaC:** AWS SAM exclusivamente.

## Restricciones Técnicas

- Skills operan **exclusivamente** sobre monolitos Python/Flask/SQLAlchemy
- No se contempla multi-cloud (solo AWS)
- Los Skills no refactorizan lógica de negocio — generan infraestructura y plantillas
- El análisis estático opera en memoria local (privacy by design)
