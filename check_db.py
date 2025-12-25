from supabase import create_client
from app.core.config import settings

# Setup connection
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

print("👀 checking database...")

# Fetch ALL rows without any filters
response = supabase.table("raw_alerts").select("*").execute()

print(f"Found {len(response.data)} rows:")
print(response.data)

