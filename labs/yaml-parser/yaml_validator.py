import warnings
import cerberus
warnings.simplefilter("ignore", UserWarning)

class Validator(cerberus.Validator):
    def _validate_description(self, constraint, field, value):
        '''For use YAML Editor'''

    def _validate_order(self, constraint, field, value):
        '''For use YAML Editor'''
    
    def _validate_selector(self, constraint, field, value):
        recent_error = None
        for _ in reversed(constraint):
            validator = cerberus.Validator(_)
            if validator.validate(value): 
                return 
            recent_error = validator._errors
        self._error(recent_error)

    def _normalize_coerce_selector(self, document):
        for key, value in self.schema.items():
            for schema in value.get('selector', []):
                validator = cerberus.Validator(schema)
                if validator.validate(document):
                    return validator.normalized(document)
        print('Not Found suitable selector schema.')

    def ordered(self, document, schema=None):
        '''For use YAML Editor'''
        schema = schema or self.schema
        document=dict(sorted(document.items(), key=lambda x: schema[x[0]].get('order', float('inf')))) 
        for k, v in document.items():
            if isinstance(v, dict) and schema[k].get('schema'):
                document[k] = self.ordered(v, schema[k]['schema'])
        return document
    