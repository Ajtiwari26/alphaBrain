import asyncio
import sys
import traceback
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from testscript.test_self_development_evidence_review import (
    make_test_envelope,
    make_passing_result,
    test_founder_review_completes_task
)
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import Base

async def main():
    try:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        SessionLocal = sessionmaker(bind=engine, class_=AsyncSession)
        async with SessionLocal() as session:
            await test_founder_review_completes_task(session)
            print("TEST PASSED")
    except Exception as e:
        print("TEST FAILED WITH EXCEPTION:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
