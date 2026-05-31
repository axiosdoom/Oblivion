from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Basket, Bond, BondBasketLink, MacroData, Valuation

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, basket_id: int | None = None, db: Session = Depends(get_db)):
    baskets = db.query(Basket).order_by(Basket.bond_count.desc()).all()
    stats = _get_stats(db)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "baskets": baskets,
        "selected_basket_id": basket_id,
        "stats": stats,
    })


@router.get("/bond/{bond_id}", response_class=HTMLResponse)
def bond_detail(request: Request, bond_id: int, db: Session = Depends(get_db)):
    bond = db.get(Bond,bond_id)
    if not bond:
        return templates.TemplateResponse("base.html", {
            "request": request,
            "error": "Bond not found",
        })

    val = db.query(Valuation).filter_by(bond_id=bond_id).order_by(Valuation.id.desc()).first()
    basket = None
    if val and val.basket_id:
        basket = db.get(Basket,val.basket_id)

    return templates.TemplateResponse("bond_detail.html", {
        "request": request,
        "bond": bond,
        "valuation": val,
        "basket": basket,
    })


@router.get("/basket/{basket_id}", response_class=HTMLResponse)
def basket_view(request: Request, basket_id: int, db: Session = Depends(get_db)):
    basket = db.get(Basket,basket_id)
    if not basket:
        return templates.TemplateResponse("base.html", {
            "request": request,
            "error": "Basket not found",
        })

    links = db.query(BondBasketLink).filter_by(basket_id=basket_id).all()
    bond_ids = [lnk.bond_id for lnk in links]
    bonds_vals = (
        db.query(Bond, Valuation)
        .outerjoin(Valuation, Bond.id == Valuation.bond_id)
        .filter(Bond.id.in_(bond_ids))
        .order_by(Valuation.delta_price.desc().nullslast())
        .all()
    )

    return templates.TemplateResponse("basket_view.html", {
        "request": request,
        "basket": basket,
        "bonds_vals": bonds_vals,
    })


@router.get("/anomalies", response_class=HTMLResponse)
def anomalies_page(request: Request, anomaly_type: str | None = None, db: Session = Depends(get_db)):
    q = (
        db.query(Bond, Valuation)
        .join(Valuation, Bond.id == Valuation.bond_id)
        .filter(Valuation.anomaly_code.isnot(None))
    )
    if anomaly_type:
        q = q.filter(Valuation.anomaly_code == anomaly_type)

    q = q.order_by(Valuation.delta_price.desc().nullslast())
    rows = q.limit(200).all()

    type_counts = {}
    for code in ["P+", "Y+", "C+", "P+Y+", "R"]:
        type_counts[code] = db.query(Valuation).filter(Valuation.anomaly_code == code).count()

    # total_count исключаем R
    total_count = sum(v for k, v in type_counts.items() if k != 'R')

    return templates.TemplateResponse("anomalies.html", {
        "request": request,
        "bonds_vals": rows,
        "selected_type": anomaly_type,
        "type_counts": type_counts,
        "total_count": total_count,
    })


def _get_stats(db: Session) -> dict:
    bond_count = db.query(Bond).count()
    basket_count = db.query(Basket).count()
    anomaly_count = db.query(Valuation).filter(Valuation.anomaly_code.isnot(None)).count()

    key_rate_row = db.query(MacroData).filter_by(indicator="key_rate").first()
    key_rate = key_rate_row.value if key_rate_row else None
    key_rate_date = str(key_rate_row.as_of_date) if key_rate_row else None

    return {
        "bond_count": bond_count,
        "basket_count": basket_count,
        "anomaly_count": anomaly_count,
        "key_rate": key_rate,
        "key_rate_date": key_rate_date,
    }
