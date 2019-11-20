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
from .version import __version__


logger = logging.getLogger(__name__)

# Sentinel-1-l1c collection as defined by this repository
#_collection = Collection.open(op.join(op.dirname(__file__), 'sentinel-1-l1c.json'))

STAC_VERSION = '0.9.0'


# settings used acoss package
SETTINGS = {
    'roda_url': 'https://roda.sentinel-hub.com/sentinel-s1-l1c',
    's3_url': 'https://sentinel-s1-l1c.s3.amazonaws.com',
    'path_pattern': '${year}/${month}/${day}/${sar:type}',
    'fname_pattern': '${id}'
}


def Transform(object):

    def __init__(self):
        self.collection = 'sentinel-1-l1c'

    def to_stac(self, metadata, base_url='./'):
        """ Transform Sentinel-1 metadata (from annotation XML) into a STAC item """

        # get metadata filenames
        filenames = metadata['filenameMap'].values()
        meta_urls = [urljoin(base_url, a) for a in filenames if 'annotation' in a and 'calibration' not in a]

        signed_url, headers = utils.get_s3_signed_url(meta_url, requestor_pays=True)
        resp = requests.get(signed_url, headers=headers)
        metadata = bf.data(fromstring(resp.text))

        import pdb; pdb.set_trace()


        adsHeader = metadata['product']['adsHeader']
        imageInfo = metadata['product']['imageAnnotation']['imageInformation']
        swathProcParams = metadata['product']['imageAnnotation']['processingInformation']['swathProcParamsList']['swathProcParams']
        if isinstance(swathProcParams, list):
            swathProcParams = swathProcParams[0]
        props = {
            'datetime': parse(adsHeader['startTime']['$']).isoformat(),
            'start_datetime': parse(adsHeader['startTime']['$']).isoformat(),
            'end_datetime': parse(adsHeader['stopTime']['$']).isoformat(),
            'platform': 'sentinel-1%s' % adsHeader['missionId']['$'][2].lower(),
            'sar:orbit_state': metadata['product']['generalAnnotation']['productInformation']['pass']['$'].lower(),
            'sar:instrument_mode': adsHeader['mode']['$'],
            'sar:product_type': adsHeader['productType']['$'],
            'sar:looks_range': swathProcParams['rangeProcessing']['numberOfLooks']['$'],
            'sar:looks_azimuth': swathProcParams['azimuthProcessing']['numberOfLooks']['$'],
            'sar:incidence_angle': imageInfo['incidenceAngleMidSwath']['$']
        }
        
        props['sat:relative_orbit'] = int(adsHeader['absoluteOrbitNumber']['$']/175.0)

        _item = {
            'type': 'Feature',
            'stac_version': STAC_VERSION,
            'stac_extensions': ['dtr', 'sat', 'sar'],
            'collection': 'sentinel-1',
            'properties': props,
            'assets': {}
        }

        item['id'] = productInfo['id']
        item.update(coordinates_to_geometry(productInfo['footprint']['coordinates'][0]))

        # add assets from productInfo
        item.data['assets'] = create_assets(productInfo)


        return Item(_item)


    def kml_to_geometry(filename):
        """ Convert KML to bbox and geometry """
        # open local
        with open(filename) as f:
            kml = bf.data(fromstring(f.read()))['kml']['Document']['Folder']['GroundOverlay']
            kml = kml['{http://www.google.com/kml/ext/2.2}LatLonQuad']['coordinates']['$']
        coordinates = [list(map(float, pair.split(','))) for pair in kml.split(' ')]
        coordinates.append(coordinates[0])
        return coordinates_to_geometry(coordinates)


    def coordinates_to_geometry(coordinates):
        """ Convert coordinates to GeoJSON Geometry and bbox """
        lats = [c[1] for c in coordinates]
        lons = [c[0] for c in coordinates]
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        return {
            'bbox': bbox,
            'geometry': {
                'type': 'Polygon',
                'coordinates': [coordinates]
            }
        }




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


