import os
import time
import json

from typing import Optional, Dict, List

from mlad.core.kubernetes import controller as ctlr


def _find_target_app_spec(target_app_name: str, app_specs: List[Dict]) -> Optional[Dict]:
    for app_spec in app_specs:
        if app_spec['name'] == target_app_name:
            return app_spec
    return None


def _check_condition(target_app_spec: Dict, target_condition: str) -> bool:
    pod_specs = target_app_spec['tasks'].values()
    if target_condition == 'Succeeded':
        return all([spec['phase'] == target_condition for spec in pod_specs])
    elif target_condition == 'Running':
        return all([spec['phase'] in ['Succeeded', 'Running'] for spec in pod_specs])
    else:
        print(f'Wrong target condition: {target_condition}')
        return False


if __name__ == '__main__':
    project_key = os.environ['PROJECT_KEY']
    dependency_specs = json.loads(os.environ['DEPENDENCY_SPECS'])
    while True:
        apps = ctlr.get_apps(project_key)
        app_specs = [ctlr.inspect_app(app) for app in apps]
        satisfied_count = 0
        for dependency_spec in dependency_specs:
            target_app_name = dependency_spec['appName']
            target_condition = dependency_spec['condition']
            target_app_spec = _find_target_app_spec(target_app_name, app_specs)
            if target_app_spec is None:
                print(f'Cannot find the target app name to check the dependency: {target_app_name}')
                continue
            if _check_condition(target_app_spec, target_condition):
                satisfied_count += 1
        if satisfied_count == len(dependency_specs):
            break
        time.sleep(3)
