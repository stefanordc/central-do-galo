
import httpx
from urllib.parse import urlparse
import logging
from app.db.pool import pool
from uuid import UUID

logger = logging.getLogger("central_galo.iframe_checker")

def check_iframe_permission(url: str) -> bool:
    try:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        # Timeout reduzido, se o site não responde em 5s não deve servir para iframe rápido
        with httpx.Client(timeout=5.0, verify=False, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = client.get(base_url, headers=headers)
            
            x_frame = response.headers.get("X-Frame-Options", "").upper()
            csp = response.headers.get("Content-Security-Policy", "").lower()
            
            if "DENY" in x_frame or "SAMEORIGIN" in x_frame:
                return False
            
            if "frame-ancestors" in csp:
                if "\'none\'" in csp or "\'self\'" in csp:
                    return False
                if "*" not in csp and "localhost" not in csp:
                    return False
                    
            return True
    except Exception as e:
        logger.warning(f"Erro ao checar iframe de {url}: {e}")
        return False

def update_iframe_status_in_db(fonte_id: UUID, status: bool):
    sql = "UPDATE public.fontes SET permite_iframe = %s, atualizado_em = now() WHERE id = %s"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, fonte_id))
            conn.commit()

def get_and_check_source(fonte_id: UUID) -> bool | None:
    sql = "SELECT url_base, permite_iframe FROM public.fontes WHERE id = %s AND ativo = true"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (fonte_id,))
            row = cur.fetchone()
            if not row:
                return None
            url, current_status = row
            
            if current_status is not None:
                return current_status
                
            if url:
                is_allowed = check_iframe_permission(url)
                update_iframe_status_in_db(fonte_id, is_allowed)
                return is_allowed
            
            return False

