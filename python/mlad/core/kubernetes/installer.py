def create_docker_registry_secret(cli):
    v1_api = client.CoreV1Api(cli)
    with open(f'{Path.home()}/.docker/config.json', 'rb') as config_file:
        data = {
            '.dockerconfigjson': base64.b64encode(config_file.read()).decode()
        }
    secret = client.V1Secret(
        api_version='v1',
        data=data,
        kind='Secret',
        metadata=dict(name='docker-mlad-sc', namespace='mlad'),
        type='kubernetes.io/dockerconfigjson'
    )
    try:
        v1_api.create_namespaced_secret('mlad', secret)
    except Exception as e:
        
