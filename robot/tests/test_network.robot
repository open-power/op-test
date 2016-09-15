*** Settings ***
Documentation		This suite will verify network and MAC configurations
...                     of OpenPower using ipmitool

Resource                ../lib/ipmi_client.robot
Resource                ../lib/utils.robot
Resource                ../lib/connection_client.robot

Suite Setup             Open Connection And Log In
Suite Teardown          Close All Connections

Test Setup              Pre Test Execution Setup
Test Teardown           Expected Result verification

*** Variables ***
${IP_ADDREDD_INVALID}      9.3.181
${IP_ADDREDD_STRING}       aa.bb.cc.dd
${MAC_ADDREDD_VALID}       00:1a:3b:4e:5c:0a
${MAC_ADDREDD_ZERO}        00:00:00:00:00:00
${MAC_ADDREDD_INVALID}     FF:FF:FF:FF:FF:FF
${MAC_ADDREDD_SHORT}       00:1a:3b
${MAC_ADDREDD_LONG}        00:1a:3b:4e:5c:0a:0a
${ENABLE_WRITE_MAC}        0x0c 0x01 0x01 0xc2 0x00
*** Test Cases ***                                

Set Invalid IP Address
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting invalid
    ...               ip address.

    Get IP Address
    ${set_resp}=    Set IP Address     ${IP_ADDREDD_INVALID}
    Should Start With    ${set_resp}    Invalid IP address

Set Invalid IP Address using string
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting ip
    ...               address using string.

    ${set_resp}=    Set IP Address     ${IP_ADDREDD_STRING}
    Should Start With    ${set_resp}    Invalid IP address


Set Zero MAC Address
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting
    ...               zero MAC address.

    ${mac_hex}=    Convert MAC Address to Hex    ${MAC_ADDREDD_ZERO}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should End With    ${set_resp}    Invalid data field in request


Set Invalid MAC Address
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting
    ...               invalid MAC address.

    ${mac_hex}=    Convert MAC Address to Hex    ${MAC_ADDREDD_INVALID}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should End With    ${set_resp}    Invalid data field in request


Set Short MAC Address
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting
    ...               short length MAC address.

    ${mac_hex}=    Convert MAC Address to Hex    ${MAC_ADDREDD_SHORT}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should End With    ${set_resp}    Request data length invalid


Set Long MAC Address
    [Documentation]   ***BAD PATH***
    ...               This test is to verify error while setting
    ...               long length MAC address.

    ${mac_hex}=    Convert MAC Address to Hex    ${MAC_ADDREDD_LONG}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should End With    ${set_resp}    Request data length invalid


Set_Valid_MAC_Address
    [Documentation]   ***GOOD PATH***
    ...               This test case tries to set MAC address of BMC.
    ...               Later revert back its old MAC address.

    ${old_mac}=    Get MAC Address

    ${mac_hex}=    Convert MAC Address to Hex    ${MAC_ADDREDD_VALID}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should Be Empty    ${set_resp}

    log to console    Waiting for system to pingable
    Wait For Host To Ping   ${OPENPOWER_HOST}
    log to console    System pinging now

    Get MAC Address

    ${mac_hex}=    Convert MAC Address to Hex    ${old_mac}
    ${set_resp}=    Set MAC Address    ${mac_hex}
    Should Be Empty    ${set_resp}

    log to console    Waiting for system to pingable
    Wait For Host To Ping   ${OPENPOWER_HOST}
    log to console    System pinging now

    Get MAC Address


***keywords***

Set IP Address
    [Documentation]   This keyword set IP address of BMC to given address
    ...               using ipmitool.
    [Arguments]       ${address}

    ${set_address}=    Run IPMI Standard Command    lan set 1 ipaddr ${address}

    [return]    ${set_address}

Set MAC Address
    [Documentation]   This keyword set MAC address of BMC to given address
    ...               using ipmitool
    [Arguments]       ${address}

    ${enable_eth}=    Run IPMI Raw Command    ${ENABLE_WRITE_MAC}
    ${set_address}=    Run IPMI Raw Command    0x0c 0x01 0x01 0x05 ${address}

    [return]    ${set_address}

Convert MAC Address to Hex
    [Documentation]   This keyword converts MAC address to hex value
    ...               Ex. 00:1a:3b:4e:5c:0a -> 0x00 0x1a 0x3b 0x4e 0x5c 0x0a
    [Arguments]       ${address}

    ${str} =    Replace String    ${address}    :    ${SPACE}0x
    ${str_hex} =    Catenate  SEPARATOR=     0x${str}

    [return]    ${str_hex}
