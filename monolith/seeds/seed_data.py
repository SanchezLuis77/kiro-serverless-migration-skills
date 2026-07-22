"""
Script de seed — Pobla la base de datos con datos de prueba.

Uso desde CLI:
  flask seed              # Inserta datos si la BD está vacía
  flask seed --reset      # Borra todo y reinicia

También puede ejecutarse como script directo:
  python seeds/seed_data.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random


def ejecutar_seed(app, reset: bool = False):
    """Función principal que orquesta la inserción de datos de prueba."""
    from app.extensions import db, bcrypt
    from app.models.usuario import Usuario
    from app.models.cliente import Cliente
    from app.models.servicio import Servicio
    from app.models.orden_trabajo import OrdenTrabajo, DetalleOrden

    with app.app_context():
        if reset:
            print("Eliminando datos existentes...")
            db.drop_all()
            db.create_all()
        else:
            db.create_all()

        # ------------------------------------------------------------------
        # USUARIOS (técnicos y administrador)
        # ------------------------------------------------------------------
        if Usuario.query.count() == 0:
            print("Insertando usuarios...")
            usuarios = [
                Usuario(
                    nombre='Carlos',
                    apellido='Mendoza',
                    email='admin@taller.com',
                    password_hash=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                    rol='admin',
                    activo=True,
                ),
                Usuario(
                    nombre='Juan',
                    apellido='Pérez',
                    email='juan.perez@taller.com',
                    password_hash=bcrypt.generate_password_hash('tecnico123').decode('utf-8'),
                    rol='tecnico',
                    activo=True,
                ),
                Usuario(
                    nombre='María',
                    apellido='García',
                    email='maria.garcia@taller.com',
                    password_hash=bcrypt.generate_password_hash('tecnico123').decode('utf-8'),
                    rol='tecnico',
                    activo=True,
                ),
                Usuario(
                    nombre='Luis',
                    apellido='Torres',
                    email='luis.torres@taller.com',
                    password_hash=bcrypt.generate_password_hash('tecnico123').decode('utf-8'),
                    rol='tecnico',
                    activo=False,  # Técnico inactivo para pruebas
                ),
            ]
            db.session.add_all(usuarios)
            db.session.commit()
            print(f"  >> {len(usuarios)} usuarios insertados")

        # ------------------------------------------------------------------
        # SERVICIOS (catálogo de reparaciones)
        # ------------------------------------------------------------------
        if Servicio.query.count() == 0:
            print("Insertando servicios...")
            servicios = [
                # Computación
                Servicio(nombre='Diagnóstico de laptop', descripcion='Diagnóstico completo de hardware y software',
                         precio_base=15000, tiempo_estimado_horas=1.0, categoria='computacion'),
                Servicio(nombre='Cambio de pantalla laptop', descripcion='Reemplazo de pantalla LCD/LED dañada',
                         precio_base=85000, tiempo_estimado_horas=2.0, categoria='computacion'),
                Servicio(nombre='Limpieza y mantenimiento PC', descripcion='Limpieza de polvo, pasta térmica y optimización',
                         precio_base=25000, tiempo_estimado_horas=1.5, categoria='computacion'),
                Servicio(nombre='Cambio de disco duro a SSD', descripcion='Migración de datos e instalación de SSD',
                         precio_base=45000, tiempo_estimado_horas=2.0, categoria='computacion'),
                Servicio(nombre='Reinstalación de sistema operativo', descripcion='Formateo y reinstalación de Windows/Linux',
                         precio_base=30000, tiempo_estimado_horas=3.0, categoria='computacion'),
                # Celular
                Servicio(nombre='Cambio de pantalla celular', descripcion='Reemplazo de pantalla rota o sin imagen',
                         precio_base=60000, tiempo_estimado_horas=1.0, categoria='celular'),
                Servicio(nombre='Cambio de batería celular', descripcion='Reemplazo de batería deteriorada',
                         precio_base=35000, tiempo_estimado_horas=0.5, categoria='celular'),
                Servicio(nombre='Reparación de conector de carga', descripcion='Soldadura o cambio del puerto USB',
                         precio_base=40000, tiempo_estimado_horas=1.5, categoria='celular'),
                # Electrodoméstico
                Servicio(nombre='Reparación de microondas', descripcion='Diagnóstico y reparación de microondas',
                         precio_base=30000, tiempo_estimado_horas=2.0, categoria='electrodomestico'),
                Servicio(nombre='Reparación de lavadora', descripcion='Diagnóstico y reparación de lavadora',
                         precio_base=50000, tiempo_estimado_horas=3.0, categoria='electrodomestico'),
                # Electrónico
                Servicio(nombre='Reparación de fuente de poder', descripcion='Diagnóstico y reparación de fuentes ATX',
                         precio_base=35000, tiempo_estimado_horas=2.0, categoria='electronico'),
                Servicio(nombre='Diagnóstico de placa madre', descripcion='Análisis de componentes y soldadura',
                         precio_base=40000, tiempo_estimado_horas=3.0, categoria='electronico'),
            ]
            db.session.add_all(servicios)
            db.session.commit()
            print(f"  >> {len(servicios)} servicios insertados")

        # ------------------------------------------------------------------
        # CLIENTES
        # ------------------------------------------------------------------
        if Cliente.query.count() == 0:
            print("Insertando clientes...")
            clientes = [
                Cliente(nombre='Ana', apellido='Rodríguez', email='ana.rodriguez@email.com',
                        telefono='+56912345678', direccion='Av. Providencia 1234, Santiago',
                        documento_identidad='12.345.678-9'),
                Cliente(nombre='Pedro', apellido='Soto', email='pedro.soto@gmail.com',
                        telefono='+56923456789', direccion='Calle Los Robles 567, Maipú',
                        documento_identidad='13.456.789-0'),
                Cliente(nombre='Valentina', apellido='López', email='vlopez@outlook.com',
                        telefono='+56934567890', direccion='Pasaje El Bosque 89, Ñuñoa',
                        documento_identidad='14.567.890-1'),
                Cliente(nombre='Roberto', apellido='Jiménez', email=None,
                        telefono='+56945678901', direccion='Los Conquistadores 456, Las Condes',
                        documento_identidad='15.678.901-2'),
                Cliente(nombre='Catalina', apellido='Fuentes', email='catifuentes@mail.com',
                        telefono='+56956789012', direccion='Av. Grecia 789, Macul',
                        documento_identidad='16.789.012-3'),
                Cliente(nombre='Diego', apellido='Morales', email='dmorales@empresa.cl',
                        telefono='+56967890123', direccion='Tobalaba 123, Providencia',
                        documento_identidad='17.890.123-4'),
                Cliente(nombre='Sofía', apellido='Castro', email='sofia.castro@web.cl',
                        telefono='+56978901234', direccion='Avda. Matta 567, Santiago Centro',
                        documento_identidad='18.901.234-5'),
            ]
            db.session.add_all(clientes)
            db.session.commit()
            print(f"  >> {len(clientes)} clientes insertados")

        # ------------------------------------------------------------------
        # ÓRDENES DE TRABAJO con detalles
        # ------------------------------------------------------------------
        if OrdenTrabajo.query.count() == 0:
            print("Insertando órdenes de trabajo...")

            tecnicos = Usuario.query.filter_by(rol='tecnico', activo=True).all()
            clientes_db = Cliente.query.all()
            servicios_db = Servicio.query.all()

            ordenes_data = [
                # Orden completada — laptop
                {
                    'cliente': clientes_db[0], 'tecnico': tecnicos[0],
                    'estado': 'completado',
                    'descripcion': 'Laptop no enciende, posible problema en placa madre o fuente.',
                    'tipo': 'Laptop', 'marca': 'HP', 'modelo': 'Pavilion 15',
                    'dias_atras': 15,
                    'servicios': [(servicios_db[0], 1), (servicios_db[11], 1)],  # Diagnóstico + placa
                },
                # Orden en reparación — celular
                {
                    'cliente': clientes_db[1], 'tecnico': tecnicos[0],
                    'estado': 'en_reparacion',
                    'descripcion': 'Pantalla rota después de caída. Táctil no responde.',
                    'tipo': 'Smartphone', 'marca': 'Samsung', 'modelo': 'Galaxy A54',
                    'dias_atras': 3,
                    'servicios': [(servicios_db[5], 1)],  # Cambio pantalla
                },
                # Orden pendiente — laptop
                {
                    'cliente': clientes_db[2], 'tecnico': None,
                    'estado': 'pendiente',
                    'descripcion': 'PC muy lento, tarda más de 5 minutos en iniciar.',
                    'tipo': 'PC Escritorio', 'marca': 'Genérico', 'modelo': 'AMD Ryzen',
                    'dias_atras': 1,
                    'servicios': [(servicios_db[2], 1), (servicios_db[3], 1)],  # Limpieza + SSD
                },
                # Orden en diagnóstico — microondas
                {
                    'cliente': clientes_db[3], 'tecnico': tecnicos[1],
                    'estado': 'en_diagnostico',
                    'descripcion': 'Microondas hace ruido pero no calienta. Posible magnetrón.',
                    'tipo': 'Microondas', 'marca': 'Mabe', 'modelo': 'KOR-6L0B',
                    'dias_atras': 2,
                    'servicios': [(servicios_db[8], 1)],  # Reparación microondas
                },
                # Orden completada — celular batería
                {
                    'cliente': clientes_db[4], 'tecnico': tecnicos[0],
                    'estado': 'completado',
                    'descripcion': 'Batería dura menos de 2 horas, se hinchó ligeramente.',
                    'tipo': 'Smartphone', 'marca': 'Apple', 'modelo': 'iPhone 12',
                    'dias_atras': 20,
                    'servicios': [(servicios_db[6], 1)],  # Cambio batería
                },
                # Orden completada — PC mantenimiento
                {
                    'cliente': clientes_db[5], 'tecnico': tecnicos[1],
                    'estado': 'completado',
                    'descripcion': 'Mantenimiento anual preventivo y actualización de SO.',
                    'tipo': 'Laptop', 'marca': 'Lenovo', 'modelo': 'IdeaPad 330',
                    'dias_atras': 8,
                    'servicios': [(servicios_db[2], 1), (servicios_db[4], 1)],  # Limpieza + reinstalación
                },
                # Orden cancelada
                {
                    'cliente': clientes_db[6], 'tecnico': None,
                    'estado': 'cancelado',
                    'descripcion': 'Lavadora no centrifuga. Cliente desistió de la reparación.',
                    'tipo': 'Lavadora', 'marca': 'Mademsa', 'modelo': 'Avant 9',
                    'dias_atras': 10,
                    'servicios': [(servicios_db[9], 1)],  # Reparación lavadora
                },
            ]

            for i, od in enumerate(ordenes_data):
                fecha_ingreso = datetime.utcnow() - timedelta(days=od['dias_atras'])
                numero = f"OT-{fecha_ingreso.strftime('%Y%m%d')}-{str(i+1).zfill(4)}"

                orden = OrdenTrabajo(
                    numero_orden=numero,
                    cliente_id=od['cliente'].id,
                    tecnico_id=od['tecnico'].id if od['tecnico'] else None,
                    estado=od['estado'],
                    descripcion_problema=od['descripcion'],
                    tipo_equipo=od['tipo'],
                    marca_equipo=od['marca'],
                    modelo_equipo=od['modelo'],
                    fecha_ingreso=fecha_ingreso,
                    fecha_estimada=fecha_ingreso + timedelta(days=5),
                    fecha_completado=fecha_ingreso + timedelta(days=random.randint(1, 4))
                    if od['estado'] == 'completado' else None,
                )
                db.session.add(orden)
                db.session.flush()

                total = 0.0
                for servicio, cantidad in od['servicios']:
                    detalle = DetalleOrden(
                        orden_id=orden.id,
                        servicio_id=servicio.id,
                        precio_unitario=servicio.precio_base,
                        cantidad=cantidad,
                    )
                    db.session.add(detalle)
                    total += float(servicio.precio_base) * cantidad

                orden.total = total

            db.session.commit()
            print(f"  >> {len(ordenes_data)} ordenes de trabajo insertadas")

        print("\nSeed completado. Credenciales de prueba:")
        print("  Admin:   admin@taller.com        / admin123")
        print("  Tecnico: juan.perez@taller.com   / tecnico123")
        print("  Tecnico: maria.garcia@taller.com / tecnico123")


if __name__ == '__main__':
    # Permite ejecutar directamente: python seeds/seed_data.py
    from app import create_app
    app = create_app('development')
    ejecutar_seed(app, reset='--reset' in sys.argv)
