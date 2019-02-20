#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of 'dob'.
#
# 'dob' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'dob' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'dob'.  If not, see <http://www.gnu.org/licenses/>.

"""
Packaging instruction for setup tools.

Refs:

  https://setuptools.readthedocs.io/

  https://packaging.python.org/en/latest/distributing.html

  https://github.com/pypa/sampleproject
"""

import os
import re
# sys is not used herein, but by dob/__init__.py, which we exec.
# F401 'sys' imported but unused
import sys  # noqa: F401

# Because exec(init_py), silence linter.
from gettext import gettext as _  # noqa: F401
from io import open

try:
    # See below: We could instead use find_packages, but instead hardcode,
    #   from setuptools import setup, find_packages
    from setuptools import setup
except ImportError:
    from distutils.core import setup


requirements = [
    # https://github.com/pytest-dev/apipkg
    'apipkg',
    # Platform-specific directory magic.
    #  https://github.com/ActiveState/appdirs
    'appdirs',
    # (lb): Click may be the best optparser of any language I've used.
    #  https://github.com/pallets/click
    # FIXME: (lb): Click has not been PyPI'ed since January, 2017,
    #        yet there's been a ton of activity since!
    #        What I really want is the 'hidden' option, because
    #        there's a built-in `--version` option, and then I
    #        added the `-v` option, and I didn't want to pollute
    #        the help with 2 mostly redundant version option lines.
    #        So I forked Click, and published bleeding edge code!
    #        Now `dob` truly is Alpha software!!
    #  'Click',
    'click--hotoffthehamster',
    # Indispensable aliases support for Click.
    #  Stolen from: https://github.com/click-contrib/click-aliases
    #  Released at: https://github.com/hotoffthehamster/click-alias
    'click-alias >= 0.1.0a1',
    # Enable Click color support (we don't use colorama directly, but it does),
    #  "on Windows, this ... is only available if colorama is installed".
    #  https://click.palletsprojects.com/en/5.x/utils/#ansi-colors
    #  https://pypi.org/project/colorama/
    'colorama',
    # "Very simple Python library for color and formatting in terminal."
    #  https://gitlab.com/dslackw/colored
    'colored',
    # Python 2 configparser backport.
    #  https://docs.python.org/3/library/configparser.html
    'configparser >= 3.5.0b2',
    # Compatibility layer between Python 2 and Python 3.
    #  https://python-future.org/
    'future',
    # Vocabulary word pluralizer.
    #  https://github.com/ixmatus/inflector
    'Inflector',
    # https://github.com/hjson/hjson-py
    'hjson',
    # Humanfriendly is one of the many table formatter choices.
    #  https://github.com/xolox/python-humanfriendly
    'humanfriendly',
    # Elapsed timedelta formatter, e.g., "1.25 days".
    'human-friendly_pedantic-timedelta >= 0.0.6',
    # https://github.com/mnmelo/lazy_import
    'lazy_import',
    # The heart of Hamster. (Ye olde `hamster-lib`).
    'nark',
    # Amazeballs prompt library.
    'prompt-toolkit >= 2.0.0',
    # For the Carousel Fact description lexer.
    #  http://pygments.org/
    'pygments',
    # Just Another EDITOR package.
    #  https://github.com/fmoo/python-editor
    'python-editor',
    # Virtuous Six Python 2 and 3 compatibility library.
    #  https://six.readthedocs.io/
    'six',
    # https://github.com/grantjenks/python-sortedcontainers/
    'sortedcontainers',
    # Tabulate is one of the many table formatter choices.
    #  https://bitbucket.org/astanin/python-tabulate
    'tabulate',
    # Texttable is one of the many table formatter choices.
    #  https://github.com/bufordtaylor/python-texttable
    'texttable',
]


# *** Boilerplate setuptools helper fcns.

# Source values from the top-level {package}/__init__.py,
# to avoid hardcoding herein.

# (lb): I was inspired by PPT's get_version() to write this mess.
# Thank you, PPT!

def top_level_package_file_path(package_dir):
    """Return path of {package}/__init__.py file, relative to this module."""
    path = os.path.join(
        os.path.dirname(__file__),
        package_dir,
        '__init__.py',
    )
    return path


def top_level_package_file_read(path):
    """Read the file at path, and decode as UTF-8."""
    with open(path, 'rb') as init_f:
        init_py = init_f.read().decode('utf-8')
    return init_py


def looks_like_app_code(line):
    """Return True if the line looks like `key = ...`."""
    matches = re.search("^\S+ = \S+", line)
    return matches is not None


def top_level_package_file_strip_imports(init_py):
    """Stip passed array of leading entries not identified as `key = ...` code."""
    # Expects comments, docstrings, and imports up top; ``key = val`` lines below.
    culled = []
    past_imports = False
    for line in init_py.splitlines():
        if not past_imports:
            past_imports = looks_like_app_code(line)
        if past_imports:
            culled.append(line)
    return "\n".join(culled)


def import_business_vars(package_dir):
    """Source the top-level __init__.py file, minus its import statements."""
    pckpath = top_level_package_file_path(package_dir)
    init_py = top_level_package_file_read(pckpath)
    source = top_level_package_file_strip_imports(init_py)
    exec(source)
    cfg = {key: val for (key, val) in locals().items() if key.startswith('__')}
    return cfg


# Import variables from nark/__init__.py,
# without triggering that files' imports.
cfg = import_business_vars('dob')

# *** Local file content.

long_description = open(
    os.path.join(
        os.path.dirname(__file__),
        'README.rst'
    ),
    encoding='utf-8',
).read()

# *** Package definition.

setup(
    name=cfg['__pipname__'],
    version=cfg['__version__'],
    author=cfg['__author__'],
    author_email=cfg['__author_email__'],
    url=cfg['__projurl__'],
    description=cfg['__briefly__'],
    long_description=long_description,
    # Alternatively, ask setuptools to figure out the package name(s):
    #   packages=find_packages(),
    packages=['dob', ],
    package_dir={'dob': 'dob'},
    install_requires=requirements,
    license='GPLv3',
    zip_safe=False,
    keywords=cfg['__keywords__'],
    classifiers=[
        # FIXME/2018-06-13: Our goal (this Summer?): Production/Stable.
        # 'Development Status :: 2 - Pre-Alpha',
        'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python',
        # 'Topic :: Artistic Software',
        'Topic :: Office/Business :: News/Diary',
        # 'Topic :: Religion',  # Because Hamster *is* is religion!
        'Topic :: Text Processing',
    ],
    # <app>=<pkg>.<cls>.run
    entry_points='''
    [console_scripts]
    dob=dob.dob:run
    '''.strip()
)

