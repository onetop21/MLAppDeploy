#!/home/onetop21/base3.7/bin/python
import os

from cerberus.validator import DocumentError
from cerberus_kind.utils import parse_error
from cerberus_document_editor import yaml_parser

from mlad.cli.validator.yaml_validator import Validator
from mlad.cli.validator.exceptions import InvalidProjectYaml


SCHEMA_PATH = os.path.dirname(os.path.abspath(__file__))


def validate(target):
    with open(f'{SCHEMA_PATH}/schema.yaml') as f:
        schema = yaml_parser.load(f)
    v = Validator(schema, purge_unknown=True)
    try:
        res = v.validate(target)
    except DocumentError as e:
        raise InvalidProjectYaml(str(e))

    if res:
        return v.normalized_by_order(target)
    else:
        raise InvalidProjectYaml(parse_error(v.errors, with_path=True))
