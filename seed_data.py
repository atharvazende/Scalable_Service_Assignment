import pandas as pd
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Database connections
DB_URLS = {
    "catalog_db": "postgresql+asyncpg://eci_user:eci_password@localhost:5432/catalog_db",
    "inventory_db": "postgresql+asyncpg://eci_user:eci_password@localhost:5432/inventory_db",
    "order_db": "postgresql+asyncpg://eci_user:eci_password@localhost:5432/order_db",
    "payment_db": "postgresql+asyncpg://eci_user:eci_password@localhost:5432/payment_db",
    "shipping_db": "postgresql+asyncpg://eci_user:eci_password@localhost:5432/shipping_db"
}

async def insert_data(engine, table, df):
    async with engine.begin() as conn:
        for _, row in df.iterrows():
            columns = ", ".join(row.index)
            values = ", ".join([f"'{str(x)}'" if pd.notnull(x) else 'NULL' for x in row.values])
            query = f"INSERT INTO {table} ({columns}) VALUES ({values}) ON CONFLICT DO NOTHING;"
            await conn.execute(text(query))

async def main():
    print("Loading CSVs...")
    products = pd.read_csv("ECI Dataset/eci_products_indian.csv")
    inventory = pd.read_csv("ECI Dataset/eci_inventory_indian.csv")
    customers = pd.read_csv("ECI Dataset/eci_customers_indian.csv")
    orders = pd.read_csv("ECI Dataset/eci_orders_indian.csv")
    order_items = pd.read_csv("ECI Dataset/eci_order_items_indian.csv")
    payments = pd.read_csv("ECI Dataset/eci_payments_indian.csv")
    shipments = pd.read_csv("ECI Dataset/eci_shipments_indian.csv")

    print("Seeding Catalog DB...")
    catalog_engine = create_async_engine(DB_URLS["catalog_db"])
    await insert_data(catalog_engine, "products", products)
    
    print("Seeding Inventory DB...")
    inventory_engine = create_async_engine(DB_URLS["inventory_db"])
    await insert_data(inventory_engine, "inventory", inventory)
    
    print("Seeding Order DB...")
    order_engine = create_async_engine(DB_URLS["order_db"])
    await insert_data(order_engine, "customers", customers)
    await insert_data(order_engine, "orders", orders)
    await insert_data(order_engine, "order_items", order_items)
    
    print("Seeding Payment DB...")
    payment_engine = create_async_engine(DB_URLS["payment_db"])
    await insert_data(payment_engine, "payments", payments)
    
    print("Seeding Shipping DB...")
    shipping_engine = create_async_engine(DB_URLS["shipping_db"])
    await insert_data(shipping_engine, "shipments", shipments)

    print("Data seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
