from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from app.db.pool import pool


@dataclass(frozen=True, slots=True)
class CategoryMatch:
    slug: str
    confidence: float


CATEGORY_PRIORITY = {
    "pos-jogo": 10,
    "pre-jogo": 20,
    "financeiro": 30,
    "mercado": 40,
    "departamento-medico": 50,
    "base": 60,
    "futebol-feminino": 70,
    "arena-mrv": 80,
    "treinos": 90,
    "entrevistas": 100,
    "bastidores": 110,
    "institucional": 120,
    "torcida": 130,
    "geral": 999,
}


def _normalize(value: str | None) -> str:
    text = value or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def classify_news(titulo: str, resumo: str | None = None) -> list[CategoryMatch]:
    normalized_summary = _normalize(resumo)
    if normalized_summary.startswith("acompanhe as ultimas noticias do atletico mineiro"):
        normalized_summary = ""

    text = _normalize(f"{titulo} {normalized_summary}")
    matches: dict[str, float] = {}

    def add(slug: str, confidence: float) -> None:
        matches[slug] = max(matches.get(slug, 0.0), confidence)

    # Contexto de partida.
    if _contains(
        text,
        r"\b(pos-jogo|apos o jogo|apos a partida|depois do jogo|melhores momentos|"
        r"empatam|empataram|so empatam|venceu|vitoria sobre|derrota para|repercussao da partida|"
        r"heroi da classificacao|classificacao na)\b",
    ):
        add("pos-jogo", 0.95)

    if _contains(
        text,
        r"\b(provaveis? escalacoes?|escalacao|desfalques?|suspensos?|pendurados?|arbitragem|"
        r"onde assistir|horario|pre-jogo|classico|duelo|enfrenta|encarar|antes de enfrentar|"
        r"as vesperas|jogo de ida|primeiro classico|foco no classico|vai jogar|teste de fogo|"
        r"estreantes para classico|esperanca para classico|proximo jogo)\b",
    ):
        add("pre-jogo", 0.95)

    # Mercado e dinheiro podem coexistir.
    if _contains(
        text,
        r"\b(quanto .*receber|deve receber|receber pela venda|valor milionario|milhoes|"
        r"mecanismo de solidariedade|premiacao|orcamento|receita|divida|balanco|"
        r"direitos economicos|percentual da transferencia|saf)\b",
    ):
        add("financeiro", 0.98)

    if _contains(
        text,
        r"\b(contratacao|contratar|reforco|mercado de transferencias|mercado|transferencia|"
        r"proposta|negocia|negociado|venda de|vendido|ser vendido|saida|deixar o clube|"
        r"alvo do|permanecer|permanencia|futuro no atletico|janela|rescisao|renovacao)\b",
    ):
        add("mercado", 0.94)

    if _contains(
        text,
        r"\b(departamento medico|dm do atletico|lesao|lesionado|recuperado|recuperacao|"
        r"cirurgia|exames?|liberado pelo departamento medico)\b",
    ):
        add("departamento-medico", 0.97)

    if _contains(text, r"\b(treino|treinos|jogo-treino|reapresentacao|preparacao|programacao semanal)\b"):
        add("treinos", 0.90)

    if _contains(
        text,
        r"\b(revela|responde|rebate|afirma|declara|projeta|faz alerta|valoriza|"
        r"prega respeito|coletiva|entrevista|abre o jogo)\b",
    ):
        add("entrevistas", 0.82)

    if _contains(text, r"\b(sub-20|sub 20|galinho|categorias? de base|crias)\b"):
        add("base", 0.98)

    if _contains(text, r"\b(futebol feminino|brasileirao feminino|atletico feminino|galotinha)\b"):
        add("futebol-feminino", 0.99)

    if "arena mrv" in text and _contains(text, r"\b(ingresso|estadio|obra|evento|publico|torcida|acesso|operacao)\b"):
        add("arena-mrv", 0.94)

    if _contains(text, r"\b(torcida|torcedor|torcedora|ingresso|caravana|mosaico)\b"):
        add("torcida", 0.90)

    if _contains(text, r"\b(cbf|diretor|ceo|presidente|comunicado|acao do clube|premio confut)\b"):
        add("institucional", 0.80)

    if _contains(text, r"\b(bastidores|ambiente interno|diretoria avalia|decisao interna)\b"):
        add("bastidores", 0.85)

    if not matches:
        add("geral", 0.60)

    return [
        CategoryMatch(slug=slug, confidence=confidence)
        for slug, confidence in sorted(
            matches.items(),
            key=lambda item: (CATEGORY_PRIORITY.get(item[0], 999), -item[1]),
        )
    ]


def save_news_categories(noticia_id: UUID, titulo: str, resumo: str | None = None) -> None:
    matches = classify_news(titulo=titulo, resumo=resumo)
    slugs = [match.slug for match in matches]

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Regras automáticas podem ser recalculadas. Classificações manuais/IA são preservadas.
            cur.execute(
                "delete from public.noticias_categorias where noticia_id = %s and origem = 'regra'",
                (noticia_id,),
            )

            cur.execute(
                "select id, slug from public.categorias where ativo = true and slug = any(%s)",
                (slugs,),
            )
            category_ids = {slug: category_id for category_id, slug in cur.fetchall()}

            for index, match in enumerate(matches):
                category_id = category_ids.get(match.slug)
                if not category_id:
                    continue
                cur.execute(
                    """
                    insert into public.noticias_categorias
                        (noticia_id, categoria_id, principal, origem, confianca)
                    values (%s, %s, %s, 'regra', %s)
                    on conflict (noticia_id, categoria_id) do update
                    set principal = excluded.principal,
                        origem = excluded.origem,
                        confianca = excluded.confianca
                    """,
                    (noticia_id, category_id, index == 0, match.confidence),
                )

            # Mantém somente uma categoria principal por notícia.
            if matches:
                main_slug = matches[0].slug
                main_id = category_ids.get(main_slug)
                if main_id:
                    cur.execute(
                        """
                        update public.noticias_categorias
                        set principal = (categoria_id = %s)
                        where noticia_id = %s
                        """,
                        (main_id, noticia_id),
                    )

        conn.commit()
