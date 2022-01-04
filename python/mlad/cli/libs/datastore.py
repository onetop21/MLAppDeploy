# Extension for DataStore
datastores = {}


def add_datastore(kind, initializer=lambda: {}, finalizer=lambda x: x,
                  translator=lambda n, k, v: f"{n.upper()}_{k.upper()}={v or ''}", **prompt):
    datastores[kind] = {
        'prompt': prompt,
        'initializer': initializer,
        'finalizer': finalizer,
        'translator': translator
    }


def get_env(config):
    env = []
    for kind, datastore in config['datastore'].items():
        for k, v in datastore.items():
            translated = datastores[kind]['translator'](kind, k, v)
            if isinstance(translated, str):
                env.append(translated)
            else:
                env += translated
    return env
