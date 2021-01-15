from fastapi import FastAPI, Depends, Header
from mladservice.routers import image, service, project, node, auth
from mladservice.auth import Authorization

def create_app():
    app = FastAPI()
    return app

user = Authorization('user')
admin = Authorization('admin')

app = create_app()
app.include_router(image.router)
app.include_router(node.router, dependencies=[Depends(admin.verify_auth)])
app.include_router(service.router)
app.include_router(project.router, dependencies=[Depends(user.verify_auth)])
app.include_router(auth.router,dependencies=[Depends(admin.verify_auth)])
