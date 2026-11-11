import os, xmlrpc.client, psycopg2
from dotenv import load_dotenv
load_dotenv()

# Odoo
url = os.getenv("ODOO_URL")
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(os.getenv("ODOO_DB"), os.getenv("ODOO_USER"), os.getenv("ODOO_KEY"), {})
print("Odoo UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
productos = models.execute_kw(os.getenv("ODOO_DB"), uid, os.getenv("ODOO_KEY"),
    "product.template", "search_read", [[]],
    {"fields": ["name", "list_price", "qty_available"]})
print("Productos en Odoo:", len(productos))

# PostgreSQL d3kicks
conn = psycopg2.connect(host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
    dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"))
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
print("Tablas en d3kicks:", [t[0] for t in cur.fetchall()])