import logging

from stac_sentinel.sentinel1 import Transform as TransformS1
#from stac_sentinel.sentinel2 import Transform as TransformS2

# quiet loggers
logging.getLogger('botocore').propagate = False