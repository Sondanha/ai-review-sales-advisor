# db/models.py
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Integer, Date, Float

Base = declarative_base()

class Merchant(Base):
    __tablename__ = "merchant"
    encoded_mct: Mapped[str] = mapped_column("encoded_mct", String, primary_key=True)
    name: Mapped[str] = mapped_column("mct_nm", String, nullable=True)
    sigungu: Mapped[str] = mapped_column("mct_sigungu_nm", String, nullable=True)
    are_d: Mapped[str] = mapped_column("are_d", String, nullable=True)

class MerchantMonthlyMetrics(Base):
    __tablename__ = "merchant_monthly_metrics"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    encoded_mct: Mapped[str] = mapped_column(String, index=True)
    yyyymm: Mapped[str] = mapped_column(String, index=True)
    sales_amt: Mapped[float] = mapped_column(Float)
    txn_cnt: Mapped[int] = mapped_column(Integer)
