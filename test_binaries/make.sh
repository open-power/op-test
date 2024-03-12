#!/bin/bash
nproc=`nproc`
yes "" | make oldconfig /dev/null 2>&1
make -j$nproc -S vmlinux > /dev/null 2>&1
# make modules && make install 2>&1 