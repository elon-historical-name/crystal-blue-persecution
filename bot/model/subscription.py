from sqlalchemy import Column, String, Integer, BigInteger
from sqlalchemy.orm import Mapped

from model.base import Base


class Subscription(Base):
    __tablename__ = "subscription"
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = Column(BigInteger, nullable=False)
    did: Mapped[str] = Column(String, nullable=False)
