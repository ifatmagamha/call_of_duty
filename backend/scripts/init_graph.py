import argparse

from app.demo.seed import seed_demo_graph
from app.infrastructure.neo4j.client import Neo4jClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Neo4j operational graph.")
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Delete configured graph data and recreate the deterministic demo graph.",
    )
    args = parser.parse_args()
    if not args.reset_demo:
        parser.error("Pass --reset-demo to acknowledge destructive demo reset.")
    client = Neo4jClient()
    try:
        client.verify_connectivity()
        result = seed_demo_graph(client)
        print(f"Neo4j demo graph initialized: {result}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
