#!/usr/bin/python

# This module includes various useful string functions.

import string
import textwrap

import gen_python_globals as g
import gen_python_misc_funcs as gmisc

################################################################################
def find_char(char, buffer):

  # Search a string buffer for a given character. Return 0 if it exists, and 1
  # if it does not.

  if buffer.find(char) >= 0:
    return 0
  else:
    return 1

################################################################################



################################################################################
def munch(buffer, charset=string.whitespace):

  # Search a string buffer for a given character set. Return the portion of the
  # string before and after the first instance of any character (or multiple
  # characters) in that set. The default behavior is to munch on white space.
  # This is basically strtok but it returns the remainder too.

  # First, we need to look for a starting point.
  beginmark = -1
  for i in range (0,len(buffer)):
    if buffer[i] not in charset:
      beginmark = i
      break

  # Is our string nothing but our delimiters?
  if beginmark == -1:
    return("","")

  # Now we start the string munching.
  startmark = -1
  endmark = -1

  for i in range(beginmark,len(buffer)):
    if buffer[i] in charset:
      startmark = i
      break

  # In case there are no instances of the character.
  if startmark == -1:
    return (buffer[beginmark:],"")

  for i in range(startmark,len(buffer)):
    if buffer[i] not in charset:
      endmark = i
      break

  # With our marks found, let's decide what to return.
  if endmark == -1:
    return (buffer[beginmark:startmark],"")

  # Munched portion, then remaining string.
  return (buffer[beginmark:startmark],buffer[endmark:])

################################################################################



################################################################################
def rmunch(buffer, charset=string.whitespace):

  # Search a string buffer for a given character set. Return the portion of the
  # string before and after the last instance of any character (or multiple
  # characters) in that set. The default behavior is to munch on white space.
  # This is basically strtok backwards but it returns the remainder too.

  # First, we need to look for a starting point.
  beginmark = -1
  for i in range (len(buffer)-1,-1,-1):
    if buffer[i] not in charset:
      beginmark = i
      break

  # Is our string nothing but our delimiters?
  if beginmark == -1:
    return("","")

  # Now we start the string munching.
  startmark = -1
  endmark = -1

  for i in range(beginmark,-1,-1):
    if buffer[i] in charset:
      endmark = i
      break

  # In case there are no instances of the character.
  if endmark == -1:
    return ("",buffer[:beginmark+1])

  for i in range(endmark,-1,-1):
    if buffer[i] not in charset:
      startmark = i
      break

  # With our marks found, let's decide what to return.
  if startmark == -1:
    return ("",buffer[endmark+1:beginmark+1])

  # Remaining string, then munched portion.
  return (buffer[:startmark+1],buffer[endmark+1:beginmark+1])

################################################################################



################################################################################
def filepath_to_varname(filepath):

  # This function takes a file path (or any string, really) and converts any
  # punctuation or whitespace to underscores.

  # Copy the string.
  varname = filepath[:]

  # Create a translator. Translate all punctuation and whitespace into _.
  badchars = string.punctuation + string.whitespace
  underscores = "_" * len(badchars)
  underscore_replace = string.maketrans(badchars,underscores)

  varname = varname.translate(underscore_replace)
  return varname

################################################################################



################################################################################
def col_wrap(strlist, widthlist, rjustify=False, indent=0, separation=1):

  # This function takes an arbitrary number of strings, and turns them into
  # well-formatted, text-wrapped columns.
  #
  # strlist - A list of strings.
  # widthlist - The width of each column, corresponding to strlist.
  # rjustify - A list indicating which columns should be right-justified. If
  #            not supplied, no columns are right-justified.
  # indent - How much the first column should be indented by.
  # separation - How much each column should be separated by.

  # Error checks.
  if len(strlist) != len(widthlist):
    print_error("Length of string list and width list must match in col_print.")
    return None

  try:
    widthlist = map(int,widthlist)
    for width in widthlist:
      if width <= 0:
        print_error("Widths must be 1 or greater in col_print.")
        return None
  except ValueError:
    print_error("Widths must be integers in col_print.")
    return None

  if rjustify is False or rjustify is True:
    rjustify = [rjustify] * len(strlist)

  wrapped_col_list = []

  # The first thing we need to do is wrap each string to the appropriate width.
  for strng, width in zip(strlist,widthlist):
    wrapped_str = textwrap.fill(strng,width)
    wrapped_str_list = wrapped_str.split("\n")
    wrapped_col_list.append(wrapped_str_list)

  # We now have our wrapped columns in a list of lists. Now we need to
  # rearrange them into actual columns.

  wrapped_string = ""

  # First, we need to establish a format string to use on each line.
  format_str = "%" + str(indent) + "s"
  for i in range(len(strlist)):
    if rjustify[i]:
      format_str += "%" + str(widthlist[i]) + "s"
    else:
      format_str += "%-" + str(widthlist[i]) + "s"
    if i+1 < len(strlist):
      format_str += "%" + str(separation) + "s"
  format_str += "\n"

  # Next, we need to place our string information inside the formatted string,
  # adding it to our overall wrapped string. We do this by assembling a tuple
  # of our elements to use for formatting.
  max_len = max(map(len,wrapped_col_list))

  for i in range(max_len):
    format_tuple = []
    for j in range(len(wrapped_col_list)):
      format_tuple.append("")
      # Do a try/except, in case one string runs out early.
      try:
        format_tuple.append(wrapped_col_list[j][i])
      except:
        format_tuple.append("")

    # Convert to tuple and format.
    format_tuple = tuple(format_tuple)
    line_str = format_str % format_tuple
    wrapped_string += line_str

  return wrapped_string[:-1]

################################################################################
