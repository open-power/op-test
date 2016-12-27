#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG 
# This is an automatically generated prolog. 
#  
# esw_dev_tools src/aipl/x86/gen_python_misc_funcs.py 1.5 
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

# This module includes a variety of functions related to paths and more.

import binascii
import datetime
import math
import os
import re
import string
import getpass
import random

import gen_python_globals as g

################################################################################

# Many functions implemented in gen_bash_misc_funcs have built-in Python
# equivalents, which will be listed here.

# calc calc_str -> print eval(calc_str)
# max a b -> max(a,b)
# change_case str 0 -> str.lower()  # str is the variable name
# change_case str 1 -> str.upper()
# add_trailing_char str char -> str + char
# remove_leading_chars str char -> str.lstrip(char)
# remove_trailing_chars str char -> str.rstrip(char)
# trim_chars str char -> str.strip(char)
# ascii_hex_to_char buffer -> binascii.unhexlify(buffer)
# absolute_dir_path(dir_path) -> os.path.abspath(dir_path)

# Date-related functions have been moved to gen_python_date_funcs.py

################################################################################
def build_cmd_buf(our_parms, additional_parms, cmd_buf):

  g.print_error("build_cmd_buf is not implemented.")
  # return cmd_buf
  pass

################################################################################



################################################################################
def comment_help_text(loc_indent, headers):

  # This function prints out some help text about comments.

  g.print_error("comment_help_text is not implemented.")
  pass

################################################################################



################################################################################
def my_read(save_IFS, IFS):

  g.print_error("my_read is not implemented.")
  # return read_buffer
  pass

################################################################################



################################################################################
def extract_date_from_status_line(line):

  g.print_error("extract_date_from_status_line is not implemented.")
  # return loc_date
  pass

################################################################################



################################################################################
def directional_egrep(file_path, line_num, search_direction):

  g.print_error("directional_egrep is not implemented.")
  # return egrep_result
  pass

################################################################################



################################################################################
def get_nearest_time_stamp(file_path, line_num, search_direction):

  g.print_error("get_nearest_time_stamp is not implemented.")
  # return time_var
  pass

################################################################################



################################################################################
def sort_by_last_time_stamp(parm_list):

  g.print_error("sort_by_last_time_stamp is not implemented.")
  # return parm_list
  pass

################################################################################



################################################################################
def create_temp_file_name(suffix=None, add_to_cleanup_list=False, delimiter="_"):

  user = getpass.getuser()
  dir = "/tmp/%s/" % user

  if not (os.path.exists(dir)): 
    rc = os.makedir(dir)
  else:
    rc = 0 

  pgm_name = os.path.basename(__file__)

  rand_num = random.randint(10000, 999999) 

  pid = os.getpid()

  temp_file_name = str(dir) + str(pgm_name) + ":pid_" + str(pid) + ":" + str(rand_num) + ":temp_db_results" 

  return rc, temp_file_name
 
################################################################################



################################################################################
def cleanup_temp_file(file_list, remove_from_global_list=False):

  g.print_error("cleanup_temp_file is not implemented.")
  # return rc
  pass

################################################################################



################################################################################
def round_up(floatnum):

  # This function rounds a floating-point number upward to the next whole
  # number.

  int_part, dec_part = math.modf(floatnum)
  if dec_part > 0:
    return int_part+1
  else:
    return int_part

################################################################################



################################################################################
def get_file_attributes(file_var_prefix, file_path):

  g.print_error("get_file_attributes is not implemented.")
  pass

################################################################################



################################################################################
def print_file_attributes(file_var_prefix, file_path, loc_file_var_suffixes=None):

  g.print_error("print_file_attributes is not implemented.")
  pass

################################################################################



################################################################################
def split_path(file_path, get_abs_dir_path=False):

  # This function takes a file path and splits it into a file name and a
  # directory path.

  # First test: have we been given an absolute path? If the first character
  # is a /, then we have.
  abs_path = (file_path[0] == '/')

  # If we haven't been given an absolute path, a little bit of work needs to
  # be done.
  full_path = file_path
  if not abs_path:
    # Are we supposed to get an absolute path?
    if get_abs_dir_path:
      full_path = os.path.abspath(file_path)
    else:
      full_path = "./" + file_path

  # Now we can separate this into the base path and the file name.
  dir_path = os.path.dirname(full_path) + "/"
  base_name = os.path.basename(full_path)

  return (dir_path, base_name)

################################################################################



################################################################################
def valid_write_dir(dir_path):

  # This function returns True if dir_path is an existing directory and can be
  # written to.

  if not os.path.isdir(dir_path):
    g.print_error("Directory \"" + dir_path + "\" does not exist.")
    return False
  elif not os.access(dir_path, os.W_OK | os.X_OK):
    g.print_error("Directory \"" + dir_path + "\" is not writeable for your userid.")
    return False

  return True

################################################################################



################################################################################
def get_real_caller_func():

  g.print_error("get_real_caller_func is not implemented.")
  # return funcname
  pass

################################################################################



################################################################################
def check_pts_group_membership(group_name, group_cell, userid, print_err):

  g.print_error("check_pts_group_membership is not implemented.")
  # return rc
  pass

################################################################################



################################################################################
def max_key(lst, keyfunc=None):

  # This function will find the maximum element in a list, based on applying
  # a key function to each one. max() can do this itself in later versions of
  # Python, but not in 2.4.3.

  if keyfunc is None:
    return max(lst)

  max_val = None
  max_item

  for item in lst:
    if max_val is None:
      max_val = keyfunc(item)
      max_item = item
    else:
      current_val = keyfunc(item)
      if max_val < current_val:
        max_val = current_val
        max_item = item

  return max_item

################################################################################



################################################################################
def zip_long(filler,*lists):

  # This function zips together many lists. If one list runs out, the zipping
  # continues, with the filler item taking the place of the exhausted list.
  # Used for col_wrap.

  final_list = []

  max_len = max(map(len,lists))

  # Do this once for every entry in the longest list.
  for i in range(max_len):
    list_entry = []
    # Look at every list and grab entry i.
    for lst in lists:
      # Catch an IndexError. If we do, then this list has run out of things.
      try:
        list_entry.append(lst[i])
      except IndexError:
        list_entry.append(filler)
    final_list.append(list_entry)

  return final_list

################################################################################



################################################################################
def enum(*sequential, **named):

  # This function basically allows for enum support, since Python does not
  # support them until 3.4. Code borrowed from StackOverflow.
  #
  # An enum can be created like so:
  #   new_enum = enum('zero', 'one, 'two'='TWO')
  # And called like this:
  #   new_enum.zero

  enums = dict(zip(sequential, range(len(sequential))), **named)
  reverse = dict((value, key) for key, value in enums.iteritems())
  enums['reverse_mapping'] = reverse
  return type('Enum', (), enums)

################################################################################
