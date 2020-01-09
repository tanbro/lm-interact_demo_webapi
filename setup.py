#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import os

from setuptools import find_packages, setup


setup(
    name='lmdemo',
    description='huamei.ai LM Demo 的 Webserver',
    author="Liu Xue Yan",
    author_email="liu_xue_yan@foxmail.com",
    long_description=(2 * os.linesep).join(
        io.open(file, encoding='utf-8').read()
        for file in ('README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'AUTHORS.md')
    ),
    long_description_content_type='text/markdown',
    license='commercial',
    url='https://github.com/tanbro/lm-webdemo-site',
    python_requires='>=3.6',
    setup_requires=[
        'setuptools_scm',
        'setuptools_scm_git_archive',
    ],
    use_scm_version={
        # guess-next-dev:	automatically guesses the next development version (default)
        # post-release:	generates post release versions (adds postN)
        'version_scheme': 'guess-next-dev',
        'write_to': 'lmdemo/version.py',
    },
    install_requires=[
        'dataclasses;python_version<"3.7"',
        'fastapi',
        'python-dateutil',
        'PyYAML',
        'transitions[diagrams]',
    ],
    extras_require={
        'uvicorn': ['uvicorn', 'python-dotenv']
    },
)
