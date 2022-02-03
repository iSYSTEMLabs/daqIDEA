from setuptools import setup, find_packages

setup(name='daqIDEA',
      version='1.0',
      description='iSYSTEM daqIDEA',
      author='iSYSTEM',
      author_email='support@isystem.com',
      url='https://www.isystem.com/',
      install_requires=[
          "isystem.connect",
          "matplotlib",
          "numpy",
          "openpyxl"
      ]
      )
