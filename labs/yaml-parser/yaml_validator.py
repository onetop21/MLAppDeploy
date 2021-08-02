#!/home/onetop21/base3.7/bin/python
import copy
import warnings
import cerberus
warnings.simplefilter("ignore", UserWarning)

class Validator(cerberus.Validator):
    def _validate_selector(self, constraint, field, value):
        del self.schema[field]['selector']
        document = copy.deepcopy(self.document)
        for _ in reversed(constraint):
            self.schema[field]['schema'] = _
            if self.validate(document): return
            if cerberus.Validator({'kind': _['kind']}).validate({'kind': value.get('kind')}): return