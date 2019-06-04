import boto3
import json

import os.path as op

from datetime import datetime, timedelta
from gzip import GzipFile
from io import BytesIO

# code from https://alexwlchan.net/2018/01/listing-s3-keys-redux/

def get_matching_s3_objects(bucket, prefix='', suffix=''):
    """
    Generate objects in an S3 bucket.

    :param bucket: Name of the S3 bucket.
    :param prefix: Only fetch objects whose key starts with
        this prefix (optional).
    :param suffix: Only fetch objects whose keys end with
        this suffix (optional).
    """
    s3 = boto3.client('s3')
    kwargs = {'Bucket': bucket}

    # If the prefix is a single string (not a tuple of strings), we can
    # do the filtering directly in the S3 API.
    if isinstance(prefix, str):
        kwargs['Prefix'] = prefix

    while True:

        # The S3 API response is a large blob of metadata.
        # 'Contents' contains information about the listed objects.
        resp = s3.list_objects_v2(**kwargs)

        try:
            contents = resp['Contents']
        except KeyError:
            return

        for obj in contents:
            key = obj['Key']
            if key.startswith(prefix) and key.endswith(suffix):
                yield obj

        # The S3 API is paginated, returning up to 1000 keys at a time.
        # Pass the continuation token into the next response, until we
        # reach the final page (when this field is missing).
        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break


def get_matching_s3_keys(bucket, prefix='', suffix=''):
    """
    Generate the keys in an S3 bucket.

    :param bucket: Name of the S3 bucket.
    :param prefix: Only fetch keys that start with this prefix (optional).
    :param suffix: Only fetch keys that end with this suffix (optional).
    """
    for obj in get_matching_s3_objects(bucket, prefix, suffix):
        yield obj['Key']


def read_from_s3(bucket, key):
    """ Download object from S3 as JSON """
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response['Body'].read()
    if op.splitext(key)[1] == '.gz':
        body = GzipFile(None, 'rb', fileobj=BytesIO(body)).read()
    return body.decode('utf-8')


def latest_inventory(bucket, key, filename):
    """ Return generator function for specified filename in a Bucket inventory """
    s3 = boto3.client('s3')
    # get latest file
    today = datetime.now()
    _key = None
    for dt in [today, today - timedelta(1)]:
        prefix = op.join(key, dt.strftime('%Y-%m-%d'))
        keys = [k for k in get_matching_s3_keys(bucket, prefix=prefix, suffix='manifest.json')]
        if len(keys) == 1:
            _key = keys[0]
            break
    if _key:
        manifest = json.loads(read_from_s3(bucket, _key))
        for f in manifest.get('files', []):
            inv = read_from_s3(bucket, f['key']).split('\n')
            inv = [i.replace('"', '').split(',') for i in inv if filename in i]
            for info in inv:
                yield {
                    'datetime': parse(info[3]),
                    'path': info[1]
                }


def read_inventory_file(filename):
    """ Create generator from inventory file """
    with open(filename) as f:
        line = f.readline()
        if 'datetime' not in line:
            parts = line.split(',')
            yield {
                'datetime': parse(parts[0]),
                'path': parts[1].strip('\n')
            }
        for line in f.readlines():
            parts = line.split(',')
            yield {
                'datetime': parse(parts[0]),
                'path': parts[1].strip('\n')
            }