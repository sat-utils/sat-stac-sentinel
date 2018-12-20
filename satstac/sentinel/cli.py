import argparse
import logging
import sys

from datetime import datetime

import satstac
from satstac import Catalog
import satstac.sentinel as sentinel
from .version import __version__

# quiet loggers
logging.getLogger('urllib3').propagate = False
logging.getLogger('requests').propagate = False

logger = logging.getLogger(__name__)


def parse_args(args):
    desc = 'sat-stac-sentinel (v%s)' % __version__
    dhf = argparse.ArgumentDefaultsHelpFormatter
    parser0 = argparse.ArgumentParser(description=desc)

    pparser = argparse.ArgumentParser(add_help=False)
    pparser.add_argument('--version', help='Print version and exit', action='version', version=__version__)
    pparser.add_argument('--log', default=2, type=int,
                         help='0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical')

    # add subcommands
    subparsers = parser0.add_subparsers(dest='command')

    # command 1
    parser = subparsers.add_parser('ingest', parents=[pparser], help='Ingest records into catalog', formatter_class=dhf)
    parser.add_argument('catalog', help='Catalog that contains the Collection')
    valid_date = lambda d: datetime.strptime(d, '%Y-%m-%d').date()
    parser.add_argument('--start', help='Start date of ingestion', default=None, type=valid_date)
    parser.add_argument('--end', help='End date of ingestion', default=None, type=valid_date)

    # command 2
    #parser = subparsers.add_parser('cmd2', parents=[pparser], help='Command 2', formatter_class=dhf)
    # parser.add_argument()

    # turn Namespace into dictinary
    parsed_args = vars(parser0.parse_args(args))

    return parsed_args


def cli():
    args = parse_args(sys.argv[1:])
    logging.basicConfig(stream=sys.stdout, level=args.pop('log') * 10)
    cmd = args.pop('command')   

    if cmd == 'ingest':
        cat = Catalog.open(args['catalog'])
        sentinel.add_items(cat, start_date=args['start'], end_date=args['end'])


if __name__ == "__main__":
    cli()