#!/home/onetop21/base3.7/bin/python
from cerberus.validator import DocumentError
from cerberus_kind import Validator

from mlad.cli.validator.yaml_parser import load, dump, SCHEMA_PATH
from mlad.cli.validator.exceptions import InvalidProjectYaml, InvalidComponentYaml


def validate(target):
    with open(f'{SCHEMA_PATH}/schema.yaml') as f:
        schema = load(f)

    v = Validator(schema, ordered=True)
    try:
        res = v.validate(target)
    except DocumentError as e:
        raise InvalidProjectYaml(str(e))
    if res:
        return v.normalized_by_order(target)
    else:
        print(v.errors)
        raise InvalidProjectYaml(v.errors)

