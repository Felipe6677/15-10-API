from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Path, status, Depends
from sqlmodel import SQLModel, Field, create_engine, Session, select
from pydantic import constr

class BrandBase(SQLModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    country: Optional[constr(strip_whitespace=True, max_length=50)] = None
    founded_year: Optional[int] = None
    website: Optional[constr(strip_whitespace=True, max_length=200)] = None

class Brand(BrandBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class BrandCreate(BrandBase):
    pass

class BrandRead(BrandBase):
    id: int

class BrandUpdate(SQLModel):
    name: Optional[constr(strip_whitespace=True, min_length=1, max_length=100)] = None
    country: Optional[constr(strip_whitespace=True, max_length=50)] = None
    founded_year: Optional[int] = None
    website: Optional[constr(strip_whitespace=True, max_length=200)] = None

app = FastAPI(title="API Marcas de Carros", version="1.0")

DATABASE_URL = "sqlite:///./brands.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def seed_data():
    examples = [
        {"name": "Toyota", "country": "Japan", "founded_year": 1937, "website": "https://www.toyota-global.com/"},
        {"name": "Ford", "country": "United States", "founded_year": 1903, "website": "https://www.ford.com/"},
        {"name": "Volkswagen", "country": "Germany", "founded_year": 1937, "website": "https://www.vw.com/"},
        {"name": "Hyundai", "country": "South Korea", "founded_year": 1967, "website": "https://www.hyundai.com/"},
        {"name": "Ferrari", "country": "Italy", "founded_year": 1939, "website": "https://www.ferrari.com/"},
    ]
    with Session(engine) as session:
        existing = session.exec(select(Brand)).first()
        if existing:
            return
        for b in examples:
            session.add(Brand(**b))
        session.commit()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_data()

@app.get("/", tags=["root"])
def root():
    return {"message": "API de Marcas de Carros — acesse /docs para ver a OpenAPI UI"}

@app.post("/brands/", response_model=BrandRead, status_code=status.HTTP_201_CREATED, tags=["brands"])
def create_brand(brand_in: BrandCreate, session: Session = Depends(get_session)):
 
    stmt = select(Brand).where(Brand.name.ilike(brand_in.name))
    exists = session.exec(stmt).first()
    if exists:
        raise HTTPException(status_code=400, detail="Marca com esse nome já existe.")
    brand = Brand.from_orm(brand_in)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return brand

@app.get("/brands/", response_model=List[BrandRead], tags=["brands"])
def list_brands(
    q: Optional[str] = Query(None, description="Buscar por nome (substring)"),
    country: Optional[str] = Query(None, description="Filtrar por país"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    stmt = select(Brand)
    if q:
        stmt = stmt.where(Brand.name.contains(q))
    if country:
        stmt = stmt.where(Brand.country.ilike(country))
    stmt = stmt.offset(offset).limit(limit)
    results = session.exec(stmt).all()
    return results


@app.get("/brands/{brand_id}", response_model=BrandRead, tags=["brands"])
def get_brand(brand_id: int = Path(..., gt=0), session: Session = Depends(get_session)):
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Marca não encontrada.")
    return brand

@app.put("/brands/{brand_id}", response_model=BrandRead, tags=["brands"])
def replace_brand(brand_id: int, brand_in: BrandCreate, session: Session = Depends(get_session)):
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Marca não encontrada.")

    stmt = select(Brand).where(Brand.name.ilike(brand_in.name), Brand.id != brand_id)
    conflict = session.exec(stmt).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Outra marca com esse nome já existe.")
    brand.name = brand_in.name
    brand.country = brand_in.country
    brand.founded_year = brand_in.founded_year
    brand.website = brand_in.website
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return brand


@app.patch("/brands/{brand_id}", response_model=BrandRead, tags=["brands"])
def update_brand(brand_id: int, brand_in: BrandUpdate, session: Session = Depends(get_session)):
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Marca não encontrada.")
    updated = False
    for field, value in brand_in.dict(exclude_unset=True).items():
        setattr(brand, field, value)
        updated = True
    if not updated:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
   
    if brand_in.name:
        stmt = select(Brand).where(Brand.name.ilike(brand_in.name), Brand.id != brand_id)
        conflict = session.exec(stmt).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Outra marca com esse nome já existe.")
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return brand

@app.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["brands"])
def delete_brand(brand_id: int, session: Session = Depends(get_session)):
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Marca não encontrada.")
    session.delete(brand)
    session.commit()
    return


@app.get("/stats/by-country", tags=["stats"])
def brands_by_country(session: Session = Depends(get_session)):
   
    stmt = select(Brand)
    results = session.exec(stmt).all()
    counts = {}
    for b in results:
        key = b.country or "Unknown"
        counts[key] = counts.get(key, 0) + 1
    return {"total": len(results), "by_country": counts}
