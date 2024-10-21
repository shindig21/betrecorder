# poll_tick.py

from betfair_api import BetfairAPI

def main():
    # Initialize the BetfairAPI instance
    api = BetfairAPI()

    # Specify the market ID you want to poll
    # Replace with a valid and active market ID obtained from 'test_betfair_api.py' or other sources
    market_id = "1.234509152"  # Example: Replace with a valid market ID

    # Specify polling interval in seconds
    polling_interval = 5  # Adjust as needed, e.g., 5 seconds

    # Specify output file
    output_file = 'tick_data.json'

    # Start polling
    try:
        api.poll_market_book(market_id=market_id, interval=polling_interval, output_file=output_file)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure logout is called in case of unexpected errors
        api.logout()

if __name__ == "__main__":
    main()
