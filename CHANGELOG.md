# Changelog

All notable changes to pydico will be documented in this file.

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
and released versions use the `vMAJOR.MINOR.PATCH` Git tag format.

<!-- version list -->

## v0.1.0 (2026-09-30)

### Bug Fixes

- Added missing raise to error & improved None check safety
  ([`a2111c7`](https://github.com/root/pydico/commit/a2111c73a78ba68ff653cf52a86bc5116d5986af))

- Update Git installation steps to include CA certificates and configure SSL
  ([`16295ea`](https://github.com/root/pydico/commit/16295ea7eb471b3d4c7a05f2e057907b48ab16c2))

### Features

- Add examples for FastAPI, Click CLI, and Discord bot integrations; enhance documentation and
  structure
  ([`196b8e8`](https://github.com/root/pydico/commit/196b8e8779506f39c161367a143900fc6fc23f7a))

- Added overload to functions get, add_transient, add_singleton & improved test coverage
  ([`48498d8`](https://github.com/root/pydico/commit/48498d871699b99e9e356e45bcb8531303e36d60))

- Complete standard collection injection and validation
  ([`7b8910c`](https://github.com/root/pydico/commit/7b8910cfa599a1dd4e770111a960c752e55ace1a))

- Enhance documentation, implement function injection, and add context management for resolvers
  ([`09f09e0`](https://github.com/root/pydico/commit/09f09e01119dcb7b1ea19d9d0af3f5208e5b8255))

- Enhance documentation, implement resource lifecycle management, and add disposal error handling
  ([`05ae310`](https://github.com/root/pydico/commit/05ae310f4ce21a637b9129c06108aad736b5031b))

- Enhance service collection and provider with thread safety and circular dependency detection
  ([`71b3732`](https://github.com/root/pydico/commit/71b3732439ac780059eddb5cf7c97eb45eb023e8))

- Enhanced error handling and added comprehensive type hints
  ([`4db00be`](https://github.com/root/pydico/commit/4db00be2648cf1c5955e7512a144a87eb5074282))

- Implement keyed injection support with InjectKey metadata and enhance dependency resolution
  ([`a05feee`](https://github.com/root/pydico/commit/a05feeefa75351d130b1cba0a2e206a6286ae3af))

- Implement scoped service lifetime and enhance service resolution context
  ([`a4a908a`](https://github.com/root/pydico/commit/a4a908ac55fab2886cecd1a0aedf0c3d74e38d71))

- Implement structured error model and enhance exception handling
  ([`0df624e`](https://github.com/root/pydico/commit/0df624e2a528b85d8b34ec7820a1823ce781064b))

- Stabilize lifecycle management, enhance error handling, and improve documentation
  ([`48161fd`](https://github.com/root/pydico/commit/48161fdd2e58de1cb0543aeb9b2f8f695ce31a18))

- Update public API exports, enhance README, and refactor context handling
  ([`c5e487f`](https://github.com/root/pydico/commit/c5e487fd34b64cc54f986cdf0c967713d1da1e8b))

### Refactoring

- Remove ROADMAP and TODO files; implement async lifecycle management
  ([`105f338`](https://github.com/root/pydico/commit/105f338b963c1659dcfca73b9e56c1c6baa52700))
