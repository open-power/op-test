#!/usr/bin/python

# This module includes date- and time-related functions. The exception is
# the sprint_time() and print_time() functions, as those are used so
# universally that they are kept in gen_python_globals.

# A MyDate class is included in this file, because it makes a lot of things
# much easier (printing, adding, subtracting, getting hours, etc). The
# function date_math is now obsolete as a result, though date_subtract is
# still implemented.

import commands
import datetime
import math
import os
import re
import string
import time

import gen_python_globals as g
import gen_python_obj_funcs as gobj
import gen_python_string_funcs as gstr

# Some regex variables.
valid_alpha_time_zone_regex = "[A-Z]{3}"
valid_year_regex = "[0-9]{4}"
valid_month_regex = "(0[1-9]|1[0-2])"
valid_day_of_month_regex = "([0][1-9]|[12][0-9]|3[0-1])"
valid_hour_24_regex = "([0-1][0-9]|[2][0-3])"
valid_minute_regex = "([0-5][0-9])"
valid_second_regex = "([0-5][0-9])"
valid_status_date_regex = r"#\(" + valid_alpha_time_zone_regex + r"\) " + valid_year_regex + "/" + valid_month_regex + "/" + valid_day_of_month_regex + " " + valid_hour_24_regex + ":" + valid_minute_regex + ":" + valid_second_regex

################################################################################
class MyDate(gobj.GenPythonObject):

  # Start MyDate definition.

  # This is an intelligent date object that can print itself, perform math on
  # itself, return individual components and more. All arguments are
  # represented as ints internally, with the exception of time_zone. If any
  # attribute is changed, the MyDate object adjusts itself to be internally
  # consistent.

  # A set of vital attributes that cannot be deleted from an object.
  required_atts = set(("time_zone", "day_name", "month_name", "year", "month", "day", "hour", "minute", "second", "day_of_week", "day_of_year", "dst", "epoch", "microseconds"))

  # A set of attributes that, if changed, requires a readjustment of the MyDate
  # object, to ensure internal consistency.
  adjust_atts = set(("month_name", "year", "month", "day", "hour", "minute", "second", "day_of_week", "day_of_year", "epoch"))

#*******************************************************************************
  def __init__(self, arg=None, sql=False):

    # We can be given either an integer (the number of epoch seconds) or a
    # string (in our preferred format or SQL format). We'll assume that it's
    # epoch seconds, either in int or string format, and if Python throws an
    # error we'll try it as a string. If arg=None, then we'll make a MyDate
    # object that corresponds to right now.

    # We have to start with the epoch seconds. Once we have that in some way,
    # the process of creating the object is always the same.
    if arg is None:
      # If we were given no argument, just use now.
      current_time = time.time()
      microseconds, epoch = math.modf(current_time)
      epoch = int(epoch)
      microseconds = int(round(microseconds,6) * (10**6))
    # In the case where we were given an argument.
    else:
      # Try to process it as an int or float.
      try:
        microseconds, epoch = math.modf(arg)
        epoch = int(epoch)
        microseconds = int(round(microseconds,6) * (10**6))
      # If that fails, try to process it as a string.
      except ValueError:
        if not sql:
          epoch = date_to_seconds(arg)
          microseconds = 0
        else:
          # The SQL case is much more complicated.
          microseconds = int(gstr.rmunch(arg,".")[1])
          microseconds = float("0." + microseconds)
          microseconds = int(round(microseconds,6) * (10**6))
          sql_dummy_str = "#(CDT) " + sql_date_to_std(arg)
          epoch = date_to_seconds(sql_dummy_str)

    # Now we use this function to set all of the time data.
    self.apply_date_from_epoch(epoch, microseconds)

#*******************************************************************************

  # __setattr__ and all needed support functions.

#*******************************************************************************
  def __setattr__(self, name, value):

    # A custom setter. We do this to ensure that the date and the seconds are
    # internally consistent.

    name = name.lower()
    if name in MyDate.adjust_atts:
      self.adjust_date(name, value)
    elif name in ["day_name","day_of_week"]:
      raise AttributeError(self.__class__.__name__ + "." + name + " cannot be directly modified (desired behavior cannot be known)")
    else:
      self.__dict__[name] = value

#*******************************************************************************



#*******************************************************************************
  def apply_date_from_epoch(self, epoch, microseconds):

    # This function takes in the epoch seconds and microseconds, and sets all
    # of the MyDate attributes based on those values.

    # A time tuple contains as much broken-down information as we can get,
    # almost. We just need the time zone, the day name, the month name, and
    # the epoch seconds.
    now_tuple = time.localtime(epoch)
    time_zone = time.strftime("%Z", now_tuple)
    day_name = time.strftime("%A", now_tuple)
    month_name = time.strftime("%B", now_tuple)
    year, month, day, hour, minute, second, day_of_week, day_of_year, dst = now_tuple

    # Now we actually set all the attributes. We need to directly modify the
    # __dict__ because we're overloading __setattr__.
    self.__dict__["epoch"] = epoch
    self.__dict__["microseconds"] = microseconds
    self.__dict__["time_zone"] = time_zone
    self.__dict__["day_name"] = day_name
    self.__dict__["month_name"] = month_name
    self.__dict__["year"] = year
    self.__dict__["month"] = month
    self.__dict__["day"] = day
    self.__dict__["hour"] = hour
    self.__dict__["minute"] = minute
    self.__dict__["second"] = second
    self.__dict__["day_of_week"] = day_of_week
    self.__dict__["day_of_year"] = day_of_year
    self.__dict__["dst"] = dst

#*******************************************************************************



#*******************************************************************************
  def convert_month_name_to_date(self, value):

    # This function converts the name of a month into a number.

    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    month_num = months.index(value) + 1
    return month_num

#*******************************************************************************



#*******************************************************************************
  def convert_day_num_to_date(self, value):

    # This function converts the day_of_year attribute into month and day.
    leap_year = self.year % 4 == 0 and (self.year % 100 != 0 or self.year % 400 == 0)
    month_vals = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_num = 1

    for i, days in enumerate(month_vals):
      if i == 1 and leap_year:
        days += 1
      if value > days:
        value -= days
        month_num += 1
      else:
        break

    self.__dict__["month"] = month_num
    self.__dict__["day"] = value

#*******************************************************************************



#*******************************************************************************
  def verify_day_month_year(self, name, value):

    # Since considerations for different month lengths and leap years is pretty
    # complicated, we're giving it all its own function. In this function, we
    # assume the other two values were valid before our attempted change.

    # Determine if it's a leap year.
    if name == "year":
      leap_year = value % 4 == 0 and (value % 100 != 0 or value % 400 == 0)
    else:
      leap_year = self.year % 4 == 0 and (self.year % 100 != 0 or self.year % 400 == 0)

    # Case 1: year. We don't need to check much.
    if name == "year":
      if self.month == 2 and self.day == 29:
        if leap_year:
          return True
        else:
          return False
      else:
        return True
    # Case 2: month. See if we're violating the day, or a leap year.
    if name == "month":
      if self.day == 31:
        if value in set((1, 3, 5, 7, 8, 10, 12)):
          return True
        else:
          return False
      elif self.day == 30:
        if value != 2:
          return True
        else:
          return False
      elif self.day == 29:
        if value != 2:
          return True
        elif leap_year:
          return True
        else:
          return False
      else:
        return True
    # Case 3: day. Treated generally the same as case 2.
    if name == "day":
      if value == 31:
        if self.month in set((1, 3, 5, 7, 8, 10, 12)):
          return True
        else:
          return False
      elif value == 30:
        if self.month != 2:
          return True
        else:
          return False
      elif value == 29:
        if self.month != 2:
          return True
        elif leap_year:
          return True
        else:
          return False
      else:
        return True

    # Default case. We should not get here.
    return False

#*******************************************************************************



#*******************************************************************************
  def verify_date_value(self, name, value):

    # This function checks to make sure that we are setting a MyDate attribute
    # to an appropriate value. If it's valid, we return a slightly cleaner
    # version of the value. Otherwise, we raise an exception.

    att_err_string = "Invalid value for " + self.__class__.__name__ + "." + str(name) + ": " + str(value)

    # Catch all possible invalid values in this try/except. This also lets us
    # throw our own ValueErrors if we have invalid values.
    try:
      if name == "day_name":
        if value.lower() in set(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")):
          return value.capitalize()
        else:
          raise ValueError
      if name == "month_name":
        if value.lower() in set(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")):
          return value.capitalize()
        else:
          raise ValueError
      if name == "year":
        if int(value) >= 1969:
          if self.verify_day_month_year(name, int(value)):
            return int(value)
          else:
            att_err_string += " (incompatible with month = " + str(self.month) + " and day = " + str(self.day) + ")"
            raise ValueError
        else:
          att_err_string += " (year must be 1969 or greater, after the epoch)"
          raise ValueError
      if name == "month":
        if int(value) >= 1 and int(value) <= 12:
          if self.verify_day_month_year(name, int(value)):
            return int(value)
          else:
            att_err_string += " (incompatible with year = " + str(self.year) + " and day = " + str(self.day) + ")"
        else:
          raise ValueError
      if name == "day":
        if int(value) >= 1 and int(value) <= 31:
          if self.verify_day_month_year(name, int(value)):
            return int(value)
          else:
            att_err_string += " (incompatible with year = " + str(self.year) + " and month = " + str(self.month) + ")"
        else:
          raise ValueError
      if name == "hour":
        if int(value) >= 0 and int(value) <= 23:
          return int(value)
        else:
          raise ValueError
      if name == "minute":
        if int(value) >= 0 and int(value) <= 59:
          return int(value)
        else:
          raise ValueError
      if name == "second":
        if int(value) >= 0 and int(value) <= 59:
          return int(value)
        else:
          raise ValueError
      if name == "day_of_week":
        if int(value) >= 0 and int(value) <= 6:
          return int(value)
        else:
          raise ValueError
      if name == "day_of_year":
        if self.year % 4 == 0 and (self.year % 100 != 0 or self.year % 400 == 0):   # Leap year?
          if int(value) >= 1 and int(value) <= 366:
            return int(value)
          else:
            raise ValueError
        else:
          if int(value) >= 1 and int(value) <= 365:
            return int(value)
          else:
            att_err_string += " (incompatible with year = " + str(self.year) + ")"
            raise ValueError
      if name == "epoch":
        if value >= 0:
          return value
        else:
          raise ValueError
    except ValueError:
      # Reject this exception and substitute our own.
      raise AttributeError(att_err_string)

    # It shouldn't be possible to get here.
    raise AttributeError(att_err_string)

#*******************************************************************************



#*******************************************************************************
  def adjust_date(self, name, value):

    # This function is called whenever a key MyDate attribute is changed. It
    # adjusts the other attributes so that the internal date is consistent.

    # Verify that we were given an acceptable value.
    value = self.verify_date_value(name, value)

    # What we do depends on the attribute that was changed.
    if name == "epoch":
      # If we changed the epoch seconds, adjust the microseconds if necessary
      # and then change all other values based on that.
      microseconds, epoch = math.modf(value)
      epoch = int(epoch)
      if microseconds < 0.000001 and microseconds > -0.000001:
        microseconds = self.microseconds
      else:
        microseconds = int(round(microseconds,6) * (10**6))
    else:
      # Otherwise, we need to derive the new epoch seconds, then reload the
      # data based on that.
      self.__dict__[name] = value
      if name == "month_name":
        self.__dict__["month"] = self.convert_month_name_to_date(value)
      elif name == "day_of_year":
        self.convert_day_num_to_date(value)
      epoch = date_to_seconds(self.__str__())
      microseconds = self.microseconds

    # Now reset the date information.
    self.apply_date_from_epoch(epoch, microseconds)

#*******************************************************************************

  # Deleter (we need to restrict a lot of deletions).

#*******************************************************************************
  def __delattr__(self, name):

    # A custom deleter that prevents the user from deleting vital attributes.

    if name in MyDate.required_atts:
      raise AttributeError(name + " is a vital " + self.__class__.__name__ + " attribute and cannot be deleted")

    gobj.GenPythonObject.__delattr__(self, name)

#*******************************************************************************

  # Print functions.

#*******************************************************************************
  def __str__(self):

    # Prints out a string representation of the MyDate object, in our preferred
    # format.

    return "#(%s) %s/%s/%s %s:%s:%s" % (self.time_zone, str(self.year).zfill(4), str(self.month).zfill(2), str(self.day).zfill(2), str(self.hour).zfill(2), str(self.minute).zfill(2), str(self.second).zfill(2))

#*******************************************************************************



#*******************************************************************************
  def __repr__(self):

    # Prints out a brief object representation of the date, including the SQL
    # representation of the date.

    return "<" + self.__class__.__name__ + " object at " + hex(id(self)) + ": '" + self.to_sql() + "'>"

#*******************************************************************************



#*******************************************************************************
  def to_sql(self):

    # Prints out a string representation of the MyDate object, in SQL format.

    return "%s-%s-%s-%s.%s.%s.%s" % (str(self.year).zfill(4), str(self.month).zfill(2), str(self.day).zfill(2), str(self.hour).zfill(2), str(self.minute).zfill(2), str(self.second).zfill(2), str(self.microseconds).zfill(6))

#*******************************************************************************

  # Comparison functions.

#*******************************************************************************
  def __lt__(self, other):

    # Less than (<). We can just compare epoch seconds and microseconds.

    try:
      if self.epoch < other.epoch:
        return True
      elif self.epoch > other.epoch:
        return False

      if self.microseconds < other.microseconds:
        return True

      return False
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************



#*******************************************************************************
  def __le__(self, other):

    # Less than or equal to (<=).

    try:
      if self.epoch < other.epoch:
        return True
      elif self.epoch > other.epoch:
        return False

      if self.microseconds <= other.microseconds:
        return True

      return False
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************



#*******************************************************************************
  def __eq__(self, other):

    # Equal to (==).

    try:
      return self.epoch == other.epoch and self.microseconds == other.microseconds
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************



#*******************************************************************************
  def __ne__(self, other):

    # Not equal to (!=).

    try:
      return self.epoch != other.epoch or self.microseconds != other.microseconds
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************



#*******************************************************************************
  def __gt__(self, other):

    # Greater than (>).

    try:
      if self.epoch > other.epoch:
        return True
      elif self.epoch < other.epoch:
        return False

      if self.microseconds > other.microseconds:
        return True

      return False
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************



#*******************************************************************************
  def __ge__(self, other):

    # Greater than or equal to (>=).

    try:
      if self.epoch > other.epoch:
        return True
      elif self.epoch < other.epoch:
        return False

      if self.microseconds >= other.microseconds:
        return True

      return False
    except AttributeError:
      raise TypeError(self.__class__.__name__ + ": comparison with type " + other.__class__.__name__ + " is not supported")

#*******************************************************************************

  # Arithmetic functions. The following functions are defined:
  # - Adding a timedelta object to MyDate (also in-place).
  # - Subtracting a timedelta object from MyDate (also in-place).
  # - Subtracting one MyDate object from another.

#*******************************************************************************
  def __add__(self, other):

    # Addition of a timedelta object. Should return a new MyDate object without
    # modifying the current one.

    try:
      self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
      other_seconds = float(other.microseconds + (other.seconds + (other.days * 24 * 3600)) * 10**6) / 10**6
      new_seconds = self_seconds + other_seconds
      return MyDate(new_seconds)
    except AttributeError:
      # other is not a timedelta.
      raise TypeError(self.__class__.__name__ + ": addition with type \"" + other.__class__.__name__ + "\" is not supported")

#*******************************************************************************



#*******************************************************************************
  def __sub__(self, other):

    # Subtraction of a timedelta object or a MyDate object. Should return a new
    # MyDate object without modifying the current one.

    self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
    try:
      # First, see if this is a MyDate object.
      other_seconds = float(other.epoch) + (float(other.microseconds) / 10**6)
      new_seconds = self_seconds - other_seconds
      return datetime.timedelta(seconds=new_seconds)
    except AttributeError:
      # Now try it again as a timedelta object.
      try:
        other_seconds = float(other.microseconds + (other.seconds + (other.days * 24 * 3600)) * 10**6) / 10**6
        new_seconds = self_seconds - other_seconds
        return MyDate(new_seconds)
      except AttributeError:
        # Unsupported type.
        raise TypeError(self.__class__.__name__ + ": subtraction of type \"" + other.__class__.__name__ + "\" is not supported")

    new_seconds = self_seconds - other_seconds
    return datetime.timedelta(seconds=new_seconds)

#*******************************************************************************



#*******************************************************************************
  def __radd__(self, other):

    # The operand-swapped version of __add__. It's the exact same.
    try:
      self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
      other_seconds = float(other.microseconds + (other.seconds + (other.days * 24 * 3600)) * 10**6) / 10**6
      new_seconds = self_seconds + other_seconds
      return MyDate(new_seconds)
    except AttributeError:
      # other is not a timedelta.
      raise TypeError(self.__class__.__name__ + ": addition with type \"" + other.__class__.__name__ + "\" is not supported")

#*******************************************************************************



#*******************************************************************************
  def __rsub__(self, other):

    # The operand-swapped version of __sub__. We do not support this for
    # timedelta.
    try:
      # See if this is a MyDate object.
      self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
      other_seconds = float(other.epoch) + (float(other.microseconds) / 10**6)
      new_seconds = self_seconds - other_seconds
      return datetime.timedelta(seconds=new_seconds)
    except AttributeError:
      # Unsupported type.
      raise TypeError(self.__class__.__name__ + ": right-hand subtraction of type \"" + other.__class__.__name__ + "\" is not supported")

#*******************************************************************************



#*******************************************************************************
  def __iadd__(self, other):

    # The in-place version of __add__. This should modify the original object
    # and return it, instead of creating a new object.

    try:
      self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
      other_seconds = float(other.microseconds + (other.seconds + (other.days * 24 * 3600)) * 10**6) / 10**6
      new_seconds = self_seconds + other_seconds
    except AttributeError:
      # other is not a timedelta.
      raise TypeError(self.__class__.__name__ + ": addition with type \"" + other.__class__.__name__ + "\" is not supported")

    microseconds, epoch = math.modf(new_seconds)
    epoch = int(epoch)
    microseconds = int(round(microseconds,6) * (10**6))

    self.apply_date_from_epoch(epoch, microseconds)
    return self

#*******************************************************************************



#*******************************************************************************
  def __isub__(self, other):

    # The in-place verison of __sub__. This should modify the original object
    # and return it, instead of creating a new object. We cannot subtract one
    # MyDate from another in this manner.

    self_seconds = float(self.epoch) + (float(self.microseconds) / 10**6)
    try:
      other_seconds = float(other.microseconds + (other.seconds + (other.days * 24 * 3600)) * 10**6) / 10**6
      new_seconds = self_seconds - other_seconds
    except AttributeError:
      # Unsupported type.
      raise TypeError(self.__class__.__name__ + ": in-place subtraction of type \"" + other.__class__.__name__ + "\" is not supported")

    microseconds, epoch = math.modf(new_seconds)
    epoch = int(epoch)
    microseconds = int(round(microseconds,6) * (10**6))

    self.apply_date_from_epoch(epoch, microseconds)
    return self

#*******************************************************************************

  # Hash method.

#*******************************************************************************
  def __hash__(self):

    # A hash method, so a date can be used in a dictionary.

    return hash((self.epoch, self.microseconds))

#*******************************************************************************

  # End MyDate definition.

################################################################################



################################################################################
def get_status_file_start_end_time(file_path, use_end_time_entry=True):

  # This function looks through a provided status file, obtaining the earliest
  # and latest time stamps from it. If use_end_time_entry is False, the
  # modification time of the file is used instead.

  date_re = re.compile(valid_status_date_regex)
  start_time = None
  end_time = None

  # Open up the file for reading.
  try:
    fd = open(file_path,"r")

    # Look through every line for a date timestamp, and place that into
    # start_time.
    for line in fd:
      date_match = date_re.match(line)
      if date_match != None:
        start_time = date_match.string[date_match.start():date_match.end()]
        break

    # If we didn't find any timestamps at all, then we need to use the
    # modification time for both the start and end.
    if start_time == None:
      use_end_time_entry = False

    # Now get the ending time stamp. The first way is to look through the file
    # some more, recording every instance, so the last one is saved.
    if use_end_time_entry:
      for line in fd:
        date_match = date_re.match(line)
        if date_match != None:
          end_time = date_match.string[date_match.start():date_match.end()]

    # In case we're using the modification time instead.
    else:
      modtime = os.path.getmtime(file_path)
      end_time = seconds_to_date(modtime)
  except:
    g.print_error("Error reading data from \"" + file_path + "\".")
    return (None, None)

  # With the file read, we make our final decisions about what to do. By this
  # point, one of these two variables has to be set.
  if start_time == None:
    start_time = end_time
  elif end_time == None:
    end_time = start_time

  return (start_time, end_time)

################################################################################



################################################################################
def calc_runtime(file_name, use_end_time_entry=True):

  # This function will look through a status file in order to determine the
  # runtime of a given function. We return both the number of seconds and a
  # formatted string. Output format is "DD HH:MM:SS".

  # First, determine the file's start and end times.
  start_time, end_time = get_status_file_start_end_time(file_name, use_end_time_entry)

  # Convert to epoch seconds and get the runtime in seconds.
  start_sec = int(date_to_seconds(start_time))
  end_sec = int(date_to_seconds(end_time))
  run_sec = end_sec - start_sec

  # Determine the number of days, hours, minutes and seconds.
  days = run_sec / 86400
  run_rem = run_sec % 86400
  hours = run_rem / 3600
  run_rem = run_rem % 3600
  minutes = run_rem / 60
  seconds = run_rem % 60

  # Create the string.
  run_str = "%s %s:%s:%s" % (str(days).zfill(2), str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2))

  return (run_sec, run_str)

################################################################################



################################################################################
def sql_date_to_std(sql_date):

  # This function converts a SQL-formatted date string into our preferred
  # format.
  #
  # SQL: 2014-07-03-13.22.13.000000
  # STD: 2014/07/03 13:22:13

  # Some munching will extract the relevant numbers so we can place them
  # into a different string.
  year, sql_rem = gstr.munch(sql_date, "- ")
  month, sql_rem = gstr.munch(sql_rem, "-")
  day, sql_rem = gstr.munch(sql_rem, "-")
  hour, sql_rem = gstr.munch(sql_rem, ".")
  minute, sql_rem = gstr.munch(sql_rem, ".")
  second, sql_rem = gstr.munch(sql_rem, ". \n\t\r")

  std_date = "%s/%s/%s %s:%s:%s" % (year, month, day, hour, minute, second)

  return std_date

################################################################################



################################################################################
def std_to_sql_date(std_date):

  # This function converts a date string in our preferred format into a SQL
  # format.
  #
  # STD: 2014/07/03 13:22:13
  # SQL: 2014-07-03-13.22.13.000000

  # Some munching will extract the relevant numbers so we can place them
  # into a different string.
  year, std_rem = gstr.munch(std_date, "/ ")
  month, std_rem = gstr.munch(std_rem, "/")
  day, std_rem = gstr.munch(std_rem, " ")
  hour, std_rem = gstr.munch(std_rem, ":")
  minute, std_rem = gstr.munch(std_rem, ":")
  second, std_rem = gstr.munch(std_rem, ". \n\t\r")

  sql_date = "%s-%s-%s-%s.%s.%s.000000" % (year, month, day, hour, minute, second)

  return sql_date

################################################################################



################################################################################
def date_to_seconds(date_str):

  # A function that converts our preferred date format to seconds since the
  # epoch.

  # First, we need to munch on our date_str to get the information we need.
  timezone, date_rem = gstr.munch(date_str, "#() ")
  year, date_rem = gstr.munch(date_rem,"/")
  month, date_rem = gstr.munch(date_rem,"/")
  day, date_rem = gstr.munch(date_rem," ")
  hour, date_rem = gstr.munch(date_rem,":")
  minute, date_rem = gstr.munch(date_rem,":")
  second, date_rem = gstr.munch(date_rem,".")

  # Convert to integers.
  year = int(year) ; month = int(month) ; day = int(day)
  hour = int(hour) ; minute = int(minute) ; second = int(second)

  # We need to determine the day of the week and of the year, which we can do
  # quickly with datetime. date_tuple[6] and [7] contain those data.
  date_tuple = datetime.date(year,month,day).timetuple()

  # Now we use that, along with our previously known values, to create the
  # full time tuple. The final -1 means we don't know the DST status, so
  # Python will figure it out for us.
  time_tuple = (date_tuple[0], date_tuple[1], date_tuple[2], hour, minute, second, date_tuple[6], date_tuple[7], -1)

  # Now getting the epoch seconds is easy.
  seconds = time.mktime(time_tuple)

  return seconds

################################################################################



################################################################################
def seconds_to_date(seconds):

  # A function that converts seconds since the epoch to our preferred date
  # format.

  date_str = time.strftime("#(%Z) %Y/%m/%d %H:%M:%S", time.localtime(seconds))
  return date_str

################################################################################



################################################################################
def date_subtract(date1, date2):

  # This function will subtract one date from the other, returning the number
  # of seconds they are separated by. Useful if we have two strings; if we
  # have MyDate objects, subtraction is directly supported.

  seconds1 = date_to_seconds(date1)
  seconds2 = date_to_seconds(date2)
  time_delta = seconds1 - seconds2

  return time_delta

################################################################################



################################################################################
def calc_min_time_unit(total_seconds):

  # This function takes in an integer number of seconds, and returns the
  # largest unit that can be used to describe that number of seconds, e.g. if
  # we are passed 7200 seconds, this is more than an hour but less than a day,
  # so "hours" is returned.

  try:
    total_seconds = int(total_seconds)
    if total_seconds < 60:
      return "seconds"
    elif total_seconds < 3600:
      return "minutes"
    elif total_seconds < 86400:
      return "hours"
    else:
      return "days"
  except ValueError:
    raise ValueError("invalid type for calc_min_time_unit: " + total_seconds.__class__.__name__)

################################################################################



################################################################################
def convert_secs_to_dhms(seconds, unit="days", include_units=False):

  # This function takes a given number of seconds and converts it to another
  # unit (days, hours, minutes, or just seconds again). If include_units is
  # true, the unit will be provided at the end of the printed string. The
  # function returns a string as well as a full unit breakdown in numbers.

  # 60*60*24
  secs_per_day = 86400
  # 60*60
  secs_per_hour = 3600

  total_days = int(seconds) / secs_per_day
  days_remainder = int(seconds) % secs_per_day

  total_hours = days_remainder / secs_per_hour
  hours_remainder = days_remainder % secs_per_hour

  total_minutes = hours_remainder / 60
  total_seconds = hours_remainder % 60

  # Instead of a switch statement, which doesn't actually exist in Python,
  # we will use a dictionary of functions to decide what our output will be.

  # Case "days".
  def days_func():
    total_time = "%s %s:%s:%s" % (str(total_days).zfill(2), str(total_hours).zfill(2), str(total_minutes).zfill(2), str(total_seconds).zfill(2))
    if include_units:
      if total_days == 1:
        total_time += " day"
      else:
        total_time += " days"
    return (total_time, total_days, total_hours, total_minutes, total_seconds)

  # Case "hours".
  def hours_func():
    total_hours += total_days * 24
    total_time = "%s:%s:%s" % (str(total_hours).zfill(2), str(total_minutes).zfill(2), str(total_seconds).zfill(2))
    if include_units:
      if total_days == 1:
        total_time += " hour"
      else:
        total_time += " hours"
    return (total_time, total_hours, total_minutes, total_seconds)

  # Case "minutes".
  def minutes_func():
    total_hours += total_days * 24
    total_minutes += total_hours * 60
    total_time = "%s:%s" % (str(total_minutes).zfill(2), str(total_seconds).zfill(2))
    if include_units:
      if total_days == 1:
        total_time += " minute"
      else:
        total_time += " minutes"
    return (total_time, total_minutes, total_seconds)

  # Case "seconds".
  def seconds_func():
    total_hours += total_days * 24
    total_minutes += total_hours * 60
    total_seconds += total_minutes * 60
    total_time = "%s" % str(total_seconds).zfill(2)
    if include_units:
      if total_days == 1:
        total_time += " second"
      else:
        total_time += " seconds"
    return (total_time, total_seconds)

  func_dict = {"days" : days_func, "hours" : hours_func, "minutes" : minutes_func, "seconds" : seconds_func}

  # Now look up and execute the correct function, then return the value given.
  try:
    retvalue = func_dict[unit]()
  except KeyError:
    g.print_error("Programmer error. Incorrect unit provided to convert_secs_to_dhms().")
    return None

  return retvalue

################################################################################



################################################################################
def convert_dhms_to_secs(dhms_str):

  # This function is the opposite of convert_secs_to_dhms. It takes in a DHMS
  # string and returns the total number of seconds.
  #
  # DHMS format:
  #   DD HH:MM:SS [days|hours|minutes|seconds]

  munch_string = string.lowercase + string.uppercase + " :"
  total_seconds = 0

  # We'll munch away at the string to get the info we need, in reverse order.
  # We'll make sure to remove all letters in the string as we munch, so we
  # don't accidentally preserve the unit.
  dhms_rem, seconds = gstr.rmunch(dhms_str,munch_string)
  dhms_rem, minutes = gstr.rmunch(dhms_rem,munch_string)
  dhms_rem, hours = gstr.rmunch(dhms_rem,munch_string)
  dhms_rem, days = gstr.rmunch(dhms_rem,munch_string)

  # Add up all of the seconds.
  if days != "":
    total_seconds += int(days) * 86400
  if hours != "":
    total_seconds += int(hours) * 3600
  if minutes != "":
    total_seconds += int(minutes) * 60
  if seconds != "":
    total_seconds += int(seconds)

  return total_seconds

################################################################################



################################################################################
def get_fsp_time():

  # This function obtains specific time measurements (current minutes, seconds,
  # etc) from a FSP and stores it in a number of variables, which are then
  # returned. Usage:
  # system_time, year, month, day, hours, minutes, seconds, microseconds, epoch_seconds = get_fsp_time()

  # First, get the system time.
  stat, system_time = commands.getstatusoutput("rtim timeofday | grep 'System time is' | cut -f 2- -d :")
  system_time = system_time.strip()

  # Next, use that system time string to get all the other variables.
  year = system_time[0:4]
  month = system_time[5:7]
  day = system_time[8:10]
  hours = system_time[11:13]
  minutes = system_time[14:16]
  seconds = system_time[17:19]
  microseconds = system_time[20:26]

  # Lastly, get the number of epoch seconds, which requires a weird format
  # on the FSP in order to get.
  epoch_command = "date -d " + month + day + hours + minutes + year + "." + seconds + " +%s"
  stat, epoch_seconds = commands.getstatusoutput(epoch_command)

  return (system_time, year, month, day, hours, minutes, seconds, microseconds, epoch_seconds)

################################################################################
