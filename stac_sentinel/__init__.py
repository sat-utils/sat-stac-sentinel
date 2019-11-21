import logging

from stac_sentinel.sentinel1l1c import Transform as TransformS1l1c
#from stac_sentinel.sentinel2 import Transform as TransformS2

# quiet loggers
logging.getLogger('botocore').propagate = False