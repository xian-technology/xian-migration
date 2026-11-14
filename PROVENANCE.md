# Source provenance

Extracted from `xian-technology/xian-abci` at commit
`2e5bb132c9cceaccfba7015771a40a727500a788` (2026-10-30).

- Original migration feature: PR #36, commit `0bb8ed9`, by Benji
  (`75325191+duelingbenjos@users.noreply.github.com`).
- Storage-identity and timestamp repairs: `828b139`, by Endogen.
- Integration with current core fixes: `2e5bb13`.

The initial import preserves the repaired source, tests and migration guide.
Subsequent extraction changes move modules into `xian_migration`, replace
private genesis imports with public APIs, and make runtime inputs explicit.
The upstream code was Apache-2.0 at extraction; the project owner has since
relicensed both `xian-abci` and this repository under MIT (see `LICENSE`). No
live exports, keys or chain state are included. This repository retains the
migration implementation after the temporary ABCI branch is removed.
