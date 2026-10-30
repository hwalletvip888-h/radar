#!/bin/bash
C=/root/.foundry/bin/cast
RPC=https://rpc.xlayer.tech
ADDR=0x5aa63697bebb6a104dced00ce77fa4574aab1379
echo "=== X Layer OKB balance ==="
$C balance $ADDR --rpc-url $RPC 2>&1
echo "=== X Layer BEM balance ==="
$C call 0x60e62Efa9405d6873C5deaBD4E6CC91c25363952 "balanceOf(address)(uint256)" $ADDR --rpc-url $RPC 2>&1
