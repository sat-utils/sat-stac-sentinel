import boto3
import json
import logging
import requests
import sys

import os.path as op

from datetime import datetime
from stac_sentinel import SentinelSTAC

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

client = boto3.client('sns', region_name=SentinelSTAC.region)

# new Sentinel scene SNS ARN
# arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product

# SNS Topics for publishing STAC Item
collections = {
    'sentinel-s2-l1c': 'arn:aws:sns:eu-central-1:552188055668:sentinel-stac'
}


def lambda_handler(event, context):
    logger.debug('Event: %s' % json.dumps(event))
    
    msg = json.loads(event['Records'][0]['Sns']['Message'])
    logger.debug('Message: %s' % json.dumps(msg))

    # sentinel-2
    '''
    for m in msg['tiles']:
        # get metadata file
        url = op.join(SentinelSTAC.FREE_URL, m['path'], 'tileInfo.json')
        r = requests.get(url, stream=True)
        metadata = json.loads(r.text)
        logger.debug('Metadata: %s' % json.dumps(metadata))

        # transform to STAC
        scene = SentinelSTAC('sentinel-s2-l1c', metadata)
        item = scene.to_stac()
        logger.info('Item: %s' % json.dumps(item.data))

        # publish to SNS
        client.publish(TopicArn=sns_arn, Message=json.dumps(item.data))
        logger.info('Published to %s' % sns_arn)
    '''