"""
Tests básicos de humo para verificar que la aplicación arranca
y los endpoints principales responden correctamente.

Ejecutar con:
  python -m pytest tests/ -v
"""
import pytest
import json
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope='session')
def app():
    """Crea la aplicación Flask en modo testing con BD en memoria."""
    app = create_app('development')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'JWT_SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })
    with app.app_context():
        _db.create_all()
        # Insertar datos mínimos
        from seeds.seed_data import ejecutar_seed
        ejecutar_seed(app, reset=False)
        yield app
        _db.drop_all()


@pytest.fixture(scope='session')
def client(app):
    """Cliente HTTP de testing."""
    return app.test_client()


@pytest.fixture(scope='session')
def token_admin(client):
    """Obtiene un token JWT de admin para los tests."""
    resp = client.post('/api/auth/login', json={
        'email': 'admin@taller.com',
        'password': 'admin123'
    })
    data = resp.get_json()
    return data['datos']['access_token']


@pytest.fixture(scope='session')
def token_tecnico(client):
    """Obtiene un token JWT de técnico para los tests."""
    resp = client.post('/api/auth/login', json={
        'email': 'juan.perez@taller.com',
        'password': 'tecnico123'
    })
    data = resp.get_json()
    return data['datos']['access_token']


# -----------------------------------------------------------------------
# Tests de autenticación
# -----------------------------------------------------------------------

class TestAuth:
    def test_login_exitoso(self, client):
        resp = client.post('/api/auth/login', json={
            'email': 'admin@taller.com',
            'password': 'admin123'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert 'access_token' in data['datos']

    def test_login_credenciales_invalidas(self, client):
        resp = client.post('/api/auth/login', json={
            'email': 'admin@taller.com',
            'password': 'wrong-password'
        })
        assert resp.status_code == 401

    def test_perfil_requiere_jwt(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401

    def test_perfil_con_jwt_valido(self, client, token_admin):
        resp = client.get('/api/auth/me',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['datos']['email'] == 'admin@taller.com'

    def test_register_nuevo_usuario(self, client, token_admin):
        resp = client.post('/api/auth/register', json={
            'nombre': 'Test',
            'apellido': 'Usuario',
            'email': 'test.usuario@taller.com',
            'password': 'test123',
            'rol': 'tecnico'
        })
        assert resp.status_code == 201


# -----------------------------------------------------------------------
# Tests de clientes
# -----------------------------------------------------------------------

class TestClientes:
    def test_listar_requiere_jwt(self, client):
        resp = client.get('/api/clientes/')
        assert resp.status_code == 401

    def test_listar_clientes(self, client, token_admin):
        resp = client.get('/api/clientes/',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'items' in data['datos']
        assert data['datos']['total'] >= 0

    def test_crear_cliente(self, client, token_admin):
        resp = client.post('/api/clientes/', json={
            'nombre': 'Nuevo',
            'apellido': 'Cliente',
            'telefono': '+56999999999',
            'email': 'nuevo.cliente@test.com'
        }, headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 201

    def test_buscar_cliente_por_nombre(self, client, token_admin):
        resp = client.get('/api/clientes/?q=Ana',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Tests de servicios
# -----------------------------------------------------------------------

class TestServicios:
    def test_listar_servicios_es_publico(self, client):
        """Este endpoint NO requiere JWT — debe ser accesible."""
        resp = client.get('/api/servicios/')
        assert resp.status_code == 200

    def test_listar_categorias_es_publico(self, client):
        resp = client.get('/api/servicios/categorias')
        assert resp.status_code == 200

    def test_filtrar_por_categoria(self, client):
        resp = client.get('/api/servicios/?categoria=computacion')
        assert resp.status_code == 200

    def test_crear_servicio_requiere_jwt(self, client):
        resp = client.post('/api/servicios/', json={
            'nombre': 'Test', 'precio_base': 1000
        })
        assert resp.status_code == 401


# -----------------------------------------------------------------------
# Tests de transacciones
# -----------------------------------------------------------------------

class TestTransacciones:
    def test_listar_ordenes(self, client, token_admin):
        resp = client.get('/api/transacciones/',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200

    def test_crear_orden(self, client, token_admin):
        # Obtener IDs válidos
        clientes = client.get('/api/clientes/',
                               headers={'Authorization': f'Bearer {token_admin}'}).get_json()
        servicios = client.get('/api/servicios/').get_json()

        cliente_id = clientes['datos']['items'][0]['id']
        servicio_id = servicios['datos']['items'][0]['id']
        precio = servicios['datos']['items'][0]['precio_base']

        resp = client.post('/api/transacciones/', json={
            'cliente_id': cliente_id,
            'descripcion_problema': 'Equipo de prueba no enciende al presionar el botón.',
            'tipo_equipo': 'Laptop',
            'detalles': [{'servicio_id': servicio_id, 'precio_unitario': precio, 'cantidad': 1}]
        }, headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 201

    def test_filtrar_ordenes_por_estado(self, client, token_admin):
        resp = client.get('/api/transacciones/?estado=pendiente',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Tests de reportes
# -----------------------------------------------------------------------

class TestReportes:
    def test_resumen_requiere_admin(self, client, token_tecnico):
        resp = client.get('/api/reportes/resumen',
                          headers={'Authorization': f'Bearer {token_tecnico}'})
        assert resp.status_code == 403

    def test_resumen_con_admin(self, client, token_admin):
        resp = client.get('/api/reportes/resumen',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'ordenes' in data['datos']
        assert 'ingresos_mes_actual' in data['datos']

    def test_reporte_ingresos(self, client, token_admin):
        resp = client.get('/api/reportes/ingresos?agrupacion=dia',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200

    def test_servicios_top(self, client, token_admin):
        resp = client.get('/api/reportes/servicios-top?limite=5',
                          headers={'Authorization': f'Bearer {token_admin}'})
        assert resp.status_code == 200
