# Append (don't replace) into .husky/pre-commit.
# Assumes the file already runs tsc via husky, per money-disk's
# pre-Wave-1 state. If a future project has no husky yet, this
# whole flag needs a "write from scratch" branch — not built.

npx lint-staged
