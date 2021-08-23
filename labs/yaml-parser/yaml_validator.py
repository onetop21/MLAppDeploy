#!/home/onetop21/base3.7/bin/python
import copy
import warnings
import cerberus
warnings.simplefilter("ignore", UserWarning)

class Validator(cerberus.Validator):
    def _validate_description(self, constraint, field, value):
        pass
    
    def _validate_selector(self, constraint, field, value):
        del self.schema[field]['selector']
        recent_error = None
        for _ in reversed(constraint):
            validator = cerberus.Validator(_)
            if validator.validate(value): 
                self.schema[field]['schema'] = _
                return 
            recent_error = validator._errors
        self._error(recent_error)