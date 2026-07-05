SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties
RETURN name, labelsOrTypes, properties ORDER BY name;

MATCH (n)
UNWIND labels(n) AS label
RETURN label, count(n) AS node_count ORDER BY label;

MATCH (o:Observation)-[r:OBSERVED_AT]->(c:Clinic)
RETURN count(r) AS observation_links,
       count(DISTINCT o) AS linked_observations,
       count(DISTINCT c) AS observed_clinics;

MATCH (w:Warehouse)-[r:CAN_SUPPLY]->(c:Clinic)
RETURN count(r) AS warehouse_supply_routes;
