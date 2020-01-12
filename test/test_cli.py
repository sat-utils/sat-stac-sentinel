import os
import unittest

from datetime import datetime as dt

from stac_sentinel.cli import parse_args

testpath = os.path.dirname(__file__)


class Test(unittest.TestCase):

    def test_parse_no_args(self):
        args = parse_args([''])
        assert(len(args)==7)

    def test_parse_args(self):
        args = parse_args('sentinel-s1-l1c'.split(' '))
        assert(args['collection'] == 'sentinel-s1-l1c')