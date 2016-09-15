#!/usr/bin/python
'''
#############################################################
#    @file     openpower_ffdc_list.py
#    @author:  George Keishing
#
#    @brief    List for FFDC ( First failure data capture )
#              commands and files to be collected as a part
#              of the test case failure.
#############################################################
'''

#-------------------
# FFDC default list
#-------------------

#-----------------------------------------------------------------
#Dict Name {  Index string : { Key String :  Comand string} }
#-----------------------------------------------------------------
FFDC_CMD = {
             'FIRMWARE INFO' :
                 {
                    'AMI Level'  : 'cat /proc/ractrends/Helper/FwInfo',
                    'OS info'  : 'uname -a',
                 },
           }

FFDC_IPMI_CMD = {
             'SYSTEM DATA' :
                 {
                    'Sel Time'            : 'sel time get',
                    'Chassis power info'  : 'chassis status',
                    'Product info' : 'fru print 43',
                    'Boot Count'   : 'sensor get "Boot Count"',
                    'BIOS and BMC Boot Sides'  : 'sensor list | grep -i "Golden Side"',
                    'Host Status'  : 'sdr list | grep -e "OS Boot" -e "FW Boot Progress" -e "Host Status"',
                 },
           }

# add file list needed to be offload from BMC
FFDC_FILE_CMD = {
             'BMC FILES' :
                 {
                    # Execute and write to file
                    # File name : command
                    'BMC_dmsg'    : 'dmesg',
                    'BMC_meminfo' : 'cat /proc/meminfo',
                    'BMC_cpuinfo' : 'cat /proc/cpuinfo',
                    'BMC_uptime'  : 'cat /proc/uptime',
                 },

             'IPMI FILES' :
                 {
                    'BMC_sensorlist'  : 'sensor list',
                    'BMC_eSel'        : 'sel elist',
                    'BMC_fru'         : 'fru print',
                 },

             'OS FILES' :
                 {
                    'OS_release'  : 'cat /etc/os-release',
                    'OS_kernel-version'  : 'uname -a',
                 },

           }

#-----------------------------------------------------------------


# base class for FFDC default list
class openpower_ffdc_list():

    ########################################################################
    #   @@brief   This method returns the list from the dictionary for cmds
    #   @param    i_type: @type string: string index lookup
    #   @return   List of key pair from the dictionary
    ########################################################################
    def get_ffdc_cmd(self,i_type):
        return FFDC_CMD[i_type].items()

    ########################################################################
    #   @@brief   This method returns the list from the dictionary for ipmi
    #             cmds
    #   @param    i_type: @type string: string index lookup
    #   @return   List of key pair from the dictionary
    ########################################################################
    def get_ffdc_ipmi_cmd(self,i_type):
        return FFDC_IPMI_CMD[i_type].items()

    ########################################################################
    #   @@brief   This method returns the list from the dictionary for scp
    #   @param    i_type: @type string: string index lookup
    #   @return   List of key pair from the dictionary
    ########################################################################
    def get_ffdc_file_cmd(self,i_type):
        return FFDC_FILE_CMD[i_type].items()

    ########################################################################
    #   @@brief   This method returns the list index from dictionary
    #   @return   List of index to the dictionary
    ########################################################################
    def get_ffdc_index(self):
        return FFDC_CMD.keys()

    ########################################################################
    #   @@brief   This method returns the list index from dictionary
    #   @return   List of index to the dictionary
    ########################################################################
    def get_ffdc_ipmi_index(self):
        return FFDC_IPMI_CMD.keys()

    ########################################################################
    #   @@brief   This method returns the list index from dictionary
    #   @return   List of index to file list dictionary
    ########################################################################
    def get_ffdc_file_index(self):
        return FFDC_FILE_CMD.keys()

