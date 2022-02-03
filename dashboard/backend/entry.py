from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from mlad.app import app as mlad_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.mount('/mlad', mlad_app, name='mlad')
app.mount('/', StaticFiles(directory='static', html=True), name='static')


if __name__ == '__main__':
    uvicorn.run(app, debug=True, host='0.0.0.0', port=2022)