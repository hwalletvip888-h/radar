#!/bin/bash
C=/root/.foundry/bin/cast
RPC=https://rpc.xlayer.tech
BIND=0x68809fd2fb343aa57d0aeb7f33defe477c9666f9
IMPL=0x5ebf29b80789e548907c707530c3c7607c4347df

echo "=== DomainBinding impl code size ==="
$C code $IMPL --rpc-url $RPC 2>/dev/null | tr -d '\n' | wc -c

echo "=== impl selectors ==="
$C code $IMPL --rpc-url $RPC 2>/dev/null > /tmp/bind.bin
grep -oE '63[0-9a-f]{8}' /tmp/bind.bin | sort | uniq -c | sort -rn | head -30

echo "=== candidate bind selectors ==="
for sig in \
  "bind(string,address,uint256)" "bind(string,address)" "bind(bytes32,address,uint256)" \
  "bind(string,address,uint256,uint256)" "activate(string,address,uint256)" "register(string,address,uint256)" \
  "bind(string,address,uint256,bytes)" "monthlyFee()" "isActive(string)" "activation(string)"; do
  sel=$($C keccak "$sig" 2>/dev/null | cut -c1-10)
  echo "$sel  $sig"
done

echo "=== monthlyFee() ==="
$C call $BIND "monthlyFee()(uint256)" --rpc-url $RPC 2>&1 | head -1
