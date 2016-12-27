#!/usr/bin/python

# This module contains some general class functions, as well as one
# overall base class to inherit from.

import os

import gen_python_globals as g

################################################################################
class GenPythonObject(object):

#*******************************************************************************
  def __init__(self, obj_name):
    self.obj_name = obj_name

#*******************************************************************************



#*******************************************************************************
  def __repr__(self):

    # This function prints out a standard object representation that's easy to
    # understand. We used to print out the dictionary, but that has the
    # dangerous possibility of infinite recursion if an object references
    # itself somehow.

    return "<" + self.__class__.__name__ + " object at " + hex(id(self)) + ">"

#*******************************************************************************



#*******************************************************************************
  def __str__(self):

    # This function by default will print out all defined class and instance
    # variables, in a well-formatted way. To print out all the variables for
    # object test_obj, just use "print test_obj".

    printstr = ""
    formatstr = "%" + str(g.col1_indent) + "s%-" + str(g.col1_width) + "s%s\n"
    allvars = self.__dict__
    for var, value in allvars.iteritems():
      printstr += formatstr % ("",str(var)+":",str(value))

    # Remove the final newline character and we're done.
    return printstr[:-1]

#*******************************************************************************



#*******************************************************************************
  def valid(self):

    # This function ensures that the object is valid. Implementation is left
    # entirely to the subclass.

    return True

#*******************************************************************************



#*******************************************************************************
  def read_obj(self, file_path=None, validate=True):

    # This function will look through a file and prepare for reading the file
    # into this object. The actual reading in of data needs to be handled by
    # each subclass of GenPythonObject, but they can call this superclass
    # function to handle some of the validation. That's less typing for us.

    if file_path == None:
      file_path = "/tmp/" + g.system_parms["username"] + "/" + self.obj_name

    if validate:
      if not os.path.isfile(file_path):
        g.print_error(file_path + " is not a valid file.")
        return None

    return file_path

################################################################################
