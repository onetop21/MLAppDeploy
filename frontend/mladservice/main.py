from fastapi import FastAPI, Depends, Header
from fastapi.logger import logger
from fastapi import FastAPI, Depends
from mladservice.routers import image, service, project, node, auth
from mladservice.auth import Authorization
from mladcli.libs.auth import generate_admin_token

APIV1 = '/api/v1'

def create_app():
    app = FastAPI()

    user = Authorization('user')
    admin = Authorization('admin')

    #app.include_router(image.router, prefix=APIV1)
    app.include_router(node.router,prefix=APIV1,
                       dependencies=[Depends(admin.verify_auth)])
    app.include_router(service.router, prefix=APIV1)
    app.include_router(project.router, prefix=APIV1,
                       dependencies=[Depends(user.verify_auth)])
    app.include_router(auth.router, prefix=APIV1,
                       dependencies=[Depends(admin.verify_auth)])
        
    print(f"Admin Token : {generate_admin_token().decode()}")

    return app

app = create_app()

if __name__ == '__main__':
    '''
    For Debugging
    '''
    import uvicorn
    uvicorn.run(app, host='0.0.0.0')
