# Click CLI example

Click owns argument parsing and command execution. The application provider is
stored in Click's application state, and every command creates an isolated
pydico scope.

Install Click and run the commands from the repository root:

```shell
python -m pip install click
python -m examples.click_cli.main users
python -m examples.click_cli.main users --all
python -m examples.click_cli.main deactivate 2
```
