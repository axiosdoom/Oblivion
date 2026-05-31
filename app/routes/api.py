from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import TINKOFF_TOKEN
from app.database import get_db
from app.models import Basket, Bond, BondBasketLink, Valuation
from app.schemas import BasketOut, BondOut, PipelineResult, ValuationOut
from app.services.comparison import get_yield_curve_data

router = APIRouter(prefix="/api")


@router.post("/run", response_model=PipelineResult)
def run_pipeline(db: Session = Depends(get_db)):
    from app.services.pipeline import run_full_pipeline
    stats = run_full_pipeline(db, TINKOFF_TOKEN)
    return PipelineResult(**stats)


@router.get("/bonds")
def list_bonds(
    basket_id: int | None = None,
    rating: str | None = None,
    min_ytm: float | None = None,
    anomaly_only: bool = False,
    sort_by: str = "delta_price",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
):
    q = db.query(Bond, Valuation).outerjoin(Valuation, Bond.id == Valuation.bond_id)

    if basket_id:
        bond_ids = [
            lnk.bond_id
            for lnk in db.query(BondBasketLink).filter_by(basket_id=basket_id).all()
        ]
        q = q.filter(Bond.id.in_(bond_ids))

    if rating:
        q = q.filter(Bond.rating == rating)

    if min_ytm is not None:
        q = q.filter(Bond.ytm_percent >= min_ytm)

    if anomaly_only:
        q = q.filter(Valuation.anomaly_code.isnot(None), Valuation.anomaly_code != 'R')

    sort_col = {
        "delta_price": Valuation.delta_price,
        "delta_yield": Valuation.delta_yield,
        "risk_adjusted_yield": Valuation.risk_adjusted_yield,
        "duration": Bond.duration_years,
        "delta_curve": Valuation.delta_curve,
        "ytm": Bond.ytm_percent,
        "name": Bond.name,
        "rating": Bond.rating,
    }.get(sort_by, Valuation.delta_price)

    if sort_dir == "asc":
        q = q.order_by(sort_col.asc().nullslast())
    else:
        q = q.order_by(sort_col.desc().nullslast())

    rows = q.limit(500).all()

    result = []
    for bond, val in rows:
        basket_name = None
        if val and val.basket_id:
            bsk = db.get(Basket,val.basket_id)
            if bsk:
                basket_name = bsk.name

        result.append({
            "bond": BondOut.model_validate(bond).model_dump(mode="json"),
            "valuation": ValuationOut.model_validate(val).model_dump(mode="json") if val else None,
            "basket_name": basket_name,
        })

    return result


@router.get("/bonds/{bond_id}")
def get_bond(bond_id: int, db: Session = Depends(get_db)):
    bond = db.get(Bond,bond_id)
    if not bond:
        return {"error": "Bond not found"}

    val = db.query(Valuation).filter_by(bond_id=bond_id).order_by(Valuation.id.desc()).first()
    basket_name = None
    basket = None
    if val and val.basket_id:
        basket = db.get(Basket,val.basket_id)
        if basket:
            basket_name = basket.name

    return {
        "bond": BondOut.model_validate(bond).model_dump(mode="json"),
        "valuation": ValuationOut.model_validate(val).model_dump(mode="json") if val else None,
        "basket": BasketOut.model_validate(basket).model_dump(mode="json") if basket else None,
        "basket_name": basket_name,
    }


@router.get("/baskets")
def list_baskets(db: Session = Depends(get_db)):
    baskets = db.query(Basket).order_by(Basket.bond_count.desc()).all()
    return [BasketOut.model_validate(b).model_dump(mode="json") for b in baskets]


@router.get("/baskets/{basket_id}")
def get_basket(basket_id: int, db: Session = Depends(get_db)):
    basket = db.get(Basket,basket_id)
    if not basket:
        return {"error": "Basket not found"}
    return BasketOut.model_validate(basket).model_dump(mode="json")


@router.get("/yield-curve/{basket_id}")
def yield_curve(basket_id: int, db: Session = Depends(get_db)):
    data = get_yield_curve_data(db, basket_id)
    if not data:
        return {"points": [], "curve": []}
    return data


@router.get("/anomalies")
def list_anomalies(
    anomaly_type: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Bond, Valuation).join(Valuation, Bond.id == Valuation.bond_id).filter(
        Valuation.anomaly_code.isnot(None)
    )

    if anomaly_type:
        q = q.filter(Valuation.anomaly_code == anomaly_type)

    q = q.order_by(Valuation.delta_price.desc().nullslast())
    rows = q.limit(200).all()

    result = []
    for bond, val in rows:
        basket_name = None
        if val.basket_id:
            bsk = db.get(Basket,val.basket_id)
            if bsk:
                basket_name = bsk.name

        result.append({
            "bond": BondOut.model_validate(bond).model_dump(mode="json"),
            "valuation": ValuationOut.model_validate(val).model_dump(mode="json"),
            "basket_name": basket_name,
        })

    return result


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    from app.models import MacroData
    bond_count = db.query(Bond).count()
    basket_count = db.query(Basket).count()
    valuation_count = db.query(Valuation).count()
    anomaly_count = db.query(Valuation).filter(Valuation.anomaly_code.isnot(None), Valuation.anomaly_code != 'R').count()

    key_rate_row = db.query(MacroData).filter_by(indicator="key_rate").first()
    key_rate = key_rate_row.value if key_rate_row else None
    key_rate_date = str(key_rate_row.as_of_date) if key_rate_row else None

    return {
        "bond_count": bond_count,
        "basket_count": basket_count,
        "valuation_count": valuation_count,
        "anomaly_count": anomaly_count,
        "key_rate": key_rate,
        "key_rate_date": key_rate_date,
    }
