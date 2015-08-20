# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/opCIConfigure.py $
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
import argparse
import ConfigParser

parser = argparse.ArgumentParser(
        description='This script writes the opCItools module configuration\
                file with the path and filename of the PNOR image')

parser.add_argument(
        'pnorPath', metavar='pnorPath', type=str,
        nargs='+', help='Path to the PNOR image')
parser.add_argument(
        'pnorFilename', metavar='pnorFilename', type=str,
        nargs='+', help='File name of the PNOR image')

args = parser.parse_args()

print args.pnorPath[0] + args.pnorFilename[0]
config = ConfigParser.RawConfigParser()
config.readfp(open('op_ci_tools.cfg'))
config.set('test', 'imagedir', args.pnorPath[0])
config.set('test', 'imagename', args.pnorFilename[0])
with open('op_ci_tools.cfg', 'w') as configfile:
    config.write(configfile)
