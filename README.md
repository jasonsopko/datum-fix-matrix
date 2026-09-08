# DATUM fix matrix

Generated 2026-09-08 14:37 UTC from the live repositories by `generate.py`; the page with color is at `docs/index.html` (GitHub Pages). Bold = merged where that build comes from; plain = a PR or branch exists; missing = no fix; n/a = no gateway.

| Fix | OCEAN | innerhat | CONVOY | FlyTheElephant | MaVeTh | Lazarus |
|---|---|---|---|---|---|---|
| **Payouts: a wrong answer here pays miners short** | | | | | | |
| Full payout coinbase on BLAKE2b jobs (class 4, not the 755-byte class 2) | missing | **merged #17** | #10, #8 open | **on master** | **on master** | branch blake2b-unsplit-coinbase |
| Never pair the pool-only class 0 with a full template when the coinbaser is late | missing | missing | #13 open | missing | missing | branch late-coinbaser-convoy |
| Sigop budget on payout outputs (a big P2PKH split can exceed the block limit) | missing | missing | #10 open | missing | **on master** | n/a |
| Block weight accounted with the 164-byte header and the coinbase's real static size | missing | missing | #10 open | missing | **on master** | n/a |
| Coinbaser wait race / lost wakeup | #229 open | #19 open | #9 open | missing | missing | n/a |
| **Safety: malformed input from the pool or a miner** | | | | | | |
| Job-validation parser bounds and clz(0) guard | #236 open | #20 open | #11 open | missing | missing | n/a |
| Bound the 0x50 0x11 transaction reply to the buffer | #235 open | #18 open | #2 open | missing | missing | n/a |
| Header XOR through memcpy (undefined behavior) | missing | missing | #5 closed | missing | missing | n/a |
| **Operations: blocks and logs** | | | | | | |
| submitblock "duplicate" treated as the block being accepted | #233 open | #14 open | #3 open | **on master** | missing | branch blake2b-unsplit-coinbase |
| Log the node's JSON-RPC error instead of dropping it | missing | missing | #4 open | **on master** | missing | branch blake2b-unsplit-coinbase |
| Logger waits for its writer thread at init | #231 open | missing | #6 open | missing | missing | n/a |
| Name the client that found a block | missing | missing | #7 open | missing | missing | n/a |
| Warn about BLAKE2b misconfiguration before it costs a block | missing | #12 open | missing | missing | missing | n/a |
| Template PoW on the status page | missing | #11 open | missing | **on master** | missing | branch blake2b-unsplit-coinbase |
| BLAKE2b setup guide | missing | #10 open | missing | **on master** | missing | branch blake2b-unsplit-coinbase |
| Share prevalidation, share hash on node-check lines, log rotation | missing | #9 open | missing | **on master** | missing | branch blake2b-unsplit-coinbase |
| Smart logging by state (NoFlames) | missing | #13 open | missing | missing | missing | n/a |
| Drop the forced BIP9 bit 4 (high-hash), headline warning, mainnet address display | missing | missing | missing | missing | branch mainnet-coinbaser-ui-addr | n/a |
| **Platform** | | | | | | |
| Luke's 64-bit Prime ID, submitblock failure handling, oversized tag, jsonrpc free | missing | missing | **on master** | missing | **on master** | branch late-coinbaser-convoy |
| Wire-time fixes and macOS build (August 26 batch) | missing | **on master** | **on master** | **on master** | **on master** | branch blake2b-unsplit-coinbase |

## What people install

| Package or build | Built from | Payout coinbase fix |
|---|---|---|
| Léo Haf's StartOS package, mempool.guide registry (Retropex/datum-gateway-startos, branch pow) | `CONVOYMining/datum_gateway at 7491a50` | **present** |
| paulscode's StartOS package (paulscode/datum-blake2b-startos) | `paulscode/datum_gateway at beb9461` | missing |
| gridlabs gridpool appliance (gridlabs-science/datum-gateway-blake2b-gridpool, branch develop) | `gridlabs-science/datum-gateway-blake2b-gridpool at develop` | **present** |
| FlyTheElephant's build (master) | `FlyTheElephant1/datum_gateway at master` | **present** |

To add a fix, append an entry to `FIXES` in `generate.py`: a marker regex, a file path or a commit, plus PR numbers per repository.
