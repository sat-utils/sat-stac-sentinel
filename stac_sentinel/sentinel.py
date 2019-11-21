import json
import logging
import requests

import boto3utils.s3 as s3
import os.path as op

from dateutil.parser import parse
from xmljson import badgerfish as bf
from xml.etree.ElementTree import fromstring
from .version import __version__

logger = logging.getLogger(__name__)


class SentinelSTAC(object):

    region = 'eu-central-1'
    stac_version = '0.9.0'

    def __init__(self, collection, metadata):
        assert(collection in ['sentinel-s1-l1c', 'sentinel-s2-l1c'])
        self.collection = collection
        self.metadata = metadata

    def to_stac(self, **kwargs):
        """ Convert metadata to a STAC Item """
        if self.collection == 'sentinel-s1-l1c':
            item = self.process_s1l1c(**kwargs)
        elif self.collection == 'sentinel-s2-l1c':
            item = self.process_s2l1c(**kwargs)

    def get_asset_definition(self):
        """ Get Asset Definition from Collection """
        filename = op.join(op.dirname(__file__), '%s.json' % self.collection)
        collection = json.loads(open(filename).read())
        return collection['assets']

    def process_s1l1c(self, base_url='./'):
        """ Transform Sentinel-1 L1c metadata (from annotation XML) into a STAC item """

        # get metadata filenames
        filenames = list(self.metadata['filenameMap'].values())
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
        assets = self.get_asset_definition()

        # populate Asset URLs
        assets['thumbnail']['href'] = base_url + '/preview/quick-look.png'
        assets['metadata']['href'] = base_url + '/productInfo.json'
        filenames = [a for a in self.metadata['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
        for f in filenames:
            pol = op.splitext(f)[0].split('-')[-1].upper()
            assets['%s' % pol]['href'] = base_url + '/' + f.replace('.xml', '.tiff')
            assets['%s-metadata' % pol] = base_url + '/' + f

        item = {
            'type': 'Feature',
            'stac_version': self.stac_version,
            'stac_extensions': ['dtr', 'sat', 'sar'],
            'id': self.metadata['id'],
            'collection': self.collection,
            'properties': props,
            'assets': assets,
            'links': [self.get_collection_link()]
        }

        # add bbox and geometry
        item.update(self.coordinates_to_geometry(self.metadata['footprint']['coordinates'][0]))

        return item    

    def process_s2l1c(self):
        """ Create STAC Item from Sentinel-2 L1C metadata """
        return {}

    def get_collection_link(self):
        repo_url = 'https://raw.githubusercontent.com/sat-utils/sat-stac-sentinel'
        collection_url = repo_url + '/develop/stac_sentinel/%s.json' % self.collection
        return {
            'rel': 'collection',
            'type': 'application/json',
            'href': collection_url
        }


    @classmethod
    def get_xml_metadata(cls, filename):
        """ get XML metadata """
        try: 
            if filename[0:5] == 's3://':
                # if s3, try presigned URL
                url, headers = s3.get_presigned_url(filename, aws_region=cls.region, requester_pays=True)
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

    @classmethod
    def coordinates_to_geometry(cls, coordinates):
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

    @classmethod
    def kml_to_geometry(cls, filename):
        """ Convert KML to bbox and geometry """
        # open local
        with open(filename) as f:
            kml = bf.data(fromstring(f.read()))['kml']['Document']['Folder']['GroundOverlay']
            kml = kml['{http://www.google.com/kml/ext/2.2}LatLonQuad']['coordinates']['$']
        coordinates = [list(map(float, pair.split(','))) for pair in kml.split(' ')]
        coordinates.append(coordinates[0])
        return cls.coordinates_to_geometry(coordinates)

