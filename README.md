## pydico
A robust dependency injection library for Python, inspired by Microsoft .NET.pydico brings the familiar patterns of the Microsoft.Extensions.DependencyInjection (IServiceProvider) ecosystem to Python. It is designed for developers who value strict typing, clean architecture, and the ergonomics of the .NET generic host pattern.

### Features
- .NET-like API: Familiar methods like ``add_transient``, ``add_singleton``, and keyed services.
- Modern Python: Built for Python 3.13+, leveraging the latest typing features (``ParamSpec``, ``Protocol``, ``Self``).
- Lifetime Management: robust support for Transient (new instance every time) and Singleton (shared instance) lifetimes.
- Type-Safe Injection: Includes an @inject decorator that works seamlessly with type checkers (MyPy/Pyright).
-Zero Dependencies: Lightweight and focused solely on DI.

### Installation
```
uv pip install pydico
# or
pip install pydico
```
### Usage
#### The C# Style Container
If you are coming from C#, you will feel right at home.
```python
from pydico import Container
from abc import ABC, abstractmethod

# 1. Define Interfaces (Protocols or ABCs)
class ILogger(ABC):
    @abstractmethod
    def log(self, msg: str): ...

# 2. Define Implementations
class ConsoleLogger(ILogger):
    def log(self, msg: str):
        print(f"[Log]: {msg}")

class Service:
    def __init__(self, logger: ILogger):
        self.logger = logger

    def run(self):
        self.logger.log("Service is running!")

# 3. Register Services (Just like Program.cs)
Container.add_singleton(ILogger, ConsoleLogger)
Container.add_transient_self(Service)

# 4. Resolve
service = Container.get(Service)
service.run()
```
#### Decorator Injection
For function-based views or handlers, pydico provides an intuitive decorator syntax similar to FastAPI or other modern frameworks, but powered by your central container.
```python
from pydico import inject, Depends

@inject
def process_request(data: dict, service: Service = Depends[Service]):
    service.run()
    print(f"Processing {data}...")
```
#### Lifetimes
- Transient: Created every time they are requested.
- Singleton: Created the first time they are requested, and then every subsequent request uses the same instance.