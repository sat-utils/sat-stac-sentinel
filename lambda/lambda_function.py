import boto3
import json
import logging
import requests
import sys

import os.path as op

from datetime import datetime
from stac_sentinel import SentinelSTAC
from urllib.parse import urljoin

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

client = boto3.client('sns', region_name=SentinelSTAC.region)

# new Sentinel scene SNS ARN
# arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product

# SNS Topics for publishing STAC Item
collections = {
    'sentinel-s1-l1c': 'arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s1-l1c',
    'sentinel-s2-l1c': 'arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s2-l1c',
    'sentinel-s2-l2a': 'arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s2-l2a'
}


def lambda_handler(event, context):
    logger.debug('Event: %s' % json.dumps(event))
    
    metadata = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info('Message: %s' % json.dumps(metadata))

    # determine the collection
    collection = None
    if 'tiles' in metadata:
        # sentinel-2
        lvl = metadata['name'].split('_')[0][3:5]
        if lvl == 'L1':
            collection = 'sentinel-s2-l1c'
        elif lvl == 'L2':
            collection = 'sentinel-s2-l2a'
    elif 'missionId' in metadata:
        collection = 'sentinel-s1-l1a'
        
    if collection is None:
        msg = 'Message not recognized'
        logger.error(msg)
        return msg

    logger.info('Collection %s' % collection)

    items = []
    if 'sentinel-s1' in collection:
        scene = SentinelSTAC(collection, metadata)
        item = scene.to_stac(base_url='s3://%s/%s' % (collection, metadata['path']))
        items.append(item)
    else:
        # there should never be more than one tile
        for md in metadata['tiles']:
            # get tile info for each tile
            url = urljoin(SentinelSTAC.FREE_URL, md['path'], 'tileInfo.json')
            r = requests.get(url, stream=True)
            metadata = json.loads(r.text)
            logger.debug('Metadata: %s' % json.dumps(metadata))

            # transform to STAC
            scene = SentinelSTAC(collection, metadata)
            item = scene.to_stac(base_url='https://nosuchaddress')
            items.append(item)

    for item in items:
        logger.info('Item: %s' % json.dumps(item))
        # publish to SNS
        client.publish(TopicArn=collections[collection], Message=json.dumps(item))
        logger.info('Published %s to %s' % (item['id'], collections[collection]))