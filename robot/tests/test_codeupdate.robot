*** Settings ***
Documentation           This suite will test BMC and PNOR update using ipmitool.

Resource                ../lib/ipmi_client.robot
Resource                ../lib/utils.robot
Resource                ../lib/connection_client.robot

Suite Setup             Open Connection And Log In
Suite Teardown          Close All Connections

Test Setup              Pre Test Execution Setup
Test Teardown           Expected Result verification

*** Variables ***
${PNOR}                  component 2
${BMC}                   component 1
${SUFFIX}                -z 30000 force <<< y

*** Test Cases ***

Update BMC and PNOR
   [Documentation]   Update BMC and PNOR using IPMITool

   Check If Image Exist   ${IMG_PATH}

   Put Power Off State

   Sleep   60sec
   Preserve Network Settings

   ${hpm_cmd}=  Catenate  SEPARATOR=    ${HPM_UPDATE}${SPACE}${IMG_PATH}${SPACE}${SUFFIX}
   ${status}=  Run IPMI Standard Command    ${hpm_cmd}
   Should Contain    ${status}   Firmware upgrade procedure successful

   Sleep   30sec
   log to console    Waiting for system to pingable
   Wait For Host To Ping   ${OPENPOWER_HOST}
   log to console    System pinging now

   Put Power On State

   Wait for OS

Update BMC
   [Documentation]   Update BMC using IPMITool

   Check If Image Exist   ${IMG_PATH}

   Put Power Off State
   Sleep   60sec

   Preserve Network Settings

   ${hpm_cmd}=  Catenate  SEPARATOR=    ${HPM_UPDATE}${SPACE}${IMG_PATH}${SPACE}${SUFFIX}
   ${status}=  Run IPMI Standard Command    ${hpm_cmd}
   Should Contain    ${status}   Firmware upgrade procedure successful

   Sleep   30sec
   log to console    Waiting for system to pingable
   Wait For Host To Ping   ${OPENPOWER_HOST}
   log to console    System pinging now

   Put Power On State

   Wait for OS

*** Keywords ***

Check If Image Exist
   [Documentation]   Check if the given image exist
   [Arguments]       ${arg}
   OperatingSystem.File Should Exist    ${arg}   msg=File ${arg} doesn't exist..

Preserve Network Settings
   [Documentation]  Network setting is preserved
   Log To Console   \n Preserve Network Settings
   ${status}=    Run IPMI Standard Command    ${BMC_PRESRV_LAN}
   Should not contain   ${status}   Unable to establish LAN session

