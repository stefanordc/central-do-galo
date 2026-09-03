from fastapi import APIRouter

from app.schemas.category import CategoriaOut
from app.services.category_service import listar_categorias

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoriaOut])
def get_categorias() -> list[dict]:
    return listar_categorias()
