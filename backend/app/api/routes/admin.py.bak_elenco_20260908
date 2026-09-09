import secrets
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation

from app.services.admin_service import (
    criar_conta_x,
    criar_pagina,
    listar_contas_x_admin,
    listar_paginas_admin,
)
from app.services.source_service import (
    criar_canal_youtube,
    listar_canais_youtube_admin,
)
from app.services.site_config_service import (
    atualizar_capa_site,
    obter_capa_site,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# Credenciais fixas solicitadas para o painel local.
_ADMIN_EMAIL = "stefanobrunofaria@gmail.com"
_ADMIN_PASSWORD = "Skt8punk@stefano"
_ADMIN_SESSION_TOKEN = secrets.token_urlsafe(48)


class AdminLoginIn(BaseModel):
    email: str
    senha: str


class PaginaCreateIn(BaseModel):
    titulo: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=1, max_length=120)
    conteudo: str = Field(min_length=1, max_length=100_000)
    ativo: bool = True


class ContaXCreateIn(BaseModel):
    nome: str = Field(default="", max_length=160)
    usuario: str = Field(min_length=1, max_length=200)
    oficial: bool = False
    confiabilidade: int = Field(default=80, ge=0, le=100)


class CanalYoutubeCreateIn(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    url: str = Field(min_length=1, max_length=500)
    oficial: bool = False
    confiabilidade: int = Field(default=80, ge=0, le=100)


class CapaSiteUpdateIn(BaseModel):
    ativo: bool = False
    tipo: Literal["imagem", "video"] = "imagem"
    media_url: str | None = Field(default=None, max_length=3000)


def _validar_admin(authorization: str | None) -> None:
    prefixo = "Bearer "
    if not authorization or not authorization.startswith(prefixo):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão de admin ausente.")
    token = authorization[len(prefixo):].strip()
    if not secrets.compare_digest(token, _ADMIN_SESSION_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão de admin inválida.")


@router.post("/login")
def login_admin(payload: AdminLoginIn) -> dict:
    email_ok = secrets.compare_digest(payload.email.strip().lower(), _ADMIN_EMAIL.lower())
    senha_ok = secrets.compare_digest(payload.senha, _ADMIN_PASSWORD)
    if not (email_ok and senha_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login ou senha inválidos.")
    return {"token": _ADMIN_SESSION_TOKEN, "email": _ADMIN_EMAIL}


@router.get("/paginas")
def get_paginas_admin(authorization: str | None = Header(default=None)) -> list[dict]:
    _validar_admin(authorization)
    return listar_paginas_admin()


@router.post("/paginas", status_code=status.HTTP_201_CREATED)
def post_pagina_admin(
    payload: PaginaCreateIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_admin(authorization)
    try:
        return criar_pagina(
            titulo=payload.titulo,
            slug=payload.slug,
            conteudo=payload.conteudo,
            ativo=payload.ativo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Já existe uma página com esse slug.") from exc


@router.get("/x/contas")
def get_contas_x_admin(authorization: str | None = Header(default=None)) -> list[dict]:
    _validar_admin(authorization)
    return listar_contas_x_admin()


@router.post("/x/contas", status_code=status.HTTP_201_CREATED)
def post_conta_x_admin(
    payload: ContaXCreateIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_admin(authorization)
    try:
        return criar_conta_x(
            nome=payload.nome,
            usuario=payload.usuario,
            oficial=payload.oficial,
            confiabilidade=payload.confiabilidade,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Esse perfil do X já está cadastrado.") from exc


@router.get("/youtube/canais")
def get_canais_youtube_admin(authorization: str | None = Header(default=None)) -> list[dict]:
    _validar_admin(authorization)
    return listar_canais_youtube_admin()


@router.post("/youtube/canais", status_code=status.HTTP_201_CREATED)
def post_canal_youtube_admin(
    payload: CanalYoutubeCreateIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_admin(authorization)
    try:
        return criar_canal_youtube(
            nome=payload.nome,
            url=payload.url,
            oficial=payload.oficial,
            confiabilidade=payload.confiabilidade,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Esse canal do YouTube já está cadastrado.") from exc


@router.get("/capa-publica")
def get_capa_publica() -> dict:
    return obter_capa_site()


@router.get("/capa")
def get_capa_admin(authorization: str | None = Header(default=None)) -> dict:
    _validar_admin(authorization)
    return obter_capa_site()


@router.put("/capa")
def put_capa_admin(
    payload: CapaSiteUpdateIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_admin(authorization)

    try:
        return atualizar_capa_site(
            ativo=payload.ativo,
            tipo=payload.tipo,
            media_url=payload.media_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
