import os
import json
import asyncio
import inspect
import aiohttp

from typing import Callable
from collections import defaultdict

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from .model import ComponentDeleteRequestModel, ComponentPostRequestModel
from .db import DBClient

# os.environ['MLAD_ADDRESS'] = 'http://172.20.41.35:30547/beta'
# os.environ['MLAD_ADDRESS'] = 'http://172.20.41.35:8441'
# os.environ['MLAD_SESSION'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiam9vb25ob2UiLCJob3N0bmFtZSI6Impvb29uaG9lLU1TLTdCMjMiLCJ1dWlkIjoiYzY3ZDAzYzUtODQ1Mi00ZTliLWI4ZGUtYTg2NmQ5ZTBlNWRjIn0.DWj8Y_xQO6167rRyBgYrNVVaHzq6xDIqCNp458HkKsc'

app = FastAPI()
address = f'{os.environ["MLAD_ADDRESS"]}/api/v1'
headers = {
    'session': os.environ['MLAD_SESSION'],
    'version': '0.4.1'
}
db_client = DBClient()


async def _request_resources(key: str, session: aiohttp.ClientSession, group_by: str = 'project'):
    async with session.get(f'{address}/project/{key}/resource',
                           headers=headers, params={'group_by': group_by}) as resp:
        resp.raise_for_status()
        return await resp.json()


# dashbaord의 node tab에서 보여줄 정보 반환하는 함수
async def request_nodes(_, session: aiohttp.ClientSession):
    ret = []
    nodes = []
    async with session.get(f'{address}/node/list', headers=headers) as resp:
        resp.raise_for_status()
        nodes = await resp.json()

    resource_dict = defaultdict(lambda: {})
    async with session.get(f'{address}/node/resource', headers=headers) as resp:
        resp.raise_for_status()
        resource_dict = await resp.json()
    for node in nodes:
        name = node['hostname']
        ret.append({
            **node,
            'metrics': [{
                'type': k,
                'capacity': v['capacity'],
                'used': v['used'],
                'free': v['allocatable']
            } for k, v in resource_dict[name].items()]
        })
    return ret


# dashboard에서 project tab에서 보여주는 project 목록 정보를 반환하는 함수
async def request_projects(_, session: aiohttp.ClientSession):
    ret = []
    projects = []
    async with session.get(f'{address}/project', headers=headers) as resp:
        resp.raise_for_status()
        projects = await resp.json()

    async def fetch_apps(project):
        async with session.get(f'{address}/project/{project["key"]}/app', headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    apps_list = await asyncio.gather(*[fetch_apps(project) for project in projects])
    resource_res_coroutines = [
        _request_resources(project["key"], session)
        for project in projects
    ]
    resource_responses = await asyncio.gather(*resource_res_coroutines)
    for i, project in enumerate(projects):
        key = project['key']
        username = project['username']
        name = project['project']
        image = project['image']
        n_apps = 0
        n_replicas = 0
        n_tasks = 0
        hostname = project['workspace']['hostname']
        workspace = project['workspace']['path']
        apps = apps_list[i]
        for spec in apps['specs']:
            tasks = spec['task_dict'].values()
            statuses = [task['status'] for task in tasks]
            n_apps += 1
            n_replicas += spec['replicas']
            n_tasks += statuses.count('Running')

        resource_dict = resource_responses[i]
        ret.append({
            'key': key, 'username': username, 'name': name, 'image': image,
            'n_apps': n_apps, 'n_replicas': n_replicas, 'n_tasks': n_tasks,
            'hostname': hostname, 'workspace': workspace,
            **resource_dict
        })
    return ret


def get_components(_):
    return db_client.get_components()


# project tab에서 project detail 화면을 보여주기 위한 함수
async def request_project_detail(data: str, session: aiohttp.ClientSession):
    data = json.loads(data)
    if len(data) == 0:
        return {}
    key = data['key']
    ret = {}
    async with session.get(f'{address}/project/{key}', headers=headers) as resp:
        resp.raise_for_status()
        ret = await resp.json()
    total_resource_dict = await _request_resources(key, session)
    resource_detail_dict = await _request_resources(key, session, group_by='app')
    ret = {**ret, **total_resource_dict}

    specs = []
    async with session.get(f'{address}/project/{key}/app', headers=headers) as resp:
        resp.raise_for_status()
        apps = await resp.json()
        specs = apps['specs']
        for i, spec in enumerate(specs):
            specs[i] = {**specs[i], 'resources': resource_detail_dict[spec['name']]}

    ret = {**ret, 'apps': specs}
    return ret


@app.post('/component')
def run_components(req: ComponentPostRequestModel):
    db_client.run_component(req.components)
    return {
        'message': 'Successfully run components'
    }


@app.delete('/component')
def delete_components(req: ComponentDeleteRequestModel):
    db_client.delete_component(req.name)
    return {
        'message': f'Successfully delete component [{req.name}]'
    }


async def handle_message(websocket: WebSocket, request_func: Callable):
    await websocket.accept()
    while True:
        async with aiohttp.ClientSession() as session:
            try:
                data = await websocket.receive_text()
                if inspect.iscoroutinefunction(request_func):
                    ret = await request_func(data, session)
                else:
                    loop = asyncio.get_event_loop()
                    ret = await loop.run_in_executor(None, request_func, data)
                await websocket.send_json({'status_code': 200, 'data': ret})
            except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError, RuntimeError):
                pass
            except Exception as e:
                await websocket.send_json({'status_code': 500, 'message': str(e)})


@app.websocket('/nodes')
async def send_nodes(websocket: WebSocket):
    await handle_message(websocket, request_nodes)


@app.websocket('/components')
async def send_components(websocket: WebSocket):
    await handle_message(websocket, get_components)


@app.websocket('/projects')
async def send_projects(websocket: WebSocket):
    await handle_message(websocket, request_projects)


@app.websocket('/project')
async def send_project_detail(websocket: WebSocket):
    await handle_message(websocket, request_project_detail)
