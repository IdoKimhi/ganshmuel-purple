import requests
import time

WEIGHT = "http://localhost:8082"
BILLING = "http://localhost:8088"
# WEIGHT = "http://weight-app:5000"
# BILLING = "http://billing-app:5000"



def wait_for_service(url, name):
    print(f"Waiting for {name}...")
    for i in range(30):
        try:
            r = requests.get(url)
            if r.status_code == 200:
                print(f"{name} is ready!")
                return
        except:
            pass
        time.sleep(1)
    raise Exception(f"{name} did NOT start")


def test_e2e_flow():

    wait_for_service(WEIGHT + "/health", "WEIGHT")
    wait_for_service(BILLING + "/health", "BILLING")

    provider_name = f"test-provider-{int(time.time())}"
    truck_id = f"TRK-{int(time.time())}"

    print("\n=== STEP 1: Create Provider ===")
    r = requests.post(BILLING + "/provider", json={"name": provider_name})
    assert r.status_code in (200, 201)
    provider_id = r.json()["id"]
    print("Provider ID:", provider_id)

    print("\n=== STEP 2: Register Truck ===")
    r = requests.post(BILLING + "/truck", json={"id": truck_id, "provider": int(provider_id)})
    assert r.status_code in (200, 201)
    print("Truck registered:", truck_id)

    print("\n=== STEP 3: Weight IN ===")
    r = requests.post(WEIGHT + "/weight", json={
        "direction": "in",
        "truck": truck_id,
        "containers": "C1",
        "weight": 1000,
        "unit": "kg",
        "force": False,
        "produce": "orange"
    })
    assert r.status_code in (200, 201)
    print("IN OK")

    print("\n=== STEP 4: Weight OUT ===")
    r = requests.post(WEIGHT + "/weight", json={
        "direction": "out",
        "truck": truck_id,
        "containers": "C1",
        "weight": 700,
        "unit": "kg",
        "force": False,
        "produce": "orange"
    })
    assert r.status_code in (200, 201)
    neto = r.json()["neto"]
    assert isinstance(neto, int)
    print("OUT OK, neto =", neto)

    time.sleep(1)

    print("\n=== STEP 5: Upload rates ===")
    r = requests.post(BILLING + "/rates", params={"file": "rates.xlsx"})
    assert r.status_code in (200, 201)
    print("Rates uploaded")

    print("\n=== STEP 6: Get Bill ===")
    r = requests.get(f"{BILLING}/bill/{provider_id}")
    assert r.status_code == 200
    bill = r.json()
    print("Bill:", bill)

    assert bill["truckCount"] == 1
    assert bill["sessionCount"] >= 1

    # חיפוש פרי orange בביל
    found = any(p["product"] == "orange" for p in bill["products"])
    assert found, "orange product missing from bill!"

    print("\n🎉 E2E FLOW — PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_e2e_flow()
