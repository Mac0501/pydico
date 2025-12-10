from abc import ABC

type Interface = type[ABC]
type Dependency = type[object]
type Key = str | Interface | Dependency
