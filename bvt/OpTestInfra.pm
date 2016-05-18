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

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(set_verbose is_verbose_enabled vprint trim findRelFile);
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
