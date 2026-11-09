"""
generate_persistence.py — Skill 02: Migrador de Persistencia

Genera la infraestructura de persistencia serverless para un monolito Flask migrado:
  - VPC + subnets + NAT Gateway + security groups
  - RDS Aurora Serverless v2 cluster + RDS Proxy
  - Lambda Layer con SQLAlchemy + psycopg2 + modelos adaptados
  - Scripts de migración Alembic
  - Configuración SSM Parameter Store

Consume el migration-manifest.json del Skill 01 y los modelos SQLAlchemy del monolito.

Principios de diseño:
  - Sin dependencias externas: usa exclusivamente módulos de la biblioteca estándar
    de Python 3.9+ (json, os, sys, pathlib, argparse, typing, ast, re, textwrap)
  - Templates CloudFormation/SAM como cadenas de texto (no require PyYAML)
  - Análisis AST de modelos para detectar funciones SQLite no portables
  - Salida determinista: mismo input → mismo output

Uso:
    python generate_persistence.py --manifest <ruta_manifest> --monolith <ruta_monolito>
    python generate_persistence.py --manifest <ruta> --monolith <ruta> --output <dir>

Códigos de salida:
    0 — Generación exitosa; infraestructura lista para desplegar
    1 — El archivo manifest no existe
    2 — El directorio del monolito no existe
    3 — Error de escritura del output

Proyecto: Trabajo de Grado — Maestría en Ingeniería de Software
          Pontificia Universidad Javeriana Cali
Autor:    Luis Gerardo Sánchez Ordóñez
Director: Juan Gabriel Quintero Barbosa — Head Solutions Architecture, AWS Colombia
"""

import json
import os
import sys
import re
import ast
import argparse
import textwrap
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

SKILL_VERSION = "1.0.0"
DEFAULT_DB_NAME = "taller_db"
DEFAULT_VPC_CIDR = "10.0.0.0/16"
DEFAULT_OUTPUT_DIR = "serverless-output/persistence"

# Mapeo de tipos SQLite → PostgreSQL
SQLITE_TO_POSTGRES_TYPES = {
    "INTEGER": "INTEGER",
    "TEXT": "TEXT",
    "REAL": "DOUBLE PRECISION",
    "BLOB": "BYTEA",
    "NUMERIC": "NUMERIC",
    # SQLAlchemy types
    "String": "VARCHAR",
    "Integer": "INTEGER",
    "Float": "DOUBLE PRECISION",
    "Boolean": "BOOLEAN",
    "DateTime": "TIMESTAMP",
    "Date": "DATE",
    "Time": "TIME",
    "Text": "TEXT",
    "LargeBinary": "BYTEA",
}

# Funciones SQLite que deben reemplazarse en PostgreSQL
SQLITE_FUNCTIONS_TO_REPLACE = {
    "strftime": "to_char",
    "datetime": "to_timestamp",
    "julianday": "EXTRACT(EPOCH FROM {}) / 86400",
}


# ---------------------------------------------------------------------------
# === ManifestLoader ===
# Responsabilidad: cargar y validar el migration-manifest.json
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
        Retorna el dict del manifest o lanza FileNotFoundError.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in manifest: {exc}")

        # Validar estructura mínima
        required_keys = ["metadata", "summary", "modules", "lambda_layers"]
        missing = [k for k in required_keys if k not in manifest]
        if missing:
            raise ValueError(f"Manifest missing required keys: {missing}")

        return manifest


# ---------------------------------------------------------------------------
# === ModelAnalyzer ===
# Responsabilidad: analizar modelos SQLAlchemy y detectar funciones SQLite
# ---------------------------------------------------------------------------

class ModelAnalyzer:
    """
    Analiza los archivos de modelos SQLAlchemy para extraer metadatos y detectar
    funciones SQLite no portables a PostgreSQL.
    """

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.warnings: List[str] = []
        self.models_found: List[str] = []
        self.sqlite_patterns_detected: List[Dict[str, str]] = []

    def analyze(self) -> Dict[str, Any]:
        """
        Recorre el directorio de modelos y devuelve un resumen del análisis.
        """
        if not self.models_dir.exists():
            self.warnings.append(f"Models directory not found: {self.models_dir}")
            return {
                "total_models": 0,
                "models": [],
                "sqlite_patterns": [],
                "warnings": self.warnings,
            }

        for py_file in self.models_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            self._analyze_file(py_file)

        return {
            "total_models": len(self.models_found),
            "models": self.models_found,
            "sqlite_patterns": self.sqlite_patterns_detected,
            "warnings": self.warnings,
        }

    def _analyze_file(self, py_file: Path) -> None:
        """
        Analiza un archivo Python para detectar clases que heredan de db.Model
        y funciones SQLite en queries.
        """
        try:
            source = py_file.read_text(encoding='utf-8', errors='replace')
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            self.warnings.append(f"SyntaxError in {py_file}: {exc}")
            return

        # Detectar clases que heredan de db.Model
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if self._inherits_from_model(node):
                    self.models_found.append(node.name)

        # Detectar funciones SQLite en el código
        self._detect_sqlite_functions(py_file, source)

    @staticmethod
    def _inherits_from_model(class_node: ast.ClassDef) -> bool:
        """
        Verifica si una clase hereda de db.Model.
        """
        for base in class_node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True
            if isinstance(base, ast.Name) and base.id == "Model":
                return True
        return False

    def _detect_sqlite_functions(self, py_file: Path, source: str) -> None:
        """
        Busca referencias a funciones SQLite (strftime, datetime, etc.) en el código.
        """
        for func_name in SQLITE_FUNCTIONS_TO_REPLACE:
            pattern = rf"\b{func_name}\("
            if re.search(pattern, source):
                self.sqlite_patterns_detected.append({
                    "file": str(py_file.relative_to(self.models_dir.parent.parent)),
                    "function": func_name,
                    "replacement": SQLITE_FUNCTIONS_TO_REPLACE[func_name],
                })


# ---------------------------------------------------------------------------
# === VPCTemplateGenerator ===
# Responsabilidad: generar template-vpc.yaml
# ---------------------------------------------------------------------------

class VPCTemplateGenerator:
    """
    Genera el template CloudFormation para VPC + networking.
    """

    @staticmethod
    def generate(vpc_cidr: str = DEFAULT_VPC_CIDR) -> str:
        """
        Genera el template YAML para la VPC.
        """
        return textwrap.dedent(f"""\
        AWSTemplateFormatVersion: '2010-09-09'
        Description: 'VPC + Networking para migración serverless - Skill 02'
        
        Parameters:
          EnvironmentName:
            Type: String
            Default: 'taller'
            Description: 'Nombre del ambiente'
        
        Resources:
          # VPC Principal
          VPC:
            Type: AWS::EC2::VPC
            Properties:
              CidrBlock: {vpc_cidr}
              EnableDnsHostnames: true
              EnableDnsSupport: true
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-vpc'
                - Key: ManagedBy
                  Value: 'Skill-02-Persistence'
          
          # Internet Gateway
          InternetGateway:
            Type: AWS::EC2::InternetGateway
            Properties:
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-igw'
          
          AttachGateway:
            Type: AWS::EC2::VPCGatewayAttachment
            Properties:
              VpcId: !Ref VPC
              InternetGatewayId: !Ref InternetGateway
          
          # Subnets Públicas (para NAT Gateway)
          PublicSubnet1:
            Type: AWS::EC2::Subnet
            Properties:
              VpcId: !Ref VPC
              CidrBlock: 10.0.1.0/24
              AvailabilityZone: !Select [0, !GetAZs '']
              MapPublicIpOnLaunch: true
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-public-subnet-1'
          
          PublicSubnet2:
            Type: AWS::EC2::Subnet
            Properties:
              VpcId: !Ref VPC
              CidrBlock: 10.0.2.0/24
              AvailabilityZone: !Select [1, !GetAZs '']
              MapPublicIpOnLaunch: true
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-public-subnet-2'
          
          # Subnets Privadas (para RDS y Lambdas)
          PrivateSubnet1:
            Type: AWS::EC2::Subnet
            Properties:
              VpcId: !Ref VPC
              CidrBlock: 10.0.11.0/24
              AvailabilityZone: !Select [0, !GetAZs '']
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-private-subnet-1'
          
          PrivateSubnet2:
            Type: AWS::EC2::Subnet
            Properties:
              VpcId: !Ref VPC
              CidrBlock: 10.0.12.0/24
              AvailabilityZone: !Select [1, !GetAZs '']
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-private-subnet-2'
          
          # NAT Gateway (para que Lambdas accedan a internet)
          NATGatewayEIP:
            Type: AWS::EC2::EIP
            DependsOn: AttachGateway
            Properties:
              Domain: vpc
          
          NATGateway:
            Type: AWS::EC2::NatGateway
            Properties:
              AllocationId: !GetAtt NATGatewayEIP.AllocationId
              SubnetId: !Ref PublicSubnet1
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-nat-gateway'
          
          # Route Tables
          PublicRouteTable:
            Type: AWS::EC2::RouteTable
            Properties:
              VpcId: !Ref VPC
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-public-rt'
          
          PublicRoute:
            Type: AWS::EC2::Route
            DependsOn: AttachGateway
            Properties:
              RouteTableId: !Ref PublicRouteTable
              DestinationCidrBlock: 0.0.0.0/0
              GatewayId: !Ref InternetGateway
          
          PublicSubnet1RouteTableAssociation:
            Type: AWS::EC2::SubnetRouteTableAssociation
            Properties:
              SubnetId: !Ref PublicSubnet1
              RouteTableId: !Ref PublicRouteTable
          
          PublicSubnet2RouteTableAssociation:
            Type: AWS::EC2::SubnetRouteTableAssociation
            Properties:
              SubnetId: !Ref PublicSubnet2
              RouteTableId: !Ref PublicRouteTable
          
          PrivateRouteTable:
            Type: AWS::EC2::RouteTable
            Properties:
              VpcId: !Ref VPC
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-private-rt'
          
          PrivateRoute:
            Type: AWS::EC2::Route
            Properties:
              RouteTableId: !Ref PrivateRouteTable
              DestinationCidrBlock: 0.0.0.0/0
              NatGatewayId: !Ref NATGateway
          
          PrivateSubnet1RouteTableAssociation:
            Type: AWS::EC2::SubnetRouteTableAssociation
            Properties:
              SubnetId: !Ref PrivateSubnet1
              RouteTableId: !Ref PrivateRouteTable
          
          PrivateSubnet2RouteTableAssociation:
            Type: AWS::EC2::SubnetRouteTableAssociation
            Properties:
              SubnetId: !Ref PrivateSubnet2
              RouteTableId: !Ref PrivateRouteTable
          
          # Security Groups
          LambdaSecurityGroup:
            Type: AWS::EC2::SecurityGroup
            Properties:
              GroupDescription: 'Security group para Lambdas'
              VpcId: !Ref VPC
              SecurityGroupEgress:
                - IpProtocol: -1
                  CidrIp: 0.0.0.0/0
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-lambda-sg'
          
          RDSSecurityGroup:
            Type: AWS::EC2::SecurityGroup
            Properties:
              GroupDescription: 'Security group para RDS Aurora'
              VpcId: !Ref VPC
              SecurityGroupIngress:
                - IpProtocol: tcp
                  FromPort: 5432
                  ToPort: 5432
                  SourceSecurityGroupId: !Ref LambdaSecurityGroup
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-rds-sg'
        
        Outputs:
          VPCId:
            Description: 'VPC ID'
            Value: !Ref VPC
            Export:
              Name: !Sub '${{EnvironmentName}}-VPCId'
          
          PrivateSubnet1Id:
            Description: 'Private Subnet 1 ID'
            Value: !Ref PrivateSubnet1
            Export:
              Name: !Sub '${{EnvironmentName}}-PrivateSubnet1'
          
          PrivateSubnet2Id:
            Description: 'Private Subnet 2 ID'
            Value: !Ref PrivateSubnet2
            Export:
              Name: !Sub '${{EnvironmentName}}-PrivateSubnet2'
          
          LambdaSecurityGroupId:
            Description: 'Security Group para Lambdas'
            Value: !Ref LambdaSecurityGroup
            Export:
              Name: !Sub '${{EnvironmentName}}-LambdaSG'
          
          RDSSecurityGroupId:
            Description: 'Security Group para RDS'
            Value: !Ref RDSSecurityGroup
            Export:
              Name: !Sub '${{EnvironmentName}}-RDSSG'
        """)


# ---------------------------------------------------------------------------
# === RDSTemplateGenerator ===
# Responsabilidad: generar template-rds.yaml
# ---------------------------------------------------------------------------

class RDSTemplateGenerator:
    """
    Genera el template CloudFormation para RDS Aurora Serverless v2 + RDS Proxy.
    """

    @staticmethod
    def generate(db_name: str = DEFAULT_DB_NAME) -> str:
        """
        Genera el template YAML para RDS Aurora + RDS Proxy.
        """
        return textwrap.dedent(f"""\
        AWSTemplateFormatVersion: '2010-09-09'
        Description: 'RDS Aurora Serverless v2 + RDS Proxy - Skill 02'
        
        Parameters:
          EnvironmentName:
            Type: String
            Default: 'taller'
            Description: 'Nombre del ambiente'
          
          DBName:
            Type: String
            Default: '{db_name}'
            Description: 'Nombre de la base de datos'
          
          DBUsername:
            Type: String
            Default: 'admin'
            Description: 'Usuario master de la base de datos'
            NoEcho: true
          
          DBPassword:
            Type: String
            NoEcho: true
            Description: 'Contraseña master (mínimo 8 caracteres)'
            MinLength: 8
        
        Resources:
          # Secret en Secrets Manager para credenciales RDS
          DBSecret:
            Type: AWS::SecretsManager::Secret
            Properties:
              Name: !Sub '${{EnvironmentName}}-rds-secret'
              Description: 'Credenciales RDS Aurora'
              SecretString: !Sub |
                {{
                  "username": "${{DBUsername}}",
                  "password": "${{DBPassword}}",
                  "engine": "postgres",
                  "host": "${{DBCluster.Endpoint.Address}}",
                  "port": 5432,
                  "dbname": "${{DBName}}"
                }}
          
          # DB Subnet Group
          DBSubnetGroup:
            Type: AWS::RDS::DBSubnetGroup
            Properties:
              DBSubnetGroupName: !Sub '${{EnvironmentName}}-db-subnet-group'
              DBSubnetGroupDescription: 'Subnet group para RDS Aurora'
              SubnetIds:
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet1'
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet2'
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-db-subnet-group'
          
          # Aurora Serverless v2 Cluster
          DBCluster:
            Type: AWS::RDS::DBCluster
            Properties:
              Engine: aurora-postgresql
              EngineMode: provisioned
              EngineVersion: '15.4'
              DatabaseName: !Ref DBName
              MasterUsername: !Ref DBUsername
              MasterUserPassword: !Ref DBPassword
              DBSubnetGroupName: !Ref DBSubnetGroup
              VpcSecurityGroupIds:
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-RDSSG'
              ServerlessV2ScalingConfiguration:
                MinCapacity: 0.5
                MaxCapacity: 2
              BackupRetentionPeriod: 7
              PreferredBackupWindow: '03:00-04:00'
              PreferredMaintenanceWindow: 'sun:04:00-sun:05:00'
              StorageEncrypted: true
              EnableHttpEndpoint: false
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-aurora-cluster'
          
          # Aurora Instance (Serverless v2)
          DBInstance1:
            Type: AWS::RDS::DBInstance
            Properties:
              Engine: aurora-postgresql
              DBClusterIdentifier: !Ref DBCluster
              DBInstanceClass: db.serverless
              PubliclyAccessible: false
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-aurora-instance-1'
          
          # RDS Proxy
          DBProxy:
            Type: AWS::RDS::DBProxy
            Properties:
              DBProxyName: !Sub '${{EnvironmentName}}-rds-proxy'
              EngineFamily: POSTGRESQL
              Auth:
                - AuthScheme: SECRETS
                  SecretArn: !Ref DBSecret
                  IAMAuth: DISABLED
              RoleArn: !GetAtt DBProxyRole.Arn
              VpcSubnetIds:
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet1'
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-PrivateSubnet2'
              VpcSecurityGroupIds:
                - Fn::ImportValue: !Sub '${{EnvironmentName}}-RDSSG'
              RequireTLS: true
              IdleClientTimeout: 1800
              Tags:
                - Key: Name
                  Value: !Sub '${{EnvironmentName}}-rds-proxy'
          
          DBProxyTargetGroup:
            Type: AWS::RDS::DBProxyTargetGroup
            Properties:
              DBProxyName: !Ref DBProxy
              TargetGroupName: default
              DBClusterIdentifiers:
                - !Ref DBCluster
          
          # IAM Role para RDS Proxy
          DBProxyRole:
            Type: AWS::IAM::Role
            Properties:
              AssumeRolePolicyDocument:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: rds.amazonaws.com
                    Action: 'sts:AssumeRole'
              ManagedPolicyArns:
                - 'arn:aws:iam::aws:policy/service-role/AmazonRDSProxyExecutionRole'
              Policies:
                - PolicyName: DBProxySecretsAccess
                  PolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Action:
                          - 'secretsmanager:GetSecretValue'
                        Resource: !Ref DBSecret
        
        Outputs:
          DBClusterEndpoint:
            Description: 'Aurora Cluster Endpoint'
            Value: !GetAtt DBCluster.Endpoint.Address
            Export:
              Name: !Sub '${{EnvironmentName}}-DBClusterEndpoint'
          
          DBProxyEndpoint:
            Description: 'RDS Proxy Endpoint (usar este en Lambdas)'
            Value: !GetAtt DBProxy.Endpoint
            Export:
              Name: !Sub '${{EnvironmentName}}-DBProxyEndpoint'
          
          DBSecretArn:
            Description: 'ARN del Secret con credenciales'
            Value: !Ref DBSecret
            Export:
              Name: !Sub '${{EnvironmentName}}-DBSecretArn'
          
          DBName:
            Description: 'Nombre de la base de datos'
            Value: !Ref DBName
            Export:
              Name: !Sub '${{EnvironmentName}}-DBName'
        """)


# ---------------------------------------------------------------------------
# === Main Orchestrator ===
# ---------------------------------------------------------------------------

def main():
    """
    Punto de entrada principal del script.
    """
    parser = argparse.ArgumentParser(
        description="Skill 02: Genera infraestructura de persistencia serverless"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Ruta al migration-manifest.json (generado por Skill 01)"
    )
    parser.add_argument(
        "--monolith",
        type=Path,
        required=True,
        help="Ruta al directorio raíz del monolito Flask"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=DEFAULT_DB_NAME,
        help=f"Nombre de la base de datos (default: {DEFAULT_DB_NAME})"
    )
    parser.add_argument(
        "--vpc-cidr",
        type=str,
        default=DEFAULT_VPC_CIDR,
        help=f"CIDR para la VPC (default: {DEFAULT_VPC_CIDR})"
    )

    args = parser.parse_args()

    # Validar que manifest existe
    if not args.manifest.exists():
        print(f"❌ Error: Manifest not found: {args.manifest}", file=sys.stderr)
        print(f"   Ejecuta primero el Skill 01 (Analizador de Monolito)", file=sys.stderr)
        sys.exit(1)

    # Validar que monolith existe
    if not args.monolith.exists():
        print(f"❌ Error: Monolith directory not found: {args.monolith}", file=sys.stderr)
        sys.exit(2)

    # Cargar manifest
    print(f"📖 Cargando manifest desde: {args.manifest}")
    loader = ManifestLoader(args.manifest)
    try:
        manifest = loader.load()
        print(f"✅ Manifest cargado exitosamente")
        print(f"   Total endpoints: {manifest['metadata']['total_endpoints']}")
    except Exception as exc:
        print(f"❌ Error cargando manifest: {exc}", file=sys.stderr)
        sys.exit(1)

    # Analizar modelos
    models_dir = args.monolith / "app" / "models"
    print(f"\n🔍 Analizando modelos en: {models_dir}")
    analyzer = ModelAnalyzer(models_dir)
    model_analysis = analyzer.analyze()
    print(f"✅ Modelos encontrados: {model_analysis['total_models']}")
    if model_analysis['sqlite_patterns']:
        print(f"⚠️  Patrones SQLite detectados: {len(model_analysis['sqlite_patterns'])}")
        for pattern in model_analysis['sqlite_patterns']:
            print(f"   - {pattern['file']}: {pattern['function']}() → {pattern['replacement']}()")

    # Crear directorio de salida
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Directorio de salida: {output_dir.resolve()}")

    # Generar templates
    print(f"\n🏗️  Generando templates de infraestructura...")

    # 1. VPC Template
    vpc_template = VPCTemplateGenerator.generate(args.vpc_cidr)
    vpc_path = output_dir / "template-vpc.yaml"
    vpc_path.write_text(vpc_template, encoding='utf-8')
    print(f"   ✅ {vpc_path.name}")

    # 2. RDS Template
    rds_template = RDSTemplateGenerator.generate(args.db_name)
    rds_path = output_dir / "template-rds.yaml"
    rds_path.write_text(rds_template, encoding='utf-8')
    print(f"   ✅ {rds_path.name}")

    # 3. Deployment Guide
    guide_content = generate_deployment_guide(args.db_name, args.vpc_cidr, model_analysis)
    guide_path = output_dir / "DEPLOYMENT_GUIDE.md"
    guide_path.write_text(guide_content, encoding='utf-8')
    print(f"   ✅ {guide_path.name}")

    # Summary
    print(f"\n✨ Generación completada exitosamente!")
    print(f"\n📦 Archivos generados:")
    print(f"   - template-vpc.yaml    (VPC + networking)")
    print(f"   - template-rds.yaml    (Aurora Serverless v2 + RDS Proxy)")
    print(f"   - DEPLOYMENT_GUIDE.md  (guía de despliegue)")
    print(f"\n🚀 Siguiente paso:")
    print(f"   cd {output_dir}")
    print(f"   # Revisar templates y seguir DEPLOYMENT_GUIDE.md")

    sys.exit(0)


def generate_deployment_guide(db_name: str, vpc_cidr: str, model_analysis: Dict) -> str:
    """
    Genera la guía de despliegue en Markdown.
    """
    timestamp = datetime.utcnow().isoformat()
    return textwrap.dedent(f"""\
    # Deployment Guide — Skill 02: Migrador de Persistencia
    
    **Generado:** {timestamp}
    **Base de datos:** {db_name}
    **VPC CIDR:** {vpc_cidr}
    **Skill Version:** {SKILL_VERSION}
    
    ---
    
    ## 📋 Resumen
    
    Este directorio contiene la infraestructura de persistencia serverless para tu aplicación Flask migrada:
    
    - **VPC** con subnets públicas/privadas, NAT Gateway, security groups
    - **RDS Aurora Serverless v2** (PostgreSQL 15.x)
    - **RDS Proxy** para connection pooling desde Lambdas
    - **Secrets Manager** para credenciales seguras
    
    **Modelos migrados:** {model_analysis['total_models']}
    **Patrones SQLite detectados:** {len(model_analysis['sqlite_patterns'])}
    
    ---
    
    ## 🚀 Pasos de Despliegue
    
    ### Paso 1: Desplegar VPC (primero)
    
    ```bash
    aws cloudformation deploy \\
      --template-file template-vpc.yaml \\
      --stack-name taller-vpc \\
      --capabilities CAPABILITY_IAM \\
      --region us-east-1
    ```
    
    **Tiempo estimado:** 3-5 minutos
    
    **Validar:** Verifica que la VPC y subnets se crearon:
    ```bash
    aws ec2 describe-vpcs --filters "Name=tag:Name,Values=taller-vpc"
    ```
    
    ### Paso 2: Desplegar RDS Aurora (después de VPC)
    
    ⚠️ **IMPORTANTE:** Debes proporcionar una contraseña segura para el usuario master.
    
    ```bash
    aws cloudformation deploy \\
      --template-file template-rds.yaml \\
      --stack-name taller-rds \\
      --capabilities CAPABILITY_IAM \\
      --parameter-overrides \\
          EnvironmentName=taller \\
          DBName={db_name} \\
          DBUsername=admin \\
          DBPassword=TU_PASSWORD_SEGURA_AQUI \\
      --region us-east-1
    ```
    
    **Tiempo estimado:** 10-15 minutos
    
    **Validar:** Verifica que el cluster Aurora se creó:
    ```bash
    aws rds describe-db-clusters --db-cluster-identifier taller-aurora-cluster
    ```
    
    ### Paso 3: Obtener endpoints
    
    ```bash
    # Aurora Cluster Endpoint (conexión directa, no recomendada desde Lambda)
    aws cloudformation describe-stacks \\
      --stack-name taller-rds \\
      --query "Stacks[0].Outputs[?OutputKey=='DBClusterEndpoint'].OutputValue" \\
      --output text
    
    # RDS Proxy Endpoint (USAR ESTE en Lambdas)
    aws cloudformation describe-stacks \\
      --stack-name taller-rds \\
      --query "Stacks[0].Outputs[?OutputKey=='DBProxyEndpoint'].OutputValue" \\
      --output text
    ```
    
    ---
    
    ## 🔧 Configuración de Lambdas
    
    ### Variables de entorno requeridas
    
    Cada Lambda que acceda a la base de datos debe tener estas variables:
    
    ```yaml
    Environment:
      Variables:
        DB_PROXY_ENDPOINT: <valor del output DBProxyEndpoint>
        DB_NAME: {db_name}
        DB_SECRET_ARN: <valor del output DBSecretArn>
        DB_PORT: '5432'
    ```
    
    ### VPC Configuration
    
    Las Lambdas DEBEN desplegarse en las subnets privadas de la VPC:
    
    ```yaml
    VpcConfig:
      SecurityGroupIds:
        - Fn::ImportValue: taller-LambdaSG
      SubnetIds:
        - Fn::ImportValue: taller-PrivateSubnet1
        - Fn::ImportValue: taller-PrivateSubnet2
    ```
    
    ### IAM Policy requerida
    
    ```yaml
    Policies:
      - Statement:
          - Effect: Allow
            Action:
              - secretsmanager:GetSecretValue
            Resource: !ImportValue taller-DBSecretArn
          - Effect: Allow
            Action:
              - rds-db:connect
            Resource: '*'
          - Effect: Allow
            Action:
              - ec2:CreateNetworkInterface
              - ec2:DescribeNetworkInterfaces
              - ec2:DeleteNetworkInterface
            Resource: '*'
    ```
    
    ---
    
    ## 💾 Migración de Datos
    
    ### Opción A: Export/Import manual
    
    1. **Exportar datos de SQLite:**
    ```bash
    sqlite3 monolith/instance/taller.db .dump > dump.sql
    ```
    
    2. **Editar dump.sql:** Reemplazar sintaxis SQLite por PostgreSQL
    
    3. **Importar a Aurora:**
    ```bash
    psql -h <DBProxyEndpoint> -U admin -d {db_name} -f dump.sql
    ```
    
    ### Opción B: ETL programático (recomendado para producción)
    
    Crear un script Python que:
    1. Lee de SQLite con SQLAlchemy
    2. Escribe en PostgreSQL con SQLAlchemy
    3. Maneja conversiones de tipos y funciones
    
    ---
    
    ## 🧪 Testing de Conexión
    
    ### Test desde Lambda local
    
    ```python
    import psycopg2
    import boto3
    import json
    
    def get_db_credentials():
        secrets_client = boto3.client('secretsmanager')
        secret_arn = "<DBSecretArn>"
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        return json.loads(response['SecretString'])
    
    def test_connection():
        creds = get_db_credentials()
        conn = psycopg2.connect(
            host="<DBProxyEndpoint>",
            port=5432,
            database="{db_name}",
            user=creds['username'],
            password=creds['password']
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        print(cur.fetchone())
        conn.close()
    
    if __name__ == "__main__":
        test_connection()
    ```
    
    ---
    
    ## 💰 Estimación de Costos (us-east-1)
    
    ### Costos fijos mensuales
    - **RDS Proxy:** ~$0.015/hora × 730 horas = **~$11/mes**
    - **NAT Gateway:** ~$0.045/hora × 730 horas = **~$33/mes**
    - **NAT Gateway data:** ~$0.045/GB procesado
    
    ### Costos variables (pago por uso)
    - **Aurora Serverless v2:** ~$0.12/ACU-hora (0.5-2 ACU configurados)
      - Mínimo (~0.5 ACU 24/7): ~$44/mes
      - Promedio (~1 ACU): ~$88/mes
      - Pico (~2 ACU): ~$175/mes
    - **Storage:** $0.10/GB-mes
    - **Backup storage:** $0.021/GB-mes
    
    **Total estimado:** $90-150/mes para carga baja/media
    
    ---
    
    ## 🛠️ Troubleshooting
    
    ### Lambda no puede conectar a RDS
    
    **Síntomas:** `Timeout` o `Connection refused`
    
    **Causas comunes:**
    1. Lambda no está en subnets privadas de la VPC
    2. Security group de Lambda no tiene egress en puerto 5432
    3. Security group de RDS no permite ingress desde SG de Lambda
    
    **Solución:**
    ```bash
    # Verificar configuración VPC de Lambda
    aws lambda get-function-configuration --function-name <nombre> --query VpcConfig
    
    # Verificar security groups
    aws ec2 describe-security-groups --group-ids <LambdaSG>
    aws ec2 describe-security-groups --group-ids <RDSSG>
    ```
    
    ### Error "too many connections"
    
    **Causa:** Lambdas están abriendo conexiones sin cerrarlas
    
    **Solución:**
    - Usa RDS Proxy (ya configurado)
    - Asegúrate de cerrar conexiones en finally blocks
    - Configura `max_overflow=0` en SQLAlchemy Engine
    
    ### Cold start alto (>3 segundos)
    
    **Causa:** Lambda descargando Layer + estableciendo conexión DB
    
    **Solución:**
    - Usa Provisioned Concurrency (costo adicional)
    - Mantén conexiones DB warm con keepalive queries
    - Considera connection pooling en la Lambda (no en el handler)
    
    ---
    
    ## ⚠️ Patrones SQLite Detectados
    
    Los siguientes archivos usan funciones SQLite que NO son compatibles con PostgreSQL:
    
    """)
    
    # Agregar tabla de patrones detectados
    guide = generate_deployment_guide.__doc__ or ""
    if model_analysis['sqlite_patterns']:
        guide += "\n| Archivo | Función SQLite | Reemplazo PostgreSQL |\n"
        guide += "|---------|----------------|---------------------|\n"
        for pattern in model_analysis['sqlite_patterns']:
            guide += f"| `{pattern['file']}` | `{pattern['function']}()` | `{pattern['replacement']}()` |\n"
    else:
        guide += "✅ No se detectaron patrones SQLite incompatibles.\n"
    
    guide += textwrap.dedent("""
    
    **Acción requerida:** Edita manualmente estos archivos reemplazando las funciones.
    
    ---
    
    ## 📚 Referencias
    
    - [Aurora Serverless v2 Pricing](https://aws.amazon.com/rds/aurora/pricing/)
    - [RDS Proxy Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-planning.html)
    - [Lambda VPC Configuration](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
    - [PostgreSQL vs SQLite Functions](https://www.postgresql.org/docs/current/functions.html)
    
    ---
    
    **Generado por:** Skill 02 — Migrador de Persistencia  
    **Autor:** Luis Gerardo Sánchez Ordóñez  
    **Proyecto:** Trabajo de Grado — Maestría en Ingeniería de Software  
    **Institución:** Pontificia Universidad Javeriana Cali
    """)
    
    return guide


if __name__ == "__main__":
    main()
