from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

def __run_migrations__(connection, script_location: str, dsn: str) -> None:
    print('Running DB migrations in %r on %r', script_location, dsn)
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', script_location)
    alembic_cfg.set_main_option('sqlalchemy.url', dsn)
    command.upgrade(alembic_cfg, 'head')

async def run_migrations_async(script_location: str, dsn: str, *args, **kwargs) -> None:
    async_engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with async_engine.begin() as conn:
        await conn.run_sync(__run_migrations__, script_location, dsn)
