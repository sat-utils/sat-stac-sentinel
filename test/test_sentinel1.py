import json
import unittest

from datetime import datetime as dt
import os.path as op

from stac_sentinel import SentinelSTAC

testpath = op.dirname(__file__)


class Test(unittest.TestCase):
    """ Test main module """

    def read_test_metadata(self):
        with open(op.join(testpath, 'samples/sentinel-s2-l1c-tileInfo.json')) as f:
            dat = json.loads(f.read())
        return dat

    def test_init_class(self):
        scene = SentinelSTAC('sentinel-s2-l1c', self.read_test_metadata())
        assert(scene.stac_version == '0.9.0')
        assert(scene.metadata['gridSquare'] == 'VB')

    def _test_get_aws_archive(self):
        for item in SentinelSTAC.get_aws_archive('sentinel-s2-l2a'):
            assert('properties' in item)
            assert('stac_version' in item)
            break

    def test_transform(self):
        item = SentinelSTAC('sentinel-s2-l1c', self.read_test_metadata()).to_stac()
        assert(item['stac_version'] == '0.9.0')
        assert(item['type'] == 'Feature')
        assert(len(item['assets']) == 17)
        assert(item['properties']['sentinel:sequence'] == "0")
