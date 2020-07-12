from setuptools import setup, find_packages

# Get version
__version__ = '0.0.1'
with open('mlad/__version__.py') as f:
  import re
  version = re.search(r'version[ =\'"]+([0-9.]+)', f.read())
  if version:
    for group in version.groups():
      __version__ = group

setup(
  name='MLAppDeploy',
  version=__version__,
  description='Machine learning Application Deployment Tool.',
  author='Hyoil LEE',
  author_email='onetop21@gmail.com',
  license='MIT License',
  packages=find_packages(exclude=['.temp']),
  url='',
  zip_safe=False,
  python_requires='>3.5',
  install_requires=['Click==7.0', 'PyYAML<4.3,>=3.10', 'docker==4.0.2'],
  scripts=['mlad/mlad']
)

