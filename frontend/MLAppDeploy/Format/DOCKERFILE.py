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
#RUN apt install -y hello
#COPY requirements.txt 
#RUN pip install -r requirements.txt

# Copy projects
COPY . .

# Entrypoint
ENTRYPOINT  [{ENTRYPOINT}]
CMD         [{CMD}]

'''

sys.modules[__name__] = FORMAT
