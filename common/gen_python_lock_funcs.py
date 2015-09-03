#!/usr/bin/python

# This module contains functions that will allow for easy semaphore locking.
# gen_bash_lock_funcs used a lot of things from gen_bash_obj_funcs, since Bash
# does not support objects natively. Python does, though, so our lives are made
# substantially easier. All classes do inherit from GenPythonObject, defined in
# gen_python_obj_funcs.py, which has one or two base functions defined.

# The only function you should employ from this module is mlock. All other
# functions are just here to support that.

import commands
import inspect
import os
import signal
import string
import sys
import time

import gen_python_cmd_funcs as gcmd
import gen_python_exit_funcs as gexit
import gen_python_globals as g
import gen_python_obj_funcs as gobj
import gen_python_opt_funcs as gopt
import gen_python_misc_funcs as gmisc
import gen_python_print_funcs as gprint
import gen_python_sig_funcs as gsig
import gen_python_string_funcs as gstr

# A debug variable that affects .last_holder_info files.
my_lockfile_debug = True

# A variable to indicate if we should print anything out.
lock_quiet = True

# A variable that determines which signals to block.
signals_to_block = [signal.SIGINT, signal.SIGTERM, signal.SIGALRM]

################################################################################
class Lock(gobj.GenPythonObject):

  # This class contains all the variables and methods needed for locks.
  # The following Bash methods are now class methods:
  #
  # valid_lock_obj obj_name -> obj_name.valid()
  # read_obj obj_name -> obj_name.read_obj()
  # read_lock_obj obj_name -> obj_name.read_lock()
  # write_lock_obj obj_name -> obj_name.write_lock()
  # print_lock_obj obj_name -> obj_name.print_lock()
  # lock_lock_obj_sema4 obj_name -> obj_name.lock_sema4()
  # unlock_lock_obj_sema4 obj_name -> obj_name.unlock_sema4()
  # add_pid_to_lock_obj obj_name lock_type pid
  #   -> obj_name.add_pid(pid)
  # remove_pid_from_lock_obj obj_name lock_type pid
  #   -> obj_name.remove_pid(pid)
  # change_lock_obj obj_name cmd_buf -> obj_name.change(cmd_buf)
  # search_list 'pid:lock_type:hostname' req_queue ' '
  #   -> obj_name.find_pid(pid, hostname)
  #
  # To just see all of the object's variables, simply type "print obj_name".

#*******************************************************************************
  def __init__(self, obj_name=None, targ_path=None, dir_path=None, file_name=None, lock_path=None, sema4_path=None, excl_list=[], shared_list=[], req_queue=[]):

    # The constructor for a Lock object. It's pretty simple, since we want to
    # be able to create a totally blank Lock if necessary (for read_obj, for
    # example).

    self.obj_name = obj_name
    self.targ_path = targ_path
    self.dir_path = dir_path
    self.file_name = file_name
    self.lock_path = lock_path
    self.sema4_path = sema4_path
    self.excl_list = excl_list
    self.shared_list = shared_list
    self.req_queue = req_queue
    # Some cleanup stuff.
    self.req_queue_changed = False
    self.lock_object_changed = False

#*******************************************************************************



#*******************************************************************************
  def __repr__(self):

    # Make this object printable easily.

    formatstr = "%s: %s, " * 8
    formatstr += "%s: %s"
    printstr = formatstr % ("obj_name",str(self.obj_name),"targ_path",str(self.targ_path),"dir_path",str(self.dir_path),"file_name",str(self.file_name),"lock_path",str(self.lock_path),"sema4_path",str(self.sema4_path),"excl_list",str(self.excl_list),"shared_list",str(self.shared_list),"req_queue",str(self.req_queue))
    return printstr

#*******************************************************************************



#*******************************************************************************
  def __str__(self):

    # Make this object printable easily.

    formatstr = ("%" + str(g.col1_indent) + "s%-" + str(g.col1_width) + "s%s\n") * 8
    formatstr += "%" + str(g.col1_indent) + "s%-" + str(g.col1_width) + "s%s"
    printstr = formatstr % ("","obj_name:",str(self.obj_name),"","targ_path:",str(self.targ_path),"","dir_path:",str(self.dir_path),"","file_name:",str(self.file_name),"","lock_path:",str(self.lock_path),"","sema4_path:",str(self.sema4_path),"","excl_list:",str(self.excl_list),"","shared_list:",str(self.shared_list),"","req_queue:",str(self.req_queue))
    return printstr

#*******************************************************************************



#*******************************************************************************
  def valid(self):

    # This function verifies that a given lock object is valid. It checks three
    # variables to make sure they are assigned.

    if self.targ_path == None or self.targ_path == 0 or self.targ_path == "":
      g.print_error("The " + str(self.obj_name) + " object is not properly initialized. Specifically, the targ_path member variable is blank.")
      self.print_lock()
      return False
    elif self.lock_path == None or self.lock_path == 0 or self.lock_path == "":
      g.print_error("The " + str(self.obj_name) + " object is not properly initialized. Specifically, the lock_path member variable is blank.")
      self.print_lock()
      return False
    elif self.sema4_path == None or self.sema4_path == 0 or self.sema4_path == "":
      g.print_error("The " + str(self.obj_name) + " object is not properly initialized. Specifically, the sema4_path member variable is blank.")
      self.print_lock()
      return False

    return True

#*******************************************************************************



#*******************************************************************************
  def read_obj(self, file_path=None, validate=True):

    # This function will read in object data from a file and place the contents
    # into this object.

    # The superclass method has some validation stuff.
    file_path = super(Lock, self).read_obj(file_path, validate)
    if file_path == None:
      return 1

    # Now we open up the file and parse its contents line by line.
    lockfile = open(file_path,"r")
    try:
      for line in lockfile:
        # First off, if this is the first line, we need to extract the name of
        # the object. This will let us process all the other information.
        if " object:\n" in line:
          obj_name, remainder = gstr.munch(line)
          self.obj_name = obj_name
          continue

        # If this isn't the first line, we already have an object name, so let's
        # break the line down into varname and varvalue.
        varname, varvalue = gstr.munch(line,":")
        varvalue = varvalue.strip(string.whitespace)

        # What we do next depends on varname. We have two pass cases for
        # the sake of compatibility.
        if varname == self.obj_name + "_class":
          pass
        elif varname == self.obj_name + "_obj_name":
          pass
        elif varname == self.obj_name + "_dir_path":
          self.dir_path = varvalue
        elif varname == self.obj_name + "_file_name":
          self.file_name = varvalue
        elif varname == self.obj_name + "_targ_path":
          self.targ_path = varvalue
        elif varname == self.obj_name + "_lock_path":
          self.lock_path = varvalue
        elif varname == self.obj_name + "_sema4_path":
          self.sema4_path = varvalue
        elif varname == self.obj_name + "_excl_list":
          self.excl_list = create_lockers_from_string(varvalue)
          if self.excl_list == None:
            g.print_error("Error parsing excl_list from file \"" + file_path + "\". Data may be bad.")
            return 1
        elif varname == self.obj_name + "_shared_list":
          self.shared_list = create_lockers_from_string(varvalue)
          if self.shared_list == None:
            g.print_error("Error parsing shared_list from file \"" + file_path + "\". Data may be bad.")
            return 1
        elif varname == self.obj_name + "_req_queue":
          self.req_queue = create_lockers_from_string(varvalue)
          if self.req_queue == None:
            g.print_error("Error parsing req_queue from file \"" + file_path + "\". Data may be bad.")
            return 1
        else:
          g.print_error("Unknown data found in lock file \"" + file_path + "\". Data may be bad.")
          return 1
    except:
      g.print_error("IO error reading data from \"" + file_path + "\".")
      return 1

    lockfile.close()

    # Data was successfully read in.
    return 0

#*******************************************************************************



#*******************************************************************************
  def read_lock_helper(self, current_list, pw_file, cur_epoch_seconds, advanced_cleanup=False):

    # A helper function for read_lock() that iterates over every record in a
    # list and reads data into the lock object.

    new_rec_list = []

    # We want to see if each PID in our record list is still active. If it is,
    # then we will include it in our new list of records to return. If not, we
    # exclude it. Whenever a "continue" appears, we're jumping to the next
    # record without adding the old one.
    for record in current_list:
      time_held = cur_epoch_seconds - record.epoch_seconds
      # Has this lock expired?
      if record.expiration != 0 and time_held > record.expiration:
        if not lock_quiet:
          gprint.print_time("The \"" + record.lock_type + "\" lock held by process \"" + record.pid + "\" on machine \"" + record.host_name + "\" has been held for " + str(time_held) + " seconds. This exceeds its expiration time of " + str(record.expiration) + " seconds. This lock is being forcibly removed.")
        continue

      # Advanced cleanup?
      if advanced_cleanup:
        # Is this a locker that originated from this machine?
        if record.host_name == g.system_parms["hostname"]:
          # Run a ps command to see if the process still exists.
          stat, output = commands.getstatusoutput("ps " + record.pid + " >/dev/null 2>&1")
          if stat != 0:
            continue
        else:
          # This is a locker that originated on another machine. We'll have to
          # use rcmd to determine the process status.
          rcmd_buf = "rcmd -s -l " + g.system_parms["username"] + " -pf " + pw_file + " " + record.host_name + " \"ps --no-header " + record.pid + "\" 2>&1"
          if not g.quiet:
            gprint.issuing(rcmd_buf)
          stat, output = commands.getstatusoutput(rcmd_buf)
          if stat == 0:
            if output == "":
              # No output was returned, so the process no longer exists.
              continue

      # At this point, we either know the process still exists, or we can't
      # verify that it doesn't. It goes into the list to be returned.
      new_rec_list.append(record)

    return new_rec_list

#*******************************************************************************



#*******************************************************************************
  def read_lock(self, advanced_cleanup=False):

    # This function will look through a lock object file and read its contents
    # into the current lock object, then do some additional checks to see if
    # the PIDs looking at the lock are still active.

    # First, check the object's lock file to see if data is in it. If so, we'll
    # read it into this object. If not, we'll just process the PIDs currently
    # in this lock.
    if os.path.isfile(self.lock_path):
      self.read_obj(self.lock_path)

    pw_file = g.system_parms["home"] + "/private/password"
    cur_epoch_seconds = int(time.time())

    # We're going to iterate over every single list, reading in data.
    self.excl_list = self.read_lock_helper(self.excl_list, pw_file, cur_epoch_seconds, advanced_cleanup)
    self.shared_list = self.read_lock_helper(self.shared_list, pw_file, cur_epoch_seconds, advanced_cleanup)
    self.req_queue = self.read_lock_helper(self.req_queue, pw_file, cur_epoch_seconds, advanced_cleanup)

    return 0

#*******************************************************************************



#*******************************************************************************
  def write_obj(self, dir_path=None, file_name=None):

    # This function will write out the lock contents into a file.

    if dir_path == None:
      dir_path = self.dir_path
    if file_name == None:
      file_name = self.file_name

    # First, check to see if the directory can be written to.
    if not gmisc.valid_write_dir(dir_path):
      return 1

    # Now open up the lock file for writing, and put all our info in.
    file_path = dir_path + file_name
    f = open(file_path,"w")
    try:
      f.write(self.obj_name + " object:\n")
      f.write(self.obj_name + "_class:lock\n")
      f.write(self.obj_name + "_obj_name:" + self.obj_name + "\n")
      f.write(self.obj_name + "_dir_path:" + self.dir_path + "\n")
      f.write(self.obj_name + "_file_name:" + self.file_name + "\n")
      f.write(self.obj_name + "_targ_path:" + self.targ_path + "\n")
      f.write(self.obj_name + "_lock_path:" + self.lock_path + "\n")
      f.write(self.obj_name + "_sema4_path:" + self.sema4_path + "\n")
      f.write(self.obj_name + "_excl_list:" + write_lockers_to_string(self.excl_list) + "\n")
      f.write(self.obj_name + "_shared_list:" + write_lockers_to_string(self.shared_list) + "\n")
      f.write(self.obj_name + "_req_queue:" + write_lockers_to_string(self.req_queue) + "\n")
    except:
      g.print_error("Could not write lock object " + self.obj_name + " to file " + file_path + ".")
      return 1

    f.close()

    return 0

#*******************************************************************************



#*******************************************************************************
  def write_lock(self):

    # This function will write data from a lock object into a lock file. If
    # there are no programs holding or waiting for the lock, then the lock file
    # will be deleted.

    # Check to see if there are any lockers waiting for this file. If there
    # are none, we can just delete the lock file.
    if self.excl_list == [] and self.shared_list == [] and self.req_queue == []:
      # Does the file actually exist?
      if os.path.isfile(self.lock_path):
        file_deleted = False

        # We put ourselves in a loop, because we really want to ensure that
        # the lock file is deleted.
        for i in range(0,20):
          try:
            os.remove(self.lock_path)
            file_deleted = True
            break
          except:
            time.sleep(1)

        # If we failed to delete the existing lock file, return failure.
        if not file_deleted:
          g.print_error("Failed to remove lock file " + self.lock_path + " in write_lock().")
          return 1

    # At this point, we know we need to write out to file. We need the name of
    # the lock file, though.
    junk, lock_file = gstr.rmunch(self.lock_path,"/")
    self.write_obj(self.dir_path, lock_file)

    return 0

#*******************************************************************************



#*******************************************************************************
  def print_lock(self, col1_width=2, indent=3):

    # This function prints out the lock object's details in a well-formatted
    # manner. Uses the print_obj function for basic information, then goes
    # further and prints more information relevant to locks.

    print self

    # We need to print some information about the PIDs that are currently
    # associated with this lock.
    indentstr = " " * indent
    print
    print "Local PID report:"

    # Get a full list of records in every one of the object lists.
    full_rec_list = self.excl_list + self.shared_list + self.req_queue

    # Acquire the PIDs.
    pid_string = ""
    for locker_rec in full_rec_list:
      pid_string += str(locker_rec.pid) + " "

    # If there are any PIDs to report on, proceed.
    if pid_string == "":
      print indentstr + "No PIDs found."
    else:
      stat, output = commands.getstatusoutput("ps -o pid,user,cmd " + pid_string + " 2>/dev/null")
      output = output.splitlines()
      for line in output:
        print indentstr + line

#*******************************************************************************



#*******************************************************************************
  def lock_sema4(self):

    # This function locks the semaphore file associated with this lock object.

    # Some variables we can adjust.
    sleep_time = 0.1
    retries = 600

    my_lockfile(self.sema4_path, sleep_time, retries)

    return 0

#*******************************************************************************



#*******************************************************************************
  def unlock_sema4(self):

    # This function unlocks the semaphore file associated with this lock object.
    # We're going to try repeatedly to delete it, for up to two minutes, since
    # a semaphore is a dangerous file to leave around.

    success = False
    for i in range(0,120):
      rc = gexit.remove_cleanup_file(self.sema4_path, quiet_del=True)
      if rc == 0:
        success = True
        break
      else:
        time.sleep(1)

    # Did we fail to remove the semaphore file?
    if not success:
      g.print_error("Failed to remove semaphore file " + self.sema4_path + ". File should be deleted manually as soon as possible.")
      return 1

    return 0

#*******************************************************************************



#*******************************************************************************
  def add_pid(self, lock_type, expiration, pid=None, hostname=None):

    # This function adds a given PID to a lock's request queue. If a PID is not
    # provided, it is acquired from the current program, along with the host
    # name.

    if pid == None:
      pid = str(g.system_parms["pid"])
    if hostname == None:
      hostname = g.system_parms["hostname"]

    # Create the object and store it in the req_queue.
    epoch_seconds = int(time.time())
    newlocker = Locker(pid, lock_type, hostname, epoch_seconds, int(expiration))
    self.req_queue.append(newlocker)

    # Set a flag to indicate that the req_queue has changed, for cleanup
    # purposes.
    self.req_queue_changed = True

    return 0

#*******************************************************************************



#*******************************************************************************
  def remove_pid(self, pid=None, hostname=None):

    # This function removes a given PID from a lock's request queue. If a PID
    # is not provided, it is acquired from the current program, along with the
    # host name.

    if pid == None:
      pid = str(g.system_parms["pid"])
    if hostname == None:
      hostname = g.system_parms["hostname"]

    ret_locker = None

    # Look at every locker in the req_queue and see if the PID matches the one
    # provided, and also make sure it's a local PID. If so, pop it from the
    # list. We won't have a memory leak since Python deletes objects
    # automatically when they're no longer referenced.
    for i in range(0,len(self.req_queue)):
      if self.req_queue[i].pid == pid and self.req_queue[i].host_name == hostname:
        ret_locker = self.req_queue.pop(i)
        break

    # Set a flag to indicate that the req_queue has un-changed, for cleanup
    # purposes.
    self.req_queue_changed = False

    return ret_locker

#*******************************************************************************



#*******************************************************************************
  def remove_pid_from_list(self, locklist, pid=None, hostname=None):

    # This function removes a given PID from a particular lock list. If a PID
    # is not provided, it is acquired from the current program.

    if pid == None:
      pid = str(g.system_parms["pid"])
    if hostname == None:
      hostname = g.system_parms["hostname"]

    ret_locker = None

    # Look at every locker in the locklist and see if the PID matches the one
    # provided, and also make sure it's a local PID. If so, pop it from the
    # list. We won't have a memory leak since Python deletes objects
    # automatically when they're no longer referenced.
    for i in range(0,len(locklist)):
      if locklist[i].pid == pid and locklist[i].host_name == hostname:
        ret_locker = locklist.pop(i)
        break

    return ret_locker

#*******************************************************************************



#*******************************************************************************
  def find_pid(self, pid=None, hostname=None):

    # This function searches for a given PID in a lock's requests queue. If a
    # PID is not provided, it is acquired from the current program, along with
    # the hostname.

    if pid == None:
      pid = str(g.system_parms["pid"])
    if hostname == None:
      hostname = g.system_parms["hostname"]

    # Look at every locker in the req_queue and see if the PID and hostname
    # match the ones provided.
    for i in range(0,len(self.req_queue)):
      if self.req_queue[i].pid == pid and self.req_queue[i].host_name == hostname:
        return True

    return False

#*******************************************************************************



#*******************************************************************************
  def change(self, change_func):

    # This function locks a given lock object, reads in lock data, executes a
    # given function, writes out lock data again, and then unlocks the
    # semaphore.

    rc = self.lock_sema4()
    if rc != 0:
      return rc

    rc = self.read_lock()
    if rc != 0:
      self.unlock_sema4()
      return rc

    cmd_rc = change_func()

    rc = self.write_lock()
    if rc != 0:
      self.unlock_sema4()
      return rc

    rc = self.unlock_sema4()
    if rc != 0:
      return rc

    return cmd_rc

################################################################################



################################################################################
class Locker(gobj.GenPythonObject):

  # This class contains all the variables needed for lockers.

#*******************************************************************************
  def __init__(self, pid, lock_type, host_name, epoch_seconds, expiration):
    self.pid = pid
    self.lock_type = lock_type
    self.host_name = host_name
    self.epoch_seconds = epoch_seconds
    self.expiration = expiration

#*******************************************************************************



#*******************************************************************************
  def __repr__(self):

    # Make this object printable easily.

    formatstr = ("%" + str(g.col1_indent) + "s%-" + str(g.col1_width) + "s%s\n") * 4
    formatstr += "%" + str(g.col1_indent) + "s%-" + str(g.col1_width) + "s%s"
    printstr = formatstr % ("","pid:",str(self.pid),"","lock_type:",str(self.lock_type),"","host_name:",str(self.host_name),"","epoch_seconds:",str(self.epoch_seconds),"","expiration:",str(self.expiration))
    return printstr

#*******************************************************************************



#*******************************************************************************
  def write(self):

    # Return this object as a string that can be written to a lock file.

    printstr = "%s:%s:%s:%s:%s" % (self.pid, self.lock_type, self.host_name, str(self.epoch_seconds), str(self.expiration))
    return printstr

#*******************************************************************************



#*******************************************************************************
  def valid(self):

    # This function verifies that a given lock object is valid. It checks all
    # variables to make sure they are assigned.

    if self.pid == None or self.pid == 0 or self.pid == "":
      g.print_error("This Locker object is not properly initialized. Specifically, the pid member variable is blank.")
      print self
      return False
    elif self.lock_type == None or self.lock_type == 0 or self.lock_type == "":
      g.print_error("This Locker object is not properly initialized. Specifically, the lock_type member variable is blank.")
      print self
      return False
    elif self.host_name == None or self.host_name == 0 or self.host_name == "":
      g.print_error("This Locker object is not properly initialized. Specifically, the host_name member variable is blank.")
      print self
      return False
    elif self.epoch_seconds == None or self.epoch_seconds == 0 or self.epoch_seconds == "":
      g.print_error("This Locker object is not properly initialized. Specifically, the epoch_seconds member variable is blank.")
      print self
      return False
    elif self.expiration == None or self.expiration == "":
      g.print_error("This Locker object is not properly initialized. Specifically, the expiration member variable is blank.")
      print self
      return False

    return True

################################################################################



################################################################################
def my_lockfile(file_path, sleeptime=1, retries=20, locktimeout=0, suspend=4):

  # A Python conversion of the Bash my_lockfile function, which itself is an
  # enhancement over the standard lockfile program. Some enhancements:
  # - Will print out standardized error messages upon failure.
  # - Will place the lock file into the global cleanup list, so that when this
  #     program terminates, the lock will automatically be removed.
  # - Can sleep in microsecond increments.
  # - Puts identifying debug information into a ".last_holder_info" file.

  # If this was called from "lock_sema4" then we don't need to validate its
  # parameters. Otherwise we'll double-check the file path.
  if inspect.stack()[1][3] != "lock_sema4":
    dir_path, file_name = gmisc.split_path(file_path, True)
    if not gmisc.valid_write_dir(dir_path):
      return 1

  # Grab the PID and save it in something more easily called.
  pid = str(g.system_parms["pid"])

  # The info file we're going to write to.
  info_file = file_path + ".last_holder_info"

  lock_acquired = False

  # We're going to try this up to (retries) number of times.
  for i in range(0,retries):

    # We're going to trap SIGINT, SIGTERM and SIGALRM while we attempt this.
    gsig.trap_signals(signals_to_block)

    lockfd = None

    # There's a low-level command that will create a file only if it doesn't
    # already exist, which is exactly what we need. The operation has to
    # be atomic or else we have nasty race conditions.
    try:
      lockfd = os.open(file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except:
      # If we couldn't get the lockfile, release the signals, sleep for a bit
      # and then try again.
      gsig.release_signals()
      time.sleep(sleeptime)
      continue

    # If we made it here, we acquired the file.
    lock_acquired = True

    # Close the lock file descriptor, we're not actually writing any data
    # into it yet. We just needed to make sure the file was ours.
    os.close(lockfd)

    # Let's add it to the list of files to clean up when the program exits.
    # We don't want the lock to persist after we're done with it.
    gexit.add_cleanup_file(file_path)

    # We're going to open up another file, the .last_holder_info file, and
    # start placing data into it. This time we don't care if it exists already
    # or not.
    infofd = open(info_file,"w")

    # Redirect stdout, so we can dump lots of info quickly into the file.
    stdout_old = sys.stdout
    sys.stdout = infofd

    try:
      # Should we be placing additional debug info into .last_holder_info?
      if my_lockfile_debug:
        # First, we write the call stack.
        gprint.print_call_stack()
        print

        # Then we print out various parameters.
        gprint.print_system_parms()
        gprint.print_global_vars()

        # Lastly, we print out the file path.
        g.print_var("file_path",file_path)

      else:
        # We'll just display some simple information.
        print
        print g.program_name + ", user " + g.system_parms["username"] + ", PID " + str(g.system_parms["pid"]) + "."
        print
    except Exception, e:
      g.print_error("IO error: could not write data to \"" + info_file + "\". Exception received: \"" + str(e) + "\"")

    # Close the file.
    infofd.close()

    # Restore stdout.
    sys.stdout = stdout_old

    # We're done here. Release signals and break out of the loop.
    gsig.release_signals()
    break

  # How many attempts did it take us?
  if not lock_quiet:
    g.print_var("num_lockfile_attempts",str(i+1))

  # If we failed, print out some information about the lock to stderr.
  if not lock_acquired:
    g.print_error("Failed to obtain lock on " + file_path + " after " + str(i+1) + " attempts.")
    stdout_old = sys.stdout
    sys.stdout = sys.stderr

    gprint.print_dashes()
    print "Displaying the " + info_file + " info file, which contains information on the last known holder of the lock on " + file_path + ". This may be the process that prevented us from getting the sema4 file lock."

    # Open up the .last_holder_info file and display its contents.
    try:
      infofd = open(info_file,"r")
      for line in infofd:
        sys.stderr.write(line)
    except:
      g.print_error("IO error: could not read data from \"" + info_file + "\".")
    infofd.close()

    sys.stdout = stdout_old
    return 1

  return 0

################################################################################



################################################################################
def create_lock_obj(file_path):

  # This function creates a new lock object, given a file path to store a lock
  # file in.

  delim = ":"

  # Generate the directory path and the file name.
  dir_path, file_name = gmisc.split_path(file_path,True)

  # Throw an error if our directory doesn't exist, or can't be written to.
  if not gmisc.valid_write_dir(dir_path):
    return None

  # A couple of other attributes to generate.
  lock_path = str(dir_path) + "." + file_name + delim + "lockfile"
  sema4_path = str(dir_path) + "." + file_name + delim + "semaphore"

  # The last thing to put in is an obj_name. It's a Bash holdover that we
  # don't really need for the same reasons, but it can be handy to have a
  # name to print out in case of errors.
  obj_name = gstr.filepath_to_varname(file_name) + "_lock"

  # Now create the Lock.
  lock_obj = Lock(obj_name, file_path, dir_path, file_name, lock_path, sema4_path, [], [], [])

  return lock_obj

################################################################################



################################################################################
def create_lockers_from_string(buffer):

  # This function processes a string containing one or more locker data
  # objects, and turns them into as many Lockers as possible.

  locker_list = []

  # Munch away at the string to get our Locker data.
  while buffer != "":
    pid, buffer = gstr.munch(buffer,":")
    lock_type, buffer = gstr.munch(buffer,":")
    host_name, buffer = gstr.munch(buffer,":")
    epoch_seconds, buffer = gstr.munch(buffer,":")
    expiration, buffer = gstr.munch(buffer)

    # Create the Locker object.
    new_locker = Locker(pid, lock_type, host_name, int(epoch_seconds), int(expiration))

    # Check to see if the object is valid. If it isn't, then we had incomplete
    # information in our string, and we should raise an error.
    if not new_locker.valid():
      return None

    # Add the locker to the list.
    locker_list.append(new_locker)

  return locker_list

################################################################################



################################################################################
def write_lockers_to_string(locker_list):

  # This function takes a list of Locker objects, and returns them as a string
  # that can be written to a lock file.

  lockerstr = ""
  for locker in locker_list:
    lockerstr += locker.write() + " "

  # Trim off the final space before returning.
  return lockerstr[:-1]

################################################################################



################################################################################
def base_lock_cleanup(signal, rc=0, *args):

  # The basic cleanup function for base_lock, to be used at the end of the
  # function or in case of an error.
  #
  # args:
  #   0: current_lock - the lock object we're currently using.
  #   1: lock_type - the type of the lock we're working with.

  current_lock = args[0]
  lock_type = args[1]
  ret_code = 0
  lock_action_status = False

  # We're going to trap signals during cleanup. It's good practice in case
  # we're cleaning up from a non-error state.
  gsig.trap_signals(signals_to_block)

  if not lock_quiet:
    gprint.print_func_name()

  if current_lock.req_queue_changed and rc == 0:
    # If rc is 0, then base_lock probably completed successfully, so let's
    # remove our PID from the waiting list.
    if current_lock.remove_pid() == None:
      ret_code = 1

  # If the lock object changed, we should write it back out.
  if current_lock.lock_object_changed:
    if current_lock.write_lock() == 1:
      ret_code = 1

  # Are we currently holding a semaphore lock? If the program was interrupted
  # due to some signal, we're going to assume yes. Otherwise, take a look
  # through the cleanup_file_list.
  semaphore_lock_held = True
  if current_lock.sema4_path not in gexit.cleanup_file_list:
    semaphore_lock_held = False

  if semaphore_lock_held:
    if current_lock.unlock_sema4() == 1:
      ret_code = 1

  # If all went well, we should write out a certain value to lock_action_status
  # for the caller to use, assuming that we are trying to remove a lock.
  if lock_type == "u" and rc == 0:
    lock_action_status = True

  # Release trapped signals.
  gsig.release_signals()

  # A return code of 0 indicates that everything went well. base_lock will use
  # this value and gen_func_cleanup won't, so this is ok to do.
  return (ret_code, lock_action_status)

################################################################################



################################################################################
def base_lock(lock_obj, expiration, lock_type="s"):

  # This function is used exclusively by mlock, in order to implement a lock
  # request on a given file.

  lock_action_status = False

  # First, push the cleanup function onto the stack, in case a signal
  # interrupts. We can call it in case of a general error with
  # gexit.pop_cleanup_func(0,1).
  gexit.push_cleanup_func(base_lock_cleanup, lock_obj, lock_type)

  # We have to lock the semaphore file, so we're the only ones who can
  # manipulate the lock file.
  if lock_obj.lock_sema4() == 1:
    gexit.pop_cleanup_func(0,1)
    return (1, lock_action_status)

  # Next, read in data from the lock file. Block signals briefly.
  gsig.trap_signals(signals_to_block)
  read_stat = lock_obj.read_lock()
  gsig.release_signals()
  if read_stat == 1:
    gexit.pop_cleanup_func(0,1)
    return (1, lock_action_status)

  # Print out information.
  if not lock_quiet:
    print "Initial value of the " + str(lock_obj.obj_name) + " object:"
    print lock_obj

  # Are we getting an exclusive or shared lock?
  if lock_type == "s" or lock_type == "x":

    # First, we need to add ourselves to the request queue if we aren't already
    # there.
    if not lock_obj.find_pid():
      lock_obj.add_pid(lock_type,expiration)
      lock_obj.lock_obj_changed = True
      if not lock_quiet:
        print "The " + str(lock_obj.obj_name) + " object has been changed as shown:"
        print lock_obj

    # We can only proceed if we're the first PID waiting for the lock. If
    # another process wants it, then we need to back off.
    first_pid = lock_obj.req_queue[0]
    if first_pid.pid != str(g.system_parms["pid"]) or first_pid.host_name != g.system_parms["hostname"]:
      gexit.pop_cleanup_func(0,1)
      if not lock_quiet:
        g.print_error("There is at least one process ahead of us in the request queue waiting for a lock on " + str(lock_obj.targ_path) + ".")
        sys.stderr.write(str(lock_obj)+"\n")
      return (1, lock_action_status)

    # Last question: does someone else already have an exclusive lock? If so,
    # we can't get any kind of lock.
    if lock_obj.excl_list != []:
      gexit.pop_cleanup_func(0,1)
      lock_holder = lock_obj.excl_list[0]
      cur_epoch_seconds = int(time.time())
      time_held = cur_epoch_seconds - lock_holder.epoch_seconds
      if not lock_quiet:
        g.print_error("Process " + str(lock_holder.pid) + " from host " + lock_holder.host_name + " currently holds an exclusive lock on " + str(lock_obj.targ_path) + " and has held it for " + str(time_held) + " seconds.")
        sys.stderr.write(str(lock_obj)+"\n")
      return (1, lock_action_status)

  # At this point, we know we can at least get a shared lock. If that's what
  # we want, then proceed to get it.
  if lock_type == "s":
    # We can't really signal right away that the lock is now acquired; we can't
    # do that until this function returns somehow, unless we want to start
    # messing with globals, which we really want to avoid. We can set this
    # variable now, so any future returns indicate what's happened.
    lock_action_status = True

    # Get our Locker object from the request queue. If for some reason it's
    # not there, create a new object.
    cur_epoch_seconds = int(time.time())
    locker_rec = lock_obj.remove_pid()
    if locker_rec == None:
      locker_rec = Locker(str(g.system_parms["pid"]), lock_type, g.system_parms["hostname"], cur_epoch_seconds, expiration)

    # Make sure we're getting the right kind of lock. We have a policy that a PID
    # can only request one kind of lock on the same file at any one time.
    locker_rec.lock_type = lock_type

    # Reset the epoch_seconds parameter for the locker. We don't want time spent
    # in the wait queue to count against our total lock time.
    locker_rec.epoch_seconds = cur_epoch_seconds

    # Move our Locker to the shared list.
    lock_obj.shared_list.append(locker_rec)

    # Finally, indicate that the lock object has changed.
    lock_obj.lock_object_changed = True
    if not lock_quiet:
      print "The " + str(lock_obj.obj_name) + " object has been changed as shown:"
      print lock_obj

  # If we're looking for an exclusive lock, then we need to make sure nobody
  # currently has a shared lock on the object.
  elif lock_type == "x":
    if lock_obj.shared_list != []:
      gexit.pop_cleanup_func(0,1)

      # Print out all the PIDs sharing the lock.
      pidstr = ""
      for locker_rec in lock_obj.shared_list:
        pidstr += str(locker_rec.pid) + ", "
      if not lock_quiet:
        g.print_error("An exclusive lock on " + str(lock_obj.targ_path) + " could not be obtained because the following PIDs hold shared locks on the file: " + pidstr[:-2])
      return (1, lock_action_status)

    # We're good to get the exclusive lock.
    lock_action_status = True

    # Get our Locker object from the request queue. If for some reason it's
    # not there, create a new object.
    cur_epoch_seconds = int(time.time())
    locker_rec = lock_obj.remove_pid()
    if locker_rec == None:
      locker_rec = Locker(str(g.system_parms["pid"]), lock_type, g.system_parms["hostname"], cur_epoch_seconds, expiration)

    # Make sure we're getting the right kind of lock. We have a policy that a PID
    # can only request one kind of lock on the same file at any one time.
    locker_rec.lock_type = lock_type

    # Reset the epoch_seconds parameter for the locker. We don't want time spent
    # in the wait queue to count against our total lock time.
    locker_rec.epoch_seconds = cur_epoch_seconds

    # Move our Locker to the exclusive list.
    lock_obj.excl_list.append(locker_rec)

    # Finally, indicate that the lock object has changed.
    lock_obj.lock_object_changed = True
    if not lock_quiet:
      print "The " + str(lock_obj.obj_name) + " object has been changed as shown:"
      print lock_obj

  # If we just need to remove a lock, do that here.
  elif lock_type == "u":
    # Remove the exclusive lock if we are holding it. (Is this right?)
    if lock_obj.excl_list != []:
      excl_locker = lock_obj.excl_list[0]

      # Is this our exclusive lock? If so, unlock it.
      if excl_locker.pid == str(g.system_parms["pid"]) and excl_locker.host_name == g.system_parms["hostname"]:
        lock_obj.excl_list = []

    # Remove any shared locks this PID has.
    lock_obj.remove_pid_from_list(lock_obj.shared_list)

    # Finally, indicate that the lock object has changed.
    lock_obj.lock_object_changed = True
    if not lock_quiet:
      print "The " + str(lock_obj.obj_name) + " object has been changed as shown:"
      print lock_obj

  # If we just want to get lock information, we've done that already.
  elif lock_type == "i":
    pass

  # If we want to get more advanced lock information, do a full print_lock().
  elif lock_type == "p":
    lock_obj.print_lock()

  # We should never get here.
  else:
    pass

  # Perform cleanup now, which is where we write the lock object back out to
  # file. If the cleanup failed, report that.
  rc, las_ret = base_lock_cleanup(0,0,lock_obj,lock_type)
  gexit.remove_cleanup_func(base_lock_cleanup)
  if las_ret == True:
    lock_action_status = True

  return (rc, lock_action_status)

################################################################################



################################################################################
def mlock_cleanup(signal, rc=0, *args):

  # The cleanup function for mlock.
  #
  # args:
  #   0: current_lock - the lock object we're currently using.

  current_lock = args[0]

  # Temporarily trap signals.
  gsig.trap_signals(signals_to_block)

  if not lock_quiet:
    gprint.print_func_name()

  # If we've changed the req_queue, we need to remove ourselves from it.
  if current_lock.req_queue_changed:
    current_lock.change(current_lock.remove_pid)

  # Release trapped signals.
  gsig.release_signals()

  return rc

################################################################################



################################################################################
def mlock(file_path, expiration, lock_type="s", time_out=-1, loc_quiet=True):

  # The main function for locking and unlocking files. Programs should only
  # interact with this function for locking purposes.

  global lock_quiet
  lock_quiet = loc_quiet

  lock_action_status = False

  # We start with a lot of verification. First, have we been given a valid
  # lock type?
  if len(lock_type) > 1 or lock_type not in "sxiup":
    g.print_error("Invalid lock type: " + lock_type)
    return (1, lock_action_status)

  # Type checking on time_out.
  try:
    time_out = int(time_out)
  except:
    g.print_error("Invalid time_out value: " + str(time_out))
    return (1, lock_action_status)

  # Value checking on time_out.
  if time_out < -1:
    g.print_error("Invalid time_out value: " + str(time_out))
    return (1, lock_action_status)

  # Type checking on expiration.
  try:
    expiration = int(expiration)
  except:
    g.print_error("Invalid expiration value: " + str(expiration))
    return (1, lock_action_status)

  # Value checking on expiration.
  if expiration < 0:
    g.print_error("Invalid expiration value: " + str(expiration))
    return (1, lock_action_status)

  # If we've been given nothing but a directory, with no file name at the
  # end, that's ok, but we'll strip off the ending "/".
  file_path = file_path.rstrip("/")

  # With all of our values double-checked, we can go ahead and create our
  # lock object. If it returns none, then we know our file path was invalid.
  lock_obj = create_lock_obj(file_path)
  if lock_obj == None:
    dir_path, file_name = gmisc.split_path(file_path, True)
    g.print_error("Invalid file path: " + dir_path + file_name)
    return (1, lock_action_status)

  # Now that the lock object is created, we should push our cleanup function
  # onto the stack.
  gexit.push_cleanup_func(mlock_cleanup, lock_obj)

  # The last question is how many times we are going to try and acquire the
  # lock. That depends on the value of time_out.

  # Case 1: only try once.
  if time_out == 0:
    rc, lock_action_status = base_lock(lock_obj, expiration, lock_type)
    if rc == 1:
      gexit.pop_cleanup_func(0,1)
      return (1, lock_action_status)

  # Case 2: try for a certain amount of time. We'll set an alarm.
  elif time_out > 0:
    rc = 1
    lock_acquired = False

    original_handler = signal.signal(signal.SIGALRM, gsig.gen_timeout_handler)

    # The retry loop. It'll exit automatically after time_out seconds.
    signal.alarm(time_out)
    try:
      while not lock_acquired:
        rc, lock_action_status = base_lock(lock_obj, expiration, lock_type)
        if rc == 0 or lock_action_status == True:
          lock_acquired = True
    except gsig.GeneralTimeout:
      pass

    # Turn the alarm off.
    signal.alarm(0)
    signal.signal(signal.SIGALRM, original_handler)

    # Did we succeed? If not, cleanup and exit.
    if rc == 1:
      gexit.pop_cleanup_func(0,1)
      return (1, lock_action_status)

  # Case 3: try indefinitely.
  else:
    lock_acquired = False

    # The retry loop. It'll run until we get the lock, or a signal stops it.
    while not lock_acquired:
      rc, lock_action_status = base_lock(lock_obj, expiration, lock_type)
      if rc == 0 or lock_action_status == True:
        lock_acquired = True

  # If we got the lock, but rc is 1 anyway, we should return that value after
  # cleanup, to be on the safe side.
  if rc == 1:
    gexit.pop_cleanup_func(0,1)
    return (1, lock_action_status)

  # Perform cleanup now. If the cleanup failed, report that.
  rc = mlock_cleanup(0,0,lock_obj)
  gexit.remove_cleanup_func(mlock_cleanup)

  return (rc, lock_action_status)

################################################################################
