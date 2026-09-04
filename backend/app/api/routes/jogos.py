from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.services.jogo_service import listar_jogos, status_jogos

router = APIRouter(prefix="/jogos", tags=["jogos"])


@router.get("")
def get_jogos(
    inicio: date | None = Query(default=None),
    fim: date | None = Query(default=None),
) -> list[dict]:
    hoje = date.today()
    inicio_resolvido = inicio or (hoje - timedelta(days=45))
    fim_resolvido = fim or (hoje + timedelta(days=120))

    try:
        return listar_jogos(
            inicio=inicio_resolvido,
            fim=fim_resolvido,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
def get_status_jogos() -> dict:
    return status_jogos()
