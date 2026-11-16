"""Watchlist management."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.models import Watchlist, WatchlistItem
from app.schemas.research import WatchlistCreate, WatchlistItemCreate, WatchlistOut


def list_watchlists(db: Session) -> list[WatchlistOut]:
    rows = db.scalars(
        select(Watchlist).options(selectinload(Watchlist.items)).order_by(Watchlist.name)
    ).all()
    return [WatchlistOut.model_validate(row) for row in rows]


def create_watchlist(db: Session, payload: WatchlistCreate) -> WatchlistOut:
    watchlist = Watchlist(name=payload.name.strip(), description=payload.description)
    db.add(watchlist)
    _commit(db, f"A watchlist named '{watchlist.name}' already exists")
    db.refresh(watchlist)
    return WatchlistOut.model_validate(watchlist)


def delete_watchlist(db: Session, watchlist_id: int) -> None:
    db.delete(_get(db, watchlist_id))
    db.commit()


def add_item(db: Session, watchlist_id: int, payload: WatchlistItemCreate) -> WatchlistOut:
    watchlist = _get(db, watchlist_id)
    watchlist.items.append(WatchlistItem(ticker=payload.ticker, notes=payload.notes))
    _commit(db, f"{payload.ticker} is already on this watchlist")
    db.refresh(watchlist)
    return WatchlistOut.model_validate(watchlist)


def remove_item(db: Session, watchlist_id: int, ticker: str) -> WatchlistOut:
    watchlist = _get(db, watchlist_id)
    item = next((i for i in watchlist.items if i.ticker == ticker), None)
    if item is None:
        raise NotFoundError(f"{ticker} is not on this watchlist")
    watchlist.items.remove(item)
    db.commit()
    db.refresh(watchlist)
    return WatchlistOut.model_validate(watchlist)


def _get(db: Session, watchlist_id: int) -> Watchlist:
    watchlist = db.get(Watchlist, watchlist_id)
    if watchlist is None:
        raise NotFoundError(f"Watchlist {watchlist_id} does not exist")
    return watchlist


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc
