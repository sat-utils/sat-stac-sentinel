import boto3
import gzip
import json
import logging
import requests
import sys

import numpy as np
import os.path as op

from shapely.geometry import MultiPoint, Point
from shapely import geometry

from datetime import datetime
from dateutil.parser import parse
from pyproj import Proj, transform as reproj
from satstac import Collection, Item, utils
from urllib.parse import urljoin
from xmljson import badgerfish as bf
from xml.etree.ElementTree import fromstring
from .utils import latest_inventory as inventory
from .version import __version__


logger = logging.getLogger(__name__)

# Sentinel-1-l1c collection as defined by this repository
_collection = Collection.open(op.join(op.dirname(__file__), 'sentinel-1-l1c.json'))
bandmap = {b['name']: i for i, b in enumerate(_collection['sar:bands'])}


# settings used acoss package
SETTINGS = {
    'roda_url': 'https://roda.sentinel-hub.com/sentinel-s1-l1c',
    's3_url': 'https://sentinel-s1-l1c.s3.amazonaws.com',
    'path_pattern': '${year}/${month}/${day}/${sar:type}',
    'fname_pattern': '${id}'
}


def latest_inventory():
    """ Get latest inventory of Sentinel-1 bucket """
    return inventory('sentinel-inventory', 'sentinel-s1-l1c/sentinel-s1-l1c-inventory', 'productInfo.json')


def add_items(catalog, records, start_date=None, end_date=None, s3meta=False, prefix=None, publish=None):
    """ Stream records to a collection with a transform function 
    
    Keyword arguments:
    start_date -- Process this date and after
    end_date -- Process this date and earlier
    s3meta -- Retrieve metadata from s3 rather than Sinergise URL (roda)
    """
    
    # use existing collection or create new one if it doesn't exist
    cols = {c.id: c for c in catalog.collections()}
    if 'sentinel-1-l1c' not in cols.keys():
        catalog.add_catalog(_collection)
        cols = {c.id: c for c in catalog.collections()}
    collection = cols['sentinel-1-l1c']

    client = None
    if publish:
        parts = publish.split(':')
        client = boto3.client('sns', region_name=parts[3])

    duration = []
    # iterate through records
    for i, record in enumerate(records):
        start = datetime.now()
        if i % 50000 == 0:
            logger.info('%s: Scanned %s records' % (start, str(i)))
        dt = record['datetime'].date()
        if prefix is not None:
            # if path doesn't match provided prefix skip to next record
            if record['path'][:len(prefix)] != prefix:
                continue
        if s3meta:
            url = op.join(SETTINGS['s3_url'], record['path'])
        else:
            url = op.join(SETTINGS['roda_url'], record['path'])
        #if i == 10:
        #    break
        if (start_date is not None and dt < start_date) or (end_date is not None and dt > end_date):
            # skip to next if before start_date
            continue
        try:
            productInfo = read_remote(url)
            md_assets = [a for a in productInfo['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
            meta_url = urljoin(SETTINGS['s3_url'], record['path'].replace('productInfo.json', md_assets[0]))
            signed_url, headers = utils.get_s3_signed_url(meta_url, requestor_pays=True)
            resp = requests.get(signed_url, headers=headers)
            metadata = bf.data(fromstring(resp.text))
            item = transform(productInfo['id'], productInfo['footprint']['coordinates'], metadata)
            item.data['assets'] = create_assets(productInfo)
        except Exception as err:
            logger.error('Error creating STAC Item %s: %s' % (record['path'], err))
            continue
        try:
            collection.add_item(item, path=SETTINGS['path_pattern'], filename=SETTINGS['fname_pattern'])
            if client:
                client.publish(TopicArn=publish, Message=json.dumps(item.data))
            duration.append((datetime.now()-start).total_seconds())
            logger.info('Ingested %s in %s' % (item.filename, duration[-1]))
        except Exception as err:
            logger.error('Error adding %s: %s' % (item.id, err))
    logger.info('Read in %s records averaging %4.2f sec (%4.2f stddev)' % (i, np.mean(duration), np.std(duration)))


def transform(id, coordinates, metadata):
    """ Transform Sentinel metadata (from tileInfo.json) into a STAC item """

    # geo
    lats = [c[1] for c in coordinates[0]]
    lons = [c[0] for c in coordinates[0]]
    bbox = [min(lons), min(lats), max(lons), max(lats)]

    adsHeader = metadata['product']['adsHeader']
    imageInfo = metadata['product']['imageAnnotation']['imageInformation']
    swathProcParams = metadata['product']['imageAnnotation']['processingInformation']['swathProcParamsList']['swathProcParams']
    if isinstance(swathProcParams, list):
        swathProcParams = swathProcParams[0]
    props = {
        'datetime': parse(adsHeader['startTime']['$']).isoformat(),
        'dtr:start_datetime': parse(adsHeader['startTime']['$']).isoformat(),
        'dtr:end_datetime': parse(adsHeader['stopTime']['$']).isoformat(),
        'sar:platform': 'sentinel-1%s' % adsHeader['missionId']['$'][2].lower(),
        'sar:instrument_mode': adsHeader['mode']['$'],
        'sar:type': adsHeader['productType']['$'],
        'sar:absolute_orbit': adsHeader['absoluteOrbitNumber']['$'],
        'sar:pass_direction': metadata['product']['generalAnnotation']['productInformation']['pass']['$'].lower(),
        'sar:looks_range': swathProcParams['rangeProcessing']['numberOfLooks']['$'],
        'sar:looks_azimuth': swathProcParams['azimuthProcessing']['numberOfLooks']['$'],
        'sar:incidence_angle': imageInfo['incidenceAngleMidSwath']['$']
    }
    
    props['sar:relative_orbit'] = int(props['sar:absolute_orbit']/175.0)

    _item = {
        'type': 'Feature',
        'id': id,
        'collection': 'sentinel-1-l1c',
        'bbox': bbox,
        'geometry': {
            'type': 'Polygon',
            'coordinates': coordinates
        },
        'properties': props,
        'assets': {}
    }
    return Item(_item)


def create_assets(productInfo):
    """ Create asset metadata from productInfo """
    s3_url = urljoin(SETTINGS['s3_url'], productInfo['path'])
    roda_url = urljoin(SETTINGS['roda_url'], productInfo['path'])

    # add assets
    assets = _collection.data['assets']
    assets = utils.dict_merge(assets, {
        'thumbnail': {'href': urljoin(s3_url, 'preview/quick-look.png')},
        'info': {'href': urljoin(roda_url, 'productInfo.json')}
    })

    # get asset filenames
    filenames = [a for a in productInfo['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
    for f in filenames:
        pol = op.splitext(f)[0].split('-')[-1].upper()
        assets['%s' % pol] = {
            'title': 'Data',
            'type': 'image/vnd.stac.geotiff',
            'href': urljoin(s3_url + '/', f.replace('.xml', '.tiff')),
            'sar:bands': [bandmap[pol]]
        }
        assets['%s-metadata' % pol] = {
            'title': 'Metadata',
            'type': 'application/xml',
            'href': urljoin(s3_url + '/', f)
        }
    return assets


def read_remote(url):
    """ Retrieve remote JSON """
    # Read JSON file remotely
    r = requests.get(url, stream=True)
    metadata = json.loads(r.text)
    return metadata
