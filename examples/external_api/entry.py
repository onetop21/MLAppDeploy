from mlad.api import API

if __name__ == '__main__':
    projects = API.project.get()
    print(projects)
