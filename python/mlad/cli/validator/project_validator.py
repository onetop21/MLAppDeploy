#!/home/onetop21/base3.7/bin/python
import sys
import json
from mlad.cli.validator.yaml_parser import load, dump, SCHEMA_PATH
from mlad.cli.validator.yaml_validator import Validator
from mlad.cli.validator.exceptions import InvalidProjectYaml
from cerberus.validator import DocumentError

def validate(project):
    with open(f'{SCHEMA_PATH}/schema-project.yaml') as f:
        schema = load(f)

    v = Validator(schema)
    try:
        res = v.validate(project)
    except DocumentError as e:
        raise InvalidProjectYaml(str(e))
    if res:
        print("Project file verified.")
        output = v.ordered(v.normalized(project))
        with open("output.yaml", "w") as f:
            f.write(dump(output))
        return output
    else:
        print(v.errors)
        raise InvalidProjectYaml(v.errors)