import logging

from stac_sentinel.sentinel import SentinelSTAC

# quiet loggers
logging.getLogger('botocore').propagate = False