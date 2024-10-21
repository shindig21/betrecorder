import time
import logging
from datetime import datetime
from betfair_api import BetfairAPI

def log_market_data(api, market_id, event_name, output_file):
    """
    Logs the market data every second for the given market until the event starts.
    """
    logger = logging.getLogger('betfair_api')
    logger.info(f"Starting to log market data for {event_name}.")
    start_time = None

    try:
        while True:
            market_books = api.client.betting.list_market_book(
                market_ids=[market_id],
                price_projection={
                    'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'],
                    'virtualise': False
                }
            )

            if market_books:
                market_data = vars(market_books[0])
                timestamp = datetime.utcnow().isoformat()
                market_data['timestamp'] = timestamp

                with open(output_file, 'a') as f:
                    f.write(f"{timestamp}: {market_data}\n")
                
                logger.info(f"Logged market data for {event_name} at {timestamp}")

                # Update start time if available
                if 'market_definition' in market_data and market_data['market_definition']:
                    start_time = datetime.strptime(market_data['market_definition']['market_time'], '%Y-%m-%dT%H:%M:%S.%fZ')

            if start_time and datetime.utcnow() >= start_time:
                logger.info(f"{event_name} has started. Stopping logging.")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Market logging stopped manually.")
    except Exception as e:
        logger.error(f"Error while logging market data: {e}")
    finally:
        api.logout()

def main():
    # Initialize the BetfairAPI instance
    api = BetfairAPI()

    # Configure logging
    logger = logging.getLogger('betfair_api')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler('betfair_api_debug.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    try:
        logger.info("Successfully initialized Betfair API instance.")
        
        # Define the filter for UK horse racing events
        horse_racing_filter = {
            'eventTypeIds': ["7"],  # Horse Racing
            'marketCountries': ["GB"],  # Restrict to UK races
            'marketStartTime': {
                "from": datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z"),
                "to": datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
            }
        }

        # List the available events
        events = api.list_events(horse_racing_filter)
        if not events:
            logger.error("No horse racing events found.")
            return

        logger.info(f"Retrieved {len(events)} events.")

        # Loop through each event sorted by start time
        for event in sorted(events, key=lambda x: x.event.open_date):
            event_name = event.event.name
            market_start_time = event.event.open_date

            logger.info(f"Polling markets for event '{event_name}' starting at {market_start_time}")

            # Fetch market catalogue for the event
            markets = api.client.betting.list_market_catalogue(
                filter={"eventIds": [event.event.id]},
                max_results='100',
                market_projection=['MARKET_START_TIME', 'RUNNER_DESCRIPTION', 'MARKET_DESCRIPTION']
            )

            if not markets:
                logger.warning(f"No markets available for event '{event_name}'")
                continue

            # Sort markets by the amount of money matched
            sorted_markets = sorted(markets, key=lambda x: x.total_matched, reverse=True)

            # Select the market with the most money matched
            top_market = sorted_markets[0]
            logger.info(f"Top Market for Event '{event_name}' (Market ID: {top_market.market_id})")
            logger.info(f"Market Name: {top_market.market_name}, Total Matched: {top_market.total_matched}")

            # Log market data every second until the event starts
            event_log_file = f"{event_name.replace(' ', '_')}_{market_start_time.strftime('%Y%m%d%H%M%S')}.log"
            log_market_data(api, top_market.market_id, event_name, event_log_file)

            # After event has started, move to the next event

    except Exception as e:
        logger.error(f"Error: {e}")

    finally:
        # Log out from the API
        try:
            api.logout()
            logger.info("Logged out from Betfair API.")
        except Exception as e:
            logger.error(f"Error during logout: {e}")

if __name__ == "__main__":
    main()
