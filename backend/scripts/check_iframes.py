import asyncio
from app.core.config import get_settings
from app.db.pool import pool, open_pool, close_pool
from app.services.iframe_checker import get_and_check_source

async def run_checker():
    print("Iniciando verificacao de fontes...")
    open_pool(get_settings())
    
    sql = "SELECT id, nome, url_base FROM public.fontes WHERE ativo = true AND permite_iframe IS NULL"
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            
    if not rows:
        print("Nenhuma fonte pendente de checagem encontrada.")
    
    for row in rows:
        fonte_id, nome, url = row
        if not url:
            continue
        print(f"Checando {nome}...")
        status = get_and_check_source(fonte_id)
        print(f"Resultado de {nome}: {'Permitido' if status else 'Bloqueado'}")
    
    close_pool()
    print("Finalizado.")

if __name__ == "__main__":
    asyncio.run(run_checker())
