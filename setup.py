#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Ludolph: Erigones API plugin.
# Copyright (C) 2015 Erigones, s. r. o.
#
# See the LICENSE file for copying permission.

import sys
import codecs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# noinspection PyPep8Naming
from es.__init__ import __version__ as VERSION

DESCRIPTION = 'Erigones API plugin'

with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

if sys.version_info[0] < 3:
    DEPS = ['ludolph', 'dnspython', 'requests']
else:
    DEPS = ['ludolph', 'dnspython3', 'requests']

CLASSIFIERS = [
    'Environment :: Console',
    'Environment :: Plugins',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: MIT License',
    'Operating System :: MacOS',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

packages = [
    'es',
]

setup(
    name='ludolph-es',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author='Erigones',
    author_email='erigones [at] erigones.com',
    url='https://github.com/erigones/ludolph-es/',
    license='MIT',
    packages=packages,
    install_requires=DEPS,
    platforms='any',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
