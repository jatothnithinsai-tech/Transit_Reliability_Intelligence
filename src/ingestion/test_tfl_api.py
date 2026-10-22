import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("TFL_API_KEY")

url = "https://api.tfl.gov.uk/Line/Mode/tube/Status"

params = {
    "app_key": api_key
}

response = requests.get(url, params=params)

print("Status code:", response.status_code)

data = response.json()

for item in data:
    line_name = item["name"]
    status = item["lineStatuses"][0]["statusSeverityDescription"]
    print(line_name, "-", status)