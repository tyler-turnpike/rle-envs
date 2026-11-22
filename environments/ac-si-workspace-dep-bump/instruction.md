**SEC-118: move orders to fastjson 2**

Security flagged fastjson 1.x (SEC-118: the 1.x decoder can be made to allocate unbounded
memory on deeply nested input; 2.1 limits nesting depth). Our service, `orders`, in the
workspace at `/app`, still runs on 1.x. Both versions are vendored under `vendor/`, and the
2.x changes are listed at the top of `vendor/fastjson-2.1.0/fastjson/__init__.py`.

Please move orders to fastjson 2.1:

- Update orders' code for the 2.x API without changing its behaviour: amounts stay exact,
  receipts keep their current JSON format (finance diffs them), and malformed input still
  raises `OrderError`.
- Pin orders to `fastjson>=2.1,<3` in `packages/orders/pyproject.toml`.
- `./mono test orders` passes on 2.1 and `./mono check` resolves the workspace.

I'm offline from this evening, so please take it all the way through on your own, and leave
me a short summary of what you changed.
