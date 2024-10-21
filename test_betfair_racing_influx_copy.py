import time
import logging
import signal
import sys
from datetime import datetime, timedelta
import pytz
from betfair_api import BetfairAPI
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from betfairlightweight import filters  # Import filters for market filtering
from betfairlightweight.exceptions import BetfairError
import yaml
from threading import Event, Thread
from datetime import timezone
import betfairlightweight
from betfairlightweight.endpoints.baseendpoint import BaseEndpoint



# Load configuration from config.yaml
def load_config():
    with open("config.yaml", 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Error loading YAML configuration: {exc}")
            sys.exit(1)

# Initialize InfluxDB Client
def init_influx_client(config):
    influx_client = InfluxDBClient(url=config['influxdb']['url'], token=config['influxdb']['token'], org=config['influxdb']['org'])
    return influx_client.write_api(write_options=SYNCHRONOUS)

# Global termination event for graceful shutdown
terminate_event = Event()

# Signal handler for graceful shutdown
def signal_handler(sig, frame, logger):
    logger.info("Termination signal received. Shutting down gracefully...")
    terminate_event.set()

# Set up logging
def setup_logging():
    logger = logging.getLogger('betfair_api')
    logger.setLevel(logging.INFO)  # Set to INFO to reduce verbosity
    if not logger.handlers:
        fh = logging.FileHandler('betfair_api_debug.log')
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

# Get UK timezone aware time
def get_uk_time():
    utc_now = datetime.utcnow()
    return utc_now.replace(tzinfo=pytz.utc)

# Re-authenticate if session error occurs
def handle_session_error(api, logger):
    try:
        logger.info("Re-authenticating due to session expiry.")
        api.client.login()
        logger.info("Re-authentication successful.")
    except BetfairError as e:
        logger.error(f"Failed to re-authenticate: {e}")

# Fetch events with proper filtering
def fetch_events(api, logger):
    horse_racing_filter = {
        'eventTypeIds': ["7"],  # Horse Racing
        'marketCountries': ["GB"],  # Restrict to UK races
        'marketStartTime': {
            "from": get_uk_time().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (get_uk_time() + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
        }
    }

    events = api.list_events(horse_racing_filter)
    if not events:
        logger.error("No horse racing events found.")
        return []

    # Exclude unwanted event names
    excluded_keywords = ["(F/C)", "(RFC)", "Daily Win Dist Odds"]
    filtered_events = [
        event for event in events
        if not any(keyword in event.event.name for keyword in excluded_keywords)
    ]

    # Print retrieved events for inspection
    print("Retrieved Events:")
    for event in filtered_events:
        print(f"Event Name: {event.event.name}, Start Time: {event.event.open_date}, Event ID: {event.event.id}")

    return sorted(filtered_events, key=lambda x: x.event.open_date)


# Poll and log markets for a given event, then select the market with the largest total matched near event start time
def poll_markets_for_event(api, event, logger):
    event_name = event.event.name
    event_start_time = event.event.open_date

    # Ensure event_start_time is in UTC
    event_start_time = event_start_time.astimezone(pytz.utc) if event_start_time.tzinfo else event_start_time.replace(tzinfo=pytz.utc)
    
    logger.info(f"Polling markets for event '{event_name}' starting at {event_start_time} (UTC)")
    
    try:
        # Define a filter for market retrieval
        market_catalogue_filter = filters.market_filter(event_ids=[event.event.id])
        markets = api.client.betting.list_market_catalogue(
            filter=market_catalogue_filter,
            market_projection=['MARKET_START_TIME', 'MARKET_DESCRIPTION'],  # Include MARKET_DESCRIPTION to get market_type
            max_results='100',
            sort='FIRST_TO_START'
        )

        if not markets:
            logger.warning(f"No markets available for event '{event_name}'")
            return None

        # ---  Print raw API response ---
        print("Raw API Response:")
        print(markets._data)
        print(markets[0]._data) 
        # ------------------------------

        # Output all market details
        print(f"Markets for event '{event_name}':")
        for market in markets:
            market_type = market._data['marketDescription']['marketType']  # Access through _data
            print(f"Market ID: {market.market_id}, Market Name: {market.market_name}, Market Type: {market_type}, "
                    f"Total Matched: {market.total_matched}, Market Start Time: {market.market_start_time}")

        # Apply a time tolerance to filter valid markets
        time_tolerance = timedelta(minutes=30)  # Adjust time window
        valid_markets = [
            m for m in markets 
            if m.market_start_time and 
            abs(m.market_start_time.replace(tzinfo=pytz.utc) - event_start_time) <= time_tolerance
        ]

        if not valid_markets:
            logger.warning(f"No markets found starting around the event start time for '{event_name}'")
            return None

        # Select the top market by total matched
        top_market = max(valid_markets, key=lambda x: x.total_matched, default=None)

        if top_market:
            market_type = top_market._data['marketDescription']['marketType']  # Access through _data
            logger.info(f"Selected Market for Event '{event_name}': Market ID {top_market.market_id}, "
                        f"Name: {top_market.market_name}, Market Type: {market_type}, Total Matched: {top_market.total_matched}")
        else:
            logger.warning(f"No valid markets found for event '{event_name}'")
        
        return top_market

    except BetfairError as e:
        logger.error(f"Error fetching markets for event '{event_name}': {e}")
        return None







# Poll and log market data
def log_market_data(api, market_id, event_name, market_start_time, runner_names, logger, write_api, config):
    try:
        while not terminate_event.is_set():
            try:
                market_books = api.client.betting.list_market_book(
                    market_ids=[market_id],
                    price_projection={
                        'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'],
                        'virtualise': False
                    }
                )

                if market_books:
                    market_data = market_books[0]._data
                    market_data['timestamp'] = get_uk_time().isoformat()

                    # Define the necessary variables
                    market_name = market_books[0].market_name  # Or retrieve from market details
                    market_type = market_books[0].market_type  # Assuming market_description has market_type

                    if market_data.get('totalMatched', 0) > 0:
                        point = Point("betting_market") \
                            .tag("market_id", market_data['marketId']) \
                            .tag("market_name", market_name) \
                            .tag("event_name", event_name) \
                            .tag("market_type", market_type) \
                            .field("total_matched", float(market_data['totalMatched'])) \
                            .field("total_available", float(market_data.get('totalAvailable', 0))) \
                            .field("bet_delay", market_data['betDelay']) \
                            .field("number_of_runners", market_data['numberOfRunners']) \
                            .field("number_of_active_runners", market_data['numberOfActiveRunners']) \
                            .field("status", market_data['status']) \
                            .time(get_uk_time())

                        write_api.write(config['influxdb']['bucket'], config['influxdb']['org'], point)

                        logger.info(f"Logged market data for '{event_name}' at {market_data['timestamp']}")
                    else:
                        logger.warning(f"Market '{market_id}' for '{event_name}' has 'totalMatched' <= 0. Skipping logging.")

                if market_start_time is None:
                    logger.warning(f"Market start time is None for '{event_name}'. Skipping.")
                    break

                if datetime.utcnow() >= market_start_time:
                    logger.info(f"Market '{market_id}' for '{event_name}' has started. Stopping logging.")
                    break

                time.sleep(1)
            except BetfairError as e:
                if '403' in str(e):
                    logger.error("Status code error: 403. Re-authenticating.")
                    handle_session_error(api, logger)
                else:
                    logger.error(f"Unexpected error: {e}")
                    raise
    finally:
        try:
            api.logout()
            logger.info(f"Logged out from Betfair API for Market ID: {market_id}.")
        except BetfairError as e:
            logger.error(f"Error during logout for Market ID: {market_id}: {e}")



# Main function to drive the execution
def main():
    config = load_config()
    write_api = init_influx_client(config)
    logger = setup_logging()

    print(f"betfairlightweight version: {betfairlightweight.__version__}")

    # Register the signal handler for graceful termination
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, logger))

    try:
        api = BetfairAPI()
        logger.info("Successfully initialized Betfair API instance.")

        events = fetch_events(api, logger)
        if not events:
            return

        for event in events:
            if terminate_event.is_set():
                logger.info("Termination signal received. Exiting event loop.")
                break

            # Poll all markets for the event
            top_market = poll_markets_for_event(api, event, logger)
            if not top_market:
                continue

            # Build runner name map
            runner_names = {runner.selection_id: runner.runner_name for runner in top_market.runners}

            # Start logging market data for the selected market
            log_thread = Thread(
                target=log_market_data,
                args=(api, top_market.market_id, event, top_market.market_start_time, runner_names, logger, write_api, config),
                daemon=True
            )   


            # Wait for the current market to start or termination signal
            while log_thread.is_alive() and not terminate_event.is_set():
                time.sleep(1)

    finally:
        terminate_event.set()
        try:
            api.logout()
            logger.info("Logged out from Betfair API.")
        except BetfairError as e:
            logger.error(f"Error during logout: {e}")

if __name__ == "__main__":
    main()

