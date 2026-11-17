# Experimento Comparativo — Agent Skills para Migración Serverless

**Objetivo:** Demostrar que Kiro IDE + Agent Skills supera a agentes LLM baseline (Claude/Kiro sin Skills) en la migración de monolitos Flask a arquitectura serverless AWS.

**Fecha de diseño:** 9 de noviembre de 2026  
**Investigador:** Luis Gerardo Sánchez Ordóñez  
**Director:** Juan Gabriel Quintero Barbosa

---

## 1. Pregunta de Investigación

**Pregunta principal:**  
¿Los Agent Skills en Kiro IDE mejoran significativamente la cobertura, completitud y eficiencia de migraciones automáticas de monolitos Flask a arquitectura serverless AWS, comparado con agentes LLM baseline?

**Hipótesis:**  
Kiro + Agent Skills logrará >85% de cobertura de migración (vs ~62% baseline), con menor esfuerzo manual y mejor resolución de gaps arquitectónicos.

---

## 2. Variables del Experimento

### Variables Independientes (Tratamientos)

| Tratamiento | Descripción | Herramientas |
|-------------|-------------|--------------|
| **T1: Claude Baseline** | Claude 3.5 Sonnet sin contexto especializado | Claude API + prompt manual |
| **T2: Kiro Baseline** | Kiro IDE sin Agent Skills | Kiro IDE (conversational mode) |
| **T3: Kiro + Skills** | Kiro IDE con los 5 Agent Skills | Kiro IDE + Skills 1-5 |

### Variables Dependientes (Métricas)

| Métrica | Definición | Unidad | Target |
|---------|------------|--------|--------|
| **Cobertura de endpoints** | % de endpoints del manifest con infraestructura generada | % | >85% |
| **Gaps resueltos** | # de gaps críticos (GAP-01, GAP-02, GAP-03) resueltos | # | 3/3 |
| **Tiempo de desarrollo** | Tiempo total para generar infraestructura completa | horas | <4h |
| **Esfuerzo manual** | # de intervenciones humanas requeridas | # | <10 |
| **Completitud de templates** | % de templates CloudFormation sintácticamente válidos | % | 100% |
| **Anti-patrones detectados** | # de anti-patrones identificados correctamente | # | ≥7 |
| **Documentación generada** | # de guías/READMEs generados automáticamente | # | ≥5 |

### Variables de Control

- **Mismo monolito:** Todos los tratamientos usan el mismo monolito Flask (29 endpoints, 5 módulos)
- **Mismo objetivo:** Generar infraestructura CloudFormation completa para AWS
- **Mismo investigador:** Luis ejecuta los 3 tratamientos
- **Mismo ambiente:** Misma máquina, misma versión de Python

---

## 3. Diseño Experimental

### Tipo de Diseño

**Within-subjects design (intra-sujetos):**
- Mismo investigador ejecuta los 3 tratamientos
- Orden aleatorizado para evitar learning effects
- Mediciones repetidas con el mismo sujeto experimental

### Orden de Ejecución (Aleatorizado)

```
Aleatorización usando random.choice():
1. T2: Kiro Baseline (primero, para evitar contaminación con Skills)
2. T1: Claude Baseline (segundo, sin contexto de Kiro)
3. T3: Kiro + Skills (último, con conocimiento acumulado)

Justificación del orden:
- T2 primero: evita que el conocimiento de Skills contamine el baseline
- T1 segundo: Claude nunca vio Kiro, no hay contaminación
- T3 último: incluso con knowledge priming, debe superar baselines
```

### Duración Total

| Tratamiento | Tiempo estimado |
|-------------|-----------------|
| T1: Claude Baseline | 4-6 horas |
| T2: Kiro Baseline | 3-5 horas |
| T3: Kiro + Skills | 1-2 horas |
| Análisis de resultados | 2 horas |
| **Total** | **10-15 horas** |

---

## 4. Procedimiento Detallado

### Fase 1: Preparación (30 min)

1. **Crear entorno limpio para cada tratamiento:**
   ```bash
   mkdir experiment/treatment-{1,2,3}
   cp -r monolith/ experiment/treatment-1/
   cp -r monolith/ experiment/treatment-2/
   cp -r monolith/ experiment/treatment-3/
   ```

2. **Definir prompt estándar:**
   ```
   "Analiza este monolito Flask y genera toda la infraestructura 
   CloudFormation necesaria para migrarlo a AWS serverless 
   (Lambda, API Gateway, RDS Aurora, S3). El monolito tiene 29 
   endpoints distribuidos en 5 módulos (auth, clientes, servicios, 
   transacciones, reportes). Genera templates completos y listos 
   para desplegar."
   ```

3. **Preparar checklist de validación** (mismo para todos):
   - [ ] Templates CloudFormation sintácticamente válidos
   - [ ] Código Lambda generado
   - [ ] Resolución de GAP-01 (Connection pooling)
   - [ ] Resolución de GAP-02 (Local filesystem)
   - [ ] Resolución de GAP-03 (Token blacklist)
   - [ ] Documentación de deployment
   - [ ] Cobertura de 29 endpoints

### Fase 2: Ejecución de Tratamientos

#### T1: Claude Baseline (4-6 horas)

**Protocolo:**
1. Abrir Claude.ai (web interface)
2. Enviar prompt estándar + código del monolito
3. Seguir conversación hasta obtener infraestructura completa
4. Registrar:
   - Tiempo total de conversación
   - # de mensajes intercambiados
   - # de correcciones/regeneraciones solicitadas
   - Archivos generados
5. Validar con checklist

**Datos a recolectar:**
- Transcript completo de la conversación
- Todos los archivos generados
- Logs de tiempo por tarea

#### T2: Kiro Baseline (3-5 horas)

**Protocolo:**
1. Abrir Kiro IDE (sin activar Skills)
2. Enviar mismo prompt estándar
3. Usar solo modo conversational (Vibe session)
4. NO mencionar los Skills existentes
5. Seguir conversación hasta completar infraestructura
6. Registrar mismas métricas que T1

**Datos a recolectar:**
- Kiro session log
- Archivos generados
- # de tool calls ejecutados
- Tiempo total

#### T3: Kiro + Skills (1-2 horas)

**Protocolo:**
1. Abrir Kiro IDE (Skills 1-5 disponibles)
2. Enviar prompt optimizado para Skills:
   ```
   "Analiza el monolito Flask con Skill 01, luego genera 
   infraestructura con Skills 02-04, y valida con Skill 05."
   ```
3. Kiro debe activar Skills automáticamente
4. Registrar mismas métricas
5. Validar con checklist

**Datos a recolectar:**
- Session log con Skills activados
- Archivos generados (mismo output que desarrollo)
- # de Skills activados
- Tiempo total

### Fase 3: Validación (30 min por tratamiento)

**Para cada tratamiento, ejecutar:**

1. **Validación sintáctica:**
   ```bash
   python skills/skill-05-validator/scripts/validate_infrastructure.py \
     --manifest experiment/treatment-X/manifest.json \
     --output experiment/treatment-X/validation/
   ```

2. **Contar métricas:**
   ```python
   # Script de análisis (crear)
   python experiment/scripts/analyze_results.py \
     --treatment experiment/treatment-X/ \
     --output experiment/results/treatment-X-metrics.json
   ```

3. **Manual review:**
   - Revisar cada template manualmente
   - Verificar gaps resueltos
   - Contar líneas de documentación

### Fase 4: Análisis Estadístico (2 horas)

1. **Estadísticas descriptivas:**
   - Media, mediana, desviación estándar por métrica
   - Gráficos de barras comparativos

2. **Pruebas de significancia:**
   - ANOVA (si N > 3 repeticiones)
   - Wilcoxon signed-rank test (para N=1 por tratamiento)
   - Effect size (Cohen's d)

3. **Interpretación:**
   - ¿T3 superó a T1 y T2 significativamente?
   - ¿Se cumplió la hipótesis (>85% coverage)?
   - ¿Cuál fue el bottleneck de cada tratamiento?

---

## 5. Métricas de Recolección

### Checklist de Validación (Misma para todos)

```json
{
  "treatment_id": "T1|T2|T3",
  "timestamp_start": "ISO-8601",
  "timestamp_end": "ISO-8601",
  "duration_minutes": 0,
  
  "coverage": {
    "total_endpoints": 29,
    "covered_endpoints": 0,
    "coverage_percentage": 0.0
  },
  
  "gaps_resolved": {
    "GAP-01": false,
    "GAP-02": false,
    "GAP-03": false,
    "total_resolved": 0
  },
  
  "templates": {
    "total_generated": 0,
    "syntactically_valid": 0,
    "deployable": 0,
    "template_list": []
  },
  
  "lambda_code": {
    "total_functions": 0,
    "syntactically_valid": 0,
    "has_handler": 0
  },
  
  "documentation": {
    "readme_files": 0,
    "deployment_guides": 0,
    "migration_guides": 0,
    "total_pages": 0
  },
  
  "anti_patterns": {
    "detected": 0,
    "expected": 7,
    "detection_rate": 0.0
  },
  
  "effort": {
    "messages_exchanged": 0,
    "regenerations_requested": 0,
    "manual_fixes": 0,
    "tool_calls": 0
  },
  
  "notes": "Observaciones cualitativas del investigador"
}
```

---

## 6. Criterios de Éxito

### Criterio Primario

**Cobertura de endpoints ≥ 85%**

- T1 (Claude): esperado ~60-65%
- T2 (Kiro): esperado ~62% (baseline conocido)
- T3 (Kiro + Skills): esperado >85%

### Criterios Secundarios

1. **Gaps críticos resueltos:** T3 debe resolver 3/3, T1/T2 esperan 0-1/3
2. **Tiempo:** T3 debe ser ≤50% del tiempo de T1/T2
3. **Esfuerzo manual:** T3 debe requerir <10 intervenciones vs >20 en T1/T2
4. **Completitud:** T3 debe generar 100% templates válidos vs ~70% en T1/T2

---

## 7. Análisis de Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Claude no genera infraestructura completa | Alta | Alto | Extender tiempo, multiple prompts |
| Kiro baseline se comporta mejor de lo esperado | Media | Medio | Documentar mejoras recientes de Kiro |
| Skill activation falla en T3 | Baja | Alto | Probar Skills antes del experimento |
| Sesgos del investigador (learning effect) | Media | Medio | Aleatorizar orden, usar checklist objetivo |
| No hay diferencia significativa entre T2 y T3 | Baja | Alto | Analizar cualitativamente qué falló |

---

## 8. Reporte de Resultados

### Estructura del Paper (Capítulo 6 de la tesis)

1. **Abstract del experimento** (1 página)
2. **Metodología** (2 páginas)
   - Diseño experimental
   - Variables y métricas
   - Procedimiento
3. **Resultados** (3 páginas)
   - Tablas comparativas
   - Gráficos de cobertura, tiempo, esfuerzo
   - Análisis estadístico
4. **Discusión** (2 páginas)
   - Interpretación de resultados
   - Limitaciones del estudio
   - Implicaciones prácticas

### Gráficos Clave a Generar

1. **Bar chart:** Cobertura de endpoints (T1 vs T2 vs T3)
2. **Bar chart:** Gaps resueltos (stacked)
3. **Line chart:** Tiempo de desarrollo
4. **Heatmap:** Completitud por categoría (templates, Lambda, docs)
5. **Radar chart:** Métricas multidimensionales

---

## 9. Timeline del Experimento

| Día | Actividad | Duración |
|-----|-----------|----------|
| **Día 1** | Preparación + T2 (Kiro Baseline) | 4 horas |
| **Día 2** | T1 (Claude Baseline) | 5 horas |
| **Día 3** | T3 (Kiro + Skills) | 2 horas |
| **Día 4** | Validación de 3 tratamientos | 2 horas |
| **Día 5** | Análisis estadístico + gráficos | 3 horas |
| **Total** | | **16 horas** |

---

## 10. Aprobación Ética

**Declaración:**  
Este experimento no involucra sujetos humanos más allá del investigador ejecutando los tratamientos. No requiere aprobación de comité de ética. Los datos del monolito Flask son sintéticos y no contienen información sensible.

**Reproducibilidad:**  
- Monolito Flask: disponible en GitHub (código abierto)
- Skills: disponibles en el repositorio del proyecto
- Prompts: documentados en este diseño experimental
- Cualquier investigador puede replicar el experimento

---

## 11. Próximos Pasos Inmediatos

1. ✅ Diseño experimental completo (este documento)
2. ⏭️ Crear estructura de directorios para el experimento
3. ⏭️ Implementar script de análisis `analyze_results.py`
4. ⏭️ Ejecutar T2 (Kiro Baseline) — **Día 1**
5. ⏭️ Ejecutar T1 (Claude Baseline) — **Día 2**
6. ⏭️ Ejecutar T3 (Kiro + Skills) — **Día 3**
7. ⏭️ Validar y analizar resultados — **Días 4-5**

---

**Autor:** Luis Gerardo Sánchez Ordóñez  
**Fecha:** 9 de noviembre de 2026  
**Revisión:** v1.0
