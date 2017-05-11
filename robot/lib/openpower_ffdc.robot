*** Settings ***
Documentation      This module is for collecting data on test case failure
...                for openpower systems. It will collect the data with a
...                default name openpower_ffdc_report.txt under directory
...                logs/testSuite/testcaseName/ on failure.

Library            String
Library            DateTime
Library            openpower_ffdc_list.py
Library            rf_support_lib.py

Resource           connection_client.robot
Resource           ipmi_client.robot

Variables          ../data/variables.py

*** Variables ***

${PRINT_LINE}      ------------------------------------------------------------------------

${MSG_INTRO}       This document contains the following information:
${MSG_DETAIL}      ${\n}\t\t[ Detailed Logs Captured Section ]
${HEADER_MSG}      ${\n}${PRINT_LINE}${\n}\t\tOPEN POWER TEST FAILURE DATA CAPTURE
...                ${\n}\t\t------------------------------------
...                ${\n}${\n}TEST SUITE FILE\t\t: ${SUITE_NAME} ${\n}
${FOOTER_MSG}      ${PRINT_LINE} ${\n}

${FFDC_LOG_PATH}   ${EXECDIR}${/}logs${/}

*** Keywords ***

Log FFDC If Test Case Failed
    [Documentation]   Main entry point to gather logs on Test case failure

    # Return from here if the test case is a PASS
    Return From Keyword If  '${TEST_STATUS}' != 'FAIL'

    ${cur_time}=       get current time stamp
    Log To Console     ${\n}FFDC Collection Started \t: ${cur_time}
    ${time_tag}=       get strip string    ${cur_time}
    Set Global variable   ${ffdc_time_global}   ${time_tag}

    # Log directory setup
    ${suite_name}=   Catenate  SEPARATOR=    ${SUITE_NAME.replace(" ", "")}
    ${suite_dir}=   Catenate  SEPARATOR=     ${suite_name}-${time_tag}
    ${testname_dir}=    Catenate  SEPARATOR=   ${TEST_NAME.replace(" ", "")}

    Set Suite Variable   ${FFDC_DIR_PATH}   ${FFDC_LOG_PATH}${suite_dir}${/}${testname_dir}-${ffdc_time_global}

    # -- FFDC workspace create --
    create ffdc directory
    openpower header message

    # -- FFDC processing entry point --
    Execute FFDC command list on BMC
    Execute FFDC ipmi command list on BMC
    ffdc file list

    ${cur_time}=       get current time stamp
    Log To Console     FFDC Collection Completed \t: ${cur_time}
    Log                ${\n}${FFDC_DIR_PATH}


create ffdc directory
    [Documentation]    Creates directory and report file
    Create Directory   ${FFDC_DIR_PATH}
    create ffdc report file


create ffdc files
    [Documentation]     Create a user input file name for ffdc
    [Arguments]         ${args}=
    Set Suite Variable  ${FFDC_FILE_PATH}   ${FFDC_DIR_PATH}${/}${ffdc_time_global}-${args}
    Create File         ${FFDC_FILE_PATH}

create ffdc report file
    [Documentation]     Create a generic file name for ffdc
    Set Suite Variable  ${FFDC_FILE_PATH}   ${FFDC_DIR_PATH}${/}${ffdc_time_global}-openpower_ffdc_report.txt
    Create File         ${FFDC_FILE_PATH}


write data to file
    [Documentation]     Write data to the ffdc report document
    [Arguments]         ${data}=""   ${path}=${FFDC_FILE_PATH}
    Append To File      ${path}   ${data}


get current time stamp
    [Documentation]     Get the current time stamp data
    ${cur_time}=    Get Current Date      result_format=%Y-%m-%d %H:%M:%S
    [return]   ${cur_time}

openpower header message
    [Documentation]     Write header message to the report document
    ${cur_time}=    get current time stamp
    write data to file    ${HEADER_MSG}
    write data to file    TEST CASE NAME\t\t: ${TEST_NAME}${\n}
    write data to file    FAILURE TIME STAMP\t: ${cur_time}${\n}
    write data to file    ${\n}${MSG_INTRO}${\n}

    # --- FFDC header notes ---
    @{entries}=     Get ffdc index
    :FOR  ${index}  IN   @{entries}
    \   write data to file   * ${index.upper()}
    \   write data to file   ${\n}

    @{entries}=     Get ffdc ipmi index
    :FOR  ${index}  IN   @{entries}
    \   write data to file   * ${index.upper()}
    \   write data to file   ${\n}

    write data to file    ${FOOTER_MSG}
    write data to file    ${MSG_DETAIL}

write cmd output to ffdc file
    [Documentation]     Write cmd output data to the report document
    [Arguments]         ${data_str}=""   ${data_cmd}=""
    write data to file  ${\n}${FOOTER_MSG}
    write data to file  ${ENTRY_CMD_TYPE.upper()} : ${data_str}\t
    write data to file  ${\n}Executed : ${data_cmd} ${\n}
    write data to file  ${FOOTER_MSG}


Execute FFDC command list on BMC
    [Documentation]    Get the commands, connect to BMC and execute commands
    ${con_status}=   Run Keyword And Return Status    Open Connection And Log In
    Run Keyword And Return If   ${con_status} == ${False}  Log  Open Connection Failed

    @{entries}=     Get ffdc index
    :FOR  ${index}  IN   @{entries}
    \     Loop through ffdc dict list and execute   ${index}


Execute FFDC ipmi command list on BMC
    [Documentation]    Get the commands, connect to BMC and execute commands

    @{entries}=     Get ffdc ipmi index
    :FOR  ${index}  IN   @{entries}
    \     Loop through ffdc dict list and execute ipmi   ${index}


Loop through ffdc dict list and execute
    [Documentation]    Feed in key pair list from dictionary to execute
    [Arguments]        ${data_str}=    ${type}=

    @{ffdc_default_list}=    Get ffdc cmd    ${data_str}

    Set Suite Variable   ${ENTRY_CMD_TYPE}   ${data_str}
    :FOR  ${cmd}  IN  @{ffdc_default_list}
    \    Execute command and write to ffdc    ${cmd[0]}  ${cmd[1]}

Loop through ffdc dict list and execute ipmi
    [Documentation]    Feed in key pair list from dictionary to execute
    [Arguments]        ${data_str}=    ${type}=

    @{ffdc_default_list}=    Get ffdc ipmi cmd    ${data_str}

    Set Suite Variable   ${ENTRY_CMD_TYPE}   ${data_str}
    :FOR  ${cmd}  IN  @{ffdc_default_list}
    \    Execute command and write to ffdc ipmi    ${cmd[0]}  ${cmd[1]}


Execute command and write to ffdc
    [Documentation]    Execute command on bmc box and write to ffdc
    [Arguments]        ${data_str}=""   ${data_cmd}=""
    write cmd output to ffdc file   ${data_str}  ${data_cmd}

    ${stdout}  ${stderr}=    Execute Command    ${data_cmd}   return_stderr=True
    # Write stdout data on success and error msg to the file on failure
    Run Keyword If   '${stderr}' == '${EMPTY}'   write data to file   ${stdout} ${\n}
    ...  ELSE  Run Keyword   write data to file  ${stderr} ${\n}
    write data to file    ${FOOTER_MSG}


Execute command and write to ffdc ipmi
    [Documentation]    Execute command on bmc box and write to ffdc
    [Arguments]        ${data_str}=""   ${data_cmd}=""
    write cmd output to ffdc file   ${data_str}  ${data_cmd}

    ${stdout}=   Run IPMI Standard Command    ${data_cmd}
    write data to file   ${stdout} ${\n}
    write data to file    ${FOOTER_MSG}


# For creating files in FFDC directory
ffdc file list
    [Documentation]    Run ipmi and file commands
    ${con_status}=   Run Keyword And Return Status    Open Connection And Log In
    Run Keyword And Return If   ${con_status} == ${False}  Log  Open Connection Failed

    @{entries}=     Get ffdc file index
    :FOR  ${index}  IN   @{entries}
    \   Run Keyword If   '${index}' == 'BMC FILES'    ffdc file list command    ${index}
    \   Run Keyword If   '${index}' == 'IPMI FILES'   ffdc ipmi list command    ${index}
    \   Run Keyword If   '${index}' == 'OS FILES'   ffdc os list command    ${index}


ffdc ipmi list command
    [Documentation]    create files to current log directory
    [Arguments]        ${index}

    # --- Files to be created ---
    @{ffdc_default_list}=    Get ffdc file cmd    ${index}

    :FOR  ${cmd}  IN  @{ffdc_default_list}
    # Create File to current test FFDC directory
    \    create ffdc files   ${cmd[0]}
    \    Execute ipmi command and write to file   ${cmd[1]}


ffdc file list command
    [Documentation]    create files to current log directory
    [Arguments]        ${index}

    # --- Files to be created ---
    @{ffdc_default_list}=    Get ffdc file cmd    ${index}

    :FOR  ${cmd}  IN  @{ffdc_default_list}
    # Create File to current test FFDC directory
    \    create ffdc files   ${cmd[0]}
    \    Execute file command and write to file   ${cmd[1]}


ffdc os list command
    [Documentation]    create files to current log directory
    [Arguments]        ${index}

    ${con_status}=   Run Keyword And Return Status    Open OS Connection And Log In
    Run Keyword And Return If   ${con_status} == ${False}  Log  Open OS Connection Failed

    # --- Files to be created ---
    @{ffdc_default_list}=    Get ffdc file cmd    ${index}

    :FOR  ${cmd}  IN  @{ffdc_default_list}
    # Create File to current test FFDC directory
    \    create ffdc files   ${cmd[0]}
    \    Execute file command and write to file   ${cmd[1]}


Execute ipmi command and write to file
    [Documentation]    Execute command on bmc box and write to ffdc file
    [Arguments]        ${data_cmd}=""

    ${stdout}=   Run IPMI Standard Command    ${data_cmd}
    write data to file   ${stdout} ${\n}


Execute file command and write to file
    [Documentation]    Execute command on bmc box and write to ffdc file
    [Arguments]        ${data_cmd}=""

    Log To Console   Executing : ${data_cmd}
    ${stdout}  ${stderr}=    Execute Command    ${data_cmd}   return_stderr=True
    # Write stdout data on success and error msg to the file on failure
    Run Keyword If   '${stderr}' == '${EMPTY}'   write data to file   ${stdout} ${\n}
    ...  ELSE  Run Keyword   write data to file  ${stderr} ${\n}

