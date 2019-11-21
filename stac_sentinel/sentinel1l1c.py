import boto3
import gzip
import json
import logging
import requests
import sys

import boto3utils.s3 as s3
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


class Transform(object):

    def __init__(self):
        self.collection = 'sentinel-s1-l1c'
        self.region = 'eu-central-1'

    def get_xml_metadata(self, filename):
        """ get XML metadata """
        try: 
            if filename[0:5] == 's3://':
                # if s3, try presigned URL
                url, headers = s3.get_presigned_url(filename, aws_region=self.region, requester_pays=True)
                resp = requests.get(url, headers=headers)
                # TODO - check response
                metadata = resp.text
            elif op.exists(filename):
                with open(filename) as f:
                    metadata = f.read()
            return bf.data(fromstring(metadata))
        except Exception as err:
            logger.error('Error reading %s' % filename)
            return None

    def to_stac(self, metadata, base_url='./'):
        """ Transform Sentinel-1 metadata (from annotation XML) into a STAC item """

        # get metadata filenames
        filenames = list(metadata['filenameMap'].values())
        meta_urls = ['%s/%s' % (base_url, a) for a in filenames if 'annotation' in a and 'calibration' not in a]

        extended_metadata = self.get_xml_metadata(meta_urls[0])

        adsHeader = extended_metadata['product']['adsHeader']
        imageInfo = extended_metadata['product']['imageAnnotation']['imageInformation']
        procInfo = extended_metadata['product']['imageAnnotation']['processingInformation']
        swathProcParams = procInfo['swathProcParamsList']['swathProcParams']
        if isinstance(swathProcParams, list):
            swathProcParams = swathProcParams[0]
        props = {
            'datetime': parse(adsHeader['startTime']['$']).isoformat(),
            'start_datetime': parse(adsHeader['startTime']['$']).isoformat(),
            'end_datetime': parse(adsHeader['stopTime']['$']).isoformat(),
            'platform': 'sentinel-1%s' % adsHeader['missionId']['$'][2].lower(),
            'sar:instrument_mode': adsHeader['mode']['$'],
            'sar:product_type': adsHeader['productType']['$'],
            'sar:looks_range': swathProcParams['rangeProcessing']['numberOfLooks']['$'],
            'sar:looks_azimuth': swathProcParams['azimuthProcessing']['numberOfLooks']['$'],
            'sat:orbit_state': extended_metadata['product']['generalAnnotation']['productInformation']['pass']['$'].lower(),
            'sat:incidence_angle': imageInfo['incidenceAngleMidSwath']['$'],
            'sat:relative_orbit': int(adsHeader['absoluteOrbitNumber']['$']/175.0)
        }

        # get Asset definition dictionary from Collection
        collection = Collection.open(op.join(op.dirname(__file__), '%s.json' % self.collection))
        assets = collection._data['assets']

        # populate Asset URLs
        assets['thumbnail']['href'] = base_url + '/preview/quick-look.png'
        assets['metadata']['href'] = base_url + '/productInfo.json'
        filenames = [a for a in metadata['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
        for f in filenames:
            pol = op.splitext(f)[0].split('-')[-1].upper()
            assets['%s' % pol]['href'] = base_url + '/' + f.replace('.xml', '.tiff')
            assets['%s-metadata' % pol] = base_url + '/' + f

        item = {
            'type': 'Feature',
            'stac_version': STAC_VERSION,
            'stac_extensions': ['dtr', 'sat', 'sar'],
            'id': metadata['id'],
            'collection': self.collection,
            'properties': props,
            'assets': assets,
            'links': [
                {
                    'rel': 'collection',
                    'type': 'application/json'
                    'href': 
                }
            ]
        }

        # add bbox and geometry
        item.update(self.coordinates_to_geometry(metadata['footprint']['coordinates'][0]))

        return item

    def coordinates_to_geometry(self, coordinates):
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

    def kml_to_geometry(self, filename):
        """ Convert KML to bbox and geometry """
        # open local
        with open(filename) as f:
            kml = bf.data(fromstring(f.read()))['kml']['Document']['Folder']['GroundOverlay']
            kml = kml['{http://www.google.com/kml/ext/2.2}LatLonQuad']['coordinates']['$']
        coordinates = [list(map(float, pair.split(','))) for pair in kml.split(' ')]
        coordinates.append(coordinates[0])
        return self.coordinates_to_geometry(coordinates)
