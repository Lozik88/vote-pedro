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
import requests
import shutil

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, 
    UnexpectedAlertPresentException, 
    NoSuchElementException
    )
project_path = os.path.join(os.path.dirname(__file__))
with open("config.yml") as f:
    config = yaml.safe_load(f)

logger = logging.getLogger("vote-pedro")
log_file = os.path.join(config['log_path'],datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".txt")
logging.basicConfig(
    level=config['log_level']
    ,format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"
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
    # <script type="text/javascript" src="https://secure.polldaddy.com/p/13562405.js"></script>
    # scroll down the page until js source is found
    for _ in range(0,25):
        browser.find_element(By.TAG_NAME,"body").send_keys(Keys.PAGE_DOWN)
    # extract poll javascript from page
    try:
        js_url = browser.find_element(By.XPATH,".//script[starts-with(@src,'https://secure.polldaddy.com/p/')]").get_attribute("src")
    except NoSuchElementException as e:
        logger.error("polldaddy source url wasn't found. " \
                     "You may have encountered a CAPTCHA or the poll on this page doesn't " \
                     "use https://secure.polldaddy.com/p/")
        raise e
    browser.close()
    return js_url

def create_js_file(url:str):
    """
    The `url` is the secure.polldaddy.com url that contains the specific poll id
    The js source will be extracted and  saved to dynamic-poll.js for the flask application.
    """
    response = requests.get(url)
    with open(os.path.join('webgui','static','dynamic-poll.js'),'w') as f:
        f.write(response.text)

def set_dynamic_page(url:str=config["poll_page"]):
    """
    Routine to setup dynamic-poll.js. `url` is the webpage that contains the poll you want to rig.
    """
    js_url = extract_poll_js(url)
    create_js_file(js_url)

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
        
    except subprocess.CalledProcessError as e:
        logger.error("Failed to issue disconnect command to PIA VPN.")

def get_radio_id(browser,poll_winner:str=config["poll_winner"]):
    return browser \
        .find_element(By.XPATH,f".//span[contains(text(),'{poll_winner}')]") \
        .find_element(By.XPATH,"./..") \
        .get_attribute("for")

def get_form_id(browser):
    return browser \
        .find_element(By.XPATH,".//form[contains(@id,'PDI_form')]") \
        .get_attribute("id")

def create_browser(is_headless:bool=False,**kwargs):
    """Creates a selenium browser"""
    options=Options()
    if is_headless:
        options.add_argument("--headless") 
    service = Service(executable_path=config['chrome_driver_path'])
    browser = webdriver.Chrome(
        service=service
        ,options=options
    )
    return browser

def rig_poll(
        _:int=0
        ,votes_end:int=config['votes_end']
        ,poll_winner:str=config["poll_winner"]
        ):
    logger.info('Rigging poll...')
    
    has_pia = bool(shutil.which("piactl"))
    if has_pia:
        disconnect_from_pia()
    
    vote_counter=0
    return_class = 'pds-return-poll'
    browser = create_browser()
    browser.get(config["flask_url"])
    
    radio_id = get_radio_id(browser,poll_winner)
    form_id = get_form_id(browser)
    poll_id = form_id.split("PDI_form")[-1]
    WebDriverWait(browser,30).until(
                    EC.presence_of_element_located(
                        (By.ID,form_id)
                        )
                    )
    total_votes=""
    start_time = datetime.datetime.now()
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
                                # (By.ID,"pd-vote-button13562405")
                                (By.ID,f"pd-vote-button{poll_id}")
                            )
            ).submit()
            # ty_for_votes = browser.find_elements(By.XPATH,".//div[@class='pds-question-top']")
            # if ty_for_votes:
            #     if 'we have already counted your vote' in ty_for_votes[0].text:
            #         time.sleep(10)
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
                                if poll_winner in elem.text
                                ][0].children)[2].text.split('(')[1].split(' ')[0]
        if total_votes == new_total_votes:
            if has_pia:
                logger.warning("Vote total has not changed, assuming polls are IP locked. "\
                    "Acquiring new IP address.")
                disconnect_from_pia()
                connect_to_pia()
                time.sleep(5)
            else:
                print("Vote total has not changed from previous count. Taking a snooze...")
                time.sleep(300)
        total_votes=new_total_votes
        
        # return to poll screen
        WebDriverWait(browser,30).until(
                        EC.presence_of_element_located(
                            (By.CLASS_NAME,return_class)
                            )
                        )
        # time.sleep(random.randint(2,3))
        browser.execute_script(f'javascript:PDV_go{poll_id}();')
        vote_counter+=1
        diff_time = datetime.datetime.now() - start_time
        hours, remainder = divmod(diff_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        logger.info(
            f"Vote cast:{vote_counter} | Totals: {total_votes} "\
            f"| To: [{poll_winner}]" \
            f"| TotalTime: " \
                f"{str(hours).rjust(2,'0')}" \
                f":{str(minutes).rjust(2,'0')}" \
                f":{str(seconds).rjust(2,'0')}"
        )

def start_flask_app():
    flask_script = os.path.join(project_path,"webgui","main.py")
    os.environ["FLASK_APP"] = flask_script
    subprocess.Popen(
        ["flask","run"]
        ,env = os.environ
        )
    
if __name__ == '__main__':
    start_flask_app()
    rig_poll()