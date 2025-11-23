import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "http://localhost:8086"

def print_result(test_name, success, message=""):
    status = "PASS" if success else "FAIL"
    print(f"[{status}] {test_name}: {message}")

def make_request(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    req = urllib.request.Request(url, method=method, headers=headers)
    
    if data:
        json_data = json.dumps(data).encode('utf-8')
        req.data = json_data
        
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            try:
                json_body = json.loads(response_body)
            except:
                json_body = response_body
            return status_code, json_body
    except urllib.error.HTTPError as e:
        response_body = e.read().decode('utf-8')
        try:
            json_body = json.loads(response_body)
        except:
            json_body = response_body
        return e.code, json_body
    except Exception as e:
        return 0, str(e)

def run_tests():
    print(f"Starting tests against {BASE_URL}...")
    
    # 1. Health Check
    code, body = make_request("GET", "/health")
    print_result("Health Check", code == 200, f"Code: {code}")

    # 2. GET /unknown (Expected to fail based on code analysis)
    code, body = make_request("GET", "/unknown")
    if code == 404:
        print_result("GET /unknown", False, "Endpoint not implemented (404)")
    else:
        print_result("GET /unknown", code == 200, f"Code: {code}, Body: {body}")

    # 3. POST /weight (IN)
    truck_id = "T-12345"
    data_in = {
        "direction": "in",
        "truck": truck_id,
        "containers": "C-1,C-2",
        "weight": 1000,
        "unit": "kg",
        "produce": "apples",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_in)
    print_result("POST /weight (IN)", code == 201, f"Code: {code}, Body: {body}")
    
    if code != 201:
        print("Skipping dependent tests...")
        return

    # 4. POST /weight (IN) again - Force=False (Should fail)
    code, body = make_request("POST", "/weight", data_in)
    # Spec says: "if force=false will generate an error"
    # Current impl: Likely creates a new session or overwrites without checking?
    print_result("POST /weight (IN) Duplicate Force=False", code != 201, f"Code: {code} (Expected Error), Body: {body}")

    # 5. POST /weight (IN) again - Force=True (Should overwrite)
    data_in_force = data_in.copy()
    data_in_force["force"] = True
    data_in_force["weight"] = 1100
    code, body = make_request("POST", "/weight", data_in_force)
    # Spec says: "if force=true will over-write previous weigh of same truck"
    print_result("POST /weight (IN) Duplicate Force=True", code == 201 or code == 200, f"Code: {code}, Body: {body}")

    # 6. POST /weight (NONE) after IN (Should fail)
    data_none = {
        "direction": "none",
        "truck": truck_id,
        "containers": "C-3",
        "weight": 500,
        "unit": "kg",
        "produce": "pears",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_none)
    # Spec says: "none" after "in" will generate error
    print_result("POST /weight (NONE) after IN", code != 201, f"Code: {code} (Expected Error), Body: {body}")

    # 7. POST /weight (OUT)
    data_out = {
        "direction": "out",
        "truck": truck_id,
        "containers": "C-1,C-2", # Same containers
        "weight": 200, # Empty truck
        "unit": "kg",
        "produce": "apples",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_out)
    print_result("POST /weight (OUT)", code == 201, f"Code: {code}, Body: {body}")

    # 8. POST /weight (OUT) without IN (New truck)
    data_out_bad = data_out.copy()
    data_out_bad["truck"] = "T-99999"
    code, body = make_request("POST", "/weight", data_out_bad)
    print_result("POST /weight (OUT) without IN", code == 404 or code == 400, f"Code: {code} (Expected 404/400), Body: {body}")

    # 9. GET /weight (Filter)
    code, body = make_request("GET", "/weight?filter=in,out")
    print_result("GET /weight", code == 200, f"Code: {code}, Items: {len(body) if isinstance(body, list) else body}")

    # --- EDGE CASES ---
    print("\n--- Edge Case Tests ---")
    
    # 10. Missing Fields
    required_fields = ['direction', 'truck', 'containers', 'weight', 'unit', 'produce', 'force']
    base_data = {
        "direction": "in",
        "truck": "T-EDGE",
        "containers": "C-EDGE",
        "weight": 100,
        "unit": "kg",
        "produce": "test",
        "force": False
    }
    
    for field in required_fields:
        bad_data = base_data.copy()
        del bad_data[field]
        code, body = make_request("POST", "/weight", bad_data)
        print_result(f"Missing Field: {field}", code == 400, f"Code: {code} (Expected 400)")

    # 11. Invalid Weight (Negative)
    bad_data = base_data.copy()
    bad_data["weight"] = -100
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Invalid Weight (Negative)", code == 400, f"Code: {code} (Expected 400)")

    # 12. Invalid Unit
    bad_data = base_data.copy()
    bad_data["unit"] = "tons"
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Invalid Unit", code == 400, f"Code: {code} (Expected 400)")

    # 13. Empty String Fields
    bad_data = base_data.copy()
    bad_data["truck"] = ""
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Empty Truck", code == 400, f"Code: {code} (Expected 400)")

    # 14. Wrong Type for Weight (String)
    bad_data = base_data.copy()
    bad_data["weight"] = "100"
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Weight as String", code == 400, f"Code: {code} (Expected 400)")

    # 15. Float Weight
    bad_data = base_data.copy()
    bad_data["weight"] = 100.5
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Float Weight", code == 400, f"Code: {code} (Expected 400)")

    # 16. Zero Weight
    bad_data = base_data.copy()
    bad_data["weight"] = 0
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Zero Weight", code == 400, f"Code: {code} (Expected 400)")

    # 17. Force as String
    bad_data = base_data.copy()
    bad_data["force"] = "true"
    code, body = make_request("POST", "/weight", bad_data)
    # This might actually work depending on Python's truthy evaluation
    print_result("Force as String", code in [200, 201, 400], f"Code: {code}")

    # 18. Whitespace-Only Truck
    bad_data = base_data.copy()
    bad_data["truck"] = "   "
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Whitespace-Only Truck", code == 400, f"Code: {code} (Expected 400)")

    # 19. Whitespace-Only Produce
    bad_data = base_data.copy()
    bad_data["produce"] = "   "
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Whitespace-Only Produce", code == 400, f"Code: {code} (Expected 400)")

    # 20. Empty Containers for IN
    bad_data = base_data.copy()
    bad_data["containers"] = ""
    code, body = make_request("POST", "/weight", bad_data)
    print_result("Empty Containers (IN)", code == 400, f"Code: {code} (Expected 400)")

    # --- STATE TRANSITION TESTS ---
    print("\n--- State Transition Tests ---")
    
    # 21. OUT → OUT with force=false (Should error)
    # First complete a transaction
    truck_state = "T-STATE-1"
    data_in = {"direction": "in", "truck": truck_state, "containers": "C-X", "weight": 1000, "unit": "kg", "produce": "test", "force": False}
    make_request("POST", "/weight", data_in)
    
    data_out = {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 200, "unit": "kg", "produce": "test", "force": False}
    make_request("POST", "/weight", data_out)
    
    # Try OUT again with force=false
    data_out2 = {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 250, "unit": "kg", "produce": "test", "force": False}
    code, body = make_request("POST", "/weight", data_out2)
    print_result("OUT → OUT (force=false)", code == 400, f"Code: {code} (Expected 400), Body: {body}")

    # 22. OUT → OUT with force=true (Should overwrite)
    data_out3 = {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 300, "unit": "kg", "produce": "test", "force": True}
    code, body = make_request("POST", "/weight", data_out3)
    print_result("OUT → OUT (force=true)", code in [200, 201], f"Code: {code} (Expected 200/201)")

    # 23. NONE → NONE (Should be allowed)
    data_none1 = {"direction": "none", "truck": "na", "containers": "", "weight": 100, "unit": "kg", "produce": "standalone", "force": False}
    code, body = make_request("POST", "/weight", data_none1)
    
    data_none2 = {"direction": "none", "truck": "na", "containers": "", "weight": 150, "unit": "kg", "produce": "standalone", "force": False}
    code, body = make_request("POST", "/weight", data_none2)
    print_result("NONE → NONE", code == 201, f"Code: {code} (Expected 201)")

    # 24. OUT → IN (New session, should work)
    truck_cycle = "T-CYCLE"
    in_data = {"direction": "in", "truck": truck_cycle, "containers": "C-Y", "weight": 1000, "unit": "kg", "produce": "apples", "force": False}
    make_request("POST", "/weight", in_data)
    
    out_data = {"direction": "out", "truck": truck_cycle, "containers": "C-Y", "weight": 200, "unit": "kg", "produce": "apples", "force": False}
    make_request("POST", "/weight", out_data)
    
    # Now try IN again (new session)
    in_data2 = {"direction": "in", "truck": truck_cycle, "containers": "C-Z", "weight": 1100, "unit": "kg", "produce": "oranges", "force": False}
    code, body = make_request("POST", "/weight", in_data2)
    print_result("OUT → IN (New Session)", code == 201, f"Code: {code} (Expected 201)")

    # 25. Multiple Different Trucks IN Simultaneously
    truck_a = "T-MULTI-A"
    truck_b = "T-MULTI-B"
    
    data_a = {"direction": "in", "truck": truck_a, "containers": "C-A", "weight": 500, "unit": "kg", "produce": "apples", "force": False}
    code_a, body_a = make_request("POST", "/weight", data_a)
    
    data_b = {"direction": "in", "truck": truck_b, "containers": "C-B", "weight": 600, "unit": "kg", "produce": "oranges", "force": False}
    code_b, body_b = make_request("POST", "/weight", data_b)
    
    print_result("Multiple Trucks IN Simultaneously", code_a == 201 and code_b == 201, f"Truck A: {code_a}, Truck B: {code_b}")



if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\nAborted.")
