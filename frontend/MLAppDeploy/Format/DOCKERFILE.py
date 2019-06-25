import sys

FORMAT='''# MLAppDeploy Dockerfile
FROM {BASE}
MAINTAINER {AUTHOR}

# Environments
{ENVS}

# Working directory
WORKDIR /workspace

# Requires
{REQUIRES}

# Copy projects
COPY . .

# Entrypoint
COMMAND {COMMAND}
CMD     {ARGS}

'''

sys.modules[__name__] = FORMAT
