import sys

FORMAT = '''# MLAppDeploy Dockerfile
FROM {BASE}
MAINTAINER {MAINTAINER}

# Environments
{ENVS}

# Working directory
WORKDIR /workspace

# Pre Scripts
{PREPS}

# Copy projects
COPY . .

#Post Scripts
RUN {SCRIPT}

# Entrypoint
CMD {COMMAND}

'''

sys.modules[__name__] = FORMAT
