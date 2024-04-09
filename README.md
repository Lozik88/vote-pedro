# vote-pedro
This project is used to rig polls hosted by polldaddy.com

## Setup
Installing the required python modules; In CLI use:
```sh
python3 -m pip install -r requirements.txt
```
**NOTE:** Depending on your python installation, you may need to do `python` instead of `python3`.

Install [chromedriver](https://googlechromelabs.github.io/chrome-for-testing/#stable) and save it in this repo's `chromedriver` folder.


**(optional)** In my experience, polldaddy caps voting out at 25 votes per IP. To circumvent this, I'm using [PIA's](https://www.privateinternetaccess.com/download) piactl tool to swap IPs every 25 votes. This will come bundled with PIA desktop by default. If you don't have PIA installed, the application will simply wait 10 minutes before casting additional votes.

## config.yml

| Variable    | Description |
| -------- | ------- |
|chrome_driver_path|Abosulte path where your chromedriver is installed.
|log_path|Path where log files will be stored.|
| flask_url  | The url/address where your flask applicaiton is running  |
| poll_winner |  The person/place/thing you want to vote for. This should be the label that appears in the poll selection. e.g. if the label shows `John Smith` as a voting option, then you would put `John Smith` here.  |
| poll_page    | Web URL containing poll js source. This page should contain the poll you're aiming to rig.     |
|set_dynamic_js|If `True`, the application will scrape the javascript source code from the poll on  `poll_page`. The source code will be saved to `webgui/static/dynamic-poll.js`. Leave this as `False` if you already have the source code. |
|use_dynamic_js|If `True`, the flask application will run `webgui/static/dynamic-poll.js`. If false, it will run `webgui/static/poll.js`|
|votes_end|Number of votes to cast.|

## Running the app
In the CLI use:
```sh
python3 main.py
```