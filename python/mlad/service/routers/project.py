from typing import List
import docker
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import project
from mlad.service.exception import InvalidProjectError
from mlad.core.docker import controller as ctlr
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/project")
def project_create(req: project.CreateRequest,allow_reuse:bool = Query(False)):
    cli = ctlr.get_docker_client()
    #workspace = 
    # f"{socket.gethostname()}:{os.getcwd()}/mlad-project.yml"
    workspace = req.workspace
    username = req.username
    base_labels = ctlr.make_base_labels(
        workspace, username, dict(req.project))
    try:
        gen = ctlr.create_project_network(
            cli, base_labels, swarm=True, allow_reuse=allow_reuse)          
        for _ in gen:
            if 'stream' in _:
                print(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    network = _['output']
                else:
                    print(_['stream'])
                break
    except TypeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ctlr.inspect_project_network(network)

@router.get("/project")
def projects():
    cli = ctlr.get_docker_client()
    try:
        networks = ctlr.get_project_networks(cli)
        projects = [ ctlr.inspect_project_network(v) for k, v in networks.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return projects


@router.get("/project/{project_id}")
def project_inspect(project_id:str):
    cli = ctlr.get_docker_client()
    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)
        inspect = ctlr.inspect_project_network(network)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspect

@router.delete("/project/{project_id}")
def project_remove(project_id:str):
    cli = ctlr.get_docker_client()
    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)
        for _ in ctlr.remove_project_network(cli, network):
            if 'stream' in _:
                print(_['stream'])
            if 'status' in _:
                if _['status'] == 'succeed':
                    print('Network removed')
                break
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message': f'project {project_id} removed'}


# @router.get("/project/{project_id}/logs")
# def project_log(project_id: str, tail:str = Query('all'),
#                 follow: bool = Query(False),
#                 timestamps: bool = Query(False),
#                 names_or_ids: list = Query(None)):
#     cli = ctlr.get_docker_client()

#     network = ctlr.get_project_network(cli, project_id=project_id)
#     if not network:
#         raise InvalidProjectError(project_id)

#     key = ctlr.inspect_project_network(network)['key']
#     key = str(key).replace('-','')

#     colorkey = {}
#     for _ in ctlr.get_project_logs(cli, key, tail, follow, timestamps, names_or_ids):
#         print(_)
#         #_print_log(_, colorkey, 32, ctlr.SHORT_LEN)
#     return {}
#     #logs = ctlr.get_project_logs(cli, key, 
#     #    tail='all', follow=False, timestamps=False, names_or_ids=[])
#     # for _ in ctlr.get_project_logs(cli, key, 
#     #     tail='all', follow=False, timestamps=False, filters=[]):
#     #     if _: print_log(_, name_width, colorkey)
#     # async def get_logs(gen):
#     #     for _ in gen:
#     #         if not _: return
#     #         name = f"{_['name']}.{_['task_id']}" if 'task_id' in _ else _['name']
#     #         msg = _['stream'].decode()
#     #         log = f'{name}:{msg}'
#     #         yield log.encode()
#     #return StreamingResponse(get_logs(logs))

# import sys, itertools

# # for Log Coloring
# NoColor = '\x1b[0m'
# ErrColor = '\x1b[1;31;40m'
# Colors = []
# for bg in range(40, 48):
#     for fg in range(30, 38):
#         if fg % 10 == 1: continue # Remove Red Foreground
#         if fg % 10 == bg % 10: continue
#         color = ';'.join(['1', str(fg), str(bg)])
#         Colors.append(f'\x1b[{color}m')

# _counter = itertools.count()
# def color_index():
#     return next(_counter) % len(Colors)

# def _print_log(log, colorkey, max_name_width=32, len_short_id=10):
#     name = log['name']
#     namewidth = min(max_name_width, log['name_width'])
#     if 'task_id' in log:
#         name = f"{name}.{log['task_id'][:len_short_id]}"
#         namewidth = min(max_name_width, namewidth + len_short_id + 1)
#     msg = log['stream'].decode()
#     timestamp = log['timestamp'].strftime("[%Y-%m-%d %H:%M:%S.%f]") if 'timestamp' in log else None
#     if msg.startswith('Error'):
#         sys.stderr.write(f'{utils.ERROR_COLOR}{msg}{utils.CLEAR_COLOR}')
#     else:
#         colorkey[name] = colorkey[name] if name in colorkey else utils.color_table()[utils.color_index()]
#         if timestamp:
#             sys.stdout.write(("{}{:%d}{} {} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, timestamp, msg))
#         else:
#             sys.stdout.write(("{}{:%d}{} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, msg))
