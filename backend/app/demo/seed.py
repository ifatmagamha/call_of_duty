from __future__ import annotations

from typing import Any

from app.infrastructure.neo4j.client import Neo4jClient
from app.services.risk_service import compute_clinic_metrics, utc_now_iso


CLINICS: list[dict[str, Any]] = [
    {
        "id": "clinic-a",
        "name": "Gombe Response Center",
        "latitude": -4.3070,
        "longitude": 15.3084,
        "test_kits_available": 120,
        "people_waiting": 30,
        "nurses_available": 3,
        "threshold_min_kits": 50,
    },
    {
        "id": "clinic-b",
        "name": "Lingwala Screening Center",
        "latitude": -4.3276,
        "longitude": 15.3136,
        "test_kits_available": 35,
        "people_waiting": 96,
        "nurses_available": 2,
        "threshold_min_kits": 50,
    },
    {
        "id": "clinic-c",
        "name": "Kasa-Vubu Medical Center",
        "latitude": -4.3430,
        "longitude": 15.2980,
        "test_kits_available": 80,
        "people_waiting": 45,
        "nurses_available": 2,
        "threshold_min_kits": 40,
    },
    {
        "id": "clinic-d",
        "name": "Masina Health Post",
        "latitude": -4.3830,
        "longitude": 15.3910,
        "test_kits_available": 20,
        "people_waiting": 60,
        "nurses_available": 1,
        "threshold_min_kits": 30,
    },
    {
        "id": "clinic-e",
        "name": "Mont Ngafula Clinic",
        "latitude": -4.4300,
        "longitude": 15.2300,
        "test_kits_available": 150,
        "people_waiting": 25,
        "nurses_available": 4,
        "threshold_min_kits": 60,
    },
    {
        "id": "clinic-f",
        "name": "Bacongo Response Clinic",
        "latitude": -4.2850,
        "longitude": 15.2420,
        "test_kits_available": 42,
        "people_waiting": 74,
        "nurses_available": 2,
        "threshold_min_kits": 45,
    },
    {
        "id": "clinic-g",
        "name": "Poto-Poto Screening Center",
        "latitude": -4.2630,
        "longitude": 15.2820,
        "test_kits_available": 95,
        "people_waiting": 38,
        "nurses_available": 3,
        "threshold_min_kits": 50,
    },
    {
        "id": "clinic-h",
        "name": "Talangai Health Post",
        "latitude": -4.2220,
        "longitude": 15.2860,
        "test_kits_available": 28,
        "people_waiting": 67,
        "nurses_available": 1,
        "threshold_min_kits": 35,
    },
]

WAREHOUSES: list[dict[str, Any]] = [
    {
        "id": "warehouse-w1",
        "name": "Central Medical Warehouse",
        "latitude": -4.3150,
        "longitude": 15.3220,
        "test_kits_stock": 1000,
    },
    {
        "id": "warehouse-w2",
        "name": "East Logistics Hub",
        "latitude": -4.3850,
        "longitude": 15.4200,
        "test_kits_stock": 450,
    },
    {
        "id": "warehouse-w3",
        "name": "West Emergency Depot",
        "latitude": -4.4200,
        "longitude": 15.2400,
        "test_kits_stock": 300,
    },
]

WAREHOUSE_ROUTES = [
    ("warehouse-w1", "clinic-a", 20, "open"),
    ("warehouse-w1", "clinic-b", 25, "open"),
    ("warehouse-w1", "clinic-c", 30, "open"),
    ("warehouse-w2", "clinic-d", 35, "open"),
    ("warehouse-w2", "clinic-b", 50, "slow"),
    ("warehouse-w3", "clinic-e", 20, "open"),
    ("warehouse-w3", "clinic-c", 45, "open"),
    ("warehouse-w3", "clinic-d", 70, "slow"),
    ("warehouse-w1", "clinic-f", 40, "open"),
    ("warehouse-w1", "clinic-g", 45, "open"),
    ("warehouse-w2", "clinic-h", 65, "slow"),
]

CLINIC_ROUTES = [
    ("clinic-a", "clinic-b", 15, "open", 40),
    ("clinic-c", "clinic-b", 20, "open", 30),
    ("clinic-e", "clinic-d", 40, "open", 60),
    ("clinic-c", "clinic-d", 50, "slow", 30),
    ("clinic-g", "clinic-f", 20, "open", 25),
    ("clinic-f", "clinic-h", 35, "slow", 20),
]


def seed_demo_graph(client: Neo4jClient) -> dict[str, int]:
    def create_constraints(tx):
        tx.run(
            """
            CREATE CONSTRAINT clinic_id IF NOT EXISTS
            FOR (c:Clinic)
            REQUIRE c.id IS UNIQUE
            """
        )
        tx.run(
            """
            CREATE CONSTRAINT warehouse_id IF NOT EXISTS
            FOR (w:Warehouse)
            REQUIRE w.id IS UNIQUE
            """
        )
        tx.run(
            """
            CREATE CONSTRAINT observation_id IF NOT EXISTS
            FOR (o:Observation)
            REQUIRE o.id IS UNIQUE
            """
        )

    def seed_data(tx):
        tx.run("MATCH (n) DETACH DELETE n")

        now = utc_now_iso()
        clinics = []
        for clinic in CLINICS:
            enriched = {
                **clinic,
                **compute_clinic_metrics(clinic),
                "last_updated_at": now,
            }
            clinics.append(enriched)
        tx.run(
            """
            UNWIND $clinics AS clinic
            CREATE (c:Clinic)
            SET c = clinic
            """,
            clinics=clinics,
        )

        warehouses = [
            {**warehouse, "last_updated_at": now} for warehouse in WAREHOUSES
        ]
        tx.run(
            """
            UNWIND $warehouses AS warehouse
            CREATE (w:Warehouse)
            SET w = warehouse
            """,
            warehouses=warehouses,
        )

        tx.run(
            """
            UNWIND $routes AS route
            MATCH (w:Warehouse {id: route.source_id})
            MATCH (c:Clinic {id: route.target_id})
            CREATE (w)-[:CAN_SUPPLY {
              delivery_time_minutes: route.delivery_time_minutes,
              road_status: route.road_status
            }]->(c)
            """,
            routes=[
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "delivery_time_minutes": delivery_time,
                    "road_status": road_status,
                }
                for source_id, target_id, delivery_time, road_status in WAREHOUSE_ROUTES
            ],
        )
        tx.run(
            """
            UNWIND $routes AS route
            MATCH (source:Clinic {id: route.source_id})
            MATCH (target:Clinic {id: route.target_id})
            CREATE (source)-[:CAN_SUPPLY {
              delivery_time_minutes: route.delivery_time_minutes,
              road_status: route.road_status,
              max_transfer_kits: route.max_transfer_kits
            }]->(target)
            """,
            routes=[
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "delivery_time_minutes": delivery_time,
                    "road_status": road_status,
                    "max_transfer_kits": max_transfer,
                }
                for (
                    source_id,
                    target_id,
                    delivery_time,
                    road_status,
                    max_transfer,
                ) in CLINIC_ROUTES
            ],
        )
        return {"clinics": len(clinics), "warehouses": len(warehouses)}

    client.write(create_constraints)
    return client.write(seed_data)
