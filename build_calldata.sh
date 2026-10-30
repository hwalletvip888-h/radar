#!/bin/bash
C=/root/.foundry/bin/cast
echo "=== bind calldata ==="
$C calldata "bind(string,address,uint256)" "11.2.4.tape" 0xd09abd74ca548c7a0de26e20125f35605ff35517 120 2>&1
