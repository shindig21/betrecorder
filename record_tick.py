# record_tick.py

from betfair_api import BetfairAPI

def main():
    # Initialize the BetfairAPI instance
    api = BetfairAPI()

    # Specify the market ID you want to subscribe to
    # Replace with a valid and active market ID obtained from 'markets_log.json' or other sources
    market_id = "1.234509152"  # Example: Replace with a valid market ID

    # Start recording tick data and display it in real-time
    try:
        api.record_tick_data(market_id=market_id, output_file='tick_data.json')
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure logout is called in case of unexpected errors
        api.logout()

if __name__ == "__main__":
    main()
