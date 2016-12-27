#!/usr/bin/perl
# IBM_PROLOG_BEGIN_TAG  
# This is an automatically generated prolog.    
# 
# $Source: op-auto-test/boot/op_boot_test.pl $
# 
# OpenPOWER Automated Test Project  
# 
# Contributors Listed Below - COPYRIGHT 2015    
# [+] International Business Machines Corp.     
# 
# 
# Licensed under the Apache License, Version 2.0 (the "License");   
# you may not use this file except in compliance with the License.  
# You may obtain a copy of the License at   
#   
# http://www.apache.org/licenses/LICENSE-2.0    
#   
# Unless required by applicable law or agreed to in writing, software 
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or 
# implied. See the License for the specific language governing 
# permissions and limitations under the License. 
#   
# IBM_PROLOG_END_TAG 


use strict;
use POSIX;
use List::Util 'first'; 
use sigtrap qw/handler signal_handler normal-signals/;
use Switch; 
use Getopt::Long qw(GetOptions);

if ($#ARGV < 0 || $ARGV[0] eq '-h') 
{
    parmHelp();
    exit(0);
}

# Variables
############# Global ############
our $bmc_IP = '';                       # BMC IP address
our $bmc_name = '';                     # BMC Hostname
our $bmc_pwrd = '';                     # BMC Password 
our $bmc_user = '';                     # BMC User ID 
our $log_file = '';                     # System name_date_time.status 
our $sol_file = '';                     # File to be used to log the SOL console data 
our $solPid = '';                       # PID for the SOL console 
our $r_host = '';                       # Host OS Hostname 
our $r_user = '';                       # Host OS userid 
our $r_pwrd = '';                       # Host OS' Password
our $bmc_state = '';                    # Stores the state of the bmc 
our $FFDC_Path = './';                  # FFDC Path
our $Status_Path = './';                # Status Path
our $stop_on; 
our $time_out = 360;                    # Time out value for the wait states - default 90 minutes $time_out * 0.25
our $os_ping = 1;

#########################################
#  IPL Results:  9                      #
# 0 BMC power on                        #
# 1 BMC Host Reboot                     #
# 2 BMC Power Cycle                     #
# 3 BMC Power Reset                     #
# 4 BMC Power Off                       #
# 5 BMC Power Soft                      #
# 6 BMC AC Cycle                        #
# 7 BMC MC Reset warm                   #
# 8 BMC oob hpm                         #
#########################################
our @results = (0,0,0,0,0,0,0,0,0);                   # Stores the number of passes for each IPL
our @fails = (0,0,0,0,0,0,0,0,0);                     # Stores the number of fails for each IPL
our @Last_ten = '';                                 # Store the last 10 IPLs we did
our @IPLs_wanted = '';                              # Read from the setup file for IPLs we want to run
our @PwrOn = ('BMC Host reboot','BMC Power Off', 'BMC Power Reset', 'BMC Power Cycle', 'BMC AC Cycle','BMC Power Soft', 'BMC MC Reset warm');       # IPLs valid from power on w/ OS 
our @PwrOnNOS = ('BMC Power Off', 'BMC Power Reset', 'BMC Power Cycle', 'BMC AC Cycle');                # IPLs valid from power on w/o OS 
our @PwrOff = ('BMC Power on' , 'BMC AC Cycle', 'BMC MC Reset warm');                               # IPLs valid from power off state

# Variables we need to fill
our $mch_ser_num = ''; 
our $mch_type_model = '9999-999';           # Temporary bogus Make type model
our $wrk_name = '';                         # Workstation name
our $wrk_display = '';
our $wrk_userid = '';
our $pgm_sandbox = '';
our $DB2 = ''; 
our $release = '';
our $bld_name = '';
our $drv_name = '';
our $start_time_stamp = '';
our $db_pwrd = '';
our $start_ipl_time = '';
our $db_entry_open = 0;
our $ePDU = '';
our $sys_type = ''; 
our $end_pid = 0;
our @cronus = ('',''); 
our @cur_ffdc = '';                         # Stores the current round of FFDC for analysis 
our $tool_path = '';                        
our $start_test_time;                       # Used to store the time the test run started 
our $ami_lvl = '';

########### Local ###########
my $numArgs = 0;                        
my $cmd = '';                           
my $i = 0; 
my $wait = 1; 
my $host = '';  
my $option = '';
my $repeat = 3; 
my $base_path = '';
my $set_file = '';
my $wrk_around = 0;                     # This is to workaround the Ubuntu install's reboot hanging
my $status_file = '';
my $tmpIPLs; 
my $ipl_stack;
our $debug;
our $mnfg; 

my $help; 
my $c = $#ARGV; 
#######################
# Pars all the parms  #
####################### 
GetOptions(
	'option|o=s' => \$option, 
	'repeat=i' => \$repeat,
	'set_file|f=s' => \$set_file,
	'base_path|p=s' => \$base_path,
    'bmc_name=s' => \$bmc_name,
    'bmc_user=s' => \$bmc_user,
    'bmc_password=s' => \$bmc_pwrd,
    'os_host=s' => \$r_host,
    'os_user=s' => \$r_user,
    'os_password=s' => \$r_pwrd,
    'ffdc_path=s' => \$FFDC_Path,
    'ipls=s' => \$tmpIPLs,
    'status_path=s' => \$Status_Path,
    'stop_on_error:s' => \($stop_on = 'n'),
    'wait_state_timeout=s' => \$time_out,
    'DB=s' => \$DB2,
    'epdu:s' => \$ePDU,
    'FSP:s' => \$cronus[0],
    'cronus:s' => \$cronus[1],
    'status_file=s' => \$status_file,	
    'tool_path:s' => \$tool_path,	
    'ipl_stack:s' => \$ipl_stack, 
    'mnfg:s' => \($mnfg = 'n'), 
    'debug:s' => \($debug = 'n'), 
    'help|?' => \$help
) or die parmHelp();

if($c < 0 || $help) { print "missing parms\n"; parmHelp(); exit(0); }                  # If the user requested help 

if($tmpIPLs) { @IPLs_wanted = split(';', $tmpIPLs);  }   # If we have a list of wanted IPLs passed in 

# $option
chomp($option); 
if($option)
{
    $option = lc($option); 
    if($option ne 'on' && $option ne 'off' && $option ne 'soft' && $option ne 'reboot' && $option ne 'cycle' && $option ne 'ffdc' && $option ne 'reset' && $option ne 'ac' && $option ne 'warm')
    {
        print "Invalid option entered. $option\n";
        print "Valid options are: on / off / soft / reboot / cycle / reset / AC / warm / ffdc \n";
        exit(1);
    }
}

# Paths
chomp($FFDC_Path);
$FFDC_Path =~ s/^\s+//;
if($FFDC_Path) 
{
    if( -d $FFDC_Path) { }
    else { die "FFDC Path doesn't exist!\n"; }
}
chomp($Status_Path);
$Status_Path =~ s/^\s+//;
if($Status_Path) 
{
    if( -d $Status_Path) { }
    else { die "Status Path doesn't exist!\n"; }
}
if(!$base_path && $set_file) { die "**ERROR** -p <setup_file_path> option not given \n"; } 
chomp($base_path);
$base_path =~ s/^\s+//;
if($base_path) 
{
    if( -d $base_path) { }
    else { die "Setup file path doesn't exist!\n"; }
}

# Files 
if($set_file)
{
    my $tmp = "$base_path/$set_file";
    if( -e $tmp) {}
    else { die "Setup file doesn't exist!\n"; }
}
if($status_file)
{
    my $tmp = $status_file;
    if( -e $tmp) {}
    else { die "Status file doesn't exist!\n"; }
}
# Derived 
if($bmc_name)
{
    chomp($bmc_name);
    $bmc_name =~ s/^\s+//;
    my $target = $bmc_name;
    if($target =~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
    { 
        $bmc_IP = $target;
        my $cmd = "host $target";
        my $ret = qx/$cmd/; 
        my @tmp1 = split('pointer', $ret);
        $tmp1[1] =~ s/^\s+//;
        chomp($tmp1[1]);
        my @tmp_split = split(/\./, $tmp1[1]);
        $bmc_name = $tmp_split[0];
    }
    else  
    { 
        $bmc_IP = getIP($target);
        my @tmp = split(/\./, $target);
        $bmc_name = @tmp[0];
    }
}

if($set_file)
{
    
    #############################################################
    # Read the given setup file and find the system information #
    #############################################################

    # Find out if the file exists
    $set_file = "$base_path/$set_file";
    open FILE, $set_file or die "**ERROR** File $set_file not found! \n";

    print "We opened $set_file \n";
    my $row = '';                           # Used to store the row from the status file
    my @tmp = '';                           # Temp array to use for the split of the $row
    my $ret = '';                           # Used to catch the return from the command we issue 

    while($row = <FILE>)                    # Read through each row of the setup file 
    {
        chomp($row);                        # Chomp any extra characters from the row
        @tmp = split "]", $row;             # Split the row based on a space character

        if($tmp[0] eq '[BMC_name')          # If we found the BMC_name line in the setup file
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            my $target = $tmp[1]; 
            if($target =~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
            { 
                $bmc_IP = $target;
                my $cmd = "host $target";
                $ret = qx/$cmd/; 
                my @tmp1 = split('pointer', $ret);
                $tmp1[1] =~ s/^\s+//;
                chomp($tmp1[1]);
                my @tmp_split = split(/\./, $tmp1[1]);
                $bmc_name = $tmp_split[0];
            }
            else  
            { 
                #$bmc_name = $target; 
                $bmc_IP = getIP($target);
                my @tmp = split(/\./, $target);
                $bmc_name = @tmp[0];
            }
        }
        if($tmp[0] eq '[BMC_user')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { $bmc_user = $tmp[1]; }
        }
        if($tmp[0] eq '[BMC_Password')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            $bmc_pwrd = $tmp[1];
        }
        if($tmp[0] eq '[OS_Host')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            $r_host = $tmp[1];
        }   
        if($tmp[0] eq '[OS_user')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            $r_user = $tmp[1];
        }
        if($tmp[0] eq '[OS_Password')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            $r_pwrd = $tmp[1];
        }
        if($tmp[0] eq '[FFDC_Path')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) 
            {
                if( -d $tmp[1]) { $FFDC_Path = $tmp[1]; }
                else { print "FFDC Path $tmp[1] is not valid!\n"; exit(1) }
            }
        }
        if($tmp[0] eq '[Status_Path')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) 
            { 
                if( -d $tmp[1]) { $Status_Path = $tmp[1]; }
                else { print "Status Path $tmp[1] is not valid!\n"; exit(1) }
            }
        }
        if($tmp[0] eq '[Tool_Path')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) 
            { 
                if( -d $tmp[1]) { $tool_path = $tmp[1]; }
                else { print "Tool Path $tmp[1] is not valid!\n"; exit(1) }
            }
        }
        if($tmp[0] eq '[stop_on_error')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1] && $tmp[1] eq 'yes') { $stop_on = 'y'; }
            
        }
        if($tmp[0] eq '[wait_state_timeout')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { $time_out = $tmp[1]; }
        }
        if($tmp[0] eq '[DB')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { $DB2 = $tmp[1]; }
        }
        if($tmp[0] eq '[ePDU')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { $ePDU = $tmp[1]; }
        }
        # Added for Cronus 
        if($tmp[0] eq '[FSP')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { @cronus[0] = $tmp[1]; }
        }
        if($tmp[0] eq '[cronus')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            if($tmp[1]) { @cronus[1] = $tmp[1]; }
        }
        if($tmp[0] eq '[IPLS')
        {
            chomp($tmp[1]);
            $tmp[1] =~ s/^\s+//;
            # Split out the IPLs, based on ; ?
            @IPLs_wanted = split ";", $tmp[1];
        }
    }   
    close FILE;                             # Close the file now that we have read in all we need
}
#############################################################
# Validate the parms passed and generate the derived values #
#############################################################

# Find the hostname of the current LCB we are running from
my $cmd = "hostname";
$wrk_name = qx/$cmd/;
chomp($wrk_name);

#########################################################
# Check that we have all the parms we need to run!      #
#########################################################
if(!$bmc_IP) { print "Missing BMC name / IP \n"; exit(1); }     # BMC IP address
if(!$bmc_name) { print "Missing BMC name / IP \n"; exit(1); }   # BMC Hostname
if(!$bmc_user) { print "Missing BMC UserID \n"; exit(1); }      # BMC USERID
if(!$bmc_pwrd) { print "Missing BMC password \n"; exit(1); }    # BMC Password

####### Check if we were given a host OS #######
if($r_host)
{
    if(!$r_user) { print "Missing Host userid \n"; exit(1); }
    if(!$r_pwrd) { print "Missing Host password \n"; exit(1); }
}
if(!$FFDC_Path) { print "Missing FFDC Path \n"; exit(1); }      # FFDC Path
if(!$Status_Path) { print "Missing Status Path \n"; exit(1); }  # Status Path
if(!$IPLs_wanted[0]) { print "Missing IPL list \n"; exit(1); }  # IPLs wanted list


#########################################################
#                   Start of main program body          #
#########################################################
# Figure out the file name for logging the status. 
our $nice_timestamp = getTimeStamp('file');

if( -e $status_file) { $log_file = $status_file; }
else { $log_file = "$Status_Path/$bmc_name.$nice_timestamp.status"; }

open STATUS_FILE, ">>$log_file" or die "**ERROR** Unable to open the file for writing\n";

print_to_status("********** Start of the Status file for $bmc_name **********\n");

print_to_status("Starting op_boot_test.pl"); 

if($set_file) { print_to_status("We are using $set_file for system settings"); }

# Check the passed parms for $stop_on
if($stop_on eq '0') { $stop_on = 'n'; }
if($stop_on eq '1' || !$stop_on) { $stop_on = 'y'; }
if($stop_on ne 'n' && $stop_on ne 'y')  { print_to_status("**ERROR** Invalid stop on setting!"); exit(1); }

# Check the passed parms for $debug
if($mnfg eq '0') { $mnfg = 'n';} 
if($mnfg eq '1' || !$mnfg) { $mnfg = 'y'; }
if($mnfg ne 'n' && $mnfg ne 'y') { print_to_status("**ERROR** Invalid mnfg setting!"); exit(1); }
if($mnfg eq 'n') { $mnfg = '';} 

# Check the passed parms for $debug
if($debug eq '0') { $debug = 'n';} 
if($debug eq '1' || !$debug) { $debug = 'y'; }
if($debug ne 'n' && $debug ne 'y') { print_to_status("**ERROR** Invalid debug setting!"); exit(1); }
if($debug eq 'n') { $debug = '';} 

####### Check if we were asked to run an AC Cycle IPL but no ePDU name was passed in #######
my $tmp_ipl = 'BMC AC Cycle';
if ( grep( /^$tmp_ipl$/, @IPLs_wanted ) ) { if(!$ePDU) { print_to_status("No ePDU passed in! Unable to do AC cycle IPLs"); print_to_status("@IPLs_wanted", 'clean'); exit(1); } }

# Check if the logresults files exist else don't try and log
if($DB2)
{
    if(logResults("check_log_files")) 
    { 
        $DB2 = ''; 
        print_to_status("External Log Scripts not found. Disabling external logging."); 
    }                # Returns non-zero if any of the files are not found
}

my $result = '';
########################################################
# Output all the parms passed in w/ passwords hidden   #
########################################################
if($debug) 
{ 
    print_to_status("Debug value is $debug", 'debug'); 
    print_to_status("Outputting submitted parms:", 'debug');
    
    ################ BMC Options ################
    print_to_status("BMC Options:", 'clean'); 
    print_to_status("--bmc_name $bmc_name", 'clean'); 
    print_to_status("--bmc_user $bmc_user", 'clean'); 
    print_to_status("--bmc_password $bmc_pwrd", 'clean'); 

    ################ Host Options ################
    print_to_status("Host Options:", 'clean'); 
    print_to_status("--os_name $r_host", 'clean'); 
    print_to_status("--os_user $r_user", 'clean'); 
    print_to_status("--os_password $r_pwrd", 'clean'); 
    
    ################ FFDC / Status ################
    print_to_status("FFDC / Status:", 'clean'); 
    print_to_status("--ffdc_path $FFDC_Path", 'clean');
    print_to_status("--status_path $Status_Path", 'clean');
    print_to_status("--status_file $status_file", 'clean');
    print_to_status("--tool_path $tool_path", 'clean');
    
    ################ Misc ################
    print_to_status("Misc:", 'clean'); 
    print_to_status("--stop_on_error $stop_on", 'clean');
    print_to_status("--wait_state_timeout $time_out", 'clean');
    print_to_status("--ipls @IPLs_wanted", 'clean');
    print_to_status("--ipl_stack $ipl_stack", 'clean');
    print_to_status("--mnfg $mnfg", 'clean');
    print_to_status("--DB $DB2", 'clean');
    print_to_status("--epdu $cronus[0]", 'clean');
    print_to_status("--cronus $cronus[1]", 'clean');   
}
################################################################
# Figure out what kind of system this is using bmc_sysinfo.pl  #
################################################################
getSystemInfo();            

#####################################################################
# Add code to use the passed in $ipl_stack instead of the default   #
#####################################################################
my @IPL_Loop;
my @tmp_Loop;
my $tmp;

if($debug) { print_to_status("Checking the stack", 'clean'); }
if($ipl_stack) # Parse the passed ipl stack then assign it to @IPL_Loop
{ 
    @IPL_Loop = split(',', $ipl_stack); 
    # Add code to check if we are in mnfg mode and make sure the list of IPLs are (mfg). Then strip the (mfg) from each. else call error
    if($mnfg) 
    {
        # Loop through the @IPL_Loop and make sure each has (mfg) suffix, then strip the suffix.
        # Count the number of entries. 
        foreach(@IPL_Loop)
        {
            if($_ =~ "(mfg)")   # Strip the (mfg) off the IPL name, chomp extra whitespace.
            {  
                $tmp = substr($_, 0, -5);           # Trim off the last 5 chars "(mfg)"
                $tmp =~ s/\s+$//;                   # Trim any left over white space at the end of the string
                push(@tmp_Loop, $tmp);              # Push into temp array. 
            }
            else                # We got passed a non (mfg) IPL name, call an error
            {
                print_to_status("**ERROR** Invalid IPL passed in stack. $_."); exit(1); 
            }
        }        
        # Once we are finished looping through the passed stack, @tmp_Loop should have the valid stack, so copy it to @IPL_Loop
        @IPL_Loop = @tmp_Loop;
    }
    # If we are not in mnfg mode and the passed stack has (mfg) IPLs, call error
    else
    {
        # Loop through the @IPL_Loop and make sure there are no (mfg) IPLs.
        foreach(@IPL_Loop)
        {
            if($_ =~ '(mfg)') { print_to_status("**ERROR** Invalid IPL passed in stack. $_."); exit(1); }
        }   # If no (mfg) IPL names were found, we are good to go! 
    }
}                
else {  @IPL_Loop = ('BMC Power Off','BMC Host reboot','BMC Power on' ); }   # Default stack

our $IPL_run = '';
my $max_try = 0;
my $create_endit;

# If we want to run the loop
if(!$option)
{
    print_to_status("**************** Adjusting the IPL lists ****************");
    fixIPLList(@IPLs_wanted); 
    print_to_status("");
    
    ################################### Check for environment variables ###################################
    if($ENV{'START_TEST_TIME'})             # This variable is set by a wrapper script for op_boot_test.pl
    { 
        # Grab the START_TEST_TIME, MCH_SER_NUM, MCH_TYPE_MODEL ENV variables 
        $start_test_time = $ENV{'START_TEST_TIME'}; 
        $mch_ser_num = $ENV{'MCH_SER_NUM'};
        $mch_type_model = $ENV{'MCH_TYPE_MODEL'};   
        
        # Check for IPL_PASS to be 1, if it is, then the previous wrapper called AutoHPM and the hpm update was counted as an IPL
        if($ENV{'IPL_PASS'}) { @results[8]++; }         
        
    }
    else                                    # An external wrapper isn't running, so set the environmental variable
    {
        $ENV{'MCH_SER_NUM'} = $mch_ser_num;
        $ENV{'MCH_TYPE_MODEL'} = $mch_type_model;
        $ENV{'IPL_PASS'} = 0;
        $ENV{'IPL_FAIL'} = 0; 
        if($DB2) { logResults("start_test_run"); }                          # Initial record creation     
        $create_endit = 1;                                                  # The external wrapper didn't create the endit button
    }
    ################################### End Check for environment variables ################################
    
    if($create_endit)
    {
        # Create the End button for the run
        my $p = $$;
        $end_pid = fork();                  # For the console logging off
        if( $end_pid == 0 )                 # If we are in the forked process
        {
            my $cmd = "if xhost 2>&1; then echo \"yes\"; else echo \"no\"; fi";
            my $ret = qx/$cmd/;
                
            if($ret =~ /yes/)
            {
                my $cmd = "autoend -- -fg darkblue -bg honeydew $p ";
                my @ret = qx/$cmd/; 
            }
            exit(0);
        }
        #my $res = waitpid($end_pid, WNOHANG);                          # Wait for the child pid to die but do not hang.
        print_to_status("We have started autoend");
    }
    
    print_to_status("Doing $repeat IPLs");
    log_sol_console('end');                                 # Make sure the SOL console is deactivated 
    ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'off');    # Make sure the BMC is at the powered off state 
    waitforstate('off');

    # Clear SELs before syncing time
    print_to_status("******************* Clearing SEL *******************");
    
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sel clear 2>&1";
    print_to_status("Issuing: $cmd");
    my $ret = qx/$cmd/;
    
    print_to_status("******************* SEL Cleared *******************");
        
    # Sync time on the BMC w/ LCB
    print_to_status("**************** Checking the Time ****************");
    syncTime();
    print_to_status("");
    

    
    ############################### START of the IPL LOOP ###############################
    for(my $i = 1; $i <= $repeat; $i++)
    {
        print_to_status("**********Starting IPL $i of $repeat**********"); 
                
        # Check the boot count
        checkBootCount(); 
        
        # Check the State of the system
        checkSysState(1); 
        
        $solPid = findPid($bmc_IP, $bmc_user);                      # Check if we have a SOL pid! 
        $max_try = 0;                                               # Reset the max tries to open a SOL console 
        
        while(!$solPid && $max_try < 3)
        {
            log_sol_console('start');                               # Start the SOL Console
            $max_try++;
        }
        # Pop off the IPL
        $IPL_run = getNextIPL(\@IPL_Loop);
        
        # Display the Stack
        showStack(@IPL_Loop);
        
        # call the function to do the IPL - Return pass or fail
        $start_ipl_time = getTimeStamp();
        $result = doIPL($IPL_run);  
        
        # Update the DB
        #if($DB2) { dbPost('ipl', $IPL_run ,$result); }  # Update after ipl finished
        if($DB2) { logResults("ipl_end", $IPL_run, $result, $start_ipl_time); } # Update after ipl finished
                
        # If we failed, dump FFDC - This can take a long time. Might need a timeout ?
        if(!$result)                                            
        {
            print_to_status("The stop on setting is $stop_on");
            if($stop_on eq 'y') { stopOn(); }
            print_to_status("IPL_FAILED: \"$IPL_run\" failed.");
            dump_FFDC();
        }
        else 
        { 
            print_to_status("IPL_SUCCESS: \"$IPL_run\" succeeded."); 
            dump_FFDC(1);                                   ## Added to clean things up 
        }
        
        # Add the function to analyse the current FFDC files
        ffdcSummary(); 
        
        # Add an IPL summary here
        print_results();
        
        # Check the boot count
        #checkBootCount(); 
        
        print_to_status("**********Finished IPL $i of $repeat**********\n\n");
        
        # IF we are at the OS, get the system information?
        my $state = checkSysState();
        if($state == 3) { readFromHost(); }
                
        log_sol_console('end');
    }
    #if($DB2) { dbPost('end'); }                         # ENDing update after IPL tests are finished.
    if($DB2) { logResults("end_test_run"); }             # ENDing update after IPL tests are finished.
    endTest(); 
}
else
{
    $DB2 = '';                                          # We don't want to update the DB for single IPLs
    if($option eq 'ffdc')                               # Dump FFDC using parameter file
    {
        dump_FFDC(3); 
    }
    ################################# Else we want to do the given IPL #################################
    else                                                
    {
        switch ($option) {
            case 'on'       { $IPL_run = "BMC Power on" }               # BMC Power on      - Works
            case 'off'      { $IPL_run = "BMC Power Off" }              # BMC Power off     - Works 
            case 'soft'     { $IPL_run = "BMC Power Soft" }             # BMC Power soft    - Works 
            case 'reboot'   { $IPL_run = "BMC Host reboot" }            # OS reboot         - Works 
            case 'cycle'    { $IPL_run = "BMC Power Cycle" }            # BMC Power Cycle   - Works
            case 'reset'    { $IPL_run = "BMC Power Reset" }            # BMC Power Reset   - Works from OS  
            case 'ac'       { $IPL_run = "BMC AC Cycle" }               # BMC AC cycle      - Works 
            case 'warm'     { $IPL_run = "BMC MC Reset warm" }          # BMC MC Reset warm - Works
            else            { print "We shouldn't be here!\n"; exit(1) }    # Should never get here!
        }
        checkBootCount(); 
        $result = doIPL($IPL_run); 
        checkBootCount(); 
        if(!$result)                                            
        {
            print_to_status("IPL_FAILED: \"$IPL_run\" failed.");
            dump_FFDC();
        }
        else 
        { 
            print_to_status("IPL_SUCCESS: \"$IPL_run\" succeeded."); 
            dump_FFDC(1);                                               ## Added to clean things up 
        }
    }
}

print_to_status("Normal Completion.");
print_to_status($log_file);

close STATUS_FILE; 
exit(0); 

#########################################################
#########################################################
#                   End of main program body            #
#########################################################

#########################################################
#                   Start of functions                  #
#########################################################

sub ipmiPowerChange                     # ipmiPowerChange($bmc_IP, $bmc_pwrd, $host, 'on');
{
    #global STATUS_FILE;
    my $n = 0;
    my $b_ip = @_[0];
    my $b_pw = @_[1];
    my $b_ta = @_[2];
    my $action = @_[3];
    my $cmd = '';
    
    if($action eq 'reboot')
    {
        print_to_status("");
        print_to_status("-------------- Issuing the reboot  --------------");
        remotecmd();
        #waitforstate('reboot');
    }
    ######### Else handle on, off, soft, reset, and cycle #########
    elsif($action eq 'on' || $action eq 'off' || $action eq 'soft' || $action eq 'reset' || $action eq 'cycle')
    {
        $cmd = "ipmitool -I lanplus -H $b_ip -P $b_pw -U $bmc_user power $action 2>&1";
        print_to_status("Issuing: $cmd");
        print_to_status("");
        print_to_status("-------------- Issuing the power $action --------------");
        
        my $ret = qx/$cmd/; 
        
        print_to_status("Command has been issued");
        print_to_status($ret);
    }
    elsif($action eq 'warm')
    {
        # Kill the SOL console 
        log_sol_console('end');
        
        $cmd = "ipmitool -I lanplus -H $b_ip -P $b_pw -U $bmc_user mc reset $action 2>&1";
        print_to_status("Issuing: $cmd");
        print_to_status("");
        print_to_status("-------------- Issuing the mc reset $action --------------");
        
        my $ret = qx/$cmd/; 
        
        print_to_status("Command has been issued");
        print_to_status("Sleeping 30 seconds for reset to trigger");
        sleep 30;
        print_to_status($ret);
        
        # Restart the SOL console
        log_sol_console('restart');
    }
}
#####################################
# Pass in the state to wait for     #
# on / (off/soft) / host / reboot   #
#####################################
sub waitforstate
{
    my $w_state = @_[0];                # The state to wait for
    my $found = 0;
    my $ping_cmd = '';
    my $r = 0;
    my $i = 0;                      # Used to loop through a sleep sequence for the power on w/o Host
    my $retval = '';
    my $match = '';
    my $count = 0; 
    my $ret = 1;                    # Return value for the check on failed to reach state - 1 = good 0 = bad
    my $total_wait = ($time_out*0.25);
    
    if($w_state eq 'host' || $w_state eq 'on' || $w_state eq 'reboot' || $w_state eq 'cycle')
    {
        if($r_host)                     # If we have a host to run to 
        {
            if($w_state eq 'cycle')
            {
                sleep 15;               # Sleep for 15 seconds to wait for the ipmi cycle to execute
            }
            print_to_status("Checking every 15 seconds for up to $total_wait minutes for $r_host to become active");
            my $cmd = "jrcmd -l $r_user -p $r_pwrd -s $r_host 'uptime' 2>/dev/null ";
            while(!$found)
            {       
                $retval = qx/$cmd/;                     # Why do we get a funky character on success?
                $match = first { /load/ } $retval;      
                
                if(!$match)                             # Check if the return had an ERROR  
                {
                    print "#";
                    print STATUS_FILE "#";
                    $count++; 
                    sleep 15; 
                }
                else                                    # We had successful connected to the OS 
                {
                    print "\n\r";
                    print STATUS_FILE "\n";
                    print_to_status("OS is now talking");
                    $found = 1;
                    $count = 0;                         # Reset the count as the OS is talking fine
                    last; 
                }
                if($count > $time_out) { last;}         # Exceeded the time out - Break out of while loop!
            }
            if($count > $time_out)
            {
                print "\n\r";
                print STATUS_FILE "\n";
                print_to_status("We timed out waiting for the OS to return - $total_wait minutes");
                $count = 0; 
                $ret = 0;
            }
        }                                               # End of the Host stuff
        else                                            # We need something to check that the power on is done
        {
            if($w_state eq 'on' || $w_state eq 'cycle')
            {
                $ret = ipmiCheckPowerState($bmc_IP, $bmc_pwrd, $host, 'on');
            }
            print_to_status("Waiting for the system to power $w_state"); 
            
            while($count < $time_out)
            {
                print "#";                              # Output to show the test is doing something
                print STATUS_FILE "#";
                $count++;
                sleep 15;                               # Sleep for 15 seconds 
            }
            print "\n\r";
            print STATUS_FILE "\n";
            my $x = $count*15; 
            print_to_status("We waiting for $total_wait minutes for the power $w_state to complete");
        }
    }   # End of the if wait state is host / on / reboot / cycle 
    else                                                # Wait state is off / soft 
    {
        # Delay for power to be off
        $ret = ipmiCheckPowerState($bmc_IP, $bmc_pwrd, $host, 'off');
    }

    return $ret; 
}
#############################################################################
# This function will read from the host OS to gather data.                  #
# eg; # OS level (uname -a)                                                 #
# Execute Opal-PRD tests from the OS                                        #
# eg; occ disable, occ enable, occ reset                                    #
# Other commands can be added to run commands and gather data from the OS   #
#############################################################################
sub readFromHost
{
    # Need to use an outside script? or system ssh command to get the data we want.
    my @ret; 
    my $opt = @_[0]; 
    
    if(!$opt)
    {
        print_to_status("Gatherin system info from the OS:");
        ##### Check the OS Level #####
        print_to_status("OS level:");
        my $cmd = "jrcmd -l $r_user -p $r_pwrd -s $r_host 'uname -a' 2>&1";
        print_to_status("$cmd");
        @ret = qx/$cmd/;
        printf STATUS_FILE "@ret\n";
        print("\r\n@ret\r\n");
    }
    
    if($opt eq 'Opal')
    {
        ##### Opal-PRD App #####
        #Two mfg cmds:
        # OCC Disable 
        my $cmd = "jrcmd -t 60 -l $r_user -p $r_pwrd -s $r_host 'echo $r_pwrd | sudo -kS opal-prd occ disable' 2>&1";
        @ret = qx/$cmd/;
        sleep 5;
        
        # OCC Enable 
        my $cmd = "jrcmd -t 60 -l $r_user -p $r_pwrd -s $r_host 'echo $r_pwrd | sudo -kS opal-prd occ enable' 2>&1";
        @ret = qx/$cmd/;
        sleep 5;
        
        # OCC Reset
        my $cmd = "jrcmd -t 60 -l $r_user -p $r_pwrd -s $r_host 'echo $r_pwrd | sudo -kS opal-prd occ reset' 2>&1";
        @ret = qx/$cmd/;
        sleep 5;
    }
}
# Sending a remote command to the OS using an expect script
# Currently this limited to reboot only! 
sub remotecmd
{
    # Ubuntu doesn't allow root login so need to sudo for the reboot - echo 'password' | sudo -kS command
    my $cmd = "jrcmd -l $r_user -p $r_pwrd -s $r_host 'echo $r_pwrd | sudo -kS reboot' 2>&1";
    
    print_to_status("Issuing: $cmd");
    print_to_status("We are issuing a reboot to the OS and sleeping for 15 seconds.");
        
    my @ret = qx/$cmd/;
    
    my $match = first { /The system is going down for reboot NOW!/ } @ret;  
    # Need to check the returned data for the "The system is going down for reboot NOW!" 
    # IF we find it, we need to send that line to the output, else handle the error! 
    print_to_status($match);
    sleep 15;
}
# This function will wait for the power state to reach Off before we go onto the next iteration of the IPL loop
sub ipmiCheckPowerState()
{
    my $n = 0;
    my $b_ip = @_[0];
    my $b_pw = @_[1];
    my $b_ta = @_[2];
    my $e_state = @_[3]; 
    my $action = 'status';
    my $l = 1; 
    my $ret = '';
    my $count = 0; 
    my $ret_val = 1; 
    
    $cmd = "ipmitool -I lanplus -H $b_ip -P $b_pw -U $bmc_user power $action 2>&1";
    print_to_status("Issuing: $cmd");
    print_to_status("");
    print_to_status("-------------- Issuing the power $action --------------");
    
    
    # Need to add a count in here to terminate the waiting for the power state to change.
    while($l)
    {
        $ret = qx/$cmd/; 
        
        if($ret =~ /$e_state/)
        {
            print "\n\r";
            print STATUS_FILE "\n";
            print_to_status("Power is $e_state");
            $l = 0;                 # Set loop to end as we have reached expected power state 
        }
        else 
        {
            print "#";
            print STATUS_FILE "#";
        }
        
        sleep(15);                  # Wait 15 seconds then try the command again.
        $count++;
        
        if($count > 40)
        {
            print_to_status("");
            print_to_status("We have waited longer than 10 minutes for power state to change");
            $ret_val = 0; 
            last; 
        }
    }   
    print_to_status("Sleeping for 15 seconds while we wait for the system to fully power $e_state");
    sleep(15);
    print_to_status($ret);
    return $ret_val; 
    
}
##########################################################
# This function will output to the IPL run's status file #
##########################################################
sub print_to_status
{
    my $msg = @_[0];
    my $flag = @_[1]; 
    my $replace = " ********";
    my $tout = '';
    
    if($msg)
    {
        if(!$flag)
        {
            # Generate a time stamp for each line of the status file 
            my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
            my $nice_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year+1900,$mon+1,$mday,$hour,$min,$sec);
            my $tz = strftime("%Z", localtime());
            
            ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = gmtime(time);
            my $nice_gm_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year+1900,$mon+1,$mday,$hour,$min,$sec);
            
            $tout = "#($tz) $nice_timestamp - (UTC) $nice_gm_timestamp - ";
                
            # Modify the msg to hide the passwords  
            if($bmc_pwrd) { $msg =~ s/\s$bmc_pwrd/$replace/g; } 
            if($r_pwrd) { $msg =~ s/\s$r_pwrd/$replace/g; }
        }   
        if($flag =~ 'debug')
        {
            $tout = '**DEBUG**';
        }
        # print the output to the status file
        print "$tout $msg\n\r";
        print STATUS_FILE "$tout $msg\n";
    }
    else
    {
        print "\n\r";
        print STATUS_FILE "\n";
    }
    
}

#######################################
# This function will take 2 options   #
# Start and end                       #
####################################### 
sub log_sol_console
{
    $nice_timestamp = getTimeStamp('file');
    
    my $act = @_[0];
        
    if($act eq 'start')                         # If we requested to start an SOL console log
    {
        $sol_file = "$FFDC_Path/$bmc_name.$nice_timestamp.sol";
          
        print_to_status("-------------- Starting SOL console log --------------");
        
        ##################################################################
        # Activate the SOL console                                       #
        # ipmitool -I lanplus -H <BMC IP> -P <BMC Password> sol activate #
        ##################################################################
        my $pid = fork();                   # For the console logging off
        
        if( $pid == 0 )                     # If we are in the forked process
        {
            
            #my $cmd = "ipmitool -v -v -v -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sol activate > $sol_file";  # Used for debug
            my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sol activate > $sol_file 2>&1";
            print_to_status("$cmd");
            my @ret = qx/$cmd/; 
            
            exit(0);
        }               
        my $res = waitpid(-1, WNOHANG);                         # Wait for the child pid to die but do not hang.
        
        sleep(5);       
        $solPid = findPid($bmc_IP, $bmc_user);                      ## Added to find out if we have started a process.
        if($solPid)
        {
            print_to_status("The SOL pid is: $solPid");
            
        }
        else
        {
            print_to_status("Failed to Open SOL connection. Will try a max of 3 times.");
            sleep(10);
        }
    }
    elsif($act eq 'end')                                                            # We were requested to close the SOL console        
    {
        print_to_status("-------------- Closing SOL console log --------------");
        #####################################################################
        # Deactivate the SOL console                                        #
        # ipmitool -I lanplus -H <BMC IP> -P <BMC Password> sol deactivate  #
        #####################################################################
        my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sol deactivate";
        print_to_status("$cmd");
        my @ret = qx/$cmd/; 
                
        print_to_status("Sleeping for 10 seconds to wait for the BMC to deactivate the sol");
        sleep 10;
        killPid($bmc_IP, $bmc_user); 
        print_to_status("Sleeping for 10 seconds to wait for the LCB to kill the process");
        sleep 10;
        $solPid = findPid($bmc_IP, $bmc_user);
        # Could add a check for the pid here and loop X times till the process dies?   ***CHK***
        
        print_to_status("-------------- SOL console log Closed --------------");
        print_to_status("");
    }
    elsif($act eq 'restart')
    {
        # The SOL Console connection will some times go away. This is due to AC cycle or mc reset.
        # Need to restart the console using the same output file.
        # Check if the old process is still running / BMC Connection check?
        
        my $pid = fork();                   # For the console logging off
        
        if( $pid == 0 )                     # If we are in the forked process
        {
            
            #my $cmd = "ipmitool -v -v -v -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sol activate > $sol_file";  # Used for debug
            my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sol activate >> $sol_file 2>&1";
            print_to_status("$cmd");
            my @ret = qx/$cmd/; 
            
            exit(0);
        }               
        my $res = waitpid(-1, WNOHANG);                         # Wait for the child pid to die but do not hang.
        
        sleep(5);       
        $solPid = findPid($bmc_IP, $bmc_user);                      ## Added to find out if we have started a process.
        if($solPid)
        {
            print_to_status("The SOL pid is: $solPid");
            
        }
        
    
    }
    
}
##############################################################
# This function figure out the results for the current round #
##############################################################
sub print_results()
{
    my $p_tot = 0;
    my $f_tot = 0; 
    my $mfg = '';
    
    #####################################
    #  IPL Results:                     #
    # 0 BMC Power on                    #
    # 1 BMC Host re-ipl                 #
    # 2 BMC Power Cycle,                #
    # 3 BMC Power Reset,                #
    # 4 BMC Power Off,                  #
    # 5 BMC Power Soft                  #
    # 6 BMC AC Cycle                    #
    # 7 BMC MC Reset warm               #
    #####################################
    for(@results) { $p_tot += $_; }                                                                     # Total up the passes
    for(@fails) { $f_tot += $_; } 
    
    if($mnfg) { $mfg = "(mfg)"; }
    # Total up the fails 
    printf("%-24s  %4s  %4s\n\r", "IPL type", "Pass", "Fail");
    print "=====================================\n\r";
    printf("%-24s %4u %4u\n\r", "BMC Power on $mfg",@results[0],@fails[0]);
    printf("%-24s %4u %4u\n\r", "BMC Host re-ipl $mfg",@results[1],@fails[1]);
    printf("%-24s %4u %4u\n\r", "BMC Power Cycle $mfg",@results[2],@fails[2]);
    printf("%-24s %4u %4u\n\r", "BMC Power Reset $mfg",@results[3],@fails[3]);
    printf("%-24s %4u %4u\n\r", "BMC Power Off $mfg",@results[4],@fails[4]);
    printf("%-24s %4u %4u\n\r", "BMC Power Soft $mfg",@results[5],@fails[5]);
    printf("%-24s %4u %4u\n\r", "BMC AC Cycle $mfg",@results[6],@fails[6]);
    printf("%-24s %4u %4u\n\r", "BMC MC Reset warm $mfg",@results[7],@fails[7]);
    printf("%-24s %4u %4u\n\r", "BMC oob hpm",@results[8],@fails[8]);
    print "=====================================\n\r";
    printf("%-24s %4u %4u\n\r\n\r\n\r", "Totals:", $p_tot, $f_tot);

    
    printf STATUS_FILE ("%-24s  %4s  %4s\n", "IPL type", "Pass", "Fail");
    print STATUS_FILE "=====================================\n";
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Power on $mfg",@results[0],@fails[0]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Host reboot $mfg",@results[1],@fails[1]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Power Cycle $mfg",@results[2],@fails[2]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Power Reset $mfg",@results[3],@fails[3]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Power Off $mfg",@results[4],@fails[4]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC Power Soft $mfg",@results[5],@fails[5]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC AC Cycle $mfg",@results[6],@fails[6]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC MC Reset warm $mfg",@results[7],@fails[7]);
    printf STATUS_FILE ("%-24s %4u %4u\n", "BMC oob hpm",@results[8],@fails[8]);
    print STATUS_FILE "=====================================\n";
    printf STATUS_FILE ("%-24s %4u %4u\n\n", "Totals:", $p_tot, $f_tot);
    

}
##################################################################
# Default handler of signals sent to the script or it's children #
##################################################################
sub signal_handler 
{
    if($solPid)                             # If we have a solPid then we probably have an open console, so close it.
    {
        print "\r\nWe are logging the sol\r\n";
        log_sol_console('close'); 
    }
    #if($db_entry_open && $db_pwrd)                      # If we have an open testdata record tracking the tests runs.
    #{
        #if($DB2) { dbPost('end'); } 
        if($DB2) { logResults("end_test_run"); }             # ENDing update after IPL tests are finished.
    #}
    #system('reset'); 
    print_to_status("Abnormal Completion.");
    print_to_status($log_file); 
    print "Caught a signal!";
    exit(0); 
}
######################################################################
# This function will dump FFDC                                       #
# - Calls bmc_ffdc script                                            #
# - Saves the FFDC files given and outputs to stdout and status file #
######################################################################
sub dump_FFDC ()
{
    #########################
    # Global variable names #
    # $bmc_name             #
    # $bmc_pwrd             #
    # $pass                 #
    # $IPL_run              #
    #########################
    my $option = @_[0];
    my $cmd = '';
    my $path_check = "$FFDC_Path/$bmc_name";
    my $state = checkSysState(); 
    my $state_out = '';
    my $wrk_IP = getIP($wrk_name);
    my $host_IP = getIP($r_host);
    @cur_ffdc = '';                             # Clearing out the current FFDC array
    
    if($option) { print_to_status("FFDC Dump requested!"); }
    
    print_to_status("******************** Beginning dump of FFDC ********************");
    print_to_status("");
    
    print "Copy this data to the defect:\r\n";
    print STATUS_FILE "Copy this data to the defect:\n";
    print_to_status("");
    
    #$bld_name
    print "Build Name: $bld_name \r\n";
    print STATUS_FILE "Build Name: $bld_name \n";
    
    ######################################### Add FRU system info #########################################
    my $id = 0;
    if($sys_type =~ 'habanero') { $id = 43; }
    elsif($sys_type =~ 'palmetto') { $id = 15; }
    #elsif($sys_type =~ 'firestone') { $id = 47; }   # This might eventually move to 59
    
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user fru print $id 2>&1";   
    my @tmp;
    ################### Pull when firestone fru id # figured out 
    if($sys_type =~ 'firestone') 
    {
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 0x4f 0x4e 0x0 0x0 0x00 0x0 0x0 0x0 | xxd -r -p 2>&1";   
        my @ret = qx/$cmd/; 
        
        print_to_status($cmd);
        print "System Firmware: \r\n";
        print STATUS_FILE "System Firmware: \r\n";
        foreach(@ret)
        {
            chomp($_);
            $_ =~ s/^\s+//;
            print "$_\r\n";
            print STATUS_FILE "$_\r\n";
        }
    } 
    ################### Pull when firestone fru id # figured out 
    else 
    {
        my @ret = qx/$cmd/; 
        print_to_status($cmd);
        foreach(@ret)
        {
            chomp($_);
            @tmp = split(':', $_);
            $tmp[0] =~ s/^\s+//;
            $tmp[1] =~ s/^\s+//;
            print "$tmp[0] : $tmp[1]\r\n";
            print STATUS_FILE "$tmp[0] : $tmp[1]\r\n";
        }
    }
    print_to_status("");
    ######################################### Add AMI code info #########################################
    print "AMI Level: \r\n";
    print STATUS_FILE "AMI Level: \r\n";
    $cmd = "jrcmd -l $bmc_user -p $bmc_pwrd -s $bmc_IP 'cat /proc/ractrends/Helper/FwInfo' 2>&1";   
    my @ret = qx/$cmd/;
    foreach(@ret)
    {
        chomp($_);
        print "$_\r\n";
        print STATUS_FILE "$_\r\n";
    }
    print_to_status("");
    
    print "Workstation Name: $wrk_name \r\n";
    print STATUS_FILE "Workstation Name: $wrk_name \n";
    print "Workstation IP: $wrk_IP \r\n";
    print STATUS_FILE "Workstation IP: $wrk_IP \n";
        
    print "Partition Name: $r_host\r\n";
    print STATUS_FILE "Partition Name: $r_host \n";
    print "Partition IP: $host_IP \r\n";
    print STATUS_FILE "Partition IP: $host_IP \n";
    
    print "BMC Name: $bmc_name\r\n";
    print STATUS_FILE "BMC Name: $bmc_name\n";  
    print "BMC IP: $bmc_IP \r\n";
    print STATUS_FILE "BMC IP: $bmc_IP \n";
    
    if(@cronus[0])
    {
        print "Cronus information:\n\r"; 
        print STATUS_FILE "Cronus information:\n"; 
        print "FSP: @cronus[0]\n\r";
        print STATUS_FILE "FSP: @cronus[0]\n";
        #my $tmp_ip = getIP(@cronus[0]); 
        #print "FSP IP: $tmp_ip\n\r";
        #print STATUS_FILE "FSP IP: $tmp_ip\n";
        print "Target: @cronus[1]\n\r";
        print STATUS_FILE "Target: @cronus[1]\n";
    }
    
    print_to_status("");
        
    # Gather the state of the system
    switch ($state) {
        case 1          { $state_out = "$bmc_name is powered off" }
        case 2          { $state_out = "$bmc_name is powered on but OS is not pinging" }
        case 3          { $state_out = "$bmc_name is powered on and the OS, $r_host is pinging" }
        else            { $state_out = "$bmc_name is in an unknown state" }
    }   
    print "System status: $state_out\n\r";
    print STATUS_FILE "System status: $state_out\n";
    
    ######################################### Add Boot Status #########################################
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor list | grep \"FW Boot\" 2>&1";
    my $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    my $fwBootSts = "$tmp[0] $tmp[3]";
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sdr elist | grep \"FW Boot\"";
    $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    $fwBootSts .= " $tmp[4]";

    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor list | grep \"OS Boot\" 2>&1";
    $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    my $osBootSts = "$tmp[0] $tmp[3]";
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sdr elist | grep \"OS Boot\"";
    $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    $osBootSts .= " $tmp[4]";

    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor list | grep \"Host Status\" 2>&1";
    $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    my $hsBootSts = "$tmp[0] $tmp[3]";
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sdr elist | grep \"Host Status\"";
    $ret = qx/$cmd/;
    @tmp = split('\|', $ret);
    $hsBootSts .= " $tmp[4]";
    
    chomp($fwBootSts);
    chomp($osBootSts);
    chomp($hsBootSts);
    print "$fwBootSts\n\r";
    print "$osBootSts\n\r"; 
    print "$hsBootSts\n\r"; 
    print STATUS_FILE "$fwBootSts\n\r";
    print STATUS_FILE "$osBootSts\n\r";
    print STATUS_FILE "$hsBootSts\n\r";
    
    print_to_status("");
    
    print "--------------------------------------\n\r";
    print STATUS_FILE "--------------------------------------\n";
    
    # Print out the @Last_ten IPL array
    print "Last 10 IPLs\n\r";
    print STATUS_FILE "Last 10 IPLs\n";
    foreach(@Last_ten)
    {
        print "$_\n\r";
        print STATUS_FILE "$_\n";
    }
    
    print "--------------------------------------\n\r";
    print STATUS_FILE "--------------------------------------\n";
    
    #print_to_status("Issuing: $cmd");
    print_to_status("");
    print "FFDC Files are:\r\n";
    print STATUS_FILE "FFDC Files are:\n";
    #print_to_status("FFDC Files are:");
    
    push(@cur_ffdc, $log_file); 
    print "$log_file\r\n";
    print STATUS_FILE "$log_file\n";
    
    # Dump FFDC here using the bmc_ffdc script 
    $cmd = "bmc_ffdc $bmc_IP --password=$bmc_pwrd  --userid=$bmc_user --ffdc_dir_path=$FFDC_Path --quiet=y 2>&1"; 
    my @ret = qx/$cmd/; 
    my $sel_file = ''; 
    push(@cur_ffdc,@ret);
    
    foreach(@ret)
    {
        if($_, /$path_check/)
        {
            print "$_\r";
            print STATUS_FILE "$_";
            
            #Check if the FFDC file is the sel list
            if($_ =~ /\.sels/)  
            { 
                $sel_file = $_; 
                push(@cur_ffdc, $sel_file);
                if($option == 2) { $IPL_run = 'BMC Power on'; }
                # Call the SEL filter script using $IPL_run to pick the right whitelist 
                # Output from this script should be another file with a filter SEL list 
                # IPLs can be power on, power off, reboot, reset ?
                filterSel($sel_file, $IPL_run); 
                
                # Add code here to check if we have a tarball expanded and /fspmount/<bmc_name>/x86/bin/eSEL.pl exists
                if( -e "$tool_path/$bmc_name/x86/bin/eSEL.pl")
                {
                    # call the eSEL.pl script 
                    my $cmd = "$tool_path/$bmc_name/x86/bin/eSEL.pl -t $bmc_name -o $FFDC_Path "; 
                    #print_to_status("$cmd");
                    my @eSel_ret = qx/$cmd/; 
                    
                    # Process the return
                    foreach(@eSel_ret)
                    {
                        chomp($_);
                        if($_ =~ /$FFDC_Path/) 
                        {
                            my @eSel_tmp = split(/:/, $_);
                            $eSel_tmp[1] =~ s/^\s+//;
                            print_to_status($eSel_tmp[1], 'clean');
                            push(@cur_ffdc, $eSel_tmp[1]);
                            #print STATUS_FILE "$eSel_tmp[1]\n";
                            
                        }
                    } # end foreach to process eSEL.pl output   
                } # end of if to see if we have a eSEL.pl script
                
            } # end of if we are processing the .sels files
        } # end of if we have a ffdc file 
    } # end of foreach to process the bmc_ffdc output
    
    push(@cur_ffdc,$sol_file); 
    print "$sol_file\r\n";
    print STATUS_FILE "$sol_file\n";

    ##### Check the opal-prd info in /var/log/syslog #####
    if($state == 3)
    {
        my $cmd = "jrcmd -l $r_user -p $r_pwrd -s $r_host 'which opal-prd' 2>&1";
        my $ret = qx/$cmd/;
        if($ret =~ /no opal-prd in/) {  }
        else 
        { 
            # we are at the OS so run the Opal commands
            readFromHost('Opal'); 
            
            # cat the /var/log/syslog | opal-prd 
            my $cmd = "jrcmd -l $r_user -p $r_pwrd -s $r_host -t 300 'cat /var/log/syslog | grep opal-prd' 2>&1";
            @ret = qx/$cmd/;
            
            # Open a file for the opal-prd traces
            $nice_timestamp = getTimeStamp('file');
            my $opal_file = "$FFDC_Path/$bmc_name.$nice_timestamp.opal-prd";
            open OPAL_FILE, ">$opal_file" or warn "Unable to open the file\n";
            print OPAL_FILE "@ret\n";
            close OPAL_FILE; 
            
            push(@cur_ffdc, $opal_file); 
            print "$opal_file\r\n";
            print STATUS_FILE "$opal_file";
            
        }
    }
    
    print_to_status("");
    print_to_status("");
    print_to_status("******************* Finished dumping of FFDC *******************");
    print_to_status("");
    
    if($option != 3)
    {
        # Clear the SEL since we have gathered it already
        print_to_status("******************* Clearing SEL *******************");
        
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sel clear 2>&1";
        print_to_status("Issuing: $cmd");
        @ret = qx/$cmd/;
        
        print_to_status("******************* SEL Cleared *******************");
        print_to_status("");
    }
}
#####################################################
# This function finds the pid # for the sol console #
# and kills the process on the LCB                  #
#####################################################
sub killPid
{
    my $IP = @_[0];
    my $UID = @_[1];
    
    my $cmd = "ps -ef | egrep '$IP -P XXXXX -U $UID sol activate' | grep -v 'grep' | cut -c9-15 2>&1"; 
    my $ret = qx/$cmd/; 

    if($ret)
    {
        my $kill_cmd = "kill -9 $ret";
        print "$kill_cmd\n\r";
        $ret = qx/$kill_cmd/; 
    }
    else 
    {
        return "none"
    }

}
#################################################################################################
# This function finds the pid # for any sol processes for this BMC on the LCB we are running on #
#################################################################################################
sub findPid
{
    my $IP = @_[0];
    my $UID = @_[1];
    my $ret = 0;
    
    my $cmd = "ps -ef | egrep '$IP -P XXXXX -U $UID sol activate' | grep -v 'grep' | cut -c9-15 2>&1"; 
    $ret = qx/$cmd/; 
    
    # Check if we have a numeric return
    if ($ret =~ /\d+/)  { return $ret;  }
    else { return ''; } 
    
}
############################################################################
# This function handles the stop On conditional and kills the test cleanly #
############################################################################
sub stopOn
{
    print_to_status("IPL_FAILED: \"$IPL_run\" failed.");
    dump_FFDC();
    log_sol_console('end');
   # if($DB2) { dbPost('end'); } 
    if($DB2) { logResults("end_test_run"); }             # ENDing update after IPL tests are finished.
    
    ffdcSummary(); 
    print_results();
    endTest(); 
    print_to_status("Stop on Condition hit!");
        
    print_to_status($log_file);
    close STATUS_FILE; 
    exit(0); 
}
sub getTimeStamp
{
    my $ttype = @_[0]; 
    my $ret = '';
    my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
    
    if($ttype eq 'file') { $ret = sprintf ( "%02d%02d%02d.%02d%02d%02d",$year-100,$mon+1,$mday,$hour,$min,$sec); }
    else { $ret = sprintf ( "%04d-%02d-%02d-%02d.%02d.%02d.000000",$year+1900,$mon+1,$mday,$hour,$min,$sec); }

    return $ret; 
}

##########################
# Does the requested IPL #
##########################
sub doIPL
{
    my $ipl = @_[0];
    my $ret = 1;                            # Default value is the IPL passed - 0 = failed - 1 = IPL passed.
    my $time_stamp = getTimeStamp();        # This is the timestamp for the IPL 
    $time_stamp = substr($time_stamp, 0, -7); 
    
    if($mnfg) { print_to_status("We are doing a $ipl (mfg)"); }
    else { print_to_status("We are doing a $ipl"); }
    
    ################ 0 BMC power on #################
    if($ipl eq 'BMC Power on')
    {
        #print_to_status("We are doing a BMC Power on");
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'on');
        #if($DB2) { dbPost('update'); }                              # Update after power on requested
        #if($DB2) { logResults("still_running"); }                              # Update after power on requested
        if(waitforstate('on')) 
        { 
            $os_ping = 1;                                           # We were able to power on, if there's a host, it is pinging
            @results[0]++; 
        }
        else 
        { 
            $os_ping = 0;                                           # If we failed to power on, the OS isn't pinging! 
            @fails[0]++; 
            $ret = 0;                                               # Set the return to failed
        } 
    }
    
    ################ 1 BMC Host Reboot #################
    if($ipl eq 'BMC Host reboot')
    {
        #print_to_status("We are doing a BMC Host Reboot");
        # Reboot the system 
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'reboot');
        #if($DB2) { dbPost('update'); }                  # Update after reboot is requested
        #if($DB2) { logResults("still_running"); }
        if(waitforstate('host')) { @results[1]++; }
        else 
        { 
            @fails[1]++; 
            $ret = 0;
        }
        
    }
    
    ################ 2 BMC Power Cycle #################
    # This IPL requires the OS to be able to handle the cycle request! 
    if($ipl eq 'BMC Power Cycle')
    {
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'cycle');
        #if($DB2) { dbPost('update'); }                  # Update after cycle is requested
        #if($DB2) { logResults("still_running"); }
        # This is where we wait for x time for the re-ipl to finish
        if(waitforstate('cycle')) { @results[2]++; }
        else 
        { 
            @fails[2]++; 
            $ret = 0;
        } 
    }
    
    ################ 3 BMC Power Reset #################
    if($ipl eq 'BMC Power Reset')
    {
        #print_to_status("We are doing a BMC Power Reset");
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'reset');
        #if($DB2) { dbPost('update'); }                          # Update after power off is requested
        #if($DB2) { logResults("still_running"); }
        if(waitforstate('on')) { @results[3]++; }               # Need to handle the IPL pass / fail count better! 
        else 
        {
            @fails[3]++; 
            $ret = 0;
        }
        
    }
    
    ################ 4 BMC Power Off #################
    if($ipl eq 'BMC Power Off')
    {
        #print_to_status("We are doing a BMC Power Off");
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'off');
        $os_ping = 0;                                           # We are powering off the system 
        #if($DB2) { dbPost('update'); }                          # Update after power off is requested
        #if($DB2) { logResults("still_running"); }
        if(waitforstate('off')) { @results[4]++; }
        else 
        {
            @fails[4]++; 
            $ret = 0;
        }
        
    }
    ################ 5 BMC Power Soft #################
    # This IPL requires the OS to be able to handle the soft off request! 
    if($ipl eq 'BMC Power Soft')
    {
        #print_to_status("We are doing a BMC Power Soft");
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'soft');
        $os_ping = 0;                                           # We are powering off the system 
        #if($DB2) { dbPost('update'); }                          # Update after power off is requested
        #if($DB2) { logResults("still_running"); }
        if(waitforstate('off')) { @results[5]++; }
        else 
        {
            @fails[5]++; 
            $ret = 0;
        }
        
    }   
    ################ 6 BMC AC Cycle #################
    if($ipl eq 'BMC AC Cycle')
    {
        #print_to_status("We are doing a BMC AC Cycle");
        my $ac_file = 'pcycle'; 
        my $cmd = "which pcycle"; 
        my $ac_ret = qx/$cmd/;
        
        chomp($ac_ret); 
        
        if( -e $ac_ret ) 
        {
            print_to_status("The $ac_file exists!"); 
            #pcycle --ipc_host=rickepdu1.aus.stglabs.ibm.com --outlet_names='tul199fp' --ipc_cmd=reboot --down_time=30'
            my $cmd = "$ac_file --ipc_host=$ePDU --outlet_names=$bmc_name --ipc_cmd=reboot --down_time=30 --quiet=y"; 
            print_to_status("$cmd");
            my $result = qx/$cmd/;
                    
            print_to_status("Sleeping 90 more seconds for power cycle to finish");
            sleep 90;
        }
        else { print_to_status("The $ac_file doesn't exists. Or missing ePDU. We are unable to do an AC cycle."); $ret = 0; }
        $os_ping = 0;                                           # We are powering off the system 
        #if($DB2) { dbPost('update'); }                          # Update after IPL is requested
        #if($DB2) { logResults("still_running"); }
        if(waitforstate('off')) { @results[6]++; }
        else 
        {
            @fails[6]++; 
            $ret = 0;
        }
        
    }   
    ################ 7 BMC MC Reset warm #################
    if($ipl eq 'BMC MC Reset warm')
    {
        #print_to_status("We are doing a BMC MC Reset warm");
        ipmiPowerChange($bmc_IP, $bmc_pwrd, $r_host, 'warm');
        $os_ping = 0;                                           # We are powering off the system 
        #if($DB2) { dbPost('update'); }                          # Update after IPL is requested
        #if($DB2) { logResults("still_running"); }
        # Add a check for what state we are starting from. If on, wait for ON?  If off, wait for off. And need a timer? or a new state?
        my $c = checkSysState();
        my $wait_state = 'on';
        if($c == 1) { $wait_state = 'off'; }
        
        # Add code to restart the SOL
        #print_to_status("Sleeping 30 seconds then reconnecting the SOL");
        #sleep 30;
        #log_sol_console('restart');
        
        if(waitforstate($wait_state)) { @results[7]++; }
        else 
        {
            @fails[7]++; 
            $ret = 0;
        }
    }
    
    # Add the timestamp to the IPL we just did
    my $pdata = "$time_stamp - Doing \"$ipl\"";
    
    # Push the IPL $pdata to the @Last_ten Array.  
    # Push the IPL $pdata to the @Last_ten Array.  
    push(@Last_ten, $pdata);
    
    # If the array is over 10, shift the oldest entry off the array
    my $c = @Last_ten; 
    if($c > 10) { my $toss = shift(@Last_ten); }
    
    return $ret; 
}
########################################################
# Function to get the next IPL from the stack and add  # 
# a new, valid IPL onto the stack                      #
#  - Pass in the IPL stack array by reference          #
#  - Check the current state of the system and see if  #
# the "next" IPL is valid to run else go to the next   # 
########################################################
sub getNextIPL
{
    my $ret = '';
    my $state = checkSysState();
    my $valid = 0;
    my $count = 0;
    #########################################################
    # Update these lists to add more IPLs                   #
    #  - Use setup file to determine what IPLs are valid    #
    #########################################################
    #my @PwrOn = ('BMC Host reboot','BMC Power Off', 'BMC Power Reset', 'BMC Power Cycle', 'BMC AC Cycle','BMC Power Soft'); #, 'BMC MC Reset warm');       # IPLs valid from power on w/ OS 
    #my @PwrOnNOS = ('BMC Power Off', 'BMC Power Reset', 'BMC Power Cycle', 'BMC AC Cycle');                        # IPLs valid from power on w/o OS 
    #my @PwrOff = ('BMC Power on' , 'BMC AC Cycle' );   #, 'BMC MC Reset warm');                                # IPLs valid from power off state
    
    while(!$valid)
    {
        $ret = pop(@{$_[0]});                                                           # Pop off the next IPL in the stack
        my $c = @{$_[0]}[0];                                                            # Used to check the end of the stack to get a valid IPL added on
        
        if($c =~ /off/ || $c =~ /Reset/ || $c =~ /AC/)                                  # IF we should be at the power off state
        { 
            my $elem = $PwrOff[rand @PwrOff];
            # Check if we got 'BMC AC Cycle' and we do not have a valid ePDU
            if($elem eq 'BMC AC Cycle' && !$ePDU) { $elem = 'BMC Power on'; }           # If we randomly selected AC cycle and no ePDU was given, default to power on
            unshift(@{$_[0]}, $elem);                                                   # Add to the stack
            if($debug) { print_to_status("We added $elem to the stack", 'debug'); }
        }           
        else                                                                            # Else we are powered on so grab a random IPL from the list
        {
            my $elem = $PwrOn[rand @PwrOn];
            # Check if we got 'BMC AC Cycle' and we do not have a valid ePDU
            if($elem eq 'BMC AC Cycle' && !$ePDU) { $elem = 'BMC Power off'; }          # If we randomly selected AC cycle and no ePDU was given, default to power off
            unshift(@{$_[0]}, $elem);                                                   # Add to the stack
            if($debug) { print_to_status("We added $elem to the stack", 'debug'); }
        }
        
        # Check if the IPL we popped off is valid for the state we are in
       switch ($state) {
            case 1      { if(grep {$_ eq $ret} @PwrOff) {$valid = 1;} else { $ret = 'BMC Power on'; $valid = 1; if($debug) { print_to_status("Forced $ret", 'debug');} } }     # Check valid IPL from power off
            case 2      { if(grep {$_ eq $ret} @PwrOnNOS) {$valid = 1;} else { $ret = 'BMC Power Off'; $valid = 1; if($debug) { print_to_status("Forced $ret", 'debug');} } }   # Check valid IPLs for power on w/o OS
            case 3      { if(grep {$_ eq $ret} @PwrOn) {$valid = 1;} else { $ret = 'BMC Power Off'; $valid = 1; if($debug) { print_to_status("Forced $ret", 'debug');} } }      # Check valid IPLs for power on w/ OS
            else        {  } # Should never get here!
        }

        if($count > 9)
        { 
            print_to_status("We were unable to find a valid IPL in 10 tries");
            exit(1);
        }
        $count++;
    }
    return $ret; 
}
sub fixIPLList
{
    
    my @Wanted_list = @_;
    my @tmp;                                        # Temporary array to hold the good entries
    my @tmp_pop;                                    # Temporary array for the loops
    my @tmp_Loop; 
    my $tmp;
    
    if($debug) { print_to_status("Checking the IPL List", 'clean'); }
    #################### Start test for mnfg ####################
    if($mnfg) 
    {
        # Loop through and make sure each has (mfg) suffix, then strip the suffix.
        foreach(@Wanted_list)
        {
            if($_ =~ "(mfg)")   # Strip the (mfg) off the IPL name, chomp extra whitespace.
            {  
                $tmp = substr($_, 0, -5);           # Trim off the last 5 chars "(mfg)"
                $tmp =~ s/\s+$//;                   # Trim any left over white space at the end of the string
                push(@tmp_Loop, $tmp);              # Push into temp array. 
            }
            else                # We got passed a non (mfg) IPL name, call an error
            {
                print_to_status("**ERROR** Invalid IPL passed in list. $_."); exit(1); 
            }
        }        
        # Once we are finished looping through the passed stack, @tmp_Loop should have the valid stack, so copy it to @IPL_Loop
        @Wanted_list = @tmp_Loop;
    }
    # If we are not in mnfg mode and the passed IPL list has (mfg) IPLs, call error
    else
    {
        # Loop through and make sure there are no (mfg) IPLs.
        foreach(@Wanted_list)
        {
            if($_ =~ '(mfg)') { print_to_status("**ERROR** Invalid IPL passed in. $_."); exit(1); }
        }   # If no (mfg) IPL names were found, we are good to go! 
    }
    #################### End test for mnfg ####################
    
    @tmp = @PwrOn;                                  # Set the temp array equal to the power on IPL list 
    foreach(@tmp)
    {
        if($_ ~~ @Wanted_list) { push(@tmp_pop,$_); }   # If the entry is found in the wanted list, pop it onto the array
    }
    @PwrOn = @tmp_pop;                              # Replace the old array with the new
    undef(@tmp_pop);                                # Clear the temp array
       
    @tmp = @PwrOnNOS;                               # Set the temp array equal to the power on w/o OS IPL list 
    foreach(@tmp)
    {
        if($_ ~~ @Wanted_list) { push(@tmp_pop,$_); } 
    }
    @PwrOnNOS = @tmp_pop; 
    undef(@tmp_pop);
  
    @tmp = @PwrOff;                                 # Set the temp array equal to the power off IPL list 
    foreach(@tmp)
    {
        if($_ ~~ @Wanted_list) { push(@tmp_pop,$_); } 
    }
    @PwrOff = @tmp_pop; 
}
########################################################
# Simple function to display the stack of IPLs         #
# - Pass in the IPL stack array                        #
########################################################
sub showStack
{
    my $s = @_;
    print_to_status("**********stack!**********");
    for(my $i = 0; $i < $s; $i++)
    {
        if($mnfg) { print_to_status("@_[$i] (mfg)"); }
        else { print_to_status("@_[$i]"); }
    }
    print_to_status("**************************");
}
########################################################
# This function will check what state the IPL ended in #
# 1 - power off                                        #
# 2 - power on / OS not pinging                        #
# 3 - power on / OS pinging                            #
########################################################
sub checkSysState
{   
    my $ret = '';
    my $o = @_; 
    my $s_out = '';
    my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user chassis power status 2>&1";     # Check the power status 
    print_to_status("Issuing: $cmd");
    my $result = qx/$cmd/;
    chomp($result);         
    
    if($result =~ /off/) { $ret = 1; }                                  # If power state is off, set return to 1 
    if($result =~ /on/)                                                 # If power state is on, set return to 2 then check for OS 
    { 
        $ret = 2;                                                                       
        if($r_host)                                                     # check if there is an OS and if it's pinging
        {
            $cmd = "ping -c 1 -w 1 $r_host 2>&1";                       # ping -c 1 -w 1 $r_host
            $result = qx/$cmd/;
            if($result =~ /100%/) {}                                    # If we see "100%" that means we lost all packets and failed to ping
            else { $ret = 3; }                                          # Else we pinged the OS, set retrun to 3
        }   
    }
    
    if($o == 1)
    {
        switch ($ret) {
            case 1          { $s_out = "$bmc_name is powered off" }
            case 2          { $s_out = "$bmc_name is powered on but OS is not pinging" }
            case 3          { $s_out = "$bmc_name is powered on and the OS, $r_host is pinging" }
            else            { $s_out = "$bmc_name is in an unknown state" }
        }   
        print_to_status("System status: $s_out");
    }
        
    return $ret;                                                        # Return 
}
sub checkBootCount
{
    my $s = @_;
    
    print_to_status("Checking Boot Count"); 
    my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor get \"Boot Count\" | grep \"Boot Count\" 2>&1";      # Check the power status 
    #print_to_status("Issuing: $cmd");
    my $ret = qx/$cmd/;
    chomp($ret); 
    my @broken = split(/x/, $ret); 
    chop($broken[1]);
    my $sensID = $broken[1];
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user raw 0x04 0x2d 0x$sensID 2>&1";     # Check the power status 
    my $sens_cmd = $cmd; 
    #print_to_status("Issuing: $cmd");
    $ret = qx/$cmd/;
    
    my @sensSplit = split(' ', $ret);

    print_to_status("The Boot Count is $sensSplit[2]"); 
    
    # If we are starting with a boot count of 0x00, we will force it back to 0x02
    if($sensSplit[2] eq '00' )
    {
        print_to_status("Setting Boot Count back to 02");
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user raw 0x04 0x30 0x$sensID 0x01 0x00 0x02 0x00 0x00 2>&1";        # Check the power status 
        $ret = qx/$cmd/;
        
        sleep 5; 
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor get \"Boot Count\" | grep \"Boot Count\" 2>&1";
        $cmd = $sens_cmd; 
        $ret = qx/$cmd/;
        @sensSplit = split(' ', $ret);
        print_to_status("The Boot Count is $sensSplit[2]"); 
    }
    
    print_to_status("Checking BIOS and BMC Boot Sides");
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sensor list | grep -i 'Golden Side'";
    $ret = qx/$cmd/;
    print_to_status($cmd, 'clean');
    chomp($ret);
    $ret =~ s/^\s+//;
    print_to_status($ret, 'clean'); 
    
    print_to_status("");
}
sub filterSel
{
    my $sel_file = @_[0];
    my $ipl = @_[1]; 
    my $filter_cmd = "$tool_path/$bmc_name/x86/bin/bmc_sel_filter.py";        # Can be changed to whatever you want to use for filtering sels
    my $sys = $sys_type;     # Change to $sys_type later once we split whitelists between system types
    
    if( -e $filter_cmd)
    {
        if($sys =~ 'habanero') { $sys = 'habanero'; }
        
        if( -e $filter_cmd)
        {
            # Figure out which Whitelist to use based on system type and IPL done
            my $whitelist = '';             # Based on system type and IPL performed 
            if($ipl =~ /on/) { $whitelist = "$tool_path/$bmc_name/data/$sys.poweron.whitelist.dat"; }
            if($ipl =~ /Off/ || $ipl =~ /Soft/) { $whitelist = "$tool_path/$bmc_name/data/$sys.poweroff.whitelist.dat"; }
            if($ipl =~ /reboot/ || $ipl =~ /Cycle/) { $whitelist = "$tool_path/$bmc_name/data/$sys.poweron.whitelist.dat"; } # "$tool_path/$bmc_name/data/$sys.reboot.whitelist.dat"; }
            if($ipl =~ /AC/ || $ipl =~ /Reset/) { $whitelist = "$tool_path/$bmc_name/data/$sys.poweron.whitelist.dat"; }   # "$tool_path/$bmc_name/data/$sys.reset.whitelist.dat"; }
            
            # Figure out the output file name based on the .sels file passed in
            my @tmp = split(/\.sels/,$sel_file);
            my $filter_ofile = "$tmp[0].filter.sels";   
            
            chomp($sel_file);
            
            # Build the command based on filter_cmd, whitelist, sel file, and filter output file
            my $cmd = "$filter_cmd $whitelist $sel_file >> $filter_ofile";
            my $ocmd = "echo '$cmd' > $filter_ofile";
            my $ret = qx/$ocmd/;
            
            # Run the command 
            $ret = qx/$cmd/;
            
            # print out the filter file to the STDOUT and Status file
            print "$filter_ofile\n\r";
            print STATUS_FILE "$filter_ofile\n";
            
            # Push the filter_ofile to the current ffdc array.
            if($filter_ofile) { push(@cur_ffdc, $filter_ofile); } 
        }
    }
}
sub endTest
{
    # Kill the autoend button if it's still running
    #my $cmd = "ps -ef | grep autoend | grep $end_pid";
    #print_to_status("$cmd");
    #my $ret = qx/$cmd/;
    #print_to_status("We are checking for $end_pid");
    
    #if($ret) 
    #{
    #   print_to_status("Pid found, sending term");
    #   $cmd = "kill -s TERM $end_pid";
    #   $ret = qx/$cmd/;
    #   print_to_status("$ret");
    #}
    
    # Reset the xterm window to clean up from the sol console 
    #system('reset'); 
}
sub getIP 
{
    my $host = @_[0];
    my $cmd = "host $host";
    my $ret = qx/$cmd/; 
    my @tmp = split ' ', $ret; 
    return $tmp[3]; 
}
sub syncTime
{
    my $get_time = '';
    
    my $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sel time get 2>&1";     # Check the Time on the BMC
    my $ret = qx/$cmd/;
    chomp($ret);
    my $b_date = $ret; 
    
    $cmd = 'date -u +"%m/%d/%Y %T" 2>&1';
    $ret = qx/$cmd/;
    chomp($ret);
    my $w_date = substr($ret,0, -3); 
    
    if($b_date =~ $w_date) { print_to_status("Time of $w_date is close enough"); }
    else 
    { 
        print_to_status("Syncing date on the BMC to $ret"); 
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user sel time set \"$ret\" 2>&1";       # Set the time on the BMC
        print_to_status("Issuing: $cmd");
        $ret = qx/$cmd/;
    }
}
#################################################################################
# This function is used to read through the given list of current FFDC files    #
# and pick out key debug flags.                                                 #
# eg; from the SOL file, "error reported by" messages.                          #
# Check if certain applications were running                                    #
# Other FFDC debug triggers can be added to all of the possible FFDC files      #
#################################################################################
sub ffdcSummary()
{
    my @ffdc = ''; 
    my $key = '';
    print_to_status("******************** Beginning Summary of FFDC *****************");
    print_to_status("");

    # Loop through the FFDC files
    foreach (@cur_ffdc)
    {
        @ffdc = split(/\./, $_);
        $key = $ffdc[3];
        chomp($key); 
        #if($debug) { if($key) { print_to_status("$key $_", 'clean');  } }
        # SEL Summary
        #if($key eq 'sels') { print_to_status("SELs"); }
        # SEL Filter summary
        # Check if the error log script from fsp can be re-purposed 
        if($key eq 'filter') 
        { 
            print_to_status("SEL Filter", 'clean'); 
            my ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,$atime,$mtime,$ctime,$blksize,$blocks) = stat($_);
            if( -e $_ && $size > 300 ) 
            { 
                # Open the file and output the headers
                my $cmd = "cat $_ | grep -i \" | \" 2>&1"; 
                my $ret = qx/$cmd/;    
                if($ret) { print_to_status($ret, 'clean'); }
                else { print_to_status("No Filtered SELs found", 'clean'); }
            }
            else { print_to_status("Filter file empty / doesn't exist", 'clean'); }
        }
        # eSEL file
        if($ffdc[4] eq 'text')
        {
            print_to_status("eSELs", 'clean'); 
            my ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,$atime,$mtime,$ctime,$blksize,$blocks) = stat($_);
            if( -e $_ ) 
            { 
                my $SRC_tmp = '';
                my @SRC_out;
                my $tmp; 
                my @tmp_split;
                
                # Open the file and output the Reference Code
                my $cmd = "cat $_ | grep -i -A 6 \"| Reference Code \" 2>&1"; 
                my @ret = qx/$cmd/;    
                if(@ret) 
                {
                    foreach(@ret)
                    {
                        if($_ =~ 'Reference Code' ) 
                        {   
                            $tmp = $_; 
                            @tmp_split = split(' ', $tmp);
                            $SRC_tmp = "$tmp_split[4] - " ;  
                        }
                        if($_ =~ 'reasoncode' ) 
                        { 
                            $tmp = $_; 
                            @tmp_split = split(' ', $tmp);
                            $SRC_tmp .= $tmp_split[3];
                            print_to_status($SRC_tmp, 'clean');
                        }
                    }
                }
                else { print_to_status("No eSELs found", 'clean'); }
            }
            else { print_to_status("eSEL file empty / doesn't exist", 'clean'); }
        }
        # System Config summary
        #if($key eq 'syscfg') { print_to_status("System Config"); }
        # FRU summary
        #if($key eq 'fru') { print_to_status("FRU list"); }
        # System Info summary
        #if($key eq 'sysinfo') { print_to_status("System Info"); }
        # dmesg summary
        #if($key eq 'dmesg') { print_to_status("dmesg"); }
        # collectlogs summary
        #if($key eq 'collectlogs') { print_to_status("Collect Logs"); }
        # sortlogs summary
        #if($key eq 'sortlogs') { print_to_status("Sort Logs"); }
        # SOL summary
        # "Error reported by" + 6 lines after - grep -i -B 1 -A 5 "error reported by"
        if($key eq 'sol') 
        { 
            print_to_status("");
            print "SOL\n\r"; 
            print STATUS_FILE "SOL\n"; 
            my ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,$atime,$mtime,$ctime,$blksize,$blocks) = stat($_);
            if( -s $_ && $size > 45 ) 
            {
                my $cmd = "cat $_ | grep -i -B 1 -A 5 \"error reported by\" 2>&1"; 
                my $ret = qx/$cmd/;
                
                if($ret)
                {
                    print "$ret\n\r"; 
                    print STATUS_FILE "$ret\n"; 
                }
                else
                {
                    print "No Error reported data found\n\r"; 
                    print STATUS_FILE "No Error reported data found\n"; 
                }
            }
            else { print "SOL file is empty\n\r"; print STATUS_FILE "SOL file is empty\n"; }
        }
        # opal-prd summary
        if($key eq 'opal-prd') 
        { 
            print_to_status("");
            print "Opal-prd app\n\r"; 
            print STATUS_FILE "Opal-prd app\n"; 
            my ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,$atime,$mtime,$ctime,$blksize,$blocks) = stat($_);
            if($size > 10) { print "Opal-prd app is running\r\n"; print STATUS_FILE "Opal-prd app is running\n"; }
            else { print "Missing Opal-prd app.\r\n"; print STATUS_FILE "Missing Opal-prd app.\n"; }
            
        }
    }  # End of the foreach to loop through FFDC files 
    
    print_to_status("");
    checkBootCount();
    print_to_status("******************** End of Summary ****************************");
    print_to_status("");
}
####################################################################
# This function is used to log the results to an external script.  #
# DB, CSV, or other using an external script (Not provided)        #
####################################################################
sub logResults
{
    #fspipl_start_test      -- Used at the start of the test 
    #fspipl_log_testcase    -- Used to log the end of an IPL pass or fail
    #fspipl_test_complete   -- Used to end the test run
       
    my $cmd = '';
    my $func = @_[0];
    my $p_tot = 0;
    my $f_tot = 0;
    my $ret;
    my @tmp; 
    my $end_test_rc = 3210;                         # This value can change based on why the tests ended - # of IPLs finished, Stop on error, terminated by user?
    my $tmp_file;  
    my $tmp_ret; 
    my $fspipl_quiet='y'; 
    
    if($debug) { print_to_status("Setting quiet flag to \"n\"", 'debug'); $fspipl_quiet = 'n'; }
    
    if($func eq 'check_log_files')
    {
        # Check if fspipl_start_test exists
        $tmp_file = 'fspipl_start_test'; 
        $cmd = "which $tmp_file 2>/dev/null"; 
        $tmp_ret = qx/$cmd/;
        if(!$tmp_ret) { return 1; }

        # Check if fspipl_log_testcase exists
        $tmp_file = 'fspipl_log_testcase'; 
        $cmd = "which $tmp_file 2>/dev/null"; 
        $tmp_ret = qx/$cmd/;
        if(!$tmp_ret) { return 1; }
        
        # Check if fspipl_test_complete exists
        $tmp_file = 'fspipl_test_complete'; 
        $cmd = "which $tmp_file 2>/dev/null"; 
        $tmp_ret = qx/$cmd/;
        if(!$tmp_ret) { return 1; }
        
        return; 
    }
    # Build the command to call 
    elsif($func eq 'start_test_run')
    {
        #fspipl_start_test
        $cmd = "fspipl_start_test $bmc_name --host_name=$r_host --status_log_file=$log_file --test_really_running=1 --quiet=$fspipl_quiet 2>&1";
        my @ret = qx/$cmd/; 
        print_to_status("Issuing: $cmd");
        if($debug) 
        { 
            #print_to_status($ret, 'debug'); 
            print "@ret\r\n";
            print STATUS_FILE "@ret\n";
        }
        
        
        foreach(@ret)
        {
            if($_ =~ /start_test_time:/) # && !$start_test_time)
            {
                @tmp = split(':', $_);
                chomp($tmp[1]); 
                $tmp[1] =~ s/^\s+//;
                $start_test_time = $tmp[1]; 
                $ENV{'START_TEST_TIME'} = $start_test_time;
            }
        } 
    }
    elsif($func eq 'ipl_end')
    {
        #fspipl_log_testcase
        my $ipl_type_desc = @_[1]; 
        if($mnfg) { $ipl_type_desc .= " (mfg)"; }
        my $ipl_success = @_[2]; 
        my $start_ipl_time = @_[3]; 
        for(@results) { $p_tot += $_; }                 # Total up the passes
        for(@fails) { $f_tot += $_; }                   # Total up the fails
        
        $cmd = "fspipl_log_testcase --mch_ser_num=$mch_ser_num --mch_type_model=$mch_type_model --start_test_time=$start_test_time --start_ipl_time=$start_ipl_time --ipl_type_desc=\"$ipl_type_desc\" --ipl_success=$ipl_success --ipl_pass=$p_tot --ipl_fail=$f_tot --test_really_running=1 --quiet=$fspipl_quiet 2>&1"; 
        print_to_status("Issuing: $cmd");
        $ret = qx/$cmd/; 
        if($debug) { print_to_status($ret, 'debug'); }
    }
    elsif($func eq 'end_test_run')
    {
        #fspipl_test_complete
        $cmd = "fspipl_test_complete --mch_ser_num=$mch_ser_num --mch_type_mode=$mch_type_model --start_test_time=$start_test_time --end_test_rc=$end_test_rc --quiet=$fspipl_quiet  2>&1"; 
        print_to_status("Issuing: $cmd");
        $ret = qx/$cmd/; 
        if($debug) { print_to_status($ret, 'debug'); }
    }

}
################################################################################################
# This function will fill in the sys_type, bld_name, mch_ser_num, and mch_type_model variables # 
################################################################################################
sub getSystemInfo
{
    my $state = checkSysState(); 
    my $state_out = '';
    my $wrk_IP = getIP($wrk_name);
    my $host_IP = getIP($r_host);
    
    my $cmd = "bmc_sysinfo.pl -t $bmc_IP -p $bmc_pwrd -u $bmc_user --quiet";
    print_to_status("Gathering system info");
    print_to_status("Issuing: $cmd");
    my $ret = qx/$cmd/; 
    my @tmp = split(':', $ret);
    
    $sys_type = $tmp[1];
    $bld_name = $tmp[3];
    $mch_ser_num = $tmp[2];
    $mch_type_model = $tmp[4];  
    $ami_lvl = $tmp[5]; 

    ######################################### Add FRU system info #########################################
    my $id = 0;
    if($sys_type =~ 'habanero') { $id = 43; }
    elsif($sys_type =~ 'palmetto') { $id = 15; }
    #elsif($sys_type =~ 'firestone') { $id = 47; }   # This might eventually move to 59
    
    $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user fru print $id 2>&1";   
    my @tmp;
    ################### Pull when firestone fru id # figured out 
    if($sys_type =~ 'firestone') 
    {
        $cmd = "ipmitool -I lanplus -H $bmc_IP -P $bmc_pwrd -U $bmc_user raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 0x4f 0x4e 0x0 0x0 0x00 0x0 0x0 0x0 | xxd -r -p 2>&1";   
        my @ret = qx/$cmd/; 
        
        print_to_status($cmd);
        print "\r\n################################ Outputting System Info ################################\r\n";
        print STATUS_FILE "\r\n################################ Outputting System Info ################################\n";
        print "System Firmware: \r\n";
        print STATUS_FILE "System Firmware: \n";
        print "Build Name: $bld_name \r\n";
        print STATUS_FILE "Build Name: $bld_name \n";
        foreach(@ret)
        {
            chomp($_);
            $_ =~ s/^\s+//;
            print "$_\r\n";
            print STATUS_FILE "$_\r\n";
        }
    } 
    ################### Pull when firestone fru id # figured out 
    else 
    {
        my @ret = qx/$cmd/; 
        print_to_status($cmd);
        print "\r\n################################ Outputting System Info ################################\r\n";
        print STATUS_FILE "\r\n################################ Outputting System Info ################################\n";
        print "System Firmware: \r\n";
        print STATUS_FILE "System Firmware: \n";
        print "Build Name: $bld_name \r\n";
        print STATUS_FILE "Build Name: $bld_name \n";
        foreach(@ret)
        {
            chomp($_);
            @tmp = split(':', $_);
            $tmp[0] =~ s/^\s+//;
            $tmp[1] =~ s/^\s+//;
            print "$tmp[0] : $tmp[1]\r\n";
            print STATUS_FILE "$tmp[0] : $tmp[1]\r\n";
        }
    }
    #print_to_status("");
    ######################################### Add AMI code info #########################################
    print "AMI Level: \r\n";
    print STATUS_FILE "AMI Level: \r\n";
    $cmd = "jrcmd -l $bmc_user -p $bmc_pwrd -s $bmc_IP 'cat /proc/ractrends/Helper/FwInfo' 2>&1";   
    my @ret = qx/$cmd/;
    foreach(@ret)
    {
        chomp($_);
        print "$_\r\n";
        print STATUS_FILE "$_\r\n";
    }
    print_to_status("");
    
    print "Workstation Name: $wrk_name \r\n";
    print STATUS_FILE "Workstation Name: $wrk_name \n";
    print "Workstation IP: $wrk_IP \r\n";
    print STATUS_FILE "Workstation IP: $wrk_IP \n";
        
    print "Partition Name: $r_host\r\n";
    print STATUS_FILE "Partition Name: $r_host \n";
    print "Partition IP: $host_IP \r\n";
    print STATUS_FILE "Partition IP: $host_IP \n";
    
    print "BMC Name: $bmc_name\r\n";
    print STATUS_FILE "BMC Name: $bmc_name\n";  
    print "BMC IP: $bmc_IP \r\n";
    print STATUS_FILE "BMC IP: $bmc_IP \n";
    
    if(@cronus[0])
    {
        print "Cronus information:\n\r"; 
        print STATUS_FILE "Cronus information:\n"; 
        print "FSP: @cronus[0]\n\r";
        print STATUS_FILE "FSP: @cronus[0]\n";
        print "Target: @cronus[1]\n\r";
        print STATUS_FILE "Target: @cronus[1]\n";
    }
    
    print_to_status("");
        
    # Gather the state of the system
    switch ($state) {
        case 1          { $state_out = "$bmc_name is powered off" }
        case 2          { $state_out = "$bmc_name is powered on but OS is not pinging" }
        case 3          { $state_out = "$bmc_name is powered on and the OS, $r_host is pinging" }
        else            { $state_out = "$bmc_name is in an unknown state" }
    }   
    print "System status: $state_out\n\r";
    print STATUS_FILE "System status: $state_out\n";     
    print "\r\n################################### END System Info ####################################\r\n";
    print STATUS_FILE "\r\n################################### END System Info ####################################\n";
}
##############################################################################################
# This is the help output when no parms are given or -h or --help or -? are entered as parms #
##############################################################################################
sub parmHelp
{
    print "Usage:  op_boot_test.pl [-f <setup_file>] [--option [on/off/soft/reboot/cycle/reset/warm/ac/ffdc]] [-p <path to setup file>] [-r #] [extra options] \n";
    print "\n";
    
    ################ Brief paragraph describing the basic function of the script ################
    print "The op_boot_test.pl script will run an opening default stack of IPLs followed by a random IPL selection from the given IPLS list. \n";
    print "When an IPL finishes, FFDC will be gathered using the bmc_ffdc script, if it's found in the PATH. The script will also try to \n";
    print "save off the SOL console output for each IPL. Each IPL has an ending condition of either power off, power on, or OS Login. If \n"; 
    print "the contition is not met within the given timeout, we will consider it an error and dump FFDC. \n";
    print "\n";
    ################ Basic script options ################
    print "Basic Options: \n";
    print "--option, o <on/off/soft/reboot/cycle/reset/warm/ac/ffdc> This will overide the IPLing options and do just the 1 ipl / ffdc gathering \n";
    print "--set_file, f <setup_file>                      This file can be used in place of the Extra Options \n";
    print "--base_path, p <path_to_setup_file>             This parm must be passed in if we are using a setup file \n";
    print "--repeat, r <#>                                 This parm is used to tell how many IPLs we want to run. Default is 3. \n";
    print "\n";
    print "The setup file can also be used to contain the following options\n";
    print "\n";
    print "Extra Options: (Parms with a * are required if no -f <setup_file> is used) \n";
    ################ BMC Options ################
    print "--bmc_name <bmc_name>            *This is the BMC name for the given system \n";
    print "--bmc_user <bmc_userid>          *This is the BMC userid for the given system \n";
    print "--bmc_password <bmc_password>    *This is the BMC password for the given system \n";
    ################ Host Options ################
    print "--os_host <os_hostname>          This is the Operating System hostname \n";
    print "--os_user <os_userid>            This is the userid for the Operating System \n";
    print "--os_password <os_password>      This is the Operating System's password \n";
    ################ FFDC / Status ################
    print "--ffdc_path <FFDC_Path>          This is the path that we want to direct the FFDC to. Default is ./ \n";
    print "--status_path <status_path>      This is the path that we want to direct the status file to. Default is ./ \n";
    print "--status_file <path/file>        This is the path/file to use instead of the default generated status file. \n";
    print "--tool_path <path_to_tools>      This is the patch to extra tools for the ffdc. Includes SEL whitelists and eSEL translation. \n";
    ################ Misc ################
    print "--stop_on_error <y/n>            This is the stop on toggle. Default is n. This can be passed in as a blank. \n";
    print "--wait_state_timeout <#>         This is the number of 15 second intervals for an IPL to finish. Value * 0.25 = minutes. Default is 360 \n";
    print "--ipls <List_of_IPLs>            *This is the list of the IPLs we want to do. eg; -IPLS \"BMC Host reboot;BMC Power Off\" \n";
    print "--ipl_stack <List_of_IPLs>       This is the list of IPLs we want to run 1st during the test run. This can be passed in as a blank. \n";
    print "--mnfg <y/n>                     This is the flag to signal that the user has set the mnfg Override flags. It will change the display of the IPLs to add (mfg) to the end.\n";
    print "--DB <db2_name>                  This is the DB name. \n";
    print "--ePDU <ePDU_name>               This is the ePDU we want to use for AC cycle IPLs. Can be passed in as a blank. \n";
    print "--FSP <FSP_IP>                   This is the FSP being used for cronus debug. Only used for information purposes. Can be passed in as a blank. \n";
    print "--cronus <cronus_target>         This is the crouns target name. Only used for information purposes. Can be passed in as a blank. \n";
    print "--debug <y/n>                    This is the flag to output extra debug info in the status file. Default is n. This can be passed in as a blank. \n"; 
    
    print "\n";
    print "Example usage: \n";
    print "op_boot_test.pl -p /tmp -f paul33.bmc -r 100  \n";
    print "\n";
    print "op_boot_test.pl --BMC_name paul46 --BMC_user <userid> --BMC_password <password> --OS_host paul40 --OS_user <userid> --OS_password <password> --IPLS \"BMC Host reboot,BMC Power Off,BMC Power Reset,BMC Power Cycle,BMC AC Cycle,BMC MC Reset warm,BMC Power on\" --wait_state_timeout 120 \n";   
}