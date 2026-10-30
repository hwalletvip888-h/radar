#!/bin/bash
C=/root/.foundry/bin/cast
RPC=https://rpc.xlayer.tech
IMPL=0x5ebf29b80789e548907c707530c3c7607c4347df

$C code $IMPL --rpc-url $RPC 2>/dev/null > /tmp/bind2.bin

echo "=== 候选函数名，逐个测是否在 impl 里 ==="
for sig in \
  "bind(string,address,uint256)" "bind(string,address)" "register(string,address,uint256)" \
  "activate(string,address,uint256)" "bindName(string,address,uint256)" "setName(string,address,uint256)" \
  "pay(string,address,uint256)" "assign(string,address,uint256)" "claimName(string,address,uint256)" \
  "reserve(string,address,uint256)" "open(string,address,uint256)" "registerName(string,address,uint256)" \
  "bind(string,uint256,address)" "bind(uint256,address,uint256)" "bind(address,string,uint256)" \
  "renew(string,uint256)" "extend(string,uint256)" "setBinding(string,address,uint256)" \
  "update(string,address,uint256)" "configure(string,address,uint256)" "setup(string,address,uint256)"; do
  sel=$($C keccak "$sig" 2>/dev/null | cut -c1-10)
  selhex=${sel#0x}
  if grep -q "$selhex" /tmp/bind2.bin; then
    echo "✅ HIT: $sel  $sig"
  else
    echo "   miss: $sel  $sig"
  fi
done
