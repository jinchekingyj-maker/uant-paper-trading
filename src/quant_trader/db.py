from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings
from .domain import utcnow


class Base(DeclarativeBase):
    pass


class AccountModel(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    positions: Mapped[list["PositionModel"]] = relationship(cascade="all, delete-orphan")


class PositionModel(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    market: Mapped[str] = mapped_column(String(8))
    symbol: Mapped[str] = mapped_column(String(32))
    security_type: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    last_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    market: Mapped[str] = mapped_column(String(8))
    symbol: Mapped[str] = mapped_column(String(32))
    security_type: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class FillModel(Base):
    __tablename__ = "fills"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LatestPriceModel(Base):
    __tablename__ = "latest_prices"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str] = mapped_column(String(8), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    trading_date: Mapped[date] = mapped_column(Date)


def make_engine(url: str = settings.database_url):
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.get(AccountModel, settings.default_account_id) is None:
            session.add(AccountModel(id=settings.default_account_id, cash=settings.initial_cash))
            session.commit()


def get_session():
    with SessionLocal() as session:
        yield session
