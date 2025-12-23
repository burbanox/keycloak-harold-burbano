import os
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from authlib.integrations.starlette_client import OAuth, OAuthError
from jose import jwt



KEYCLOAK_BROWSER_BASE = os.getenv("KEYCLOAK_BROWSER_BASE", "http://localhost:8080")
KEYCLOAK_BACKEND_BASE = os.getenv("KEYCLOAK_BACKEND_BASE", "http://host.docker.internal:8080")
REALM = os.getenv("KEYCLOAK_REALM", "demo-realm")

CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "fastapi-client")
CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")

APP_BASE = os.getenv("APP_BASE", "http://localhost:8000")
REDIRECT_URI = f"{APP_BASE}/callback"

AUTHORIZE_URL = f"{KEYCLOAK_BROWSER_BASE}/realms/{REALM}/protocol/openid-connect/auth"
TOKEN_URL = f"{KEYCLOAK_BACKEND_BASE}/realms/{REALM}/protocol/openid-connect/token"
JWKS_URL = f"{KEYCLOAK_BACKEND_BASE}/realms/{REALM}/protocol/openid-connect/certs"

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev_session_secret_change_me")

LOGOUT_REDIRECT_URI = f"{APP_BASE}/"
END_SESSION_URL = f"{KEYCLOAK_BROWSER_BASE}/realms/{REALM}/protocol/openid-connect/logout"


app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

oauth = OAuth()
oauth.register(
    name="keycloak",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    authorize_url=AUTHORIZE_URL,
    access_token_url=TOKEN_URL,
    jwks_uri=JWKS_URL,
    client_kwargs={"scope": "openid profile email"},
)


def _get_roles_from_access_claims(claims: dict) -> list[str]:
    roles: list[str] = []

    # Mapper custom "roles"
    r = claims.get("roles")
    if isinstance(r, list):
        roles.extend(r)

    # Realm roles
    ra = claims.get("realm_access") or {}
    r = ra.get("roles")
    if isinstance(r, list):
        roles.extend(r)

    # Client roles (fastapi-client)
    res = claims.get("resource_access") or {}
    client = res.get(CLIENT_ID) or {}
    r = client.get("roles")
    if isinstance(r, list):
        roles.extend(r)

    return sorted(set(roles))




def get_session_user(request: Request) -> dict | None:
    return request.session.get("user")


def require_login(request: Request) -> dict:
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_roles(*required: str):
    def dep(request: Request):
        roles = request.session.get("roles")
        if not roles:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if not set(required).issubset(set(roles)):
            raise HTTPException(status_code=403, detail="Forbidden")

        return {"roles": roles}
    return dep


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user = request.session.get("user")
    email = None
    if user:
        email = user.get("email") or user.get("preferred_username")

    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "title": "Login",
            "realm": REALM,
            "user": user,
            "email": email,
            "keycloak_url": KEYCLOAK_BROWSER_BASE,
        },
    )


@app.get("/login")
async def login(request: Request):
    return await oauth.keycloak.authorize_redirect(request, REDIRECT_URI)


@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except OAuthError as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "title": "Error", "message": "Error OAuth", "detail": str(e.error)},
            status_code=400,
        )

    id_token = token.get("id_token")
    access_token = token.get("access_token")

    if not id_token or not access_token:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Error",
                "message": "No se recibieron tokens esperados",
                "detail": f"keys={list(token.keys())}",
            },
            status_code=400,
        )

    id_claims = jwt.get_unverified_claims(id_token)
    access_claims = jwt.get_unverified_claims(access_token)
    roles = _get_roles_from_access_claims(access_claims)

    request.session["id_token"] = id_token
    request.session["user"] = {
        "sub": id_claims.get("sub"),
        "email": id_claims.get("email"),
        "preferred_username": id_claims.get("preferred_username"),
    }
    request.session["roles"] = roles

    if "admin" in roles:
        return RedirectResponse(url="/admin")
    if "users" in roles:
        return RedirectResponse(url="/user")
    return RedirectResponse(url="/no-role")



@app.get("/user", response_class=HTMLResponse)
async def user_page(request: Request, auth=Depends(require_roles("users"))):
    user = require_login(request)
    email = user.get("email") or user.get("preferred_username") or "usuario"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "User",
            "mode": "user",
            "email": email,
            "roles": auth["roles"],
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, auth=Depends(require_roles("admin"))):
    user = require_login(request)
    email = user.get("email") or user.get("preferred_username") or "usuario"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Admin",
            "mode": "admin",
            "email": email,
            "roles": auth["roles"],
        },
    )


@app.get("/no-role", response_class=HTMLResponse)
async def no_role(request: Request):
    user = request.session.get("user")
    email = None
    if user:
        email = user.get("email") or user.get("preferred_username")

    return templates.TemplateResponse(
        "no_role.html",
        {
            "request": request,
            "title": "Sin rol",
            "email": email,
        },
    )


@app.get("/logout")
async def logout(request: Request):
    id_token = request.session.get("id_token")
    request.session.clear()

    params = {"post_logout_redirect_uri": LOGOUT_REDIRECT_URI}
    if id_token:
        params["id_token_hint"] = id_token

    return RedirectResponse(url=f"{END_SESSION_URL}?{urlencode(params)}")



