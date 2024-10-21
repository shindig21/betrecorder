# betfair_api.py

import os
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from betfairlightweight import APIClient
from betfairlightweight.exceptions import BetfairError
import logging

class BetfairAPI:
    def __init__(self, config_path='.env'):
        # Configure logging to file and console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("betfair_api.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Load environment variables
        load_dotenv(dotenv_path=config_path)
        self.username = os.getenv('BETFAIR_USERNAME')
        self.password = os.getenv('BETFAIR_PASSWORD')
        self.app_key = os.getenv('BETFAIR_APP_KEY')
        self.cert_file = os.getenv('BETFAIR_CERT_FILE')
        self.key_file = os.getenv('BETFAIR_KEY_FILE')

        # Validate environment variables
        if not all([self.username, self.password, self.app_key, self.cert_file, self.key_file]):
            self.logger.error("One or more environment variables are missing. Please check your .env file.")
            raise EnvironmentError("Missing environment variables.")

        # Initialize API client
        try:
            self.client = APIClient(
                username=self.username,
                password=self.password,
                app_key=self.app_key,
                cert_files=(self.cert_file, self.key_file)
            )
            self.client.login()
            self.logger.info("Authenticated with Betfair API.")
        except BetfairError as e:
            self.logger.error(f"Failed to authenticate with Betfair API: {e}")
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during API client initialization: {e}")
            raise

    def logout(self):
        try:
            self.client.logout()
            self.logger.info("Logged out from Betfair API.")
        except BetfairError as e:
            self.logger.error(f"Error during logout: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during logout: {e}")

    def list_event_types(self):
        try:
            event_types = self.client.betting.list_event_types()
            self.logger.info("Retrieved event types.")
            return event_types
        except BetfairError as e:
            self.logger.error(f"Error retrieving event types: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving event types: {e}")
            return None

    def list_events(self, market_filter=None):
        try:
            if market_filter is None:
                market_filter = {}
            events = self.client.betting.list_events(filter=market_filter)
            self.logger.info(f"Retrieved {len(events)} events.")
            return events
        except BetfairError as e:
            self.logger.error(f"Error retrieving events: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving events: {e}")
            return None

    def list_competitions(self, competition_filter=None, locale='en'):
        try:
            if competition_filter is None:
                competition_filter = {}
            competitions = self.client.betting.list_competitions(filter=competition_filter, locale=locale)
            self.logger.info(f"Retrieved {len(competitions)} competitions.")
            return competitions
        except BetfairError as e:
            self.logger.error(f"Error retrieving competitions: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving competitions: {e}")
            return None

    def list_market_types(self):
        try:
            market_types = self.client.betting.list_market_types()
            self.logger.info("Retrieved market types.")
            return market_types
        except BetfairError as e:
            self.logger.error(f"Error retrieving market types: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving market types: {e}")
            return None

    def poll_market_book(self, market_id, interval=5, output_file='tick_data.json'):
        """
        Polls the market book for the specified market ID at regular intervals and records tick data.
        
        :param market_id: The ID of the market to poll.
        :param interval: Time between polls in seconds.
        :param output_file: Path to the output file.
        """
        self.logger.info(f"Starting to poll market book for market ID: {market_id} every {interval} seconds.")
        last_data = None

        try:
            while True:
                try:
                    market_books = self.client.betting.list_market_book(
                        market_ids=[market_id],
                        price_projection={
                            'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'],
                            'virtualise': False
                        }
                    )
                    
                    if market_books:
                        current_data = vars(market_books[0])  # Use vars() to convert to dict
                        current_timestamp = datetime.utcnow().isoformat()

                        # Compare with last_data to detect changes
                        if last_data is None or current_data != last_data:
                            # Add timestamp
                            current_data['timestamp'] = current_timestamp

                            # Append to output file with custom serialization
                            with open(output_file, 'a') as f:
                                f.write(json.dumps(current_data, default=str) + '\n')

                            self.logger.info(f"Tick Data Recorded at {current_timestamp} for market ID {market_id}.")
                            
                            # Update last_data
                            last_data = current_data
                        else:
                            self.logger.debug(f"No changes detected at {current_timestamp} for market ID {market_id}.")
                    else:
                        self.logger.warning(f"No market book data retrieved for market ID: {market_id}.")

                except BetfairError as e:
                    self.logger.error(f"BetfairError during polling: {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error during polling: {e}")

                time.sleep(interval)
        except KeyboardInterrupt:
            self.logger.info("Polling stopped by user.")
        finally:
            self.logout()

    def poll_new_events(self, interval=60, output_file='new_events.json', event_type_ids=None, competition_ids=None):
        """
        Polls for new events at regular intervals and logs them to a file with a timestamp.

        :param interval: Time between polls in seconds.
        :param output_file: Path to the output file.
        :param event_type_ids: List of event type IDs to filter events.
        :param competition_ids: List of competition IDs to filter events.
        """
        self.logger.info(f"Starting to poll new events every {interval} seconds.")
        known_event_ids = self._load_known_event_ids()

        try:
            while True:
                # Define your filters here (modify as needed)
                filter = {
                    'marketStartTime': {
                        'from': (datetime.utcnow() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        'to': (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    }
                }
                if event_type_ids:
                    filter['eventTypeIds'] = event_type_ids
                if competition_ids:
                    filter['competitionIds'] = competition_ids

                current_events = self.list_events(market_filter=filter)
                if current_events:
                    new_events = [event for event in current_events if event.event.id not in known_event_ids]
                    if new_events:
                        timestamp = datetime.utcnow().isoformat()
                        with open(output_file, 'a') as f:
                            for event in new_events:
                                event_dict = {
                                    'event_id': event.event.id,
                                    'event_name': event.event.name,
                                    'country_code': event.event.country_code,
                                    'competition_id': event.event.competition_id,
                                    'market_start_time': event.market_start_time,
                                    'timestamp': timestamp
                                }
                                f.write(json.dumps(event_dict) + '\n')
                        self.logger.info(f"Logged {len(new_events)} new events at {timestamp}.")
                        # Update known_event_ids
                        known_event_ids.update(event.event.id for event in new_events)
                        self._save_known_event_ids(known_event_ids)
                    else:
                        self.logger.debug("No new events found.")
                else:
                    self.logger.debug("No events retrieved.")
                time.sleep(interval)
        except KeyboardInterrupt:
            self.logger.info("Polling stopped by user.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during polling: {e}")
            self.logout()

    def _load_known_event_ids(self, file_path='known_events.json'):
        """
        Loads known event IDs from a file to avoid duplicate logging.

        :param file_path: Path to the file storing known event IDs.
        :return: A set of known event IDs.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    known_event_ids = set(json.load(f))
                    self.logger.debug(f"Loaded {len(known_event_ids)} known event IDs.")
                    return known_event_ids
                except json.JSONDecodeError:
                    self.logger.warning("Known events file is corrupted. Starting fresh.")
                    return set()
        else:
            self.logger.debug("No known events file found. Starting fresh.")
            return set()

    def _save_known_event_ids(self, known_event_ids, file_path='known_events.json'):
        """
        Saves known event IDs to a file.

        :param known_event_ids: A set of known event IDs.
        :param file_path: Path to the file storing known event IDs.
        """
        with open(file_path, 'w') as f:
            json.dump(list(known_event_ids), f)
        self.logger.debug(f"Saved {len(known_event_ids)} known event IDs.")
