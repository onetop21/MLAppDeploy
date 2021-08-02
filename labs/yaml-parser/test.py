#!/home/onetop21/base3.7/bin/python
import sys
import json
from pprint import pprint
from yaml_parser import load, dump
from yaml_validator import Validator

#$1 schema
#$2 document
with open(sys.argv[1]) as f:
    schema = load(f)

with open(sys.argv[2]) as f:
    document = load(f)

print('Document.')
pprint(document, sort_dicts=False)
v = Validator(schema)
if v.validate(document):
    print('Verified.')
    pprint(v.document, sort_dicts=False)
    with open('output.yaml', 'w') as f:
        f.write(dump(v.document))
else:
    print("Errors:", v.errors)
    sys.exit(1)
