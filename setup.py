#!/usr/bin/env python
from setuptools import setup, find_packages
from imp import load_source
from os import path
import io

__version__ = load_source('stac_sentinel.version', 'stac_sentinel/version.py').__version__

here = path.abspath(path.dirname(__file__))

# get the dependencies and installs
with io.open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')

install_requires = [x.strip() for x in all_reqs if 'git+' not in x and 'requirements' not in x]
dependency_links = [x.strip().replace('git+', '') for x in all_reqs if 'git+' not in x]

setup(
    name='stac-sentinel',
    author='Matthew Hanson (matthewhanson)',
    author_email='matt.a.hanson@gmail.com',
    version=__version__,
    description='Creating STAC Items for Sentinel',
    url='https://github.com/sat-utils/sat-stac-sentinel.git',
    license='MIT',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='',
    entry_points={
        'console_scripts': ['stac-sentinel=stac_sentinel.cli:cli'],
    },
    packages=['stac_sentinel'],
    include_package_data=True,
    install_requires=install_requires,
    dependency_links=dependency_links,
)
