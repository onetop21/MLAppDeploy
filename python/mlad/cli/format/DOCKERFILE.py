import sys

FORMAT = '''
FROM {BASE}
MAINTAINER {MAINTAINER}

{ENVS}

WORKDIR /workspace

{PREPS}

COPY . .

RUN {SCRIPT}

CMD {COMMAND}
'''

sys.modules[__name__] = FORMAT
