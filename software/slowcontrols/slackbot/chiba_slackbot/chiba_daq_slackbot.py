import sys
from slack import WebClient
from chiba_slackbot import info
import aiohttp
import ssl
import certifi

def retry_connection(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except aiohttp.client_exceptions.ClientConnectorError:
            func(*args, **kwargs)
        return
    return wrapper

def start_bot():
    token = info.token
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    slack_client = WebClient(token=info.token, ssl=ssl_context)
    ##still works in scanbox but not on grappa
    #slack_client = WebClient(token)
    #slack_client.connect()
    #slack_client.chat_postMessage(channel="#chiba-daq", text="Slow Monitoring Online")
    return slack_client

@retry_connection
def send_message(msg):
    slack_client = start_bot()
    slack_client.chat_postMessage(channel=info.channel, text=msg)

@retry_connection
def send_warning(msg, shifter_id=info.shifter_id,
                 expert_id=info.expert_id,
		 admin_id=info.admin_id):
    slack_client = start_bot()
    slack_client.chat_postMessage(channel=info.channel, text=msg)
    slack_client.chat_postMessage(channel=shifter_id, text=msg)
    slack_client.chat_postMessage(channel=expert_id, text=msg)
    slack_client.chat_postMessage(channel=admin_id, text=msg)

@retry_connection
def send_critical(msg, shifter_id=info.shifter_id, expert_id1=info.expert_id,
                  expert_id2=info.shifter_idbkp, admin_id=info.admin_id):
    slack_client = start_bot()
    slack_client.chat_postMessage(channel=info.channel, text=msg)
    slack_client.chat_postMessage(channel=shifter_id, text=msg)
    slack_client.chat_postMessage(channel=expert_id1, text=msg)
    slack_client.chat_postMessage(channel=expert_id2, text=msg)
    slack_client.chat_postMessage(channel=admin_id, text=msg)

@retry_connection
def push_slow_mon(up_file, title):
    slack_client = start_bot()
    with open(up_file, 'rb') as file_content:
        slack_client.files_upload(channels=info.channel,
                    file=file_content, title=title)
##end
