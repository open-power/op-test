#!/usr/bin/python

# This module contains general options processing functions for a Python
# program.

import getopt
import pwd
import string

import gen_python_globals as g

# The default options. Can add to this list in the main
# program, or remove from it.
shortopts = ""
longopts = ["help"]
boolopts = []
varopts = []
funcopts = []
posparms = []
optparms = []

################################################################################
def bool_convert(boolval):

  # A handy function that will translate a number of different values into
  # either 0 or 1. Used for boolean variables. If any non-recognized value is
  # passed in, then we pass it to the bool() function.

  if isinstance(boolval, basestring) and boolval.lower() in ("n", "no", "f", "false", "0", "none"):
    return 0
  else:
    boolval = bool(boolval)
    if boolval:
      return 1
    else:
      return 0

################################################################################



################################################################################
def gen_print_parms():

  # This function prints out all positional parameters in an easy-to-read
  # format. Used whenever the programmer wants.

  global posparms
  global optparms

  for name, len, default_val in posparms:
    print_global(name)

  for name, len, default_val in optparms:
    print_global(name)

  return 0

################################################################################



################################################################################
def get_options(args):

  # The main function to parse options. Many of these are generated
  # automatically from a few values provided.

  global shortopts
  global longopts
  global boolopts
  global varopts
  global funcopts
  global posparms
  global optparms

  try:
    opts, parms = getopt.gnu_getopt(args, shortopts, longopts)
  except getopt.GetoptError:
    g.print_error("Invalid option flag(s) specified.")
    return 1

  # Process command line options. We have some short-circuiting present.
  for opt, arg in opts:
    found = False
    if opt == "--help":
      return 2
    if boolopts != []:
      # Process all boolean options here.
      for flagname, var, default_val, needarg in boolopts:
        if opt == flagname:
          if needarg:
            g.global_vars[var] = bool_convert(arg)
          else:
            g.global_vars[var] = not default_val
          found = True
          break
    if not found and varopts != []:
      # Process all variable-setting options here.
      for flagname, var, default_val in varopts:
        if opt == flagname:
          g.global_vars[var] = arg
          found = True
          break
    if not found and funcopts != []:
      # Process all function-executing options here.
      for flagname, func in funcopts:
        if opt == flagname:
          func()
          break

  # Process command line parameters. We used to pop arguments from these lists,
  # but keeping track of positions with integers is way faster.
  argn = 0; amax = len(parms); parmn = 0; pmax = len(posparms)
  while argn < amax and parmn < pmax:
    # Go through the designated parms in order and assign values.
    varname, varlen, default_val = posparms[parmn]
    if varlen == 1:
      g.global_vars[varname] = parms[argn]
    elif varlen == 0:
      g.global_vars[varname] = parms[argn:amax]
    else:
      g.global_vars[varname] = parms[argn:argn+varlen]
    if varlen == 0:
      argn = amax
      # Checking for a programmer error.
      if parmn+1 < pmax or optparms != []:
        print "Programmer error: cannot allow additional parameters after a parm list takes all remaining arguments."
        return 1
    else:
      argn += varlen
    parmn += 1

  # If there are any mandatory parameters that have gone unassigned,
  # raise an error.
  if parmn < pmax:
    g.print_error("Mandatory parameter not specified.")
    return 1

  # Process optional command line parameters.
  parmn = 0; pmax = len(optparms)
  while argn < amax and parmn < pmax:
    # Go through the designated parms in order and assign values.
    varname, varlen, default_val = optparms[parmn]
    if varlen == 1:
      g.global_vars[varname] = parms[argn]
    elif varlen == 0:
      g.global_vars[varname] = parms[argn:amax]
    else:
      g.global_vars[varname] = parms[argn:argn+varlen]
    if varlen == 0:
      argn = amax
      # Checking for a programmer error.
      if parmn+1 < pmax:
        g.print_error("Programmer error: cannot allow additional parameters after a parm list takes all remaining arguments.")
        return 1
    else:
      argn += varlen
    parmn += 1

  # If there are any command line parameters left, not a problem, just don't
  # use them.

  return 0

################################################################################



# The below functions handle the printing of help messages.



################################################################################
def print_usage():

  # This function prints an example usage of the given program.
  # <program_name> [OPTIONS] EACH PARAMETER CAPITALIZED LIKE THIS

  global shortopts
  global longopts
  global posparms
  global optparms

  # Program name and options.
  printstr = "Usage: " + g.program_name
  if shortopts != "" or longopts != []:
    printstr += " [OPTIONS]"

  # Each mandatory parameter.
  for paramname, paramlen, default_val in posparms:
    printstr += " " + paramname.upper()
    # Number of arguments.
    if paramlen > 1:
      printstr += "(x" + str(paramlen) + ")"
    elif paramlen == 0:
      printstr += "..."

  # Each optional parameter.
  for paramname, paramlen, default_val in optparms:
    printstr += " [" + paramname.upper()
    # Number of arguments.
    if paramlen > 1:
      printstr += "(x" + str(paramlen) + ")"
    elif paramlen == 0:
      printstr += "..."
    printstr += "]"

  print printstr
  print

  return 0

################################################################################



################################################################################
def print_parm(paramname, desc, exvals="", default=True, loc_col1_indent=2, loc_col1_width=33):

  # This function automatically prints out help information for a given
  # parameter. exvals allows the programmer to specify example values for the
  # parameter. Setting default to False will suppress the printout of the
  # default value. The program automatically determines the number of arguments
  # it takes, and whether or not it's optional.

  # First we search for the parameter name in our list. If it's not there, throw
  # an error.
  parm, opt = parm_search(paramname)
  if parm == None:
    g.print_error("Programmer error: attempting to print help for parameter " + paramname + " but this parameter does not exist.")
    return 1

  # Add example values, if necessary.
  if exvals != "":
    paramname += " (ex: " + exvals + ")"

  descheader = ""
  # Is the parameter optional?
#  if opt:
#    descheader += "Optional. "

  # Does this parameter take multiple arguments?
  if parm[1] == 0:
    descheader += "Takes all remaining arguments in the command line. "
  elif parm[1] != 1:
    descheader += "Takes " + str(parm[1]) + " arguments. "

  descfooter = ""
  # Print out the default value, if necessary.
  if default:
    descfooter += " The default value is \"" + str(parm[2]) + "\"."

  format_string = "%" + str(loc_col1_indent) + "s%-" + str(loc_col1_width) + "s%s"
  print format_string % ("", paramname, descheader + desc + descfooter)

  return 0

################################################################################



################################################################################
def print_opt(optname, desc, exvals="", default=True, loc_col1_indent=2, loc_col1_width=33):

  # This function automatically prints out help information for a given option.
  # exvals allows the programmer to specify example values for the option; if
  # the option was specified as boolean by using add_bool_option, <y/n> will
  # be printed automatically unless another value is passed in. Setting default
  # to False will suppress the printout of the default value.

  # First we search for the parameter name in our list. If it's not there, throw
  # an error.
  option = opt_search(optname)
  if option == None:
    g.print_error("Programmer error: attempting to print help for option " + optname + " but this option does not exist.")
    return 1

  # Determine what kind of option this is, by its length.
  is_bool = len(option) == 4
  is_var = len(option) == 3
  is_func = len(option) == 2

  # Get the appropriate data out of the thing.
  flag = option[0]
  if is_func:
    default_val = ""
    default = False
  else:
    default_val = option[2]

  # Add example values, if necessary.
  if exvals != "":
    flag += "=<" + exvals + ">"
  elif is_bool:
    flag += "=<y/n>"

  descfooter = ""
  # Print out the default value, if necessary.
  if default:
    if is_bool:
      if default_val == 0:
        descfooter += " The default value is \"n\"."
      else:
        descfooter += " The default value is \"y\"."
    else:
      descfooter += " The default value is \"" + str(default_val) + "\"."

  format_string = "%" + str(loc_col1_indent) + "s%-" + str(loc_col1_width) + "s%s"
  print format_string % ("", flag, desc + descfooter)

  return 0

################################################################################



# The below functions are used for creating new option flags, and can be used
# in any order. Option flags are considered to be implicitly optional, so if a
# flag is required for the program, the programmer will have to handle that
# manually.



################################################################################
def add_opt_flag(flagname, needarg):

  # This function will determine whether a flag is a long or short flag, then
  # add it to the current list, assuming it doesn't already exist there. It
  # returns the - or -- flag that was added. Returns a 1 error code if the
  # option has already been added.

  global shortopts
  global longopts

  # A one-character flag is a short flag.
  flagstr = ""
  fullflag = flagname
  short = False
  if len(flagname) == 1:
    short = True

  # Make the corret append.
  if short:
    flagstr = "-" + flagname
  else:
    flagstr = "--" + flagname

  # Add it to the appropriate list.
  if short:
    if flagname in shortopts:
      return (1, None)
    else:
      if needarg:
        fullflag += ":"
      shortopts += fullflag
  else:
    if needarg:
      fullflag += "="
    if fullflag in longopts:
      return (1, None)
    else:
      longopts += [fullflag]

  return (0, flagstr)

################################################################################



################################################################################
def add_bool_option(flagname, default_val=False, alt_var=None):

  # Creates an argument-accepting option flag.
  # Creates a boolean variable associated with the flag.

  global boolopts

  # Convert the default value to 0 or 1.
  default_val = bool_convert(default_val)

  # Create a new variable in global_vars and assign its value.
  var = flagname
  if alt_var != None:
    var = str(alt_var)
  g.global_vars[var] = default_val

  # Add it to our options list.
  retval, flagstr = add_opt_flag(flagname, True)
  if retval == 1:
    g.print_error("Option " + flagname + " already exists in program, cannot be added again.")
    return 1
  boolopts += [[flagstr, var, default_val, True]]

  return 0

################################################################################



################################################################################
def add_var_option(flagname, default_val=None, alt_var=None):

  # Creates an argument-accepting option flag.
  # Creates a general variable associated with the flag.

  global varopts

  # Create a new variable in global_vars and assign its value.
  var = flagname
  if alt_var != None:
    var = str(alt_var)
  g.global_vars[var] = default_val

  # Add it to our options list.
  retval, flagstr = add_opt_flag(flagname, True)
  if retval == 1:
    g.print_error("Option " + flagname + " already exists in program, cannot be added again.")
    return 1
  varopts += [[flagstr, var, default_val]]

  return 0

################################################################################



################################################################################
def add_bool_flag(flagname, default_val=False, alt_var=None):

  # Create an argument-free option flag.
  # Creates a boolean variable associated with the flag.
  # Using this flag on the command line sets the value of var to the opposite of
  # default_val.

  global boolopts

  # Convert the default value to 0 or 1.
  default_val = bool_convert(default_val)

  # Create a new variable in global_vars and assign its value.
  var = flagname
  if alt_var != None:
    var = str(alt_var)
  g.global_vars[var] = default_val

  # Add it to our options list.
  retval, flagstr = add_opt_flag(flagname, False)
  if retval == 1:
    g.print_error("Option " + flagname + " already exists in program, cannot be added again.")
    return 1
  boolopts += [[flagstr, var, default_val, False]]

  return 0

################################################################################



################################################################################
def add_func_flag(flagname, func):

  # Creates an argument-free option flag.
  # Associates a function with this flag, to be executed if the flag is present.

  global funcopts

  # Add it to our options list. There's no variable to assign since there's no
  # single value to store.
  retval, flagstr = add_opt_flag(flagname, False)
  if retval == 1:
    g.print_error("Option " + flagname + " already exists in program, cannot be added again.")
    return 1
  funcopts += [[flagstr, func]]

  return 0

################################################################################



################################################################################
def boolean_list(boollist):

  # This function takes a space-separated list of boolean option names and
  # creates variables for each one of them. Their default value is False, and
  # they are optional by default as well.

  global boolopts

  if boollist == None or boollist == "":
    return 0

  boolvars = string.split(boollist)
  for boolvar in boolvars:
    if add_bool_option(boolvar) == 1:
      return 1

  return 0

################################################################################



################################################################################
def longoptions(optlist):

  # This function takes a space-separated list of option names and processes
  # them. This function should never be used before boolean_list. If a provided
  # option was used in boolean_list, then it will simply change the default
  # value.

  global boolopts
  global varopts

  if optlist == None or optlist == "":
    return 0

  # Parse all options.
  allopts = string.split(optlist)

  # Parse each option.
  for opt in allopts:
    # We need to check and see if a default value was provided.
    splitopt = string.split(opt,":=")
    if len(splitopt) == 2:
      optname, optval = splitopt
    elif len(splitopt) == 1:
      optname = splitopt[0]
      optval = None

    # Scan the list of boolean options, to see if that one is there.
    searchopt = None
    for boolopt in boolopts:
      if boolopt[0] == optname or boolopt[0] == "-"+optname or boolopt[0] == "--"+optname:
        searchopt = boolopt
        break

    if searchopt == None:
      # It's not there, so just add it as a var option.
      add_var_option(optname, default_val=optval)
    else:
      # Change the default and current value of the variable.
      boolval = bool_convert(optval)
      searchopt[2] = boolval
      g.global_vars[optname] = boolval

  return 0
################################################################################



################################################################################
def opt_search(optname):

  # Search for an existing option and retrieve all information on it.
  # Returns None if not found. The length of the list that's returned tells us
  # what kind of option it is (bool, var, func).

  global boolopts
  global varopts
  global funcopts

  for opt in boolopts:
    if opt[0] == optname or opt[0] == "-"+optname or opt[0] == "--"+optname:
      return opt

  for opt in varopts:
    if opt[0] == optname or opt[0] == "-"+optname or opt[0] == "--"+optname:
      return opt

  for opt in funcopts:
    if opt[0] == optname or opt[0] == "-"+optname or opt[0] == "--"+optname:
      return opt

  return None

################################################################################



# The below functions are used for adding positional parameters to your program,
# and must be called in the order that you wish for the positional parameters
# to appear. Unlike option flags, these can be specified as either optional or
# mandatory. Additionally, all optional parameters will be processed last and
# so must go at the end of the command line.



################################################################################
def add_pos_parm(var, default_val=None, optional=True):

  # Creates a positional parameter.
  # Creates a general variable associated with the parameter.
  # Can be specified as optional, is not optional by default.
  # If not optional, adding a custom default value is a bit nonsensical.

  global posparms
  global optparms

  g.global_vars[var] = default_val
  if optional:
    optparms += [[var, 1, default_val]]
  else:
    posparms += [[var, 1, default_val]]

  return 0

################################################################################



################################################################################
def add_pos_parm_list(varlist, len=0, default_val=[], optional=True):

  # Creates a list of positional parameters.
  # Creates a general list variable associated with the list of parameters.
  # Can be specified as optional, is not optional by default.
  # If a list length is provided, the list will accept exactly len arguments.
  # If len = 0, then the list will acquire all remaining arguments not already
  # processed. If you use this function with len = 0, this should be the last
  # add_pos_parm function called.

  global posparms
  global optparms

  g.global_vars[varlist] = default_val
  if optional:
    optparms += [[varlist, len, default_val]]
  else:
    posparms += [[varlist, len, default_val]]

  return 0

################################################################################



################################################################################
def positional_parm_names(varlist):

  # Takes a string that represents all positional parameters, separated by
  # spaces, and creates one parm for each. Currently creates them with no
  # default values, and optional.

  global optparms

  if varlist == None or varlist == "":
    return 0

  allparms = string.split(varlist)
  for parm in allparms:
    if add_pos_parm(parm) == 1:
      return 1

  return 0

################################################################################



################################################################################
def parm_search(parmname):

  # Search for an existing parameter and retrieve all information on it.
  # Returns None if not found.

  global posparms
  global optparms

  for parm in posparms:
    if parm[0] == parmname:
      return (parm, False)

  for parm in optparms:
    if parm[0] == parmname:
      return (parm, True)

  return (None, None)

################################################################################
