import sys
import os
from setuptools import setup, find_packages
from mlad import __version__

def main():
    # Read Description form file
    try:
        with open('README.md') as f:
            description = f.read()
    except:
        print('Cannot find README.md file.', file=sys.stderr)
        description = ""

    setup(
      name='MLAppDeploy',
      version=__version__,
      description='Machine learning Application Deployment Tool.',
      long_description=description,
      author='Hyoil LEE',
      author_email='onetop21@gmail.com',
      license='MIT License',
      packages=find_packages(exclude=['.temp']),
      url='https://github.com/onetop21/MLAppDeploy.git',
      zip_safe=False,
      python_requires='>3.6',
      install_requires=[
        'Click>=7.0,<8.0.0', 
        'PyYAML>=5.4.1,<6.0', 
        'docker>=4.0.2,<5.0.0',
        'requests>=2.22.0,<3.0.0',
        'requests-unixsocket>=0.2.0',
        'python-dateutil>=2.8.1,<3.0.0',
        'uvicorn>=0.13.3,<1.0.0',
        'fastapi>=0.63.0,<1.0.0',
        'psutil>=5.8.0,<5.9.0',
        'omegaconf>=2.0.6,<3.0.0',
        'kubernetes>=19.0.0,<20.0.0',
        'PyJWT>=2.1.0,<3.0.0',
        'Cerberus>=1.3.0,<1.4.0',
        'cerberus-kind==0.0.6',
        'dictdiffer==0.9.0'
      ],
      entry_points='''
        [console_scripts]
        mlad=mlad.cli.__main__:main
      '''
    )

if __name__ == '__main__':
    main()
