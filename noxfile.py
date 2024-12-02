import nox

toml = nox.project.load_toml("pyproject.toml")
deps = toml['project']["dependencies"] + toml['dependency-groups']["test"]

@nox.session
def test(session):
    session.install(*deps)
    session.run(*'pytest --ignore=test_kivy.py --doctest-modules'.split() + session.posargs)

@nox.session
def kivy(session):
    # session.install('kivy', 'ipdb', *deps)
    session.install('kivy', *deps)
    session.run('pytest', *session.posargs)
