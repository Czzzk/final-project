import json
import os
import boto3
import botocore
#import pandas as pd
import pandas as pd
import boto3
import sys
import fpdf
import datetime
from io import StringIO

#send email
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import uuid


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

#email
SENDER = "Sender Name <czk990815@gmail.com>"
RECIPIENT = "czk990815@gmail.com"
AWS_REGION = "us-east-1"
SUBJECT = "COVID-19 UPDATE"


### SQS Utils###
def sqs_queue_resource(queue_name):
    """Returns an SQS queue resource connection
    Usage example:
    In [2]: queue = sqs_queue_resource("dev-job-24910")
    In [4]: queue.attributes
    Out[4]:
    {'ApproximateNumberOfMessages': '0',
     'ApproximateNumberOfMessagesDelayed': '0',
     'ApproximateNumberOfMessagesNotVisible': '0',
     'CreatedTimestamp': '1476240132',
     'DelaySeconds': '0',
     'LastModifiedTimestamp': '1476240132',
     'MaximumMessageSize': '262144',
     'MessageRetentionPeriod': '345600',
     'QueueArn': 'arn:aws:sqs:us-west-2:414930948375:dev-job-24910',
     'ReceiveMessageWaitTimeSeconds': '0',
     'VisibilityTimeout': '120'}
    """

    sqs_resource = boto3.resource('sqs', region_name=REGION)
    log_sqs_resource_msg = "Creating SQS resource conn with qname: [%s] in region: [%s]" %\
     (queue_name, REGION)
    LOG.info(log_sqs_resource_msg)
    queue = sqs_resource.get_queue_by_name(QueueName=queue_name)
    return queue

def sqs_connection():
    """Creates an SQS Connection which defaults to global var REGION"""

    sqs_client = boto3.client("sqs", region_name=REGION)
    log_sqs_client_msg = "Creating SQS connection in Region: [%s]" % REGION
    LOG.info(log_sqs_client_msg)
    return sqs_client

def sqs_approximate_count(queue_name):
    """Return an approximate count of messages left in queue"""

    queue = sqs_queue_resource(queue_name)
    attr = queue.attributes
    num_message = int(attr['ApproximateNumberOfMessages'])
    num_message_not_visible = int(attr['ApproximateNumberOfMessagesNotVisible'])
    queue_value = sum([num_message, num_message_not_visible])
    sum_msg = """'ApproximateNumberOfMessages' and 'ApproximateNumberOfMessagesNotVisible' = *** [%s] *** for QUEUE NAME: [%s]""" %\
         (queue_value, queue_name)
    LOG.info(sum_msg)
    return queue_value

def delete_sqs_msg(queue_name, receipt_handle):

    sqs_client = sqs_connection()
    try:
        queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
        delete_log_msg = "Deleting msg with ReceiptHandle %s" % receipt_handle
        LOG.info(delete_log_msg)
        response = sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    except botocore.exceptions.ClientError as error:
        exception_msg = "FAILURE TO DELETE SQS MSG: Queue Name [%s] with error: [%s]" %\
            (queue_name, error)
        LOG.exception(exception_msg)
        return None

    delete_log_msg_resp = "Response from delete from queue: %s" % response
    LOG.info(delete_log_msg_resp)
    return response

def create_sentiment(row):
    """Uses AWS Comprehend to Create Sentiments on a DataFrame"""

    LOG.info(f"Processing {row}")
    comprehend = boto3.client(service_name='comprehend')
    payload = comprehend.detect_sentiment(Text=row, LanguageCode='en')
    LOG.debug(f"Found Sentiment: {payload}")
    sentiment = payload['Sentiment']
    return sentiment

def apply_sentiment(df, column="wikipedia_snippit"):
    """Uses Pandas Apply to Create Sentiment Analysis"""

    df['Sentiment'] = df[column].apply(create_sentiment)
    return df

### S3 ###

def lambda_handler(event, context):
    """Entry Point for Lambda"""
    today=datetime.date.today()
    
    LOG.info(f"SURVEYJOB LAMBDA, event {event}, context {context}")
    receipt_handle  = event['Records'][0]['receiptHandle'] #sqs message
    #'eventSourceARN': 'arn:aws:sqs:us-east-1:561744971673:producer'
    event_source_arn = event['Records'][0]['eventSourceARN']

    names = [] #Captured from Queue
    
    # Process Queue
    for record in event['Records']:
        body = json.loads(record['body'])
        countryname = body['name']

        #Capture for processing
        names.append(countryname)

        extra_logging = {"body": body, "countryname":countryname}
        LOG.info(f"SQS CONSUMER LAMBDA, splitting sqs arn with value: {event_source_arn}",extra=extra_logging)
        qname = event_source_arn.split(":")[-1]
        extra_logging["queue"] = qname
        LOG.info(f"Attemping Deleting SQS receiptHandle {receipt_handle} with queue_name {qname}", extra=extra_logging)
        res = delete_sqs_msg(queue_name=qname, receipt_handle=receipt_handle)
        LOG.info(f"Deleted SQS receipt_handle {receipt_handle} with res {res}", extra=extra_logging)
    
    
    
    s3 = boto3.resource('s3')
    # get your credentials from environment variables
    #aws_id = os.environ['AWS_ID']
    #aws_secret = os.environ['AWS_SECRET']
    client = boto3.client('s3')
    bucket_name = 'covid.summer.project'
    object_key = '{}.csv'.format(today)
    csv_obj = client.get_object(Bucket=bucket_name, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string))
    
    names = ["China","USA"]
    for name in names:
        
        result = df.loc[df['Country,Other'] == name]
        finalresult = ["{}:{}".format(i,result[i].iloc[0]) for i in list(result.columns)]
        pdf = fpdf.FPDF(format='letter')
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        for i in finalresult:
            pdf.write(5,str(i))
            pdf.ln()
        pdf.output("/tmp/testings.pdf")
        
        bucket = s3.Bucket('daily.case.country')
        bucket.upload_file('/tmp/testings.pdf',f'{name}_{today}.pdf')
        
        Key = 'testings.pdf'
        
        ATTACHMENT = '/tmp/{}'.format(Key)
        
        # The email body for recipients with non-HTML email clients.
        BODY_TEXT = "Hello,\r\nPlease see the attached file for the update of COVID-19."
        
        # The HTML body of the email.
        BODY_HTML = """\
        <html>
        <head></head>
        <body>
        <h1>Hello!</h1>
        <p>Please see the attached file for the update of COVID-19.</p>
        </body>
        </html>
        """
        
        # The character encoding for the email.
        CHARSET = "utf-8"
        
        # Create a new SES resource and specify a region.
        client = boto3.client('ses',region_name=AWS_REGION)
        
        # Create a multipart/mixed parent container.
        msg = MIMEMultipart('mixed')
        # Add subject, from and to lines.
        msg['Subject'] = SUBJECT 
        msg['From'] = SENDER 
        msg['To'] = RECIPIENT
        
        # Create a multipart/alternative child container.
        msg_body = MIMEMultipart('alternative')
        
        # Encode the text and HTML content and set the character encoding. This step is
        # necessary if you're sending a message with characters outside the ASCII range.
        textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
        htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)
        
        # Add the text and HTML parts to the child container.
        msg_body.attach(textpart)
        msg_body.attach(htmlpart)
        
        # Define the attachment part and encode it using MIMEApplication.
        att = MIMEApplication(open(ATTACHMENT, 'rb').read())
        
        # Add a header to tell the email client to treat this part as an attachment,
        # and to give the attachment a name.
        att.add_header('Content-Disposition','attachment',filename=os.path.basename(ATTACHMENT))
        
        # Attach the multipart/alternative child container to the multipart/mixed
        # parent container.
        msg.attach(msg_body)
        
        # Add the attachment to the parent container.
        msg.attach(att)
        #print(msg)
        try:
            #Provide the contents of the email.
            response = client.send_raw_email(
                Source=SENDER,
                Destinations=[
                    RECIPIENT
                ],
                RawMessage={
                    'Data':msg.as_string(),
                },
                #ConfigurationSetName=CONFIGURATION_SET
            )
        # Display an error if something goes wrong.	
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            print("Email sent! Message ID:"),
            print(response['MessageId'])
    
    # Write result to S3
    #write_s3(df=df, bucket="fangsentiment11", name=names)