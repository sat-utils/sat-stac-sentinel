import os
import unittest

from datetime import datetime as dt

from satstac.sentinel.cli import parse_args

testpath = os.path.dirname(__file__)


class Test(unittest.TestCase):

    def test_parse_no_args(self):
        with self.assertRaises(SystemExit):
            parse_args([''])
        with self.assertRaises(SystemExit):
            parse_args(['-h'])