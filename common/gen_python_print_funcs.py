#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG 
# This is an automatically generated prolog. 
#  
# esw_dev_tools src/aipl/x86/gen_python_print_funcs.py 1.3 
#  
# Licensed Materials - Property of IBM 
#  
# Restricted Materials of IBM 
#  
# COPYRIGHT International Business Machines Corp. 2014 
# All Rights Reserved 
#  
# US Government Users Restricted Rights - Use, duplication or 
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp. 
#  
# IBM_PROLOG_END_TAG 

# This module contains various functions related to printing.

import inspect
import os
import string
import sys
import textwrap
import time

import gen_python_date_funcs as gdate
import gen_python_globals as g
import gen_python_string_funcs as gstr

hidden_text_list = []

# print_var and print_error have been moved to gen_python_globals.py.

# Compatibility import.
program_name = g.program_name
program_path = g.program_path
print_error = g.print_error
print_var = g.print_var
sprint_time = g.sprint_time

################################################################################
def printf(str, *args):
  sys.stdout.write(str % args)

  # Apparently this works! So says the Python Cookbook, anyway.

  return 0

################################################################################



################################################################################
def print_time(str=None):

  if str is None:
    print g.sprint_time(),
  else:
    print g.sprint_time(), str

################################################################################



################################################################################
def qprint(str):

  # Only print this string if "quiet" is not True in global_vars.

  if g.quiet != True:
    print str

################################################################################



################################################################################
def qprint_time(str=None):

  # Only print the time if "quiet" is not True in global_vars. Handy.

  if g.quiet != True:
    if str is None:
      print g.sprint_time(),
    else:
      print g.sprint_time(), str

################################################################################



################################################################################
def dprint(str):

  # Only print this string if "debug" is True in global_vars.

  if g.debug == True:
    print_time("DEBUG: " + str)

  return 0

################################################################################



################################################################################
def print_global(var_name, loc_col1_indent=g.col1_indent, loc_col1_width=g.col1_width):

  # This function will print the global var name/value passed to it. Using a
  # global dictionary lets us simplify this command.

  format_string = "%" + str(loc_col1_indent) + "s%-" + str(loc_col1_width) + "s%s"
  print format_string % ("", var_name + ":", g.global_vars[var_name])

  return
################################################################################



################################################################################
def print_system_parms():

  # This prints out some basic system information for gen_print_header().

  # File name.
  g.print_var("command_line",g.program_path)
  # Process ID.
  g.print_var(g.program_name + "_pid",g.system_parms["pid"])
  # PGID.
  g.print_var(g.program_name + "_pgid",g.system_parms["pgid"])
  # User ID.
  g.print_var("uid",str(g.system_parms["userid"]) + " (" + g.system_parms["username"] + ")")
  # Group ID.
  g.print_var("gid",str(g.system_parms["gid"]) + " (" + g.system_parms["username"] + ")")
  # Host name.
  g.print_var("hostname",g.system_parms["hostname"])
  # Display.
  g.print_var("DISPLAY",g.system_parms["display"])

  return 0

################################################################################



################################################################################
def print_global_vars():

  # This function prints out all of the variables in global_vars along with
  # their values. Note that Python dictionaries do not maintain any sort of
  # order. If we want these to appear in a non-aribtrary order we can do that,
  # but performance will be impacted.

  for var, value in g.global_vars.iteritems():
    g.print_var(var,value)

  return 0

################################################################################



################################################################################
def add_hidden_text(hidden_word):

  # Adds a word to the global hidden_text_list. Doesn't add duplicates.

  global hidden_text_list

  if hidden_word not in hidden_text_list:
    hidden_text_list.append(hidden_word)

  return 0

################################################################################



################################################################################
def my_print(string_buf):

  # This function imitates the Bash function my_echo. It prints out the provided
  # string, except any text that appears in the global hidden_text_list is
  # replaced with "********". This is useful for password protection, mainly.
  # The issuing() function uses this to print by default.

  global hidden_text_list

  for hidden_word in hidden_text_list:
    # If we find a hidden word...
    if string.find(string_buf, hidden_word):
      # Python has a function that handles the replacement for us.
      string_buf = string.replace(string_buf, hidden_word, "********")

  # Now print the resulting string.
  print string_buf

  return 0

################################################################################




################################################################################
def issuing(cmd_buf, show_hidden_text=False):

  # This function will print the var name/value passed to it.
  # NEW: this function uses my_print by default, which will hide anything in
  # the hidden_text_list global list. This can be changed if desired.

  if show_hidden_text:
    print_time("Issuing: " + cmd_buf)
  else:
    print_time() ; my_print("Issuing: " + cmd_buf)

  return
################################################################################



################################################################################
def print_runtime():

  if g.quiet:
    return

  # This function is designed to be called at the end of your program.  It will display the run_time of your program.

  # This function relies on global variable start_time being set by the caller at the start of program execution.

  end_time = "%9.9f" % time.time()

  math_string = str(end_time) + " - " + "%9.9f" % g.start_time
  run_time_secs = eval(math_string)


  run_time_secs = "%i" % round(run_time_secs)

  # We've made a Python function to do this, above. No more Bash needed.
  run_time = gdate.convert_secs_to_dhms(run_time_secs)[0]

  g.print_var("run_time", run_time)

  return
################################################################################



################################################################################
def print_ending_source():

  # This function prints a "script ending" message.

  if not g.quiet:
    print_time("Ending " + g.program_path + " script.")
    print

  return 0

################################################################################



################################################################################
def print_func_name():

  # This function will print out the name of whatever function it's being
  # called from, along with its parameters. We get this information by
  # inspecting the program stack.

  # inspect.stack()[1] indicates the parent frame. [0] would be this frame.
  caller_frame = inspect.stack()[1]
  caller_name = caller_frame[3]
  caller_locals = inspect.getargvalues(caller_frame[0])[3]

  print_time("Executing: " + g.program_name + "::" + caller_name)

  for var, value in caller_locals.iteritems():
    g.print_var(var,value)

  return 0

################################################################################



################################################################################
def print_call_stack():

  # This function prints out the full call stack for the given point in the
  # program, with arguments and line numbers and nice formatting.

  print "--------------------------------------------------------------------------------"
  print "Python function call stack"
  print
  print "Line # Function name and arguments"
  print "------ -------------------------------------------------------------------------"

  # Grab the current program stack.
  current_stack = inspect.stack()

  # Process each frame in turn.
  for stack_frame in current_stack:
    # Get the line number first.
    lineno = str(stack_frame[2])

    # Next, the function name.
    func_name = str(stack_frame[3])
    if func_name == "?":
      # "?" is the name used when code occurs not in a function.
      func_name = "(none)"

    # We'll add the specific file name as well.
    file_path = str(stack_frame[1])
    file_split = file_path.rsplit("/",1)
    if len(file_split) > 1:
      file_name = file_split[1]
    else:
      file_name = file_split[0]
    func_str = "%s::%s" % (file_name, func_name)

    # Finally, the program arguments, if any. This is trickier.
    locals_str = ""
    argvals = inspect.getargvalues(stack_frame[0])
    function_parms = argvals[0]
    frame_locals = argvals[3]
    if function_parms != []:
      locals_str += "("

    first_var = True
    for var, value in frame_locals.iteritems():
      # We need to cross-reference our locals dictionary with our list of
      # parameters.
      if var in function_parms:
        if not first_var:
          locals_str += ", "
        else:
          first_var = False
        locals_str += "%s = %s" % (var, repr(value))
    if function_parms != []:
      locals_str += ")"

    # Now we need to print this in a nicely-wrapped way.
    func_locals_str = func_str + " " + locals_str
    col_output = gstr.col_wrap([lineno, func_locals_str],[6,73],[True,False])
    print col_output

  print "--------------------------------------------------------------------------------"

  return 0

################################################################################



################################################################################
def process_error_message():

  # This may be added in later. This is the last gen_bash_print_funcs to
  # convert.

  g.print_error("process_error_message is not implemented.")
  pass

################################################################################



################################################################################
def print_dashes():

  # Print out a dashed line.

  print "-------------------------------------------------------------------------------------------------------"

  return 0

################################################################################



################################################################################
def print_stars():

  # This function prints a line of stars.

  print "********************************************************************************"

  return 0

################################################################################
