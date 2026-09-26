from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bank_lab.backups import BackupError, create_backup, restore_test
from bank_lab.database import Base
from bank_lab.scenarios import remediate_scenario, retest_scenario, run_scenario
from bank_lab.seed import seed_database


@pytest.fixture
async def seeded_db() -> AsyncIterator[tuple[AsyncSession, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
            await seed_database(session, password_factory=lambda: "Fixture-Pass-42!")
        yield session, factory
    await engine.dispose()


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_all_six_scenarios_are_bounded_and_preserve_retest_lineage(
    seeded_db: tuple[AsyncSession, async_sessionmaker[AsyncSession]],
) -> None:
    db, _factory = seeded_db
    results: dict[str, bool] = {}
    for number in range(1, 7):
        scenario_id = f"S0{number}"
        resource = f"cyber-assess-scenario-{scenario_id.lower()}-acceptance"
        baseline = await run_scenario(db, scenario_id, resource)
        remediation = await remediate_scenario(db, scenario_id, baseline.run_id, resource)
        retest = await retest_scenario(db, scenario_id, baseline.run_id, remediation.run_id)
        assert baseline.status == "frozen"
        assert remediation.observations["baseline_run_id"] == baseline.run_id
        assert retest.observations["passed"] is True
        results[scenario_id] = bool(retest.observations["passed"])
    assert results == {f"S0{i}": True for i in range(1, 7)}


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_backup_hash_failure_and_isolated_restore(
    seeded_db: tuple[AsyncSession, async_sessionmaker[AsyncSession]], tmp_path: Path
) -> None:
    source, _factory = seeded_db
    backup = await create_backup(source, tmp_path / "backups", "RUN-ACCEPTANCE")
    original = backup.path.read_bytes()
    backup.path.write_bytes(original + b"tampered")
    target_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'restore.db'}")
    async with target_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    target_factory = async_sessionmaker(target_engine, expire_on_commit=False)
    async with target_factory() as target:
        with pytest.raises(BackupError, match="hash validation failed"):
            await restore_test(target, backup.path, backup.sha256)
    backup.path.write_bytes(original)
    async with target_factory() as target:
        restored = await restore_test(target, backup.path, backup.sha256)
    await target_engine.dispose()
    assert restored.valid is True
    assert restored.counts["users"] == 24
    assert restored.counts["service_requests"] == 50
