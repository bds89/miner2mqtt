from setuptools import setup, find_packages
from os.path import join, dirname
import m2m

setup(
    name='miner2mqtt',
    version=m2m.__version__,
    author='bds89',
    author_email='bds89@mail.ru',
    packages=find_packages(),
    long_description=open(join(dirname(__file__), 'README.md')).read(),
    include_package_data=True,
    install_requires=[
        'paho-mqtt'
]
)
