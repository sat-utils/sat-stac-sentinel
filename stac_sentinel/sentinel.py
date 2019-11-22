import json
import logging
import requests

import boto3utils.s3 as s3
import os.path as op

from dateutil.parser import parse
from pyproj import Proj, transform as reproj
from shapely import geometry
from xmljson import badgerfish as bf
from xml.etree.ElementTree import fromstring
from .version import __version__

logger = logging.getLogger(__name__)


class SentinelSTAC(object):

    region = 'eu-central-1'
    stac_version = '0.9.0'
    collections = {
        'sentinel-s1-l1c': 'productInfo.json',
        'sentinel-s2-l1c': 'tileInfo.json',
        'sentinel-s2-l2a': 'tileInfo.json'
    }
    FREE_URL = 'https://roda.sentinel-hub.com'

    def __init__(self, collection, metadata):
        assert(collection in self.collections.keys())
        self.collection = collection
        self.metadata = metadata

    def to_stac(self, **kwargs):
        """ Convert metadata to a STAC Item """
        if self.collection == 'sentinel-s1-l1c':
            item = self.to_stac_from_s1l1c(**kwargs)
        elif 'sentinel-s2' in self.collection:
            item = self.to_stac_from_s2(**kwargs)
        return item

    def get_collection(self):
        """ Get STAC Collection JSON """
        filename = op.join(op.dirname(__file__), '%s.json' % self.collection)
        collection = json.loads(open(filename).read())
        return collection        

    def get_collection_link(self):
        """ Return a STAC link to STAC Collection JSON from GitHub repo """
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

    @classmethod
    def get_aws_archive(cls, collection, **kwargs):
        """ Generator function returning the archive of Sentinel data on AWS
        Keyword arguments:
        prefix -- Process only files keys begining with this prefix
        start_date -- Process this date and after
        end_date -- Process this date and earlier

        Returns:
        Iterator of STAC Items using specified Transform object
        """
        

        # get latest AWS inventory for this collection
        inventory_url = 's3://sentinel-inventory/%s/%s-inventory' % (collection, collection)
        inventory = s3.latest_inventory(inventory_url, **kwargs, suffix=cls.collections[collection])

        # iterate through latest inventory
        for record in inventory:
            url = '%s/%s/%s' % (self.FREE_URL, collection, record['Key'])
            logger.debug('Fetching initial metadata: %s' % url)
            try:
                # get initial JSON file file
                r = requests.get(url, stream=True)
                metadata = json.loads(r.text)
                base_url = 's3://%s/%s' % (record['Bucket'], op.dirname(record['Key']))                        
                # transform to STAC Item
                sentinel_scene = cls(collection, metadata)
                item = sentinel_scene.to_stac(base_url=base_url)
                yield item

            except Exception as err:
                logger.error('Error creating STAC Item %s: %s' % (record['url'], err))
                continue

    def to_stac_from_s1l1c(self, base_url='./'):
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
        assets = self.get_collection()['assets']

        # populate Asset URLs
        assets['thumbnail']['href'] = base_url + '/preview/quick-look.png'
        assets['metadata']['href'] = base_url + '/productInfo.json'
        filenames = [a for a in self.metadata['filenameMap'].values() if 'annotation' in a and 'calibration' not in a]
        for f in filenames:
            pol = op.splitext(f)[0].split('-')[-1].upper()
            fname = f.replace('annotation', 'measurement').replace('.xml', '.tiff')
            assets['%s' % pol]['href'] = base_url + '/' + fname
            assets['%s-metadata' % pol]['href'] = base_url + '/' + f

        assets = {k: assets[k] for k in assets if 'href' in assets[k]}

        item = {
            'type': 'Feature',
            'stac_version': self.stac_version,
            'stac_extensions': ['dtr', 'sat', 'sar'],
            'id': '_'.join(self.metadata['id'].split('_')[0:-1]),
            'collection': self.collection,
            'properties': props,
            'assets': assets,
            'links': [self.get_collection_link()]
        }

        # add bbox and geometry
        item.update(self.coordinates_to_geometry(self.metadata['footprint']['coordinates'][0]))

        return item

    def to_stac_from_s2(self, base_url=''):
        """ Create STAC Item from Sentinel-2 L1C or L2A metadata """
        dt = parse(self.metadata['timestamp'])
        # Item properties
        props = {
            'datetime': dt.isoformat(),
            'platform': 'sentinel-2%s' % self.metadata['productName'][2].lower(),
            'eo:cloud_cover': float(self.metadata['cloudyPixelPercentage']),
            'sentinel:utm_zone': self.metadata['utmZone'],
            'sentinel:latitude_band': self.metadata['latitudeBand'],
            'sentinel:grid_square': self.metadata['gridSquare'],
            'sentinel:sequence': self.metadata['path'].split('/')[-1],
            'sentinel:product_id': self.metadata['productName']
        }

        # geometry - TODO see about getting this from a productInfo file without having to reproject
        epsg = self.metadata['tileOrigin']['crs']['properties']['name'].split(':')[-1]
        coordinates = self.metadata['tileDataGeometry']['coordinates']
        ys = [c[1] for c in coordinates[0]]
        xs = [c[0] for c in coordinates[0]]
        p1 = Proj(init='epsg:%s' % epsg)
        p2 = Proj(init='epsg:4326')
        lons, lats = reproj(p1, p2, xs, ys)
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        coordinates = [[[lons[i], lats[i]] for i in range(0, len(lons))]]
        geom = geometry.mapping(geometry.Polygon(coordinates[0]).convex_hull)

        # assets
        assets = self.get_collection()['assets']
        assets['thumbnail']['href'] = op.join(base_url, 'preview.jpg')
        assets['info']['href'] = op.join(base_url, 'tileInfo.json')
        assets['metadata']['href'] = op.join(base_url, 'metadata.xml')
        assets['overview']['href'] = op.join(base_url, 'TKI.jp2')
        assets['B01']['href'] = op.join(base_url, 'B01.jp2')
        assets['B02']['href'] = op.join(base_url, 'B02.jp2')
        assets['B03']['href'] = op.join(base_url, 'B03.jp2')
        assets['B04']['href'] = op.join(base_url, 'B04.jp2')
        assets['B05']['href'] = op.join(base_url, 'B05.jp2')
        assets['B06']['href'] = op.join(base_url, 'B06.jp2')
        assets['B07']['href'] = op.join(base_url, 'B07.jp2')
        assets['B08']['href'] = op.join(base_url, 'B08.jp2')
        assets['B8A']['href'] = op.join(base_url, 'B8A.jp2')
        assets['B09']['href'] = op.join(base_url, 'B09.jp2')
        assets['B10']['href'] = op.join(base_url, 'B10.jp2')
        assets['B11']['href'] = op.join(base_url, 'B11.jp2')
        assets['B12']['href'] = op.join(base_url, 'B11.jp2')
        #if dt < datetime(2016,12,6):
        #    del assets['tki']

        sid = str(self.metadata['utmZone']) + self.metadata['latitudeBand'] + self.metadata['gridSquare']
        level = self.metadata['datastrip']['id'].split('_')[3]
        id = '%s_%s_%s_%s_%s' % (self.metadata['productName'][0:3], sid,
                                 dt.strftime('%Y%m%d'), props['sentinel:sequence'], level)

        item = {
            'type': 'Feature',
            'id': id,
            'bbox': bbox,
            'geometry': geom,
            'properties':props,
            'assets': assets,
            'links': [self.get_collection_link()]
        }
        return item          