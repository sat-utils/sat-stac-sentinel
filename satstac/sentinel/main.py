import boto3
import gzip
import json
import logging
import requests
import sys

import os.path as op

from datetime import datetime, timedelta
from dateutil.parser import parse
from pyproj import Proj, transform as reproj
from satstac import Collection, Item, utils
from .utils import get_matching_s3_keys, read_from_s3

from .version import __version__


logger = logging.getLogger(__name__)

_collection = Collection.open(op.join(op.dirname(__file__), 'sentinel-2-l1c.json'))

SETTINGS = {
    'roda_url': 'https://roda.sentinel-hub.com/sentinel-s2-l1c',
    'inv_bucket': 'sentinel-inventory',
    'inv_key': 'sentinel-s2-l1c/sentinel-s2-l1c-inventory',
    'path_pattern': 'tiles/${sentinel:utm_zone}/${sentinel:latitude_band}/${sentinel:grid_square}/' + \
                        '${year}/${month}/${day}/${sentinel:sequence}'
}


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
            collection.add_item(item, path=SETTINGS['path_pattern'], filename='item')
            logger.debug('Ingested %s in %s' % (item.id, datetime.now()-now))
        except Exception as err:
            logger.error('Error adding %s: %s' % (item.id, err))


def records():
    """ Return generator function for list of scenes """
    s3 = boto3.client('s3')
    # get latest file
    today = datetime.now()
    key = None
    for dt in [today, today - timedelta(1)]:
        prefix = op.join(SETTINGS['inv_key'], dt.strftime('%Y-%m-%d'))
        keys = [k for k in get_matching_s3_keys(SETTINGS['inv_bucket'], prefix=prefix, suffix='manifest.json')]
        if len(keys) == 1:
            key = keys[0]
            break
    if key:
        manifest = json.loads(read_from_s3(SETTINGS['inv_bucket'], key))
        for f in manifest.get('files', []):
            inv = read_from_s3(SETTINGS['inv_bucket'], f['key']).split('\n')
            inv = [i.replace('"', '').split(',') for i in inv if 'tileInfo.json' in i]
            for info in inv:
                yield {
                    'datetime': parse(info[3]),
                    'url': op.join(SETTINGS['roda_url'], info[1])
                }


def transform(data):
    """ Transform Sentinel metadata (from tileInfo.json) into a STAC item """
    utm_zone = data['utmZone']
    lat_band = data['latitudeBand']
    grid_square = data['gridSquare']
    dt = parse(data['timestamp'])
    epsg = data['tileOrigin']['crs']['properties']['name'].split(':')[-1]

    url = op.join('https://sentinel-s2-l1c.s3.amazonaws.com', data['path'])
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
    #if dt < datetime(2016,12,6):
    #    del assets['tki']

    props = {
        'collection': 'sentinel-2-l1c',
        'datetime': dt.isoformat(),
        'eo:platform': 'sentinel-2%s' % data['productName'][2].lower(),
        'eo:cloud_cover': int(float(data['cloudyPixelPercentage'])),
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

def read_remote(url):
    """ Return a line iterator for a remote file """
    r = requests.get(url, stream=True)
    for line in r.iter_lines():
        yield line.decode()