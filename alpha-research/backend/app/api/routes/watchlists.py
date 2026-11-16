"""Watchlist CRUD."""

from fastapi import APIRouter, Response, status

from app.api.deps import DbSession, TickerPath
from app.schemas.research import WatchlistCreate, WatchlistItemCreate, WatchlistOut
from app.services import watchlists

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(db: DbSession) -> list[WatchlistOut]:
    return watchlists.list_watchlists(db)


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist(db: DbSession, payload: WatchlistCreate) -> WatchlistOut:
    return watchlists.create_watchlist(db, payload)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(db: DbSession, watchlist_id: int) -> Response:
    watchlists.delete_watchlist(db, watchlist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watchlist_id}/items", response_model=WatchlistOut, status_code=201)
def add_item(db: DbSession, watchlist_id: int, payload: WatchlistItemCreate) -> WatchlistOut:
    return watchlists.add_item(db, watchlist_id, payload)


@router.delete("/{watchlist_id}/items/{ticker}", response_model=WatchlistOut)
def remove_item(db: DbSession, watchlist_id: int, ticker: TickerPath) -> WatchlistOut:
    return watchlists.remove_item(db, watchlist_id, ticker)
