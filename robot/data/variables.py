#!/usr/bin/python

##
#    @file    variables.py
#    @brief   Contains common IPMI constants
#
#    @author  Rahul Maheshwari
#
#    @date    June 29, 2016
##

##
# @brief This class contains common IPMI constants
#
class variables():
    HELP_CMD = "ipmitool -H "
    PREFIX_CMD = " -I lanplus -U ADMIN -P admin"

    # Powering on/off/status
    POWER_ON   = "power on"
    POWER_OFF  = "power off"
    POWER_STATUS = "power status"

    POWER_SOFT   = "power soft"

    # Resets
    WARM_RESET   = "mc reset warm"
    BMC_COLD_RESET = "mc reset cold"

    # SEL commands
    SEL_CLEAR   = "sel clear"
    SEL_ELIST   = "sel elist"

    # Host status 
    HOST_STATUS  = "sdr elist |grep 'Host Status'"

    # Network
    BMC_PRESRV_LAN = "raw 0x32 0xba 0x18 0x00"

    # Update
    HPM_UPDATE = " hpm upgrade"
    BMC_FWANDPNOR_IMAGE_UPDATE = "-z 30000 force"
