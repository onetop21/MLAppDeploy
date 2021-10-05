#!/home/onetop21/base3.7/bin/python
from mlad.cli.validator.yaml_parser import load, dump, SCHEMA_PATH
from mlad.cli.validator.yaml_validator import Validator
from mlad.cli.validator.exceptions import InvalidProjectYaml, InvalidComponentYaml
from cerberus.validator import DocumentError


def validate_project(target):
    with open(f'{SCHEMA_PATH}/schema-project.yaml') as f:
        schema = load(f)

    v = Validator(schema)
    try:
        res = v.validate(target)
    except DocumentError as e:
        raise InvalidProjectYaml(str(e))
    if res:
        return v.ordered(v.normalized(target))
    else:
        print(v.errors)
        raise InvalidProjectYaml(v.errors)


def validate_component(target):
    with open(f'{SCHEMA_PATH}/schema-component.yaml') as f:
        schema = load(f)

    v = Validator(schema)
    try:
        res = v.validate(target)
    except DocumentError as e:
        raise InvalidComponentYaml(str(e))
    if res:
        return v.ordered(v.normalized(target))
    else:
        raise InvalidComponentYaml(v.errors)