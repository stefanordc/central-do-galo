import psycopg, os
from dotenv import load_dotenv

load_dotenv("backend/.env")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE fontes ADD COLUMN IF NOT EXISTS permite_iframe BOOLEAN;")
        conn.commit()
print("Coluna adicionada com sucesso!")
