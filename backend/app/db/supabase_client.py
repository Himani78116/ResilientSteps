import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_url = os.environ.get("SUPABASE_URL")
_key = os.environ.get("SUPABASE_SERVICE_KEY")

if not _url or not _key:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from backend/.env"
    )

supabase: Client = create_client(_url, _key)
