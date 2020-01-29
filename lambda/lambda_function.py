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

# NOTE: this lambda function requires GeoLambda layers
# - arn:aws:lambda:eu-central-1:552188055668:layer:geolambda:2
# - arn:aws:lambda:eu-central-1:552188055668:layer:geolambda-python:1


# NOTE: this lambda to be subscribed to the following SNS topics:
# - (S1-L1C) arn:aws:sns:eu-central-1:214830741341:SentinelS1L1C
# - (S2-L1C) arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product
# - (S2-L2A) arn:aws:sns:eu-central-1:214830741341:SentinelS2L2A

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
        lvl = metadata['name'].split('_')[1][3:5]
        if lvl == 'L1':
            collection = 'sentinel-s2-l1c'
        elif lvl == 'L2':
            collection = 'sentinel-s2-l2a'
    elif 'missionId' in metadata:
        collection = 'sentinel-s1-l1c'
        
    if collection is None:
        msg = 'Message not recognized'
        logger.error(msg)
        return msg

    logger.info('Collection %s' % collection)

    items = []
    if 'sentinel-s1' in collection:
        base_url = 's3://%s/%s' % (collection, metadata['path'])
        fnames = [f"{base_url}/{a}" for a in metadata['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
        md = {
            'id': metadata['id'],
            'coordinates': metadata['footprint']['coordinates'],
            'filenames': fnames
        }
        scene = SentinelSTAC(collection, md)
        item = scene.to_stac()
        items.append(item)
    else:
        # there should never be more than one tile
        for md in metadata['tiles']:
            # get tile info for each tile
            url = '%s/%s/%s/tileInfo.json' % (SentinelSTAC.FREE_URL, collection, md['path'])
            logger.info('metadata url = %s' % url)
            r = requests.get(url, stream=True)
            metadata = json.loads(r.text)
            logger.debug('Metadata: %s' % json.dumps(metadata))

            # transform to STAC
            scene = SentinelSTAC(collection, metadata)
            item = scene.to_stac(base_url='s3://%s/%s' % (collection, md['path']))
            items.append(item)

    for item in items:
        logger.info('Item: %s' % json.dumps(item))
        # publish to SNS
        client.publish(TopicArn=collections[collection], Message=json.dumps(item),
                       MessageAttributes=get_sns_attributes(item))
        logger.info('Published %s to %s' % (item['id'], collections[collection]))


def get_sns_attributes(item):
    """ Get Attributes from STAC item for publishing to SNS """
    return {
        'properties.datetime': {
            'DataType': 'String',
            'StringValue': item['properties']['datetime']
        },
        'bbox.ll_lon': {
            'DataType': 'Number',
            'StringValue': str(item['bbox'][0])
        },
        'bbox.ll_lat': {
            'DataType': 'Number',
            'StringValue': str(item['bbox'][1])
        },
        'bbox.ur_lon': {
            'DataType': 'Number',
            'StringValue': str(item['bbox'][2])
        },
        'bbox.ur_lat': {
            'DataType': 'Number',
            'StringValue': str(item['bbox'][3])
        }     
    }