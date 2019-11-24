# stac-sentinel

This repository is used for the creating [STAC Items](https://github.com/radiantearth/stac-spec) for [Sentinel remote sensing data](https://sentinel.esa.int) from their original metadata. Currently [Sentinel-1](https://sentinel.esa.int/web/sentinel/missions/sentinel-1) and [Sentinel-2](https://sentinel.esa.int/web/sentinel/missions/sentinel-2) data is supported.

The library includes:

- STAC Collection metadata for [Sentinel-1 L1C](stac_sentinel/sentinel-s1-l1c.json), [Sentinel-2 L1C](stac_sentinel/sentinel-s2-l1c.json), and [Sentinel-2 L2A](stac_sentinel/sentinel-s2-l2a.json)
- Function for transforming the original metadata of a scene (productInfo.json for Sentinel-1, tileInfo.json for Sentinel-2) into a STAC Item
- A Python generator function to loop through the entire archive of [Sentinel-1 on AWS](https://registry.opendata.aws/sentinel-1/) and [Sentinel-2 on AWS](https://registry.opendata.aws/sentinel-2/) for any of the Collections
- A Command Line Interface (CLI) for fetching STAC Item metadata for the archives on AWS
- A Lambda function that listens for new scenes on AWS and publishes the complete STAC Item to an SNS topic


## SNS Topics

There is a publicly deployed version of the stac-sentinel Lambda function along with a publicly available SNS topic. Anyone can subscribe to the SNS topic from resources in their AWS account (use the ARNs provided below) in order to get metadata for the latest Sentinel scenes. The SNS message is JSON that contains the STAC Item at:

```
stac_item = message['Records'][0]['Sns']['Message']
```

The published message also uses [SNS Message attributes](https://docs.aws.amazon.com/sns/latest/dg/sns-message-attributes.html) that can be used to filter SNS messages using [SNS Message Filter](https://docs.aws.amazon.com/sns/latest/dg/sns-message-filtering.html). The published STAC SNS messages can be filtered using these attributes:

- `properties.datetime`
- `bbox.ll_lon`
- `bbox.ur_lon`
- `bbox.ll_lat`
- `bbox.ur_lat`

For example, an SNS filter policy that only notifies the subscriber when an Item is over Rio de Janeiro (22.9068° S, 43.1729° W) looks like this keeping-a-spatiotemporal-asset-catalog-stac-up-to-date-with-sns-sqs/)):

```json
{
	"bbox.ll_lon": [{"numeric":["<=",-43.1729]}],
	"bbox.ur_lon": [{"numeric":[">=",-43.1729]}],
	"bbox.ll_lat": [{"numeric":["<=",-22.9068]}],
	"bbox.ur_lat": [{"numeric":[">=",-22.9068]}]
}
```

Thanks to Frederico Liporace for his article [Keeping a SpatioTemporal Asset Catalog (STAC) Up To Date with SNS/SQS](https://aws.amazon.com/blogs/publicsector/).


### SNS ARNs

#### Sentinel-1 L1C

| STAC Version | SNS ARN  |
| -------- | ----  |
| 0.9.0    | arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s1-l1c |

#### Sentinel-2 L1C

| STAC Version | SNS ARN  |
| -------- | ----  |
| 0.6.0    | arn:aws:sns:eu-central-1:552188055668:sentinel-stac |
| 0.9.0    | arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s2-l1c |

#### Sentinel-2 L2A

| STAC Version | SNS ARN  |
| -------- | ----  |
| 0.9.0    | arn:aws:sns:eu-central-1:608149789419:stac-0-9-0_sentinel-s2-l2a |


## Public Catalogs

An earlier version of the repository was used to create the [Sentinel-2 STAC 0.6.0 catalog](https://sentinel-stac.s3.amazonaws.com/catalog.json), which is indexed in [Earth-Search](https://earth-search.aws.element84.com/stac) and [Development Seed's sat-api](https://sat-api.developmentseed.org/stac).

This section will be updated with newer catalogs as they become available.


## Installation

If you are interested in using the library to create STAC Items from the historical archive rather than an existing catalog or new scene notifications, you will need to install this library from GitHub.

Because stac-sentinel uses PyProj, the [PROJ system libraries](https://proj.org/) will be needed as well and needs to be installed as per your system. You could also consider using the [GeoLambda](https://github.com/developmentseed/geolambda) base Docker image, which includes PROJ.

Then, to install the latest released version (from the `master` branch).

```
$ pip install git+https://github.com/sat-utils/sat-stac-sentinel
```

To install a specific versions of stac-sentinel, install the matching version of stac-sentinel. 

```bash
pip install git+https://github.com/sat-utils/sat-stac-sentinel@0.2.0
```

The table below shows the corresponding versions between stac-sentinel and STAC:

| stac-sentinel | STAC  |
| -------- | ----  |
| 0.1.0    | 0.6.0 |
| 0.2.0    | 0.9.0 |


## Usage

### Accessing Sentinel archive on AWS

The most common way of using this library will be to access the historical archive and generate STAC records from it in order to add to a catalog, index, or use for processing.

While the AWS Sentinel buckets are all `requester-pays` (meaning the requester pays egress costs), there are public buckets containing the [S3 inventories](https://docs.aws.amazon.com/AmazonS3/latest/dev/storage-inventory.html), which is what stac-sentinel uses. This is a quick and efficient way to get a listing of the contents of a bucket.

```
from stac_sentinel import SentinelSTAC

for item in SentinelSTAC.get_aws_archive('sentinel-s2-l1c'):
    print(item['id'])
```

The `get_aws_archive` function finds the latest inventory (within 1 day) for the proper Sentinel collection, it then reads the files looking for the correct metadata file it needs (productInfo.json or tileInfo.json). For each found metadata file it creates the STAC Item and returns it. The `get_aws_archive` function is a Python generator, meaning that it is not processing all of the files before it returns. It will return the first STAC Item, then processes the next one on the subsequent loop.

There are a few keyword arguments supported to the `get_aws_archive` that allow some basic filtering.

- `prefix`: Only S3 keys that start with `prefix` are transformed, otherwise the file is skipped. For instance this provides a way to fetch only `GRD` Sentinel-1 data (prefix='GRD'), or to get only a specific grid for Sentinel-2 (prefix='tiles/17/T/KE')
- `start_date` and `end_date` - Only scenes with a LastModifiedDate on or after `start_date` and/or on or before `end_date` are transformed. Note this is not the date of the scene, but the datetime when the scene was last modified on S3.

### Command Line Interface

A command line tool is available for accessing the AWS archive in the same manner as using `get_aws_archive`.

```bash
$ stac-sentinel -h

stac-sentinel (v0.2.0b1)

positional arguments:
  collection            Collection ID

optional arguments:
  -h, --help            show this help message and exit
  --version             Print version and exit
  --log LOG             0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical
                        (default: 2)
  --prefix PREFIX       Only ingest scenes with a path starting with prefix
                        (default: None)
  --start_date START_DATE
                        Only ingest scenes with a Last Modified Date past
                        provided start date (default: None)
  --end_date END_DATE   Only ingest scenes with a Last Modified Date before
                        provided end date (default: None)
  --save SAVE           Save fetch Items as <id>.json files to this folder
                        (default: None)
```

The difference between using the CLI and using the library function is that the CLI provides a few options for what to do with the STAC Item once it is returned.

- `save`: Use the `--save` keyword to provide a folder where the STAC Item JSON files will be saved. All will be saved as one file and they will not be linked together like a normal catalog.
- `publish`: Use `--publish` to publish each STAC Item to an SNS topic to which you have write permissions.

These two options are not yet implemented, but are in the roadmap:
- `catalog`: Specify a catalog to add the Collection metadata and all STAC Items to an existing static catalog.
- `add_to_es`: Provide an Elasticsearch endpoint to add the STAC Items to an Elasticsearch instance

### Transforming individual scenes

Transforming a single scene is not useful for most users, but is included here for clarity. It may also be useful to look at the [SentinelSTAC.get_aws_archive() function](stac_sentinel/sentinel.py#101)

The class `SentinelSTAC` allows one to transform the original metadata provided in productInfo.json (Sentinel-1) or tileInfo.json (Sentinel-2) into a STAC Item.

```
# transform a Sentinel-1 L1C scene

import json
from stac_sentinel import SentinelSTAC

metadata = json.loads(open('productInfo.json').read())

# create an instance of SentinelSTAC for this scene
scene = SentinelSTAC('sentinel-s1-l1c', metadata)

# get the STAC Item
item = scene.to_stac(base_url='')
```

The `base_url` is the location, either local or remote, where the data for this scene can be found. In the case above, the data is staged locally, so the base_url is given as just the current directory, where it will look for the asset data files expected (as provided in the original metadata).  

If the data is remote, then reading it for a scene would look different:

```
# transform a Sentinel-2 L1C scene

import requests
import json
from stac_sentinel import SentinelSTAC

# get tileInfo
url = 'https://roda.sentinel-hub.com/sentinel-s2-l1c/tiles/17/T/KE/2015/10/23/0/tileInfo.json'
r = requests.get(url, stream=True)
metadata = json.loads(r.text)

# create an instance of SentinelSTAC for this scene
scene = SentinelSTAC('sentinel-s2-l1c', metadata)

# get the STAC Item
base_url = 's3://sentinel-s2-l1c/tiles/17/T/KE/2015/10/23/0'
item = scene.to_stac(base_url=base_url)
```

Note however that in this example, the base_url of s3://sentinel-s2-l1c, is a requester-pays bucket. It will be used to generate the links to the assets as seen in the [Sentinel-2 L1C example](samples/sentinel-s2-l1c_item.json), but none of these files are accessed directly.

However, for Sentinel-1, there is an additional metadata file that is needed that is only available in the bucket. **If you have credentials defined when running this code, it will automatically use requester-pays and you will be charged!** 


## Notes on STAC transofmration

### Sentinel-1

The data that is ingested by the sat-stac-sentinel CLI starts with bucket inventory files that are retrieved and used to find all of the `productInfo.json` files (this is the metadata for one Sentinel scene). This does not contain all of the data needed to create a STAC item however. For each Sentinel-1 asset in the scene there is an XML annotation file (in the annotation/ subdirectory). Most of the data in the annotation file is the same across all annotation files within the scene, so only a single one is needed (there is asset specific data including statistics and noise estimates that are not needed). This annotation file is fetched (from a requester pays bucket), and usedto fill in the additional STAC metadata.

### Sentinel-2

The data that is ingested by the sat-stac-sentinel CLI starts with bucket inventory files that are retrieved and used to find all of the `tileInfo.json` files (this is the metadata for one Sentinel scene). In addition to the inventories, an SNS message is published (arn:aws:sns:us-west-2:274514004127:NewSceneHTML) whenever a new `index.html` appears in the bucket. The sat-stac-sentinel Lambda function listens for this message to get the link of the s3 path with the new scene.

In either case the tileInfo.json contains all of the data needed to create a STAC Item, however the given geometry is in native coordinates rather than lat/lon. The library reprojects the geometry using EPSG:4326. Additionally, the convex hull is calculated for the geometry. In most cases this doesn't make a difference, however some of the tile geometries can be long and complex. Taking the convex hull is a way to simplify the geometry without impacting search and discovery.

## Development

The `master` branch is the latest versioned release, while the `develop` branch is the latest development version. When making a new release:

- Update the [version](stac_sentinel/version.py)
- Update [CHANGELOG.md](CHANGELOG.md)
- Create PR and merge to master
- Create a release on GitHub from `master` with the new version

Currently, the Lambda function needs to be deployed manually. It is `stac-sentinel-v0` located in `eu-central-1`.


## About
[stac_sentinel](https://github.com/sat-utils/stac-sentinel) leverages the use of Spatio-Temporal Asset Catalogs](https://github.com/radiantearth/stac-spec)
