global dependencies_installed


def set_dependency_installed_flag(flag: bool):
    global dependencies_installed
    dependencies_installed = flag


def are_dependencies_installed() -> bool:
    global dependencies_installed
    return dependencies_installed
