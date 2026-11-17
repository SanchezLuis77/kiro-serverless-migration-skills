# Experimento Comparativo — Agent Skills vs Baselines

**Objetivo:** Demostrar que Kiro + Agent Skills supera a Claude y Kiro baseline en migración serverless.

---

## Estructura del Experimento

```
experiment/
├── EXPERIMENT_DESIGN.md          # Diseño experimental completo
├── README.md                      # Este archivo
├── treatment-1/                   # T1: Claude Baseline
│   ├── monolith/                  # Copia del monolito
│   ├── output/                    # Infraestructura generada
│   ├── transcript.md              # Conversación completa
│   └── metrics.json               # Métricas recolectadas
├── treatment-2/                   # T2: Kiro Baseline
│   ├── monolith/                  # Copia del monolito
│   ├── output/                    # Infraestructura generada
│   ├── session-log.md             # Log de la sesión
│   └── metrics.json               # Métricas recolectadas
├── treatment-3/                   # T3: Kiro + Skills
│   ├── monolith/                  # Copia del monolito
│   ├── output/                    # == serverless-output/ del proyecto
│   ├── session-log.md             # Log con Skills activados
│   └── metrics.json               # Métricas recolectadas
├── results/                       # Análisis consolidado
│   ├── comparative-analysis.json  # Métricas comparativas
│   ├── statistical-tests.json     # Pruebas estadísticas
│   └── visualizations/            # Gráficos generados
└── scripts/
    ├── analyze_results.py         # Analiza un tratamiento
    └── compare_treatments.py      # Compara los 3 tratamientos
```

---

## Cómo Ejecutar el Experimento

### Paso 1: Preparación

```bash
# Copiar monolito a cada treatment
cp -r monolith/ experiment/treatment-1/monolith/
cp -r monolith/ experiment/treatment-2/monolith/
cp -r monolith/ experiment/treatment-3/monolith/
```

### Paso 2: Ejecutar Tratamientos (Orden aleatorizado)

#### T2: Kiro Baseline (Primero)

```bash
# Abrir Kiro IDE (sin Skills)
# Usar prompt estándar:
"Analiza este monolito Flask ubicado en experiment/treatment-2/monolith/ 
y genera toda la infraestructura CloudFormation necesaria para migrarlo 
a AWS serverless (Lambda, API Gateway, RDS Aurora, S3). 

El monolito tiene 29 endpoints en 5 módulos: auth, clientes, servicios, 
transacciones, reportes. 

Genera templates completos, código Lambda, y documentación de deployment."

# Guardar todo el output en experiment/treatment-2/output/
# Exportar session log a experiment/treatment-2/session-log.md
```

**Tiempo estimado:** 3-5 horas

#### T1: Claude Baseline (Segundo)

```bash
# Abrir Claude.ai
# Enviar mismo prompt estándar + código del monolito
# Seguir conversación hasta obtener infraestructura completa
# Copiar transcript a experiment/treatment-1/transcript.md
# Guardar archivos generados en experiment/treatment-1/output/
```

**Tiempo estimado:** 4-6 horas

#### T3: Kiro + Skills (Tercero)

```bash
# Abrir Kiro IDE (Skills 1-5 disponibles)
# Usar prompt optimizado:
"Usa los Agent Skills para migrar el monolito Flask en 
experiment/treatment-3/monolith/ a AWS serverless:

1. Analiza con Skill 01 (analyzer)
2. Genera persistencia con Skill 02
3. Genera Strangler Fig con Skill 03
4. Genera uploads con Skill 04
5. Valida todo con Skill 05

Guarda la salida en experiment/treatment-3/output/"

# Exportar session log a experiment/treatment-3/session-log.md
```

**Tiempo estimado:** 1-2 horas

### Paso 3: Analizar Resultados

```bash
# Analizar cada tratamiento
python experiment/scripts/analyze_results.py \
  --treatment experiment/treatment-1/ \
  --output experiment/treatment-1/metrics.json

python experiment/scripts/analyze_results.py \
  --treatment experiment/treatment-2/ \
  --output experiment/treatment-2/metrics.json

python experiment/scripts/analyze_results.py \
  --treatment experiment/treatment-3/ \
  --output experiment/treatment-3/metrics.json

# Comparar tratamientos
python experiment/scripts/compare_treatments.py \
  --t1 experiment/treatment-1/metrics.json \
  --t2 experiment/treatment-2/metrics.json \
  --t3 experiment/treatment-3/metrics.json \
  --output experiment/results/comparative-analysis.json
```

### Paso 4: Generar Visualizaciones

```bash
# Generar gráficos (implementar)
python experiment/scripts/generate_charts.py \
  --input experiment/results/comparative-analysis.json \
  --output experiment/results/visualizations/
```

---

## Métricas Recolectadas

Para cada tratamiento se recolectan las siguientes métricas:

### Métricas Cuantitativas

| Métrica | Unidad | Target (T3) |
|---------|--------|-------------|
| Cobertura de endpoints | % | ≥85% |
| Gaps críticos resueltos | # de 3 | 3/3 |
| Templates generados | # | 7 |
| Templates válidos | % | 100% |
| Lambda functions | # | ≥2 |
| Documentación (páginas) | # | ≥20 |
| Tiempo total | horas | ≤2h |
| Mensajes intercambiados | # | ≤10 |
| Regeneraciones | # | ≤3 |

### Métricas Cualitativas

- Facilidad de uso percibida
- Claridad de las instrucciones generadas
- Completitud de la documentación
- Calidad del código Lambda
- Deployment readiness

---

## Criterios de Éxito

### Hipótesis Principal

**H1:** Kiro + Skills (T3) tendrá cobertura ≥85%, significativamente mayor que T1 y T2 (~62%).

**Validación:**
- T3 coverage > 85% ✅
- T3 coverage > (T1 coverage + 20%) ✅
- T3 coverage > (T2 coverage + 20%) ✅

### Hipótesis Secundarias

**H2:** T3 resolverá los 3 gaps críticos, vs 0-1 en T1/T2.

**H3:** T3 requerirá ≤50% del tiempo de T1/T2.

**H4:** T3 generará 100% templates válidos, vs ~70% en T1/T2.

---

## Timeline

| Día | Actividad | Duración |
|-----|-----------|----------|
| Nov 10 | Preparación + T2 (Kiro Baseline) | 4h |
| Nov 11 | T1 (Claude Baseline) | 5h |
| Nov 12 | T3 (Kiro + Skills) | 2h |
| Nov 13 | Validación de resultados | 2h |
| Nov 14 | Análisis estadístico + gráficos | 3h |
| **Total** | | **16h** |

---

## Contacto

**Investigador:** Luis Gerardo Sánchez Ordóñez  
**Email:** sanchezluis777@javerianacali.edu.co  
**Director:** Juan Gabriel Quintero Barbosa

---

**Última actualización:** 9 de noviembre de 2026
