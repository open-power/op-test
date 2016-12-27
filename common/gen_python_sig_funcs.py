#!/usr/bin/python

# "Ok, I'm opening the trap. Don't look directly at the trap!"

# This module has functions and globals to take care of some common signal
# issues. Mainly it focuses on either ignoring signals, or trapping them so
# they can be re-called or discarded later. We also have some timeout/alarm
# handlers in here.

# NOTE ON USING TIMEOUT FUNCTIONS OR DECORATORS:
#
# This module provides two main methods of adding timeout to a function.
#
# If you know that a function will always require the same timeout value, use
# the gen_timeout_decorator at the point where the function is defined,
# like so:
#   @gen_timeout_decorator(x)
#   def foo(arg0, arg1, ..., argn):
#     ...
# This will cause the function to automatically time out after x seconds
# whenever it is invoked. This does not require you to do anything special when
# calling the function.
#
# If you will not know the timeout value until runtime, you should use the
# gen_timeout_function instead, at the time when the function is called. When
# you want to call foo(arg0, arg1, ..., argn) with a timeout of 30 seconds, use:
#   gen_timeout_function(30, foo, arg0, arg1, ..., argn)
# This will execute the function, but time it out after 30 seconds. It will
# also return whatever value that foo() would have returned, or None if the
# function timed out.

import os
import signal

import gen_python_globals as g
import gen_python_print_funcs as gprint

# This list contains all the signals received during a trap period. Trap
# periods should not be nested; you should only be trapping signals for later
# use if you have an operation that needs to be atomic and uninterrupted.
global_received_signals = []

# Currently trapped signals are stored in this global list.
global_trapped_signals = []

# This variable is a global timeout indicator.
command_timed_out = 0

################################################################################
class GeneralTimeout(Exception):

  # A custom exception class, to be used with gen_timeout_handler in order to
  # make custom timeouts for operations.

  pass

################################################################################



################################################################################
def gen_timeout_handler(signo, frame):

  # This function is used to manually time operations out.

  raise GeneralTimeout()

################################################################################



################################################################################
def gen_alarm_handler(signo, frame):

  # This handler will print a time-out message, and set the global variable
  # command_timed_out to 1. We can't pass it any variables besides the default
  # two, so if you want a different signal handler that can read local variables,
  # you will need to define it yourself within the function that's using the
  # alarm.

  global command_timed_out

  command_timed_out = 1
  if not g.quiet:
    gprint.print_time("Alarm went off. command_timed_out set to 1.")

################################################################################



################################################################################
def gen_timeout_decorator(timeout_arg):

  # This function is used as a decorator, and makes it very easy to turn a
  # function into one that will automatically time itself out. In order to
  # convert a function to a timing-out function, simply place
  #   @gsig.gen_timeout_decorator(x)
  # right above the function definition. This will cause the function to time
  # out after x seconds.

  def wrap(func):
    # Test our timeout_arg in a scope where we know the function name.
    try:
      timeout_int = int(timeout_arg)
    except ValueError:
      g.print_error("Programmer error: function " + func.__name__ + " decorated with invalid timeout value in gen_timeout_decorator.")
      return None

    def time_wrapped_func(*args, **kwargs):
      original_handler = signal.signal(signal.SIGALRM,gen_timeout_handler)
      signal.alarm(timeout_int)

      try:
        rv = func(*args, **kwargs)
      except GeneralTimeout:
        g.print_error("Function " + func.__name__ + " timed out after " + str(timeout_int) + " seconds.")
        rv = None

      signal.alarm(0)
      signal.signal(signal.SIGALRM,original_handler)

      return rv

    return time_wrapped_func
  return wrap

################################################################################



################################################################################
def variable_timeout_decorator(func):

  # This function is used as a decorator, and makes it very easy to turn a
  # function into one that will automatically time itself out. In order to
  # convert a function foo() to a timing-out function, simply place
  #   @gsig.variable_timeout_decorator()
  #   def foo(arg0, arg1, ..., argn):
  #     ...
  # right above the function definition. This will create a new parm at the
  # beginning of the function, which will be the timeout value. To call foo(),
  # you need to do this:
  #   foo(timeout, arg0, arg1, ..., argn):
  # This will cause the function to time out after timeout seconds.

  def time_wrapped_func(timeout_arg, *args, **kwargs):
    # Test our timeout_arg in a scope where we know the function name.
    try:
      timeout_int = int(timeout_arg)
    except ValueError:
      g.print_error("Programmer error: function " + func.__name__ + " decorated with invalid timeout value in gen_timeout_decorator.")
      return None

    original_handler = signal.signal(signal.SIGALRM,gen_timeout_handler)
    signal.alarm(timeout_int)

    try:
      rv = func(*args, **kwargs)
    except GeneralTimeout:
      g.print_error("Function " + func.__name__ + " timed out after " + str(timeout_int) + " seconds.")
      rv = None

    signal.alarm(0)
    signal.signal(signal.SIGALRM,original_handler)

    return rv

  return time_wrapped_func

################################################################################



################################################################################
def gen_timeout_function(timeout, func, *args, **kwargs):

  # This function is used as a way to add timeout to a function when the
  # timeout value will not be known until runtime. It will return None if the
  # timeout occurred, or the function's return value otherwise.

  # Error check.
  try:
    timeout = int(timeout)
  except ValueError:
    g.print_error(str(timeout) + ", provided as timeout for " + func.__name__ + " is not a valid timeout value.")
    return None

  original_handler = signal.signal(signal.SIGALRM,gen_timeout_handler)
  signal.alarm(timeout)

  try:
    rv = func(*args, **kwargs)
  except GeneralTimeout:
    g.print_error("Function " + func.__name__ + " timed out after " + str(timeout) + " seconds.")
    rv = None

  signal.alarm(0)
  signal.signal(signal.SIGALRM,original_handler)

  return rv

################################################################################



################################################################################
def ignore_signals(signo, frame):

  # This signal handler will just ignore signals sent to it. This is used
  # mainly in preparation for exit functions.

  pass

################################################################################



################################################################################
def trap_signal_handler(signo, frame):

  # The signal handler for signals we currently wish to trap.

  global global_received_signals

  global_received_signals.append(signo)

################################################################################



################################################################################
def trap_signal(signo):

  # This function will change the signal handler of the provided signal, so that
  # it will be sent to trap_signal_handler and added to whatever list we're
  # storing signals in. We store the signal number along with its original
  # handler, so it can be restored later.
  #
  # Only use this function if you want to block all signals and then reuse or
  # discard them later. If you just want to easily change a signal handler,
  # use change_signal.

  global global_trapped_signals

  try:
    original_handler = signal.signal(signo, trap_signal_handler)
    global_trapped_signals.append((signo, original_handler))
  except RuntimeError:
    g.print_error("Cannot trap signal " + str(signo) + ". Python does not allow this signal handler to be changed.")
    return 1

  return 0

################################################################################



################################################################################
def trap_signals(signo_list):

  # This function does the same thing as trap_signal, but does it for a list
  # of signals instead.

  for signo in signo_list:
    trap_signal(signo)

  return 0

################################################################################



################################################################################
def release_signals(reraise=True):

  # This function restores all the old signal handlers of signals that were
  # trapped by trap_signal. If reraise is True, then all of the signals are
  # re-raised in turn; otherwise, the signals are discarded.

  global global_trapped_signals
  global global_received_signals

  # Restore signal handlers.
  for signo, handler in global_trapped_signals:
    try:
      signal.signal(signo, handler)
    except RuntimeError:
      g.print_error("Cannot release signal " + str(signo) + ". Python does not allow this signal handler to be changed.")

  global_trapped_signals = []

  # We need to copy the list of received signals into another list, or else
  # it's never actually going to be cleared, since we're firing off signals
  # and all that.
  local_received_signals = list(global_received_signals)
  global_received_signals = []

  # Re-raise received signals.
  if reraise:
    for sig in local_received_signals:
      os.kill(g.system_parms["pid"], sig)

  return 0

################################################################################



################################################################################
def change_signal(signo, newhandler, siglist):

  # This function will change the handler of signo to newhandler, storing the
  # old handler in siglist. The main advantage of using this function over
  # signal.signal is that if you're changing the handler of many different
  # signals, you can use restore_signals to change them all back at once.

  try:
    original_handler = signal.signal(signo, newhandler)
    siglist.append((signo, original_handler))
  except RuntimeError:
    g.print_error("Cannot trap signal " + str(signo) + ". Python does not allow this signal handler to be changed.")

  return siglist

################################################################################



################################################################################
def save_signals():

  # This function stores the current signal handler of every signal into a
  # long list and returns it.

  siglist = []
  
  for signame in dir(signal):
    # There are certain signals we don't want to try to catch. The ones we like
    # all start with SIG.
    if signame.startswith("SIG"):
      try:
        signo = getattr(signal,signame)
        sighandler = signal.getsignal(signo)
        siglist.append([signo,sighandler])
      # Not all signals work with getsignal for some reason.
      except (RuntimeError,ValueError):
        pass

  return siglist

################################################################################



################################################################################
def restore_signals(siglist):

  # This function restores all the original signal handlers in our provided
  # list.

  while siglist != []:
    signo, sighandler = siglist.pop()
    try:
      signal.signal(signo, sighandler)
    # Some signals can't be reassigned.
    except RuntimeError:
      pass

  return 0

################################################################################
