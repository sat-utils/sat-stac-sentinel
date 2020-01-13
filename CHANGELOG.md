# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.2.0] - 2020-01-12

### Added
- Sentinel-1 support
- Sentinel-2 L2A support

### Changed
- STAC version updated to 0.9.0
- Complete refactor of library into a Class SentinelSTAC

## Removed
- Functionality for creating/appending to a Catalog. This library now just creates the Items from the original metadata and allows one to loop throught the STAC Items in the archive on AWS
- Creating/appending to Catalogs can use this library, but it is outside the scope

### Fixed
- Fix filename of Band B8A, which was incorrectly set to B08, issue #11
- Update temporal extent of collection to be datetime instead of just date

## [v0.1.0] - 2018-10-25

Initial Release

[Unreleased]: https://github.com/sat-utils/sat-stac-sentinel/compare/0.1.0...HEAD
[v0.2.0]: https://github.com/sat-utils/sat-stac-sentinel/compare/0.1.0...0.2.0
[v0.1.0]: https://github.com/sat-utils/sat-stac-sentinel/tree/0.1.0