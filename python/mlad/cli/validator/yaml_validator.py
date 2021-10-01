import warnings
import cerberus

warnings.simplefilter("ignore", UserWarning)


class Validator(cerberus.Validator):
    def _validate_description(self, constraint, field, value):
        '''For use YAML Editor'''

    def _validate_order(self, constraint, field, value):
        '''For use YAML Editor'''

    def _validate_multiline(self, constraint, field, value):
        '''For use YAML Editor'''

    def _validate_selector(self, constraint, field, value):
        _errors = []
        for _ in reversed(constraint):
            validator = Validator(_)
            if validator.validate(value):
                return
            if not validator.errors.get('kind'):
                _errors = validator._errors
        if _errors:
            def update_document_path(errors):
                for error in errors:
                    error.document_path = (*self.document_path, field, *error.document_path)
                    if error.info:
                        for info in error.info:
                            update_document_path(info)
            update_document_path(_errors)
            self._error(_errors)
        else:
            self._error(validator._errors)

    def _normalize_coerce_selector(self, document):
        for key, value in self.schema.items():
            for schema in value.get('selector', []):
                validator = Validator(schema)
                if validator.validate(document):
                    return validator.normalized(document)
        return validator.normalized(document)

    def ordered(self, document, schema=None):
        '''For use YAML Editor'''
        schema = schema or self.schema
        document = dict(
            sorted(document.items(), key=lambda x: schema[x[0]].get('order', float('inf'))))
        for k, v in document.items():
            if isinstance(v, dict) and schema[k].get('schema'):
                document[k] = self.ordered(v, schema[k]['schema'])
        return document