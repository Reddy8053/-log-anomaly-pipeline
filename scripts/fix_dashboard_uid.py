import urllib.request
import json
import base64
import sys

def main():
    auth = base64.b64encode(b"admin:admin").decode("utf-8")
    req = urllib.request.Request("http://localhost:3000/api/datasources")
    req.add_header("Authorization", f"Basic {auth}")

    cloudwatch_uid = None

    try:
        with urllib.request.urlopen(req) as resp:
            datasources = json.loads(resp.read().decode())
            for ds in datasources:
                if ds['type'] == 'cloudwatch':
                    cloudwatch_uid = ds['uid']
                    print(f"Found CloudWatch UID: {cloudwatch_uid}")
                    break
    except Exception as e:
        print(f"Error getting datasources: {e}")
        sys.exit(1)

    if not cloudwatch_uid:
        print("No CloudWatch data source found in Grafana!")
        sys.exit(1)

    # Read the dashboard.json
    try:
        with open("grafana/dashboard.json") as f:
            dashboard_str = f.read()
    except Exception as e:
        print(f"Error reading dashboard file: {e}")
        sys.exit(1)

    # Replace the hardcoded uid with the dynamic one
    updated_dashboard_str = dashboard_str.replace('"uid": "cloudwatch"', f'"uid": "{cloudwatch_uid}"')
    dashboard_data = json.loads(updated_dashboard_str)

    payload = json.dumps({
        "dashboard": dashboard_data,
        "overwrite": True
    }).encode("utf-8")

    req2 = urllib.request.Request("http://localhost:3000/api/dashboards/db", data=payload)
    req2.add_header("Content-Type", "application/json")
    req2.add_header("Authorization", f"Basic {auth}")

    try:
        with urllib.request.urlopen(req2) as resp:
            print("Successfully updated dashboard with new UID:", resp.read().decode())
    except Exception as e:
        print(f"Error updating dashboard: {e}")

if __name__ == "__main__":
    main()
