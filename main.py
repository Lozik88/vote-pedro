import time
import json
import bs4
import datetime
import subprocess 
import random
import logging
import yaml
import os
import sys

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException

with open("config.yml") as f:
    config = yaml.safe_load(f)

logger = logging.getLogger("vote-pedro")
log_file = os.path.join(config['log_path'],datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".txt")
logging.basicConfig(
    level=config['log_level']
    ,format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ,handlers=[
        logging.FileHandler(log_file)
        ,logging.StreamHandler(sys.stdout)
    ]
    )

def extract_poll_js(url:str=config['poll_page']):
    """
    extracts the javascript used to create the poll.
    the javascript is usually stored under a url like this:
    https://secure.polldaddy.com/p/13562405.js
    """
    browser = create_browser()
    browser.get(url)
    browser

# swap this out with whatever localhost address the flask app is running off of.
url = 'http://127.0.0.1:5000/'

def save_cookies(browser):
    cookies = browser.get_cookies()
    json.dump(cookies,open('cookies.json','w'),indent=3)

def get_available_regions():
    """Fetches the list of available PIA regions."""
    result = subprocess.run(["piactl", "get", "regions"], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Failed to fetch PIA regions.")
        return []
    
    # Split the output by lines to get a list of regions
    regions = result.stdout.strip().split('\n')
    return regions

def connect_to_pia():
    """Connects to a randomly selected PIA region."""
    regions = get_available_regions()
    if not regions:
        logger.error("No regions available to connect.")
        return
    
    # Select a random region
    selected_region = random.choice(regions)
    logger.info(f"Selected region: {selected_region}")

    # Set the region
    try:
        subprocess.run(["piactl", "set", "region", selected_region], check=True)
    except subprocess.CalledProcessError:
        logger.error(f"Failed to set PIA region to {selected_region}.")
        return

    # Connect
    try:
        subprocess.run(["piactl", "connect"], check=True)
        # Wait for the VPN to connect
        while not is_vpn_connected():
            logger.info("Waiting for VPN to connect...")
            time.sleep(2)  # Wait for 2 seconds before checking again
        logger.info("Connected to PIA VPN.")
    except subprocess.CalledProcessError:
        logger.error("Failed to connect to PIA VPN.")

def is_vpn_connected():
    """Checks if the VPN is currently connected."""
    result = subprocess.run(["piactl", "get", "connectionstate"], capture_output=True, text=True)
    # This assumes that the disconnected state is clearly identifiable
    return "Disconnected" not in result.stdout

def disconnect_from_pia():
    """Disconnects from PIA VPN and waits until the disconnection is complete."""
    try:
        subprocess.run(["piactl", "disconnect"], check=True)
        logger.info("Disconnect command issued to PIA VPN.")
        
        # Wait for the VPN to disconnect
        while is_vpn_connected():
            logger.info("Waiting for VPN to disconnect...")
            time.sleep(2)  # Wait for 2 seconds before checking again
            
        logger.info("Disconnected from PIA VPN.")
        
    except subprocess.CalledProcessError:
        logger.error("Failed to issue disconnect command to PIA VPN.")

def create_browser():
    options=Options()
    service = Service(executable_path=config['chrome_driver_path'])
    browser = webdriver.Chrome(
        service=service
        ,options=options
    )
    return browser

def rig_poll(_:int=0,votes_end:int=config['votes_end']):
    vote_counter=0
    disconnect_from_pia()
    logger.info('Rigging poll...')
    form_id = "PDI_form13562405"
    radio_id = 'PDI_answer60615636'
    return_class = 'pds-return-poll'
    browser = create_browser()

    browser.get(url)
    WebDriverWait(browser,30).until(
                    EC.presence_of_element_located(
                        (By.ID,form_id)
                        )
                    )
    total_votes=""
    for i in range(1,votes_end,1):
        # pick candidate
        WebDriverWait(browser,30).until(
                        EC.element_to_be_clickable(
                            (By.ID,radio_id)
                            )
                        )
        radio_btn = browser.find_element(By.ID,radio_id)
        radio_btn.send_keys(Keys.SPACE)
        # time.sleep(random.randint(2,3))
        # radio_btn.submit()
        retry_attempt = 0
        max_attempts = 10
        while True:
            WebDriverWait(browser,30).until(
                            EC.element_to_be_clickable(
                                (By.ID,"pd-vote-button13562405")
                            )
            ).submit()

            # grabbing vote counts. 
            # added retry block because the submit button doesn't always produce poll counts
            try:
                WebDriverWait(browser,10).until(
                                EC.presence_of_element_located(
                                    (By.CLASS_NAME,'pds-feedback-result')
                                    )
                                )
            except (TimeoutException,UnexpectedAlertPresentException) as e:
                if retry_attempt >= max_attempts:
                    raise e
                retry_attempt+=1
                logger.warning("Received timeout error while looking for poll counts. " \
                      f"Attempting retry [{retry_attempt}] of [{max_attempts}]")
                continue
            break



        soup = bs4.BeautifulSoup(browser.page_source, 'html.parser')
        new_total_votes = list([elem for elem in soup.find_all('label') 
                                if 'Riley Harris' in elem.text
                                ][0].children)[2].text.split('(')[1].split(' ')[0]
        if total_votes == new_total_votes:
            logger.warning("Vote total has not changed, assuming polls are IP locked. "\
                  "Acquiring new IP address.")
            disconnect_from_pia()
            connect_to_pia()
            # print("Vote total has not changed from previous count. Taking a snooze...")
            # time.sleep(300)
        total_votes=new_total_votes
        
        # return to poll screen
        WebDriverWait(browser,30).until(
                        EC.presence_of_element_located(
                            (By.CLASS_NAME,return_class)
                            )
                        )
        # time.sleep(random.randint(2,3))
        browser.execute_script('javascript:PDV_go13562405();')
        vote_counter+=1
        logger.info(
            f"Vote cast:{vote_counter} Totals: {total_votes} "\
            f"| {datetime.datetime.now().strftime('%m-%d-%Y, %H:%M:%S')}"
        )
if __name__ == '__main__':
    rig_poll()
