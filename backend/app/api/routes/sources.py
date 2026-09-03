from fastapi import APIRouter

from app.schemas.source import FonteOut
from app.services.source_service import listar_fontes

router = APIRouter(prefix="/fontes", tags=["fontes"])


@router.get("", response_model=list[FonteOut])
def get_fontes() -> list[dict]:
    return listar_fontes()
