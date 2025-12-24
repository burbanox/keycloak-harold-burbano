# FastAPI + Keycloak (OIDC) + Docker Compose

Este proyecto implementa autenticación y autorización basada en roles usando **Keycloak (OIDC)** y **FastAPI**, con renderizado de **templates HTML** y manejo de sesión mediante cookies.  
La infraestructura está orquestada con **Docker Compose**, incluyendo **PostgreSQL** como base de datos de Keycloak.

---

## 🧱 Arquitectura general

- **FastAPI**
  - Backend principal
  - Maneja login, callback OIDC, sesiones y autorización por roles
  - Renderiza templates HTML (`Jinja2`)
- **Keycloak**
  - Proveedor de identidad (OIDC)
  - Maneja usuarios, roles y autenticación
- **PostgreSQL**
  - Base de datos de Keycloak
- **Docker Compose**
  - Red interna entre servicios
  - Exposición controlada de puertos al host

---

## 📁 Estructura del proyecto

```text
.
├── app/
│   ├── static/                # Archivos estáticos (CSS, JS, imágenes)
│   ├── templates/             # Templates HTML (Jinja2)
│   ├── Dockerfile             # Imagen del servicio FastAPI
│   ├── main.py                # Aplicación FastAPI
│   └── requirements.txt       # Dependencias Python
│
├── keycloak_data/              # Volumen persistente de Keycloak
├── pg_data/                    # Volumen persistente de PostgreSQL
│
├── .env                        # Variables de entorno
├── docker-compose.yaml         # Orquestación de servicios
├── README.md                   # Documentación del proyecto
└── .gitignore

```

# 🔐 Flujo de autenticación (OIDC)

1. El usuario accede a `/login`
2. FastAPI redirige al Keycloak (browser)
3. El usuario se autentica en Keycloak
4. Keycloak redirige a `/callback`
5. FastAPI:
   - Intercambia `code → tokens`
   - Extrae roles
   - Guarda información mínima en sesión
6. El usuario es redirigido según su rol:
   - `/admin`
   - `/user`
   - `/no-role`

---

# 🌍 Por qué existen **DOS direcciones** de Keycloak

Se usan dos bases distintas porque hay **dos actores de red diferentes**:

| Actor       | Variable                  | Ejemplo                    | Uso            |
|------------|---------------------------|----------------------------|----------------|
| Navegador  | KEYCLOAK_BROWSER_BASE     | http://localhost:8080      | Login / Logout |
| Backend    | KEYCLOAK_BACKEND_BASE     | http://keycloak:8080       | Token / JWKS   |

**Notas importantes:**

- El navegador **NO conoce** el DNS interno de Docker  
- FastAPI dentro de Docker **NO debe usar `localhost`**

---


# 🚀 Despliegue y Configuración del Proyecto

## ▶️ Cómo Levantar el Proyecto

Para construir e iniciar todos los servicios del proyecto:

1.  **Construir e Iniciar Servicios (en segundo plano):**
    ```bash
    docker compose up -d --build
    ```
2.  **Ver Servicios Activos:**
    ```bash
    docker compose ps
    ```
3.  **Ver Logs (en tiempo real):**
    ```bash
    docker compose logs -f
    ```

---

## ⛔ Detener / Reiniciar Servicios

* **Parar Todo:** Detiene y elimina los contenedores y redes.
    ```bash
    docker compose down
    ```
* **Reinicio Limpio (Recomendado):** Detiene y reinicia los contenedores.
    ```bash
    docker compose down && docker compose up -d
    ```
* **Borrado Total (⚠️ ¡Elimina Datos!):** Detiene, elimina contenedores, redes **y volúmenes** (datos persistentes).
    ```bash
    docker compose down -v
    ```

---

## 👤 Roles y Autorización

Los roles de usuario se gestionan a través del `access token` de autenticación.

* **Roles Soportados:**
    * `Realm roles`
    * `Client roles` (específicamente para `fastapi-client`)
* **Almacenamiento de Roles:** Los roles se guardan en la sesión del usuario para su uso posterior:
    ```python
    request.session["roles"]
    ```
* **Ejemplos de Mapeo de Roles a Rutas:**
    * `admin` → `/admin`
    * `users` → `/user`

---

## 🔒 Seguridad (Decisiones Importantes en Desarrollo)

| Decisión | Estado | Descripción |
| :--- | :--- | :--- |
| Guardado de `access token` | **❌ No** | Se evita guardar el `access token` completo en la sesión para prevenir *cookies* grandes. |
| Información de Usuario | **✅ Solo mínima** | Solo se almacena la información estrictamente necesaria del usuario. |
| Gestión de Sesiones | **✅ SessionMiddleware** | Las sesiones se gestionan mediante el `SessionMiddleware` de FastAPI. |
| Validación Criptográfica JWT | **⚠️ No (Modo Desarrollo)** | Los JWTs **NO** se validan criptográficamente en modo desarrollo. |

---

## 🚧 Modo Desarrollo

Este proyecto está configurado para un **entorno de desarrollo local**:

* Conexiones **HTTP**
* Keycloak en modo `start-dev`
* Tokens decodificados **sin verificación de firma**

**⚠️ Para un entorno de Producción se Requiere:**

* **HTTPS** (cifrado de la comunicación)
* **Validación de Firma JWT** (seguridad de los tokens)
* Uso de un **Reverse Proxy** (Nginx / Traefik)
* **Cookies Seguras** (`Secure`, `SameSite`)

---

## 📌 Requisitos

Para poder ejecutar el proyecto, necesitas tener instalados:

* **Docker**
* **Docker Compose v2+**
* **Navegador moderno** (para la interfaz de usuario)