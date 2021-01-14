from fastapi import FastAPI
from mladservice.routers import image, service, project, node

def create_app():
    app = FastAPI()
    return app


app = create_app()
app.include_router(image.router)
app.include_router(node.router)
app.include_router(service.router)
app.include_router(project.router)