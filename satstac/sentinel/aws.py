import boto3
import boto3utils.s3 as s3
import json
import logging
import os.path as op
import requests

from datetime import datetime
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


#    'RODA_URL': 'https://roda.sentinel-hub.com/',
#    's3_url': 'https://%s.s3.amazonaws.com' % CID,
#    'path_pattern': '${year}/${month}/${day}/${sar:type}',
#    'fname_pattern': '${id}'

RODA_URL = 'https://roda.sentinel-hub.com/'


def latest_inventory(collection_id, **kwargs):
    # get latest AWS inventory for this collection
    inventory_url = 's3://sentinel-inventory/%s/%s-inventory' % (collection_id, collection_id)
    inventory = s3.latest_inventory(inventory_url, **kwargs)
    return inventory


def get_stac_items(transform, **kwargs):
    """ Stream records to a collection with a transform function 
    
    Keyword arguments:
    start_date -- Process this date and after
    end_date -- Process this date and earlier
    prefix -- Process only files who's key begins with this prefix
    """

    duration = []

    inventory = latest_inventory(transform.collection, **kwargs)

    # iterate through latest inventory
    for i, record in enumerate(inventory):
        start = datetime.now()
        if i % 50000 == 0:
            logger.info('%s: Scanned %s records' % (start, str(i)))

        # TODO - option of getting from s3 instead?  Didn't seem to be faster last I checked
        # plus it also costs $ due to requestor pays
        url = '%s/%s' % (RODA_URL, record['Key'])

        try:
            # get productInfo file
            metadata = read_remote_json(url)

            base_url = 'https://%s.s3.amazonaws.com/%s' % (record['Bucket'], record['Key'])
            item = transform.to_stac(metadata, base_url=base_url)

            yield item

        except Exception as err:
            logger.error('Error creating STAC Item %s: %s' % (record['path'], err))
            continue
        try:
            duration.append((datetime.now()-start).total_seconds())
            logger.info('Ingested %s in %s' % (item.filename, duration[-1]))
        except Exception as err:
            logger.error('Error adding %s: %s' % (item.id, err))
    logger.info('Read in %s records averaging %4.2f sec (%4.2f stddev)' % (i, np.mean(duration), np.std(duration)))


def read_remote_json(url):
    """ Retrieve remote JSON """
    # Read JSON file remotely
    r = requests.get(url, stream=True)
    metadata = json.loads(r.text)
    return metadata