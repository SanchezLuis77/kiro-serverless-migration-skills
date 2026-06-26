# Kiro Serverless Migration Skills

**Trabajo de Grado — Maestría en Ingeniería de Software**  
Pontificia Universidad Javeriana Cali

---

## Descripción

Conjunto de Agent Skills para Kiro IDE que reducen las brechas de automatización en la migración de aplicaciones monolíticas Flask a arquitecturas serverless en AWS.

## Motivación

Experimento empírico preliminar sobre un monolito Flask (5 módulos, 29 endpoints, 5 tablas SQLite):

| Herramienta | Cobertura funcional | Gaps documentados |
|-------------|--------------------|--------------------|
| Claude (Anthropic) | ~18% | 78 gaps |
| Kiro sin Skills | ~62% | 14 gaps (~37-40 días-persona) |
| **Kiro + Skills (objetivo)** | **>85%** | **Reducción ≥60%** |

## Estructura del Proyecto

```
├── .kiro/
│   ├── steering/       # Contexto del agente para todo el proyecto
│   └── specs/          # Especificaciones de cada artefacto
├── monolith/           # Aplicación Flask monolítica de referencia
├── skills/             # Los 5 Agent Skills desarrollados
│   ├── skill-01-analyzer/      # Analizador de monolito + manifiesto
│   ├── skill-02-persistence/   # Migrador de persistencia RDS/VPC
│   ├── skill-03-strangler/     # Orquestador Strangler Fig
│   ├── skill-04-uploads/       # Migrador de uploads a S3
│   └── skill-05-validator/     # Validador post-generación
├── evaluation/         # Scripts y resultados del experimento comparativo
└── docs/               # Documentación académica
```

## Skills Desarrollados

| # | Skill | Capa | Estado |
|---|-------|------|--------|
| 1 | Analizador de monolito | Análisis | 🔲 Pendiente |
| 2 | Migrador de persistencia | Persistencia | 🔲 Pendiente |
| 3 | Orquestador Strangler Fig | Autenticación/Coexistencia | 🔲 Pendiente |
| 4 | Migrador de uploads | Operacional | 🔲 Pendiente |
| 5 | Validador post-generación | Observabilidad/Validación | 🔲 Pendiente |

## Instalación de Skills en Kiro

```bash
# Desde el marketplace de Kiro (próximamente)
# O directamente desde este repositorio:
git clone https://github.com/SanchezLuis77/kiro-serverless-migration-skills
```

## Servicios AWS Objetivo

Lambda · Fargate · App Runner · API Gateway · Aurora Serverless v2 · RDS Proxy · S3 · CloudWatch · X-Ray · SSM Parameter Store

**IaC:** AWS SAM

## Investigador

**Luis Gerardo Sánchez Ordóñez**  
Maestría en Ingeniería de Software — Pontificia Universidad Javeriana Cali  
Director: Juan Gabriel Quintero Barbosa (Head Solutions Architecture, AWS Colombia)

## Licencia

MIT — Publicado como código abierto para la comunidad de Kiro.
