from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
import models
import schemas
from database import engine, Base, get_db
import utils

app = FastAPI(title="Catalog Service API", version="1.0.0")
utils.setup_common_app(app)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

@app.post("/v1/products", response_model=schemas.ProductResponse, status_code=201)
async def create_product(product: schemas.ProductCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product).where(models.Product.sku == product.sku))
    db_product = result.scalars().first()
    if db_product:
        raise HTTPException(status_code=400, detail="SKU already registered")
    
    new_product = models.Product(**product.model_dump())
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    return new_product

@app.get("/v1/products", response_model=List[schemas.ProductResponse])
async def list_products(
    skip: int = Query(0, ge=0), 
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Product).offset(skip).limit(limit)
    if category:
        query = query.where(models.Product.category == category)
    result = await db.execute(query)
    products = result.scalars().all()
    return products

@app.get("/v1/products/{product_id}", response_model=schemas.ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product).where(models.Product.product_id == product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/v1/products/{product_id}", response_model=schemas.ProductResponse)
async def update_product(product_id: int, product_update: schemas.ProductUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product).where(models.Product.product_id == product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
        
    await db.commit()
    await db.refresh(product)
    return product
