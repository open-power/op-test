#!/bin/bash
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/fwts_execution.sh $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
# [+] International Business Machines Corp.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG
#
#  @package fwts_execution.sh

# install required packages to compile and build fwts tool
sudo apt-get install -y autoconf automake libglib2.0-dev libtool libpcre3-dev libjson* flex bison dkms libfdt-dev device-tree-compiler python-pip
if [ $? == 0 ]; then
        echo "Required packages are installed";
else
	echo "Required packages installation failed";
        exit $?;
fi

pip install pyparsing
if [ $? == 0 ]; then
        echo "python package pyparsing installed";
else
        exit $?;
fi
modprobe ipmi_devintf

WORKDIR="/tmp"
# clone FWTS source into working directroy
if [ -d $WORKDIR"/fwts" ]; then
	rm -rf $WORKDIR/fwts
fi

git clone git://kernel.ubuntu.com/hwe/fwts.git $WORKDIR/fwts
if [ $? == 0 ]; then
	echo "FWTS Source is cloned";
else
	echo "Cloning FWTS source is failed";
	exit $?;
fi

# Clone skiboot source to generate olog.json file
if [ -d $WORKDIR"/skiboot" ]; then
        rm -rf $WORKDIR"/skiboot"
fi

git clone https://github.com/open-power/skiboot $WORKDIR/skiboot
if [ $? == 0 ]; then
        echo "skiboot Source is cloned";
else
	echo "Cloning Skiboot is failed";
        exit $?;
fi

# Generate olog json file
mkdir -p /usr/local/share/fwts/
$WORKDIR/skiboot/external/fwts/generate-fwts-olog $WORKDIR/skiboot/ -o /usr/local/share/fwts/olog.json
if [ $? == 0 ]; then
        echo "Generated the olog.json file for OLOG test";
else
        echo "Generation of olog.json file from skiboot is failed";
        exit $?;
fi

cd $WORKDIR/fwts
autoreconf -ivf
./configure
if [ $? == 0 ]; then
        echo "Configuration is finished successfully";
else
	echo "Configuration is failed"
        exit $?;
fi

make
if [ $? == 0 ]; then
        echo "Compilation finished successfully";
else
	echo "Compilation is failed"
        exit $?;
fi
cd $WORKDIR/fwts/src
./fwts
if [ $? == 0 ]; then
	cat results.log
	echo "All the FWTS tests are passed";
else
	echo "one or more FWTS tests are failed"
	cat results.log
	exit $?;
fi
