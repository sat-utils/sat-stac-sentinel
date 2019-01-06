import boto3
import json
import logging
import os
import requests
import sys

from datetime import datetime
from satstac import STACError, Collection
from satstac.sentinel import transform, SETTINGS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

client = boto3.client('sns', region_name='us-europe-1')

# new Sentinel scene SNS ARN
# arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product

# SNS Topic for publishing STAC Item
sns_arn = 'arn:aws:sns:eu-central-1:552188055668:sentinel-stac'


def lambda_handler(event, context):
    collection = Collection.open('https://sentinel-stac.s3.amazonaws.com/sentinel-2-l1c/catalog.json')
    
    msg = json.loads(event['Records'][0]['Sns']['Message'])
    for m in msg['Records']:
        logger.info('Message: %s' % json.dumps(m))
        url = 'https://%s.s3.amazonaws.com/%s' % (m['s3']['bucket']['name'], m['s3']['object']['key'])
        #id = os.path.splitext(os.path.basename(os.path.dirname(url)))[0]
        data = {
            #'id': id,
            #'datetime': datetime.strptime(id.split('_')[3], '%Y%m%d'),
            'url': url
        }
        # transform to STAC
        item = transform(data)
        logger.debug('Item: %s' % json.dumps(item.data))
        #collection.add_item(item, path=SETTINGS['path_pattern'])
        #logger.info('Added %s as %s' % (item, item.filename))
        #client.publish(TopicArn=sns_arn, Message=json.dumps(item.data))
        #logger.info('Published to %s' % sns_arn)
