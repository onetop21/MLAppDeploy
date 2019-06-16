import sys

FORMAT='''# MLAppDeploy Dockerfile
FROM {BASE}
MAINTAINER {AUTHOR}

# Environments
{ENVS}

# Working directory
WORKDIR /workspace

# Dependencies
{DEPENDS}

# Copy projects
COPY . .

# Entrypoint
ENTRYPOINT  {ENTRYPOINT}
CMD         {ARGS}

'''

sys.modules[__name__] = FORMAT
