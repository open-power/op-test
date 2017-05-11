*** Settings ***
Documentation		This suite will verifiy basic ipmitool related test
...                     cases. It includes test case for testing power on/off,
...                     reset, sol etc.

Resource                ../lib/ipmi_client.robot
Resource                ../lib/utils.robot
Resource                ../lib/connection_client.robot

Suite Setup             Open Connection And Log In
Suite Teardown          Close All Connections

Test Setup              Pre Test Execution Setup
Test Teardown           Expected Result verification


*** Variables ***


*** Test Cases ***                                

Restart_using_NMI
    [Documentation]   Restart using NMI

    Log To Console       \n Triggering NMI
    Run IPMI Standard Command    power diag
    Sleep   60sec

    Wait for OS


Multiple times Activate and Deactivate SOL
    [Documentation]   Continous IPMItool command to BMC
    : FOR    ${count}    IN RANGE    0    15
    \    Log To Console  \n [ *** IPMItool command count: ${count} *** ]
    \    Run IPMI Standard Command    sol deactivate
    \
    \    ${resp}=    Run IPMI Standard Command    sol activate &
    \    Log To Console    ${resp}
    \    Should Contain    ${resp}    SOL Session operational


Continous IPMItool command to BMC
    [Documentation]   Continous IPMItool command to BMC
    : FOR    ${count}    IN RANGE    0    15
    \    Log To Console  \n [ *** IPMItool command count: ${count} *** ]
    \    ${resp}=    Run IPMI Standard Command    sol info
    \    Should Contain    ${resp}    Set in progress


Multiple Power OFF and ON
    [Documentation]   Multiple iteration of power off and on
    : FOR    ${count}    IN RANGE    0    15
    \    Log To Console  \n [ *** Power OFF and ON count: ${count} *** ]
    \    Log To Console       \n Powering OFF System
    \    Initiate Power Off
    \
    \    Log To Console       \n Powering ON System
    \    Initiate Power On
    \
    \    Log To Console       \n Wait for OS to come online
    \    Wait for OS
    \    Log To Console       \n Partition now online


Multiple CEC Reset
    [Documentation]   Multiple iteration of CEC reset

    : FOR    ${count}    IN RANGE    0    15
    \    Log To Console  \n [ *** CEC Reset count: ${count} *** ] \n
    \    CEC Reset


Multiple BMC Reset
    [Documentation]   Multiple iteration of BMC reset

    : FOR    ${count}    IN RANGE    0    15
    \    Log To Console  \n [ *** BMC Reset count: ${count} *** ] \n
    \    BMC Reset


***keywords***

BMC Reset
    [Documentation]   Reset BMC using ipmitool

    Log To Console       \n Reseting BMC....
    ${resp}=    Run IPMI Standard Command    power reset
    Should Be Equal    ${resp}    Chassis Power Control: Reset

    log to console    Waiting for system to pingable
    Wait For Host To Ping   ${OPENPOWER_HOST}
    log to console    System pinging now

    Log To Console       \n Wait for OS to come online
    Wait For Host To Ping    ${OS_HOST}   15min
    Log To Console       \n partition now online

CEC Reset
    [Documentation]   Reset CEC using ipmitool

    Log To Console       \n Reseting CEC....
    ${resp}=    Run IPMI Standard Command    power cycle
    Should Be Equal    ${resp}    Chassis Power Control: Cycle

    Log To Console       \n Wait for OS to come online
    Wait For Host To Ping    ${OS_HOST}   15min
    Log To Console       \n partition now online
