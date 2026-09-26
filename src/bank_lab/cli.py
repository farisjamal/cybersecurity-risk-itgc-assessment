"""Small operator CLI for the bank lab package."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from bank_lab.config import Settings
from bank_lab.database import build_engine, build_session_factory
from bank_lab.scenarios import remediate_scenario, retest_scenario, run_scenario
from bank_lab.seed import seed_database


async def _seed(settings: Settings, seed: int) -> int:
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    try:
        async with factory() as session:
            result = await seed_database(session, seed)
        print(
            json.dumps(
                {
                    "seeded": result.created,
                    "counts": result.counts,
                    "business_digest": result.business_digest,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        await engine.dispose()


async def _scenario(settings: Settings, args: argparse.Namespace) -> int:
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    try:
        async with factory() as session:
            if args.action == "run":
                result = await run_scenario(session, args.id, args.resource)
            elif args.action == "remediate":
                result = await remediate_scenario(
                    session, args.id, args.baseline_run, args.resource
                )
            else:
                result = await retest_scenario(
                    session, args.id, args.baseline_run, args.remediation_run
                )
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "scenario_id": result.scenario_id,
                    "status": result.status,
                    "observations": result.observations,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bank-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed", help="seed the migrated lab database")
    seed_parser.add_argument("--seed", type=int, default=42)
    scenario_parser = subparsers.add_parser("scenario", help="run a bounded scenario operation")
    scenario_commands = scenario_parser.add_subparsers(dest="action", required=True)
    scenario_run = scenario_commands.add_parser("run")
    scenario_run.add_argument("--id", required=True, choices=[f"S0{i}" for i in range(1, 7)])
    scenario_run.add_argument("--resource", required=True)
    scenario_remediate = scenario_commands.add_parser("remediate")
    scenario_remediate.add_argument("--id", required=True, choices=[f"S0{i}" for i in range(1, 7)])
    scenario_remediate.add_argument("--resource", required=True)
    scenario_remediate.add_argument("--baseline-run", required=True)
    scenario_retest = scenario_commands.add_parser("retest")
    scenario_retest.add_argument("--id", required=True, choices=[f"S0{i}" for i in range(1, 7)])
    scenario_retest.add_argument("--baseline-run", required=True)
    scenario_retest.add_argument("--remediation-run", required=True)
    args = parser.parse_args(argv)
    if args.command == "seed":
        return asyncio.run(_seed(Settings(), args.seed))
    if args.command == "scenario":
        return asyncio.run(_scenario(Settings(), args))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
