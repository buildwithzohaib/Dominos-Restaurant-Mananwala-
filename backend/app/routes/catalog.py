from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Category, Product, RestaurantTable
from app.schemas.schemas import CategoryOut, ProductOut, TableOut

router = APIRouter(prefix="/api", tags=["catalog"])

@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return db.query(Category).filter(Category.active.is_(True)).order_by(Category.name_display).all()

@router.get("/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.available.is_(True)).order_by(Product.name_display).all()

@router.get("/tables", response_model=list[TableOut])
def tables(db: Session = Depends(get_db)):
    return db.query(RestaurantTable).filter(RestaurantTable.active.is_(True)).order_by(RestaurantTable.id).all()
