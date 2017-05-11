*** Settings ***
Resource                ../lib/resource.txt
Resource                ../lib/ipmi_client.robot
Resource                ../lib/openpower_ffdc.robot

Library                 SSHLibrary
Library                 OperatingSystem

*** Variables ***


*** Keywords ***

Wait For Host To Ping
    [Arguments]  ${host}  ${timeout}=${OPENPOWER_REBOOT_TIMEOUT}min
    ...          ${interval}=5 sec

    # host      IP address of the host to ping.
    # timeout   The amount of time after which attempts to ping cease.
    # interval  The amount of time in between attempts to ping.

    Wait Until Keyword Succeeds  ${timeout}  ${interval}  Ping Host  ${host}

    Log To Console    '** OS IS ONLINE **'

Ping Host
    [Arguments]     ${host}
    ${RC}   ${output} =     Run and return RC and Output    ping -c 4 ${host}
    Log     RC: ${RC}\nOutput:\n${output}
    Should be equal     ${RC}   ${0}

Get Power State
    [Documentation]  Returns the power state as on or off
    ${status}=    Run IPMI Standard Command   ${POWER_STATUS}
    Log To Console   \n ${status}
    [return]   ${status}

Chassis SEL Check
    ${status}=    Run IPMI Standard Command   ${SEL_ELIST}
    Log To Console   ${status}
    #Should be equal   ${status}    SEL has no entries

Chassis SEL Clear
    ${status}=    Run IPMI Standard Command   ${SEL_CLEAR}
    Log To Console   ${status}
    Should Contain   ${status}    Clearing SEL

Initiate Power Off
    [Documentation]  Chassis power off
    ${resp}=    Run IPMI Standard Command   ${POWER_OFF}
    Should Be Equal    ${resp}    Chassis Power Control: Down/Off

Initiate Power On
    [Documentation]  Chassis power on
    ${resp}=    Run IPMI Standard Command   ${POWER_ON}
    Should Be Equal    ${resp}    Chassis Power Control: Up/On

Put Power On State
    [Documentation]  Get system in power on state
    ${status}=   Get Power State
    Run Keyword If	'${status}'!='Chassis Power is on'   Initiate Power On
    ${status}=  Get Power State
    Should be equal   ${status}    Chassis Power is on

Put Power Off State
    [Documentation]  Get system in power off state
    ${status}=   Get Power State
    Run Keyword If      '${status}'!='Chassis Power is off'   Initiate Power OFF
    ${status}=  Get Power State
    Should be equal   ${status}    Chassis Power is off

Force Power On
    [Documentation]  Force system to power on
    Initiate Power Off
    Initiate Power On

Check OS
    [Documentation]  Attempts to ping the host OS and then checks that the host
    ...              OS is up by running an SSH command.
    [Arguments]  ${os_host}=${OS_HOST}  ${os_username}=${OS_USERNAME}
    ...          ${os_password}=${OS_PASSWORD}
    [Teardown]  Close Connection

    # os_host           The DNS name/IP of the OS host associated with our BMC.
    # os_username       The username to be used to sign on to the OS host.
    # os_password       The password to be used to sign on to the OS host.

    # Attempt to ping the OS. Store the return code to check later.
    ${ping_rc}=    Run Keyword and Return Status  Ping Host  ${os_host}

    Open connection    ${os_host}
    Login    ${os_username}    ${os_password}

    ${output}    ${stderr}    ${rc}=    Execute Command    uptime    return_stderr=True
    ...          return_rc=True

    # If the return code returned by "Execute Command" is non-zero, this keyword
    # will fail.
    Should Be Equal    ${rc}      ${0}
    # We will likewise fail if there is any stderr data.
    Should Be Empty    ${stderr}

    # We will likewise fail if the OS did not ping, as we could SSH but not ping
    Should Be Equal As Strings    ${ping_rc}    ${TRUE}

Wait for OS
    [Documentation]  Waits for the host OS to come up via calls to "Check OS".
    [Arguments]  ${os_host}=${OS_HOST}  ${os_username}=${OS_USERNAME}
    ...          ${os_password}=${OS_PASSWORD}  ${timeout}=${OS_WAIT_TIMEOUT}

    # os_host           The DNS name or IP of the OS host associated with our
    #                   BMC.
    # os_username       The username to be used to sign on to the OS host.
    # os_password       The password to be used to sign on to the OS host.
    # timeout           The timeout in seconds indicating how long you're
    #                   willing to wait for the OS to respond.

    # The interval to be used between calls to "Check OS".
    ${interval}=  Set Variable  5

    Wait Until Keyword Succeeds  ${timeout} sec  ${interval}  Check OS
    ...                          ${os_host}  ${os_username}  ${os_password}

Get IP Address
    [Documentation]   This keyword return IP address of BMC using ipmitool

    ${resp}=    Run IPMI Standard Command    lan print
    ${address_line} =   Get Lines Matching Pattern    ${resp}    IP Address*
    ${ip_address_list} =   Get Regexp Matches   ${address_line}   (?:[0-9]{1,3}\.){3}[0-9]{1,3}
    ${ip_address} =   Get From List   ${ip_address_list}   0
    log to console    ${ip_address}

    [return]    ${ip_address}

Get MAC Address
    [Documentation]   This keyword return MAC address of BMC using ipmitool

    ${resp}=    Run IPMI Standard Command    lan print
    ${address_line} =   Get Lines Matching Pattern    ${resp}    MAC Address*
    ${mac_address_list} =   Get Regexp Matches   ${address_line}   ([0-9a-fA-F][0-9a-fA-F]:){5}([0-9a-fA-F][0-9a-fA-F])
    ${mac_address} =   Get From List   ${mac_address_list}   0
    log to console    ${mac_address}

    [return]    ${mac_address}

Put OS to online
    [Documentation]  Get OS to online by powering on the system

    ${ping_rc}=  Run Keyword and Return Status  Ping Host  ${os_host}
    Run Keyword If   ${ping_rc}!=${TRUE}   Force Power On
    Wait for OS

Pre Test Execution Setup
    [Documentation]  Perform pre test execution setup. It performs sel clear
    ...              and make sure that the system is in runtime

    Put OS to online

    Run IPMI Standard Command    sol deactivate

    ${resp} =    Get MAC Address
    #Set Suite Variable    ${MAC_ADDRESS_PRE_TEST}    ${resp}
    Set Global Variable    ${MAC_ADDRESS_PRE_TEST}    ${resp}

    Chassis SEL Clear
    log to console    '************* PRE TEST SETUP DONE **********************'

Expected Result verification
    [Documentation]  Verify expected result post test execution. It performs
    ...              sel log, network configuration, mac address check


    log to console    '************* POST TEST VERIFICATION ********************'
    Chassis SEL Check
    ${ip_address} =    Get IP Address
    Should Be Equal As Strings    ${ip_address}   ${OPENPOWER_HOST}

    ${mac_address} =    Get MAC Address
    Should Be Equal As Strings    ${mac_address}   ${MAC_ADDRESS_PRE_TEST}

    ${resp}=    Run IPMI Standard Command    sol activate &
    Log To Console    ${resp}
    Should Contain    ${resp}    SOL Session operational


    Wait For Host To Ping    ${OPENPOWER_HOST}
    Check OS
    #Sleep   60sec

    Run Keyword If Test Failed    Log FFDC If Test Case Failed

    log to console    '*************************************************************'
