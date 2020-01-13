import argparse
import boto3
import logging
import sys

from datetime import datetime
from dateutil.parser import parse as dateparse
from json import dumps
from os import makedirs, path as op
from .sentinel import SentinelSTAC
from .version import __version__

logger = logging.getLogger(__name__)


def parse_args(args):
    desc = 'stac-sentinel (v%s)' % __version__
    dhf = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(description=desc, formatter_class=dhf)

    parser.add_argument('--version', help='Print version and exit', action='version', version=__version__)
    parser.add_argument('--log', default=2, type=int,
                         help='0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical')
    
    # collection (required)
    parser.add_argument('collection', help='Collection ID')

    # filtering
    parser.add_argument('--prefix', help='Only ingest scenes with a path starting with prefix', default=None)
    parser.add_argument('--start_date', help='Only ingest scenes with a Last Modified Date past provided start date', default=None)
    parser.add_argument('--end_date', help='Only ingest scenes with a Last Modified Date before provided end date', default=None)

    # output control
    parser.add_argument('--save', help='Save fetch Items as <id>.json files to this folder', default=None)
    parser.add_argument('--publish', help='SNS to publish new Items to', default=None)

    # turn Namespace into dictinary
    parsed_args = vars(parser.parse_args(args))

    # convert date fields to dates
    for d in ['start_date', 'end_date']:
        if parsed_args[d]:
            parsed_args[d] = dateparse(parsed_args[d]).date()
    return parsed_args


def cli():
    args = parse_args(sys.argv[1:])
    logging.basicConfig(stream=sys.stdout, level=args.pop('log') * 10) 

    publish = args.pop('publish', None)

    collection_id = args.pop('collection')
    savepath = args.pop('save')
    if savepath is not None:
        makedirs(savepath, exist_ok=True)
    for i, item in enumerate(SentinelSTAC.get_aws_archive(collection_id, **args)):
        print(item['properties']['datetime'], item['id'])
        # save items as JSON files
        if savepath:
            fname = op.join(savepath, '%s.json' % item['id'])
            with open(fname, 'w') as f:
                f.write(dumps(item))
        # publish to SNS
        if publish:
            client = boto3.client('sns', region_name=publish.split(':')[3])
            client.publish(TopicArn=publish, Message=dumps(item))
        if i > 5:
            break


if __name__ == "__main__":
    cli()