# poll_events.py

from betfair_api import BetfairAPI
from datetime import datetime, timedelta
import json

def main():
    # Initialize the BetfairAPI instance
    api = BetfairAPI()

    # Define the event type IDs or competition IDs you want to monitor
    # For example, to monitor Soccer and Horse Racing:
    # Event Type IDs can be found in your 'event_types.json' file
    selected_event_type_ids = ["1", "7"]  # "1" for Soccer, "7" for Horse Racing

    # Alternatively, you can specify competition IDs
    # selected_competition_ids = ["12345", "67890"]  # Replace with actual competition IDs

    # Start polling for new events every 60 seconds and log them to 'new_events.json'
    try:
        api.poll_new_events(
            interval=60,
            output_file='new_events.json',
            event_type_ids=selected_event_type_ids
            # competition_ids=selected_competition_ids  # Uncomment and set if using competition IDs
        )
    except Exception as e:
        print(f"An error occurred during polling: {e}")
    finally:
        # Ensure logout is called in case of unexpected errors
        api.logout()

if __name__ == "__main__":
    main()
