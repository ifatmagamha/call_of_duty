from fastapi import APIRouter, Depends

from app.schemas import SupplyLink
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client

router = APIRouter(tags=["graph"])


@router.get("/supply-links", response_model=list[SupplyLink])
def list_supply_links(client: Neo4jClient = Depends(get_neo4j_client)):
    def work(tx):
        result = tx.run(
            """
            MATCH (source:Warehouse)-[route:CAN_SUPPLY]->(target:Clinic)
            WHERE route.road_status IN ['open', 'slow']
            RETURN source, route, target
            ORDER BY route.delivery_time_minutes ASC
            """
        )
        links = []
        for record in result:
            source = dict(record["source"])
            route = dict(record["route"])
            target = dict(record["target"])
            links.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "source_type": "warehouse",
                    "source_latitude": source["latitude"],
                    "source_longitude": source["longitude"],
                    "target_id": target["id"],
                    "target_name": target["name"],
                    "target_type": "clinic",
                    "target_latitude": target["latitude"],
                    "target_longitude": target["longitude"],
                    "delivery_time_minutes": route["delivery_time_minutes"],
                    "road_status": route["road_status"],
                    "max_transfer_kits": route.get("max_transfer_kits"),
                }
            )
        return links

    return client.read(work)
