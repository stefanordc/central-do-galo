
import asyncio
from app.core.config import get_settings
import psycopg

def add_col():
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE fontes ADD COLUMN IF NOT EXISTS permite_iframe BOOLEAN;")
            conn.commit()
    print("Coluna adicionada com sucesso.")

add_col()

