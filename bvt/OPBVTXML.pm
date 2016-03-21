#!/usr/bin/perl
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/bvt/run-op-bvt $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2016
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

# Run OpenPower automated build verification test (BVT)
#
# Author: Stewart Smith

package OPBVTXML;

use XML::LibXML;

sub bvt_xml_expand_all
{
    my ($xmlfile) = @_;

    my $parser = XML::LibXML->new();
    my $dom = XML::LibXML->load_xml(location => $xmlfile);
    $parser->process_xincludes($dom);

    for my $bvt_xml_node ($dom->findnodes('//*[local-name()="bvt-xml"]')) {
	# We treat <bvt-xml> as an include
	# so we grab the content of the file, insert it into the doc.
	my $bvt_xml_file = XML::LibXML->load_xml(location => $bvt_xml_node->textContent);
	$parser->process_xincludes($bvt_xml_file);
	$bvt_xml_node->replaceNode($bvt_xml_file->documentElement());
    }

    return $dom;
}

# Validate the syntax of the specified XML file
sub bvt_xml_is_valid
{
    my ($schemafn, $xmlfile) = @_;

    my $dom = bvt_xml_expand_all($xmlfile);

    # Validate the resulting XML
    my $xmlschema = XML::LibXML::Schema->new(location => $schemafn);

    return ! eval { $xmlschema->validate($dom) };
}

1;
