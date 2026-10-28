import requests
import json

# Test the new advanced risk analysis endpoint
url = 'http://127.0.0.1:5000/advanced_risk_analysis'
headers = {'Content-Type': 'application/json'}
data = {'sector': 'IT'}

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        result = response.json()
        print('API call successful!')
        print(f'Sector: {result.get("sector")}')
        print(f'Risk counts: {result.get("risk_counts")}')
        print(f'Safest stock: {result.get("safest_stock")}')
        print(f'Number of insights: {len(result.get("insights", []))}')
        print(f'Number of table rows: {len(result.get("table_data", []))}')
    else:
        print(f'API call failed with status: {response.status_code}')
        print(response.text)
except Exception as e:
    print(f'Error: {e}')