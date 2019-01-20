# sat-stac-sentinel

This is a repository used for the creation and maintenance of a [STAC](https://github.com/radiantearth/stac-spec) compliant [Sentinel catalog](https://sentinel-stac.s3.amazonaws.com/catalog.json) for data from the [Sentinel on AWS project](https://registry.opendata.aws/sentinel-2/) (located at s3://sentinel-s2-l1c/).

There are two pieces of this repository:

- A Python library (satstac.sentinel) and CLI containing functions for reading Sentinel metadata, transforming to STAC Items, and adding to the Sentinel catalog.
- An AWS Lambda handler that accepts an SNS message containing the s3 URL for a new Sentinel scene, transforms it, and adds it to the catalog.

To create the Sentinel STAC catalog located at https://sentinel-stac.s3.amazonaws.com/catalog.json the sat-stac-sentinel CLI was used to create the initial catalog of historical data. The Lambda function is deployed and keeping the catalog up to date with new scenes.

## Installation



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


The `catalog` argument is the URL to the root catalog which contains a child collection called 'sentinel-2-l1c'. If the 'sentinel-2-l1c' Collection does not exist in the Catalog it will be added. In the case of the catalog maintained by this repo it is located at https://sentinel-stac.s3.amazonaws.com/catalog.json.

If `start` and/or `end` are provided the records are all scanned and only those meeting the date requirements are ingested.


## Transforming Sentinel metadata to STAC

The data that is ingested by the sat-stac-sentinel CLI starts with

In addition to the inventories, an SNS message is published (arn:aws:sns:us-west-2:274514004127:NewSceneHTML) whenever a new `index.html` appears in the bucket. The sat-stac-sentinel Lambda function listens for this message to get the link of the s3 path with the new scene.




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
