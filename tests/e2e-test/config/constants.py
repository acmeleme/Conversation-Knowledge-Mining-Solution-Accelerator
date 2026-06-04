from dotenv import load_dotenv
import os
import json

load_dotenv()
URL = os.getenv('url') or ''
if URL.endswith('/'):
    URL = URL[:-1]

API_URL = os.getenv('api_url') or ''
if API_URL.endswith('/'):
    API_URL = API_URL[:-1]

USERNAME = os.getenv('USERNAME', '')
PASSWORD = os.getenv('PASSWORD', '')

# Resolve path relative to this file (tests/e2e-test/config/constants.py)
# Always works regardless of which directory pytest is invoked from.
_e2e_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_file_path = os.path.join(_e2e_root, 'testdata', 'prompts.json')

with open(json_file_path, 'r') as file:
    data = json.load(file)
    questions = data['questions']

