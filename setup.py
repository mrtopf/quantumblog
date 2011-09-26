from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='quantumblog',
      version=version,
      description="Blogging Software",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='COM.lounge',
      author_email='info@comlounge.net',
      url='',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        "starflyer",
        "mongoquery",
      ],
      entry_points="""
        [console_scripts]
        run = starflyer.scripts:run
        [starflyer_app_factory]
        default = quantumblog.main:app_factory
        [starflyer_setup]
        default = quantumblog.setup:setup
      """,
      )
