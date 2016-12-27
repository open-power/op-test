#!/usr/bin/perl 	
# IBM_PROLOG_BEGIN_TAG 	
# This is an automatically generated prolog. 	
# 	
# $Source: op-auto-test/flash/AutoHPM.pl $ 	
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

######################################################################################################

use strict;
use POSIX;
use List::Util 'first'; 
use Switch; 
use Getopt::Long qw(GetOptions);

my $numArgs = $#ARGV + 1;					# Get the number of args passed in
our $target = '';
our $userid = '';
our $pwrd = '';
our $sys_user = '';
our $sys_pwrd = ''; 
our $tball;
our $hpm_status_file = '';
my $platform = ''; 
my $host_name = '';
my $cmd = ''; 
my $quiet;
my $help;
my $image = ''; 							
my $hpm_image = ''; 
our $build = ''; 						
my $LCB_IP = '';
my $speed = 30000; 
our $pass = 0; 								# There is no pass for the system
my $AMI;
my $noTrace; 
my $force;
my $fix_known_hosts = 'n'; 
our $debug; 

#########################################################################################
# 									Parm handling  										#
#########################################################################################

my $c = $#ARGV; 

GetOptions(
    'target|t=s' => \$target, 
    'build|b=s' => \$build,
    'platform|p=s' => \$platform,
    'user=s' => \$userid,
    'password=s' => \$pwrd,
    'sys_user=s' => \$sys_user,
    'sys_password=s' => \$sys_pwrd, 
    'speed|z=s' => \$speed,
    'image=s' => \$hpm_image,
    'hpm_status_file=s' => \$hpm_status_file,
    'tarball' => \$tball, 
    'AMI' => \$AMI, 
    'noTrace' => \$noTrace, 
    'force' => \$force,
    'fix_known_hosts:s' => \($fix_known_hosts = 'n'), 
    'debug:s' => \($debug = 'n'),
    'help|?' => \$help, 
    'quiet' => \$quiet,
) or die parmHelp();


if ($c < 0 || $help) 
{
    parmHelp();
    exit(0);
}
# Check the passed parms for $debug
if($debug eq '0') { $debug = 'n';} 
if($debug eq '1' || !$debug) { $debug = 'y'; }
if($debug ne 'n' && $debug ne 'y') { print_to_status("**ERROR** Invalid debug setting!"); exit(1); }
if($debug eq 'n') { $debug = '';} 


# Check the passed parms for $fix_known_hosts
if($fix_known_hosts eq '0') { $fix_known_hosts = 'n';} 
if($fix_known_hosts eq '1' || !$fix_known_hosts) { $fix_known_hosts = 'y'; }
if($fix_known_hosts ne 'n' && $fix_known_hosts ne 'y') { print_w_stamps("**ERROR** Invalid fix_known_hosts setting!"); exit(1); }
if($fix_known_hosts eq 'n') { $fix_known_hosts = '';} 

###############################################################
# Add code to check that we have the needed fields filled in  #
###############################################################
if(!$target)    { print "**ERROR** Missing BMC target name / IP\n"; exit(1); } 
if(!$userid)    { print "**ERROR** Missing BMC user id\n"; exit(1); }
if(!$pwrd)      { print "**ERROR** Missing BMC password\n"; exit(1); }
if(!$sys_user)  { print "**ERROR** Missing BMC sys userid\n"; exit(1); }
if(!$sys_pwrd)  { print "**ERROR** Missing BMC sys password\n"; exit(1); }
if(!$build)     { print "**ERROR** Missing image to load\n"; exit(1); }
if(!$platform)  { print "**ERROR** Missing platform\n"; exit(1); }
if(!$speed)     { print "**ERROR** Missing flash speed\n"; exit(1); }
###############################################################
# Add code to convert the Host name to an IP                  #
###############################################################
if($target =~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
{ 
	if(!$quiet) { print_w_stamps("We have an IP, so getting the hostname."); } 
	$cmd = "host $target";
	my $ret = qx/$cmd/; 
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
	my @tmp = split ' ', $ret; 
	$target = $tmp[3]; 
}
###############################################################
# Add code to validate the platform name given                #
###############################################################
print "$platform \n";
if($platform eq 'habanero1' || $platform eq 'habanero2' || $platform eq 'palmetto' || $platform eq 'firestone')
{
	if(!$quiet) { print_w_stamps("Platform name $platform is valid."); }
}
else
{
	print "**ERROR** Invalid platform name $platform. Valid values are habanero1, habanero2, firestone, or palmetto\n"; 
	exit(1);

}
#######################################################################
# Add code to check if the hpm update target is of the given platform #
#######################################################################
my @tmp_gpio = '';
my $sys_type = find_system_type();
my $tmp = '';
if(!$quiet) { print_w_stamps("Finding System Type"); }

if($platform eq $sys_type)
{
	if(!$quiet) { print_w_stamps("Requsted platform and target system are equal"); }
}
else 
{
	print "**ERROR** The requested platform doesn't match the system name given. It's a $sys_type\n"; 
	exit(1);
}

###############################################################
# Figure out the pass if we are using a habanero system       #
###############################################################
if($platform eq 'habanero1' || $platform eq 'habanero2') 
{
	my $c = chop($platform);
	if($c eq '1') { $pass = 1; }
}
###############################################################
# Add code to see if the image file exists                    #
###############################################################
# Find the .hpm to load 
if(!$hpm_image)
{
	print_w_stamps("Finding the image");
    $image = findHPM($platform, $noTrace); 
}
else { $image = $hpm_image; }

if($debug) { print_w_stamps("Image: $image");  }

###############################################################
# Add code to figure out the LCB's IP                         #
###############################################################
if(!$quiet) { print_w_stamps("Finding the LCB IP to use for mounting"); }
$cmd = 'hostname';
my $ret = qx/$cmd/; 
$cmd = "host $ret";
$ret = qx/$cmd/; 
my @tmp = split ' ', $ret; 
$LCB_IP = $tmp[3]; 

#########################################################################################
# 									Echo back the parms									#
#########################################################################################
if(!$quiet)
{
    print "Echoing back the parms\n";
    print "Target = $target \n";
    print "Userid = $userid \n";
    print "Password = $pwrd \n"; 
    print "LCB IP to mount to = $LCB_IP\n";
    print "Image to load = $image \n";
    print "Driver name given = $build \n";
}
#########################################################################################
# 									Main body   										#
#########################################################################################
# 1. Issue a power off to the BMC
# 2. Run the hpm update command
# 3. reboot the BPC
# 4. echo the driver into the /extlog/driver file 

if(!$image) { print_w_stamps("**ERROR** No image found!"); exit(1); }

#if($debug) { exit(0); } 

# Issue a power off to the BMC
$cmd = "ipmitool -H $target -I lanplus -P $pwrd -U $userid power off 2>&1";
print_w_stamps("Issuing: $cmd");
$ret = qx/$cmd/;
print_w_stamps("Sleeping for 15 seconds while we wait for the system to fully power off");
sleep(15);

if($AMI)
{
	print_w_stamps("HPM Auto update AMI");
	
	print_w_stamps("Setting preserve settings on BMC. (network and IPMI)");
	$cmd = "ipmitool -H $target -I lanplus -U $userid -P $pwrd raw 0x32 0xBA 0x18 0x00 2>/dev/null ";
	print_w_stamps("$cmd"); 
	$ret = qx/$cmd/;
	
    if($force) 
    {
        $cmd = "echo y | ipmitool -H $target -I lanplus -U $userid -P $pwrd hpm upgrade $image component 1 -z $speed force 2>&1";
    }
    else 
    {
        $cmd = "echo y | ipmitool -H $target -I lanplus -U $userid -P $pwrd hpm upgrade $image component 1 -z $speed 2>&1";
    }
	print_w_stamps("$cmd"); 
	$ret = qx/$cmd/; 
	sleep 15;
    
    if($debug) { print_w_stamps("Return: $ret"); }
    
	# Firmware upgrade procedure successful instead of 100%
	if($ret =~ /Firmware upgrade procedure successful/) { print_w_stamps("AMI upgrade procedure successful"); } 
	else { print_w_stamps("**ERROR** HPM upgrade failed"); exit(1); }

	print_w_stamps("Sleeping 2 minutes for default mc reset cold to finish.");
	sleep 120;
    
    # Need to add code to clear up the known_hosts issues with ssh to BMC
    if($fix_known_hosts) { fix_known_hosts(); }
}

print_w_stamps("HPM Auto update PNOR"); 
my $cmd = "echo y | ipmitool -H $target -I lanplus -U $userid -P $pwrd hpm upgrade $image component 2 -z $speed 2>&1";
print_w_stamps("$cmd"); 
my $ret = qx/$cmd/; 

sleep 15;
# Firmware upgrade procedure successful instead of 100%
if($ret =~ /Firmware upgrade procedure successful/) { print_w_stamps("Firmware upgrade procedure successful"); } 
else { print_w_stamps("**ERROR** HPM upgrade failed"); exit(1); }

print_w_stamps("Sending Cold Reset to BMC.");
$cmd = "ipmitool -H $target -I lanplus -U $userid -P $pwrd mc reset cold 2>/dev/null ";
$ret = qx/$cmd/;

print_w_stamps("Sleeping 90 seconds for mc reset cold to finish.");
sleep 90;

print_w_stamps("Updating the driver file");
$cmd = "jrcmd -l $sys_user -p $sys_pwrd -s $target 'echo $build > /conf/driver' 2>/dev/null ";
$ret = qx/$cmd/;
if($debug) { print_w_stamps("$ret"); }

if($tball)
{
	print_w_stamps("Updating the tarball"); 
	my @tmp = split(/\./, $build); 
	my $drv_rel = $tmp[0];
	my $tar_path = "/afs/austin/projects/esw/op$drv_rel/Builds/$build/tarballs/";
	tarballUpdate($tar_path, $host_name);
}
print_w_stamps("Normal Completion.");

#########################################################################################
# 									Functions   										#
#########################################################################################
sub print_w_stamps
{
	my $msg = @_[0];
	my $replace = "********";
	
	############################################
	# Break out the path for the status file
	# make sure that path exists before using the status file
	# If the status file can't be created or doesn't exist, warm but continue with the update
	############################################
	
	
	if($msg)
	{
		# Generate a time stamp for each line 
		my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
		my $nice_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year-100,$mon+1,$mday,$hour,$min,$sec);
		my $tz = strftime("%Z", localtime());
		
		($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = gmtime(time);
		my $nice_gm_timestamp = sprintf ( "%04d/%02d/%02d %02d:%02d:%02d",$year-100,$mon+1,$mday,$hour,$min,$sec);
		
		my $tout = "#($tz) $nice_timestamp - (UTC) $nice_gm_timestamp - ";
			
		# Modify the msg to hide the passwords	
		$msg =~ s/$pwrd/$replace/g;	
		#$msg =~ s/$r_pwrd/$replace/g;	
		
		# print the output 
		print "$tout $msg\n";
	}
	else
	{
		print "\n";
	}
	
}
sub tarballUpdate
{
	my $tar = "@_[0]"; 
	$tar = "$tar/mfg.OP.tools.tar.gz";
	my $sys = @_[1];
	my $tar_base = "/fspmount/$sys";
	my $tar_dir = "/fspmount/$sys";
	
	# Check if the file exists
	if( -f $tar)
	{ 
		print_w_stamps("Tar file exists. Expanding....");
		if( -d $tar_dir)
		{
			print_w_stamps("Dir $tar_dir exists, clear then expand");
			my $cmd = "rm -rf $tar_dir";
			print_w_stamps("$cmd");
			my $ret = qx/$cmd/; 
            
            $cmd = "mkdir -p $tar_base";
			print_w_stamps("$cmd");
			$ret = qx/$cmd/; 
            
			$cmd = "tar -C $tar_base -zxvf $tar";
			print_w_stamps("$cmd");
			$ret = qx/$cmd/; 
		}
		else
		{
			print_w_stamps("Dir $tar_dir doesn't exist, create and expand");
			if( -d $tar_base)
			{
				my $cmd = "tar -C $tar_base -zxvf $tar";
				print_w_stamps("$cmd");
				my $ret = qx/$cmd/; 
			}
			else
			{
				# Make the /fspmount/<system name dir>
				my $cmd = "mkdir -p $tar_base";
				print_w_stamps("$cmd");
				my $ret = qx/$cmd/;
				
				$cmd = "tar -C $tar_base -zxvf $tar";
				print_w_stamps("$cmd");
				$ret = qx/$cmd/; 
			}
		}
	}
	else
	{
		print_w_stamps("Tar file, $tar, doesn't exist, unable to extract");
	}
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
sub getIP 
{
    my $host = @_[0];
    my $cmd = "host $host";
    my $ret = qx/$cmd/; 
    my @tmp = split ' ', $ret; 
    return $tmp[3]; 
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
sub find_system_type
{
    my $cmd = "jrcmd -l $sys_user -p $sys_pwrd -s $target 'devmem 0x1e780020' 2>1& ";
    if($debug) { print_w_stamps($cmd); }
    my $ret = qx/$cmd/;
    if($debug) { print_w_stamps($ret); }
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
sub findHPM 
{
    my $plat = @_[0];
    my $noTrace = @_[1]; 
    my $ret = 'Bogus'; 
    my $cmd;
    my $image; 
    
    print_w_stamps("Plat: $plat");
    print_w_stamps("Traces: $noTrace");
    #/afs/austin/projects/esw/op810/Builds/810.1515.20150406n/op-build/output/images/palmetto_810.1535.20150821t_traces.hpm
    #/afs/austin/projects/esw/op810/Builds/810.1535.20150821t/op-build/output/images/lab/ 
	my @tmp = split(/\./, $build); 
	my $drv_rel = $tmp[0];
	#my $drv_path = "/afs/austin/projects/esw/op$drv_rel/Builds/$build/op-build/output/images";
	my $drv_path = "/afs/austin/projects/esw/op$drv_rel/Builds/$build/op-build/output/images/lab";
    my $img_file;
    
	# If pass 1 habanero, look for _pass1.hpm 
	#if($pass) { $img_file = "$platform\_$build\_pass1.hpm"; }
	if($pass) { $img_file = "8348\_$build\_traces\_pass1.hpm"; }
	# else it's not a pass 1 habanero, look for .hpm
	elsif($platform =~ 'firestone')
	{
        if($noTrace)        # This needs to modify the $drv_path from /lab to /ship. Should do this check 1st?
        {
            my $img_file = "8335\_$build\_noTraces.hpm";
            if($debug) { print_w_stamps("HPM file: $img_file"); }
            if(-e "$drv_path/$img_file") { $img_file = "8335\_$build\_noTraces.hpm"; }
            else { $img_file = "8335\_$build\_traces.hpm"; }
        }
        #else { $img_file = "$platform\_$build\.hpm"; }
        else { $img_file = "8335\_$build\_traces.hpm"; }
	}
    #elsif($platform =~ 'habanero' && $pass == 0) { $img_file = "$platform\_$build\.hpm"; }
    elsif($platform =~ 'habanero' && $pass == 0) { $img_file = "8348\_$build\_traces.hpm"; }
	#else { $img_file = "$platform\_$build\.hpm"; }
	else { $img_file = "$platform\_$build\_traces.hpm"; }
    
    $cmd = "ls $drv_path/$img_file 2>1&"; 
    print_w_stamps("image file: $img_file");
    print_w_stamps("ls cmd: $cmd");
    
	$ret = qx/$cmd/;
    print_w_stamps("ls Output: $ret");
    if(!$ret) { print_w_stamps("**ERROR** hpm image file not found."); exit(1); }
	$image = $ret; 
	chomp($image);
    print_w_stamps("Returning: $image");
    return $image; 
}
sub parmHelp
{
    print "Usage:  AutoHPM.pl -t <BMC name/IP> -b <build> -p <platform> [options][-h/?]\n";
    print "\n";
    
    print "The script AutoHPM.pl will try to load the given hpm image on the target BMC. If no specific image is given, the script will try and  \n";
    print "find the image on it's own. ";
    
    print "Basic Options: \n";
    print "-t , --target <BMC name / IP>           This is the target BMC we want to get the system info from \n";
    print "-b , --build <build_name>               This is the build name that we will use to find the image and write to /conf/driver \n";
    print "-p , --platform <platform_name>         This is the platform name for the given BMC system.  \n";
    print "-u , --user <userid>                    This is the userid to use when connecting to the target \n";
    print "--password <password>                   This is the password that goes with the given userid \n";
    print "--sys_user <userid>                     This is the BMC userid that has more permissions. \n";
    print "--sys_password <password>                This is the password that goes with the sys_user parm. \n";
    print "-q , --quiet                            This is a togle to remove the default verbose output \n";
    print "-h , --help                             This help text \n";
    print "\n";
    
    print "Extra Options:  \n";    
    print "-z , --speed <######>                   This is the speed option. Default is 30000. If issues seen with default, try 10000 \n";
    print "-i , --image <path/image_filename>      This is the full path / image to load. \n";
    print "--hpm_status_file <path/filename>       This is the full path / status file to use for logging the output from this command. \n";
    print "--tarball                               This is the toggle to tell the update to unpackage the tarball that goes with the build. \n";
    print "--AMI                                   This is the toggle to tell the update to load the AMI portion of the hpm image as well as pnor. \n";
    print "--noTrace                               This is the toggle to tell the update to try and find the _notrace.hpm version of the image files. \n";
    print "--force                                 This is the toggle to add \"force\" to the end of the hpm update command. Only affects AMI update. \n";
    print "--fix_known_hosts                       This is the toggle to \"fix\" the ssh known_hosts issue after updating AMI code. \n";
        
    print "\n";
    print "Example usage: \n";
    print "AutoHPM.pl -t paul33 -b 810.1525.20150624n -p palmetto -user <userid> --password <password> \n";
    print "\n"; 
    print "AutoHPM.pl -t paul33 -b 810.1525.20150624n -p palmetto -user <userid> --password <password> --tarball --AMI --force -z 10000 \n";
    print "\n"; 
}