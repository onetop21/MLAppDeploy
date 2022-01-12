import os

import cerberus_document_editor as cde

from mlad.cli.validator import yaml_parser
from mlad.cli.exceptions import InvalidFileTypeError


APP_NAME = 'MLAD Project YAML Editor'


def run_editor(document_path: str = './mlad-project.yml'):

    with open(f'{yaml_parser.SCHEMA_PATH}/schema.yaml') as f:
        schema = yaml_parser.load(f)

    doc_ext = os.path.splitext(document_path)[1]
    if not doc_ext.lower() in ['.yaml', '.yml']:
        raise InvalidFileTypeError(doc_ext)
    if os.path.exists(document_path):
        with open(document_path) as f:
            document = yaml_parser.load(f)
    else:
        document = {}

    app = cde.MainWindow(APP_NAME, pagestack=True)
    modified = app.run(cde.EditorPage(os.path.basename(document_path), schema, document))

    if modified:
        with open(document_path, 'wt') as f:
            f.write(yaml_parser.dump(modified))
