#!/usr/bin/python

# This module contains a robust set of functions for executing shell commands
# and some Python commands.

import commands
import os
import signal
import string
import sys
import time

import gen_python_globals as g
import gen_python_opt_funcs as gopt
import gen_python_print_funcs as gprint
import gen_python_sig_funcs as gsig

################################################################################
def cmd_fnc(cmd_buf):

  # This function will execute a given command string on the command line, but
  # only if we're not in test mode.

  if not g.test_mode:
    os.system(cmd_buf)

################################################################################



################################################################################
def cmd_fnc_u(cmd_buf):

  # This function will execute a given command string on the command line
  # whether we're in test mode or not.

  os.system(cmd_buf)

################################################################################



################################################################################
def exec_cmd(cmd_buf, stat=False, out=False, err=False, time_out=0, max_attempts=1, sleep_time=1, debug=False, bash=False):

  # This is an advanced function for executing a string as a command. It has
  # the capacity to save the output and return it, time the command out, retry
  # the function and sleep between attempts. The rmt_cmd option has been
  # removed, as the "rcmd" function now has a "-rrc" flag that will set the
  # return code automatically. This is less typing for the programmer, so just
  # do that.

  # stat: if this is set, an "issuing" message will be printed prior to
  #   execution.
  # out: if this is set, the output from the command will be printed to the
  #   screen.
  # err: if this is set, a failure message will be printed if the command fails.
  # time_out: if this is non-zero, the function will be timed out after the
  #   specified number of seconds.
  # max_attempts: the total number of times to attempt the command.
  # sleep_time: the number of seconds to wait between each attempt.
  # debug: if this is set, debug information will be printed.
  # bash: if this is set, the function will execute a Bash command instead of
  #   a Python command.

  # This function doesn't use parms in the exact same way as the bash version,
  # but just writing "param=value" works equally well in the function call,
  # i.e. exec_cmd(cmd_buf, param1=value1, param2=value2)

  stat = gopt.bool_convert(stat)
  out = gopt.bool_convert(out)
  err = gopt.bool_convert(err)
  debug = gopt.bool_convert(debug)
  current_attempt = 0

  # Print debug information, if necessary.
  if debug:
    gprint.print_time("Printing debug information for exec_cmd.")
    g.print_var("cmd_buf",cmd_buf)
    g.print_var("stat",stat)
    g.print_var("out",out)
    g.print_var("err",err)
    g.print_var("time_out",time_out)
    g.print_var("max_attempts",max_attempts)
    g.print_var("sleep_time",sleep_time)
    g.print_var("debug",debug)

  # If we're using a time-out variable, then we need to set up a time-out
  # signal handler. No need to fork processes.
  if time_out != 0:
    original_handler = signal.signal(signal.SIGALRM, gsig.gen_timeout_handler)

  # Print out an issuing message if needed.
  if stat and bash:
    gprint.issuing(cmd_buf)
    if max_attempts == 0:
      gprint.print_time("max_attempts is zero so the preceding command will not actually be executed.")

  # Now let's begin the execution.
  status = 0
  output = ""
  while current_attempt < max_attempts:
    status = 0
    if time_out == 0:
      # If we're not timing it out, just run the command.
      
      status, output = commands.getstatusoutput(cmd_buf)
      if out:
        print output
    else:
      # Otherwise, we need to set an alarm and catch a time-out.
      # We'll actually catch all exceptions, since it's possible we can
      # be executing a Python command.
      signal.alarm(time_out)
      try:
        # In the Bash case.
        if bash:
          status, output = commands.getstatusoutput(cmd_buf)
          if out:
            print output
        # In the Python case.
        else:
          if out:
            exec(cmd_buf)
          else:
            sys.stdout = os.devnull
            exec(cmd_buf)
            sys.stdout = sys.__stdout__
      except:
        # Restore stdout just in case.
        sys.stdout = sys.__stdout__
        status = 1
      signal.alarm(0)

    # We need to check the status of the command to see if it failed.
    # Note that status is set to 1 upon time-out.
    if status == 0:
      break
    else:
      current_attempt += 1
      if sleep_time != 0 and current_attempt < max_attempts:
        time.sleep(sleep_time)

  # Check to see if we ultimately failed the command.
  if status != 0:
    if err:
      g.print_error("The following command failed to execute: " + cmd_buf)
      if output != "":
        print "Command output:"
        print output

  # Reset the alarm handler.
  if time_out != 0:
    signal.signal(signal.SIGALRM, original_handler)

  return status

################################################################################



################################################################################
def sleep_kill(sleep_time, *params):

  # This function sleeps for a specified number of seconds, and then execute a
  # kill command with a specified parameter string.

  kill_string = "kill "
  time.sleep(sleep_time)
  for param in params:
    kill_string += param + " "
  cmd_fnc(kill_string)

  return 0

################################################################################



################################################################################
def multi_cmd_fnc(gen_cmd, element_list, headers=False, time_out=0, max_attempts=1, sleep_time=1, bash=False):

  # This function runs the gen_cmd one time for each element in the
  # element_list, while replacing "[element]" with the next element in the
  # list. Don't actually execute if we're in test_mode.

  # headers: if true, this has headers printed for each command.
  # time_out, max_attempts and sleep_time are the same as in exec_cmd, since
  # we just call exec_cmd from here.

  global quiet

  headers = gopt.bool_convert(headers)
  if bash:
    langstr = "Bash"
  else:
    langstr = "Python"

  # If we're not in quiet mode, print out a header.
  if not quiet:
    print "------------------------------------------------------------------------------------------------------------------------"
    gprint.print_time("Issuing a " + langstr + " command for every item in the list.")

  # We'll do this once for every list element.
  for elem in element_list:
    # Let's search for [element] in our gen_cmd, and replace it with the element
    # from our list. Since we assume that [element] is present, we'll just do the
    # replace right away.
    cmd_buf = string.replace(gen_cmd, "[element]", elem)

    # Now for the actual execution.
    if not g.test_mode:
      retval = exec_cmd(cmd_buf, headers and not quiet, not quiet, not quiet, time_out, max_attempts, sleep_time, g.global_vars["debug"], bash)

  if not quiet:
    print "------------------------------------------------------------------------------------------------------------------------"

  return 0

################################################################################
