import argparse
import asyncio
import json

from app.core.config import get_settings
from app.infrastructure.crusoe.client import CrusoeClient
from app.infrastructure.neo4j.client import Neo4jClient
from app.services.system_diagnostics import SystemDiagnostics


async def run(check_neo4j: bool, check_crusoe: bool) -> int:
    settings = get_settings()
    output = {}
    success = True
    neo4j_client = Neo4jClient() if check_neo4j else None
    try:
        diagnostics = SystemDiagnostics(
            settings,
            neo4j_client=neo4j_client,
            crusoe_client=CrusoeClient(settings) if check_crusoe else None,
        )
        if check_neo4j:
            graph = diagnostics.check_neo4j()
            output["neo4j"] = graph.model_dump(mode="json")
            success = success and graph.connected and graph.required_constraints_present
        if check_crusoe:
            crusoe = await diagnostics.check_crusoe()
            output["crusoe"] = crusoe.model_dump(mode="json")
            success = success and crusoe.all_models_accessible
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if success else 1
    finally:
        if neo4j_client is not None:
            neo4j_client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely verify Neo4j graph shape and Crusoe model access."
    )
    parser.add_argument("--neo4j", action="store_true", help="Check Neo4j only.")
    parser.add_argument("--crusoe", action="store_true", help="Check Crusoe only.")
    args = parser.parse_args()
    check_both = not args.neo4j and not args.crusoe
    return asyncio.run(run(args.neo4j or check_both, args.crusoe or check_both))


if __name__ == "__main__":
    raise SystemExit(main())
