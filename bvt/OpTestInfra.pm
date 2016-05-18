#!/usr/bin/perl
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/bvt/OpTestInfra.pm $
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
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

# OpTestInfra: Common perl functions for OpenPower IT/BVT test infrastructure
#
# Author: Alan Hlava

#use strict;
use Fcntl qw(:DEFAULT :flock LOCK_EX LOCK_UN);

package OpTestInfra;

my $verbose = 0;
my $verbose_file = "";
my $vp_indent = "";
my $ppid = 0;
my $failsumm_log = "";

my @log_hist;
my $log_hist_lim = 15;
my $log_hist_count = 0;

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(set_verbose is_verbose_enabled vprint set_failsumm_log clear_log_hist add_log_hist add_log_hist_file write_log_hist trim findRelFile);
@EXPORT_OK = qw($verbose $verbose_file);

# set_verbose
#    arg1 : 0=no verbose tracing, 1=verbose tracing to STDERRR
#    arg2 : [optional] instead of STDERR append verbose output to this file
#           (overrides arg1)

sub set_verbose
{
    my ($vval, $vfile) = @_;
    $verbose = $vval;
    $verbose_file = $vfile;
    $ppid = getppid();
}

sub is_verbose_enabled
{
    return( $verbose || ($verbose_file ne "") );
}

sub vprint
{
    my ($str) = @_;

    if ($verbose_file ne "")
    {
        if ($str =~ /^\</)
        {
            $vp_indent = substr($vp_indent, 3);
        }
        if (open(VF, ">>$verbose_file"))
        {
            flock(VF, Fcntl::LOCK_EX) || die "ERROR: could not lock $verbose_file : $!";
            printf VF "%6d|%6d|${vp_indent}${str}", $ppid, $$;
            flock(VF, Fcntl::LOCK_UN) || die "ERROR: could not unlock $verbose_file : $!";
            close(VF);
        }
        if ($str =~ /^\>/)
        {
            $vp_indent .= "   ";
        }
    }
    elsif ($verbose)
    {
        if ($str =~ /^\</)
        {
            $vp_indent = substr($vp_indent, 3);
        }
        printf STDERR "%6d|%6d|${vp_indent}${str}", $ppid, $$;
        if ($str =~ /^\>/)
        {
            $vp_indent .= "   ";
        }
    }

}

# set_failsumm_log
#    arg1 : Fully qualiified name of fail summary file
#    arg2 : [optional] Size of log history to print in the fail summary file
sub set_failsumm_log
{
    my ($fn, $lim) = @_;
    $failsumm_log = $fn;
    vprint "failsumm_log set to: $failsumm_log\n";
    if (($lim ne "") && ($lim != 0))
    {
        $log_hist_lim = $lim;
    }
    $ppid = getppid();
}

sub clear_log_hist
{
    @log_hist = ();
    $log_hist_count = 0;
}

sub add_log_hist
{
    my ($msg) = @_;
    push(@log_hist, $msg);
    if ($log_hist_count == $log_hist_lim)
    {
        shift(@log_hist);
    }
    else
    {
        ++$log_hist_count;
    }
}

sub add_log_hist_file
{
    my ($msg_file) = @_;
    my $msg_lines = `tail -${log_hist_lim} ${msg_file}`;
    chomp($msg_lines);
    my @msgs = split(/\n/, $msg_lines);
    foreach my $msg (@msgs)
    {
        add_log_hist("$msg\n");
    }
}

# write_log_hist
#    arg1 : Write history separator line? (blank=no, non-blank=yes, and use this text in it)
sub write_log_hist
{
    my ($septitle) = @_;

    if ($failsumm_log eq "")
    {
        return;
    }

    my $mach_var = $ENV{xmlvars_machine};

    # Append log history to failsumm_log file
    if (open(FSL, ">>$failsumm_log"))
    {
        if ($septitle ne "")
        {
            if ($mach_var ne "")
            {
                print FSL "\n----- $septitle (machine: $ENV{xmlvars_machine}) -----\n";
            }
            else
            {
                print FSL "\n----- $septitle -----\n";
            }

        }
        foreach my $msg (@log_hist)
        {
            print FSL "$msg";
        }
        close(FSL);
    }
    else
    {
        vprint "Unable to open $failsumm_log to write log history!  Continuing on...\n";
    }

    # Clear history for next write
    clear_log_hist();
}

sub trim
{
    my ($str) = @_;
    $str =~ s/^\s+//;
    $str =~ s/\s+$//;
    return $str;
}

                                                                            ###
# findRelFile
                                                                            ###
sub findRelFile
{
    my ($relname, $noerrormsg) = @_;
    my $fullname = "";

    vprint ">findRelFile($relname)\n";

    if ($relname =~ /^\//)
    {
        # Absolute path name specified...
        $fullname = $relname;
        if (! -e $fullname)
        {
            if (!$noerrormsg) { printErrorMsg("ERROR: could not find test script $fullname\n"); }
            $fullname = "";
        }
    }
    else
    {
	# Assume it's in $PATH
	$fullname = $relname;
    }

    vprint "<findRelFile($relname) returning: $fullname\n";
    return $fullname;
}

1;
