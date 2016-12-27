#!/usr/bin/python

# This module is sourced by all other custom modules, and contains functions
# and variables that will be useful to most functions.

import commands
import os
import pwd
import sys
import time

# The global variable dictionary. Mainly used for options.
global_vars = {}

# Let's add a few global variables that we refer to continuously.
global_vars["quiet"] = False
global_vars["test_mode"] = False
global_vars["debug"] = False
# Easier-access names for the above.
quiet = False
test_mode = False
debug = False

# Global self-referential definitions.
program_path = sys.argv[0]
program_name = os.path.basename(program_path)

# A global dictionary of system parameters. See get_system_parms() for more
# information on what is stored here.
system_parms = {}

# Some timing variables.
start_time = time.time()
sprint_time_last_seconds = start_time

################################################################################
def gv(var):

  # An easier way of accessing the global_vars dictionary, but it's
  # slow. If only Python had macros, life would be great.

  return global_vars[var]

################################################################################



################################################################################
def sysparm(var):

  # An easier way of accessing the system_parms dictionary.

  return system_parms[var]

################################################################################



################################################################################
def get_system_parms():

  # This generates and stores basic system information in the SYSTEM_PARMS
  # dictionary. Most of these are for use by gen_print_header(), but they have
  # other uses too. The commands function we're using is deprecated in newer
  # versions of Python, but we're currently running on 2.4.3.

  global system_parms

  # Current working directory.
  system_parms["pwd"] = str(os.getcwd())
  # Home directory.
  stat, output = commands.getstatusoutput("echo ${HOME}")
  system_parms["home"] = output
  # Process ID.
  system_parms["pid"] = os.getpid()
  # Process group ID. (Not used for AIX at this time.)
  if os.uname()[0] == "Linux":
    system_parms["pgid"] = os.getpgid(os.getpid())
  else:
    system_parms["pgid"] = ""
  # User name.
  system_parms["username"] = str(pwd.getpwuid(os.getuid())[0])
  # User ID.
  system_parms["userid"] = os.geteuid()
  # Group ID.
  system_parms["gid"] = os.getegid()
  # Host name.
  system_parms["hostname"] = str(os.uname()[1])
  # Display.
  stat, output = commands.getstatusoutput("echo ${DISPLAY}")
  system_parms["display"] = output
  
################################################################################



# A couple of print functions that are used everywhere. We're putting them
# here so that we don't have to worry about circular dependencies as much.



# Initialize global values used as defaults by print_var.
col1_indent=0

# Calculate default column width for print_var based on environment variable settings.  The whole idea is to make the variable value line up nicely with the time stamps.
col1_width = 29;
if 'NANOSECONDS' in os.environ:
  NANOSECONDS = os.environ['NANOSECONDS']
else:
  NANOSECONDS = 0

if ( NANOSECONDS == "1" ):
  col1_width = col1_width + 10

if 'SHOW_ELAPSED_TIME' in os.environ:
  SHOW_ELAPSED_TIME = os.environ['SHOW_ELAPSED_TIME']
else:
  SHOW_ELAPSED_TIME = 0

if ( SHOW_ELAPSED_TIME == "1" ):
  if ( NANOSECONDS == "1" ):
    col1_width = col1_width + 14
  else:
    col1_width = col1_width + 7



################################################################################
def sprint_time():

  # This function will print the time in our usual format.

  global NANOSECONDS
  global SHOW_ELAPSED_TIME
  global sprint_time_last_seconds

  seconds = time.time()
  loc_time = time.localtime(seconds)
  nanoseconds = "%0.9f" % seconds
  pos = nanoseconds.find(".")
  nanoseconds = nanoseconds[pos:]

  time_string = time.strftime("#(%Z) %Y/%m/%d %H:%M:%S", loc_time)
  if (NANOSECONDS == "1"):
    time_string = time_string + nanoseconds

  if ( SHOW_ELAPSED_TIME == "1" ):
    cur_time_seconds = seconds
    math_string = "%9.9f" % cur_time_seconds + " - " + "%9.9f" % sprint_time_last_seconds
    elapsed_seconds = eval(math_string)
    if ( NANOSECONDS == "1" ):
      elapsed_seconds = "%11.6f" % elapsed_seconds
    else:
      elapsed_seconds = "%4i" % elapsed_seconds
    sprint_time_last_seconds = cur_time_seconds;
    time_string = time_string + " - " + elapsed_seconds

  return time_string + " -"

################################################################################



################################################################################
def print_error(buffer):

  print >> sys.stderr, sprint_time() + " **ERROR** " + buffer;

################################################################################




################################################################################
def print_var(var_name, var_value, loc_col1_indent=col1_indent, loc_col1_width=col1_width):

  # This function will print the var name/value passed to it.

  format_string = "%" + str(loc_col1_indent) + "s%-" + str(loc_col1_width) + "s%s"
  print format_string % ("", var_name + ":", var_value)

  return
################################################################################
