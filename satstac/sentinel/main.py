import gzip
import json
import logging
import requests
import sys

import os.path as op

from datetime import datetime
from dateutil.parser import parse
from pyproj import Proj, transform as reproj
from satstac import Collection, Item, utils

from .version import __version__


logger = logging.getLogger(__name__)

_collection = Collection.open(op.join(op.dirname(__file__), 'sentinel-2-l1c.json'))


def add_items(catalog, start_date=None, end_date=None):
    """ Stream records to a collection with a transform function """
    
    # use existing collection or create new one if it doesn't exist
    cols = {c.id: c for c in catalog.collections()}
    if 'sentinel-2-l1c' not in cols.keys():
        catalog.add_catalog(_collection)
        cols = {c.id: c for c in catalog.collections()}
    collection = cols['sentinel-2-l1c']

    # iterate through records
    for i, record in enumerate(records()):
        now = datetime.now()
        dt = record['datetime'].date()
        if (i % 10000) == 0:
            logger.info('%s: %s records scanned' % (datetime.now(), i))
        if start_date is not None and dt < start_date:
            # skip to next if before start_date
            continue
        if end_date is not None and dt > end_date:
            # stop if after end_date
            continue
        try:
            url = record['url'].replace('sentinel-s2-l1c.s3.amazonaws.com', 'roda.sentinel-hub.com/sentinel-s2-l1c')
            metadata = get_metadata(record['url'])
            item = transform(metadata)
        except Exception as err:
            logger.error('Error getting %s: %s' % (record['url'], err))
            continue
        try:
            collection.add_item(item, path='${eo:column}/${eo:row}/${date}')
            logger.debug('Ingested %s in %s' % (item.id, datetime.now()-now))
        except Exception as err:
            logger.error('Error adding %s: %s' % (item.id, err))


def records():
    """ Return generator function for list of scenes """
    # TODO - iterate through records from Sentinel inventory
    yield {
        'id': 'id',
        'datetime': 'datetime',
        'url': 'url'
    }


def transform(data):
    """ Transform Sentinel metadata (from tileInfo.json) into a STAC item """
    utm_zone = data['utmZone']
    lat_band = data['latitudeBand']
    grid_square = data['gridSquare']
    dt = parse(data['timestamp'])
    epsg = data['tileOrigin']['crs']['properties']['name'].split(':')[-1]

    url = op.join('https://sentinel-s2-l1c.s3.amazonaws.com', data['path'])
    roda_url = op.join('https://roda.sentinel-hub.com/sentinel-s2-l1c', data['path'])

    # geo
    coordinates = data['tileDataGeometry']['coordinates']
    ys = [c[1] for c in coordinates[0]]
    xs = [c[0] for c in coordinates[0]]
    p1 = Proj(init='epsg:%s' % epsg)
    p2 = Proj(init='epsg:4326')
    lons, lats = reproj(p1, p2, xs, ys)
    bbox = [min(lons), min(lats), max(lons), max(lats)]
    coordinates = [[[lons[i], lats[i]] for i in range(0, len(lons))]]

    assets = _collection.data['assets']
    assets = utils.dict_merge(assets, {
        'thumbnail': {'href': op.join(roda_url, 'preview.jpg')},
        'metadata': {'href': op.join(roda_url, 'tileInfo.json')},
        'metadata-xml': {'href': op.join(roda_url, 'metadata.xml')},
        'tki': {'href': op.join(url, 'TKI.jp2')},
        'B01': {'href': op.join(url, 'B01.TIF')},
        'B02': {'href': op.join(url, 'B02.TIF')},
        'B03': {'href': op.join(url, 'B03.TIF')},
        'B04': {'href': op.join(url, 'B04.TIF')},
        'B05': {'href': op.join(url, 'B05.TIF')},
        'B06': {'href': op.join(url, 'B06.TIF')},
        'B07': {'href': op.join(url, 'B07.TIF')},
        'B08': {'href': op.join(url, 'B08.TIF')},
        'B8A': {'href': op.join(url, 'B08.TIF')},
        'B09': {'href': op.join(url, 'B09.TIF')},
        'B10': {'href': op.join(url, 'B10.TIF')},
        'B11': {'href': op.join(url, 'B11.TIF')},
        'B12': {'href': op.join(url, 'B11.TIF')}
    })

    props = {
        'collection': 'sentinel-2-l1c',
        'datetime': dt.isoformat(),
        'eo:platform': 'sentinel-2%s' % data['productName'][2].lower(),
        'eo:cloud_cover': int(float(data['cloudyPixelPercentage'])),
        'eo:row': data['latitudeBand'],
        'eo:column': data['gridSquare'],
        'sentinel:product_id': data['productName']
    }

    _item = {
        'type': 'Feature',
        'id': data['productName'],
        'bbox': bbox,
        'geometry': {
            'type': 'Polygon',
            'coordinates': coordinates
        },
        'properties':props,
        'assets': assets
    }
    return Item(_item)


def get_metadata(url):
    """ Convert Landsat MTL file to dictionary of metadata values """
    # Read MTL file remotely
    r = requests.get(url, stream=True)
    metadata = json.loads(r.text)
    return metadata
