#!/usr/bin/perl
# IBM_PROLOG_BEGIN_TAG  
# This is an automatically generated prolog.    
#   
# $Source: op-auto-test/boot/bmc_sysinfo.pl $   
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
use Switch; 
use Getopt::Long qw(GetOptions);

my $numArgs = $#ARGV;                  # Get the number of args passed in
our $target = '';
our $userid;
our $pwrd;
my $host_name = '';
our $sys_user = '';
our $sys_pwrd = ''; 
my $cmd = ''; 
my $quiet; 
my $help;   
my $mtm = '9999-999';                  # Make type model

GetOptions(
    'target=s' => \$target, 
    'userid=s' => \$userid,
    'password=s' => \$pwrd,
    'sys_user=s' => \$sys_user,
    'sys_password=s' => \$sys_pwrd, 
    'help|?' => \$help, 
    'quiet' => \$quiet,
) or die "Usage bmc_sysinfo.pl -t <BMC Name / IP> -u <userid> -p <password> [--quiet] [-h]\n";

if($help || $numArgs < 0) { print "$#ARGV\n"; parmHelp(); exit(0); }                      
############################################################
# Check that we got all the variables filled in correctly  #
############################################################
if(!$target) { print "**ERROR** Missing BMC target name / IP\n"; parmHelp(); exit(1); } 
if(!$userid) { print "**ERROR** Missing BMC user id\n"; parmHelp(); exit(1); }
if(!$pwrd)   { print "**ERROR** Missing BMC password\n"; parmHelp(); exit(1); }

###############################################################
# Add code to convert the Host name to an IP                  #
###############################################################
if($target =~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
{ 
    if(!$quiet) { print_w_stamps("We have an IP, so getting the hostname."); } 
    $cmd = "host $target";
    my $ret = qx/$cmd/; 
    if($ret =~ 'not found:') { die "**ERROR** Hostname not found! \n"; }
    my @tmp = split('pointer', $ret);
    $tmp[1] =~ s/^\s+//;
    $host_name = $tmp[1];
}
else  
{ 
    if(!$quiet) { print_w_stamps("We got a host name. Converting to IP."); }
    $host_name = $target; 
    $cmd = "host $target";
    my $ret = qx/$cmd/; 
    # Check if we found the hose
    if($ret =~ 'not found:') { die "**ERROR** Hostname not found! \n"; }
    my @tmp = split ' ', $ret; 
    $target = $tmp[3]; 
}

#########################################################################################
#                                   Main body                                           #
#########################################################################################
#######################################
# Make sure the BMC target is pinging #
#######################################
$cmd = "ping -c 1 -w 1 $target 2>&1";                       
my $result = qx/$cmd/;
if($result =~ /100%/) { die "**ERROR** Unable to ping target! \n";  }                           # We failed to ping

#####################################################
# Make sure the host is sshable before trying jrcmd #
#####################################################
# Try a jrcmd to get uptime and catch the result. If it returns known_hosts issue, clear the entry
$cmd = "jrcmd -l $userid -p $pwrd -s $target 'uptime' 2>1&";
if(!$quiet) { print_w_stamps("Issuing: $cmd "); }
$result = qx/$cmd/;
# If we get back the uptime, then we should be good to go with ssh.
if($result =~ /load average/)
{ 
    if(!$quiet) { print_w_stamps("ssh works!"); }
}
else    # Else we should check what we got back
{
    # If known_hosts is in the return, then it's an issue with the known_hosts file. Clear the entry for the hostname and ip of the BMC.
    if($result =~ /known_hosts/) 
    {
        print_w_stamps("The known_hosts file doesn't match the BMC. Cleaning up file"); 
        fix_known_hosts(); 
    } 
    elsif($result =~ /Connection refused/)          # Else, if we got connection refused, exit because the user has to fix this. 
    {
        print_w_stamps("**ERROR** Unable to ssh to BMC $target. Connection refused!"); exit(1); 
    } 
    else                                            # Else we don't know what's wrong with ssh, so call an error and exit
    {
        print_w_stamps("**ERROR** Unknown error with ssh to BMC $target."); exit(1);
    }
}
###############################
# Get the whole block of data #
###############################
# this will return into an array that we can parse through. 
$cmd = "jrcmd -l $userid -p $pwrd -s $target 'ifconfig | grep HWaddr | sed -e \"s/.*HWaddr //g\" -e \"s/://g\" && cat /conf/driver' 2>/dev/null ";   #&& gpiotool --get-data 48 && gpiotool --get-data 49 && gpiotool --get-data 50 ' 
if(!$quiet) { print_w_stamps("Issuing: $cmd "); }
my @ret = qx/$cmd/;

if(!$quiet) { print "@ret \n"; }
# Process the Array

###################################
# Get the MAC from the BMC system #
###################################
my $SN = @ret[0]; 
$SN =~ s/\s+$//;
if(!$SN) { $SN = 'unknown'; } 
if(!$quiet) { print_w_stamps("HW Address = $SN"); }
if($SN =~ 'unknown') { print_w_stamps("**ERROR** Unable to get a valid SN"); exit(1); }

###########################################
# Get the system type from the BMC system #
###########################################
my $sys_type;
#my $tmp = '';
if(!$quiet) { print_w_stamps("Processing What system type we have"); }

$sys_type = "BMC:" . find_system_type();

################################################### 
# Find the driver if there is one in /conf/driver #
###################################################
my $drv; 
if($ret[1]) { $drv = $ret[1]; }
chomp($drv);
if($drv =~ /cat:/ || !$drv ) { $drv = 'unknown.unknown.unknown'; }          # If we didn't find the file, return unknown 

###################################################### 
# Find the BMC Code level using fru info or raw read #
######################################################
my $ami_lvl = getBMCCodeLevel(); 

if(!$quiet) { print_w_stamps("Returning: $sys_type:$SN:$drv:$mtm:$ami_lvl "); }
print "$sys_type:$SN:$drv:$mtm:$ami_lvl";

#########################################################################################
#                                   Functions                                           #
#########################################################################################
sub print_w_stamps
{
    my $msg = @_[0];
    my $replace = "********";
    
    if($msg)
    {
        # Generate a time stamp for each line 
        my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
        my $nice_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year-100,$mon+1,$mday,$hour,$min,$sec);
        my $tz = strftime("%Z", localtime());
        
        ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = gmtime(time);
        my $nice_gm_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year-100,$mon+1,$mday,$hour,$min,$sec);
        
        my $tout = "#($tz) $nice_timestamp - (UTC) $nice_gm_timestamp - ";
        
        # print the output 
        print "$tout $msg\n";  
    }
    else
    {
        print "\n";
    }
    
}
sub find_system_type
{
    my $cmd = "jrcmd -l $sys_user -p $sys_pwrd -s $target 'devmem 0x1e780020' 2>1& ";
    if(!$quiet) { print_w_stamps($cmd); }
    my $ret = qx/$cmd/;
    my $c = substr($ret, 5,1);
    
    # Case switch based on devmem value 
    switch($c)
    {
        case [0,8]  { $ret = "palmetto"; }
        case "A"    { $ret = "habanero1"; }
        case [2]    { $ret = "habanero1"; }
        case "B"    { $ret = "habanero2"; }
        case [3]    { $ret = "habanero2"; }
        case [1,9]  { $ret = "firestone"; }
        case "F"    { $ret = "garrison"; }
        case [7]    { $ret = "garrison"; }
        else        { $ret = "Unknown"; }
    }
    return $ret; 
}
#################################################################
# This function will remove the entry for the hostname and ip   #
# from the known_hosts list. After AMI update, the key file on  #
# the BMC will be cleared and will cause issues with ssh        #
#################################################################
sub fix_known_hosts
{
    my $target_name;
    my $target_ip; 
    my $cmd; 
    my $ret; 
    
    ###################
    if($target =~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
    { 
        $target_ip = $target;
        $cmd = "host $target";
        $ret = qx/$cmd/; 
        my @tmp1 = split('pointer', $ret);
        $tmp1[1] =~ s/^\s+//;
        chomp($tmp1[1]);
        my @tmp_split = split(/\./, $tmp1[1]);
        $target_name = $tmp_split[0];
    }
    else  
    { 
        $target_ip = getIP($target);
        my @tmp = split(/\./, $target);
        $target_name = @tmp[0];
    }
    
    # Removes just the one key from the correct key file
    $cmd = "ssh-keygen -R $target_name";
    $ret = qx/$cmd/; 
    print_w_stamps($ret);
    
    $cmd = "ssh-keygen -R $target_ip";
    $ret = qx/$cmd/; 
    print_w_stamps($ret);
}
sub getBMCCodeLevel
{
    my $cmd = "jrcmd -l $userid -p $pwrd -s $target 'cat /proc/ractrends/Helper/FwInfo' 2>&1";
    my @ret = qx/$cmd/; 
    my @split;
    
    foreach(@ret)
    {
        if($_ =~ /FW_DESC/) 
        {
            # Split out based on "=" 
            @split = split('=', $_); 
            chomp($split[1]);
            $split[1] =~ s/ +/_/g;          
        }
    }
    return $split[1];    
}
sub parmHelp
{
    print "Usage: bmc_sysinfo.pl -t <BMC Name / IP> [-u <userid> -p <password>] --sys_user <user> --sys_password <password> [--quiet] [-h]\n";
    print "\n";
    
    print "The script bmc_sysinfo.pl will try and read from the bmc and return basic system info back to the caller. The data returned \n";
    print "will be the system type (habanero, palmetto, etc...), system MAC address, and the code level running if /conf/driver is filled in. ";
    
    print "Basic Options: \n";
    print "-t , --target <BMC name / IP>           This is the target BMC we want to get the system info from \n";
    print "-u , --user <userid>                    This is the userid to use when connecting to the target \n";
    print "-p , --password                         This is the password that goes with the given userid \n";
    print "--sys_user <userid>                     This is the BMC userid that has more permissions. \n";
    print "--sys_password <password>               This is the password that goes with the sys_user parm. \n";
    
    print "-q , --quiet                            This is a togle to remove the default verbose output \n";
    print "-h , --help                             This help text \n";
    print "\n";
        
    print "\n";
    print "Example usage: \n";
    print "bmc_sysinfo.pl -t paul33 -u <userid> -p <password> --sys_user <user> --sys_password <password> --quiet \n";
    print "\n"; 
}