from fastapi import APIRouter, HTTPException

from app.services.admin_service import obter_pagina_publica

router = APIRouter(prefix="/paginas", tags=["paginas"])


@router.get("/{slug}")
def get_pagina(slug: str) -> dict:
    try:
        pagina = obter_pagina_publica(slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Página não encontrada.") from exc
    if pagina is None:
        raise HTTPException(status_code=404, detail="Página não encontrada.")
    return pagina
