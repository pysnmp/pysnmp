#!/usr/bin/env sh

set -e

PYTHON=${1:-python}

# Run the pytest suite first so test failures fail the script early.
echo "Running pytest suite..."
$PYTHON -m pytest tests/

echo "Running example smoke tests..."
for x in examples/hlapi/asyncio/manager/cmdgen/*.py \
         examples/hlapi/asyncio/agent/ntforg/*.py \
         examples/v3arch/asyncio/manager/cmdgen/*.py \
         examples/v3arch/asyncio/agent/ntforg/*.py \
         examples/smi/manager/*py \
         examples/smi/agent/*.py
do
    case "${x}" in
    *spoof*|*ipv6*)
        echo "skipping ${x}"
        continue
        ;;
    *)
        $PYTHON "${x}" | tail -50
        ;;
    esac
done
