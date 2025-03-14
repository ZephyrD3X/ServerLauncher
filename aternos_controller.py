import asyncio
import time
import cloudscraper
from bs4 import BeautifulSoup
from logging_config import logger
from config import (
    ATERNOS_USERNAME,
    ATERNOS_PASSWORD,
    ATERNOS_LOGIN_URL,
    ATERNOS_SERVER_LIST_URL
)

class AternosController:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'windows',
                'mobile': False
            },
            delay=10
        )
        self._setup_lock = asyncio.Lock()
        self._max_retries = 3
        self._retry_delay = 5  # seconds
        self.selected_server = None

    async def initialize(self):
        """Initialize session"""
        try:
            logger.info("Initializing session...")
            # Go directly to the login page
            response = await self._make_request('get', ATERNOS_LOGIN_URL)
            if not response.url.endswith('/go/'):
                raise Exception("Failed to access login page directly")
            logger.info("Successfully accessed login page")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    async def _make_request(self, method, url, **kwargs):
        """Make a request with retry logic"""
        for attempt in range(self._max_retries):
            try:
                # Add common browser-like headers
                headers = kwargs.get('headers', {})
                headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                kwargs['headers'] = headers

                if method.lower() == 'get':
                    response = self.scraper.get(url, **kwargs)
                else:
                    response = self.scraper.post(url, **kwargs)

                # Log response details
                logger.debug(f"Request URL: {url}")
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response URL: {response.url}")
                logger.debug(f"Response headers: {dict(response.headers)}")

                try:
                    logger.debug(f"Response content: {response.text[:500]}...")
                except:
                    logger.debug("Could not log response content")

                response.raise_for_status()
                return response

            except Exception as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt + 1 == self._max_retries:
                    raise
                await asyncio.sleep(self._retry_delay)

    async def login(self):
        """Login to Aternos"""
        try:
            await self.initialize()

            logger.info("Accessing homepage to find signup/login links...")
            homepage_url = "https://aternos.org/:en/"
            homepage_response = await self._make_request('get', homepage_url)
            homepage_soup = BeautifulSoup(homepage_response.text, 'html.parser')
            
            # Look for the mod-signup class that contains login links
            signup_mod = homepage_soup.find(class_="mod-signup")
            
            login_link = None
            if signup_mod:
                logger.info("Found mod-signup section")
                # Look for login link
                links = signup_mod.find_all('a')
                for link in links:
                    if 'login' in link.get_text().lower() or 'login' in link.get('href', '').lower():
                        login_link = link.get('href')
                        logger.info(f"Found login link: {login_link}")
                        break
            
            if not login_link:
                logger.warning("Could not find login link in mod-signup, using default login URL")
                login_link = ATERNOS_LOGIN_URL
            
            # Make sure it's a full URL
            if not login_link.startswith('http'):
                login_link = f"https://aternos.org{login_link}"
            
            logger.info(f"Navigating to login page: {login_link}")
            response = await self._make_request('get', login_link)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Based on the HTML content, find the login form
            # The form might be in different structures, so we'll try multiple approaches
            # Find all login form divs
            form_divs = soup.find_all("div", class_="login-form")

            if not form_divs:
                logger.error("Could not find login form")
                raise Exception("Login form not found")

            # Since find_all() returns a list, pick the first form if multiple exist
            form = form_divs[0]

            # Find username and password inputs
            username_input = form.find("input", class_="username")  # Username field
            password_input = form.find("input", class_="password")  # Password field

            if not username_input or not password_input:
                logger.error("Could not find username/password inputs")
                logger.debug(f"Form HTML: {form.prettify()}")
                raise Exception("Login form elements not found")

            # Get the form action URL
            form_action = form.get('action', '')
            if form_action:
                if not form_action.startswith('http'):
                    form_action = f"https://aternos.org{form_action}"
            else:
                form_action = ATERNOS_LOGIN_URL

            # Extract hidden fields
            hidden_inputs = {}
            for hidden in form.find_all("input", type="hidden"):
                name = hidden.get('name')
                value = hidden.get('value', '')
                if name:
                    hidden_inputs[name] = value
                    logger.debug(f"Found hidden input: {name}={value}")

            # Submit login form
            logger.info("Submitting login form...")
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://aternos.org',
                'Referer': response.url
            }

            login_data = {
                **hidden_inputs,
                username_input.get('name', 'user'): ATERNOS_USERNAME,
                password_input.get('name', 'password'): ATERNOS_PASSWORD,
                'remember': 'true'
            }
            
            logger.debug(f"Login data keys: {login_data.keys()}")
            
            login_response = await self._make_request(
                'post',
                form_action,
                data=login_data,
                headers=headers,
                allow_redirects=True
            )

            # Save cookies after login
            self.scraper.cookies.update(login_response.cookies)
            
            # Wait briefly before verifying
            await asyncio.sleep(2)

            # Verify login by accessing server list
            logger.info("Verifying login...")
            verify_response = await self._make_request('get', ATERNOS_SERVER_LIST_URL)
            
            # Check if logged in by looking for signs of logged-in state
            if 'logout' in verify_response.text.lower() or 'account' in verify_response.text.lower():
                logger.info("Successfully logged into Aternos")
                return True
            else:
                logger.error("Login verification failed")
                raise Exception("Login verification failed")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    async def select_server(self, server_name: str = None):
        """Select a server from the list by name"""
        try:
            # Get the server list page
            response = await self._make_request('get', ATERNOS_SERVER_LIST_URL)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try different selectors for server cards based on the HTML snippet
            server_cards = []
            
            # Try different selectors
            selectors = [
                'div.server',
                '.servercardlist div',
                'a[href^="/server/"]',
                'div[data-id]'  # From the HTML it appears servers have data-id
            ]
            
            for selector in selectors:
                server_cards = soup.select(selector)
                if server_cards:
                    logger.debug(f"Found {len(server_cards)} server cards using selector: {selector}")
                    break
            
            if not server_cards:
                # If no servers found with selectors, try looking for server information directly
                server_headers = soup.find_all(['h2', 'h3', 'div'], string=lambda s: s and "#" in s)
                if server_headers:
                    server_cards = server_headers
                    logger.debug(f"Found {len(server_cards)} server headers")
            
            if not server_cards:
                # Last resort: look for any element with server IDs or names
                for tag in soup.find_all(['div', 'a', 'span']):
                    if tag.get('data-id') or (tag.text and "#" in tag.text):
                        server_cards.append(tag)

            if not server_cards:
                raise Exception("No servers found")

            selected = None
            actual_name = None
            server_id = None
            
            if server_name:
                # Find server by name in various attributes and content
                for card in server_cards:
                    card_text = card.get_text(strip=True)
                    title = card.get('title', '').strip()
                    
                    # Check various places where the name might be
                    potential_names = [
                        title,
                        card_text,
                        card.get('data-name', ''),
                        card.get('id', '')
                    ]
                    
                    if any(server_name.lower() in name.lower() for name in potential_names if name):
                        selected = card
                        actual_name = next((name for name in potential_names if name), "Unknown")
                        logger.debug(f"Found matching server: {actual_name}")
                        break

                if not selected:
                    raise Exception(f"Server '{server_name}' not found")
            else:
                # Select first server
                selected = server_cards[0]
                actual_name = (
                    selected.get('title', '') or 
                    selected.get_text(strip=True) or 
                    selected.get('data-name', 'Unknown Server')
                )
                logger.debug(f"Selected default server: {actual_name}")

            # Try to get server ID using different methods
            server_id = (
                selected.get('data-id') or 
                selected.get('href', '').split('/')[-1] if selected.name == 'a' else None
            )
            
            # If no ID found, try to extract from text (e.g., "#NXQg3wb6jW304RtI")
            if not server_id and '#' in selected.get_text():
                text = selected.get_text()
                hash_index = text.find('#')
                if hash_index >= 0:
                    potential_id = text[hash_index+1:].strip()
                    # Take the first "word" after # as ID
                    server_id = potential_id.split()[0] if ' ' in potential_id else potential_id
            
            if not server_id:
                # If still no ID, look for any child elements that might contain the ID
                for child in selected.find_all():
                    if child.get('data-id'):
                        server_id = child.get('data-id')
                        break
                    elif child.get('href') and '/server/' in child.get('href'):
                        server_id = child.get('href').split('/')[-1]
                        break
            
            if not server_id:
                raise Exception("Could not find server ID")

            self.selected_server = f"https://aternos.org/server/{server_id}"
            logger.info(f"Successfully selected server: {actual_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to select server: {e}")
            raise

    async def get_server_status(self):
        """Get current server status"""
        try:
            if not self.selected_server:
                # If no server is selected, try to select the first one
                await self.select_server()
                if not self.selected_server:
                    raise Exception("No server selected and couldn't auto-select one")

            response = await self._make_request('get', self.selected_server)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Based on HTML, try different status element selectors
            status_selectors = [
                '.status', 
                '.server-status', 
                '.statuslabel-label',
                'div:contains("Offline")',  # From the attached HTML
                'div[class*="status"]',
                '.statusicon',
                'div.status-label'
            ]
            
            status_element = None
            for selector in status_selectors:
                try:
                    if selector.startswith('div:contains'):
                        # Special case for contains selector
                        text = selector.split('"')[1]
                        for div in soup.find_all('div'):
                            if text in div.get_text():
                                status_element = div
                                break
                    else:
                        status_element = soup.select_one(selector)
                    
                    if status_element:
                        logger.debug(f"Found status element with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
            
            if status_element:
                status_text = status_element.get_text(strip=True)
                logger.info(f"Server status: {status_text}")
                return status_text
            
            # If we couldn't find a status element with specific classes,
            # look for common status text in the page
            for status_text in ["Offline", "Online", "Starting", "Stopping", "In Queue"]:
                if soup.find(string=lambda s: s and status_text in s):
                    logger.info(f"Found status text: {status_text}")
                    return status_text
            
            # Last resort - check for start/stop buttons to infer status
            start_button = soup.find('a', class_='btn-start') or soup.find('a', class_='start')
            stop_button = soup.find('a', class_='btn-stop') or soup.find('a', class_='stop')
            
            if stop_button and not start_button:
                return "Online"
            elif start_button and not stop_button:
                return "Offline"
            
            logger.warning("Status element not found")
            return "Status unavailable"

        except Exception as e:
            logger.error(f"Failed to get server status: {e}")
            raise

    async def start_server(self):
        """Start the Minecraft server"""
        try:
            if not self.selected_server:
                # If no server is selected, try to select the first one
                await self.select_server()
                if not self.selected_server:
                    raise Exception("No server selected and couldn't auto-select one")

            # First, check if the server is already running
            current_status = await self.get_server_status()
            if current_status.lower() in ["online", "starting", "in queue"]:
                logger.info(f"Server is already {current_status}, no need to start")
                return False

            response = await self._make_request('get', self.selected_server)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple approaches to find start button
            start_button = None
            
            # 1. Look for start button by class
            start_selectors = [
                'a.btn-start', 
                'a.start', 
                'div.start', 
                'button.start',
                'a:contains("Start")',
                'button:contains("Start")'
            ]
            
            for selector in start_selectors:
                try:
                    if ':contains' in selector:
                        # Handle contains selector
                        tag_type = selector.split(':')[0]
                        text = selector.split('"')[1]
                        for elem in soup.find_all(tag_type):
                            if text in elem.get_text():
                                start_button = elem
                                break
                    else:
                        start_button = soup.select_one(selector)
                    
                    if start_button:
                        logger.debug(f"Found start button with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
            
            # 2. Look for any element with text "Start" or href containing "start"
            if not start_button:
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    if 'start' in href.lower() or 'start' in a.get_text().lower():
                        start_button = a
                        break
            
            # 3. Look for any buttons with text "Start"
            if not start_button:
                for button in soup.find_all(['button', 'input', 'div']):
                    if 'start' in button.get_text().lower():
                        start_button = button
                        break

            if start_button:
                # Get the start URL
                start_url = None
                if start_button.name == 'a':
                    start_url = start_button.get('href')
                elif start_button.get('onclick'):
                    # Try to extract URL from onclick attribute
                    onclick = start_button.get('onclick')
                    if 'window.location' in onclick and 'http' in onclick:
                        start_url = onclick.split("'")[1] if "'" in onclick else onclick.split('"')[1]
                
                if not start_url:
                    # Try data attributes 
                    start_url = start_button.get('data-href') or start_button.get('data-url')
                
                if not start_url:
                    # Last resort: look for form with action
                    form = start_button.find_parent('form')
                    if form and form.get('action'):
                        start_url = form.get('action')
                
                if not start_url:
                    # If still no URL, try AJAX approach
                    logger.info("No direct URL found, using default start endpoint")
                    start_url = f"{self.selected_server}/start"
                
                if not start_url.startswith('http'):
                    start_url = f"https://aternos.org{start_url}"

                # Make the request to start the server
                logger.info(f"Starting server with URL: {start_url}")
                await self._make_request('get', start_url)
                
                # Sometimes Aternos requires confirmation
                await asyncio.sleep(2)
                confirm_response = await self._make_request('get', self.selected_server)
                confirm_soup = BeautifulSoup(confirm_response.text, 'html.parser')
                
                # Look for confirm button
                confirm_button = confirm_soup.find(string=lambda s: s and "Confirm" in s)
                if confirm_button:
                    confirm_element = confirm_button.parent
                    confirm_url = confirm_element.get('href')
                    if confirm_url:
                        if not confirm_url.startswith('http'):
                            confirm_url = f"https://aternos.org{confirm_url}"
                        await self._make_request('get', confirm_url)
                        logger.info("Confirmed server start")
                
                logger.info("Server start initiated")
                return True
            else:
                logger.warning("Start button not found - server might be already running")
                return False

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise

    async def stop_server(self):
        """Stop the Minecraft server"""
        try:
            if not self.selected_server:
                # If no server is selected, try to select the first one
                await self.select_server()
                if not self.selected_server:
                    raise Exception("No server selected and couldn't auto-select one")
            
            # First, check if the server is already stopped
            current_status = await self.get_server_status()
            if current_status.lower() in ["offline", "stopping"]:
                logger.info(f"Server is already {current_status}, no need to stop")
                return False

            response = await self._make_request('get', self.selected_server)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple approaches to find stop button
            stop_button = None
            
            # 1. Look for stop button by class
            stop_selectors = [
                'a.btn-stop', 
                'a.stop', 
                'div.stop', 
                'button.stop',
                'a:contains("Stop")',
                'button:contains("Stop")'
            ]
            
            for selector in stop_selectors:
                try:
                    if ':contains' in selector:
                        # Handle contains selector
                        tag_type = selector.split(':')[0]
                        text = selector.split('"')[1]
                        for elem in soup.find_all(tag_type):
                            if text in elem.get_text():
                                stop_button = elem
                                break
                    else:
                        stop_button = soup.select_one(selector)
                    
                    if stop_button:
                        logger.debug(f"Found stop button with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
            
            # 2. Look for any element with text "Stop" or href containing "stop"
            if not stop_button:
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    if 'stop' in href.lower() or 'stop' in a.get_text().lower():
                        stop_button = a
                        break
            
            # 3. Look for any buttons with text "Stop"
            if not stop_button:
                for button in soup.find_all(['button', 'input', 'div']):
                    if 'stop' in button.get_text().lower():
                        stop_button = button
                        break

            if stop_button:
                # Get the stop URL
                stop_url = None
                if stop_button.name == 'a':
                    stop_url = stop_button.get('href')
                elif stop_button.get('onclick'):
                    # Try to extract URL from onclick attribute
                    onclick = stop_button.get('onclick')
                    if 'window.location' in onclick and 'http' in onclick:
                        stop_url = onclick.split("'")[1] if "'" in onclick else onclick.split('"')[1]
                
                if not stop_url:
                    # Try data attributes 
                    stop_url = stop_button.get('data-href') or stop_button.get('data-url')
                
                if not stop_url:
                    # Last resort: look for form with action
                    form = stop_button.find_parent('form')
                    if form and form.get('action'):
                        stop_url = form.get('action')
                
                if not stop_url:
                    # If still no URL, try AJAX approach
                    logger.info("No direct URL found, using default stop endpoint")
                    stop_url = f"{self.selected_server}/stop"
                
                if not stop_url.startswith('http'):
                    stop_url = f"https://aternos.org{stop_url}"

                # Make the request to stop the server
                logger.info(f"Stopping server with URL: {stop_url}")
                await self._make_request('get', stop_url)
                
                # Sometimes Aternos requires confirmation
                await asyncio.sleep(2)
                confirm_response = await self._make_request('get', self.selected_server)
                confirm_soup = BeautifulSoup(confirm_response.text, 'html.parser')
                
                # Look for confirm button
                confirm_button = confirm_soup.find(string=lambda s: s and "Confirm" in s)
                if confirm_button:
                    confirm_element = confirm_button.parent
                    confirm_url = confirm_element.get('href')
                    if confirm_url:
                        if not confirm_url.startswith('http'):
                            confirm_url = f"https://aternos.org{confirm_url}"
                        await self._make_request('get', confirm_url)
                        logger.info("Confirmed server stop")
                
                logger.info("Server stop initiated")
                return True
            else:
                logger.warning("Stop button not found - server might be already stopped")
                return False

        except Exception as e:
            logger.error(f"Failed to stop server: {e}")
            raise

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            self.scraper.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")