class InvalidProjectError(Exception):
    def __init__(self, project_id):
        self.project_id = project_id

    def __str__(self):
        return f'Cannot find project {self.project_id}'

class InvalidServiceError(Exception):
    def __init__(self, project_id, service_id):
        self.project_id = project_id
        self.service_id = service_id
    
    def __str__(self):
        return (f'Cannot find service {self.service_id}'
               f'in project {self.project_id}')
