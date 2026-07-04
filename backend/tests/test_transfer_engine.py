from app.services.transfer_engine import create_transfer


class FakeSingleResult:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record


class FakeTx:
    def __init__(self, ongoing_count=0):
        self.created_quantity = None
        self.warehouse_stock = 1000
        self.ongoing_count = ongoing_count

    def run(self, query, **kwargs):
        if "ongoing_count" in query:
            return FakeSingleResult({"ongoing_count": self.ongoing_count})

        if "CREATE (transfer:Transfer" in query:
            self.created_quantity = kwargs["quantity"]
            self.warehouse_stock -= kwargs["quantity"]
            return FakeSingleResult(
                {
                    "transfer": {
                        "id": kwargs["transfer_id"],
                        "status": "ongoing",
                        "quantity": kwargs["quantity"],
                        "delivery_time_minutes": 25,
                        "road_status": "open",
                        "created_at": kwargs["now"],
                        "updated_at": kwargs["now"],
                    },
                    "source": {
                        "id": "warehouse-w1",
                        "name": "Central Medical Warehouse",
                    },
                    "target": {
                        "id": "clinic-b",
                        "name": "Lingwala Screening Center",
                    },
                }
            )

        return FakeSingleResult(
            {
                "source": {
                    "id": "warehouse-w1",
                    "name": "Central Medical Warehouse",
                    "test_kits_stock": self.warehouse_stock,
                },
                "route": {
                    "delivery_time_minutes": 25,
                    "road_status": "open",
                },
                "target": {
                    "id": "clinic-b",
                    "name": "Lingwala Screening Center",
                    "test_kits_available": 0,
                    "people_waiting": 96,
                    "nurses_available": 2,
                    "threshold_min_kits": 50,
                },
            }
        )


class FakeClient:
    def __init__(self, ongoing_count=0):
        self.tx = FakeTx(ongoing_count)

    def write(self, work, **kwargs):
        return work(self.tx, **kwargs)


def test_create_transfer_reserves_warehouse_stock_and_marks_ongoing():
    client = FakeClient()

    transfer = create_transfer(client, "clinic-b", "warehouse-w1")

    assert transfer.status == "ongoing"
    assert transfer.quantity == 96
    assert transfer.source_id == "warehouse-w1"
    assert client.tx.created_quantity == 96
    assert client.tx.warehouse_stock == 904


def test_create_transfer_rejects_duplicate_ongoing_transfer():
    client = FakeClient(ongoing_count=1)

    try:
        create_transfer(client, "clinic-b", "warehouse-w1")
    except ValueError as exc:
        assert "ongoing transfer already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate ongoing transfer to be rejected")
