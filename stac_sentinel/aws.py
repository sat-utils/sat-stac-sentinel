import boto3
import boto3utils.s3 as s3
import json
import logging
import os.path as op
import requests

from datetime import datetime
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


def get_stac_items(transform, **kwargs):
    """ Stream records to a collection with a transform function 
    
    Keyword arguments:
    prefix -- Process only files keys begining with this prefix
    suffix -- Process only files keys ending with this suffix
    start_date -- Process this date and after
    end_date -- Process this date and earlier
    datetime_key -- Field to use for start_date/end_date comparison (defaults to LastModifiedDate)

    Returns:
    Iterator of STAC Items using specified Transform object
    """
    RODA_URL = 'https://roda.sentinel-hub.com'

    # get latest AWS inventory for this collection
    inventory_url = 's3://sentinel-inventory/%s/%s-inventory' % (transform.collection, transform.collection)
    inventory = s3.latest_inventory(inventory_url, **kwargs, suffix='productInfo.json')

    # iterate through latest inventory
    for record in inventory:
        # TODO - option of getting from s3 instead?  Didn't seem to be faster last I checked
        # plus it also costs $ due to requestor pays
        url = '%s/%s/%s' % (RODA_URL, transform.collection, record['Key'])
        logger.debug('Fetching initial metadata: %s' % url)
        try:
            # get productInfo file
            r = requests.get(url, stream=True)
            metadata = json.loads(r.text)
            base_url = 's3://%s/%s' % (record['Bucket'], op.dirname(record['Key']))                        
            # transform to STAC Item
            item = transform.to_stac(metadata, base_url=base_url)
            yield item

        except Exception as err:
            logger.error('Error creating STAC Item %s: %s' % (record['url'], err))
            continue
