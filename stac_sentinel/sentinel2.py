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

from datetime import datetime, timedelta
from dateutil.parser import parse
from pyproj import Proj, transform as reproj
from satstac import Collection, Item, utils
from .utils import get_matching_s3_keys, read_from_s3

from .version import __version__


logger = logging.getLogger(__name__)

_collection = Collection.open(op.join(op.dirname(__file__), 'sentinel-2-l1c.json'))


class Transform(object):

    def __init__(self):
        self.collection = 'sentinel-s2-l1c'

SETTINGS = {
    'roda_url': 'https://roda.sentinel-hub.com/sentinel-s2-l1c',
    's3_url': 'https://sentinel-s2-l1c.s3.amazonaws.com',
    'inv_bucket': 'sentinel-inventory',
    'inv_key': 'sentinel-s2-l1c/sentinel-s2-l1c-inventory',
    'path_pattern': '${sentinel:utm_zone}/${sentinel:latitude_band}/${sentinel:grid_square}',
    'fname_pattern': '${date}/${id}'
}


def add_items(catalog, records, start_date=None, end_date=None, s3meta=False, prefix=None, publish=None):
    """ Stream records to a collection with a transform function 
    
    Keyword arguments:
    start_date -- Process this date and after
    end_date -- Process this date and earlier
    s3meta -- Retrieve metadata from s3 rather than Sinergise URL (roda)
    """
    
    # use existing collection or create new one if it doesn't exist
    cols = {c.id: c for c in catalog.collections()}
    if 'sentinel-2-l1c' not in cols.keys():
        catalog.add_catalog(_collection)
        cols = {c.id: c for c in catalog.collections()}
    collection = cols['sentinel-2-l1c']

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
            if s3meta:
                signed_url, headers = utils.get_s3_signed_url(url, requestor_pays=True)
                resp = requests.get(signed_url, headers=headers)
                metadata = json.loads(resp.text)
            else:
                metadata = read_remote(url)
            item = transform(metadata)
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


def transform(data):
    """ Transform Sentinel metadata (from tileInfo.json) into a STAC item """
    dt = parse(data['timestamp'])
    epsg = data['tileOrigin']['crs']['properties']['name'].split(':')[-1]

    url = op.join(SETTINGS['s3_url'], data['path'])
    roda_url = op.join(SETTINGS['roda_url'], data['path'])

    # geo
    coordinates = data['tileDataGeometry']['coordinates']
    ys = [c[1] for c in coordinates[0]]
    xs = [c[0] for c in coordinates[0]]
    p1 = Proj(init='epsg:%s' % epsg)
    p2 = Proj(init='epsg:4326')
    lons, lats = reproj(p1, p2, xs, ys)
    bbox = [min(lons), min(lats), max(lons), max(lats)]
    coordinates = [[[lons[i], lats[i]] for i in range(0, len(lons))]]

    geom = geometry.mapping(geometry.Polygon(coordinates[0]).convex_hull)

    assets = _collection.data['assets']
    assets = utils.dict_merge(assets, {
        'thumbnail': {'href': op.join(roda_url, 'preview.jpg')},
        'info': {'href': op.join(roda_url, 'tileInfo.json')},
        'metadata': {'href': op.join(roda_url, 'metadata.xml')},
        'tki': {'href': op.join(url, 'TKI.jp2')},
        'B01': {'href': op.join(url, 'B01.jp2')},
        'B02': {'href': op.join(url, 'B02.jp2')},
        'B03': {'href': op.join(url, 'B03.jp2')},
        'B04': {'href': op.join(url, 'B04.jp2')},
        'B05': {'href': op.join(url, 'B05.jp2')},
        'B06': {'href': op.join(url, 'B06.jp2')},
        'B07': {'href': op.join(url, 'B07.jp2')},
        'B08': {'href': op.join(url, 'B08.jp2')},
        'B8A': {'href': op.join(url, 'B8A.jp2')},
        'B09': {'href': op.join(url, 'B09.jp2')},
        'B10': {'href': op.join(url, 'B10.jp2')},
        'B11': {'href': op.join(url, 'B11.jp2')},
        'B12': {'href': op.join(url, 'B11.jp2')}
    })
    #if dt < datetime(2016,12,6):
    #    del assets['tki']

    props = {
        'collection': 'sentinel-2-l1c',
        'datetime': dt.isoformat(),
        'eo:platform': 'sentinel-2%s' % data['productName'][2].lower(),
        'eo:cloud_cover': float(data['cloudyPixelPercentage']),
        'sentinel:utm_zone': data['utmZone'],
        'sentinel:latitude_band': data['latitudeBand'],
        'sentinel:grid_square': data['gridSquare'],
        'sentinel:sequence': data['path'].split('/')[-1],
        'sentinel:product_id': data['productName']
    }
    sid = str(data['utmZone']) + data['latitudeBand'] + data['gridSquare']
    id = '%s_%s_%s_%s' % (data['productName'][0:3], sid, dt.strftime('%Y%m%d'), props['sentinel:sequence'] )

    _item = {
        'type': 'Feature',
        'id': id,
        'bbox': bbox,
        'geometry': geom,
        'properties':props,
        'assets': assets
    }
    return Item(_item)


def read_remote(url):
    """ Retrieve remote JSON """
    # Read JSON file remotely
    r = requests.get(url, stream=True)
    metadata = json.loads(r.text)
    return metadata
