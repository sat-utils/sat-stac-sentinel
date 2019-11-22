import argparse
import logging
import sys

from datetime import datetime
from json import dumps
from os import makedirs, path as op
#from satstac import Catalog
from .sentinel import SentinelSTAC
from .version import __version__

# quiet loggers
logging.getLogger('urllib3').propagate = False
logging.getLogger('requests').propagate = False

logger = logging.getLogger(__name__)


def parse_args(args):
    desc = 'stac-sentinel (v%s)' % __version__
    dhf = argparse.ArgumentDefaultsHelpFormatter
    parser0 = argparse.ArgumentParser(description=desc)

    pparser = argparse.ArgumentParser(add_help=False)
    pparser.add_argument('--version', help='Print version and exit', action='version', version=__version__)
    pparser.add_argument('--log', default=2, type=int,
                         help='0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical')
    pparser.add_argument('-c', '--collection', help='Collection ID', default='sentinel-s2-l1c')
    pparser.add_argument('--prefix', help='Only ingest scenes with a path starting with prefix', default=None)
    pparser.add_argument('--start_date', help='Only ingest scenes with a Last Modified Date past provided start date', default=None)
    pparser.add_argument('--end_date', help='Only ingest scenes with a Last Modified Date before provided end date', default=None)


    # add subcommands
    subparsers = parser0.add_subparsers(dest='command')

    # command 1
    parser = subparsers.add_parser('ingest', parents=[pparser], help='Ingest Sentinel STAC', formatter_class=dhf)
    parser.add_argument('--save', help='Save fetch Items as <id>.json files to this folder', default=None)

    #parser.add_argument('--publish', help='ARN to publish new Items to', default=None)

    # command 2
    h = 'Get latest inventory of Sentinel metadata files'
    parser = subparsers.add_parser('inventory', parents=[pparser], help=h, formatter_class=dhf)
    parser.add_argument('--filename', help='Filename to save', default=str(datetime.now().date()) + '.csv')

    # turn Namespace into dictinary
    parsed_args = vars(parser0.parse_args(args))

    return parsed_args


def cli():
    args = parse_args(sys.argv[1:])
    logging.basicConfig(stream=sys.stdout, level=args.pop('log') * 10)
    cmd = args.pop('command')   

    if cmd == 'ingest':
        collection_id = args.pop('collection')
        savepath = args.pop('save')
        if savepath is not None:
            makedirs(savepath, exist_ok=True)
        for item in SentinelSTAC.get_aws_archive(collection_id, **args):
            if savepath:
                fname = op.join(savepath, '%s.json' % item['id'])
                with open(fname, 'w') as f:
                    f.write(dumps(item))
            import pdb; pdb.set_trace()

        #cat = Catalog.open(args['catalog'])
        #if args['filename'] is not None:
        #    records = sentinel.read_inventory(args['filename'])
        #else:
        #    records = sentinel.latest_inventory()
        #sentinel.add_items(cat, records, start_date=args['start'], end_date=args['end'],
        #                    prefix=args['prefix'], s3meta=args['s3meta'], publish=args['publish'])
    elif cmd == 'inventory':
        filename = args.pop('filename', None)
        inventory = latest_inventory(**args)
        if filename is not None:
            # save the inventory results
            with open(filename, 'w') as f:
                keys = None
                for inv in inventory:
                    if keys is None:
                        keys = inv.keys()
                        f.write(','.join(keys) + '\n')
                    f.write(','.join([str(inv[k]) for k in keys]) + '\n')


if __name__ == "__main__":
    cli()