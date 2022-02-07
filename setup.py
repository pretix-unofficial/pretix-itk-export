import os
from distutils.command.build import build

from django.core import management
from setuptools import setup, find_packages


try:
    with open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf-8') as f:
        long_description = f.read()
except Exception:
    long_description = ''


class CustomBuild(build):
    def run(self):
        management.call_command('compilemessages', verbosity=1, interactive=False)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}


setup(
    name='pretix-itk-export',
    version='1.0.0',
    description='ITK export',
    long_description=long_description,
    url='https://github.com/rimi-itk/pretix-itk-export.git',
    author='Mikkel Ricky',
    author_email='rimi@aarhus.dk',
    license='Apache Software License',

    install_requires=['dateparser'],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_itkexport=pretix_itkexport:PretixPluginMeta
""",
)
