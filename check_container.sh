#!/bin/bash
C=/root/.foundry/bin/cast
RPC=https://rpc.xlayer.tech
CONTAINER=0xd09abd74ca548c7a0de26e20125f35605ff35517
# 处理器 #4 需要地址，先用容器查；RTX 处理器地址从 id 页面拿不到，先查容器本体

echo "=== container code size (有 code = 已开通) ==="
$C code $CONTAINER --rpc-url $RPC 2>/dev/null | tr -d '\n' | wc -c

echo "=== container OKB balance ==="
$C balance $CONTAINER --rpc-url $RPC 2>&1

echo "=== container nonce ==="
$C rpc eth_getTransactionCount $CONTAINER latest --rpc-url $RPC 2>&1
