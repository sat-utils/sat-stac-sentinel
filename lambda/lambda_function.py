import boto3
import json
import logging
import sys

import os.path as op

from datetime import datetime
from satstac import STACError, Collection
from satstac.sentinel import transform, SETTINGS, get_metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

client = boto3.client('sns', region_name='eu-central-1')

# new Sentinel scene SNS ARN
# arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product

# SNS Topic for publishing STAC Item
sns_arn = 'arn:aws:sns:eu-central-1:552188055668:sentinel-stac'


def lambda_handler(event, context):
    logger.info('Event: %s' % json.dumps(event))
    collection = Collection.open('https://sentinel-stac.s3.amazonaws.com/sentinel-2-l1c/catalog.json')
    
    msg = json.loads(event['Records'][0]['Sns']['Message'])
    logger.debug('Message: %s' % json.dumps(msg))

    for m in msg['tiles']:
        url = op.join(SETTINGS['roda_url'], m['path'], 'tileInfo.json')
        metadata = get_metadata(url)
        logger.debug('Metadata: %s' % json.dumps(metadata))
        # transform to STAC
        item = transform(metadata)
        logger.info('Item: %s' % json.dumps(item.data))
        collection.add_item(item, path=SETTINGS['path_pattern'], filename=SETTINGS['fname_pattern'])
        logger.info('Added %s as %s' % (item, item.filename))
        client.publish(TopicArn=sns_arn, Message=json.dumps(item.data))
        logger.info('Published to %s' % sns_arn)
