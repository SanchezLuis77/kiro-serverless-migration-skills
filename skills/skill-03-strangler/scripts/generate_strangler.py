"""
generate_strangler.py — Skill 03: Orquestador Strangler Fig

Genera la infraestructura de orquestación para migración gradual monolito → serverless:
  - API Gateway REST API con VPC Link al monolito
  - Lambda Authorizer para validación JWT centralizada
  - DynamoDB table para token blacklist (resuelve AP-token-blacklist)
  - Routing rules por fase de migración (Strangler Fig pattern)
  - Scripts de actualización de routing

Consume el migration-manifest.json del Skill 01 y outputs del Skill 02.

Principios de diseño:
  - Sin dependencias externas: usa exclusivamente módulos de la biblioteca estándar
    de Python 3.9+ (json, os, sys, pathlib, argparse, typing, textwrap, secrets)
  - Templates CloudFormation/SAM como cadenas de texto (no requiere PyYAML)
  - Routing rules como JSON (fácil de actualizar manualmente)
  - Código Lambda Authorizer generado (Python 3.11)

Uso:
    python generate_strangler.py --manifest <ruta_manifest>
    python generate_strangler.py --manifest <ruta> --output <dir> --jwt-secret <secret>

Códigos de salida:
    0 — Generación exitosa; infraestructura lista para desplegar
    1 — El archivo manifest no existe
    2 — Error de lectura del manifest
    3 — Error de escritura del output

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
Director: Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
"""

import json
import os
import sys
import secrets
import argparse
import textwrap
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

SKILL_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = "serverless-output/strangler"
DEFAULT_API_STAGE = "prod"
DEFAULT_MONOLITH_URL = "http://internal-monolith-alb.local"

# ---------------------------------------------------------------------------
# === ManifestLoader ===
# ---------------------------------------------------------------------------

class ManifestLoader:
    """
    Carga y valida el migration-manifest.json generado por Skill 01.
    """

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.warnings: List[str] = []

    def load(self) -> Dict[str, Any]:
        """
        Carga el manifest desde disco y valida que contenga las claves requeridas.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in manifest: {exc}")

        # Validar estructura mínima
        required_keys = ["metadata", "summary", "modules", "migration_sequence"]
        missing = [k for k in required_keys if k not in manifest]
        if missing:
            raise ValueError(f"Manifest missing required keys: {missing}")

        return manifest


# ---------------------------------------------------------------------------
# === RoutingRulesGenerator ===
# ---------------------------------------------------------------------------

class RoutingRulesGenerator:
    """
    Genera las routing rules para API Gateway basadas en la secuencia de migración.
    """

    def __init__(self, manifest: Dict[str, Any]) -> None:
        self.manifest = manifest
        self.migration_sequence = manifest.get("migration_sequence", [])
        self.modules = {m["name"]: m for m in manifest.get("modules", [])}

    def generate(self) -> Dict[str, Any]:
        """
        Genera el archivo routing-rules.json con todas las fases de migración.
        """
        phases = []

        # Fase 0: Baseline — todo al monolito
        phases.append({
            "phase": 0,
            "name": "baseline",
            "description": "Todo al monolito — sin migración aún",
            "routes": [
                {
                    "path": "/{proxy+}",
                    "method": "ANY",
                    "target": "monolith",
                    "integration_type": "HTTP_PROXY"
                }
            ]
        })

        # Fases 1-N: Migración incremental por módulo
        migrated_modules = []
        for i, phase_info in enumerate(self.migration_sequence, start=1):
            module_name = phase_info["module"]
            module = self.modules.get(module_name)
            
            if not module:
                continue

            migrated_modules.append(module_name)
            
            routes = []
            
            # Agregar rutas para módulos YA migrados (Lambdas)
            for migrated in migrated_modules:
                mod = self.modules.get(migrated)
                if mod:
                    url_prefix = mod.get("url_prefix", f"/api/{migrated}")
                    routes.append({
                        "path": f"{url_prefix}/{{proxy+}}",
                        "method": "ANY",
                        "target": f"lambda:{migrated}",
                        "integration_type": "AWS_PROXY"
                    })
            
            # Catch-all para el resto (monolito)
            routes.append({
                "path": "/{proxy+}",
                "method": "ANY",
                "target": "monolith",
                "integration_type": "HTTP_PROXY"
            })

            phases.append({
                "phase": i,
                "name": module_name,
                "description": phase_info.get("justification", f"Migrar módulo {module_name} a Lambda"),
                "prerequisites": phase_info.get("prerequisites", []),
                "routes": routes
            })

        return {
            "version": "1.0.0",
            "total_phases": len(phases),
            "current_phase": 0,
            "phases": phases
        }


# ---------------------------------------------------------------------------
# === APIGatewayTemplateGenerator ===
# ---------------------------------------------------------------------------

class APIGatewayTemplateGenerator:
    """
    Genera el template CloudFormation para API Gateway + VPC Link.
    """

    @staticmethod
    def generate(api_stage: str = DEFAULT_API_STAGE, monolith_url: str = DEFAULT_MONOLITH_URL) -> str:
        """
        Genera el template YAML para API Gateway con VPC Link.
        """
        return textwrap.dedent(f"""\
        AWSTemplateFormatVersion: '2010-09-09'
        Description: 'API Gateway + VPC Link para Strangler Fig - Skill 03'
        
        Parameters:
          EnvironmentName:
            Type: String
            Default: 'taller'
            Description: 'Nombre del ambiente'
          
          ApiStageName:
            Type: String
            Default: '{api_stage}'
            Description: 'Nombre del stage de API Gateway'
          
          MonolithURL:
            Type: String
            Default: '{monolith_url}'
            Description: 'URL del monolito Flask (ALB interno o ECS service)'
        
        Resources:
          # REST API
          RestAPI:
            Type: AWS::ApiGateway::RestApi
            Properties:
              Name: !Sub '${{EnvironmentName}}-api'
              Description: 'API Gateway para migración Strangler Fig'
              EndpointConfiguration:
                Types:
                  - REGIONAL
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-api'
                - Key: ManagedBy
                  Value: 'Skill-03-Strangler'
          
          # Lambda Authorizer (referencia desde template-authorizer.yaml)
          Authorizer:
            Type: AWS::ApiGateway::Authorizer
            Properties:
              Name: !Sub '${{EnvironmentName}}-jwt-authorizer'
              Type: TOKEN
              AuthorizerUri: !Sub 'arn:aws:apigateway:${{AWS::Region}}:lambda:path/2015-03-31/functions/${{AuthorizerFunction.Arn}}/invocations'
              AuthorizerResultTtlInSeconds: 300
              IdentitySource: method.request.header.Authorization
              RestApiId: !Ref RestAPI
          
          # VPC Link para acceso privado al monolito
          VpcLink:
            Type: AWS::ApiGateway::VpcLink
            Properties:
              Name: !Sub '${{EnvironmentName}}-vpc-link'
              Description: 'Conexión privada a monolito Flask'
              TargetArns:
                - !Ref MonolithNLB
          
          # Network Load Balancer para el monolito (target del VPC Link)
          MonolithNLB:
            Type: AWS::ElasticLoadBalancingV2::LoadBalancer
            Properties:
              Name: !Sub '${{EnvironmentName}}-monolith-nlb'
              Type: network
              Scheme: internal
              Subnets:
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet1'
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet2'
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-monolith-nlb'
          
          MonolithTargetGroup:
            Type: AWS::ElasticLoadBalancingV2::TargetGroup
            Properties:
              Name: !Sub '${{EnvironmentName}}-monolith-tg'
              Port: 5000
              Protocol: TCP
              VpcId:
                Fn::ImportValue: !Sub '${{EnvironmentName}}-VPCId'
              HealthCheckEnabled: true
              HealthCheckProtocol: HTTP
              HealthCheckPath: /health
              HealthCheckIntervalSeconds: 30
              TargetType: ip
          
          MonolithListener:
            Type: AWS::ElasticLoadBalancingV2::Listener
            Properties:
              DefaultActions:
                - Type: forward
                  TargetGroupArn: !Ref MonolithTargetGroup
              LoadBalancerArn: !Ref MonolithNLB
              Port: 5000
              Protocol: TCP
          
          # Resource raíz con proxy
          RootResource:
            Type: AWS::ApiGateway::Resource
            Properties:
              ParentId: !GetAtt RestAPI.RootResourceId
              PathPart: '{{proxy+}}'
              RestApiId: !Ref RestAPI
          
          # Método ANY para catch-all (Fase 0: todo al monolito)
          ProxyMethod:
            Type: AWS::ApiGateway::Method
            Properties:
              RestApiId: !Ref RestAPI
              ResourceId: !Ref RootResource
              HttpMethod: ANY
              AuthorizationType: CUSTOM
              AuthorizerId: !Ref Authorizer
              RequestParameters:
                method.request.path.proxy: true
              Integration:
                Type: HTTP_PROXY
                IntegrationHttpMethod: ANY
                Uri: !Sub '${{MonolithURL}}/{{proxy}}'
                ConnectionType: VPC_LINK
                ConnectionId: !Ref VpcLink
                RequestParameters:
                  integration.request.path.proxy: method.request.path.proxy
                PassthroughBehavior: WHEN_NO_MATCH
          
          # Deployment
          ApiDeployment:
            Type: AWS::ApiGateway::Deployment
            DependsOn:
              - ProxyMethod
            Properties:
              RestApiId: !Ref RestAPI
              Description: 'Initial deployment - Phase 0'
          
          # Stage
          ApiStage:
            Type: AWS::ApiGateway::Stage
            Properties:
              StageName: !Ref ApiStageName
              RestApiId: !Ref RestAPI
              DeploymentId: !Ref ApiDeployment
              Description: !Sub 'Stage ${{ApiStageName}} - Strangler Fig'
              TracingEnabled: true
              MethodSettings:
                - ResourcePath: '/*'
                  HttpMethod: '*'
                  LoggingLevel: INFO
                  DataTraceEnabled: true
                  MetricsEnabled: true
              AccessLogSetting:
                DestinationArn: !GetAtt ApiLogGroup.Arn
                Format: '$context.requestId $context.httpMethod $context.path $context.status $context.responseLatency'
          
          # CloudWatch Logs
          ApiLogGroup:
            Type: AWS::Logs::LogGroup
            Properties:
              LogGroupName: !Sub '/aws/apigateway/${{EnvironmentName}}-api'
              RetentionInDays: 7
          
          # Permission para Lambda Authorizer
          AuthorizerInvokePermission:
            Type: AWS::Lambda::Permission
            Properties:
              FunctionName: !GetAtt AuthorizerFunction.Arn
              Action: lambda:InvokeFunction
              Principal: apigateway.amazonaws.com
              SourceArn: !Sub 'arn:aws:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:${{RestAPI}}/*'
        
        Outputs:
          ApiGatewayId:
            Description: 'API Gateway REST API ID'
            Value: !Ref RestAPI
            Export:
              Name: !Sub '${{EnvironmentName}}-ApiGatewayId'
          
          ApiGatewayUrl:
            Description: 'API Gateway URL'
            Value: !Sub 'https://${{RestAPI}}.execute-api.${{AWS::Region}}.amazonaws.com/${{ApiStageName}}'
            Export:
              Name: !Sub '${{EnvironmentName}}-ApiGatewayUrl'
          
          VpcLinkId:
            Description: 'VPC Link ID'
            Value: !Ref VpcLink
            Export:
              Name: !Sub '${{EnvironmentName}}-VpcLinkId'
          
          AuthorizerId:
            Description: 'Lambda Authorizer ID'
            Value: !Ref Authorizer
            Export:
              Name: !Sub '${{EnvironmentName}}-AuthorizerId'
        """)


# ---------------------------------------------------------------------------
# === AuthorizerTemplateGenerator ===
# ---------------------------------------------------------------------------

class AuthorizerTemplateGenerator:
    """
    Genera el template CloudFormation para Lambda Authorizer.
    """

    @staticmethod
    def generate() -> str:
        """
        Genera el template YAML para Lambda Authorizer.
        """
        return textwrap.dedent("""\
        AWSTemplateFormatVersion: '2010-09-09'
        Transform: AWS::Serverless-2016-10-31
        Description: 'Lambda Authorizer para validación JWT - Skill 03'
        
        Parameters:
          EnvironmentName:
            Type: String
            Default: 'taller'
            Description: 'Nombre del ambiente'
          
          JWTSecretKey:
            Type: String
            NoEcho: true
            Description: 'JWT secret key (mismo que el monolito Flask)'
        
        Globals:
          Function:
            Runtime: python3.11
            Timeout: 5
            MemorySize: 256
            Architectures:
              - x86_64
        
        Resources:
          # Lambda Authorizer Function
          AuthorizerFunction:
            Type: AWS::Serverless::Function
            Properties:
              FunctionName: !Sub '${EnvironmentName}-jwt-authorizer'
              Description: 'Valida tokens JWT y verifica blacklist en DynamoDB'
              CodeUri: ./authorizer/
              Handler: lambda_function.lambda_handler
              Environment:
                Variables:
                  JWT_SECRET_KEY: !Ref JWTSecretKey
                  BLACKLIST_TABLE_NAME: !Ref TokenBlacklistTable
                  LOG_LEVEL: INFO
              Policies:
                - DynamoDBReadPolicy:
                    TableName: !Ref TokenBlacklistTable
              Tags:
                ManagedBy: 'Skill-03-Strangler'
          
          # DynamoDB Table para token blacklist
          TokenBlacklistTable:
            Type: AWS::DynamoDB::Table
            Properties:
              TableName: !Sub '${EnvironmentName}-token-blacklist'
              BillingMode: PAY_PER_REQUEST
              AttributeDefinitions:
                - AttributeName: token_jti
                  AttributeType: S
              KeySchema:
                - AttributeName: token_jti
                  KeyType: HASH
              TimeToLiveSpecification:
                AttributeName: expires_at
                Enabled: true
              Tags:
                - Key: Name
                  Value: !Sub '${EnvironmentName}-token-blacklist'
                - Key: ManagedBy
                  Value: 'Skill-03-Strangler'
          
          # CloudWatch Logs
          AuthorizerLogGroup:
            Type: AWS::Logs::LogGroup
            Properties:
              LogGroupName: !Sub '/aws/lambda/${AuthorizerFunction}'
              RetentionInDays: 7
        
        Outputs:
          AuthorizerFunctionArn:
            Description: 'ARN de la Lambda Authorizer'
            Value: !GetAtt AuthorizerFunction.Arn
            Export:
              Name: !Sub '${EnvironmentName}-AuthorizerFunctionArn'
          
          TokenBlacklistTableName:
            Description: 'Nombre de la tabla DynamoDB para blacklist'
            Value: !Ref TokenBlacklistTable
            Export:
              Name: !Sub '${EnvironmentName}-TokenBlacklistTableName'
          
          TokenBlacklistTableArn:
            Description: 'ARN de la tabla DynamoDB'
            Value: !GetAtt TokenBlacklistTable.Arn
            Export:
              Name: !Sub '${EnvironmentName}-TokenBlacklistTableArn'
        """)


# ---------------------------------------------------------------------------
# === AuthorizerCodeGenerator ===
# ---------------------------------------------------------------------------

class AuthorizerCodeGenerator:
    """
    Genera el código Python de la Lambda Authorizer.
    """

    @staticmethod
    def generate_handler() -> str:
        """
        Genera lambda_function.py — handler principal.
        """
        return textwrap.dedent("""\
        \"\"\"
        Lambda Authorizer para API Gateway — Validación JWT + Blacklist
        
        Valida tokens JWT Bearer y verifica si están en la blacklist de DynamoDB.
        Retorna una IAM policy que permite o niega el acceso al API.
        \"\"\"
        import os
        import json
        import logging
        import jwt
        import boto3
        from typing import Dict, Any

        # Configuración
        JWT_SECRET = os.environ['JWT_SECRET_KEY']
        BLACKLIST_TABLE = os.environ['BLACKLIST_TABLE_NAME']
        LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

        # Logger
        logger = logging.getLogger()
        logger.setLevel(LOG_LEVEL)

        # Cliente DynamoDB
        dynamodb = boto3.resource('dynamodb')
        blacklist_table = dynamodb.Table(BLACKLIST_TABLE)


        def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            \"\"\"
            Handler principal del Authorizer.
            
            Input:
                {
                  "type": "TOKEN",
                  "authorizationToken": "Bearer <token>",
                  "methodArn": "arn:aws:execute-api:..."
                }
            
            Output:
                {
                  "principalId": "user-123",
                  "policyDocument": { ... },
                  "context": { "userId": "123", "userRole": "tecnico", ... }
                }
            \"\"\"
            try:
                # Extraer token
                token = extract_token(event.get('authorizationToken', ''))
                if not token:
                    logger.warning('Missing or invalid Authorization header')
                    return generate_policy('unknown', 'Deny', event['methodArn'])
                
                # Decodificar y validar JWT
                payload = decode_jwt(token)
                if not payload:
                    logger.warning('Invalid JWT token')
                    return generate_policy('unknown', 'Deny', event['methodArn'])
                
                # Verificar blacklist
                jti = payload.get('jti')
                if is_token_revoked(jti):
                    logger.info(f'Token {jti} is in blacklist')
                    return generate_policy('unknown', 'Deny', event['methodArn'])
                
                # Token válido → Allow
                user_id = str(payload.get('sub', 'unknown'))
                logger.info(f'Token válido para user_id={user_id}')
                
                return generate_policy(
                    principal_id=user_id,
                    effect='Allow',
                    resource=event['methodArn'],
                    context={
                        'userId': user_id,
                        'userEmail': payload.get('email', ''),
                        'userRole': payload.get('rol', 'tecnico'),
                    }
                )
            
            except Exception as e:
                logger.error(f'Authorizer error: {e}', exc_info=True)
                return generate_policy('unknown', 'Deny', event['methodArn'])


        def extract_token(auth_header: str) -> str:
            \"\"\"
            Extrae el token de 'Authorization: Bearer <token>'.
            \"\"\"
            if not auth_header or not auth_header.startswith('Bearer '):
                return ''
            return auth_header[7:].strip()


        def decode_jwt(token: str) -> Dict[str, Any]:
            \"\"\"
            Decodifica y valida el JWT token.
            Retorna el payload si es válido, None si no lo es.
            \"\"\"
            try:
                payload = jwt.decode(
                    token,
                    JWT_SECRET,
                    algorithms=['HS256'],
                    options={'verify_exp': True}
                )
                return payload
            except jwt.ExpiredSignatureError:
                logger.warning('JWT token expired')
                return None
            except jwt.InvalidTokenError as e:
                logger.warning(f'Invalid JWT: {e}')
                return None


        def is_token_revoked(jti: str) -> bool:
            \"\"\"
            Verifica si el token está en la blacklist de DynamoDB.
            \"\"\"
            if not jti:
                return False
            
            try:
                response = blacklist_table.get_item(Key={'token_jti': jti})
                return 'Item' in response
            except Exception as e:
                logger.error(f'Error checking blacklist: {e}')
                # Fail-open: si DynamoDB falla, permitir el token
                return False


        def generate_policy(principal_id: str, effect: str, resource: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
            \"\"\"
            Genera una IAM policy para API Gateway.
            \"\"\"
            policy = {
                'principalId': principal_id,
                'policyDocument': {
                    'Version': '2012-10-17',
                    'Statement': [{
                        'Action': 'execute-api:Invoke',
                        'Effect': effect,
                        'Resource': resource if effect == 'Allow' else '*'
                    }]
                }
            }
            
            if context and effect == 'Allow':
                policy['context'] = context
            
            return policy
        """)

    @staticmethod
    def generate_requirements() -> str:
        """
        Genera requirements.txt para la Lambda.
        """
        return textwrap.dedent("""\
        PyJWT==2.8.0
        boto3==1.34.0
        """)


# ---------------------------------------------------------------------------
# === Main Orchestrator ===
# ---------------------------------------------------------------------------

def main():
    """
    Punto de entrada principal del script.
    """
    parser = argparse.ArgumentParser(
        description="Skill 03: Genera infraestructura Strangler Fig (API Gateway + Authorizer)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Ruta al migration-manifest.json (generado por Skill 01)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--jwt-secret",
        type=str,
        help="JWT secret key (default: generar aleatorio)"
    )
    parser.add_argument(
        "--api-stage",
        type=str,
        default=DEFAULT_API_STAGE,
        help=f"Nombre del stage de API Gateway (default: {DEFAULT_API_STAGE})"
    )
    parser.add_argument(
        "--monolith-url",
        type=str,
        default=DEFAULT_MONOLITH_URL,
        help=f"URL del monolito Flask (default: {DEFAULT_MONOLITH_URL})"
    )

    args = parser.parse_args()

    # Validar que manifest existe
    if not args.manifest.exists():
        print(f"❌ Error: Manifest not found: {args.manifest}", file=sys.stderr)
        print(f"   Ejecuta primero el Skill 01 (Analizador de Monolito)", file=sys.stderr)
        sys.exit(1)

    # Cargar manifest
    print(f"📖 Cargando manifest desde: {args.manifest}")
    loader = ManifestLoader(args.manifest)
    try:
        manifest = loader.load()
        print(f"✅ Manifest cargado exitosamente")
        print(f"   Total endpoints: {manifest['metadata']['total_endpoints']}")
        print(f"   Fases de migración: {len(manifest.get('migration_sequence', []))}")
    except Exception as exc:
        print(f"❌ Error cargando manifest: {exc}", file=sys.stderr)
        sys.exit(2)

    # Generar JWT secret si no se proveyó
    jwt_secret = args.jwt_secret or secrets.token_urlsafe(32)
    if not args.jwt_secret:
        print(f"🔐 JWT secret generado (guárdalo en SSM Parameter Store)")

    # Crear directorio de salida
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Directorio de salida: {output_dir.resolve()}")

    # Generar routing rules
    print(f"\n🔄 Generando routing rules...")
    routing_gen = RoutingRulesGenerator(manifest)
    routing_rules = routing_gen.generate()
    routing_path = output_dir / "routing-rules.json"
    with open(routing_path, 'w', encoding='utf-8') as f:
        json.dump(routing_rules, f, indent=2, ensure_ascii=False)
    print(f"   ✅ {routing_path.name} ({routing_rules['total_phases']} fases)")

    # Generar templates
    print(f"\n🏗️  Generando templates de infraestructura...")

    # 1. API Gateway
    api_template = APIGatewayTemplateGenerator.generate(args.api_stage, args.monolith_url)
    api_path = output_dir / "template-api-gateway.yaml"
    api_path.write_text(api_template, encoding='utf-8')
    print(f"   ✅ {api_path.name}")

    # 2. Lambda Authorizer
    auth_template = AuthorizerTemplateGenerator.generate()
    auth_path = output_dir / "template-authorizer.yaml"
    auth_path.write_text(auth_template, encoding='utf-8')
    print(f"   ✅ {auth_path.name}")

    # 3. Authorizer code
    authorizer_dir = output_dir / "authorizer"
    authorizer_dir.mkdir(exist_ok=True)
    
    handler_code = AuthorizerCodeGenerator.generate_handler()
    (authorizer_dir / "lambda_function.py").write_text(handler_code, encoding='utf-8')
    
    requirements = AuthorizerCodeGenerator.generate_requirements()
    (authorizer_dir / "requirements.txt").write_text(requirements, encoding='utf-8')
    print(f"   ✅ authorizer/ (Lambda code)")

    # 4. Deployment guide
    guide_content = generate_deployment_guide(manifest, routing_rules, jwt_secret, args.api_stage)
    guide_path = output_dir / "DEPLOYMENT_GUIDE.md"
    guide_path.write_text(guide_content, encoding='utf-8')
    print(f"   ✅ {guide_path.name}")

    # Summary
    print(f"\n✨ Generación completada exitosamente!")
    print(f"\n📦 Archivos generados:")
    print(f"   - template-api-gateway.yaml    (API Gateway + VPC Link)")
    print(f"   - template-authorizer.yaml     (Lambda Authorizer + DynamoDB)")
    print(f"   - routing-rules.json           ({routing_rules['total_phases']} fases de migración)")
    print(f"   - authorizer/                  (Código Lambda Authorizer)")
    print(f"   - DEPLOYMENT_GUIDE.md          (guía de despliegue)")
    print(f"\n🔐 IMPORTANTE:")
    print(f"   JWT_SECRET_KEY: {jwt_secret[:16]}... (guarda este secreto)")
    print(f"\n🚀 Siguiente paso:")
    print(f"   cd {output_dir}")
    print(f"   # Revisar templates y seguir DEPLOYMENT_GUIDE.md")

    sys.exit(0)


def generate_deployment_guide(manifest: Dict, routing_rules: Dict, jwt_secret: str, api_stage: str) -> str:
    """
    Genera la guía de despliegue en Markdown.
    """
    timestamp = datetime.utcnow().isoformat()
    total_phases = routing_rules['total_phases']
    
    return textwrap.dedent(f"""\
    # Deployment Guide — Skill 03: Orquestador Strangler Fig
    
    **Generado:** {timestamp}
    **API Stage:** {api_stage}
    **Total fases:** {total_phases}
    **Skill Version:** {SKILL_VERSION}
    
    ---
    
    ## 📋 Resumen
    
    Este directorio contiene la infraestructura de orquestación Strangler Fig:
    
    - **API Gateway** con routing por fases
    - **Lambda Authorizer** para validación JWT
    - **DynamoDB** para token blacklist (resuelve AP-token-blacklist)
    - **VPC Link** para acceso privado al monolito
    - **CloudWatch Logs** para monitoring
    
    **Endpoints totales:** {manifest['metadata']['total_endpoints']}
    **Fases de migración:** {total_phases}
    
    ---
    
    ## 🚀 Pasos de Despliegue
    
    ### Paso 1: Guardar JWT secret en SSM Parameter Store
    
    ⚠️ **CRÍTICO:** El JWT secret DEBE ser el MISMO que usa el monolito Flask.
    
    ```bash
    aws ssm put-parameter \\
      --name /taller/jwt-secret \\
      --value "{jwt_secret}" \\
      --type SecureString \\
      --description "JWT secret key para Authorizer" \\
      --region us-east-1
    ```
    
    ### Paso 2: Desplegar Lambda Authorizer (primero)
    
    ```bash
    cd authorizer
    pip install -r requirements.txt -t .
    cd ..
    
    aws cloudformation deploy \\
      --template-file template-authorizer.yaml \\
      --stack-name taller-authorizer \\
      --capabilities CAPABILITY_IAM \\
      --parameter-overrides \\
          EnvironmentName=taller \\
          JWTSecretKey={jwt_secret} \\
      --region us-east-1
    ```
    
    **Tiempo estimado:** 2-3 minutos
    
    ### Paso 3: Desplegar API Gateway (después de Authorizer)
    
    ```bash
    aws cloudformation deploy \\
      --template-file template-api-gateway.yaml \\
      --stack-name taller-api \\
      --capabilities CAPABILITY_IAM \\
      --parameter-overrides \\
          EnvironmentName=taller \\
          ApiStageName={api_stage} \\
          MonolithURL=<URL_DE_TU_MONOLITO> \\
      --region us-east-1
    ```
    
    **Tiempo estimado:** 5-7 minutos
    
    ### Paso 4: Obtener la URL de API Gateway
    
    ```bash
    aws cloudformation describe-stacks \\
      --stack-name taller-api \\
      --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \\
      --output text
    ```
    
    **Output ejemplo:** `https://abc123def.execute-api.us-east-1.amazonaws.com/prod`
    
    ---
    
    ## 🧪 Testing (Fase 0: Baseline)
    
    ### Test 1: Login (público)
    
    ```bash
    curl -X POST https://<api-gateway-url>/api/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{{"email": "admin@example.com", "password": "password123"}}'
    ```
    
    **Esperado:** Retorna JWT token (200 OK)
    
    ### Test 2: Endpoint protegido
    
    ```bash
    TOKEN="<token-del-login>"
    
    curl https://<api-gateway-url>/api/auth/me \\
      -H "Authorization: Bearer $TOKEN"
    ```
    
    **Esperado:** Retorna perfil del usuario (200 OK)
    
    ### Test 3: Logout (blacklist)
    
    ```bash
    curl -X POST https://<api-gateway-url>/api/auth/logout \\
      -H "Authorization: Bearer $TOKEN"
    ```
    
    **Esperado:** Token agregado a blacklist (200 OK)
    
    ### Test 4: Usar token revocado
    
    ```bash
    curl https://<api-gateway-url>/api/auth/me \\
      -H "Authorization: Bearer $TOKEN"
    ```
    
    **Esperado:** Authorizer niega acceso (403 Forbidden)
    
    ---
    
    ## 🔄 Migración por Fases (Strangler Fig)
    
    ### Fase 0: Baseline ✅ (actual)
    
    **Estado:** API Gateway enruta TODO al monolito
    
    **Acción:** Ninguna (ya desplegado)
    
    ---
    
    ### Fase 1: Migrar primer módulo
    
    **Módulo:** `{routing_rules['phases'][1]['name'] if len(routing_rules['phases']) > 1 else 'N/A'}`
    
    **Acciones:**
    1. Desplegar Lambdas del módulo (Skill 04 genera las funciones)
    2. Actualizar routing en API Gateway:
       ```bash
       python update_routing.py --phase 1
       ```
    3. Probar endpoints migrados
    4. Monitorear logs y métricas
    
    **Rollback:** Cambiar routing de vuelta a Fase 0
    
    ---
    
    ## 💰 Estimación de Costos (us-east-1)
    
    ### Costos fijos mensuales
    - **VPC Link:** $0.025/hora × 730 horas = **~$18/mes**
    
    ### Costos variables (por uso)
    - **API Gateway:** $3.50 por millón de requests
      - 1M req/mes: $3.50
      - 10M req/mes: $35
      - 100M req/mes: $350
    - **Lambda Authorizer:** $0.20 por millón de invocaciones + compute
      - Con cache (5 min), ~90% reducción
      - 1M req/mes → ~100K invocaciones → $0.02
    - **DynamoDB:** Pay-per-request
      - 1M reads: $0.25
      - 1M writes: $1.25
    - **Data Transfer:** $0.09/GB out
    
    **Total estimado (1M req/mes):** ~$25-30/mes  
    **Total estimado (10M req/mes):** ~$60-80/mes
    
    ---
    
    ## 🛠️ Troubleshooting
    
    ### Authorizer retorna 401 para todos los requests
    
    **Causa:** JWT secret diferente entre monolito y Authorizer
    
    **Solución:**
    1. Verificar secret en SSM:
       ```bash
       aws ssm get-parameter --name /taller/jwt-secret --with-decryption
       ```
    2. Comparar con `.env` del monolito
    3. Actualizar stack de Authorizer con el secret correcto
    
    ### API Gateway retorna 504 Timeout
    
    **Causa:** VPC Link no puede alcanzar el monolito
    
    **Solución:**
    1. Verificar que el NLB tiene targets registrados:
       ```bash
       aws elbv2 describe-target-health --target-group-arn <arn>
       ```
    2. Verificar security groups (VPC Link → NLB permitido)
    
    ### DynamoDB throttling
    
    **Causa:** Demasiadas escrituras/lecturas concurrentes
    
    **Solución:**
    - Ya configurado en On-Demand mode (escala automáticamente)
    - Si persiste, verificar que el cache del Authorizer está activo (300s)
    
    ---
    
    ## 📚 Referencias
    
    - [API Gateway VPC Links](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-private-integration.html)
    - [Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
    - [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
    
    ---
    
    **Generado por:** Skill 03 — Orquestador Strangler Fig  
    **Autor:** Luis Gerardo Sánchez Ordóñez  
    **Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
    **Institución:** Pontificia Universidad Javeriana Cali
    """)


if __name__ == "__main__":
    main()
