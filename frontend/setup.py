from setuptools import setup, find_packages
from bin import __version__

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

