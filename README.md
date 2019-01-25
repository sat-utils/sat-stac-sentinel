# sat-stac-sentinel

This is a repository used for the creation and maintenance of a [STAC](https://github.com/radiantearth/stac-spec) compliant [Sentinel catalog](https://sentinel-stac.s3.amazonaws.com/catalog.json) for data from the [Sentinel on AWS project](https://registry.opendata.aws/sentinel-2/) (located at s3://sentinel-s2-l1c/).

There are two pieces of this repository:

- A Python library (satstac.sentinel) and CLI containing functions for reading Sentinel metadata, transforming to STAC Items, and adding to the Sentinel catalog.
- An AWS Lambda handler that accepts an SNS message containing the s3 URL for a new Sentinel scene, transforms it, and adds it to the catalog.

To create the Sentinel STAC catalog located at https://sentinel-stac.s3.amazonaws.com/catalog.json the sat-stac-sentinel CLI was used to create the initial catalog of historical data. The Lambda function is deployed and keeping the catalog up to date with new scenes.

## Installation

Sat-stac-landsat can be installed from this repository. It is not in PyPi because it is not a library that is going to be of general use. It exists to create a Landsat STAC catalog and keep it up to date, which is currently ongoing.


## Usage

A command line tool is available for ingesting the existing Sentinel data on s3 and creating/adding to a STAC catalog.

```bash
$ sat-stac-sentinel -h
usage: sat-stac-sentinel [-h] {ingest,inventory} ...

sat-stac-sentinel (v0.1.0)

positional arguments:
  {ingest,inventory}
    ingest            Ingest records into catalog
    inventory         Get latest inventory of tileInfo.json files

optional arguments:
  -h, --help          show this help message and exit
```

There are two available commands:

### `inventory`

This will fetch the latest inventory files from s3://sentinel-inventory/sentinel-s2-l1c/sentinel-s2-l1c-inventory and save to a local file. This isn't necessary, files can be directly ingested from the latest inventory files, but saving the file first allows it to be broken up and run with several jobs.

### `ingest`

This will ingest records either from a local inventory file or, if not provided, the latest bucket inventory files

```
$ sat-stac-sentinel ingest -h
usage: sat-stac-sentinel ingest [-h] [--version] [--log LOG] [--start START]
                                [--end END] [--prefix PREFIX] [--s3meta]
                                [--filename FILENAME] [--publish PUBLISH]
                                catalog

positional arguments:
  catalog              Catalog that contains the Collection

optional arguments:
  -h, --help           show this help message and exit
  --version            Print version and exit
  --log LOG            0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical
                       (default: 2)
  --start START        Start date of ingestion (default: None)
  --end END            End date of ingestion (default: None)
  --prefix PREFIX      Only ingest scenes with a path starting with prefix
                       (default: None)
  --s3meta             Get metadata directly from S3 (requestor pays)
                       (default: False)
  --filename FILENAME  Inventory filename to use (default to fetch latest from
                       bucket Inventory files) (default: None)
  --publish PUBLISH    ARN to publish new Items to (default: None)
```

The `catalog` argument is the URL to the root catalog which contains a child collection called 'sentinel-2-l1c'. If the 'sentinel-2-l1c' Collection does not exist in the Catalog it will be added. In the case of the catalog maintained by this repo it is located at https://sentinel-stac.s3.amazonaws.com/catalog.json.

If `start` and/or `end` are provided the records are all scanned and only those meeting the date requirements are ingested.

If `filename` is provided it will read the inventory from a file (generated with `sat-stac-sentinel inventory`) instead of retriving the latst bucket inventory files.

The `s3meta` switch controls where the metadata comes from. The default is to get it from a proxy address rather than directly from the bucket (which is requestor pays). The actual cost is negligible, but it tunns out there is little difference in speed so this switch can be left alone.

The `publish` switch allows publishing of a new STAC Item to an SNS topic. This should not be used when creating a whole catalog, it will create too many SNS messages.

## Transforming Sentinel metadata to STAC

The data that is ingested by the sat-stac-sentinel CLI starts with bucket inventory files that are retrieved and used to find all of the `tileInfo.json` files (this is the metadata for one Sentinel scene). In addition to the inventories, an SNS message is published (arn:aws:sns:us-west-2:274514004127:NewSceneHTML) whenever a new `index.html` appears in the bucket. The sat-stac-sentinel Lambda function listens for this message to get the link of the s3 path with the new scene.

In either case the tileInfo.json contains all of the data needed to create a STAC Item, however the given geometry is in native coordinates rather than lat/lon. The library reprojects the geometry using EPSG:4326. Additionally, the convex hull is calculated for the geometry. In most cases this doesn't make a difference, however some of the tile geometries can be long and complex. Taking the convex hull is a way to simplify the geometry without impacting search and discovery.

## Development

The `master` branch is the latest versioned release, while the `develop` branch is the latest development version. When making a new release:

- Update the [version](satstac.sentinel.version.py)
- Update [CHANGELOG.md](CHANGELOG.md)
- Create PR and merge to master
- Create new tag with the version and push to GitHub:

```bash
$ git tag `<version>`
$ git push origin `<version>`
```

On a release (merge to `master`) CircleCI will package the Lambda code and deploy it to the production Lambda function that listens (via SNS) for new Sentinel scenes, creates STAC Items and adds them to the Catalog.


## About
[sat-stac-sentinel](https://github.com/sat-utils/sat-stac-sentinel) was created by [Development Seed](<http://developmentseed.org>) and is part of a collection of tools called [sat-utils](https://github.com/sat-utils).
