from invoke import task



@task
def parse(c, file):
    c.run(f".venv\\Scripts\\python cli.py parse data/samples/{file}", encoding="utf-8")

@task
def test(c):
    c.run(".venv\\Scripts\\python -m pytest tests/ -v")

@task
def extract(c, file):
    c.run(f".venv\\Scripts\\python cli.py extract-raw data/samples/{file}", encoding="utf-8")