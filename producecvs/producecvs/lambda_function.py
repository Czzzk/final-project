import json

import boto3
import botocore
#import pandas as pd
import pandas as pd
import boto3
from io import StringIO
import requests
from bs4 import BeautifulSoup
import csv
import datetime


#SETUP LOGGING
import logging
from pythonjsonlogger import jsonlogger

LOG = logging.getLogger()
LOG.setLevel(logging.DEBUG)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
LOG.addHandler(logHandler)

#S3 BUCKET
REGION = "us-east-1"

def extract_text(row, tag):
    element = BeautifulSoup(row, 'html.parser').find_all(tag)
    text = [col.get_text() for col in element]
    return text

def lambda_handler(event, context):
    """Entry Point for Lambda"""

    today=datetime.date.today()
    url = "https://www.worldometers.info/coronavirus/"
    html = requests.get(url)
    bs_obj = BeautifulSoup(html.content, "html.parser")
    table = bs_obj.find(id = "main_table_countries_yesterday")
    content = table.find_all('td')
    rows = table.find_all('tr')
    
    heading = rows.pop(0)
    heading_row = extract_text(str(heading), 'th')[1:9]
    with open('/tmp/corona.csv', 'w') as store:
        Store = csv.writer(store, delimiter=',')
        Store.writerow(heading_row)
        for row in rows:
            test_data = extract_text(str(row), 'td')[1:9]
            Store.writerow(test_data)
    # Write result to S3
    s3 = boto3.resource('s3')
    bucket = s3.Bucket('covid.summer.project')
    bucket.upload_file('/tmp/corona.csv',f'{today}.csv')