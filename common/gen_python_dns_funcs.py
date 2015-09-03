#!/usr/bin/python

# This module contains any necessary DNS functions.

import commands

import gen_python_globals as g

################################################################################
def get_mhost_dns(hostname):

  # A function that takes in a host name, runs the mhost command on it,
  # and returns the DNS name of the host.

  stat, output = commands.getstatusoutput("mhost " + hostname + " | grep host_dns_name")
  if stat != 0 or output == "" or output == None:
    # Failure, return.
    return None

  return output.split()[1]

################################################################################
