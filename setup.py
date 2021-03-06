# -*- coding: utf-8 -*-
##
## Installs co2mpas:
## 		python setup.py install
## or
##		pip install -r requirements.txt
## and then just code from inside this folder.
#
import io
import os
import re
import sys
from os import path as osp

from setuptools import setup

from polyversion import polyversion

mydir = osp.dirname(osp.abspath(__file__))
os.chdir(mydir)


def read_text_lines(fname):
    with io.open(os.path.join(mydir, fname), encoding='utf-8') as fd:
        return fd.readlines()


def yield_rst_only_markup(lines):
    """
    :param file_inp:     a `filename` or ``sys.stdin``?
    :param file_out:     a `filename` or ``sys.stdout`?`

    """
    substs = [
        # Selected Sphinx-only Roles.
        #
        (r':abbr:`([^`]+)`', r'\1'),
        (r':ref:`([^`]+)`', r'ref: *\1*'),
        (r':term:`([^`]+)`', r'**\1**'),
        (r':dfn:`([^`]+)`', r'**\1**'),
        (r':(samp|guilabel|menuselection|doc|file):`([^`]+)`', r'``\2``'),

        # Sphinx-only roles:
        #        :foo:`bar`   --> foo(``bar``)
        #        :a:foo:`bar` XXX afoo(``bar``)
        #
        #(r'(:(\w+))?:(\w+):`([^`]*)`', r'\2\3(``\4``)'),
        #(r':(\w+):`([^`]*)`', r'\1(`\2`)'),
        # emphasis
        # literal
        # code
        # math
        # pep-reference
        # rfc-reference
        # strong
        # subscript, sub
        # superscript, sup
        # title-reference


        # Sphinx-only Directives.
        #
        (r'\.\. doctest', r'code-block'),
        (r'\.\. module', r'code-block'),
        (r'\.\. plot::', r'.. '),
        (r'\.\. seealso', r'info'),
        (r'\.\. glossary', r'rubric'),
        (r'\.\. figure::', r'.. '),
        (r'\.\. image::', r'.. '),

        (r'\.\. dispatcher', r'code-block'),

        # Other
        #
        (r'\|version\|', r'x.x.x'),
        (r'\|today\|', r'x.x.x'),
        (r'\.\. include:: AUTHORS', r'see: AUTHORS'),
    ]

    regex_subs = [(re.compile(regex, re.IGNORECASE), sub)
                  for (regex, sub) in substs]

    def clean_line(line):
        try:
            for (regex, sub) in regex_subs:
                line = regex.sub(sub, line)
        except Exception as ex:
            print("ERROR: %s, (line(%s)" % (regex, sub))
            raise ex

        return line

    for line in lines:
        yield clean_line(line)


polyver = 'polyversion >= 0.2.2a0'  # Workaround buggy git<2.15, envvar: co2mpas_VERION
readme_lines = read_text_lines('README.rst')
description = readme_lines[1]
long_desc = ''.join(yield_rst_only_markup(readme_lines))


setup(
    name='co2mpas',
    ## Include a default for robustness (eg to work on shallow git -clones)
    #  but also for engraves to have their version visible.
    version='0.0.0',
    polyversion=True,
    description="The Type-Approving vehicle simulator predicting NEDC CO2 emissions from WLTP",
    long_description=long_desc,
    download_url='https://github.com/JRCSTU/ALLINONE/releases/',
    keywords="""
        CO2 fuel-consumption WLTP NEDC vehicle automotive
        EU JRC IET STU correlation back-translation policy monitoring
        M1 N1 simulator engineering scientific
    """.split(),
    url='https://co2mpas.io/',
    license='EUPL 1.1+',
    author='CO2MPAS-Team',
    author_email='JRC-CO2MPAS@ec.europa.eu',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 4 - Beta",
        'Natural Language :: English',
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        'Environment :: Console',
        'License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)',
        'Natural Language :: English',
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: OS Independent",
        'Topic :: Scientific/Engineering',
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires='>=3.5',
    setup_requires=[
        # PEP426-field actually not used by `pip`, hence
        # included also in /requirements/developmnet.pip.
        'setuptools',
        'setuptools-git>=0.3',  # Example given like that in PY docs.
        'wheel',
        polyver,
    ],
    # dev_requires=[
    #     # PEP426-field actually not used by `pip`, hence
    #     # included in /requirements/developmnet.pip.
    #     'sphinx',
    # ],
    install_requires=[
        polyver,
        'co2sim[io,plot]',
        'co2gui',
        'co2dice',
    ],
    zip_safe=True,
    options={
        'bdist_wheel': {
            'universal': True,
        },
    },
    platforms=['any'],
)
