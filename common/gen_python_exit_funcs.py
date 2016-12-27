#!/usr/bin/python

# This module contains functions that will handle normal or erroneous exit
# situations. The program can exit normally, in which case the final two
# functions are executed, or it can exit abnormally via a signal, in which case
# gen_func_cleanup is called and goes through the cleanup stack.

import os
import signal
import sys

import gen_python_globals as g
import gen_python_print_funcs as gprint
import gen_python_sig_funcs as gsig

# Functions can be pushed onto the stack with optional arguments, to be
# executed along with that function. To push a function "foo" without arguments:
#   gexit.push_cleanup_func(foo)
# To push a function "foo" with arguments:
#   gexit.push_cleanup_func(foo, arg0, arg1, ..., argn)
#
# All cleanup functions must be defined in this way, whether they have
# additional arguments or not:
#   def foo(signo, rc=0, *args):
# Then arg0, arg1, ..., argn are stored in args[0], args[1], ..., args[n].
#
# If writing a cleanup function, it's a good idea to begin by trapping
# troublesome signals with trap_signal() or trap_signals(), then finish the
# function by using release_signals(). This is especially if your cleanup
# function can potentially run in a non-error state.

# Some global lists.
cleanup_file_list = []
global_cleanup_stack = []
saved_signal_list = []

################################################################################
def add_cleanup_file(filename):

  # This function will add a file name to the global list of files to be
  # deleted at the end of the program.

  global cleanup_file_list
  cleanup_file_list.append(filename)

  return 0

################################################################################



################################################################################
def remove_cleanup_file(filename, quiet_del=False):

  # This function will search through the cleanup_file_list for the given
  # filename. If it exists, the file is deleted from the system and then
  # removed from the list. If the file is not in the cleanup list for some
  # reason, it is not deleted from the system as a failsafe.

  global cleanup_file_list

  # First, we should check to see if the file is in our list. If not, no big
  # deal. Just move on.
  try:
    cleanup_file_list.remove(filename)
  except ValueError:
    # The file wasn't in our list.
    if not quiet_del:
      print_time("File " + filename + " not found in cleanup list.")

  # Next, we should check to see if the file exists at all. If not, then that
  # counts as success, because it's possible an earlier attempt at this
  # function deleted it.
  if not os.path.isfile(filename):
    if not quiet_del:
      print_time("Attempted to delete file " + filename + " but the file does not exist. Proceeding with script.")
    return 0

  # If the file does exist, try to delete it. If we fail to, return a
  # failure.
  try:
    os.remove(filename)
  except OSError:
    # The file was in our list, but we failed to delete it for some reason.
    if not quiet_del:
      g.print_error("Cannot delete file " + filename + ".")
    return 1

  return 0

################################################################################



################################################################################
def remove_all_cleanup_files(signal,rc=0,*args):

  # This function deletes all files in the cleanup_file_list. This function is
  # always the first thing pushed onto the cleanup stack, so that it will occur
  # if the program exits erroneously. It is also called by gen_exit_function.
  #
  # The programmer can populate this list with
  #   gexit.add_cleanup_file(file_name)
  # or
  #   gexit.cleanup_file_list.append(file_name)

  if not g.quiet:
    gprint.print_func_name()

  global cleanup_file_list

  # The main cleanup loop.
  while cleanup_file_list != []:
    cleanup_file = cleanup_file_list.pop()
    try:
      # Try deleting the file.
      os.remove(filename)
    except OSError:
      # File deletion failed for some reason.
      if not quiet_del:
        g.print_error("Cannot delete file " + filename + ".")
      rc = 1

  return rc

################################################################################



################################################################################
def push_cleanup_func(cleanup_func, *args):

  # This function will push a cleanup function onto the global_cleanup_stack,
  # to be executed when it is popped off (most likely when the program is
  # interrupted by a signal). We also push on a possibly empty set of
  # additional arguments to the function.

  global global_cleanup_stack  

  global_cleanup_stack.append((cleanup_func,args))

  return 0

################################################################################



################################################################################
def pop_cleanup_func(signo=0, rc=0):

  # This function will pop a cleanup function off of the global_cleanup_stack,
  # and execute it. Usually used by gen_func_cleanup.

  global global_cleanup_stack

  cleanup_func, cleanup_args = global_cleanup_stack.pop()
  cleanup_func(signo, rc, *cleanup_args)

  return 0

################################################################################



################################################################################
def pop_cleanup_stack(signo=0, rc=0):

  # Pop and execute everything on the global_cleanup_stack.

  global global_cleanup_stack

  while global_cleanup_stack != []:
    pop_cleanup_func(signo, rc)

  return 0

################################################################################



################################################################################
def remove_cleanup_func(func):

  # This function will remove a cleanup function from the global_cleanup_stack
  # without executing it.

  global global_cleanup_stack

  for i in range(len(global_cleanup_stack)-1,-1,-1):
    if global_cleanup_stack[i][0] == func:
      global_cleanup_stack.pop(i)
      break

  return 0

################################################################################



################################################################################
def gen_func_cleanup(signo, rc=0):

  # This function is designed to execute when a SIGINT or SIGTERM occurs. It
  # will go through a global function stack, executing and popping each one in
  # turn, before finally exiting the program with a given return code.
  #
  # Each cleanup function needs to be capable of accepting signo and rc as
  # defined parameters, as well as one last *args parameter that may contain
  # something or nothing.

  global global_cleanup_stack
  global saved_signal_list

  # Save the current signal set.
  if saved_signal_list == []:
    saved_signal_list = gsig.save_signals()
  else:
    g.print_error("Possible programmer error. Attempting to save signals to saved_signal_list in gen_func_cleanup, but signals have already been saved.")

  # We're going to start by capturing and ignoring SIGINT and SIGTERM, so they
  # don't ruin our cleanup functions.
  signal.signal(signal.SIGINT, gsig.ignore_signals)
  signal.signal(signal.SIGTERM, gsig.ignore_signals)

  # Pop off all the functions in the global_cleanup_stack.
  while global_cleanup_stack != []:
    pop_cleanup_func(signo, rc)

  # Restore the previously saved signal set.
  gsig.restore_signals(saved_signal_list)

  # Now exit, which we wanted to do in the first place.
  sys.exit(rc)

################################################################################



################################################################################
def gen_exit_function_setup(rc):

  # This setup function does any pre-exit stuff.
  # By default, we set up a new signal handler that will ignore the INT and
  # TERM signals.

  signal.signal(signal.SIGINT, gsig.ignore_signals)
  signal.signal(signal.SIGTERM, gsig.ignore_signals)

  return 0

################################################################################




################################################################################
def gen_exit_function(rc):

  # This function runs whenever the program exits. It does things like print
  # the total runtime and pop the cleanup stack, and also performs the actual
  # system exit.

  # Note that remove_all_cleanup_files() will be executed here if it hasn't
  # before now.
  pop_cleanup_stack()

  gprint.print_runtime()

  gprint.print_ending_source()

  sys.exit(rc)

################################################################################
