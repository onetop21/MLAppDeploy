from setuptools import setup, find_packages

setup(
    name='MLAppDeploy',
    version='0.0.1',
    description='Machine learning Application Deployment Tool.',
    author='Hyoil LEE',
    author_email='onetop21@gmail.com',
    license='MIT License',
    packages=find_packages(exclude=['.temp']),
    url='',
    zip_safe=False,
    python_requires='>3.5',
    install_requires=['Click==7.0', 'PyYAML<4.3,>=3.10'],
    #install_requires=['Click==7.0', 'PyYAML<4.3,>=3.10', 'docker-compose==1.24.0'],
    scripts=['bin/mlad']
)

