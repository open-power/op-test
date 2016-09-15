*** Settings ***
Documentation     This module is a common connection clients for
...               open power systems

Library           SSHLibrary   30s
Library           OperatingSystem


*** Variables ***

*** Keywords ***
Open Connection And Log In
    Open connection     ${OPENPOWER_HOST}
    Login   ${OPENPOWER_USERNAME}    ${OPENPOWER_PASSWORD}

Open OS Connection And Log In
    Open connection     ${OPENPOWER_OS}
    Login   ${OS_USERNAME}    ${OS_PASSWORD}
