# test_betfair_api.py

from betfair_api import BetfairAPI
from datetime import datetime, timedelta
import json
from tqdm import tqdm  # For progress bar
import os
import logging

def main():
    # Initialize the BetfairAPI instance
    api = BetfairAPI()

    # Configure additional logging for debugging
    logger = logging.getLogger('betfair_api')
    logger.setLevel(logging.DEBUG)
    # Create handlers if not already present
    if not logger.handlers:
        fh = logging.FileHandler('betfair_api_debug.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    # Ensure the 'market_logs' directory exists for storing the JSON files
    logs_dir = 'market_logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        logger.info(f"Created 'market_logs' directory.")

    # Define filters for each sport
    filters = {
        'premier_league_today.json': {
            'eventTypeIds': ["1"],  # Soccer
            'competitionIds': [],  # To be populated with Premier League competition IDs
            'marketStartTime': {
                "from": datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z"),
                "to": datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
            },
            'totalMatched': 10000  # Only log events with total matched over 10,000
        },
        'mens_tennis_today.json': {
            'eventTypeIds': ["2"],  # Tennis
            'marketStartTime': {
                "from": datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z"),
                "to": datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
            }
        },
        'uk_horse_racing_today.json': {
            'eventTypeIds': ["7"],  # Horse Racing
            'marketCountries': ["GB"],  # Restrict to UK races
            'marketStartTime': {
                "from": datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z"),
                "to": datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
            }
        }
    }

    # Fetch competitions to get Premier League competition IDs
    try:
        football_filter = {"eventTypeIds": ["1"]}
        competitions = api.client.betting.list_competitions(filter=football_filter)
        if competitions:
            premier_league_ids = [
                comp.competition.id for comp in competitions
                if "Premier League" in comp.competition.name
            ]
            filters['premier_league_today.json']['competitionIds'] = premier_league_ids
            logger.info(f"Premier League competition IDs: {premier_league_ids}")
        else:
            logger.warning("No competitions retrieved for Premier League.")
    except Exception as e:
        logger.error(f"Error retrieving competitions: {e}")
        return

    # Initialize a dictionary to hold filtered events
    filtered_events = {
        'premier_league_today.json': [],
        'uk_horse_racing_today.json': [],
        'mens_tennis_today.json': []
    }

    # Fetch events for each sport based on the defined filters
    for filename, market_filter in filters.items():
        try:
            events = api.list_events(market_filter=market_filter)
            if events:
                for event in tqdm(events, desc=f"Processing {filename}"):
                    # Modify the market projection to remove unsupported fields
                    markets = api.client.betting.list_market_catalogue(
                        filter={"eventIds": [event.event.id]},
                        max_results='100',
                        market_projection=['MARKET_START_TIME', 'RUNNER_METADATA']  # Adjust market_projection
                    )
                    # Process and filter markets
                    for market in markets:
                        if filename == 'premier_league_today.json' and market.total_matched < 10000:
                            continue  # Skip markets with less than £10,000 matched
                        
                        market_info = {
                            'market_id': market.market_id,
                            'market_name': market.market_name,
                            'event_name': event.event.name,
                            'total_matched': market.total_matched,
                            'market_start_time': market.market_start_time.isoformat()
                        }
                        filtered_events[filename].append(market_info)

                # Write the filtered events to a JSON file in the 'market_logs' directory
                output_file = os.path.join(logs_dir, filename)
                with open(output_file, 'w') as f:
                    json.dump(filtered_events[filename], f, indent=4)
                logger.info(f"{len(filtered_events[filename])} events logged to '{output_file}'.")

        except Exception as e:
            logger.error(f"Error processing events for {filename}: {e}")

    # Logout from the Betfair API after operations
    try:
        api.logout()
        logger.info("Logged out from Betfair API.")
    except Exception as e:
        logger.error(f"Error during logout: {e}")

if __name__ == "__main__":
    main()
