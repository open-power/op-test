*** Settings ***
Documentation           This module is for executing ipmitool commands.

Resource                ../lib/resource.txt

Library                 SSHLibrary
Library                 OperatingSystem

*** Variables ***

${IPMI_CMD}       ipmitool -H ${OPENPOWER_HOST} -I lanplus -U ${OPENPOWER_USERNAME} -P ${OPENPOWER_PASSWORD}

*** Keywords ***

Run IPMI Raw Command
    [arguments]    ${args}
    ${ipmi_cmd}=   Catenate  SEPARATOR=    ${IPMI_CMD} raw ${args}
    Log To Console     \n Execute: ${ipmi_cmd}
    ${rc}    ${output}=    Run and Return RC and Output   ${ipmi_cmd}
    Sleep   5sec
    [return]    ${output}

Run IPMI Standard Command
    [arguments]    ${args}
    ${ipmi_cmd}=   Catenate  SEPARATOR=    ${IPMI_CMD}${SPACE}${args}
    Log To Console     \n Execute: ${ipmi_cmd}
    ${rc}    ${output}=    Run and Return RC and Output   ${ipmi_cmd}
    Log To Console     ${rc}
    Sleep   5sec
    [return]   ${output}
