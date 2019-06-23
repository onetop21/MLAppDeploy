import sys, os
import MLAppDeploy.libs.utils as utils
import MLAppDeploy.default as default

def get_value(key, data, default='Unknown'):
        return data[key] if key in data else default
    
def set(username, host, endpoint, accesskey, secretkey, registry):
    config = default.config(utils.read_config())
    if not get_value('username', config, None) and not username:
        username = input('Username : ')
    if username: config['username'] = username
    if host: config['host'] = host
    if endpoint: config['endpoint'] = endpoint
    if accesskey: config['accesskey'] = accesskey
    if secretkey: config['secretkey'] = secretkey
    if registry: config['registry'] = registry
    # TODO
    # If change registry. Check registry server to work.
    # And Change all image repository to new registry address
    utils.write_config(config)

def get(username, host, endpoint, accesskey, secretkey, registry):
    config = utils.read_config()
    printed = False
    if username:  print(get_value('username', config)); printed = True
    if host:      print(get_value('host', config)); printed = True
    if endpoint:  print(get_value('endpoint', config)); printed = True
    if accesskey: print(get_value('accesskey', config)); printed = True
    if secretkey: print(get_value('secretkey', config)); printed = True
    if registry:  print(get_value('registry', config)); printed = True

    if not printed:
        print('Username     :', get_value('username', config))
        print('Host Address :', get_value('host', config))
        print('S3 Endpoint  :', get_value('endpoint', config))
        print('- Access Key :', get_value('accesskey', config))
        print('- Secret Key :', get_value('secretkey', config))
        print('Registry     :', get_value('registry', config))
    
utils.generate_config()
