import logging
import requests
import time

logger = logging.getLogger(__name__)

class ApiClient:
    def __init__(self, config):
        self.config = config

    def fetch_data(self, retries=3, backoff_factor=0.5):
        """Fetch data with retry mechanism and proper error handling"""

        if not self.config.LIVE_UPDATES_API_URL or not self.config.BEARER_TOKEN:
            logger.critical("LIVE_UPDATES_API_URL and BEARER_TOKEN must be set")
            return None

        headers = {
            'Authorization': f'Bearer {self.config.BEARER_TOKEN}',
            'User-Agent': 'okhttp/3.14.9',
            'Content-Type': 'application/json; charset=UTF-8'
        }

        data = {
            "InputType": "PObKiG8pSHLNiMt7C0uIuYbdF0WNRXG5GvLp5gd5sdw="
        }
        
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.config.LIVE_UPDATES_API_URL,
                    headers=headers,
                    json=data,
                    timeout=10  # 10 second timeout
                )
                
                response.raise_for_status()
                
                json_response = response.json()
                if not isinstance(json_response, dict) or 'Data' not in json_response:
                    raise ValueError("Invalid API response format")
                    
                return json_response
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (attempt + 1))
                continue
                
        logger.critical("Failed to fetch data after maximum retries")
        return None

    def fetch_home_data(self, retries=3, backoff_factor=0.5):
        """Fetch home data with retry mechanism and proper error handling"""

        if not self.config.HOME_DATA_API_URL or not self.config.BEARER_TOKEN:
            logger.critical("HOME_DATA_API_URL and BEARER_TOKEN must be set")
            return None

        headers = {
            'Authorization': f'Bearer {self.config.BEARER_TOKEN}',
            'User-Agent': 'okhttp/3.14.9',
            'Content-Type': 'application/json; charset=UTF-8'
        }

        data = {
            "InputType": "PObKiG8pSHLNiMt7C0uIuYbdF0WNRXG5GvLp5gd5sdw="
        }

        for attempt in range(retries):
            try:
                response = requests.post(
                    self.config.HOME_DATA_API_URL,
                    headers=headers,
                    json=data,
                    timeout=2  # 10 second timeout
                )

                response.raise_for_status()

                json_response = response.json()
                if not isinstance(json_response, dict) or 'Data' not in json_response:
                    raise ValueError("Invalid API response format")

                return json_response

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (attempt + 1))
                continue

        logger.critical("Failed to fetch home data after maximum retries")
        return None