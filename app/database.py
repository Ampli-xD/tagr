from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL, DB_POOL_PRE_PING, DB_ECHO, DB_PREPARE_THRESHOLD

_connect_args = {}
if DB_PREPARE_THRESHOLD is not None:
    _connect_args["prepare_threshold"] = DB_PREPARE_THRESHOLD

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=DB_POOL_PRE_PING,
    echo=DB_ECHO,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
