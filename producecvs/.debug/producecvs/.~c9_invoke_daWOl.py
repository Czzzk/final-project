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

### S3 ###

def write_s3(df, bucket, name):
    """Write S3 Bucket"""

    csv_buffer = StringIO()
    df.to_csv(csv_buffer)
    s3_resource = boto3.resource('s3')
    filename = f"{name}_sentiment.csv"
    res = s3_resource.Object(bucket, filename).\
        put(Body=csv_buffer.getvalue())
    LOG.info(f"result of write to bucket: {bucket} with:\n {res}")

def extract_text(row, tag):
    element = BeautifulSoup(row, 'html.parser').find_all(tag)
    text = [col.get_text() for col in element]
    return text

def lambda_handler(event, context):
    """Entry Point for Lambda"""

    #LOG.info(f"SURVEYJOB LAMBDA, event {event}, context {context}")
    #receipt_handle  = event['Records'][0]['receiptHandle'] #sqs message
    #'eventSourceARN': 'arn:aws:sqs:us-east-1:561744971673:producer'
    #event_source_arn = event['Records'][0]['eventSourceARN']

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
            print(test_data)
            Store.writerow([s.encode("utf-8") for s in test_data])
    # Write result to S3
    s3 = boto3.resource('s3')
    bucket = s3.Bucket('tcovid-summer-project')
    bucket.upload_file('/tmp/corona.csv','corona.csv')
    #write_s3(df=df, bucket="fangsentiment11", name=names)