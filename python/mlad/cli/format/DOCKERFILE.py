import sys

FORMAT = '''
FROM {BASE}
MAINTAINER {MAINTAINER}

{ENVS}

WORKDIR /workspace

{PREPS}

COPY . .

{SCRIPT}

{COMMAND}
'''

sys.modules[__name__] = FORMAT
