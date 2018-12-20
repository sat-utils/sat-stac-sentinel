import json
import unittest

from datetime import datetime as dt
import os.path as op

from satstac import Catalog, sentinel

testpath = op.dirname(__file__)


class Test(unittest.TestCase):
    """ Test main module """

    def read_test_metadata(self):
        with open(op.join(testpath, 'sentinel-2-l1c-tileInfo.json')) as f:
            dat = json.loads(f.read())
        return dat

    def test_main(self):
        """ Run main function """
        # create test catalog
        fname = op.join(testpath, 'test_main', 'catalog.json')
        cat = Catalog.create(id='test').save_as(fname)
        assert(op.exists(fname))
        #fout = sentinel.main(sentinel, start_date=dt(2013, 10, 1).date())

    def test_records(self):
        for r in sentinel.records():
            assert('datetime' in r)
            assert('url' in r)
            break

    def test_transform(self):
        md = self.read_test_metadata()
        item = sentinel.transform(md)
        assert(str(item.date) == '2017-10-23')
        assert(item.data['type'] == 'Feature')
        assert(len(item.data['assets']) == 17)
        assert(item['sentinel:sequence'] == "0")

    def test_get_metadata(self):
        """ Read Sentinel metadata """
        dat = self.read_test_metadata()
        url = 'https://roda.sentinel-hub.com/sentinel-s2-l1c/tiles/57/U/VB/2017/10/23/0/tileInfo.json'
        md = sentinel.get_metadata(url)
        assert(md == dat)