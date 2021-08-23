from mlad.cli import config

from . import mock


def setup_function():
    mock.setup()


def teardown_function():
    mock.teardown()


def test_env():
    mock.init()
    ret, _ = config.env(unset=False)
    expected = sorted([
        'export S3_ENDPOINT=https://localhost:9000',
        'export S3_USE_HTTPS=1',
        'export S3_VERIFY_SSL=0',
        'export AWS_ACCESS_KEY_ID=minioadmin',
        'export AWS_SECRET_ACCESS_KEY=minioadmin',
        'export AWS_REGION=us-west-1',
        'export DB_ADDRESS=mongodb://localhost:27017',
        'export DB_USERNAME=dbadmin',
        'export DB_PASSWORD=dbadmin'
    ])
    assert ret == expected


def test_env_unset():
    mock.init()
    ret, _ = config.env(unset=True)
    expected = sorted([
        'export S3_ENDPOINT=',
        'export S3_USE_HTTPS=',
        'export S3_VERIFY_SSL=',
        'export AWS_ACCESS_KEY_ID=',
        'export AWS_SECRET_ACCESS_KEY=',
        'export AWS_REGION=',
        'export DB_ADDRESS=',
        'export DB_USERNAME=',
        'export DB_PASSWORD='
    ])
    assert ret == expected
