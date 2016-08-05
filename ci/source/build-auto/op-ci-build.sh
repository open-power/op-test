#!/bin/bash -u
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/build-auto/op-ci-build.sh $
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
#set -x
# A somewhat custom script that the hostboot dev team uses to run open power CI
# against all code commits.  Could be modified for others uses if wanted.
# parameters
# GIT_URL='ssh://<git/gerrit repo>'
# GERRIT_REFSPEC='refs/changes/06/17006/2'

# Create build dirs and setup environment.  All paths are relative to workspace
rm -rf build
mkdir -p build/hostboot
mkdir -p build/op-build
mkdir -p build/test_data
mkdir -p build/test_data/preserved_patches
mkdir -p build/test_data/dismissed_patches

HOSTBOOT_REPO=$PWD/build/hostboot
OPBUILD_REPO=$PWD/build/op-build
TEST_DIR=$PWD/build/test_data
HB_PATCH_DIR=$OPBUILD_REPO/openpower/package/hostboot
HOSTBOOT_MK=$HB_PATCH_DIR/hostboot.mk

echo "HOSTBOOT_REPO: $HOSTBOOT_REPO"
echo "HB_PATCH_DIR: $HB_PATCH_DIR"
echo "OPBUILD_REPO: $OPBUILD_REPO"
echo "TEST_DIR: $TEST_DIR"
echo "GIT_URL: $GIT_URL"
echo "GERRIT_REFSPEC: $GERRIT_REFSPEC"
echo "GERRIT_BRANCH: $GERRIT_BRANCH"

# Only Master branch is supported
if [ $GERRIT_BRANCH != "master" ]; then
    echo "Fatal. op-build ci only runs on changes pushed to master branch. \
        $GERRIT_BRANCH branch is not supported."
    exit 1
fi

#
# Setup local hostboot and op-build repos
#
cd $HOSTBOOT_REPO
git init
git fetch $GIT_URL $GERRIT_REFSPEC && git checkout FETCH_HEAD
if [ $? -ne 0 ]; then
    echo "Fatal. Could not fetch change from gerrit"
    exit 1
fi

cd $OPBUILD_REPO
git clone --recursive https://github.com/open-power/op-build.git . &&
git checkout master-next
if [ $? -ne 0 ]; then
    echo "Fatal. Could not check out op-build master-next branch"
    exit 1
fi

#
# Determine what patches needs to be applied.
# If the change-Id of the patch is not found in a gerrit/master commit then
# copy the patch to a 'preserved' dir, otherwise copy it to a 'dismissed' dir
#

# Obtain op-build's Hostboot package version
HB_VER=$(grep "HOSTBOOT_VERSION ?=" $HOSTBOOT_MK | cut -d' ' -f3)
echo "HOSTBOOT VERSION: $HB_VER"

cd $HOSTBOOT_REPO
for patch in $HB_PATCH_DIR/*.patch
do
#TODO need to handle the case where changeID is not present, i.e empty string
    changeID=$(grep "Change-Id:" $patch | cut -d' ' -f2)
    git log $HB_VER..HEAD | grep $changeID
    if [ $? -ne 0 ]; then
        cp $patch $TEST_DIR/preserved_patches
    else
        cp $patch $TEST_DIR/dismissed_patches
    fi
done

#
# Apply patches to hostboot test test branch
#

# Create some branches for debugging purposes
git checkout -b test_commit
git branch hb_pkg_version $HB_VER

# Apply only relevant (preserved) patches to top of test branch
git am $TEST_DIR/preserved_patches/*.patch
if [ $? -ne 0 ]; then
    echo "Current test tree:"
    git log $HB_VER..HEAD --format=format:'%h - %s - %an'|tee \
        $TEST_DIR/patch_apply_fail_git_log
    echo "Hostboot repo git ref log:"
    git reflog | tee $TEST_DIR/patch_apply_fail_git_reflog
    echo "Dismissed patches:"
    ls $TEST_DIR/dismissed_patches
    echo "Preserved patches:"
    ls $TEST_DIR/preserved_patches
    echo "Fatal. Could not apply patches cleanly."
    exit 1
fi

git log $HB_VER..HEAD --format=format:'%h - %s - %an'>\
        $TEST_DIR/patch_apply_clean_git_log

#
# Update hostboot local site and build op-build
#
cd $OPBUILD_REPO
export HOSTBOOT_VERSION=ci_build
export HOSTBOOT_SITE=$HOSTBOOT_REPO
export HOSTBOOT_SITE_METHOD=local
shopt -s expand_aliases
. op-build-env
op-build habanero_defconfig && op-build
