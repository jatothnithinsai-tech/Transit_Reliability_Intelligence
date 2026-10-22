import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("TFL_API_KEY")

if api_key:
    print("TfL API key loaded successfully")
else:
    print("TfL API key NOT found")