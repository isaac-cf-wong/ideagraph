# claimkit → ideagraph

**`claimkit` has been renamed to
[`ideagraph`](https://pypi.org/project/ideagraph/).**

This `claimkit` distribution is a **compatibility shim**. Installing it pulls in
`ideagraph`, and importing `claimkit` (or any `claimkit.*` submodule) returns
the matching `ideagraph` module while emitting a `DeprecationWarning`. It will
not be updated.

Please migrate:

```bash
pip uninstall claimkit
pip install ideagraph
```

and change `import claimkit` → `import ideagraph`.
