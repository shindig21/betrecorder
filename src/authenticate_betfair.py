import os
from dotenv import load_dotenv
from betfairlightweight import APIClient
from betfairlightweight.exceptions import BetfairError
import logging
import pprint
 
# Configure logging for detailed debug output
logging.basicConfig(level=logging.DEBUG)
 
# Load environment variables from .env file
load_dotenv()
 
# Retrieve credentials and SSL paths from environment variables
USERNAME = os.getenv('BETFAIR_USERNAME')
PASSWORD = os.getenv('BETFAIR_PASSWORD')
APP_KEY = os.getenv('BETFAIR_APP_KEY')
CERT_FILE = os.getenv('BETFAIR_CERT_FILE')
KEY_FILE = os.getenv('BETFAIR_KEY_FILE')
 
# Debug: Verify that environment variables are loaded
print(f"USERNAME: {'Loaded' if USERNAME else 'Not Loaded'}")
print(f"PASSWORD: {'Loaded' if PASSWORD else 'Not Loaded'}")
print(f"APP_KEY: {'Loaded' if APP_KEY else 'Not Loaded'}")
print(f"CERT_FILE: {'Loaded' if CERT_FILE else 'Not Loaded'}")
print(f"KEY_FILE: {'Loaded' if KEY_FILE else 'Not Loaded'}")
 
# Debug: Print cert_files tuple
print(f"CERT_FILES: ({CERT_FILE}, {KEY_FILE})")
 
# Validate that necessary environment variables are set
if not all([USERNAME, PASSWORD, APP_KEY, CERT_FILE, KEY_FILE]):
    raise EnvironmentError("One or more environment variables are missing. Please check your .env file.")
 
# Initialize the Betfair API client with SSL certificates as a tuple
client = APIClient(
    username=USERNAME,
    password=PASSWORD,
    app_key=APP_KEY,
    cert_files=(CERT_FILE, KEY_FILE)  # Tuple of (cert_file, key_file)
    # Removed 'debug=True' as it's not a valid parameter
)
 
def authenticate():
    try:
        # Perform login
        client.login()
        print("Successfully authenticated with Betfair API.")
 
        # Fetch account details
        account_details = client.account.get_account_details()
        print("Account Details:")
        pprint.pprint(vars(account_details))  # Use vars() to get __dict__
 
    except BetfairError as e:
        print(f"Failed to authenticate with Betfair API: {e}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)
 
if __name__ == "__main__":
    authenticate()
    # Remember to logout after operations are complete
    client.logout()
    print("Logged out from Betfair API.")
